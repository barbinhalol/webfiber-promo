# -*- coding: utf-8 -*-
"""Cérebro do Ultra Pedrão: monta contexto -> LLM -> parseia JSON -> aplica GUARDS de código.
Os guards NÃO confiam no modelo (bloqueiam preço digitado, placeholder, fastReply/fila inválidos,
e viabilidade afirmada sem o veredito do sistema)."""
import json, os, re, time
import config as C
import viability as V
import llm as L
import schedule as S
import sentimento as SENT
import regras as REG
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
# CONDIÇÃO COMERCIAL INVENTADA (25/07, teste ao vivo): perguntado "vocês cobram taxa de
# instalação?", o bot respondeu "Sim, a gente cobra instalação — mas dá pra parcelar em até 3x
# no cartão". Nada disso foi confirmado pelo dono: é a regra 11 (nunca invente) sendo furada por
# um caminho que o guard de PREÇO não cobria, porque não tem número em reais.
_COND_COMERCIAL = re.compile(
    r"\b(\d+\s*x\s*(no\s+|sem\s+|de\s+)?(cart[ãa]o|juros|vezes)|parcel\w+\s+em\s+\d+|"
    r"(taxa|custo|valor)\s+de\s+(instala|ades[ãa]o|habilita)\w*|"
    r"(cobra|cobramos|tem)\s+(taxa|ades[ãa]o|multa|fidelidade)|"
    r"(instala[çc][ãa]o|ades[ãa]o|visita)\s+(é|e|sai|fica|custa)\s+(gr[áa]tis|de\s+gra[çc]a|zero)|"
    r"sem\s+(taxa|custo|fidelidade|multa)\s+(de\s+)?(instala|ades|nenhum)|"
    r"(gr[áa]tis|de\s+gra[çc]a|isento)\s+(a\s+)?(instala[çc][ãa]o|ades[ãa]o|taxa))\b", re.I)
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
    r"(temos|tem)\s+(rede|fibra|cobertura)\s+(a[íi]|nessa|na\s+sua)|"
    # 25/07 (teste ao vivo): "voces fazem instalacao em qual bairro? moro na tijuca" ->
    # "A gente atende na Tijuca sim!" -- afirmação de cobertura com NOME DE BAIRRO, que os
    # padrões acima (que exigiam "na rua"/"aí"/"lá") não pegavam. O "(?<!se )" preserva a frase
    # legítima "quem confirma SE a gente atende o endereço novo é a equipe".
    r"(?<!se\s)\batende(mos)?\s+(a|na|no|em)\s+\w+[^.!?]{0,20}\bsim\b|"
    r"\batendemos\s+(a|na|no|em|essa|esse|sua|seu)\b|"
    r"\b(sim|claro|com\s+certeza)[,!]?\s+(a\s+gente\s+|n[óo]s\s+)?atende(mos)?\b|"
    r"\bj[áa]\s+atende(mos)?\s+(a|na|no|em)\s+\w+)", re.I)

# "SE a gente atende o endereço novo, quem confirma é a equipe" é o oposto de uma promessa --
# é justamente a frase certa. Sem isto, o guard apagava a resposta correta junto com a errada.
_COB_CONDICIONAL = re.compile(r"\bse\b[^.!?]{0,40}\batende|\bconfirm\w+[^.!?]{0,40}\batende|"
                              r"\batende[^.!?]{0,30}\b[ée]\s+a\s+(nossa\s+)?equipe", re.I)

def _afirma_cobertura(texto):
    """True só quando o texto AFIRMA que atende. Frase condicional/de encaminhamento não conta."""
    for frase in re.split(r"(?<=[.!?\n])\s+", texto or ""):
        if _COBERTURA_ASSERT.search(frase) and not _COB_CONDICIONAL.search(frase):
            return True
    return False

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

def _abertura():
    """Saudação efetiva: usa a customizada do painel (ex.: evento/feriado) se o dono deixou uma;
    senão cai na padrão fixa acima. Lida do disco a cada chamada -> o dono troca no painel e vale
    JÁ na próxima mensagem, sem deploy (mesmo mecanismo do PAINEL.ajustes)."""
    if PAINEL:
        try:
            custom = PAINEL.saudacao_custom()
            if custom:
                return custom
        except Exception:
            pass
    return _ABERTURA

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
    r"\b(sem\s+(internet|sinal|conex|net|rede|wi-?fi)|"
    r"(internet|net|wi-?fi|conex[ãa]o|sinal|rede)\s+(caiu|parou|ruim|lenta|oscil|caindo|p[ée]ssim|frac[ao])|"
    r"problema\s+(no|na|com)\b.{0,20}?(internet|net|sinal|conex|wi-?fi|rede)|"
    r"caiu\s+a\s+(internet|net)|"
    r"n[ãa]o\s+(navega|pega|funciona|conecta|t[áa]\s+(pegando|funcionando|dando|conectando))|"
    r"parou\s+de\s+funcionar|t[áa]\s+(lenta|lento|oscilando|caindo|ruim|frac[ao])|internet\s+n[ãa]o)\b", re.I)
# indica queda TOTAL (sem sinal nenhum) -> só esse caso justifica dizer "sem internet" na abertura;
# "fraca/lenta/oscilando" é queixa de qualidade, não de ausência (achado 24/07: Pedrão abriu com
# "sinto muito que esteja SEM internet" pra uma cliente que só reclamou de sinal fraco).
_SUP_TOTAL = re.compile(r"\bsem\s+(internet|sinal|conex|net|rede|wi-?fi)\b|\bcaiu\b|parou\s+de\s+funcionar", re.I)
_FINANCEIRO_KW = re.compile(
    # 24/07: mesmo bug do sentimento.py -- stem sem \w* nunca batia a forma real da palavra
    # ("atras\b" não pega "atrasada", "cobran\b" não pega "cobrança/cobrando", etc.). Testado:
    # "minha conta tá atrasada", "tô sendo cobrada", "fui bloqueado", "nome foi negativado" e
    # "quero o desbloqueio" caíam TODOS fora do atalho (iam pro LLM, mais lento) antes do \w*.
    # "cobran\w*" pega cobrança/cobrando; "cobrada/cobrado" é outro radical (particípio) -- cobrad\w*
    r"\b(atras\w*|fatura|boleto|cobran\w*|cobrad\w*|cortaram|cortada|cortou|bloque\w*|esqueci\s+de\s+pagar|"
    r"pagamento|vencid\w*|d[ée]bito|negativ\w*|2[ªa]?\s*via|segunda\s+via|desbloque\w*|financeiro)\b", re.I)
_SUP_RESOLVIDO = re.compile(
    r"\b(voltou|volto[uw]?|funcion(ou|a)|resolv(eu|ido)|deu\s+certo|normaliz|t[áa]\s+(funcionando|de\s+boa|normal)|"
    r"pegou|conectou|voltei\s+a\s+navegar|ok\s+agora|consegui|j[áa]\s+voltou)\b", re.I)
_SUP_NAO_RESOLVIDO = re.compile(
    r"\b(n[ãa]o\s+(voltou|volto|funcion|resolv|pegou|conectou|adiantou)|continua|mesma\s+coisa|"
    r"nada|ainda\s+(sem|n[ãa]o)|persist|vermelh|loss|piscando|apagad|sem\s+luz|do\s+mesmo\s+jeito|nao\s+deu)\b", re.I)
