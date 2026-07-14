# -*- coding: utf-8 -*-
"""Cérebro do Ultra Pedrão: monta contexto -> LLM -> parseia JSON -> aplica GUARDS de código.
Os guards NÃO confiam no modelo (bloqueiam preço digitado, placeholder, fastReply/fila inválidos,
e viabilidade afirmada sem o veredito do sistema)."""
import json, os, re
import viability as V
import llm as L

HERE = os.path.dirname(os.path.abspath(__file__))
def _load(name):
    with open(os.path.join(HERE, "..", "data", name), encoding="utf-8") as f:
        return f.read()

SYSTEM_PROMPT = _load("pedrao_prompt.md")
PLANOS_CTX = _load("planos_e_rapidas.md")

QUICK = {1296, 1437, 1438, 3304, 1858, 1846, 1884, 2260, 2620, 2326, 3535, 1299, 1291, 3536}
FILAS = {23, 24, 25, 112, 26}

_PRECO = re.compile(r"(R\$\s*\d|\bpor\s+\d+\s*reais\b|\bfica\s+em\s+\d|\b\d{2,4}[.,]\d{2}\b)", re.I)
_PLACEHOLDER = re.compile(r"\[[^\]]*\]|\{\{[^}]*\}\}")
# não expor quantidade de clientes/vizinhos ("mais de 80 vizinhos", "500 na rua") — soa exagero
_CONTAGEM = re.compile(r"\b(?:mais de\s*|cerca de\s*|uns?\s*)?\d{1,4}\s*(clientes?|vizinhos?|atendidos?|casas?|apto?s?|apartamentos?|moradores?|fam[íi]lias?)\b", re.I)

def _fila_por_intencao(intencao, motivo):
    s = (str(intencao) + " " + str(motivo)).lower()
    if re.search(r"suporte|t[eé]cnic|sem (internet|sinal|conex)|caiu|lent|oscil|reparo", s): return 24
    if re.search(r"cancel|financ|boleto|cobran|fatura|jur[ií]dic|procon", s): return 25
    if re.search(r"pre[çc]o|plano|viab|cobertura|contrat|comercial|empresa|cnpj", s): return 23
    return 112

def _parse_json(txt):
    if not txt: return None
    i, j = txt.find("{"), txt.rfind("}")
    if i < 0 or j < 0: return None
    try: return json.loads(txt[i:j+1])
    except Exception: return None

