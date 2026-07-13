# -*- coding: utf-8 -*-
"""Transcrição de áudio (plugável). Fluxo: baixa a mídia (mediaUrl) -> transcreve -> texto.
Provedores: gemini (grátis, aceita áudio inline) | openai (whisper) | none.
Privacidade: arquivo temporário é apagado após transcrever; nada é persistido."""
import os, base64, json, tempfile, urllib.request
import config as C

TRANSCRICAO_PROVIDER = os.environ.get("TRANSCRICAO_PROVIDER", "gemini").strip().lower()
TRANSCRICAO_MAX_MB = int(os.environ.get("TRANSCRICAO_MAX_MB", "16"))

class TranscricaoError(Exception):
    pass

def _baixar(media_url, jwt=None, limite_mb=None):
    limite = (limite_mb or TRANSCRICAO_MAX_MB) * 1024 * 1024
    headers = {"Authorization": f"Bearer {jwt}"} if jwt else {}
    req = urllib.request.Request(media_url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        ctype = r.headers.get("Content-Type", "audio/ogg")
        data = r.read(limite + 1)
    if len(data) > limite:
        raise TranscricaoError(f"áudio > {limite_mb or TRANSCRICAO_MAX_MB}MB")
    return data, ctype

def _gemini_audio(data, ctype):
    if not C.GEMINI_API_KEY:
        raise TranscricaoError("GEMINI_API_KEY ausente p/ transcrição")
    model = "gemini-2.0-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={C.GEMINI_API_KEY}"
    body = {"contents": [{"role": "user", "parts": [
        {"text": "Transcreva este áudio em português do Brasil. Devolva SOMENTE a transcrição, sem comentários."},
        {"inline_data": {"mime_type": ctype.split(";")[0], "data": base64.b64encode(data).decode()}}]}]}
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=C.LLM_TIMEOUT + 20) as r:
        out = json.loads(r.read().decode())
    try:
        return "".join(p.get("text", "") for p in out["candidates"][0]["content"]["parts"]).strip()
    except Exception:
        raise TranscricaoError(f"resposta inesperada: {json.dumps(out)[:200]}")

def transcrever(media_url, jwt=None):
    """Retorna (texto, erro). Nunca levanta — devolve erro pra camada tratar (pede confirmação por escrito)."""
    if TRANSCRICAO_PROVIDER == "none":
        return None, "transcrição desativada"
    try:
        data, ctype = _baixar(media_url, jwt=jwt)
        if TRANSCRICAO_PROVIDER == "gemini":
            return _gemini_audio(data, ctype), None
        return None, f"provider de transcrição desconhecido: {TRANSCRICAO_PROVIDER}"
    except Exception as e:
        return None, str(e)
