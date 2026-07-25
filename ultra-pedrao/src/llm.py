# -*- coding: utf-8 -*-
"""Abstração de LLM — provedor plugável por env (anthropic | gemini | fake).
Recebe (system, user) e devolve texto. Sem estado; o contexto é montado no brain."""
import json, os, re, urllib.request, urllib.error
import config as C

class LLMError(Exception):
    pass

# consumo da última chamada (tokens + acerto de cache). Lido pelo log de decisão e pelo /health
# — é a única forma de saber se o cache do prompt está quente.
ULTIMO_USO = {}

_KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "anthropic_key.txt")

# PERF (25/07): a chave era lida do DISCO a cada mensagem. Agora fica em cache e só é relida
# quando o arquivo muda (mtime+tamanho) -- o painel continua trocando a chave sem reiniciar.
_KEY_CACHE = {"chave": None, "valor": None}

def _anthropic_key():
    """Chave da Anthropic: prioriza o arquivo data/anthropic_key.txt (salvo pelo painel, sem
    terminal e sem reiniciar) e cai pro .env se o arquivo não existir."""
    try:
        st = os.stat(_KEY_FILE)
        sig = (st.st_mtime_ns, st.st_size)
        if _KEY_CACHE["chave"] == sig and _KEY_CACHE["valor"]:
            return _KEY_CACHE["valor"]
        with open(_KEY_FILE, encoding="utf-8") as f:
            k = f.read().strip()
        if k:
            _KEY_CACHE["chave"], _KEY_CACHE["valor"] = sig, k
            return k
    except Exception:
        pass
    return C.ANTHROPIC_API_KEY

# PERF (25/07): cada chamada ao modelo abria uma conexão TLS NOVA (~250ms de handshake só pra
# começar a falar). Com httpx o pool mantém a conexão viva entre mensagens. Se a lib não estiver
# no ambiente, cai no urllib de sempre -- nada quebra, só fica mais lento.
_CLIENTE = None
try:
    import httpx as _httpx
except Exception:
    _httpx = None

def _cliente_http(timeout):
    global _CLIENTE
    if _httpx is None:
        return None
    if _CLIENTE is None:
        _CLIENTE = _httpx.Client(
            timeout=timeout,
            limits=_httpx.Limits(max_keepalive_connections=6, max_connections=12,
                                 keepalive_expiry=300.0),
            http2=False)
    return _CLIENTE

def _post_json(url, headers, payload, timeout):
    data = json.dumps(payload).encode("utf-8")
    cli = _cliente_http(timeout)
    if cli is not None:
        try:
            r = cli.post(url, content=data, headers=headers, timeout=timeout)
            if r.status_code >= 400:
                raise LLMError(f"HTTP {r.status_code}: {r.text[:300]}")
            return r.json()
        except LLMError:
            raise
        except Exception as e:
            # conexão do pool pode ter morrido do outro lado: derruba o cliente e tenta
            # uma vez pelo caminho antigo, em vez de perder a resposta do cliente.
            globals()["_CLIENTE"] = None
            try:
                cli.close()
            except Exception:
                pass
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise LLMError(f"HTTP {e.code}: {e.read().decode('utf-8')[:300]}")
    except Exception as e:
        raise LLMError(str(e))

# O prefill ("{" como primeira fala do assistant) é REJEITADO pelos modelos novos da Anthropic
# — Sonnet 5, Opus 5 e toda a família 4.6+ devolvem HTTP 400 "This model does not support
# assistant messages". Pego nos logs 25/07 08:02: junto com o `temperature`, era o 2º motivo de
# TODA escalada pro modelo esperto falhar na 1ª tentativa e só responder porque o retry caía no
# Haiku — os casos difíceis (cliente irritado, PJ, suporte travado) rodavam no modelo fraco em
# silêncio, gastando o dobro do tempo (falha + retry).
# Allowlist e não denylist de propósito: são os modelos NOVOS que rejeitam, então qualquer modelo
# futuro entra sem prefill por padrão, em vez de quebrar de novo.
_PREFILL_OK = re.compile(r"(haiku-4-5|haiku-3|sonnet-4-5|sonnet-3|opus-4-5|opus-4-1|opus-4-0)", re.I)

def _aceita_prefill(model: str) -> bool:
    return bool(_PREFILL_OK.search(model or ""))

# `output_config.effort` controla profundidade do raciocínio (e, portanto, latência). Existe só
# nos modelos novos -- o Haiku 4.5 e o Sonnet 4.5 devolvem 400 se receberem o parâmetro, então
# ele NÃO pode ir em toda chamada (o Haiku é quem responde a maioria das mensagens).
_EFFORT_OK = re.compile(r"(sonnet-5|opus-5|opus-4-[678]|sonnet-4-6|opus-4-5|fable-5|mythos-5)", re.I)

def _aceita_effort(model: str) -> bool:
    return bool(_EFFORT_OK.search(model or ""))

