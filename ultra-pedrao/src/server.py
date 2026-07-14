# -*- coding: utf-8 -*-
"""Servidor webhook do Ultra Pedrão (FastAPI).
Fluxo: FlowSeller -> POST /webhook -> filtros -> dedup -> debounce -> brain -> flowseller(shadow/live).
Modo sombra (BOT_MODE=shadow): decide e REGISTRA o que faria, sem enviar."""
import time, hashlib, json
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse

import config as C
import memory as M
import schedule as S
import brain as B
import flowseller as FS
import painel as PAINEL
from debounce import Debouncer

app = FastAPI(title="Ultra Pedrão", version="0.1.0")
M.init()

# Servir as imagens do /planos pela própria VPS (tudo num lugar só, busca rápida)
import os as _os
from fastapi.staticfiles import StaticFiles
_PLANOS_DIR = _os.path.join(_os.path.dirname(__file__), "..", "data", "planos")
_os.makedirs(_PLANOS_DIR, exist_ok=True)
app.mount("/planos", StaticFiles(directory=_PLANOS_DIR), name="planos")

_SEEN = {}  # idempotência: hash do evento -> ts (dedup de webhook repetido)
_SEEN_TTL = 600
_START_TS = time.time()

def _dedup(key: str) -> bool:
    now = time.time()
    for k, ts in list(_SEEN.items()):
        if now - ts > _SEEN_TTL: _SEEN.pop(k, None)
    if key in _SEEN: return True
    _SEEN[key] = now
    return False

def _mask(tel: str) -> str:
    tel = str(tel or "")
    return (tel[:4] + "***" + tel[-2:]) if len(tel) > 6 else "***"

# ---- extração defensiva do payload (formato exato do webhook = a confirmar no 1º real) ----
def _parse_evento(p: dict):
    """Normaliza campos comuns de webhooks estilo Whaticket/FlowSeller. Tolerante a variações."""
    def g(*ks, default=None):
        for k in ks:
            cur = p
            ok = True
            for part in k.split("."):
                if isinstance(cur, dict) and part in cur: cur = cur[part]
                else: ok = False; break
            if ok and cur not in (None, ""): return cur
        return default
    # A FlowSeller embrulha o evento em "message", com o ticket aninhado (message.ticket.contact...).
    numero = str(g("message.ticket.contact.number", "ticket.contact.number", "message.contact.number",
                   "contact.number", "number", "from", default=""))
    ticket_id = g("message.ticketId", "message.ticket.id", "ticket.id", "ticketId")
    contact_id = g("message.contactId", "message.ticket.contactId", "ticket.contactId", "contactId")
    return {
        # externalKey costuma vir null -> endereçamos pelo número (fallback), guardando ids p/ o envio
        "external_key": g("message.externalKey", "message.ticket.externalKey", "externalKey", "ticket.externalKey") or numero,
        "ticket_id": ticket_id,
        "contact_id": contact_id,
        "contato": numero,
        "nome": g("message.ticket.contact.name", "ticket.contact.name", "message.contact.name",
                  "contact.name", "pushName", default=""),
        "texto": g("message.body", "body", "message.caption", "text", "message.text",
                   "interactive.button_reply.title", default=""),
        "from_me": bool(g("message.fromMe", "fromMe", default=False)),
        "is_group": bool(g("message.ticket.isGroup", "message.isGroup", "ticket.isGroup", "isGroup", default=False)),
        "tipo": g("message.mediaType", "event", "type", "mediaType", "message.type", default="chat"),
        "media_url": g("message.mediaUrl", "mediaUrl", default=None),
        "ts": g("message.timestamp", "message.msgCreatedAt", "timestamp", "ts", default=time.time()),
        "_raw": p,
    }

