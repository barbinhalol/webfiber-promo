# -*- coding: utf-8 -*-
"""
Motor de VIABILIDADE do Ultra Pedrão — a "régua de 3", checada 100% em código
(nunca pela IA). O cérebro só recebe o veredito pronto.

Regra do dono (13/07/2026):
  - 3+ clientes no MESMO rua+número  -> CONFIRMADA_PREDIO (pode confirmar atendimento
    e conduzir ao fechamento, sempre com ressalva de que a equipe confirma no dia seguinte).
  - rua consta na base, mas o número tem < 3 clientes -> PROVAVEL (fala em PROBABILIDADE,
    transfere Comercial p/ confirmar).
  - rua não consta / sem número -> FORA_BASE (nunca "não atendemos" seco; registra e transfere).

Fonte: data/enderecos.json (gerado da planilha de ~6.8k clientes).
"""
import json, os, re, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_PATH = os.path.join(HERE, "..", "data", "enderecos.json")

CONFIRMADA_PREDIO = "confirmada_predio"
PROVAVEL = "provavel"
FORA_BASE = "fora_base"
SEM_ENDERECO = "sem_endereco"

_LIMIAR = int(os.environ.get("VIAB_LIMIAR_PREDIO", "3"))

with open(BASE_PATH, encoding="utf-8") as f:
    _BASE = json.load(f)
_ADDR = _BASE["addr_counts"]        # "RUA X|123" -> n
_STREET = _BASE["street_counts"]    # "RUA X" -> n

_PREFIX = [
    (r"^R\s+", "RUA "), (r"^AV\s+", "AVENIDA "), (r"^ESTR\s+", "ESTRADA "),
    (r"^(TRAV|TV)\s+", "TRAVESSA "), (r"^(PCA|PC)\s+", "PRACA "), (r"^LAD\s+", "LADEIRA "),
]

