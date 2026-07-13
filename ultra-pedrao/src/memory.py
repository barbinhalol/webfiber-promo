# -*- coding: utf-8 -*-
"""Memória em 3 níveis (SQLite por padrão; estrutura pronta p/ Postgres):
 1) imediata  — últimas N mensagens da conversa
 2) resumo    — resumo textual atualizado (evita mandar histórico gigante ao modelo)
 3) fatos     — memória útil por contato (bairro, plano de interesse, já cliente, pendência...)
LGPD: expurgo por retenção; telefone mascarado em logs (feito na camada de log)."""
import sqlite3, json, os, time
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
"""

def _conn():
    os.makedirs(os.path.dirname(C.SQLITE_PATH), exist_ok=True)
    c = sqlite3.connect(C.SQLITE_PATH, timeout=10)
    c.execute("PRAGMA journal_mode=WAL")
    return c

def init():
    with _conn() as c:
        c.executescript(_DDL)

def add_mensagem(contato, external_key, de, texto):
    with _conn() as c:
        c.execute("INSERT INTO mensagens(contato,external_key,de,texto,ts) VALUES(?,?,?,?,?)",
                  (contato, external_key, de, texto, time.time()))

def historico(contato, n=None):
    n = n or C.MEM_MSGS_JANELA
    with _conn() as c:
        rows = c.execute("SELECT de,texto FROM mensagens WHERE contato=? ORDER BY id DESC LIMIT ?",
                         (contato, n)).fetchall()
    return [{"de": de, "texto": t} for de, t in reversed(rows)]

def get_resumo(contato):
    with _conn() as c:
        r = c.execute("SELECT texto FROM resumo WHERE contato=?", (contato,)).fetchone()
    return r[0] if r else ""

def set_resumo(contato, texto):
    with _conn() as c:
        c.execute("INSERT INTO resumo(contato,texto,ts) VALUES(?,?,?) "
                  "ON CONFLICT(contato) DO UPDATE SET texto=excluded.texto, ts=excluded.ts",
                  (contato, texto, time.time()))

def get_fatos(contato):
    with _conn() as c:
        r = c.execute("SELECT dados FROM fatos WHERE contato=?", (contato,)).fetchone()
    return json.loads(r[0]) if r and r[0] else {}

def merge_fatos(contato, novos: dict):
    if not novos: return get_fatos(contato)
    atual = get_fatos(contato)
    for k, v in novos.items():
        if v not in (None, "", {}, []):
            atual[k] = v
    with _conn() as c:
        c.execute("INSERT INTO fatos(contato,dados,ts) VALUES(?,?,?) "
                  "ON CONFLICT(contato) DO UPDATE SET dados=excluded.dados, ts=excluded.ts",
                  (contato, json.dumps(atual, ensure_ascii=False), time.time()))
    return atual

def log_evento(contato, tipo, payload):
    with _conn() as c:
        c.execute("INSERT INTO eventos(ts,contato,tipo,payload) VALUES(?,?,?,?)",
                  (time.time(), contato, tipo, json.dumps(payload, ensure_ascii=False, default=str)))

def expurgar():
    corte = time.time() - C.MEM_RETENCAO_DIAS * 86400
    with _conn() as c:
        for t in ("mensagens", "eventos"):
            c.execute(f"DELETE FROM {t} WHERE ts < ?", (corte,))