def decidir(mensagem, historico=None, memoria_cliente=None):
    """historico: [{'de':'cliente'|'pedrao','texto':...}]; memoria_cliente: dict de fatos por contato."""
    historico = historico or []
    texto_todo = " ".join([h.get("texto", "") for h in historico] + [mensagem])
    viab = V.checar(texto_todo)

    linhas = [("Pedrão" if h.get("de") in ("pedrao", "bot", "atendente") else "Cliente") + ": " + h.get("texto", "")
              for h in historico]
    linhas.append("Cliente: " + mensagem)

    ctx = []
    if memoria_cliente:
        ctx.append("MEMÓRIA DO CLIENTE (fatos já sabidos — não pergunte de novo): " + json.dumps(memoria_cliente, ensure_ascii=False))
    ctx.append("CONVERSA ATÉ AGORA:\n" + "\n".join(linhas))
    ctx.append(V.hint_para_prompt(viab))
    ctx.append("\nDecida a próxima ação do Pedrão e responda SÓ o JSON no formato definido.")
    user = "\n\n".join(ctx)
    system = SYSTEM_PROMPT + "\n\n## CONTEXTO DE PLANOS (para conversar; preço só pela imagem)\n" + PLANOS_CTX

    try:
        raw = L.gerar(system, user)
    except L.LLMError as e:
        return _fallback(f"LLM indisponível: {e}", viab)

    d = _parse_json(raw)
    if not d:
        return _fallback("JSON inválido do modelo", viab, raw=raw)

    alertas = []
    texto = (d.get("texto") or "").strip()
    if texto and _PRECO.search(texto):
        alertas.append("GUARD: preço em texto bloqueado")
        texto = "Já te mostro os valores certinhos na tabela oficial 🙂"
    if texto and _PLACEHOLDER.search(texto):
        alertas.append("GUARD: placeholder removido")
        texto = _PLACEHOLDER.sub("", texto).strip()
    if texto and _CONTAGEM.search(texto):
        alertas.append("GUARD: quantidade de clientes/vizinhos suavizada")
        texto = _CONTAGEM.sub(r"vários \1", texto)
        texto = re.sub(r"\bvários (clientes?)\b", "vários clientes", texto, flags=re.I)

    acao = d.get("acao", "responder")
    fid = d.get("fastReplyId") or 0
    fila = d.get("fila") or 0

    if acao == "fastreply" and fid not in QUICK:
        alertas.append(f"GUARD: fastReplyId {fid} inválido -> transfere comercial")
        acao, fila = "transferir", 23
    # viabilidade só "confirmada_predio" se o CÓDIGO confirmou
    if d.get("viabilidade") == "confirmada_predio" and viab["status"] != V.CONFIRMADA_PREDIO:
        alertas.append("GUARD: modelo afirmou cobertura sem veredito -> rebaixado")
        d["viabilidade"] = "provavel" if viab["status"] == V.PROVAVEL else "a_confirmar"
        if acao != "fastreply":
            acao, fila = "transferir", 23
    # texto afirma cobertura mas sistema não confirmou
    if viab["status"] != V.CONFIRMADA_PREDIO and re.search(r"atende(mos)?\s+(sim|a[ií])|chega\s+a[ií]\s+sim", texto.lower()):
        alertas.append("GUARD: texto afirmou cobertura sem veredito -> neutralizado")
        texto = "Deixa eu confirmar a viabilidade certinha do seu endereço com a equipe pra não te passar info errada."
    if acao == "transferir" and fila not in FILAS:
        fila = _fila_por_intencao(d.get("intencao", ""), d.get("motivo", ""))

    d.update({"acao": acao, "texto": texto, "fastReplyId": fid, "fila": fila,
              "_alertas": alertas, "_viabilidade_sistema": viab})
    d["_render"] = _render(d)
    return d

def resumir(historico, resumo_anterior=""):
    """Memória nível 2: comprime a conversa num resumo curto (evita mandar histórico gigante ao modelo)."""
    if not historico:
        return resumo_anterior
    linhas = "\n".join(("Pedrão" if h.get("de") in ("pedrao", "bot") else "Cliente") + ": " + h.get("texto", "")
                        for h in historico)
    sys_ = ("Você resume conversas de atendimento da WebFiber em no máximo 4 linhas, factual, sem inventar. "
            "Guarde: assunto, endereço/bairro citado, plano de interesse, se é cliente, pendências, próximo passo.")
    usr = (("Resumo anterior:\n" + resumo_anterior + "\n\n") if resumo_anterior else "") + "Conversa:\n" + linhas + \
          "\n\nAtualize o resumo (só o texto do resumo)."
    try:
        return L.gerar(sys_, usr).strip()[:800]
    except L.LLMError:
        return resumo_anterior

def _fallback(motivo, viab, raw=None):
    return {"acao": "transferir", "fila": 112, "texto": "", "intencao": "ambiguo",
            "viabilidade": "naoaplicavel", "motivo": motivo,
            "nota_interna": f"[Pedrão] transferência automática — {motivo}",
            "_alertas": [motivo], "_viabilidade_sistema": viab,
            "_raw": (raw or "")[:200], "_render": f"➡️ (fallback) transferiria Atendimento — {motivo}"}

def _render(d):
    a = d["acao"]
    if a == "fastreply": return f"📎 Enviaria rápida {d.get('fastReplyId')}" + (f" + “{d['texto']}”" if d.get("texto") else "")
    if a == "transferir": return f"➡️ Transferiria fila {d.get('fila')}" + (f" (diz: “{d['texto']}”)" if d.get("texto") else "")
    if a == "aguardar": return "⏳ Aguardaria (debounce)"
    return f"💬 “{d.get('texto','')}”"
