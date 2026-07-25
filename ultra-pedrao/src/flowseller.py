# -*- coding: utf-8 -*-
"""Cliente da API EXTERNA da FlowSeller (mapa em docs/API_EXTERNA.md).
Respeita BOT_MODE: em 'shadow' NUNCA chama a API (só devolve o que faria).
Endpoint central: POST /v1/api/external/{apiId} com corpo SendMessageBase."""
import json, os, random, threading, time, urllib.request, urllib.error
import config as C

# marca de quando ESTA mensagem do cliente começou a ser processada (por thread -- o
# processamento roda numa thread por conversa). Usada pelo orçamento de naturalidade abaixo.
_CTX = threading.local()

def marcar_inicio(t0=None):
    _CTX.t0 = t0 or time.time()

# "tempo de digitação" simulado antes do 1º envio. O objetivo NUNCA foi somar espera: é evitar
# que a resposta chegue instantânea demais (cara de robô). 25/07: virou ORÇAMENTO em vez de
# soma fixa -- o que importa é o tempo TOTAL desde a mensagem do cliente. Se o modelo já levou
# 3s pensando, o cliente já esperou o suficiente e o delay é ZERO. Só o fastpath (responde em
# ~10ms) precisa de uma pausa, e curta.
DELAY_MIN_S = float(os.environ.get("FS_DELAY_MIN_S", "0.6"))
DELAY_MAX_S = float(os.environ.get("FS_DELAY_MAX_S", "1.2"))
# tempo total (chegada do cliente -> resposta) que soa natural. Acima disso, não espera mais nada.
NATURAL_ALVO_S = float(os.environ.get("FS_NATURAL_ALVO_S", "2.0"))
# log forense byte a byte: ligado só quando FS_FORENSE=1 (erros sempre são registrados)
FORENSE_SEMPRE = os.environ.get("FS_FORENSE", "").strip() in ("1", "true", "sim")

class FSResult(dict):
    pass

def _post(apiid, jwt, path_suffix, body):
    url = f"{C.FS_BASE}/v1/api/external/{apiid}{path_suffix}"
    data = json.dumps(body).encode("utf-8")
    headers = {"content-type": "application/json"}
    if jwt:
        headers["Authorization"] = f"Bearer {jwt}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=25) as r:
        raw = r.read().decode("utf-8")
        try: return json.loads(raw)
        except Exception: return {"raw": raw}

def _forense(url, body, resp=None, erro=None):
    """Assinatura técnica EXATA de cada envio (investigação dos botões de cópia do WhatsApp,
    24/07). Grava bytes/sha/codepoints/invisíveis do texto e o que a FlowSeller devolveu, para
    que qualquer diferença entre um envio que gera o botão e um que não gera fique PROVADA em
    bytes -- nunca mais suposta. NÃO registra token, JWT, apiId nem cookie.

    25/07: a investigação fechou (causa era o aparelho do dono, não o envio), mas a ferramenta
    fica. Só que ela varre a mensagem CARACTERE A CARACTERE (unicodedata.category) + sha256 +
    INSERT, em TODO envio -- caro pra deixar ligado à toa. Agora roda quando: houve ERRO, ou
    FS_FORENSE=1 no .env. Ou seja: diagnóstico continua disponível, sem custo no dia a dia."""
    if not (erro or FORENSE_SEMPRE):
        return
    try:
        import hashlib, unicodedata
        t = body.get("body") if isinstance(body.get("body"), str) else ""
        b = t.encode("utf-8")
        invis = ["U+%04X@%d" % (ord(c), i) for i, c in enumerate(t)
                 if unicodedata.category(c) in ("Cf", "Cc") or (c.isspace() and c not in " \n")]
        d = {
            "url": (url.split("/v1/")[0] + "/v1/api/external/***"),   # apiId mascarado
            "metodo": "POST", "content_type": "application/json",
            "chaves_payload": sorted(body.keys()),
            "tipo_msg": ("midia" if body.get("mediaUrl") else "nota" if body.get("onlyNote")
                         else "transferencia" if body.get("queueId") else "texto"),
            "template": bool(body.get("templateId") or body.get("typeTemplate")),
            "preview_url": body.get("previewUrl"),          # None = campo não enviado
            "tem_context": bool(body.get("quotedMsgId")),
            "bytes": len(b), "caracteres": len(t),
            "sha256": hashlib.sha256(b).hexdigest(),
            "nfc": unicodedata.normalize("NFC", t) == t,
            "crlf": t.count("\r\n"), "lf": t.count("\n") - t.count("\r\n"),
            "espaco_inicio": len(t) - len(t.lstrip()), "espaco_fim": len(t) - len(t.rstrip()),
            "invisiveis": invis[:12],
            "cp_ini": [ord(c) for c in t[:10]], "cp_fim": [ord(c) for c in t[-10:]],
        }
        if resp is not None:
            m = (resp or {}).get("message") or {}
            tk = m.get("ticket") or {}
            d.update({"fs_id": m.get("id"), "wamid": m.get("messageId"),
                      "fs_mediaType": m.get("mediaType"), "fs_sendType": m.get("sendType"),
                      "fs_typeTemplate": m.get("typeTemplate"), "fs_templateId": m.get("templateId"),
                      "fs_params": m.get("params"), "fs_ack": m.get("ack"),
                      "fs_channel": tk.get("channel"), "fs_whatsappId": tk.get("whatsappId")})
        if erro:
            d["erro"] = str(erro)[:200]
        import memory as M
        M.log_evento(str(body.get("number") or body.get("externalKey") or ""), "envio_forense", d)
    except Exception:
        pass   # log forense NUNCA pode derrubar um envio

