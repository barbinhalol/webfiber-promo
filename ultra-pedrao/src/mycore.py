# -*- coding: utf-8 -*-
"""Integração de FATURA por CPF com o MyCore (área do cliente) — SOMENTE LEITURA.
Fonte da verdade: WebFiberApp/bff/src/adapters/mycore.adapter.ts (código em produção).

Fluxo (2 passos, como o BFF do app faz — evita o 403 do WAF em paralelo):
  1) GET cliente/list?cpfcnpj=<digitos>   -> cadastros do CPF (com telefones)
  2) GET financeiro/nopgto?id=<id> (atrasadas) e pgtopen?id=<id> (a vencer) -> faturas com Pix+boleto

ACESSO (ordem do dono 14/07/2026 — simplificado): a fatura é entregue com base SÓ no CPF informado,
SEM conferir o telefone (muitos cadastros têm telefone desatualizado, o que barraria cliente real).
Se o CPF não tiver cadastro/fatura, cai no link da área do cliente + transfere pro Financeiro.
Nota de privacidade: sem a conferência, quem souber um CPF vê a fatura daquele CPF — decisão
consciente do dono, por simplicidade.

Token: NUNCA no código. Lido de data/mycore_token.txt (chmod 600) ou da env MYCORE_TOKEN.
"""
import json, os, re, urllib.request, urllib.error, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
_TOKEN_FILE = os.path.join(HERE, "..", "data", "mycore_token.txt")

BASE_URL = os.environ.get("MYCORE_BASE_URL", "https://areadocliente.webfiberprovedor.com.br/rest.php")
TIMEOUT_S = float(os.environ.get("MYCORE_TIMEOUT_S", "8"))


class MyCoreErro(Exception):
    def __init__(self, msg, tipo="http"):
        super().__init__(msg); self.tipo = tipo


def token_configurado() -> bool:
    return bool(_token())


def _token() -> str:
    try:
        t = open(_TOKEN_FILE, encoding="utf-8").read().strip()
        if t:
            return t
    except Exception:
        pass
    return (os.environ.get("MYCORE_TOKEN") or "").strip()


def salvar_token(tok: str):
    """Grava o token no arquivo protegido (usado pelo endpoint do painel; o dono cola, nunca o bot)."""
    os.makedirs(os.path.dirname(_TOKEN_FILE), exist_ok=True)
    with open(_TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write((tok or "").strip())
    try:
        os.chmod(_TOKEN_FILE, 0o600)
    except Exception:
        pass


def digitos(s) -> str:
    return re.sub(r"\D", "", str(s or ""))


# ---------------- validação de CPF/CNPJ (evita tratar telefone como CPF) ----------------

def _cpf_valido(c: str) -> bool:
    c = digitos(c)
    if len(c) != 11 or c == c[0] * 11:
        return False
    for i in (9, 10):
        s = sum(int(c[n]) * ((i + 1) - n) for n in range(i))
        d = (s * 10) % 11 % 10
        if d != int(c[i]):
            return False
    return True


def _cnpj_valido(c: str) -> bool:
    c = digitos(c)
    if len(c) != 14 or c == c[0] * 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    for pesos, pos in ((pesos1, 12), (pesos2, 13)):
        s = sum(int(c[i]) * pesos[i] for i in range(pos))
        d = 11 - (s % 11)
        d = 0 if d >= 10 else d
        if d != int(c[pos]):
            return False
    return True


def extrair_cpf_cnpj(texto: str):
    """Acha um CPF (11) ou CNPJ (14) VÁLIDO no texto, validando o dígito verificador — assim um
    telefone de 11 dígitos NÃO é confundido com CPF. Retorna só os dígitos, ou None.
    Testa por TOKEN (cada 'palavra' vira seus dígitos) pra não juntar números separados."""
    for tok in re.split(r"\s+", texto or ""):
        d = digitos(tok)
        if len(d) == 14 and _cnpj_valido(d):
            return d
        if len(d) == 11 and _cpf_valido(d):
            return d
    # 2ª passada: CPF/CNPJ com espaços no meio (ex.: "138 449 907 55") -> todos os dígitos juntos
    d = digitos(texto)
    for tam, valida in ((14, _cnpj_valido), (11, _cpf_valido)):
        if len(d) == tam and valida(d):
            return d
    return None


# ---------------- HTTP (Bearer) ----------------

def _get(path: str, **query):
    tok = _token()
    if not tok:
        raise MyCoreErro("token do MyCore não configurado", "auth")
    url = BASE_URL.rstrip("/") + "/" + path.lstrip("/")
    if query:
        url += "?" + urllib.parse.urlencode(query)
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {tok}", "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            raw = r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise MyCoreErro(f"HTTP {e.code} em {path}", "auth" if e.code in (401, 403) else "http")
    except Exception as e:
        raise MyCoreErro(f"falha de rede em {path}: {e}", "rede")
    try:
        d = json.loads(raw)
    except Exception:
        raise MyCoreErro(f"resposta não-JSON em {path}", "parse")
    return d if isinstance(d, list) else ([d] if d else [])


def clientes_por_cpf(cpf: str):
    return _get("cliente/list", cpfcnpj=digitos(cpf))


def _faturas(path, client_id):
    try:
        return _get(path, id=str(client_id))
    except MyCoreErro:
        return []  # tolerante: pgtopen às vezes dá timeout; não derruba o resto


def faturas_atrasadas(client_id):
    return _faturas("financeiro/nopgto", client_id)


def faturas_abertas(client_id):
    return _faturas("financeiro/pgtopen", client_id)


# ---------------- formatação ----------------

def _fmt_valor(v):
    try:
        return f"{float(str(v).replace(',', '.')):.2f}".replace(".", ",")
    except Exception:
        return str(v or "")


def _fmt_data(s):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(s or ""))
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else str(s or "")


