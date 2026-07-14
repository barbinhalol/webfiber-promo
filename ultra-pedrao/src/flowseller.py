# -*- coding: utf-8 -*-
"""Cliente da API EXTERNA da FlowSeller (mapa em docs/API_EXTERNA.md).
Respeita BOT_MODE: em 'shadow' NUNCA chama a API (só devolve o que faria).
Endpoint central: POST /v1/api/external/{apiId} com corpo SendMessageBase."""
import json, urllib.request, urllib.error
import config as C

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

def _enviar(body, usar="resposta"):
    """Executa (ou simula) um POST SendMessageBase. Retorna FSResult com o que fez/faria."""
    try:
        import painel as PAINEL
        modo = PAINEL.modo_efetivo(C.BOT_MODE)
    except Exception:
        modo = C.BOT_MODE
    apiid = C.FS_APIID_RESPOSTA if usar == "resposta" else (C.FS_APIID_TRANSFER or C.FS_APIID_RESPOSTA)
    jwt = C.FS_JWT_RESPOSTA if usar == "resposta" else (C.FS_JWT_TRANSFER or C.FS_JWT_RESPOSTA)
    plan = {"endpoint": f"POST /v1/api/external/{{{usar}}}", "body": body}
    if modo == "shadow":
        return FSResult(enviado=False, modo="shadow", faria=plan)
    # TRAVA DUPLA: no piloto, so envia para a allowlist (mesmo que o filtro de processamento falhe)
    if modo == "pilot" and not _num_permitido_piloto(body):
        return FSResult(enviado=False, modo="pilot", erro="numero fora da allowlist do piloto (trava de seguranca)", faria=plan)
    if not apiid or not jwt:
        return FSResult(enviado=False, modo=C.BOT_MODE, erro="credenciais FlowSeller ausentes", faria=plan)
    try:
        resp = _post(apiid, jwt, "", body)
        return FSResult(enviado=True, modo=C.BOT_MODE, resposta=resp, body=body)
    except urllib.error.HTTPError as e:
        return FSResult(enviado=False, modo=C.BOT_MODE, erro=f"HTTP {e.code}: {e.read().decode('utf-8')[:200]}", faria=plan)
    except Exception as e:
        return FSResult(enviado=False, modo=C.BOT_MODE, erro=str(e), faria=plan)

# ---------- ações de alto nível (a decisão do brain vira uma destas) ----------

def responder_texto(external_key, texto, nota=None, number=None):
    body = {"externalKey": external_key, "body": texto}
    if number: body["number"] = number
    if nota: body["note"] = {"body": nota}
    return _enviar(body, "resposta")

def enviar_midia(external_key, media_url, legenda=None, nota=None, number=None):
    """/planos e afins: imagem por mediaUrl (a API externa não dispara fastReply direto)."""
    body = {"externalKey": external_key, "mediaUrl": media_url}
    if number: body["number"] = number
    if legenda: body["body"] = legenda
    if nota: body["note"] = {"body": nota}
    return _enviar(body, "resposta")

def nota_interna(external_key, texto, number=None):
    body = {"externalKey": external_key, "onlyNote": True, "note": {"body": texto}}
    if number: body["number"] = number
    return _enviar(body, "resposta")

def transferir(external_key, queue_id, nota=None, texto=None, user_id=None, number=None):
    body = {"externalKey": external_key, "queueId": queue_id, "forceTicketToDepartment": True}
    if number: body["number"] = number
    if user_id: body["forceTicketToUser"] = True; body["userId"] = user_id
    if texto: body["body"] = texto
    if nota: body["note"] = {"body": nota}
    return _enviar(body, "transfer")

def fechar(external_key, closing_reason_id, nota=None, number=None):
    body = {"externalKey": external_key, "forceTicketToClosed": True, "closingReasonId": closing_reason_id}
    if number: body["number"] = number
    if nota: body["note"] = {"body": nota}
    return _enviar(body, "resposta")

# mapa fastReplyId -> mediaUrl (preencher quando as imagens estiverem hospedadas na VPS)
FASTREPLY_MEDIA = {
    1296: {"text_env": "PLANOS_TEXTO", "imgs_env": "PLANOS_IMAGENS"},  # texto + 3 imagens
}

def executar_decisao(external_key, d, number=None):
    """Traduz a decisão JSON do brain em chamada(s) à API externa (respeitando shadow)."""
    acao = d.get("acao")
    nota = (d.get("nota_interna") or "").strip() or None
    if acao == "responder":
        return responder_texto(external_key, d.get("texto", ""), nota=nota, number=number)
    if acao == "fastreply":
        fid = d.get("fastReplyId")
        if fid in (1296, 1437, 1438):   # /planos = texto (negrito) + as 3 imagens, tudo de uma vez
            import respostas as R
            envios = R.planos_payloads(external_key, legenda=d.get("texto"))
            resultados = []
            for e in envios:
                if e.get("tipo") == "texto":
                    resultados.append(responder_texto(external_key, e["text"], nota=nota, number=number)); nota = None
                elif e.get("tipo") == "midia":
                    resultados.append(enviar_midia(external_key, e["mediaUrl"], number=number))
                else:
                    resultados.append(FSResult(enviado=False, aviso=e.get("detalhe")))
            return FSResult(enviado=any(r.get("enviado") for r in resultados), modo=C.BOT_MODE, sequencia=resultados)
        if fid == 1858:  # ficha de cadastro residencial
            import respostas as R
            return responder_texto(external_key, (d.get("texto", "") + "\n\n" + R.CADASTRO_RESIDENCIAL).strip(), nota=nota, number=number)
        return responder_texto(external_key, d.get("texto") or "Segue a informação 👇", nota=nota, number=number)
    if acao == "transferir":
        return transferir(external_key, d.get("fila", 112), nota=nota, texto=d.get("texto") or None, number=number)
    if acao == "aguardar":
        return FSResult(enviado=False, modo=C.BOT_MODE, faria={"acao": "aguardar"})
    return FSResult(enviado=False, modo=C.BOT_MODE, erro=f"acao desconhecida: {acao}")
