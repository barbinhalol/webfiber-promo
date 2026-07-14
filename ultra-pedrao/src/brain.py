# -*- coding: utf-8 -*-
"""Cérebro do Ultra Pedrão: monta contexto -> LLM -> parseia JSON -> aplica GUARDS de código.
Os guards NÃO confiam no modelo (bloqueiam preço digitado, placeholder, fastReply/fila inválidos,
e viabilidade afirmada sem o veredito do sistema)."""
import json, os, re
import viability as V
import llm as L
import schedule as S
import sentimento as SENT
try:
    import painel as PAINEL
except Exception:
    PAINEL = None

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
# NUNCA cravar dia/horário de visita ou conserto (ordem do dono). O único compromisso permitido é o
# padrão "próximo dia útil, às 9h" (contato, não visita) — protegido por _AGENDA_OK.
_AGENDA = re.compile(
    r"\b(amanh[ãa]|depois de amanh[ãa]|hoje (mesmo|[àa] (tarde|noite))|"
    r"(segunda|ter[çc]a|quarta|quinta|sexta|s[áa]bado|domingo)(-feira)?|"
    r"dia\s+\d{1,2}(/\d{1,2})?|em\s+\d+\s*(min|minutos?|horas?|h|dias?)|"
    r"[àa]s?\s*\d{1,2}\s*(h\b|hs\b|horas?|:\d{2})|per[íi]odo da (manh[ãa]|tarde|noite))\b", re.I)
# frases PROATIVAS de contato que NÃO são agendamento de visita -> blindadas do guard de data
_AGENDA_OK = re.compile(
    r"(pr[óo]ximo dia [úu]til|entra(m|r)?\s+em contato|entra\s+em\s+contato|"
    r"(nosso|o)\s+(time|setor|pessoal|comercial|suporte|financeiro)\s+(vai|entra|te)|"
    r"vai(m)?\s+(te\s+)?(ligar|chamar|retornar|falar com voc[êe]))", re.I)
# afirmar cobertura/presença antes do veredito do sistema (proibido — a equipe é que confirma).
# Ex. real que vazou: "a gente já tá na tua rua". Suaviza SÓ a frase, sem apagar o resto.
_COBERTURA_ASSERT = re.compile(
    r"(atende(mos)?\s+(sim|a[íi]|bem|essa|nessa|na\s+rua|a\s+rua|l[áa])|"
    r"(bem\s+)?atendid[ao]|j[áa]\s+[ée]\s+(bem\s+)?atendid|"
    r"chega\s+(a[íi]|l[áa])\s+(sim|forte|com|bem)|chega\s+bem|"
    r"j[áa]\s+(t[áa]|est(á|amos|ou)|tamos)\s+(na\s+(sua|tua)\s+rua|a[íi]\b|l[áa]\b)|"
    r"a\s+gente\s+j[áa]\s+(t[áa]|atende|tem\s+rede)|j[áa]\s+(tem|temos)\s+(rede|cobertura|fibra)\s+(a[íi]|na|l[áa])|"
    r"cobertura\s+(confirmada|garantida|boa)|com\s+certeza\s+(atende|chega|vai\s+pegar)|"
    r"vai\s+ter\s+(uma\s+)?internet\s+de\s+qualidade|"
    r"(temos|tem)\s+(rede|fibra|cobertura)\s+(a[íi]|nessa|na\s+sua))", re.I)

def _remove_sentencas(texto, padrao, protege=None):
    """Tira só as FRASES que batem no padrão (mantém o resto da mensagem).
    protege: padrão que blinda uma frase de ser removida (ex.: a frase sancionada das 9h)."""
    blocos = re.split(r'(?<=[.!?\n])\s+', texto)
    limpos = []
    for b in blocos:
        if not b.strip():
            continue
        if padrao.search(b) and not (protege and protege.search(b)):
            continue  # frase problemática -> fora
        limpos.append(b.strip())
    return " ".join(limpos).strip()

