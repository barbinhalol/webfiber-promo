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
    """Roteamento de setor (ordem do dono 14/07/2026):
    suporte -> Suporte(24) | planos/comercial -> Comercial(23) | financeiro -> Financeiro(25)
    | CANCELAMENTO -> Outros assuntos(26) — cancelamento NÃO vai pro Financeiro."""
    s = (str(intencao) + " " + str(motivo)).lower()
    if re.search(r"suporte|t[eé]cnic|sem (internet|sinal|conex)|caiu|lent|oscil|reparo", s): return 24
    # cancelamento ANTES do financeiro (senão "cancelar boleto" cairia no Financeiro)
    if re.search(r"cancel|rescis|desist|encerrar\s+(o\s+)?(contrato|plano|servi[çc]o)", s): return 26
    if re.search(r"financ|boleto|cobran|fatura|pagamento|2[ªa]?\s*via|jur[ií]dic|procon", s): return 25
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

# aceita saudações ENCADEADAS ("ola, boa noite!", "oi bom dia", "opa tudo bem", "voltei") — o `+`
# no fim do grupo deixa repetir; senão "Ola, boa noite!" não casava e caía no LLM (que recapitulava).
_SAUDACAO_PURA = re.compile(
    r"^\s*((oi+|ol[áa]|e\s*a[íi]|opa|bom\s*dia|boa\s*tarde|boa\s*noite|salve|fala(\s*a[íi])?|"
    r"blz|beleza|tudo\s*bem|tudo\s*bom|voltei|cheguei)[\s,!.?]*)+$",
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

# cliente se REFERE a algo dito antes ("você não viu aqui em cima", "já te falei"): mesmo numa
# conversa FECHADA e reaberta (que começa do zero), aí o Pedrão PODE ler o histórico pra responder.
_REF_ANTERIOR = re.compile(
    r"\b(a[íi]\s*em\s*cima|l[áa]\s*em\s*cima|(logo\s*|mais\s*)?acima|n[ãa]o\s*(viu|leu)|"
    r"j[áa]\s*(te\s*)?(falei|disse|mandei|expliquei|avisei|passei|informei|perguntei)|"
    r"te\s*(falei|mandei|passei|disse)|como\s*(eu\s*)?(falei|disse)|conforme\s*(falei|disse)|"
    r"lembra\s*que|acabei\s*de\s*(falar|dizer|mandar))\b", re.I)

def refere_anterior(texto):
    """True se o cliente cita algo já dito antes — libera ler o histórico mesmo em sessão nova."""
    return bool(_REF_ANTERIOR.search(texto or ""))

# ---- DESBLOQUEIO EM CONFIANÇA (só age com o recurso LIGADO no painel) ----
_DESBLOQ_KW = re.compile(
    r"\b(desbloque|desbloqui|em\s*confian[çc]a|na\s*confian[çc]a|me\s*(libera|libere|desbloqueia)|"
    r"religa(r|\s*a)?|reativa(r|\s*a)?|me\s*d[áa]\s*(uns|mais|alguns)\s*dias|"
    r"pag(o|ar)\s*(depois|semana|dia|amanh[ãa])|s[óo]\s*(consigo\s*)?pag(ar|o))\b", re.I)
_SIM = re.compile(r"\b(sim|quero|pode|isso|claro|com\s*certeza|aceito|fa[çz]a?|pode\s*ser|bora|"
                  r"ok|isso\s*mesmo|desejo|por\s*favor|manda|vamos|blz|beleza)\b", re.I)
_NAO = re.compile(r"\b(n[ãa]o|agora\s*n[ãa]o|deixa|depois|melhor\s*n[ãa]o|nem)\b", re.I)


def _fastpath_desbloqueio(msg, fatos, contato, sessao_nova):
    """Fluxo do desbloqueio em confiança (só é chamado quando o dono LIGA no painel):
    pede CPF -> confere elegibilidade -> pergunta 'deseja fazer?' -> no 'sim', libera (promesset),
    dá o prazo de 3 dias às 19h e avisa que é 1x por mês."""
    import mycore as MC, respostas as R
    from datetime import datetime
    mes_atual = datetime.now().strftime("%Y-%m")
    desb = "" if sessao_nova else str(fatos.get("desb") or "")

    # (2) confirmação pendente -> executa no "sim"
    if desb == "confirma":
        if _NAO.search(msg) and not _SIM.search(msg):
            return _fp("Sem problema! 😊 Qualquer coisa é só me chamar. Quer que eu te mande o boleto pra pagar?",
                       intencao="financeiro", dados={"desb": "feito"})
        if _SIM.search(msg):
            cpf, bid, mes = fatos.get("desb_cpf"), fatos.get("desb_bid"), (fatos.get("desb_mes") or "")
            if not (cpf and bid):
                return _fp("Deixa eu confirmar rapidinho — me manda seu *CPF* de novo, por gentileza? 😊",
                           intencao="financeiro", dados={"desb": "aguarda_cpf_desb"})
            try:
                MC.executar_desbloqueio(cpf, bid)
            except Exception:
                return _fp("Puxa, não consegui concluir o desbloqueio agora 😕 Vou te passar pra nossa equipe do "
                           "Financeiro pra resolver rapidinho, tá?", acao="transferir", fila=25,
                           intencao="financeiro", dados={"desb": "feito"})
            prazo = MC.prazo_desbloqueio(3)
            txt = (f"Prontinho, liberei o seu acesso em confiança! ✅\n\n"
                   f"A fatura de *{mes}* precisa ser paga até *dia {prazo}, às 19h*.\n\n"
                   f"Só um lembrete com carinho: o *desbloqueio em confiança* pode ser feito *uma vez por mês* — "
                   f"depois disso, o sistema só reativa com o pagamento. Combinado? 😊")
            return _fp(txt, intencao="financeiro", dados={"desb": "feito", "desbloqueio_mes": mes_atual, "nota_ok": 1})
        return None  # resposta ambígua -> deixa o LLM conduzir

    # (1) intenção de desbloqueio (ou já estava esperando o CPF pro desbloqueio)
    if not (_DESBLOQ_KW.search(msg) or desb == "aguarda_cpf_desb"):
        return None
    if fatos.get("desbloqueio_mes") == mes_atual:
        return _fp("Vi aqui que o *desbloqueio em confiança* já foi usado este mês 😊 Ele pode ser feito só uma vez "
                   "por mês — pra reativar agora, é pelo pagamento. Quer que eu te mande o boleto?",
                   intencao="financeiro", dados={"desb": "feito"})
    cpf = MC.extrair_cpf_cnpj(msg)
    if not cpf:
        return _fp("Claro! Pra fazer o *desbloqueio em confiança*, me manda só o seu *CPF* (pode ser só os "
                   "números) 😊", intencao="financeiro", dados={"desb": "aguarda_cpf_desb"})
    try:
        res = MC.resolver_desbloqueio(cpf)
    except Exception:
        res = {"status": "erro"}
    if res.get("status") == "elegivel":
        return _fp(f"Vi que a sua fatura de *{res['mes']}* está em aberto e o acesso está suspenso. Posso te fazer um "
                   f"*desbloqueio em confiança* de *3 dias*, pra você usar enquanto regulariza 😊\n\n"
                   f"*Você deseja fazer o desbloqueio em confiança?*",
                   intencao="financeiro",
                   dados={"desb": "confirma", "desb_cpf": res["cpf"], "desb_bid": res["boleto_id"],
                          "desb_mes": res["mes"]})
    if res.get("status") == "sem_atraso":
        return _fp("Boa notícia: não vi nenhuma fatura em atraso no seu CPF 😊 seu acesso não está bloqueado por "
                   "pagamento. Se estiver sem internet, me conta que eu te ajudo pelo suporte!",
                   intencao="financeiro", dados={"desb": "feito"})
    # sem cadastro / erro -> Financeiro humano (não inventa nada)
    return _fp(R.FINANCEIRO_FATURA, acao="transferir", fila=25, intencao="financeiro",
               nota="[Pedrão] Desbloqueio: não localizei pelo CPF (ou MyCore fora); enviei o link e transferi.",
               dados={"desb": "feito"})


def _fp(texto, acao="responder", intencao="saudacao", fila=0, fid=0, nota="", sup=None, icone="⚡", dados=None):
    dc = dict(dados or {})
    if sup is not None:
        dc["sup"] = sup
    d = {"acao": acao, "texto": texto, "fastReplyId": fid, "fila": fila,
         "intencao": intencao, "viabilidade": "naoaplicavel", "motivo": "",
         "nota_interna": nota, "dados_coletados": dc,
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

def fastpath(mensagem, sessao_nova, historico, fatos=None, sentimento=None, contato=None):
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

    # 2.5) FINANCEIRO (boleto/fatura/2ª via/atraso/bloqueio) — INTEGRAÇÃO MyCore (ordem do dono
    #      14/07/2026): o cliente pede a fatura, o Pedrão pede o CPF e ENTREGA no chat (Pix + boleto),
    #      SEM link. Só entrega se o CPF bater com o número de WhatsApp (anti-golpe/LGPD). Se não
    #      bater/achar/erro -> cai no link da área do cliente + transfere Financeiro (25).
    import respostas as R
    # 2.4) DESBLOQUEIO EM CONFIANÇA — só age quando o dono LIGA no painel (senão, dorme)
    try:
        _desb_on = bool(PAINEL and PAINEL.desbloqueio_ativo())
    except Exception:
        _desb_on = False
    if _desb_on:
        _dsb = _fastpath_desbloqueio(msg, fatos, contato, sessao_nova)
        if _dsb is not None:
            return _dsb

    fin_state = "" if sessao_nova else str(fatos.get("fin") or "")
    # entra no fluxo se pediu financeiro AGORA, ou se está aguardando o CPF E a msg tem dígitos
    # (uma tentativa de CPF) — assim, se o cliente mudar de assunto no meio, não fica preso.
    _tem_digitos = len(re.sub(r"\D", "", msg)) >= 8
    if _FINANCEIRO_KW.search(msg) or (fin_state == "aguarda_cpf" and _tem_digitos):
        import mycore as MC
        cpf = MC.extrair_cpf_cnpj(msg)
        _abre = (_ABERTURA + "\n\n") if sessao_nova else ""
        # limpa o estado do financeiro. fin="feito" (não "" — o merge_fatos ignora vazios) tira do
        # modo "aguarda_cpf"; nota_ok=1 evita virar "lead" no vigia dos 20min.
        _limpa_fin = {"fin": "feito", "fin_try": 0, "nota_ok": 1}
        if cpf and MC.token_configurado():
            try:
                res = MC.resolver_fatura(cpf, contato)   # CPF-only: contato não gateia mais
            except Exception:
                res = {"status": "fallback", "motivo": "excecao"}
            if res.get("status") == "entregue":
                d = _fp("", acao="faturas", intencao="financeiro", dados=_limpa_fin, icone="💳")
                d["_envios"] = res["envios"]
                d["_render"] = f"💳 (fatura) {res.get('qtd')} em aberto — entregaria Pix+boleto no chat"
                return d
            if res.get("status") == "sem_fatura":
                nome = (res.get("nome") or "").split(" ")[0].title()
                txt = (f"Boa notícia{', ' + nome if nome else ''}! 😊 Não encontrei nenhuma fatura em "
                       "aberto no seu CPF — parece que está tudo em dia. Precisando de mais alguma "
                       "coisa do financeiro, é só me chamar.")
                return _fp(_abre + txt, intencao="financeiro", dados=_limpa_fin, icone="✅")
            # fallback: CPF sem cadastro / MyCore fora -> link + transfere Financeiro
            return _fp(_abre + R.FINANCEIRO_FATURA, acao="transferir", intencao="financeiro", fila=25,
                       nota="[Pedrão] Financeiro — não achei fatura pelo CPF (ou MyCore fora); "
                            "enviei o link e transferi.", dados=_limpa_fin, icone="⚡➡️")
        # sem CPF ainda (ou MyCore não configurado): pede o CPF, no máx 2 tentativas
        tries = int(fatos.get("fin_try") or 0)
        if not MC.token_configurado() or tries >= 2:
            return _fp(_abre + R.FINANCEIRO_FATURA, acao="transferir", intencao="financeiro", fila=25,
                       nota="[Pedrão] Financeiro — enviei o link e transferi pro setor.",
                       dados=_limpa_fin, icone="⚡➡️")
        # tem dígitos mas não validou como CPF? avisa; senão, pede pela 1ª vez
        txt = ("Esse CPF não parece certo — confere e me manda de novo, só os números? 😊"
               if _tem_digitos else
               "Claro! Pra já puxar a sua fatura aqui, me manda só o seu *CPF* (pode ser só os números) 😊")
        return _fp(_abre + txt, intencao="financeiro", dados={"fin": "aguarda_cpf", "fin_try": tries + 1},
                   icone="⚡")

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
        ctx.append(marcador + " — atendimento reaberto (já há histórico). Cumprimente de forma SIMPLES "
                   "com a saudação padrão ('Olá!') e siga a conversa. É PROIBIDO recapitular ou comentar "
                   "em voz alta o que já foi falado antes (nada de 'que bom que você voltou', 'você queria "
                   "o plano X na Rua Y', 'você tava pensando na empresa'...). Isso soa invasivo e bisbilhoteiro. "
                   "Use o histórico SÓ internamente, pra não repetir perguntas que o cliente já respondeu.")
    elif sessao_nova:
        ctx.append(marcador + " — primeiro contato desse cliente: abra com a saudação fixa.")
    else:
        ctx.append(marcador + " — mesma conversa em andamento: não cumprimente de novo.")
    if resumo and resumo.strip():
        ctx.append("RESUMO DO QUE JÁ FOI CONVERSADO ANTES (memória INTERNA — use SÓ pra não repetir "
                   "perguntas; NUNCA recapitule nem cite em voz alta o que já foi conversado): " + resumo.strip())
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
    # ORDEM DO DONO (14/07/2026 — revisada): o bot PODE confirmar cobertura QUANDO o código confirmou
    # o prédio (3+ clientes no mesmo rua+número = CONFIRMADA_PREDIO). Fora disso, NUNCA confirma nem
    # nega — quem confirma é a equipe. Suaviza SÓ a frase de cobertura (mantém planos e próximo passo).
    if texto and viab["status"] != V.CONFIRMADA_PREDIO and _COBERTURA_ASSERT.search(texto):
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