def _num_permitido_piloto(body):
    """Trava de seguranca do PILOTO: so envia para numeros da PILOT_ALLOWLIST."""
    import re
    alvo = re.sub(r"\D", "", str(body.get("number") or body.get("externalKey") or ""))
    try:
        import painel as PAINEL
        lista = PAINEL.allowlist_efetiva(C.PILOT_ALLOWLIST)
    except Exception:
        lista = C.PILOT_ALLOWLIST
    if not lista:
        return False  # piloto sem allowlist NUNCA envia (protege contra erro de config)
    for n in lista:
        n = re.sub(r"\D", "", n)
        if n and len(alvo) >= 8 and (alvo.endswith(n) or n.endswith(alvo)):
            return True
    return False

def _enviar(body, usar="resposta", delay=True):
    """Executa (ou simula) um POST SendMessageBase. Retorna FSResult com o que fez/faria.
    delay=True espera 2-4s (aleatorio) ANTES do envio real, simulando tempo de digitacao --
    so acontece imediatamente antes do POST de verdade (nunca em shadow/erro/trava)."""
    try:
        import painel as PAINEL
        modo = PAINEL.modo_efetivo(C.BOT_MODE)
    except Exception:
        modo = C.BOT_MODE
    apiid = C.FS_APIID_RESPOSTA if usar == "resposta" else (C.FS_APIID_TRANSFER or C.FS_APIID_RESPOSTA)
    jwt = C.FS_JWT_RESPOSTA if usar == "resposta" else (C.FS_JWT_TRANSFER or C.FS_JWT_RESPOSTA)
    plan = {"endpoint": f"POST /v1/api/external/{{{usar}}}", "body": body}
    # TRAVA ANTI-BALÃO-VAZIO (incidente 24/07 22:16, ao vivo): mensagem sem texto vira balão
    # vermelho "Erro / Tentar novamente" no WhatsApp do cliente. Mídia (legenda vazia é válida)
    # e nota interna (onlyNote) passam; texto puro vazio, NUNCA.
    if not body.get("mediaUrl") and not body.get("onlyNote") and not str(body.get("body") or "").strip():
        return FSResult(enviado=False, modo=modo, erro="bloqueado: mensagem de texto vazia "
                                                       "(viraria balão de erro no cliente)", faria=plan)
    if modo == "shadow":
        return FSResult(enviado=False, modo="shadow", faria=plan)
    # TRAVA DUPLA: no piloto, so envia para a allowlist (mesmo que o filtro de processamento falhe)
    if modo == "pilot" and not _num_permitido_piloto(body):
        return FSResult(enviado=False, modo="pilot", erro="numero fora da allowlist do piloto (trava de seguranca)", faria=plan)
    if not apiid or not jwt:
        return FSResult(enviado=False, modo=C.BOT_MODE, erro="credenciais FlowSeller ausentes", faria=plan)
    try:
        if delay:
            # desconta o que o processamento JÁ consumiu (t0 marcado quando a mensagem entrou):
            # o cliente não deve esperar "pensar + digitar", só o total natural.
            gasto = 0.0
            try:
                t0 = float(getattr(_CTX, "t0", 0) or 0)
                if t0:
                    gasto = max(0.0, time.time() - t0)
            except Exception:
                pass
            espera = random.uniform(DELAY_MIN_S, DELAY_MAX_S)
            espera = min(espera, max(0.0, NATURAL_ALVO_S - gasto))
            if espera > 0.05:
                time.sleep(espera)
        try:
            resp = _post(apiid, jwt, "", body)
        except urllib.error.HTTPError as e:
            # 24/07: a config de TRANSFER morreu junto com o cancelamento do Pedrao nativo
            # (HTTP 403 Invalid token) e as transferencias paravam mudas. Fallback automatico:
            # credencial de transfer invalida -> tenta de novo com a credencial de RESPOSTA
            # (o SendMessageBase aceita queueId por qualquer config valida).
            if usar == "transfer" and e.code in (401, 403) and C.FS_APIID_RESPOSTA and \
                    (apiid, jwt) != (C.FS_APIID_RESPOSTA, C.FS_JWT_RESPOSTA):
                resp = _post(C.FS_APIID_RESPOSTA, C.FS_JWT_RESPOSTA, "", body)
            else:
                raise
        _forense(f"{C.FS_BASE}/v1/api/external/{apiid}", body, resp=resp)
        # Blindagem: a FlowSeller pode devolver HTTP 200 com corpo {} sem criar nada de verdade
        # (visto ao vivo faltando "body" no payload de midia). So consideramos enviado se a
        # resposta realmente trouxer a mensagem criada (tem id, em "message" ou na raiz).
        criado = bool((resp or {}).get("message", {}).get("id") or (resp or {}).get("id"))
        if not criado:
            return FSResult(enviado=False, modo=C.BOT_MODE, erro="FlowSeller respondeu 200 mas nao criou a mensagem (corpo vazio/inesperado)", resposta=resp, faria=plan)
        return FSResult(enviado=True, modo=C.BOT_MODE, resposta=resp, body=body)
    except urllib.error.HTTPError as e:
        _err = f"HTTP {e.code}: {e.read().decode('utf-8')[:200]}"
        _forense(f"{C.FS_BASE}/v1/api/external/{apiid}", body, erro=_err)
        return FSResult(enviado=False, modo=C.BOT_MODE, erro=_err, faria=plan)
    except Exception as e:
        _forense(f"{C.FS_BASE}/v1/api/external/{apiid}", body, erro=str(e))
        return FSResult(enviado=False, modo=C.BOT_MODE, erro=str(e), faria=plan)

