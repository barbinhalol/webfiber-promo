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
        return ("[VIABILIDADE=CONFIRMADA_PREDIO — o sistema confirmou que " + rua + " já é bem atendido pela WebFiber. "
                "PODE confirmar o atendimento com naturalidade e conduzir ao fechamento. Use um toque de prova social "
                "LEVE, tipo 'vários vizinhos seus já são nossos clientes' — NUNCA cite quantidade, número de clientes "
                "nem 'X na rua' (soa exagero e expõe dado). SEMPRE avise que a equipe confirma tudo e combina a "
                "instalação no próximo horário comercial. NUNCA marque data.]")
    if s == PROVAVEL:
        return ("[VIABILIDADE=PROVAVEL — a RUA consta na base, mas aquele número tem menos de 3 clientes. "
                "NUNCA afirme 'atendemos sim'. Fale em PROBABILIDADE boa, colete dados e transfira o Comercial (23) "
                "para confirmar a viabilidade.]")
    if s == FORA_BASE:
        return ("[VIABILIDADE=FORA_BASE — a rua não consta na base. NUNCA diga 'não atendemos' seco. "
                "Acolha, registre o endereço como demanda e transfira o Comercial (23) para confirmar.]")
    return ("[VIABILIDADE=SEM_ENDERECO — o cliente ainda não deu um endereço completo. Peça rua, número e bairro "
            "com o motivo embutido antes de falar de cobertura.]")