def _anthropic(system, user, model=None):
    """system marcado com cache_control: a Anthropic guarda esse bloco (prompt gigante,
    ~14k tokens) por 5min e cobra só 10% dele nas próximas chamadas. Como o system é IDÊNTICO
    pra todos os contatos, o cache é compartilhado entre todas as conversas enquanto estiver
    quente (não é só 'da mesma conversa') -- num bot movimentado fica aquecido o tempo todo.
    O cache NÃO é memória do cliente nem deixa o bot mais esperto: a memória real é a memory.py."""
    key = _anthropic_key()
    if not key:
        raise LLMError("ANTHROPIC_API_KEY ausente")
    modelo = model or C.LLM_MODEL
    prefill = _aceita_prefill(modelo)
    msgs = [{"role": "user", "content": user}]
    if prefill:
        # já abre o JSON pelo modelo -> ele não escreve conversa antes ("Claro! Aqui está:"),
        # economiza tokens e elimina a maior causa de "JSON inválido". A resposta volta SEM a
        # chave inicial, recolocada logo abaixo.
        msgs.append({"role": "assistant", "content": "{"})
    corpo = {"model": modelo, "max_tokens": 2000,
             "system": [{"type": "text", "text": system,
                         "cache_control": {"type": "ephemeral", "ttl": "1h"}}],
             "messages": msgs}
    if _aceita_effort(modelo) and C.LLM_EFFORT_SMART:
        corpo["output_config"] = {"effort": C.LLM_EFFORT_SMART}
    out = _post_json(
        "https://api.anthropic.com/v1/messages",
        {"x-api-key": key, "anthropic-version": "2023-06-01",
         "content-type": "application/json",
         # cache de 1h (o padrão é 5min): o Pedrão atua de madrugada, quando o intervalo entre
         # conversas passa de 5min com facilidade -- o cache expirava, cada mensagem reprocessava
         # ~13k tokens do zero E ainda pagava a escrita do cache sem nunca ler.
         "anthropic-beta": "extended-cache-ttl-2025-04-11"},
        # max_tokens 1024 -> 2000: em 24/07 22:16 (ao vivo) a resposta do Sonnet bateu no teto,
        # o JSON veio truncado e o cliente levou balão de erro. Teto maior NÃO deixa mais lento
        # (a latência depende dos tokens realmente gerados), só evita o corte.
        # SEM temperature: o Sonnet 5 rejeita o parâmetro ("`temperature` is deprecated for this
        # model", HTTP 400) -- pego nos logs 25/07: TODA escalada pro modelo esperto falhava na
        # 1ª tentativa e só respondia porque o retry caía no Haiku. Ou seja, os casos complexos
        # (cliente irritado, PJ, suporte travado) estavam perdendo o modelo melhor em silêncio.
        # A instrução de formato no system + o _parse_json tolerante já garantem o JSON quando
        # o modelo não aceita prefill.
        corpo,
        C.LLM_TIMEOUT)
    txt = "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text")
    # só recoloca a chave quando ELA foi consumida pelo prefill; sem prefill o modelo devolve o
    # JSON inteiro e prefixar "{" corromperia a resposta.
    if prefill and txt and not txt.lstrip().startswith("{"):
        txt = "{" + txt
    # MEDIÇÃO: sem registrar o usage era impossível saber se o cache do prompt estava acertando
    # (ele vale ~13k tokens por chamada). cache_read alto = quente; cache_creation alto toda hora
    # = frio, e aí o dinheiro e o tempo estão indo embora.
    try:
        u = out.get("usage") or {}
        ULTIMO_USO.update({
            "cache_read": u.get("cache_read_input_tokens", 0),
            "cache_write": u.get("cache_creation_input_tokens", 0),
            "entrada": u.get("input_tokens", 0), "saida": u.get("output_tokens", 0),
            "modelo": modelo, "truncado": out.get("stop_reason") == "max_tokens",
            "esforco": (corpo.get("output_config") or {}).get("effort", "-"),
            "prefill": prefill,
        })
        if ULTIMO_USO["truncado"]:
            import memory as _M
            _M.log_evento("sistema", "llm_truncado",
                          {"modelo": ULTIMO_USO["modelo"], "chars": len(txt)})
    except Exception:
        pass
    return txt

