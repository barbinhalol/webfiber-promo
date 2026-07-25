# -*- coding: utf-8 -*-
"""Memória em 3 níveis (SQLite por padrão; estrutura pronta p/ Postgres):
 1) imediata  — últimas N mensagens da conversa
 2) resumo    — resumo textual atualizado (evita mandar histórico gigante ao modelo)
 3) fatos     — memória útil por contato (bairro, plano de interesse, já cliente, pendência...)
LGPD: expurgo por retenção; telefone mascarado em logs (feito na camada de log)."""
import sqlite3, json, os, time, threading, contextlib
import config as C

_DDL = """
CREATE TABLE IF NOT EXISTS mensagens(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  contato TEXT, external_key TEXT, de TEXT, texto TEXT, ts REAL
);
CREATE INDEX IF NOT EXISTS ix_msg_contato ON mensagens(contato, ts);
CREATE TABLE IF NOT EXISTS resumo(contato TEXT PRIMARY KEY, texto TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS fatos(contato TEXT PRIMARY KEY, dados TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS eventos(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, contato TEXT, tipo TEXT, payload TEXT
);
CREATE TABLE IF NOT EXISTS sessao(contato TEXT PRIMARY KEY, ticket_id TEXT, ts REAL);
-- PERF (25/07): a query real de histórico é "WHERE contato=? ORDER BY id DESC" -- o índice
-- antigo era (contato, ts) e obrigava o SQLite a ordenar em memória. (contato, id) serve
-- direto. E eventos(ts) evita full scan no expurgo diário.
CREATE INDEX IF NOT EXISTS ix_msg_contato_id ON mensagens(contato, id);
CREATE INDEX IF NOT EXISTS ix_eventos_ts ON eventos(ts);
CREATE INDEX IF NOT EXISTS ix_fatos_ts ON fatos(ts);
"""

# PERF (25/07): antes cada função abria uma conexão NOVA -- os.makedirs + connect + PRAGMA
# journal_mode=WAL (grava no disco) por chamada. Uma única mensagem de cliente dispara dezenas
# dessas (get_fatos, log_evento, histórico, resumo, sessão...), e ainda por cima dentro do
# event loop async, travando os outros webhooks. Agora: UMA conexão global (WAL permite vários
# leitores + 1 escritor) protegida por lock, criada uma vez. Mantém a API igual -- só troca
# `with _conn() as c` por `with _db() as c`.
_DB_LOCK = threading.RLock()
_CONN = None

def _conn():
    global _CONN
    if _CONN is None:
        with _DB_LOCK:
            if _CONN is None:
                d = os.path.dirname(C.SQLITE_PATH)
                if d:
                    os.makedirs(d, exist_ok=True)
                c = sqlite3.connect(C.SQLITE_PATH, timeout=10, check_same_thread=False)
                c.execute("PRAGMA journal_mode=WAL")
                # com WAL, synchronous=NORMAL é seguro (só perde transações no crash do SO,
                # não corrompe) e evita um fsync por escrita -- o ganho é grande num bot que
                # grava log a cada passo.
                c.execute("PRAGMA synchronous=NORMAL")
                c.execute("PRAGMA temp_store=MEMORY")
                c.execute("PRAGMA cache_size=-8000")   # ~8MB de cache de páginas
                _CONN = c
    return _CONN

@contextlib.contextmanager
def _db():
    """Conexão compartilhada + commit/rollback, serializada por lock (as queries são de
    microssegundos; o lock nunca é o gargalo e evita 'database is locked')."""
    c = _conn()
    with _DB_LOCK:
        try:
            yield c
            c.commit()
        except Exception:
            try: c.rollback()
            except Exception: pass
            raise

def init():
    with _db() as c:
        c.executescript(_DDL)

def add_mensagem(contato, external_key, de, texto):
    with _db() as c:
        c.execute("INSERT INTO mensagens(contato,external_key,de,texto,ts) VALUES(?,?,?,?,?)",
                  (contato, external_key, de, texto, time.time()))

def historico(contato, n=None):
    n = n or C.MEM_MSGS_JANELA
    with _db() as c:
        rows = c.execute("SELECT de,texto FROM mensagens WHERE contato=? ORDER BY id DESC LIMIT ?",
                         (contato, n)).fetchall()
    return [{"de": de, "texto": t} for de, t in reversed(rows)]