def _fila_por_intencao(intencao, motivo):
    s = (str(intencao) + " " + str(motivo)).lower()
    if re.search(r"suporte|t[eé]cnic|sem (internet|sinal|conex)|caiu|lent|oscil|reparo", s): return 24
    if re.search(r"cancel|financ|boleto|cobran|fatura|jur[ií]dic|procon", s): return 25
    if re.search(r"pre[çc]o|plano|viab|cobertura|contrat|comercial|empresa|cnpj", s): return 23
    return 112

# ---------------- ATALHOS SEM LLM (fastpath) ----------------
# Medido ao vivo: o CLI grátis leva ~4,5s só pra abrir processo/rede (chão inevitável) + ~4,5s
# a mais por causa do prompt gigante (~43k caracteres) -- ~9s no total pra reproduzir um texto
# que, pra saudação e pro pedido direto de planos, já é FIXO no prompt (seções 2.6/3.8/5.1).
# Pra esses dois casos claros, respondemos por código (10ms) e pulamos o LLM inteiro. Qualquer
# mensagem fora do padrão exato cai pro decidir() normal -- nunca arrisca qualidade por velocidade.
# SAUDAÇÃO FIXA (ordem do dono): sempre "Olá!" -- NUNCA bom dia/boa tarde/boa noite. Se apresenta
# como atendente virtual (transparência) e serve pra qualquer idade (sem gíria).
_ABERTURA = "Olá! Eu sou o Pedrão, agente virtual da WebFiber 😊 Estou aqui para te ajudar."

_SAUDACAO_PURA = re.compile(
    r"^\s*(oi+|ol[áa]|e\s*a[íi]|opa|bom\s*dia|boa\s*tarde|boa\s*noite|salve|fala(\s*a[íi])?|blz|beleza|tudo\s*bem)\s*[!.,?]*\s*$",
    re.I)
_PLANOS_INTENCAO = re.compile(
    r"\b(planos?|pre[çc]os?|valor(es)?|quanto\s*(custa|fica|[ée]|sai)|pacotes?|mega)\b", re.I)
# empresa/PJ tem planos e ficha DIFERENTES -> não manda o residencial no atalho, vai pro LLM
_EMPRESA = re.compile(r"\b(empresa(rial)?|empresas|cnpj|pessoa\s+jur[íi]dica|\bpj\b|dedicad[ao]|"
                      r"minha\s+(empresa|loja)|meu\s+(escrit[óo]rio|com[ée]rcio|neg[óo]cio)|"
                      r"raz[ãa]o\s+social|est[aá]belecimento)\b", re.I)
# fastReplies do pacote RESIDENCIAL (texto+imagens dos planos e ficha) — bloqueados p/ empresa/PJ
_FIDS_RESIDENCIAL = {1296, 1437, 1438, 1858}
_SINAIS_COMPLEXOS = re.compile(
    r"\b(rua|av\.|avenida|n[°º]|cep|\d{5}-?\d{3}|cancel|problema|ruim|p[ée]ssimo|n[ãa]o\s*funciona|"
    r"caiu|lent[ao]|reclama|advogado|procon|golpe|fraude)\b", re.I)

# ---- roteiro de suporte (como o Pedrão antigo fazia: começou agora? -> tira da tomada 1min +
#      luz piscando? -> resolveu (fecha) ou não resolveu (escala Suporte 24 às 9h do próximo dia útil).
#      Só o básico -- NUNCA diagnostica rede (seção 7 do prompt). Financeiro tem prioridade e sai daqui.
_SUP_INTENCAO = re.compile(
    r"\b(sem\s+(internet|sinal|conex|net)|internet\s+(caiu|parou|ruim|lenta|oscil)|wi-?fi\s+(caiu|parou|n[ãa]o)|"
    r"caiu\s+a\s+(internet|net)|sem\s+wi-?fi|n[ãa]o\s+(navega|pega|funciona|conecta|t[áa]\s+pegando)|"
    r"parou\s+de\s+funcionar|t[áa]\s+(lenta|lento|oscilando|caindo)|internet\s+n[ãa]o)\b", re.I)
_FINANCEIRO_KW = re.compile(
    r"\b(atras|fatura|boleto|cobran|cortaram|cortada|cortou|bloque|esqueci\s+de\s+pagar|"
    r"pagamento|vencid|d[ée]bito|negativ|2[ªa]?\s*via|segunda\s+via|desbloque)\b", re.I)