# sinal ESPECÍFICO de que o cliente de fato relatou a luz/o problema técnico -> só ESSE caso pode
# fechar afirmando "luz vermelha" pro cliente e pra equipe. Achado 24/07: cliente só respondeu
# "não mudou nada" (sem citar cor nenhuma) e o roteiro fechou dizendo "a luz continuou vermelha" —
# dado inventado, foi pro cliente E pra nota interna que a equipe técnica usa pra agir.
_SUP_LUZ_VERMELHA = re.compile(r"\b(vermelh\w*|loss|piscando|apagad\w*|sem\s+luz)\b", re.I)
# 25/07 (auditoria): a regex acima AINDA deixava o bot inventar diagnóstico -- ela casa
# "piscando", "apagado", "sem luz" e até "a luz NÃO está vermelha", e o roteiro fechava
# afirmando "luz vermelha" pro cliente E pra nota da equipe técnica. Só fecha com o roteiro
# da fibra quem DISSE vermelha/LOSS, sem negação.
_LUZ_VERMELHA_POS = re.compile(r"\b(vermelh[ao]s?|loss)\b", re.I)
_LUZ_NEGADA = re.compile(r"\b(n[ãa]o|nenhum[ao]?|sem)\b[^.!?]{0,25}\b(vermelh|loss)", re.I)
_LUZ_OUTRA = re.compile(r"\b(piscando|apagad\w*|sem\s+luz|verde|azul|laranja|amarel\w*|branca)\b", re.I)

def _luz_vermelha_confirmada(msg):
    return bool(_LUZ_VERMELHA_POS.search(msg)) and not _LUZ_NEGADA.search(msg)

# "voltou MAS ainda tá ruim" NÃO é resolvido -- e queda que volta e cai de novo é justamente a
# INTERMITENTE, que a regra 5 manda tratar como prioridade (o bot encerrava com "Que ótimo!").
_SUP_RESSALVA = re.compile(
    r"\b(mas|por[ée]m|s[óo]\s+que|ainda\s+(assim|t[áa]|est[áa]|sem)|de\s+novo|dnv|novamente|toda\s+hora|"
    r"cai(u|ndo)|volta\s+e\s+cai|lent[ao]|frac[ao]|oscil\w*|ruim|inst[áa]ve|travand|"
    r"(uns?|alguns)\s*\d+\s*(min|minutos?|segundos?)|parou)\b", re.I)

# cliente JÁ reiniciou por conta própria -> regra 5 proíbe pedir de novo ("já reiniciei mil vezes")
_JA_REINICIOU = re.compile(
    r"\b(j[áa]\s+(reinici\w*|resetei|reset\w*|desliguei|liguei\s+e\s+desliguei|tirei\s+da\s+tomada|"
    r"tirei\s+e\s+(coloquei|botei)|fiz\s+isso)|"
    r"(reinici\w*|desliguei|tirei\s+da\s+tomada)\s+(v[áa]rias|muitas|mil|umas?\s*)?\d*\s*(vezes|x)\b|"
    r"reiniciei)\b", re.I)

# cliente não consegue olhar o aparelho agora -> parar de insistir na cor da luz
_NAO_SABE = re.compile(
    r"\b(n[ãa]o\s+(sei|consigo|d[áa]\s+pra?|posso)\s*(ver|olhar|checar)?|n[ãa]o\s+(t[ôo]|estou)\s+em\s+casa|"
    r"t[ôo]\s+(fora|na\s+rua|no\s+trabalho)|longe\s+de\s+casa|s[óo]\s+(mais\s+tarde|amanh[ãa]|quando\s+chegar)|"
    r"n[ãa]o\s+tem\s+ningu[ée]m\s+em\s+casa)\b", re.I)

# RECLAMAÇÃO financeira != pedido de 2ª via. Mandar boleto em aberto pra quem acabou de dizer
# "já paguei e vocês cortaram" é receita de fúria e Procon (regra 6: registrar e encaminhar).
# "2ª via" NÃO é sempre fatura: contrato, comprovante de quitação e declaração de IR usam a mesma
# palavra e o bot respondia "pra puxar a sua FATURA, me manda o CPF" (visto no teste) -- ignorando
# o que a pessoa pediu. Isso o Pedrão não emite (regra 21): registra e encaminha.
_DOC_NAO_FATURA = re.compile(
    r"\b(contrato|comprovante\s+de\s+(quita|pagamento)|declara[çc][ãa]o|imposto\s+de\s+renda|\birpf\b|"
    r"nota\s+fiscal|\bnf-?e\b|titularidade|transferir\s+(a\s+)?(conta|titular)|"
    r"mudar\s+(o\s+)?(nome|titular)|hist[óo]rico\s+de\s+pagamento)\b", re.I)

_FIN_RECLAMACAO = re.compile(
    r"\b(j[áa]\s+(paguei|foi\s+pago|t[áa]\s+pag\w*)|paguei\s+(e|mas|ontem|hoje|dia|no\s+dia)|comprovante|"
    r"cobran[çc]a\s+(indevida|errada|duplicada|a\s+mais)|cobrando\s+(a\s+mais|errado|dobrado|duas\s+vezes)|"
    r"n[ãa]o\s+reconhe[çc]o|valor\s+(errado|diferente|a\s+mais)|negativ\w*|serasa|spc|"
    r"desconto|parcel\w*|acordo|mudar\s+(o\s+)?vencimento|adiar|prorrog\w*|"
    # 25/07 (teste ao vivo): "posso pagar semana que vem? to sem grana agora" recebia uma
    # resposta incoerente pedindo endereço. Pedir PRAZO é regra 6: o Pedrão não tem autoridade,
    # só registra e encaminha ao Financeiro.
    r"pag(ar|o)\s+(semana|mes|m[êe]s|dia|depois|amanh[ãa]|segunda|s[óo]\s+dia)|"
    r"(sem|t[ôo]\s+sem|estou\s+sem)\s+(grana|dinheiro|condi[çc])|"
    r"d[áa]\s+pra\s+esperar|me\s+d[áa]\s+(um\s+)?prazo|mais\s+(uns\s+)?dias?\s+pra\s+pagar)\b", re.I)

# JÁ É CLIENTE falando do PRÓPRIO plano (upgrade, velocidade entregue): NÃO é lead novo --
# mandar tabela de planos e pedir endereço "pra ver viabilidade" pra quem é cliente há meses
# é a resposta que faz a pessoa perder a paciência.
_JA_CLIENTE = re.compile(
    r"\b(meu|minha)\s+(plano|internet|velocidade|pacote|contrato|linha)\b|"
    r"\b(contratei|assinei|pago|tenho|uso)\b[^.!?]{0,20}\b(plano|mega|giga|internet)\b|"
    r"\b(aumentar|subir|melhorar|trocar|mudar|migrar|upgrade|downgrade|reduzir|baixar)\b[^.!?]{0,15}"
    r"\b(plano|velocidade|internet|pacote)\b|"
    r"\b(teste\s+de\s+velocidade|speedtest|s[óo]\s+(d[áa]|chega|vem|t[áa]\s+dando)\s*\d+)\b", re.I)

