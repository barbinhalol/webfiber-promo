# -*- coding: utf-8 -*-
"""Servidor webhook do Ultra Pedrão (FastAPI).
Fluxo: FlowSeller -> POST /webhook -> filtros -> dedup -> debounce -> brain -> flowseller(shadow/live).
Modo sombra (BOT_MODE=shadow): decide e REGISTRA o que faria, sem enviar."""
import time, hashlib, json, asyncio, re
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse

import config as C
import memory as M
import schedule as S
import brain as B
import flowseller as FS
import painel as PAINEL
import sentimento as SENT
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

# ---- NOTA INTERNA DO LEAD (ordem do dono 14/07/2026) ----
# A nota NÃO sai na hora: sai ~20 min depois do início da conversa, e sai MESMO se o cliente sumiu
# (a equipe não pode perder o resumo do lead). Exceção: transferência mantém a nota na hora, senão
# o humano recebe o ticket sem contexto nenhum.
NOTA_APOS_S = 15 * 60   # dono: nota interna do lead ~10-15 min depois
_VIGIA_INTERVALO_S = 120

def _fmt_tel(contato):
    d = re.sub(r"\D", "", str(contato or ""))
    if d.startswith("55") and len(d) > 11:
        d = d[2:]
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return d or str(contato or "")

def _texto_nota_lead(contato, fatos):
    """Resumo do lead pro time — DESCREVE TUDO (telefone, nome, o que quer, dados coletados)."""
    linhas = ["[Pedrão · resumo do lead]"]
    linhas.append("📱 Telefone: " + _fmt_tel(contato))
    nome = (fatos.get("nome") or fatos.get("sup_nome") or "").strip()
    if nome:
        linhas.append("👤 Nome: " + nome)
    resumo = (M.get_resumo(contato) or "").strip()
    if resumo:
        linhas.append("📝 Conversa: " + resumo)
    rotulos = {"endereco": "Endereço", "sup_end": "Endereço (cadastro)", "rua": "Rua", "numero": "Número",
               "bairro": "Bairro", "plano_interesse": "Plano de interesse", "plano": "Plano",
               "cpf": "CPF", "cnpj": "CNPJ"}
    dados = [f"• {rot}: {fatos.get(k)}" for k, rot in rotulos.items() if str(fatos.get(k) or "").strip()]
    if dados:
        linhas.append("📋 Dados coletados:"); linhas += dados
    if len(linhas) <= 2:   # só header + telefone
        linhas.append("Cliente conversou com o Pedrão; ainda sem dados estruturados coletados.")
    return "\n".join(linhas)

async def _vigia_notas():
    """Posta a nota interna do lead ~15 min após o início da conversa, mesmo sem mensagem nova.
    Posta UMA VEZ só: marca nota_ok logo após a tentativa (a FlowSeller cria a nota mas às vezes
    não devolve id, então NÃO dá pra confiar no 'enviado' — sem isso, ficava repetindo a cada 2 min)."""
    while True:
        try:
            for contato, fatos in M.contatos_nota_pendente(NOTA_APOS_S):
                ext = M.ultimo_external_key(contato)
                if not ext:
                    continue
                M.merge_fatos(contato, {"nota_ok": 1})   # ANTES de postar: garante 1x só (nunca spam)
                texto = _texto_nota_lead(contato, fatos)
                if "ainda sem dados" in texto:   # conversa vazia (só "oi") -> não incomoda o time
                    continue
                # to_thread: a chamada de rede NÃO pode bloquear o event loop (senão trava o webhook)
                r = await asyncio.to_thread(FS.nota_interna, ext, texto, number=contato, delay=False)
                M.log_evento(contato, "nota_lead", {"mask": _mask(contato), "enviado": bool(r.get("enviado"))})
        except Exception as e:
            print("[vigia_notas] erro:", e, flush=True)
        await asyncio.sleep(_VIGIA_INTERVALO_S)

@app.on_event("startup")
async def _ligar_vigia():
    asyncio.create_task(_vigia_notas())