_SUP_RESOLVIDO = re.compile(
    r"\b(voltou|volto[uw]?|funcion(ou|a)|resolv(eu|ido)|deu\s+certo|normaliz|t[áa]\s+(funcionando|de\s+boa|normal)|"
    r"pegou|conectou|voltei\s+a\s+navegar|ok\s+agora|consegui|j[áa]\s+voltou)\b", re.I)
_SUP_NAO_RESOLVIDO = re.compile(
    r"\b(n[ãa]o\s+(voltou|volto|funcion|resolv|pegou|conectou|adiantou)|continua|mesma\s+coisa|"
    r"nada|ainda\s+(sem|n[ãa]o)|persist|vermelh|piscando|apagad|sem\s+luz|do\s+mesmo\s+jeito|nao\s+deu)\b", re.I)
# muda de assunto no meio do roteiro -> deixa o LLM assumir (server encerra o roteiro)
_DESVIO_ASSUNTO = re.compile(
    r"\b(plano|pre[çc]o|valor|quanto\s+custa|cancel|fatura|boleto|atendente|humano|pessoa\s+de\s+verdade|falar\s+com\s+algu[ée]m)\b", re.I)


def _fp(texto, acao="responder", intencao="saudacao", fila=0, fid=0, nota="", sup=None, icone="⚡"):
    d = {"acao": acao, "texto": texto, "fastReplyId": fid, "fila": fila,
         "intencao": intencao, "viabilidade": "naoaplicavel", "motivo": "",
         "nota_interna": nota, "dados_coletados": ({"sup": sup} if sup is not None else {}),
         "_alertas": [], "_viabilidade_sistema": {"status": "naoaplicavel"},
         "_fastpath": True, "_render": f"{icone} (atalho, sem LLM) “{texto[:80]}”"}
    return d

def _suporte_passo(msg, sup):
    """Cliente já está no roteiro de suporte (sup=1 respondeu 'começou agora'; sup=2 respondeu da luz)."""
    if _DESVIO_ASSUNTO.search(msg):
        return None  # mudou de assunto -> LLM assume (server limpa o estado do roteiro)
    if sup == "1":
        texto = ("Beleza! Vamos tentar o primeiro procedimento juntos 🙌\n\n"
                 "Tira o aparelhinho de internet (a ONU/roteador) da tomada, espera 1 minutinho e liga de novo. "
                 "Enquanto ele religa, dá uma olhada: tem alguma luz *vermelha* acesa ou piscando nele?")
        return _fp(texto, intencao="suporte", sup="2")
    # sup == "2": leu a luz / resultado do reinício
    if _SUP_RESOLVIDO.search(msg) and not _SUP_NAO_RESOLVIDO.search(msg):
        texto = ("Ótimo, que bom que voltou! 😊 Fico à disposição — qualquer coisa é só me chamar. "
                 "Posso te ajudar em mais alguma coisa?")
        return _fp(texto, intencao="suporte", sup="fim")
    if _SUP_NAO_RESOLVIDO.search(msg):
        texto = ("Entendi. Como o procedimento básico não resolveu, já vou registrar tudo certinho aqui pro nosso "
                 "time de *Suporte técnico*. Eles entram em contato com você no próximo dia útil, às 9h, pra "
                 "resolver de vez 😊\n\nPra adiantar, me confirma seu *nome completo*, o *endereço* e um *telefone* de contato?")
        nota = ("[PEDRÃO fora do horário] SUPORTE | cliente sem internet; fez o reinício básico (tirar da tomada 1 min) "
                "e NÃO resolveu | Falta: confirmar nome/endereço/telefone | Retorno agendado: próximo dia útil às 9h.")
        return _fp(texto, acao="transferir", intencao="suporte", fila=24, nota=nota, sup="fim", icone="⚡➡️")
    return None  # resposta ambígua sobre a luz -> LLM decide