def norm_rua(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().upper().strip()
    s = re.sub(r"[.,]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    for pat, rep in _PREFIX:
        s = re.sub(pat, rep, s)
    s = s.replace("REZENDE", "RESENDE")
    return s

def norm_num(n: str) -> str:
    m = re.search(r"\d+", str(n or ""))
    return m.group(0) if m else ""

# Extrai rua + número de um texto livre do cliente ("moro na rua ubaldino do amaral, 80 ap 302")
# \b no início: o tipo de logradouro só conta no COMEÇO de palavra (evita casar o "R" final de
# "contrataR", "trabalhaR" etc. e engolir o endereço verdadeiro). "R"/"AV" só como abreviação.
_TIPOS = r"(?:RUA|AVENIDA|AV|ESTRADA|ESTR|TRAVESSA|PRACA|LADEIRA|ALAMEDA|RODOVIA|R)"
_RE_ENDERECO = re.compile(r"\b" + _TIPOS + r"\.?\s+([A-Z0-9À-Ú][A-Z0-9À-Ú\s]{2,50}?)\s*[,\-]?\s*(?:N[º°O]?\.?\s*)?(\d{1,5})\b", re.I)

# rua SEM número (só o logradouro): pra reconhecer que a RUA é atendida mesmo antes do nº
_RE_RUA = re.compile(r"\b" + _TIPOS + r"\.?\s+([A-Z0-9À-Ú][A-Z0-9À-Ú\s]{3,40})", re.I)

def extrair_ruas(texto: str):
    """Devolve nomes de rua normalizados citados no texto (sem exigir número)."""
    up = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().upper()
    ruas = []
    for m in _RE_RUA.finditer(up):
        rua = norm_rua(m.group(0))
        rua = re.sub(r"\s+\d+.*$", "", rua).strip()
        rua = re.sub(r"\s+(NUMERO|NUM|NO|N|CASA|AP|APTO|APARTAMENTO|BLOCO|BL|LOTE|QUADRA|BAIRRO|FUNDOS)\s*$", "", rua).strip()
        if len(rua) >= 5:
            ruas.append(rua)
    return ruas

def extrair_enderecos(texto: str):
    """Devolve lista de (rua_norm, numero) achados no texto livre."""
    achados = []
    up = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().upper()
    for m in _RE_ENDERECO.finditer(up):
        rua = norm_rua(m.group(0).rsplit(m.group(2), 1)[0])
        num = norm_num(m.group(2))
        # limpa número residual e palavras-conector que a captura pode deixar no fim
        rua = re.sub(r"\s+\d+.*$", "", rua).strip()
        rua = re.sub(r"\s+(NUMERO|NUM|NO|N|CASA|AP|APTO|APARTAMENTO|BLOCO|BL|LOTE|QUADRA|FUNDOS)\s*$", "", rua).strip()
        if len(rua) >= 5:
            achados.append((rua, num))
    return achados

def checar(texto_cliente: str) -> dict:
    """
    Retorna o veredito de viabilidade sobre TODO o texto da conversa.
    { "status": <constante>, "rua": str|None, "numero": str|None,
      "clientes_no_numero": int, "clientes_na_rua": int, "evidencia": str }
    Escolhe o MELHOR endereço citado (prioriza CONFIRMADA_PREDIO > PROVAVEL > FORA_BASE).
    """
    achados = extrair_enderecos(texto_cliente)
    if not achados:
        # rua SEM número (ex.: "rua teodoro da silva"): se a RUA consta na base, já é PROVAVEL
        # (região atendida), só falta o número — assim o Pedrão já diz que TEM viabilidade.
        for rua in extrair_ruas(texto_cliente):
            na_rua = _STREET.get(rua, 0)
            if na_rua > 0:
                return {"status": PROVAVEL, "rua": rua, "numero": None,
                        "clientes_no_numero": 0, "clientes_na_rua": na_rua,
                        "evidencia": f"{rua} — rua atendida (sem número ainda)"}
        return {"status": SEM_ENDERECO, "rua": None, "numero": None,
                "clientes_no_numero": 0, "clientes_na_rua": 0,
                "evidencia": "nenhum endereço identificado no texto"}

    melhor = None
    rank = {CONFIRMADA_PREDIO: 3, PROVAVEL: 2, FORA_BASE: 1, SEM_ENDERECO: 0}
    for rua, num in achados:
        na_rua = _STREET.get(rua, 0)
        no_num = _ADDR.get(f"{rua}|{num}", 0) if num else 0
        if no_num >= _LIMIAR:
            status = CONFIRMADA_PREDIO
        elif na_rua > 0:
            status = PROVAVEL
        else:
            status = FORA_BASE
        cand = {"status": status, "rua": rua, "numero": num or None,
                "clientes_no_numero": no_num, "clientes_na_rua": na_rua,
                "evidencia": f"{rua}" + (f", {num}" if num else "") +
                             f" — {no_num} cliente(s) no nº, {na_rua} na rua"}
        if melhor is None or rank[status] > rank[melhor["status"]]:
            melhor = cand
    return melhor

def hint_para_prompt(v: dict) -> str:
    """Frase que a camada de execução injeta no contexto do LLM (o cérebro só age sobre isto)."""
    s = v["status"]
    if s == CONFIRMADA_PREDIO:
        rua = v.get("rua") or "o endereço informado"
        return ("[VIABILIDADE=CONFIRMADA_PREDIO — o sistema confirmou que " + rua + " já é bem atendido pela WebFiber "
                "(prédio). PODE dizer que TEMOS COBERTURA SIM, com naturalidade, e conduzir pro PRÉ-CADASTRO. "
                "Roteiro do dono, nessa linha: 'Temos cobertura sim! Inclusive verifiquei aqui que boa parte dos seus "
                "vizinhos já são nossos clientes 😊 Posso já adiantar um pré-cadastro pra você, e logo pela manhã "
                "alguém do nosso time confirma tudo e já te orienta pra instalação sair o mais rápido possível.' "
                "Prova social LEVE ('boa parte dos seus vizinhos') — NUNCA cite quantidade nem número de clientes. "
                "NUNCA marque data/hora. NUNCA encerre a conversa.]")
    if s == PROVAVEL:
        rua = v.get("rua") or "esse endereço"
        return ("[VIABILIDADE=PROVAVEL — a RUA consta na nossa base (região ATENDIDA). Ordem do dono: PODE dizer "
                "'nesse endereço temos disponibilidade SIM' com naturalidade. NÃO fique só pedindo endereço — "
                "CONDUZA pro fechamento: (1) se ainda não enviou, ENVIE OS PLANOS residenciais AGORA (acao=fastreply, "
                "fastReplyId 1296 — texto+imagens); (2) confirme NÚMERO e BAIRRO pra validar certinho; (3) pergunte se "
                "é RESIDENCIAL ou EMPRESARIAL (empresarial → conduza aos consultores / Comercial 23, ficha diferente); "
                "(4) puxe pro PRÉ-CADASTRO: 'já posso adiantar seu pré-cadastro pra equipe finalizar logo cedo e tentar "
                "encaixar a instalação o quanto antes — quem sabe no mesmo dia ou em até 24h'. Quem MARCA a instalação "
                "é o time Comercial. NUNCA marque data/hora exata. NUNCA encerre a conversa.]")
    if s == FORA_BASE:
        return ("[VIABILIDADE=FORA_BASE — a rua não consta na base ainda. NUNCA diga 'não atendemos' seco. Diga que a "
                "região é atendida, mas esse ponto específico pode precisar de uma VISTORIA técnica rápida antes da "
                "instalação, e ofereça deixar os dados: 'A região é atendida, mas esse endereço pode precisar de uma "
                "validação/vistoria técnica rápida. Já posso deixar seus dados pra equipe alinhar isso?'. Envie os "
                "planos e conduza ao pré-cadastro do mesmo jeito. Transfira o Comercial (23) pra confirmar.]")
    return ("[VIABILIDADE=SEM_ENDERECO — o cliente ainda não deu um endereço. Se ele demonstrou interesse em contratar, "
            "JÁ ENVIE OS PLANOS (fastReplyId 1296) e peça a RUA, NÚMERO e BAIRRO pra validar — não fique só pedindo "
            "endereço. Pergunte também se é residencial ou empresarial e vá conduzindo pro pré-cadastro.]")