# MUDANÇA DE ENDEREÇO. 25/07: testado ao vivo, o modelo respondia "Dá sim! A gente leva a
# internet junto" SEM saber o endereço -- promessa de cobertura que a equipe pode não cumprir.
# Reescrever a regra não bastou (o prompt principal puxa forte pro fluxo de venda), então virou
# CÓDIGO: resposta fixa, correta, e de graça.
# 25/07: a 1ª versão casava "mudar" solto -- e "quero mudar a SENHA do meu wifi" caiu no fluxo
# de mudança de endereço, respondendo "me passa o endereço novo". Agora exige contexto de LUGAR.
_MUDANCA_END = re.compile(
    r"\b(me\s+mudo|vou\s+me\s+mudar|t[ôo]\s+de\s+mudan[çc]a|"
    r"mud(ar|an[çc]a|ando)\s+(de\s+)?(casa|endere[çc]o|apartamento|resid[êe]ncia|im[óo]vel|"
    r"pra\s+outr[ao]|de\s+bairro)|"
    r"troc(ar|a)\s+de\s+(casa|endere[çc]o)|casa\s+nova|apartamento\s+novo|"
    r"outro\s+endere[çc]o|novo\s+endere[çc]o|"
    r"transferir\s+(a\s+)?(internet|linha|ponto))\b", re.I)
# "plano" fica de FORA daqui: "quero mudar meu plano" é upgrade (regra 18), não mudança de casa.
_LEVAR_INTERNET = re.compile(
    r"\b(levar?|lev(o|a)|transferir)\b[^.!?]{0,30}\b(internet|net|linha|ponto|servi[çc]o)\b|"
    r"\b(internet|net)\b[^.!?]{0,20}\bvai\s+junto\b", re.I)

# quer TROCAR de plano (upgrade/downgrade) — intenção de mudança, não reclamação
# "internet" fica de FORA: "mudar a internet" tanto pode ser trocar de plano quanto levar pra
# outra casa -- ambíguo demais pra atalho, vai pro LLM. Upgrade fala de plano/velocidade/mega.
_QUER_UPGRADE = re.compile(
    r"\b(aumentar|subir|melhorar|trocar|mudar|migrar|upgrade|downgrade|reduzir|baixar|passar)\b"
    r"[^.!?]{0,20}\b(plano|velocidade|pacote|mega|giga)\b|"
    r"\b(quero|queria|gostaria|posso)\b[^.!?]{0,20}\b(outro|um)\s+plano\b", re.I)
# RECLAMAÇÃO de velocidade entregue (regra 19) — nunca tratar como oportunidade de venda
_RECLAMA_VELOCIDADE = re.compile(
    r"\b(teste\s+de\s+velocidade|speedtest|medi(r|ndo)|s[óo]\s+(d[áa]|chega|vem|t[áa]\s+dando|"
    r"pega)\s*\d+|n[ãa]o\s+(chega|d[áa]|entrega)\s*\d+|\d+\s*(mega|mb).{0,12}\bs[óo]\b|"
    r"pago\s+por\s+\d+|contratei\s+\d+)\b", re.I)

# TROCA DE NOME/SENHA DO WI-FI: a regra 5 diz que o Pedrão NÃO executa e NÃO ensina — registra e
# a equipe faz. Testado ao vivo: o modelo respondia "você precisa acessar o roteador direto, qual
# o modelo do aparelho?", mandando o cliente mexer na configuração sozinho.
_SENHA_WIFI = re.compile(
    r"\b(mudar|trocar|alterar|mud(a|ar)|nova|esqueci|resetar|configurar|ver|saber|qual)\b"
    r"[^.!?]{0,25}\b(senha|nome)\b[^.!?]{0,18}\b(wi-?fi|rede|roteador|internet)\b|"
    r"\b(senha|nome)\s+(d[oa]\s+)?(wi-?fi|rede)\b[^.!?]{0,25}\b(mudar|trocar|alterar|nova|esqueci)\b",
    re.I)

# PERGUNTA SOBRE HORÁRIO/EXPEDIENTE — o dado existe (schedule), não há motivo pra gastar IA
# nem pra devolver "me conta, é pra contratar?" a quem fez uma pergunta objetiva.
_PERGUNTA_HORARIO = re.compile(
    r"\b(que\s+horas?|qual\s+(o\s+)?hor[áa]rio|hor[áa]rio\s+de\s+(atendimento|funcionamento|voc[êe]s)|"
    r"(voc[êe]s|vcs|abre[mn]?|atendem?|funciona[mn]?|trabalha[mn]?)\s+"
    r"(no|aos|de|em|até|ate)?\s*(domingo|s[áa]bado|fim\s+de\s+semana|feriado|que\s+horas|"
    r"\d{1,2}\s*(h|horas))|"
    r"at[ée]\s+que\s+horas|abre[mn]?\s+que\s+horas|"
    r"(voc[êe]s|vcs)\s+(trabalham|atendem|abrem)\s*\?)", re.I)

# visita/instalação já agendada (regra 20): o Pedrão não tem a agenda e não chuta horário
_VISITA_AGENDADA = re.compile(
    r"\b(t[ée]cnico|instala(dor|[çc][ãa]o)|visita|equipe)\b[^.!?]{0,25}\b(chega|vem|passa|vai\s+"
    r"(vir|passar)|marcad|agendad|hoje|amanh[ãa])|"
    r"\b(chega|vem|passa)\b[^.!?]{0,20}\b(t[ée]cnico|instalador|equipe)\b|"
    r"\b(to|t[ôo]|estou)\s+esperando\s+(o\s+)?(t[ée]cnico|instala|visita)", re.I)

# pediu HUMANO -> atender na hora, sem insistir (regra 15)
_QUER_HUMANO = re.compile(
    r"\b(atendente|humano|pessoa\s+de\s+verdade|falar\s+com\s+(algu[ée]m|uma\s+pessoa|gente)|"
    r"n[ãa]o\s+quero\s+(falar\s+com\s+)?(rob[ôo]|bot|m[áa]quina)|quero\s+(um|uma)\s+(atendente|pessoa))\b", re.I)

def _ja_disse(historico, padrao, de="cliente", n=10):
    """Olha as últimas N mensagens do cliente atrás de um padrão. O atalho decidia lendo só a
    mensagem da vez -- por isso pedia reinício de quem já tinha reiniciado 3 mensagens antes."""
    alvo = ("cliente",) if de == "cliente" else ("pedrao", "bot", "atendente")
    for h in (historico or [])[-n:]:
        if h.get("de") in alvo and padrao.search(h.get("texto") or ""):
            return True
    return False

# dicas rápidas de internet (só enviadas se o cliente ACEITAR) — texto do dono, curto
_DICAS_TEXTO = (
    "Boa! 😊 No Wi-Fi, o *5G* geralmente é mais rápido, mas funciona melhor perto do roteador (perde força "
    "com paredes). Já o *2.4GHz* (2G) alcança mais longe, porém costuma ser mais lento e sofrer interferência.\n\n"
    "Mais dicas rapidinhas:\n"
    "• Deixe o roteador em local *alto e aberto* — nunca dentro do armário.\n"
    "• Longe de micro-ondas, espelhos, paredes grossas e muitos eletrônicos.\n"
    "• Pra TV, videogame e PC, *cabo de rede* é bem mais estável que o Wi-Fi.\n"
    "• Muitos aparelhos ligados ao mesmo tempo dividem o desempenho da rede.\n"
    "• Reiniciar de vez em quando ajuda — mas se o problema volta sempre, aí o suporte analisa.")