# ---------- ações de alto nível (a decisão do brain vira uma destas) ----------

# Assinatura fixa (como os atendentes humanos assinam "*Nome*:") — deixa claro que é agente virtual
# sem precisar repetir "sou virtual" no texto. NÃO entra na saudação (que já se apresenta).
_ASSINATURA = "*Pedrão · Agente Virtual*\n"
# Copiloto Financeiro (horário humano): assinatura NEUTRA de setor — o cliente não vê "agente
# virtual"; parece o time do Financeiro respondendo (ordem do dono 24/07).
ASSIN_FINANCEIRO = "*Financeiro WebFiber*\n"

def _prox_atendimento(setor="suporte"):
    try:
        import schedule as _S
        return _S.proximo_atendimento(setor=setor)
    except Exception:
        return "no próximo dia útil, a partir das 9h"

def _assinar(texto, marca=None):
    t = texto or ""
    pref = marca or _ASSINATURA
    if t and "virtual" not in t.lower() and not t.lstrip().startswith(("*Pedrão", "*Financeiro")) and len(t) > 8:
        return pref + t
    return t

def responder_texto(external_key, texto, nota=None, number=None, delay=True, assinar=True, marca=None):
    # assinar=False p/ conteúdo que o cliente vai COPIAR (Pix copia-e-cola, linha digitável):
    # a assinatura no topo sujaria o copiar/colar no app do banco.
    # marca: assinatura alternativa (ex.: ASSIN_FINANCEIRO no copiloto).
    body = {"externalKey": external_key, "body": (_assinar(texto, marca) if assinar else (texto or ""))}
    if number: body["number"] = number
    if nota: body["note"] = {"body": nota}
    return _enviar(body, "resposta", delay=delay)

def enviar_midia(external_key, media_url, legenda=None, nota=None, number=None, delay=True):
    """/planos e afins: imagem por mediaUrl (a API externa não dispara fastReply direto).
    IMPORTANTE (confirmado ao vivo): a chave "body" precisa EXISTIR no JSON, mesmo vazia --
    sem ela a FlowSeller devolve 200 com corpo {} e NÃO cria a mensagem (falha silenciosa)."""
    body = {"externalKey": external_key, "mediaUrl": media_url, "body": legenda or ""}
    if number: body["number"] = number
    if nota: body["note"] = {"body": nota}
    return _enviar(body, "resposta", delay=delay)

def nota_interna(external_key, texto, number=None, delay=True):
    body = {"externalKey": external_key, "onlyNote": True, "note": {"body": texto}}
    if number: body["number"] = number
    return _enviar(body, "resposta", delay=delay)