def fastpath(mensagem, sessao_nova, historico, fatos=None, sentimento=None):
    """Decisão pronta SEM LLM pros casos previsíveis do prompt: saudação (sempre como atendente
    virtual), pedido claro de planos, e o roteiro de suporte básico passo a passo. Qualquer coisa
    fora do padrão exato retorna None -> cai no decidir() normal (LLM), sem arriscar qualidade."""
    fatos = fatos or {}
    msg = (mensagem or "").strip()
    if not msg:
        return None
    # cliente IRRITADO nunca cai no atalho automático -> vai pro LLM tratar com cuidado e acolhimento
    if sentimento and sentimento.get("humor") == "irritado":
        return None
    sup = "" if sessao_nova else str(fatos.get("sup") or "")

    # 0) roteiro de suporte JÁ em andamento tem prioridade
    if sup in ("1", "2"):
        return _suporte_passo(msg, sup)

    # 1) saudação pura -> abertura fixa "Olá!", sem anunciar conversa anterior (mesmo se reaberta)
    if _SAUDACAO_PURA.match(msg) and not _SINAIS_COMPLEXOS.search(msg):
        if sessao_nova:  # 1º contato OU reaberto: mesma saudação simples, sem relembrar o histórico
            return _fp(f"{_ABERTURA} Me conta o que você precisa.", intencao="saudacao")
        return None  # SESSÃO=CONTINUA: "oi" solto no meio da conversa -> LLM

    # 2) pedido de planos/internet -> FLUXO PRINCIPAL: já conhece os planos? + qual o local (viabilidade)
    #    (empresa/PJ sai pro LLM: planos e ficha empresariais são diferentes)
    if (_PLANOS_INTENCAO.search(msg) and not _SINAIS_COMPLEXOS.search(msg)
            and not _EMPRESA.search(msg) and len(msg.split()) <= 18):
        if sessao_nova:
            texto = (f"{_ABERTURA} Você já conhece nossos planos? E me diz uma coisa: "
                     "qual é o endereço aí (rua, número e bairro) pra eu já verificar a viabilidade pra você?")
            return _fp(texto, intencao="planos")
        texto = ("Perfeito! Vou te mostrar os planos aqui 👇\n\n"
                  "E me passa o endereço — rua, número e bairro — pra eu já verificar a viabilidade pra você.")
        return _fp(texto, acao="fastreply", intencao="planos", fid=1296, icone="⚡📎")

    # 3) início de suporte (só o básico; financeiro tem prioridade e sai pro LLM)
    if _SUP_INTENCAO.search(msg) and not _FINANCEIRO_KW.search(msg):
        abre = (_ABERTURA + " ") if sessao_nova else ""
        texto = (abre + "Poxa, que chato ficar sem internet! Vou te ajudar a resolver 😊 "
                 "Me diz uma coisa: isso começou agora ou já vem acontecendo há um tempo?")
        return _fp(texto, intencao="suporte", sup="1")

    return None

def _parse_json(txt):
    if not txt: return None
    i, j = txt.find("{"), txt.rfind("}")
    if i < 0 or j < 0: return None
    try: return json.loads(txt[i:j+1])
    except Exception: return None