# SENTINELA ANTI-DUPLO-BOT (incidente 15-16/07/2026: canal trocado pro chatbot NATIVO da
# FlowSeller e o Pedrao continuou respondendo -> DOIS bots na mesma conversa). Os menus do
# nativo chegam aqui pelo webhook como mensagem do NOSSO numero (fromMe). Ao reconhecer um,
# o Pedrao se PAUSA sozinho por 10 min (renovado a cada menu). Assim a troca do canal na
# FlowSeller vira o UNICO interruptor -- sem precisar lembrar do painel.
_MENU_NATIVO = re.compile(
    r"(\b[123]\s*-\s*(FALAR COM ATENDENTE|PLANOS\s*/?\s*COMERCIAL|FINANCEIRO)\b|"
    r"Escolha uma (op[çc][ãa]o|das op[çc][õo]es)|"
    r"N[ãa]o entendi sua resposta\.?\s*Vamos tentar novamente)", re.I)

# ==================== COPILOTO FINANCEIRO (ordem do dono 24/07/2026) ====================
# Durante o HORÁRIO HUMANO, quem clica "FINANCEIRO" no menu cai na fila 25 e esperava atendente
# até pra pegar 2ª via. O copiloto entrega a fatura (Pix+boleto) na fila, assinado
# "*Financeiro WebFiber*" (sem se apresentar como robô). Regras: atendente ACEITAR não o para
# (aceitam e demoram); atendente DIGITAR qualquer coisa -> silencia naquele ticket na hora.
FILA_FINANCEIRO = C.FILAS.get("financeiro", 25)
_COP_KW = re.compile(r"(financeiro|fatura|boleto|pix|2\s*ª?\s*via|segunda\s+via|pagamento|"
                     r"c[óo]digo\s+de\s+barras|linha\s+digit|vencimento|pagar)", re.I)

_BOT_TXT = {}  # contato -> [(ts, texto enviado por nós)] — p/ distinguir humano de bot no fromMe

def _registra_txt(contato, texto):
    t = (texto or "").strip()
    if not t:
        return
    l = _BOT_TXT.setdefault(contato, [])
    l.append((time.time(), t))
    del l[:-20]

def _txt_do_bot(contato, texto) -> bool:
    """True se a mensagem fromMe foi gerada por BOT (nosso ou menu nativo) — não por um humano."""
    t = (texto or "").strip()
    if not t:
        return True
    if t.startswith("*Pedrão") or t.startswith("*Financeiro"):
        return True
    # menus de botão (nativo/submenus): linhas "1 - ..." ou "Escolha ..."
    if re.search(r"^\s*\d\s*-\s*\S", t, re.M) or re.search(r"escolha", t, re.I):
        return True
    # pedaços da entrega de fatura sem assinatura (Pix copia-e-cola EMV, linha digitável, avisos)
    if re.match(r"^000201", t) or re.match(r"^[\d\s.]{40,}$", t):
        return True
    if ("Linha digitável" in t or "Pra pagar na hora" in t or "Achei sua fatura" in t
            or "Ou pague pelo boleto" in t or t.startswith("⏱️")):
        return True
    now = time.time()
    for ts, txt in _BOT_TXT.get(contato, []):
        if now - ts < 3600 and (txt == t or t.startswith(txt[:60])):
            return True
    return False