def get_resumo(contato):
    with _db() as c:
        r = c.execute("SELECT texto FROM resumo WHERE contato=?", (contato,)).fetchone()
    return r[0] if r else ""

def set_resumo(contato, texto):
    with _db() as c:
        c.execute("INSERT INTO resumo(contato,texto,ts) VALUES(?,?,?) "
                  "ON CONFLICT(contato) DO UPDATE SET texto=excluded.texto, ts=excluded.ts",
                  (contato, texto, time.time()))

def get_fatos(contato):
    with _db() as c:
        r = c.execute("SELECT dados FROM fatos WHERE contato=?", (contato,)).fetchone()
    return json.loads(r[0]) if r and r[0] else {}

def merge_fatos(contato, novos: dict):
    if not novos: return get_fatos(contato)
    atual = get_fatos(contato)
    for k, v in novos.items():
        if v not in (None, "", {}, []):
            atual[k] = v
    with _db() as c:
        c.execute("INSERT INTO fatos(contato,dados,ts) VALUES(?,?,?) "
                  "ON CONFLICT(contato) DO UPDATE SET dados=excluded.dados, ts=excluded.ts",
                  (contato, json.dumps(atual, ensure_ascii=False), time.time()))
    return atual

def get_ultimo_ticket(contato):
    """Ultimo ticket_id visto pra esse contato -- usado pra detectar atendimento novo/reaberto
    (a FlowSeller cria um ticket_id novo quando o atendimento anterior foi fechado)."""
    with _db() as c:
        r = c.execute("SELECT ticket_id FROM sessao WHERE contato=?", (contato,)).fetchone()
    return r[0] if r else None

def set_ultimo_ticket(contato, ticket_id):
    with _db() as c:
        c.execute("INSERT INTO sessao(contato,ticket_id,ts) VALUES(?,?,?) "
                  "ON CONFLICT(contato) DO UPDATE SET ticket_id=excluded.ticket_id, ts=excluded.ts",
                  (contato, str(ticket_id) if ticket_id is not None else None, time.time()))

def ultimo_external_key(contato):
    """external_key mais recente do contato — usado pra postar a nota interna sem uma msg nova."""
    with _db() as c:
        r = c.execute("SELECT external_key FROM mensagens WHERE contato=? AND external_key IS NOT NULL "
                      "ORDER BY id DESC LIMIT 1", (contato,)).fetchone()
    return r[0] if r else None

def contatos_nota_pendente(min_seg):
    """ORDEM DO DONO (14/07/2026): a nota interna do lead NÃO sai na hora — sai ~20 min depois,
    mesmo que o cliente tenha sumido. Devolve [(contato, fatos)] cuja conversa começou há
    >= min_seg e que ainda não receberam a nota (fatos['nota_ok'])."""
    agora = time.time()
    pend = []
    with _db() as c:
        # PERF (25/07): era "SELECT contato,dados FROM fatos" -- varria a tabela INTEIRA (milhares
        # de contatos) a cada tick do vigia. Um lead só vira pendente se o fato foi mexido há
        # pouco; nada com 2 dias parados entra. Usa ix_fatos_ts.
        rows = c.execute("SELECT contato, dados FROM fatos WHERE ts >= ?",
                         (agora - 172800,)).fetchall()
    for contato, dados in rows:
        try:
            d = json.loads(dados) if dados else {}
        except Exception:
            continue
        ini = d.get("lead_ts")
        if not ini or d.get("nota_ok"):
            continue
        try:
            if agora - float(ini) >= min_seg:
                pend.append((contato, d))
        except Exception:
            continue
    return pend

def log_evento(contato, tipo, payload):
    with _db() as c:
        c.execute("INSERT INTO eventos(ts,contato,tipo,payload) VALUES(?,?,?,?)",
                  (time.time(), contato, tipo, json.dumps(payload, ensure_ascii=False, default=str)))

def expurgar():
    corte = time.time() - C.MEM_RETENCAO_DIAS * 86400
    with _db() as c:
        for t in ("mensagens", "eventos"):
            c.execute(f"DELETE FROM {t} WHERE ts < ?", (corte,))