def _processar(contato, texto, ctx):
    """Chamado pelo debouncer após agrupar as mensagens do contato."""
    ext = ctx.get("external_key")
    # sessão nova/reaberta: a FlowSeller cria um ticket_id novo quando o atendimento anterior
    # foi fechado. Comparamos com o último ticket_id visto pra esse contato -- se mudou (ou é o
    # primeiro contato), sinalizamos pro cérebro cumprimentar do jeito clássico.
    ticket_id_atual = ctx.get("ticket_id")
    ticket_id_anterior = M.get_ultimo_ticket(contato)
    sessao_nova = ticket_id_atual is not None and str(ticket_id_atual) != str(ticket_id_anterior)
    if ticket_id_atual is not None:
        M.set_ultimo_ticket(contato, ticket_id_atual)

    fatos = M.get_fatos(contato)
    hist = M.historico(contato)
    d = B.decidir(texto, historico=hist, memoria_cliente=fatos, sessao_nova=sessao_nova)

    M.add_mensagem(contato, ext, "cliente", texto)
    if d.get("dados_coletados"):
        M.merge_fatos(contato, d["dados_coletados"])
    # memória nível 2: atualiza o resumo quando a conversa cresce
    hist_full = M.historico(contato, n=C.MEM_RESUMO_APOS + 4)
    if len(hist_full) >= C.MEM_RESUMO_APOS:
        try: M.set_resumo(contato, B.resumir(hist_full, M.get_resumo(contato)))
        except Exception: pass

    resultado = FS.executar_decisao(ext, d, contato) if ext else {"erro": "sem external_key"}
    if d.get("acao") in ("responder", "fastreply") and d.get("texto"):
        M.add_mensagem(contato, ext, "pedrao", d["texto"])

    M.log_evento(contato, "decisao", {
        "mask": _mask(contato), "modo": C.BOT_MODE, "acao": d.get("acao"), "sessao_nova": sessao_nova,
        "viab": d.get("_viabilidade_sistema", {}).get("status"),
        "alertas": d.get("_alertas"), "render": d.get("_render"), "envio": resultado,
    })

_DEB = Debouncer(on_flush=_processar)

@app.get("/health")
def health():
    return {"ok": True, "uptime_s": int(time.time() - _START_TS), "config": C.resumo_seguro(),
            "atuaria_agora": S.deve_atuar()}

@app.post("/webhook")
async def webhook(request: Request, x_webhook_secret: str = Header(default=""),
                  authorization: str = Header(default="")):
    if C.FS_WEBHOOK_SECRET:
        # A FlowSeller manda o "Token de autenticação" no header Authorization
        # (com prefixo opcional, ex. "Bearer xxx"); aceitamos também X-Webhook-Secret.
        recebido = (x_webhook_secret or authorization or "").strip()
        for pref in ("bearer ", "token "):
            if recebido.lower().startswith(pref):
                recebido = recebido[len(pref):].strip()
        if recebido != C.FS_WEBHOOK_SECRET:
            raise HTTPException(status_code=401, detail="webhook secret inválido")
    p = await request.json()
    ev = _parse_evento(p)

    # DEBUG: captura o payload cru + como o parser leu (pra validar/ajustar o formato do webhook)
    if C.DEBUG_WEBHOOK:
        M.log_evento(ev.get("contato") or "?", "webhook_raw", {
            "raw": p,
            "parser_leu": {"external_key": ev["external_key"], "tem_texto": bool(ev["texto"]),
                           "texto": (ev["texto"] or "")[:120], "tipo": ev["tipo"],
                           "from_me": ev["from_me"], "is_group": ev["is_group"],
                           "contato_mask": _mask(ev["contato"])},
        })

    # idempotência (webhook repetido)
    key = hashlib.sha256((str(ev["external_key"]) + str(ev["texto"]) + str(ev["ts"])).encode()).hexdigest()
    if _dedup(key):
        return {"status": "duplicado_ignorado"}

    # FILTROS (não responder): própria empresa / grupo / mensagem antiga / vazia
    if ev["from_me"]:   return {"status": "ignorado_from_me"}
    if ev["is_group"]:  return {"status": "ignorado_grupo"}
    # liga/desliga pelo painel (o "botão" do dono, sem terminal)
    if not PAINEL.ativo():
        return {"status": "desligado_no_painel"}
    _modo = PAINEL.modo_efetivo(C.BOT_MODE)
    # modo teste OU piloto: processa só número(s) autorizado(s) — ignora o resto do movimento de produção
    _lista = C.TESTE_SO_NUMERO or (PAINEL.allowlist_efetiva(C.PILOT_ALLOWLIST) if _modo == "pilot" else [])
    if _lista:
        import re as _re
        num = _re.sub(r"\D", "", ev["contato"] or "")
        alvos = [_re.sub(r"\D", "", n) for n in _lista if n]
        # número vazio NUNCA passa (evita bug de ''.endswith casar com tudo)
        if len(num) < 8 or not any(num.endswith(n) or n.endswith(num) for n in alvos if n):
            return {"status": "ignorado_fora_da_allowlist"}
    try:
        if float(ev["ts"]) and (time.time() - float(ev["ts"])) > 3600 and float(ev["ts"]) < _START_TS:
            return {"status": "ignorado_msg_antiga"}
    except Exception:
        pass
    if not ev["texto"] and ev["tipo"] not in ("audio", "ptt", "voice"):
        return {"status": "ignorado_vazio"}

    # horário: Pedrão atua fora do expediente humano (FORCAR_ATUACAO ignora o gate p/ teste — segue shadow)
    if not S.deve_atuar() and not C.FORCAR_ATUACAO:
        M.log_evento(ev["contato"], "fora_de_atuacao",
                     {"mask": _mask(ev["contato"]), "tem_texto": bool(ev["texto"]), "tipo": ev["tipo"]})
        return {"status": "dentro_horario_humano_nao_atua"}

    # áudio: baixa e transcreve; se falhar, o cérebro pede confirmação por escrito (nunca finge que entendeu)
    texto = ev["texto"]
    if ev["tipo"] in ("audio", "ptt", "voice") and not texto:
        if ev.get("media_url"):
            import transcricao as TR
            t, erro = TR.transcrever(ev["media_url"], jwt=C.FS_JWT_RESPOSTA or None)
            if t:
                texto = t
                M.log_evento(ev["contato"], "audio_transcrito", {"mask": _mask(ev["contato"]), "chars": len(t)})
            else:
                texto = "[áudio recebido, mas não consegui transcrever — peça ao cliente pra confirmar por escrito]"
                M.log_evento(ev["contato"], "audio_falha", {"mask": _mask(ev["contato"]), "erro": erro})
        else:
            texto = "[áudio recebido sem link de mídia — peça confirmação por escrito]"

    _DEB.add(ev["contato"], texto, ctx={"external_key": ev["external_key"], "nome": ev["nome"], "ticket_id": ev["ticket_id"]})
    return {"status": "enfileirado", "modo": C.BOT_MODE, "contato": _mask(ev["contato"])}