def _copiloto(ev):
    """Atende a fila do Financeiro em modo 'invisível': só fatura, e só até um humano digitar."""
    import mycore as MC
    import respostas as R
    contato, ext = ev["contato"], ev["external_key"]
    texto = str(ev["texto"])
    fatos = M.get_fatos(contato)
    cpf = MC.extrair_cpf_cnpj(texto)
    if cpf and MC.token_configurado():
        try:
            res = MC.resolver_fatura(cpf, contato)
        except Exception:
            res = {"status": "fallback", "motivo": "excecao"}
        if res.get("status") == "entregue":
            primeiro = True
            for e in res["envios"]:
                if e.get("tipo") == "pdf" and e.get("url"):
                    FS.enviar_midia(ext, e["url"], legenda=e.get("text") or "", number=contato, delay=False)
                else:
                    FS.responder_texto(
                        ext, e.get("text", ""), number=contato, delay=primeiro,
                        assinar=primeiro, marca=FS.ASSIN_FINANCEIRO,
                        nota=("[Copiloto Financeiro] Fatura entregue automaticamente (Pix + boleto) "
                              "pelo CPF informado no chat." if primeiro else None))
                    _registra_txt(contato, e.get("text", ""))
                primeiro = False
            M.log_evento(contato, "copiloto", {"mask": _mask(contato), "acao": "fatura_entregue"})
            return {"status": "copiloto_fatura_entregue"}
        if res.get("status") == "sem_fatura":
            t = ("Boa notícia! 😊 Não encontrei nenhuma fatura em aberto no seu CPF — está tudo em dia. "
                 "Precisando de mais alguma coisa do Financeiro, é só falar por aqui.")
            FS.responder_texto(ext, t, number=contato, delay=False, marca=FS.ASSIN_FINANCEIRO,
                               nota="[Copiloto Financeiro] CPF consultado: sem fatura em aberto.")
            _registra_txt(contato, t)
            M.log_evento(contato, "copiloto", {"mask": _mask(contato), "acao": "sem_fatura"})
            return {"status": "copiloto_sem_fatura"}
        # não achou o CPF / MyCore fora: manda o link oficial e deixa o humano seguir (sem transferir — já está na fila)
        FS.responder_texto(ext, R.FINANCEIRO_FATURA, number=contato, delay=False, marca=FS.ASSIN_FINANCEIRO,
                           nota="[Copiloto Financeiro] Não localizei pelo CPF (ou sistema fora); "
                                "enviei o link da área do cliente. Atendimento humano segue normal.")
        M.log_evento(contato, "copiloto", {"mask": _mask(contato), "acao": "fallback_link"})
        return {"status": "copiloto_fallback"}
    if _COP_KW.search(texto):
        # pergunta 1x (não fica repetindo se a pessoa clicar em vários botões)
        try:
            if time.time() - float(fatos.get("cop_ask_ts") or 0) < 600:
                return {"status": "copiloto_ja_perguntou"}
        except Exception:
            pass
        t = ("Posso te ajudar por aqui mesmo 😊 Você deseja a sua *fatura* (Pix ou boleto)?\n\n"
             "É só me enviar abaixo os números do seu *CPF* que eu já te envio.")
        FS.responder_texto(ext, t, number=contato, delay=False, marca=FS.ASSIN_FINANCEIRO)
        _registra_txt(contato, t)
        M.merge_fatos(contato, {"cop_ask_ts": time.time()})
        M.log_evento(contato, "copiloto", {"mask": _mask(contato), "acao": "pediu_cpf"})
        return {"status": "copiloto_pediu_cpf"}
    # assunto que não é fatura -> silêncio absoluto (humano cuida)
    return {"status": "copiloto_silencio"}

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
        # sinais de que um HUMANO/departamento já assumiu (pra o bot NÃO atropelar o atendimento):
        "status": str(g("message.ticket.status", "ticket.status", "status", default="")).lower(),
        "user_id": g("message.ticket.userId", "ticket.userId", "message.userId", "userId", default=None),
        "queue_id": g("message.ticket.queueId", "ticket.queueId", "message.queueId", "queueId", default=None),
        "_raw": p,
    }

