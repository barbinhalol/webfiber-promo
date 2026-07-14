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
    fatos = M.get_fatos(contato)
    hist = M.historico(contato)
    d = B.decidir(texto, historico=hist, memoria_cliente=fatos)

    M.add_mensagem(contato, ext, "cliente", texto)
    if d.get("dados_coletados"):
        M.merge_fatos(contato, d["dados_coletados"])
    # memória nível 2: atualiza o resumo quando a conversa cresce
    hist_full = M.historico(contato, n=C.MEM_RESUMO_APOS + 4)
    if len(hist_full) >= C.MEM_RESUMO_APOS:
        try: M.set_resumo(contato, B.resumir(hist_full, M.get_resumo(contato)))
        except Exception: pass

    resultado = FS.executar_decisao(ext, d) if ext else {"erro": "sem external_key"}
    if d.get("acao") in ("responder", "fastreply") and d.get("texto"):
        M.add_mensagem(contato, ext, "pedrao", d["texto"])

    M.log_evento(contato, "decisao", {
        "mask": _mask(contato), "modo": C.BOT_MODE, "acao": d.get("acao"),
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

    _DEB.add(ev["contato"], texto, ctx={"external_key": ev["external_key"], "nome": ev["nome"]})
    return {"status": "enfileirado", "modo": C.BOT_MODE, "contato": _mask(ev["contato"])}

# ---- admin protegido (inspeção do modo sombra) ----
def _admin(tok):
    if not C.ADMIN_TOKEN or tok != C.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="admin token inválido")

# ---- PAINEL DE CONTROLE (web, sem terminal) ----
from fastapi.responses import HTMLResponse, PlainTextResponse

@app.get("/admin/painel")
def painel_get(x_admin_token: str = Header(default="")):
    _admin(x_admin_token)
    return PAINEL.ler()

@app.post("/admin/painel")
async def painel_post(request: Request, x_admin_token: str = Header(default="")):
    _admin(x_admin_token)
    body = await request.json()
    return PAINEL.salvar(body)

@app.get("/painel", response_class=HTMLResponse)
def painel_html():
    return _PAINEL_HTML

_PAINEL_HTML = """<!doctype html><html lang=pt-br><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Painel do Pedrão</title>
<style>
:root{--bg:#0b1220;--card:#131c2e;--ac:#2f81f7;--ok:#1f9d55;--off:#b23;--tx:#e8eef7;--mut:#8aa0bd}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:16px/1.5 system-ui,Arial;padding:16px}
.wrap{max-width:640px;margin:0 auto}h1{font-size:20px;margin:6px 0 2px}.sub{color:var(--mut);font-size:13px;margin-bottom:16px}
.card{background:var(--card);border:1px solid #223;border-radius:14px;padding:16px;margin-bottom:14px}
label{display:block;font-weight:600;margin:0 0 6px}.hint{color:var(--mut);font-size:13px;margin:-2px 0 10px}
textarea,input,select{width:100%;background:#0d1526;color:var(--tx);border:1px solid #2a3b57;border-radius:10px;padding:10px;font:15px system-ui}
textarea{min-height:80px;resize:vertical}.row{display:flex;gap:10px;align-items:center}
.switch{display:flex;gap:10px;align-items:center;font-weight:700}
button{background:var(--ac);color:#fff;border:0;border-radius:10px;padding:12px 16px;font-size:16px;font-weight:700;width:100%;cursor:pointer}
.badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:13px;font-weight:700}
.on{background:rgba(31,157,85,.2);color:#6ee7a0}.offb{background:rgba(180,40,50,.2);color:#ff8f9a}
.msg{margin-top:10px;font-size:14px;color:var(--mut)}.tag{font-size:12px;color:var(--mut)}
.pill{background:#0d1526;border:1px solid #2a3b57;border-radius:10px;padding:8px 10px;font-size:13px;color:var(--mut);margin-top:8px;white-space:pre-wrap}
</style></head><body><div class=wrap>
<h1>🐺 Painel do Ultra Pedrão</h1>
<div class=sub>Controle sem terminal. As mudanças valem na hora.</div>

<div class=card id=gate>
<label>Senha do painel</label>
<div class=hint>É o ADMIN_TOKEN da VPS. Fica salvo só neste aparelho.</div>
<input id=tok type=password placeholder="cole a senha aqui" autocomplete=off>
<div style=height:10px></div><button onclick=entrar()>Entrar</button>
<div class=msg id=gmsg></div>
</div>

<div id=app style=display:none>
<div class=card>
<div class="switch"><span>Status do Pedrão:</span> <span id=stbadge class=badge>—</span></div>
<div style=height:12px></div>
<button id=btnliga onclick=toggle()>Ligar / Desligar</button>
<div class=hint style=margin-top:8px>Desligado = ele não responde ninguém (útil quando você volta pro Pedrão antigo no canal).</div>
</div>

<div class=card>
<label>Quem ele responde</label>
<select id=modo>
<option value="">(padrão do servidor)</option>
<option value="pilot">Só os números da lista (teste)</option>
<option value="live">TODOS os clientes (produção)</option>
<option value="shadow">Ninguém — só observa (sombra)</option>
</select>
<div style=height:10px></div>
<label>Números do teste (piloto)</label>
<div class=hint>Separe por vírgula. Ex.: 21964450618</div>
<input id=allow placeholder="21964450618">
</div>

<div class=card>
<div class=row style=justify-content:space-between>
<label style=margin:0>⚠️ Aviso urgente (rede/rompimento)</label>
<span class="switch"><input type=checkbox id=avon style=width:auto> <span class=tag>ativo</span></span>
</div>
<div class=hint>Ex.: "Caiu fibra em São Conrado, previsão de volta após 18h. Avise os clientes que perguntarem."</div>
<textarea id=aviso placeholder="deixe vazio quando não houver aviso"></textarea>
</div>

<div class=card>
<label>Ajustes de atendimento</label>
<div class=hint>Escreva em português o que ele deve ou não fazer. Ex.: "Não fale em quantidade de clientes. Seja mais breve nas saudações."</div>
<textarea id=ajustes placeholder="instruções livres pro Pedrão"></textarea>
</div>

<button onclick=salvar()>💾 Salvar tudo</button>
<div class=msg id=msg></div>
</div>

<script>
let TOK=localStorage.getItem('pedrao_tok')||'';
const $=id=>document.getElementById(id);
async function api(m,b){const r=await fetch('/admin/painel',{method:m,headers:{'X-Admin-Token':TOK,'content-type':'application/json'},body:b?JSON.stringify(b):undefined});if(r.status===401)throw'senha';return r.json()}
function pintar(p){$('stbadge').textContent=p.ativo?'LIGADO':'DESLIGADO';$('stbadge').className='badge '+(p.ativo?'on':'offb');
$('modo').value=p.modo||'';$('allow').value=p.allowlist||'';$('aviso').value=p.aviso||'';$('avon').checked=!!p.aviso_ativo;$('ajustes').value=p.ajustes||''}
let ATUAL={};
async function carregar(){try{ATUAL=await api('GET');pintar(ATUAL);$('gate').style.display='none';$('app').style.display='block'}catch(e){$('gmsg').textContent='Senha inválida.';localStorage.removeItem('pedrao_tok')}}
function entrar(){TOK=$('tok').value.trim();localStorage.setItem('pedrao_tok',TOK);carregar()}
async function toggle(){ATUAL=await api('POST',{ativo:!ATUAL.ativo});pintar(ATUAL);$('msg').textContent='Status alterado.'}
async function salvar(){ATUAL=await api('POST',{modo:$('modo').value,allowlist:$('allow').value,aviso:$('aviso').value,aviso_ativo:$('avon').checked,ajustes:$('ajustes').value});pintar(ATUAL);$('msg').textContent='✅ Salvo! Vale a partir de agora.'}
if(TOK)carregar();
</script></div></body></html>"""

@app.get("/admin/eventos")
def admin_eventos(x_admin_token: str = Header(default=""), limite: int = 50):
    _admin(x_admin_token)
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
                  memoria_cliente=body.get("memoria", {}))
    return {"decisao": {k: v for k, v in d.items() if not k.startswith("_")},
            "viabilidade_sistema": d.get("_viabilidade_sistema"),
            "alertas": d.get("_alertas"), "render": d.get("_render")}