def _openai(system, user):
    """A OpenAI cacheia automaticamente o prefixo repetido (o system prompt) quando ele tem
    mais de ~1024 tokens e é idêntico à chamada anterior -- sem precisar marcar nada no código,
    só manter o system estável (não concatenar nada variável nele). Desconto de 90% no trecho
    cacheado, aplicado sozinho pela OpenAI nas próximas chamadas da mesma conversa."""
    if not C.OPENAI_API_KEY:
        raise LLMError("OPENAI_API_KEY ausente")
    model = C.LLM_MODEL if re.match(r"^(gpt-|o\d)", C.LLM_MODEL) else "gpt-5.4-mini"
    out = _post_json(
        "https://api.openai.com/v1/chat/completions",
        {"Authorization": f"Bearer {C.OPENAI_API_KEY}", "content-type": "application/json"},
        {"model": model, "max_tokens": 1024,
         "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
        C.LLM_TIMEOUT)
    try:
        return out["choices"][0]["message"]["content"] or ""
    except Exception:
        raise LLMError(f"resposta inesperada: {json.dumps(out)[:300]}")

def _gemini(system, user):
    if not C.GEMINI_API_KEY:
        raise LLMError("GEMINI_API_KEY ausente")
    model = C.LLM_MODEL if "gemini" in C.LLM_MODEL else "gemini-2.0-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={C.GEMINI_API_KEY}"
    out = _post_json(url, {"content-type": "application/json"},
        {"systemInstruction": {"parts": [{"text": system}]},
         "contents": [{"role": "user", "parts": [{"text": user}]}],
         "generationConfig": {"maxOutputTokens": 1024, "temperature": 0.7}},
        C.LLM_TIMEOUT)
    try:
        return "".join(p.get("text", "") for p in out["candidates"][0]["content"]["parts"])
    except Exception:
        raise LLMError(f"resposta inesperada: {json.dumps(out)[:300]}")

# Fake determinístico p/ testes locais e modo sombra sem chave: devolve JSON plausível.
def _fake(system, user):
    low = user.lower()
    if "confirmada_predio" in low:
        return json.dumps({"acao": "fastreply", "fastReplyId": 1296, "fila": 0,
            "texto": "Olha os planos 👇 Qual fez mais sentido? Já registro seu endereço pro Comercial confirmar tudo com você a partir das 9h.",
            "intencao": "viabilidade", "viabilidade": "confirmada_predio",
            "nota_interna": "[FAKE] lead confirmado", "confianca": 0.9})
    if "provavel" in low:
        return json.dumps({"acao": "responder",
            "texto": "Registrei seu endereço! O time Comercial confirma a cobertura certinha com você a partir das 9h.",
            "intencao": "viabilidade", "viabilidade": "provavel", "fila": 23,
            "nota_interna": "[FAKE] provável", "confianca": 0.7})
    if any(k in low for k in ("cancel", "cancelar")):
        return json.dumps({"acao": "transferir", "fila": 25, "texto": "Entendi, vou encaminhar pro setor responsável.",
            "intencao": "cancelamento", "viabilidade": "naoaplicavel",
            "nota_interna": "[FAKE] cancelamento", "confianca": 0.8})
    if any(k in low for k in ("caiu", "sem internet", "lenta", "luz vermelha")):
        return json.dumps({"acao": "responder",
            "texto": "Poxa! Tenta desligar o aparelho da tomada 1 minutinho e religar. Me diz se voltou?",
            "intencao": "suporte", "viabilidade": "naoaplicavel", "fila": 24,
            "nota_interna": "[FAKE] suporte básico", "confianca": 0.75})
    return json.dumps({"acao": "responder",
        "texto": "Oi! Aqui é o Pedrão, da WebFiber 🙂 Me conta o que você precisa que eu te ajudo.",
        "intencao": "saudacao", "viabilidade": "naoaplicavel",
        "nota_interna": "", "confianca": 0.6})

def _claude_cli(system, user):
    """Cérebro via Claude headless (token de 1 ano `claude setup-token`, grátis).
    Requer a CLI `claude` instalada no container e CLAUDE_CODE_OAUTH_TOKEN no ambiente.
    Caveats: latência ~6-16s (cold start); o token vence em ~1 ano e pode parar SEM erro
    visível -> o monitor de saúde avisa. Trocar para 'anthropic'/'gemini' = 1 linha no .env."""
    import subprocess
    prompt = system + "\n\n" + user
    try:
        r = subprocess.run(["claude", "-p", prompt, "--output-format", "text"],
                           capture_output=True, text=True, timeout=C.LLM_TIMEOUT + 40)
        if r.returncode != 0:
            raise LLMError(f"claude cli rc={r.returncode}: {r.stderr[:200]}")
        return r.stdout
    except FileNotFoundError:
        raise LLMError("CLI 'claude' não instalada no container (veja docker/Dockerfile.claude)")
    except subprocess.TimeoutExpired:
        raise LLMError("claude cli timeout")

def gerar(system: str, user: str, model: str = None) -> str:
    """model: override opcional (ex.: Sonnet 5 pros casos complexos); None = LLM_MODEL padrão."""
    p = C.LLM_PROVIDER
    if p == "anthropic": return _anthropic(system, user, model)
    if p == "openai": return _openai(system, user)
    if p == "gemini": return _gemini(system, user)
    if p == "claude_cli": return _claude_cli(system, user)
    if p == "fake": return _fake(system, user)
    raise LLMError(f"provider desconhecido: {p}")