# ---- admin protegido (inspeção do modo sombra) ----
def _admin(tok):
    if not C.ADMIN_TOKEN or tok != C.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="admin token inválido")

# ---- PAINEL DE CONTROLE (web, sem terminal) ----
from fastapi.responses import HTMLResponse, PlainTextResponse

def _auth_painel(tok):
    """Painel aceita: ADMIN_TOKEN (scripts) OU PAINEL_SENHA (env) OU a senha definida no painel."""
    if C.ADMIN_TOKEN and tok == C.ADMIN_TOKEN: return
    if C.PAINEL_SENHA and tok == C.PAINEL_SENHA: return
    if PAINEL.senha_ok(tok): return
    raise HTTPException(status_code=401, detail="senha inválida")

def _sem_senha(d):
    d = dict(d); d.pop("senha", None); return d  # nunca devolve a senha ao navegador

@app.get("/admin/painel")
def painel_get(x_admin_token: str = Header(default="")):
    _auth_painel(x_admin_token)
    return _sem_senha(PAINEL.ler())

@app.post("/admin/painel")
async def painel_post(request: Request, x_admin_token: str = Header(default="")):
    _auth_painel(x_admin_token)
    body = await request.json()
    return _sem_senha(PAINEL.salvar(body))

_PAINEL_PATH = _os.path.join(_os.path.dirname(__file__), "painel.html")
@app.get("/painel", response_class=HTMLResponse)
def painel_html():
    try:
        with open(_PAINEL_PATH, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "<h1>Painel indisponivel</h1>"


@app.get("/admin/eventos")
def admin_eventos(x_admin_token: str = Header(default=""), limite: int = 50):
    _auth_painel(x_admin_token)
    import sqlite3
    con = sqlite3.connect(C.SQLITE_PATH)
    rows = con.execute("SELECT ts,contato,tipo,payload FROM eventos ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
    con.close()
    return [{"ts": r[0], "tipo": r[2], "payload": json.loads(r[3])} for r in rows]

@app.get("/admin/testar-llm")
def admin_testar_llm(x_admin_token: str = Header(default="")):
    """Verifica se o cérebro (LLM/token) está vivo — use pra detectar token de 1 ano vencido."""
    _admin(x_admin_token)
    import llm as L, time as _t
    t0 = _t.time()
    try:
        r = L.gerar("Responda só: OK", "diga OK")
        return {"ok": True, "provider": C.LLM_PROVIDER, "ms": int((_t.time()-t0)*1000), "amostra": (r or "")[:60]}
    except Exception as e:
        return JSONResponse(status_code=503, content={"ok": False, "provider": C.LLM_PROVIDER, "erro": str(e)})

@app.post("/admin/simular")
async def admin_simular(request: Request, x_admin_token: str = Header(default="")):
    """Testa uma mensagem sem passar pela FlowSeller: retorna a decisão do cérebro."""
    _admin(x_admin_token)
    body = await request.json()
    d = B.decidir(body.get("texto", ""), historico=body.get("historico", []),
                  memoria_cliente=body.get("memoria", {}), sessao_nova=bool(body.get("sessao_nova", False)))
    return {"decisao": {k: v for k, v in d.items() if not k.startswith("_")},
            "viabilidade_sistema": d.get("_viabilidade_sistema"),
            "alertas": d.get("_alertas"), "render": d.get("_render")}