def _envios_da_fatura(nome, fatura, atrasada):
    """Monta a sequência de mensagens de UMA fatura. 'raw' = sem assinatura (pra copiar limpo).
    Ordem do dono: NEGRITO no que fala da fatura; manda Pix copia-e-cola E a linha do boleto (texto),
    e o boleto pra abrir. (PDF gerado entra por 'pdf_url' quando disponível.)"""
    envios = []
    valor = _fmt_valor(fatura.get("valor"))
    venc = _fmt_data(fatura.get("dt_vencimento"))
    prim = (nome or "").strip().split(" ")[0].title() if nome else ""
    status = " *(está vencida)*" if atrasada else ""
    resumo = (f"*Achei sua fatura aqui{', ' + prim if prim else ''}!* 😊\n"
              f"💰 *Valor: R$ {valor}*\n📅 *Vencimento: {venc}*{status}")
    pix = (fatura.get("pixccola") or "").strip()
    linha = (fatura.get("linhadigitavel") or "").strip()
    pdf_url = (fatura.get("_pdf_url") or "").strip()      # PDF gerado por nós (quando houver)
    boleto_web = (fatura.get("gurl") or fatura.get("url") or "").strip()  # página do gateway (HTML)
    if pix:
        resumo += "\n\nPra pagar na hora, é só copiar o *Pix* abaixo 👇"
    envios.append({"tipo": "texto", "text": resumo})
    if pix:
        envios.append({"tipo": "raw", "text": pix})   # Pix copia-e-cola, mensagem limpa
    if linha:
        envios.append({"tipo": "texto", "text": "Ou pague pelo *boleto* — a *linha digitável* está aqui 👇"})
        envios.append({"tipo": "raw", "text": linha})
    if pdf_url:
        envios.append({"tipo": "pdf", "url": pdf_url, "text": "*Boleto em PDF* 📄"})
    elif boleto_web:
        envios.append({"tipo": "texto", "text": f"🧾 *Ver/abrir o boleto:* {boleto_web}"})
    return envios


def resolver_fatura(cpf: str, contato: str = None) -> dict:
    """Núcleo da regra (CPF-only, ordem do dono 14/07/2026 — sem conferir telefone). Retorna:
      status: 'entregue'  -> envios prontos (achou cadastro + fatura pelo CPF)
              'sem_fatura'-> achou o cadastro, mas está tudo em dia
              'fallback'  -> CPF sem cadastro / erro / MyCore fora -> link + transfere Financeiro
      (contato fica só p/ log/uso futuro; NÃO é mais usado pra liberar a fatura)."""
    try:
        clientes = clientes_por_cpf(cpf)
    except MyCoreErro as e:
        return {"status": "fallback", "motivo": f"mycore_{e.tipo}"}
    if not clientes:
        return {"status": "fallback", "motivo": "cpf_sem_cadastro"}

    nome = clientes[0].get("name") or ""
    atrasadas, abertas = [], []
    for c in clientes:
        cid = c.get("id")
        if not cid:
            continue
        atrasadas += [(f, True) for f in faturas_atrasadas(cid)]
        abertas += [(f, False) for f in faturas_abertas(cid)]
    todas = atrasadas + abertas  # prioriza vencidas
    todas = [t for t in todas if (t[0].get("pixccola") or t[0].get("linhadigitavel") or t[0].get("gurl") or t[0].get("url"))]
    if not todas:
        return {"status": "sem_fatura", "nome": nome}

    fatura, atrasada = todas[0]
    envios = _envios_da_fatura(nome, fatura, atrasada)
    if len(todas) > 1:
        envios.append({"tipo": "texto",
                       "text": f"Você tem mais {len(todas) - 1} fatura(s) em aberto. Quer que eu envie também? 😊"})
    return {"status": "entregue", "nome": nome, "envios": envios, "qtd": len(todas)}