def transferir(external_key, queue_id, nota=None, texto=None, user_id=None, number=None, delay=True):
    # "body" SEMPRE presente: sem a chave, a FlowSeller cria um registro de mensagem vazio que
    # falha ao despachar (auditoria 24/07). MAS a chave com string VAZIA dá no mesmo -- incidente
    # 24/07 22:16, ao vivo com cliente: o fallback de "JSON inválido" transferiu com texto="",
    # a FlowSeller gravou body:"" e o WhatsApp recusou -> DOIS balões vermelhos "Erro / Tentar
    # novamente" na cara do cliente. Agora: sem texto, o cliente recebe uma frase real (nunca
    # um balão vazio) com o dia certo em que a equipe volta.
    if not (texto or "").strip():
        texto = ("Vou registrar seu atendimento aqui e nossa equipe fala com você "
                 + _prox_atendimento() + ", combinado? 😊")
    body = {"externalKey": external_key, "queueId": queue_id, "forceTicketToDepartment": True,
            "body": _assinar(texto)}
    if number: body["number"] = number
    if user_id: body["forceTicketToUser"] = True; body["userId"] = user_id
    if nota: body["note"] = {"body": nota}
    return _enviar(body, "transfer", delay=delay)

def fechar(external_key, closing_reason_id, nota=None, number=None, delay=True):
    body = {"externalKey": external_key, "forceTicketToClosed": True, "closingReasonId": closing_reason_id}
    if number: body["number"] = number
    if nota: body["note"] = {"body": nota}
    return _enviar(body, "resposta", delay=delay)

# mapa fastReplyId -> mediaUrl (preencher quando as imagens estiverem hospedadas na VPS)
FASTREPLY_MEDIA = {
    1296: {"text_env": "PLANOS_TEXTO", "imgs_env": "PLANOS_IMAGENS"},  # texto + 3 imagens
}

def executar_decisao(external_key, d, number=None, marca=None):
    """Traduz a decisão JSON do brain em chamada(s) à API externa (respeitando shadow).
    marca: assinatura alternativa (o Copiloto Financeiro passa ASSIN_FINANCEIRO). ESTA é a
    ÚNICA porta de saída de fatura -- noturno e copiloto usam exatamente este caminho, mesmo
    payload e mesma cadência (investigação 24/07: nada de lógica duplicada)."""
    acao = d.get("acao")
    nota = (d.get("nota_interna") or "").strip() or None
    if acao == "responder":
        return responder_texto(external_key, d.get("texto", ""), nota=nota, number=number, marca=marca)
    if acao == "fastreply":
        fid = d.get("fastReplyId")
        if fid in (1296, 1437, 1438):   # /planos = texto (negrito) + as 3 imagens, tudo de uma vez
            import respostas as R
            envios = R.planos_payloads(external_key, legenda=d.get("texto"))
            resultados = []
            for e in envios:
                # sem atraso de digitacao aqui -- fotos/texto dos planos saem imediatos
                if e.get("tipo") == "texto":
                    resultados.append(responder_texto(external_key, e["text"], nota=nota, number=number, delay=False)); nota = None
                elif e.get("tipo") == "midia":
                    resultados.append(enviar_midia(external_key, e["mediaUrl"], number=number, delay=False))
                else:
                    resultados.append(FSResult(enviado=False, aviso=e.get("detalhe")))
            return FSResult(enviado=any(r.get("enviado") for r in resultados), modo=C.BOT_MODE, sequencia=resultados)
        if fid == 1858:  # ficha de cadastro residencial
            import respostas as R
            return responder_texto(external_key, (d.get("texto", "") + "\n\n" + R.CADASTRO_RESIDENCIAL).strip(), nota=nota, number=number)
        return responder_texto(external_key, d.get("texto") or "Segue a informação 👇", nota=nota, number=number)
    if acao == "faturas":   # integração MyCore: sequência (resumo + Pix/linha crus + boleto/PDF)
        envios = d.get("_envios") or []
        resultados, primeiro = [], True
        for e in envios:
            tp = e.get("tipo")
            if tp == "pdf" and e.get("url"):   # boleto PDF anexado (arquivo)
                resultados.append(enviar_midia(external_key, e["url"], legenda=e.get("text") or "",
                                               number=number, delay=False))
            else:
                # assina SÓ a 1ª mensagem (senão a assinatura se repetia em ~4 balões da fatura)
                resultados.append(responder_texto(external_key, e.get("text", ""),
                                                   nota=(nota if primeiro else None), number=number,
                                                   delay=primeiro, assinar=primeiro, marca=marca))
            primeiro = False
        return FSResult(enviado=any(r.get("enviado") for r in resultados), modo=C.BOT_MODE, sequencia=resultados)
    if acao == "transferir":
        return transferir(external_key, d.get("fila", 112), nota=nota, texto=d.get("texto") or None, number=number)
    if acao == "aguardar":
        return FSResult(enviado=False, modo=C.BOT_MODE, faria={"acao": "aguardar"})
    return FSResult(enviado=False, modo=C.BOT_MODE, erro=f"acao desconhecida: {acao}")