# muda de assunto no meio do roteiro -> deixa o LLM assumir (server encerra o roteiro).
# SEM \b no fim (senão "cancelar"/"cancelamento"/"planos" — as palavras MAIS comuns de desvio —
# não casavam, e o cliente ficava preso no pedido de nome+CPF do suporte).
_DESVIO_ASSUNTO = re.compile(
    r"\b(plano|pre[çc]o|valor|quanto\s+custa|cancel|fatura|boleto|atendente|humano|pessoa\s+de\s+verdade|falar\s+com\s+algu[ée]m)", re.I)

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
    r"\b(desbloque\w*|desbloqui\w*|em\s*confian[çc]a|na\s*confian[çc]a|me\s*(libera|libere|desbloqueia)|"
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

    # (2) confirmação pendente -> executa SÓ com "sim" E sem "não" (senão "não quero" liberava!)
    if desb == "confirma":
        if _NAO.search(msg):
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
                   f"Só pra você já saber: o *desbloqueio em confiança* pode ser feito *uma vez por mês* — "
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

def _suporte_passo(msg, sup, fatos, historico=None):
    """Roteiro de suporte (padrão dos exemplos do dono):
    sup=1 -> cliente mandou nome+CPF: busca o cadastro REAL no MyCore (endereço certo, nunca inventado)
             e conduz o reset do roteador. sup=2 -> lê a cor da luz: resolveu (fecha) ou não resolveu
             (resumo com os dados confirmados + encaminha com prioridade pra equipe técnica)."""
    if _DESVIO_ASSUNTO.search(msg):
        return None  # mudou de assunto -> LLM assume (server limpa o estado do roteiro)

    # (1) recebeu nome + CPF -> puxa nome/endereço REAIS do cadastro e manda o reset
    if sup == "1":
        import mycore as MC
        nome_real, end_real = "", ""
        cpf = MC.extrair_cpf_cnpj(msg)
        # regra 5: quem JÁ reiniciou por conta própria não pode ouvir "reinicia de novo".
        # Isto vinha DEPOIS do pedido de CPF -- então "já reiniciei 3 vezes" era ignorado e o
        # cliente recebia o pedido de CPF de novo, como se não tivesse dito nada (visto em
        # teste de conversa 25/07). Agora é a PRIMEIRA coisa checada.
        _ja_reset = (_JA_REINICIOU.search(msg) or fatos.get("sup_ja_reset")
                     or _ja_disse(historico, _JA_REINICIOU))
        if _ja_reset:
            return None
        if not cpf:
            # O cliente respondeu alguma coisa que não é CPF. Se ele PERGUNTOU ou reclamou
            # ("e aí? vai demorar?", "já faz 2 dias"), repetir o pedido de CPF palavra por
            # palavra é o pior atendimento possível -- e era exatamente o que acontecia, em
            # loop (regra 9). O atalho pede UMA vez; daí em diante quem conduz é o LLM, que
            # responde o que a pessoa falou e pede o dado sem soar robô.
            tries = int(fatos.get("sup_try") or 0)
            # "?" = o cliente PERGUNTOU algo; tries>=1 = já pedimos uma vez. Nos dois casos,
            # repetir seria robô. ("meu nome é João" não tem "?" e é a 1ª vez -> pede o CPF
            # que falta, que é o certo.)
            if tries >= 1 or "?" in msg:
                return None
            return _fp("Pra eu já achar seu cadastro e agilizar (sem te fazer repetir tudo depois), me confirma "
                       "só o seu *nome* e o *CPF* (pode ser só os números)? 🙏",
                       intencao="suporte", sup="1", dados={"sup_try": tries + 1})
        if cpf:
            try:
                d = MC.dados_cliente_por_cpf(cpf)
            except Exception:
                d = None
            if d:
                nome_real = d.get("nome") or ""
                end_real = d.get("endereco") or ""
        # NUNCA usar a mensagem crua como nome: sem cadastro achado, o texto do cliente virava
        # "nome" e saía no fechamento e na nota do time ("Nome: já reiniciei tudo e não funciona").
        dados = {"sup_end": end_real}
        if nome_real:
            dados["sup_nome"] = nome_real
        prim = nome_real.split(" ")[0].title() if nome_real else ""
        texto = (f"Obrigado{', ' + prim if prim else ''}! Vamos tentar restabelecer a conexão 🙌\n\n"
                 "Faz o seguinte: tira o *roteador* da tomada, conta *1 minutinho* e liga de novo — "
                 "depois espera as luzes estabilizarem.\n\n"
                 "Enquanto reinicia, quer que eu te passe umas *dicas rápidas* pra melhorar a internet no dia a dia? 😊\n\n"
                 "E me avisa qual a *cor da luz* que acendeu (verde, vermelha…) e se a internet voltou?")
        return _fp(texto, intencao="suporte", sup="2", dados=dados)

    # (2) leu a luz / resultado do reinício — ou respondeu sobre as dicas
    nome = (fatos.get("sup_nome") or "").strip()
    prim = nome.split(" ")[0].title() if nome else ""
    if _SUP_RESOLVIDO.search(msg) and not _SUP_NAO_RESOLVIDO.search(msg):
        if _SUP_RESSALVA.search(msg):
            return None   # "voltou MAS tá lenta" / "voltou e caiu de novo" -> não é resolvido:
                          # conversa de verdade (LLM). Queda intermitente é prioridade (regra 5).
        texto = (f"Que bom que voltou{', ' + prim if prim else ''}! 😊 Qualquer coisa me chama aqui. "
                 "Posso ajudar em mais alguma coisa?")
        return _fp(texto, intencao="suporte", sup="fim")
    if _NAO_SABE.search(msg):
        return None       # "não tô em casa" / "não consigo ver" -> parar de pedir a cor da luz
    if _LUZ_OUTRA.search(msg) and not _luz_vermelha_confirmada(msg):
        return None       # relatou OUTRO sinal (piscando/verde/apagada) -> o LLM registra com as
                          # palavras dele, sem cravar diagnóstico de fibra que ele não descreveu
    if _luz_vermelha_confirmada(msg):   # cliente DISSE vermelha/LOSS, sem negação -> roteiro da fibra
        end = (fatos.get("sup_end") or "").strip()
        dados_linha = (nome if nome else "(nome a confirmar)") + (f", {end}" if end else " — endereço a confirmar")
        quando = S.proximo_atendimento(setor="suporte")
        queixa = (fatos.get("sup_queixa") or "").strip()
        texto = (f"Obrigado por testar aí{', ' + prim if prim else ''} 🙏\n\n"
                 "Luz vermelha normalmente é um ajuste no sinal da *fibra* — é comum e tem solução, "
                 "mas quem resolve é a nossa *equipe técnica* em campo.\n\n"
                 f"Já deixei seu caso *registrado e priorizado* e a equipe fala com você {quando}, "
                 "por aqui mesmo. Você não precisa fazer mais nada.\n\n"
                 "Só confere se anotei certo:\n"
                 f"• Você: {dados_linha}\n"
                 + (f"• O que está acontecendo: {queixa}\n" if queixa else "")
                 + "• O aparelho está com a luz vermelha\n\n"
                 "Se tiver algo errado aí, me corrige que eu ajusto o registro 👍")
        nota = (f"[PEDRÃO fora do horário] SUPORTE PRIORITÁRIO | {dados_linha} | "
                + (f"Relato do cliente: \"{queixa}\" | " if queixa else "")
                + "Luz vermelha confirmada PELO CLIENTE (possível falha na fibra / LOSS) | "
                  "Testes: reiniciou o roteador e não resolveu | "
                  "Encaminhar equipe técnica pra agendar o reparo.")
        return _fp(texto, acao="transferir", intencao="suporte", fila=24, nota=nota, sup="fim",
                   dados={"nota_ok": 1}, icone="⚡➡️")  # já tem nota rica na transferência -> não repetir no vigia
    if _SUP_NAO_RESOLVIDO.search(msg):
        # "não mudou nada" / "continua" sem citar cor nenhuma: NÃO fechar aqui (inventaria a causa
        # técnica pro cliente e pra nota da equipe). Cai pro LLM — Sonnet (decidir() escala pelo
        # sup=="2") pra conversar de verdade, perguntar o que ela está vendo e/ou registrar sem
        # afirmar o que ela não disse.
        return None
    # ainda não falou da luz -> pode ter respondido sobre as DICAS (oferece uma vez só)
    if not fatos.get("sup_dicas"):
        if _SIM.search(msg) and not _NAO.search(msg):
            return _fp(_DICAS_TEXTO + "\n\nE aí, qual a *cor da luz* que acendeu e se a internet voltou?",
                       intencao="suporte", sup="2", dados={"sup_dicas": 1})
        if _NAO.search(msg):
            return _fp("Tranquilo! 😊 Então me avisa qual a *cor da luz* que acendeu e se a internet voltou?",
                       intencao="suporte", sup="2", dados={"sup_dicas": 1})
    return None  # resposta ambígua -> LLM decide