def _processar(contato, texto, ctx):
    """Chamado pelo debouncer após agrupar as mensagens do contato."""
    ext = ctx.get("external_key")
    # SENTINELA — 2ª checagem (pós-debounce), fecha a CORRIDA DO 1º BALÃO: na 1ª mensagem de uma
    # conversa nova, o menu nativo e o Pedrão reagem À MESMA mensagem ao mesmo tempo; no instante
    # do webhook o menu ainda não tinha saído, então a 1ª checagem não pegava. Aqui já passaram os
    # ~2s do agrupamento -> o menu nativo já chegou (fromMe) e marcou o painel -> o Pedrão desiste.
    if PAINEL.bot_nativo_ativo():
        M.log_evento(contato, "pausado_bot_nativo_pos_debounce", {"mask": _mask(contato)})
        return
    # sessão nova/reaberta: a FlowSeller cria um ticket_id novo quando o atendimento anterior
    # foi fechado. Comparamos com o último ticket_id visto pra esse contato -- se mudou (ou é o
    # primeiro contato), sinalizamos pro cérebro cumprimentar do jeito clássico.
    ticket_id_atual = ctx.get("ticket_id")
    ticket_id_anterior = M.get_ultimo_ticket(contato)
    sessao_nova = ticket_id_atual is not None and str(ticket_id_atual) != str(ticket_id_anterior)
    if ticket_id_atual is not None:
        M.set_ultimo_ticket(contato, ticket_id_atual)

    fatos = M.get_fatos(contato)
    # marca o INÍCIO da conversa (o vigia usa isso pra postar a nota do lead 20 min depois)
    if sessao_nova or not fatos.get("lead_ts"):
        _ini = time.time()
        M.merge_fatos(contato, {"lead_ts": _ini, "nota_ok": 0})
        fatos["lead_ts"] = _ini; fatos["nota_ok"] = 0
    hist = M.historico(contato)
    resumo = M.get_resumo(contato)  # memória nível 2 (agora É usada na decisão)
    # humor do cliente (código, sem LLM): adapta o tom, tira o irritado do atalho, e pinta o painel
    _ctx_txt = " ".join(h.get("texto", "") for h in hist[-4:])
    sent = SENT.classificar(texto, _ctx_txt)
    # sessão nova zera qualquer roteiro de suporte pendente (não arrasta estado velho pra conversa nova)
    if sessao_nova and fatos.get("sup") in ("1", "2"):
        M.merge_fatos(contato, {"sup": "fim"}); fatos["sup"] = "fim"
    # ORDEM DO DONO: conversa FECHADA pelo atendente -> a FlowSeller abre um TICKET NOVO
    # (sessao_nova=True) -> o Pedrão começa DO ZERO, SEM a memória da conversa anterior (não
    # recapitula). Se NÃO foi fechada (mesmo ticket), continua com todo o contexto. EXCEÇÃO: se o
    # cliente citar algo dito antes ("você não viu aqui em cima", "já te falei"), aí lê o histórico.
    _fresh = sessao_nova and not B.refere_anterior(texto)
    hist_b = [] if _fresh else hist
    resumo_b = "" if _fresh else resumo
    fatos_b = {} if _fresh else fatos
    d = B.fastpath(texto, sessao_nova, hist_b, fatos_b, sentimento=sent, contato=contato)
    if d is None:
        d = B.decidir(texto, historico=hist_b, memoria_cliente=fatos_b, sessao_nova=sessao_nova, resumo=resumo_b, sentimento=sent)
        # se havia roteiro de suporte em andamento e o LLM assumiu, encerra o roteiro (evita ficar preso)
        if fatos.get("sup") in ("1", "2"):
            d.setdefault("dados_coletados", {})["sup"] = "fim"

    # ANTI-DUPLICATA DE PLANOS: se ja mandou o pacote de planos+imagens ha < 3 min, NAO repete
    # (o cliente mandava o endereco em 2 msgs e recebia os planos 2x). So referencia o que ja foi enviado.
    _eh_planos = d.get("acao") == "fastreply" and d.get("fastReplyId") in (1296, 1437, 1438)
    _ult_planos = fatos_b.get("planos_ts")   # fresco na sessão nova (não arrasta do fechado)
    if _eh_planos and _ult_planos and (time.time() - float(_ult_planos)) < 180:
        d = {"acao": "responder", "fastReplyId": 0, "fila": 0, "intencao": "planos",
             "texto": "Os planos são esses que te mandei aqui em cima 👆 Qual deles fez mais sentido pra você?",
             "viabilidade": "naoaplicavel", "motivo": "", "nota_interna": "", "dados_coletados": {},
             "_alertas": ["cooldown planos (nao repetiu imagens)"], "_fastpath": True,
             "_viabilidade_sistema": d.get("_viabilidade_sistema", {}), "_render": "💬 (cooldown) planos ja enviados"}
    elif _eh_planos:
        d.setdefault("dados_coletados", {})["planos_ts"] = time.time()

    # ORDEM DO DONO: nada de nota interna na hora — a nota do lead sai no vigia dos 20 min.
    # EXCEÇÃO: na TRANSFERÊNCIA a nota vai junto (o humano precisa do contexto ao pegar o ticket).
    if d.get("acao") != "transferir" and d.get("nota_interna"):
        d["nota_interna"] = ""

    M.add_mensagem(contato, ext, "cliente", texto)
    if d.get("dados_coletados"):
        M.merge_fatos(contato, d["dados_coletados"])
    # memória nível 2: atualiza o resumo quando a conversa cresce
    hist_full = M.historico(contato, n=C.MEM_RESUMO_APOS + 4)
    if len(hist_full) >= C.MEM_RESUMO_APOS:
        try: M.set_resumo(contato, B.resumir(hist_full, M.get_resumo(contato)))
        except Exception: pass

    resultado = FS.executar_decisao(ext, d, contato) if ext else {"erro": "sem external_key"}
    # registra o que NÓS enviamos (o detector de "humano digitou" usa isso pra não nos confundir)
    _registra_txt(contato, d.get("texto"))
    for _e in (d.get("_envios") or []):
        _registra_txt(contato, _e.get("text"))
    if d.get("acao") in ("responder", "fastreply") and d.get("texto"):
        M.add_mensagem(contato, ext, "pedrao", d["texto"])

    M.log_evento(contato, "decisao", {
        "mask": _mask(contato), "modo": C.BOT_MODE, "acao": d.get("acao"), "sessao_nova": sessao_nova,
        "fastpath": bool(d.get("_fastpath")),
        "humor": sent.get("humor"), "cor": sent.get("cor"),
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

    # SENTINELA: menu do chatbot NATIVO saindo do nosso número -> registra e pausa o Pedrão
    # (ANTES do dedup, pra renovar a janela a cada menu visto)
    if ev["from_me"] and ev["texto"] and _MENU_NATIVO.search(str(ev["texto"])):
        PAINEL.marcar_bot_nativo()
        M.log_evento(ev["contato"], "bot_nativo_detectado", {"mask": _mask(ev["contato"])})
        return {"status": "bot_nativo_detectado_pedrao_em_pausa"}

    # HUMANO DIGITOU nesta conversa? (fromMe que não é nosso nem menu de bot) -> o copiloto
    # silencia NAQUELE ticket na hora (ordem do dono: aceitar não para; digitar para).
    if ev["from_me"] and ev["texto"] and not _txt_do_bot(ev["contato"], str(ev["texto"])):
        if ev.get("ticket_id") is not None:
            M.merge_fatos(ev["contato"], {"cop_mute_ticket": str(ev["ticket_id"])})
            M.log_evento(ev["contato"], "copiloto",
                         {"mask": _mask(ev["contato"]), "acao": "humano_digitou_silenciei"})

    # idempotência (webhook repetido) — SEM o ts: a FlowSeller às vezes reenvia a MESMA mensagem
    # com timestamp diferente, o que gerava resposta duplicada. Dedup por contato+texto na janela TTL.
    _txt_norm = " ".join(str(ev["texto"]).lower().split())
    key = hashlib.sha256((str(ev["external_key"]) + "|" + _txt_norm).encode()).hexdigest()
    if _txt_norm and _dedup(key):
        return {"status": "duplicado_ignorado"}

    # FILTROS (não responder): própria empresa / grupo / mensagem antiga / vazia
    if ev["from_me"]:   return {"status": "ignorado_from_me"}
    if ev["is_group"]:  return {"status": "ignorado_grupo"}
    # HUMANO/DEPARTAMENTO JÁ ASSUMIU: se o ticket foi aceito por um atendente (status open),
    # atribuído a um humano (userId) ou transferido pra uma fila (queueId), o Pedrão NÃO responde
    # — senão ele atropela o atendimento humano (falha grave: cliente transferido pro Suporte
    # recebia mensagem comercial do bot).
    if ev.get("status") == "open" or ev.get("user_id") or ev.get("queue_id"):
        # COPILOTO FINANCEIRO: fila 25 + copiloto ligado + nenhum humano DIGITOU neste ticket
        # -> o bot entrega a fatura ali mesmo (mesmo com atendente tendo ACEITADO — eles aceitam
        # e demoram; quem manda parar é o humano DIGITAR, tratado no marcador cop_mute_ticket).
        if (str(ev.get("queue_id") or "") == str(FILA_FINANCEIRO)
                and PAINEL.ativo() and PAINEL.copiloto_ativo() and ev["texto"]
                and str(M.get_fatos(ev["contato"]).get("cop_mute_ticket") or "") != str(ev.get("ticket_id"))):
            return await asyncio.to_thread(_copiloto, ev)
        M.log_evento(ev["contato"], "ignorado_humano_assumiu",
                     {"mask": _mask(ev["contato"]), "status": ev.get("status"),
                      "user": bool(ev.get("user_id")), "queue": ev.get("queue_id")})
        return {"status": "ignorado_humano_assumiu"}
    # liga/desliga pelo painel (o "botão" do dono, sem terminal)
    if not PAINEL.ativo():
        return {"status": "desligado_no_painel"}
    # chatbot NATIVO da FlowSeller atendendo o canal? -> o Pedrão se cala sozinho (anti-duplo-bot).
    # Some o menu nativo (canal voltou pro fluxo vazio) -> retoma automático em ~10 min.
    if PAINEL.bot_nativo_ativo():
        M.log_evento(ev["contato"], "pausado_bot_nativo", {"mask": _mask(ev["contato"])})
        return {"status": "pausado_bot_nativo_ativo"}
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


_APIKEY_PATH = _os.path.join(_os.path.dirname(__file__), "..", "data", "anthropic_key.txt")

@app.get("/admin/apikey")
def admin_apikey_status(x_admin_token: str = Header(default="")):
    """Status da chave da API (mascarada) — pro painel mostrar se já está configurada."""
    _auth_painel(x_admin_token)
    import llm as L
    k = L._anthropic_key()
    return {"tem_chave": bool(k), "mascara": (k[:11] + "…" + k[-4:]) if k and len(k) > 20 else "",
            "provider": C.LLM_PROVIDER}

@app.post("/admin/apikey")
async def admin_apikey_set(request: Request, x_admin_token: str = Header(default="")):
    """Salva a chave da API (colada no painel) num arquivo protegido — sem terminal.
    Nunca devolve a chave; o llm.py lê esse arquivo a cada chamada (não precisa reiniciar)."""
    _auth_painel(x_admin_token)
    body = await request.json()
    key = (body.get("key") or "").strip()
    if not key.startswith("sk-ant-") or len(key) < 20:
        raise HTTPException(status_code=400, detail="chave inválida (deve começar com sk-ant-)")
    _os.makedirs(_os.path.dirname(_APIKEY_PATH), exist_ok=True)
    with open(_APIKEY_PATH, "w", encoding="utf-8") as f:
        f.write(key)
    try: _os.chmod(_APIKEY_PATH, 0o600)
    except Exception: pass
    M.log_evento("admin", "apikey_set", {"len": len(key), "provider": C.LLM_PROVIDER})
    return {"ok": True, "len": len(key), "provider": C.LLM_PROVIDER}

@app.get("/admin/mycore")
def admin_mycore_status(x_admin_token: str = Header(default="")):
    """Status do token do MyCore (área do cliente) — pro painel mostrar se já está configurado."""
    _auth_painel(x_admin_token)
    import mycore as MC
    return {"tem_token": MC.token_configurado(), "base": MC.BASE_URL}

@app.post("/admin/mycore")
async def admin_mycore_set(request: Request, x_admin_token: str = Header(default="")):
    """Salva o token do MyCore (colado no painel) em arquivo protegido — sem terminal, nunca devolvido."""
    _auth_painel(x_admin_token)
    import mycore as MC
    body = await request.json()
    tok = (body.get("token") or "").strip()
    if len(tok) < 16:
        raise HTTPException(status_code=400, detail="token muito curto (confira)")
    MC.salvar_token(tok)
    M.log_evento("admin", "mycore_token_set", {"len": len(tok)})
    return {"ok": True, "len": len(tok)}

@app.post("/admin/mycore/testar")
async def admin_mycore_testar(request: Request, x_admin_token: str = Header(default="")):
    """Testa o token: busca um CPF e diz se autenticou (sem devolver dado pessoal)."""
    _auth_painel(x_admin_token)
    import mycore as MC
    if not MC.token_configurado():
        return {"ok": False, "erro": "token não configurado"}
    body = await request.json()
    cpf = MC.extrair_cpf_cnpj(body.get("cpf") or "")
    if not cpf:
        return {"ok": False, "erro": "informe um CPF/CNPJ válido pra testar"}
    try:
        clientes = MC.clientes_por_cpf(cpf)
        return {"ok": True, "autenticou": True, "achou_cadastro": len(clientes) > 0, "qtd": len(clientes)}
    except MC.MyCoreErro as e:
        return {"ok": False, "autenticou": e.tipo != "auth", "erro": f"{e.tipo}: {e}"}

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