def decidir(mensagem, historico=None, memoria_cliente=None, sessao_nova=False, resumo="", sentimento=None):
    """historico: [{'de':'cliente'|'pedrao','texto':...}]; memoria_cliente: dict de fatos por contato.
    resumo: resumo textual da conversa (memória nível 2) — injetado no contexto pra o bot lembrar do
    começo de conversas longas, mesmo depois que as msgs antigas saem da janela imediata.
    sessao_nova: True quando o atendimento está começando (primeiro contato ou reabertura após fechamento) —
    vira o marcador [SESSÃO=NOVA]/[SESSÃO=CONTINUA] que a seção 3.8 do prompt usa pra decidir se cumprimenta."""
    historico = historico or []
    texto_todo = " ".join([h.get("texto", "") for h in historico] + [mensagem])
    viab = V.checar(texto_todo)

    linhas = [("Pedrão" if h.get("de") in ("pedrao", "bot", "atendente") else "Cliente") + ": " + h.get("texto", "")
              for h in historico]
    linhas.append("Cliente: " + mensagem)

    ctx = []
    marcador = "[SESSÃO=NOVA]" if sessao_nova else "[SESSÃO=CONTINUA]"
    if sessao_nova and historico:
        ctx.append(marcador + " — atendimento reaberto: já existe histórico com esse cliente, sinalize a retomada em vez de cumprimentar como se fosse a primeira vez.")
    elif sessao_nova:
        ctx.append(marcador + " — primeiro contato desse cliente: abra com a saudação fixa.")
    else:
        ctx.append(marcador + " — mesma conversa em andamento: não cumprimente de novo.")
    if resumo and resumo.strip():
        ctx.append("RESUMO DO QUE JÁ FOI CONVERSADO ANTES (memória da conversa — use pra não esquecer o "
                   "começo nem pedir de novo o que o cliente já disse): " + resumo.strip())
    if memoria_cliente:
        ctx.append("MEMÓRIA DO CLIENTE (fatos já sabidos — não pergunte de novo): " + json.dumps(memoria_cliente, ensure_ascii=False))
    ctx.append("CONVERSA ATÉ AGORA:\n" + "\n".join(linhas))
    ctx.append(V.hint_para_prompt(viab))
    _tom = SENT.hint_tom(sentimento)
    if _tom:
        ctx.append(_tom)
    if PAINEL:
        extra = PAINEL.contexto_extra()
        if extra:
            ctx.append(extra)
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
    # EMPRESA/PJ: NUNCA mandar o pacote RESIDENCIAL (planos/ficha). Se o modelo tentar, troca por
    # coleta empresarial — a WebFiber tem planos e ficha próprios de empresa (ordem do dono).
    if acao == "fastreply" and fid in _FIDS_RESIDENCIAL and _EMPRESA.search(texto_todo):
        alertas.append("GUARD: empresa/PJ -> nao envia residencial, coleta dados empresariais")
        acao, fid, fila = "responder", 0, 0
        texto = ("Perfeito! Pra empresa a gente tem planos e condições próprias, diferentes do residencial 😊 "
                 "Me passa por gentileza o CNPJ, a razão social e o endereço do estabelecimento "
                 "(rua, número e bairro)? Já registro aqui e nosso time Comercial te retorna com as "
                 "condições empresariais certinhas.")
        d["nota_interna"] = ((d.get("nota_interna") or "").strip() +
                             " [LEAD EMPRESARIAL/PJ — passar condições empresariais, NÃO residencial]").strip()
    # viabilidade só "confirmada_predio" se o CÓDIGO confirmou
    if d.get("viabilidade") == "confirmada_predio" and viab["status"] != V.CONFIRMADA_PREDIO:
        alertas.append("GUARD: modelo afirmou cobertura sem veredito -> rebaixado")
        d["viabilidade"] = "provavel" if viab["status"] == V.PROVAVEL else "a_confirmar"
        if acao != "fastreply":
            acao, fila = "transferir", 23
    # ORDEM DO DONO: o bot NUNCA confirma nem nega cobertura (nem pra rua conhecida) — quem confirma
    # é a equipe. Suaviza SÓ a frase de cobertura (mantém o resto: planos, próximo passo).
    if texto and _COBERTURA_ASSERT.search(texto):
        alertas.append("GUARD: afirmacao de cobertura suavizada")
        novo = _remove_sentencas(texto, _COBERTURA_ASSERT)
        texto = novo if len(novo) >= 15 else ("A chance de atender aí é boa! Mas deixa eu confirmar a viabilidade "
                 "certinha do seu endereço com a equipe pra não te passar info errada.")
    # NUNCA cravar data/hora de visita/conserto — remove SÓ a frase da data (mantém o resto da resposta);
    # a frase sancionada "próximo dia útil às 9h" é blindada por _AGENDA_OK.
    if texto and _AGENDA.search(texto) and not _AGENDA_OK.search(texto):
        alertas.append("GUARD: promessa de data/hora removida (cirurgico)")
        novo = _remove_sentencas(texto, _AGENDA, protege=_AGENDA_OK)
        # NUNCA "não consigo" — mensagem PROATIVA e positiva (ordem do dono)
        texto = novo if len(novo) >= 15 else ("Perfeito, já deixei tudo registrado aqui! 😊 Nosso setor entra em "
                 "contato com você no próximo dia útil, pela manhã. Pode ser por aqui mesmo, neste número?")
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