def fastpath(mensagem, sessao_nova, historico, fatos=None, sentimento=None, contato=None):
    """Decisão pronta SEM LLM pros casos previsíveis do prompt: saudação (sempre como atendente
    virtual), pedido claro de planos, e o roteiro de suporte básico passo a passo. Qualquer coisa
    fora do padrão exato retorna None -> cai no decidir() normal (LLM), sem arriscar qualidade."""
    fatos = fatos or {}
    msg = (mensagem or "").strip()
    if not msg:
        return None
    # cliente IRRITADO (ou querendo cancelar) nunca cai no atalho -> LLM trata com cuidado
    if sentimento and sentimento.get("humor") in ("irritado", "churn"):
        return None
    sup = "" if sessao_nova else str(fatos.get("sup") or "")

    # PEDIU HUMANO -> atende na hora, sem insistir nem repetir menu (regra 15)
    if _QUER_HUMANO.search(msg):
        return None

    # AVISO OPERACIONAL ATIVO (rompimento/queda em massa): o atalho não conhece o aviso do painel
    # -- sem isso, numa queda em massa dezenas de clientes recebem "tira da tomada 1 minuto"
    # enquanto o dono já sabe que é rompimento. Assunto técnico vai pro LLM, que recebe o aviso.
    try:
        _p = PAINEL.ler() if PAINEL else {}
        if _p.get("aviso_ativo") and (_p.get("aviso") or "").strip() \
                and (_SUP_INTENCAO.search(msg) or sup in ("1", "2")):
            return None
    except Exception:
        pass

    # 0) roteiro de suporte JÁ em andamento tem prioridade
    if sup in ("1", "2"):
        return _suporte_passo(msg, sup, fatos, historico)

    # 0.3) PERGUNTA DE HORÁRIO: a informação existe no código (schedule) e o bot respondia
    # "me conta, é pra contratar ou outro assunto?" — deixando sem resposta uma pergunta objetiva.
    # "que horas o TÉCNICO chega?" é visita agendada (regra 20), não pergunta de expediente
    if _PERGUNTA_HORARIO.search(msg) and not _VISITA_AGENDADA.search(msg):
        _abre0 = (_abertura() + "\n\n") if sessao_nova else ""
        return _fp(_abre0 + "Nosso *suporte técnico* atende de segunda a sexta das *9h às 20h* e "
                   "no *sábado das 9h às 15h*. O *comercial* e o *financeiro* são de segunda a "
                   "sexta, a partir das 9h.\n\n"
                   "Por aqui eu te ajudo a qualquer hora 😊 O que você precisa?",
                   intencao="horario", icone="🕐")

    # 0.4) SENHA/NOME DO WI-FI: regra 5 — o Pedrão não executa nem ensina a mexer no roteador.
    if _SENHA_WIFI.search(msg):
        _abre0 = (_abertura() + "\n\n") if sessao_nova else ""
        return _fp(_abre0 + "Consigo registrar isso pra você! 😊 A troca de *nome ou senha do "
                   "Wi-Fi* quem faz é a nossa equipe técnica — assim ninguém corre risco de "
                   "perder a conexão.\n\n"
                   f"Já deixo anotado e eles falam com você {S.proximo_atendimento(setor='suporte')}. "
                   "Me confirma o *CPF* do titular?",
                   intencao="suporte", icone="🔑",
                   nota="[Pedrão] TROCA DE NOME/SENHA DO WI-FI — cliente pediu; equipe técnica "
                        "executa. NÃO foi passada nenhuma instrução de acesso ao roteador.")

    # 0.5) MUDANÇA DE ENDEREÇO e UPGRADE DE PLANO: dois casos em que o modelo insistia em
    # PROMETER o que não pode (que a internet "vai junto" pro endereço novo) ou em tratar cliente
    # de anos como lead novo (pedir rua/número "pra ver viabilidade"). Resposta fixa aqui, sem IA.
    # ...mas SÓ quando ele quer MUDAR de plano. "Contratei 700 e o teste dá 180" também casa
    # _JA_CLIENTE e é RECLAMAÇÃO de velocidade (regra 19) -- responder "vou registrar sua
    # mudança de plano" ali seria vender pra quem está reclamando. Esse vai pro LLM.
    if (_QUER_UPGRADE.search(msg) and not _RECLAMA_VELOCIDADE.search(msg)
            and not _SUP_INTENCAO.search(msg)):
        _abre0 = (_abertura() + "\n\n") if sessao_nova else ""
        return _fp(_abre0 + "Perfeito! Vou registrar seu pedido de *mudança de plano* e o time "
                   "Comercial te passa a condição certinha e faz a troca 😊\n\n"
                   "Me confirma o *CPF* do titular, por gentileza?",
                   intencao="venda", icone="⬆️",
                   nota="[Pedrão] UPGRADE/TROCA DE PLANO — cliente ATUAL pedindo mudança. "
                        "Comercial retorna com valor e data. (Não mandei tabela de planos nem "
                        "pedi endereço: ele já é atendido.)")

    # ...mas quem fala de "casa nova" PERGUNTANDO PREÇO é lead novo querendo contratar, não
    # cliente mudando de endereço -- esse vai pro fluxo de planos/LLM, não pra cá.
    if ((_MUDANCA_END.search(msg) or _LEVAR_INTERNET.search(msg))
            and not _FINANCEIRO_KW.search(msg) and not _PLANOS_INTENCAO.search(msg)):
        _abre0 = (_abertura() + "\n\n") if sessao_nova else ""
        return _fp(_abre0 + "Posso registrar sim! 😊 Quem confirma se a gente já atende o endereço "
                   "novo — e combina a data da mudança com você — é a nossa equipe.\n\n"
                   "Me passa o *endereço novo* (rua, número e bairro)?",
                   intencao="mudanca_endereco", icone="📦",
                   nota="[Pedrão] MUDANÇA DE ENDEREÇO — cliente quer levar o serviço pra outro "
                        "endereço. Confirmar viabilidade no endereço novo e agendar. NÃO foi "
                        "prometido nada sobre cobertura nem custo.")
    # 1) saudação pura -> abertura fixa "Olá!", sem anunciar conversa anterior (mesmo se reaberta)
    if _SAUDACAO_PURA.match(msg) and not _SINAIS_COMPLEXOS.search(msg):
        if sessao_nova:  # 1º contato OU reaberto: mesma saudação simples, sem relembrar o histórico
            return _fp(f"{_abertura()} Me conta o que você precisa.", intencao="saudacao")
        return None  # SESSÃO=CONTINUA: "oi" solto no meio da conversa -> LLM

    # 2) pedido de planos/internet -> FLUXO PRINCIPAL: já conhece os planos? + qual o local (viabilidade)
    #    (empresa/PJ sai pro LLM: planos e ficha empresariais são diferentes)
    # _JA_CLIENTE: quem fala do PRÓPRIO plano (upgrade, velocidade entregue) NÃO é lead novo --
    # mandar tabela de planos + pedir endereço pra "viabilidade" pra cliente de meses é ofensivo.
    # _FINANCEIRO_KW: "quero o valor dos planos E me manda minha fatura" tem DOIS pedidos -- o
    # atalho respondia só o primeiro e ignorava metade da mensagem (regra 4). Vai pro LLM, que
    # atende os dois.
    if (_PLANOS_INTENCAO.search(msg) and not _SINAIS_COMPLEXOS.search(msg)
            and not _EMPRESA.search(msg) and not _JA_CLIENTE.search(msg)
            and not _FINANCEIRO_KW.search(msg)
            and len(msg.split()) <= 18):
        if sessao_nova:
            texto = (f"{_abertura()} Você já conhece nossos planos? E me diz uma coisa: "
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
    # entra no fluxo se pediu financeiro AGORA, se está aguardando o CPF E a msg tem dígitos,
    # OU se já foi identificado pelo CPF seco (cpf_ok) e confirmou que quer a fatura.
    _tem_digitos = len(re.sub(r"\D", "", msg)) >= 8
    # _FIN_RECLAMACAO: "já paguei e cortaram", cobrança indevida, negativação, pedido de desconto
    # ou acordo NÃO é pedido de 2ª via -- entregar boleto em aberto nesses casos gera fúria e
    # Procon. Regra 6: registrar e encaminhar ao Financeiro humano (o LLM conduz).
    # DOIS PEDIDOS na mesma mensagem ("quero o valor dos planos E me manda minha fatura"):
    # a regra 4 manda atender os DOIS. O atalho responderia só um e ignoraria metade -- some
    # daqui e o LLM conduz. (Só quando há conjunção; "fatura do plano 700" segue no atalho.)
    _dois_pedidos = bool(_PLANOS_INTENCAO.search(msg) and _FINANCEIRO_KW.search(msg)
                         and re.search(r"\b(e|e\s+tamb[ée]m|tamb[ée]m|junto|al[ée]m\s+disso)\b", msg, re.I))
    if ((_FINANCEIRO_KW.search(msg) and not _FIN_RECLAMACAO.search(msg)
            and not _DOC_NAO_FATURA.search(msg) and not _dois_pedidos)
            or (fin_state == "aguarda_cpf" and _tem_digitos)
            or (fin_state == "cpf_ok" and _SIM.search(msg) and not _NAO.search(msg))
            or (fin_state == "escolhe" and re.fullmatch(r"\s*\d{1,2}\s*", msg or ""))):
        import mycore as MC
        cpf = MC.extrair_cpf_cnpj(msg) or (str(fatos.get("fin_cpf") or "") or None if fin_state == "cpf_ok" else None)
        _abre = (_abertura() + "\n\n") if sessao_nova else ""
        # limpa o estado do financeiro. fin="feito" (não "" — o merge_fatos ignora vazios) tira do
        # modo "aguarda_cpf"; nota_ok=1 evita virar "lead" no vigia dos 20min.
        _limpa_fin = {"fin": "feito", "fin_try": 0, "nota_ok": 1}
        # multi-endereço: cliente escolheu o número da lista? recupera o CPF e o cadastro escolhido
        client_id = None
        if fin_state == "escolhe":
            m_esc = re.fullmatch(r"\s*(\d{1,2})\s*", msg or "")
            try:
                _ops = json.loads(str(fatos.get("fin_ids") or "[]"))
            except Exception:
                _ops = []
            if m_esc and _ops and 1 <= int(m_esc.group(1)) <= len(_ops):
                cpf = str(fatos.get("fin_cpf") or "") or cpf
                client_id = _ops[int(m_esc.group(1)) - 1].get("id")
        if cpf and MC.token_configurado():
            # CPF/CNPJ com MAIS DE UM cadastro (2 casas, Airbnb com várias locações, filiais):
            # lista os endereços numerados e pergunta qual é ANTES de entregar a fatura.
            if client_id is None:
                try:
                    _cads = MC.cadastros_por_cpf(cpf)
                except Exception:
                    _cads = []
                if len(_cads) >= 2:
                    _ops2 = [{"id": c.get("id"), "end": (c.get("endereco") or c.get("nome") or "")} for c in _cads[:9]]
                    _linhas = "\n".join(f"*{i+1})* {o['end'] or 'Cadastro'}" for i, o in enumerate(_ops2))
                    return _fp(_abre + "Encontrei *mais de um cadastro* no seu CPF/CNPJ 😊 Pra eu enviar a "
                               "fatura certa, me diz qual é o endereço:\n\n" + _linhas +
                               "\n\nResponda só com o *número*.",
                               intencao="financeiro", icone="🏠",
                               dados={"fin": "escolhe", "fin_cpf": cpf,
                                      "fin_ids": json.dumps(_ops2, ensure_ascii=False)})
            try:
                res = MC.resolver_fatura(cpf, contato, client_id=client_id)   # CPF-only
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
        txt = ("Esse número não parece certo — confere e me manda de novo o *CPF ou CNPJ*, só os números? 😊"
               if _tem_digitos else
               "Claro! Pra já puxar a sua fatura aqui, me manda o seu *CPF ou CNPJ* (pode ser só os números) 😊")
        return _fp(_abre + txt, intencao="financeiro", dados={"fin": "aguarda_cpf", "fin_try": tries + 1},
                   icone="⚡")

    # 2.7) CPF/CNPJ "SECO" (mensagem é praticamente só o documento, sem contexto) — ordem do dono
    #      23/07: é pra IDENTIFICAR a pessoa no sistema, NUNCA mandar planos. Acha o cadastro,
    #      chama pelo nome se for pessoa física (com prudência) e pergunta o que ela precisa.
    import mycore as MC2
    _doc = MC2.extrair_cpf_cnpj(msg)
    _sobra = len(re.sub(r"[\d.\-/\s]", "", msg))  # o que sobra tirando números e pontuação de doc
    if _doc and _sobra <= 4 and MC2.token_configurado():
        try:
            d_cli = MC2.dados_cliente_por_cpf(_doc)
        except Exception:
            d_cli = None
        _abre2 = (_ABERTURA + "\n\n") if sessao_nova else ""
        if d_cli and (d_cli.get("nome") or "").strip():
            nome_cad = d_cli["nome"].strip()
            # PJ (CNPJ ou nome comercial) NUNCA é tratado como pessoa; PF usa o 1º nome com respeito
            _eh_pj = len(_doc) == 14 or re.search(
                r"\b(ltda|mei?|eireli|epp|s\.?a\.?|com[ée]rcio|servi[çc]os|mercado|padaria|"
                r"distribuidora|transportes|construtora|igreja|condom[íi]nio|bar|loja)\b", nome_cad, re.I)
            prim = "" if _eh_pj else nome_cad.split(" ")[0].title()
            saud_nome = f", {prim}" if (prim and len(prim) >= 3) else ""
            txt = (f"Achei seu cadastro aqui{saud_nome}! 😊\n\n"
                   "Você quer baixar a sua *fatura* para pagamento, ou é outro assunto?")
            return _fp(_abre2 + txt, intencao="financeiro", icone="🪪",
                       dados={"fin": "cpf_ok", "fin_cpf": _doc, "nome": ("" if _eh_pj else nome_cad)})
        return _fp(_abre2 + "Não localizei um cadastro com esse CPF. Confere os números pra mim, "
                   "por gentileza? Ou me conta o que você precisa que eu te ajudo 😊",
                   intencao="financeiro", icone="🪪")

    # 3) início de suporte (só o básico; financeiro tem prioridade e sai pro LLM)
    if _SUP_INTENCAO.search(msg) and not _FINANCEIRO_KW.search(msg):
        abre = (_abertura() + " ") if sessao_nova else ""
        # "sem internet" só quando é queda TOTAL de verdade; "fraca/lenta/oscilando" é queixa de
        # qualidade -- dizer "sinto muito que esteja SEM internet" pra quem só falou de sinal fraco
        # soa como se o Pedrão não tivesse lido a mensagem (achado 24/07).
        queixa = ("esteja sem internet" if _SUP_TOTAL.search(msg) else "a internet esteja ruim")
        texto = (abre + f"Sinto muito que {queixa} 😕 Vou te ajudar a resolver o quanto antes. "
                 "Pra eu achar seu cadastro e agilizar, me passa por favor o seu *nome completo* "
                 "e o *CPF (ou CNPJ)* cadastrado na conta?")
        return _fp(texto, intencao="suporte", sup="1")

    return None

def _parse_json(txt):
    """Lê o JSON da resposta do modelo. TOLERANTE a truncamento (incidente 24/07 22:16: a
    resposta bateu no teto de tokens, o JSON veio cortado no meio, o parser estrito devolveu
    None e o cliente levou uma transferência automática com balão de erro).
    Ordem: (1) JSON puro; (2) fecha chaves/aspas que ficaram abertas; (3) resgata os campos
    essenciais por regex. Só devolve None quando NADA dá pra aproveitar."""
    if not txt:
        return None
    i = txt.find("{")
    if i < 0:
        return None
    j = txt.rfind("}")
    if j > i:
        try:
            return json.loads(txt[i:j + 1])
        except Exception:
            pass
    bruto = txt[i:]
    # (2) tentativa de reparo: fecha string aberta e as chaves/colchetes que faltam
    s = bruto
    if s.count('"') % 2:
        s += '"'
    s += "]" * max(0, s.count("[") - s.count("]"))
    s += "}" * max(0, s.count("{") - s.count("}"))
    try:
        return json.loads(s)
    except Exception:
        pass
    # (3) resgate por regex: o que importa de verdade é a AÇÃO e o TEXTO pro cliente
    def _campo(nome):
        m = re.search(r'"%s"\s*:\s*"((?:[^"\\]|\\.)*)"' % nome, bruto)
        if not m:
            return ""
        try:
            return json.loads('"' + m.group(1) + '"')
        except Exception:
            return m.group(1)
    texto = _campo("texto")
    if not texto:
        return None
    d = {"acao": _campo("acao") or "responder", "texto": texto,
         "intencao": _campo("intencao") or "ambiguo",
         "viabilidade": _campo("viabilidade") or "naoaplicavel",
         "nota_interna": _campo("nota_interna"), "_json_reparado": True}
    m = re.search(r'"fila"\s*:\s*(\d+)', bruto)
    if m:
        d["fila"] = int(m.group(1))
    m = re.search(r'"fastReplyId"\s*:\s*(\d+)', bruto)
    if m:
        d["fastReplyId"] = int(m.group(1))
    return d

def _gerar_resiliente(system, user, model=None):
    """Uma falha de rede/instabilidade da API NÃO pode virar transferência automática na cara do
    cliente (era o que acontecia: qualquer exceção -> _fallback -> ticket transferido). Tenta de
    novo UMA vez, rápido; se o modelo 'esperto' falhar, a 2ª tentativa cai no rápido (Haiku),
    que responde melhor do que não responder. Erros de credencial/limite não são retentados."""
    try:
        return L.gerar(system, user, model) if model else L.gerar(system, user)
    except L.LLMError as e:
        msg = str(e)
        if any(s in msg for s in ("401", "403", "invalid_api_key", "ANTHROPIC_API_KEY ausente",
                                  "credit", "billing")):
            raise                       # problema de conta: retentar não resolve
        try:
            import memory as _M
            _M.log_evento("sistema", "llm_retry", {"erro": msg[:180], "modelo": model or C.LLM_MODEL})
        except Exception:
            pass
        time.sleep(0.4)
        return L.gerar(system, user)    # 2ª tentativa sempre no modelo rápido


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
    # QUE HORAS SÃO. O modelo não tem relógio: ele escrevia "Boa tarde!" à meia-noite e
    # "Bom dia!" às 22h (visto no teste). Também é o que permite ele falar o dia certo em que a
    # equipe volta sem depender de conta de cabeça.
    try:
        _ag = S._agora()
        _per = S.periodo_do_dia(_ag)
        # entre 0h e 5h não existe cumprimento de período: o modelo escreveu "Opa, madrugada!"
        # quando recebeu a palavra crua. Na madrugada ele só não cumprimenta por horário.
        _cump = (f"cumprimente com \"{_per}\" (e nunca outro)" if _per else
                 "é MADRUGADA: não use \"bom dia/boa tarde/boa noite\" — comece direto, com \"Olá!\"")
        ctx.append(f"[AGORA: {S._DIAS[_ag.weekday()]}, {_ag.strftime('%d/%m/%Y %H:%M')} — "
                   f"{_cump}. "
                   f"A equipe de SUPORTE volta {S.proximo_atendimento(_ag, 'suporte')}; "
                   f"COMERCIAL e FINANCEIRO voltam {S.proximo_atendimento(_ag, 'comercial')}. "
                   "Use exatamente esses prazos — não invente outro nem diga só 'próximo dia útil'.]")
    except Exception:
        pass
    # DOIS PEDIDOS na mesma mensagem: tirar do atalho não bastou -- o modelo também respondia
    # só o primeiro. A regra 4 vira aviso explícito, com os dois assuntos nomeados.
    if _PLANOS_INTENCAO.search(mensagem) and _FINANCEIRO_KW.search(mensagem):
        ctx.append("[ATENÇÃO — DOIS PEDIDOS NA MESMA MENSAGEM: o cliente falou de PLANOS/VALORES "
                   "e de FATURA/BOLETO. A regra 4 manda atender OS DOIS, nunca metade. Resolva "
                   "primeiro o que você faz sozinho (a fatura, pedindo o CPF) e trate o outro "
                   "assunto na mesma resposta.]")
    ctx.append(V.hint_para_prompt(viab))
    # REINCIDÊNCIA: o cliente que já trouxe o mesmo problema semana passada não pode ser tratado
    # como chamado novo -- é a coisa mais humana que existe ("vi que você já falou disso") e a
    # que mais muda a percepção de quem está do outro lado.
    try:
        import memory as _M
        _rec = _M.ocorrencias(memoria_cliente, tipo="suporte", dias=7)
        if len(_rec) >= 2:
            ctx.append(f"[REINCIDÊNCIA — este cliente já trouxe problema técnico {len(_rec)}x nos "
                       "últimos 7 dias. RECONHEÇA isso com naturalidade ('vi aqui que você já tinha "
                       "falado com a gente sobre isso'), é PROIBIDO pedir reinício de novo, e marque "
                       "a nota interna como REINCIDENTE — a equipe precisa tratar como caso crônico, "
                       "não como chamado novo.]")
    except Exception:
        pass
    _tom = SENT.hint_tom(sentimento)
    if _tom:
        ctx.append(_tom)
    if PAINEL:
        extra = PAINEL.contexto_extra()
        if extra:
            ctx.append(extra)
    # SAÍDA ENXUTA (25/07): cada token gerado é tempo de espera do cliente. O modelo escrevia
    # nota_interna (50-120 tokens) em TODA resposta e o server APAGA ela em qualquer ação que não
    # seja transferir (server.py) -- era ~1s por mensagem gerado pra ser descartado. Idem motivo/
    # confianca, que os guards sobrescrevem.
    # Medido em produção: o tempo de resposta é praticamente linear no número de tokens que o
    # modelo escreve (~60 tok/s). 119 tokens = 1,9s; 347 tokens = 5,1s. Ou seja, cada frase a
    # mais é espera direta do cliente -- e no WhatsApp a mensagem curta ainda é melhor de ler.
    ctx.append("\nResponda SÓ o JSON, no formato definido, e o mais CURTO possível:\n"
               "• sempre: acao, texto\n"
               "• texto: no MÁXIMO ~400 caracteres (2-4 linhas). Frase a mais = cliente esperando.\n"
               "• só quando fizer sentido: intencao, fila, fastReplyId, dados_coletados\n"
               "• nota_interna: SOMENTE quando acao=\"transferir\" (nos outros casos é descartada)\n"
               "• NÃO escreva: motivo, confianca, viabilidade, emocao, temperatura — o sistema "
               "calcula tudo isso sozinho, e o que você escrever nesses campos é jogado fora.\n"
               "• dados_coletados: só as chaves que você REALMENTE descobriu. Campo vazio "
               "(\"nome\": \"\") é descartado — não escreva.")
    user = "\n\n".join(ctx)
    # REGRAS BASE entram no SYSTEM (estável entre chamadas -> aproveitam o prompt caching da
    # Anthropic: mais rápido e ~10x mais barato que ir no ctx). Os ajustes do dono ficam no ctx
    # (variáveis) e entram DEPOIS — em conflito, o que o dono escreveu tem prioridade.
    system = (SYSTEM_PROMPT + "\n\n" + REG.bloco()
              + "\n\n## CONTEXTO DE PLANOS (para conversar; preço só pela imagem)\n" + PLANOS_CTX)

    # ESCALADA DE MODELO (ordem do dono 23/07): casos complexos vão pro Sonnet 5 (pensa melhor);
    # o resto fica no Haiku (mais rápido/barato). Complexo = cliente irritado, empresa/PJ,
    # conversa longa, mensagem grande (negociação/multiassunto), OU roteiro de suporte que já
    # reiniciou e não resolveu (achado 24/07: cliente frustrada nesse ponto raramente xinga ou
    # grita — o detector de humor por palavra-chave não pega —, mas é exatamente o momento que
    # precisa de mais conversa de verdade em vez de fechar sozinho com dado inventado).
    _complexo = ((sentimento or {}).get("humor") == "irritado" or _EMPRESA.search(texto_todo)
                 or len(historico) >= 10 or len(mensagem) > 280
                 or str((memoria_cliente or {}).get("sup")) == "2")
    _model = getattr(C, "LLM_MODEL_SMART", None) if _complexo else None

    try:
        raw = _gerar_resiliente(system, user, _model)
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
    if texto and _COND_COMERCIAL.search(texto):
        # taxa de instalação, parcelamento, fidelidade, "é grátis": nada disso está definido
        # aqui — quem informa é o Comercial. Remove só a frase que inventou.
        alertas.append("GUARD: condicao comercial inventada removida")
        novo = _remove_sentencas(texto, _COND_COMERCIAL)
        texto = novo if len(novo) >= 15 else (
            "Sobre valores e condições de instalação, quem passa certinho é o nosso time "
            "Comercial 😊 Me diz a rua, número e bairro que eu já registro seu contato.")
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
        texto = ("Perfeito, pra empresa a gente tem soluções próprias 😊 Só pra eu te indicar o melhor caminho: "
                 "a internet é pra *uso comum da empresa* (escritório, Wi-Fi da equipe, sistemas) ou vocês usam "
                 "*câmeras, alarme, servidor ou algum sistema que precise de IP fixo*? "
                 "Aí nosso time Comercial já te passa as condições certinhas.")
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
    if texto and viab["status"] != V.CONFIRMADA_PREDIO and _afirma_cobertura(texto):
        alertas.append("GUARD: afirmacao de cobertura suavizada")
        novo = _remove_sentencas(texto, _COBERTURA_ASSERT, protege=_COB_CONDICIONAL)
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
    # HORÁRIO HUMANO: fallback fica MUDO (nem nota, nem transferência) — se algo escapou dos gates
    # com a equipe presente, o pior a fazer é transferir ticket vazio e sujar a tela do time
    # (incidente 24/07: balões "Falha no envio" + notas de "JSON inválido" no meio do expediente).
    if not S.deve_atuar():
        return {"acao": "aguardar", "fila": 0, "texto": "", "intencao": "ambiguo",
                "viabilidade": "naoaplicavel", "motivo": motivo, "nota_interna": "",
                "_alertas": [motivo + " (horário humano: silêncio)"], "_viabilidade_sistema": viab,
                "_raw": (raw or "")[:200], "_render": f"🤫 (fallback silencioso, horário humano) — {motivo}"}
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
