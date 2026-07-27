# -*- coding: utf-8 -*-
"""Servidor webhook do Ultra Pedrão (FastAPI).
Fluxo: FlowSeller -> POST /webhook -> filtros -> dedup -> debounce -> brain -> flowseller(shadow/live).
Modo sombra (BOT_MODE=shadow): decide e REGISTRA o que faria, sem enviar."""
import os, time, hashlib, json, asyncio, re, threading
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse

import config as C
import memory as M
import schedule as S
import brain as B
import llm as L
import flowseller as FS
import painel as PAINEL
import sentimento as SENT
from debounce import Debouncer

app = FastAPI(title="Ultra Pedrão", version="0.1.0")
M.init()

# Servir as imagens do /planos pela própria VPS (tudo num lugar só, busca rápida)
import os as _os
from fastapi.staticfiles import StaticFiles
_PLANOS_DIR = _os.path.join(_os.path.dirname(__file__), "..", "data", "planos")
_os.makedirs(_PLANOS_DIR, exist_ok=True)
app.mount("/planos", StaticFiles(directory=_PLANOS_DIR), name="planos")

_SEEN = {}  # idempotência: hash do evento -> ts (dedup de webhook repetido)
# 24/07: TTL caiu 600->120s e a chave ganhou o ticket_id. Os BOTÕES do menu geram sempre o mesmo
# texto ("Ola", "FINANCEIRO") — com 10min de janela por contato+texto, o 2º teste/clique em
# conversa nova era engolido SEM LOG (o dono viu o copiloto "mudo"). O dedup existe só pra
# reentrega do MESMO webhook, que acontece em segundos.
_SEEN_TTL = 120
_START_TS = time.time()

# ---- NOTA INTERNA DO LEAD (ordem do dono 14/07/2026) ----
# A nota NÃO sai na hora: sai ~20 min depois do início da conversa, e sai MESMO se o cliente sumiu
# (a equipe não pode perder o resumo do lead). Exceção: transferência mantém a nota na hora, senão
# o humano recebe o ticket sem contexto nenhum.
NOTA_APOS_S = 15 * 60   # dono: nota interna do lead ~10-15 min depois
_VIGIA_INTERVALO_S = 120

def _fmt_tel(contato):
    d = re.sub(r"\D", "", str(contato or ""))
    if d.startswith("55") and len(d) > 11:
        d = d[2:]
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return d or str(contato or "")

def _texto_nota_lead(contato, fatos):
    """Resumo do lead pro time — DESCREVE TUDO (telefone, nome, o que quer, dados coletados)."""
    linhas = ["[Pedrão · resumo do lead]"]
    linhas.append("📱 Telefone: " + _fmt_tel(contato))
    nome = (fatos.get("nome") or fatos.get("sup_nome") or "").strip()
    if nome:
        linhas.append("👤 Nome: " + nome)
    resumo = (M.get_resumo(contato) or "").strip()
    if resumo:
        linhas.append("📝 Conversa: " + resumo)
    rotulos = {"endereco": "Endereço", "sup_end": "Endereço (cadastro)", "rua": "Rua", "numero": "Número",
               "bairro": "Bairro", "plano_interesse": "Plano de interesse", "plano": "Plano",
               "cpf": "CPF", "cnpj": "CNPJ"}
    dados = [f"• {rot}: {fatos.get(k)}" for k, rot in rotulos.items() if str(fatos.get(k) or "").strip()]
    if dados:
        linhas.append("📋 Dados coletados:"); linhas += dados
    if len(linhas) <= 2:   # só header + telefone
        linhas.append("Cliente conversou com o Pedrão; ainda sem dados estruturados coletados.")
    return "\n".join(linhas)

async def _vigia_notas():
    """Posta a nota interna do lead ~15 min após o início da conversa, mesmo sem mensagem nova.
    Posta UMA VEZ só: marca nota_ok logo após a tentativa (a FlowSeller cria a nota mas às vezes
    não devolve id, então NÃO dá pra confiar no 'enviado' — sem isso, ficava repetindo a cada 2 min)."""
    while True:
        try:
            # a varredura dos fatos é disco + json.loads de cada linha: em thread, pra não
            # congelar o event loop (e com ele todos os webhooks) a cada tick.
            _pend = await asyncio.to_thread(M.contatos_nota_pendente, NOTA_APOS_S)
            for contato, fatos in _pend:
                ext = M.ultimo_external_key(contato)
                if not ext:
                    continue
                M.merge_fatos(contato, {"nota_ok": 1})   # ANTES de postar: garante 1x só (nunca spam)
                texto = _texto_nota_lead(contato, fatos)
                if "ainda sem dados" in texto:   # conversa vazia (só "oi") -> não incomoda o time
                    continue
                # to_thread: a chamada de rede NÃO pode bloquear o event loop (senão trava o webhook)
                r = await asyncio.to_thread(FS.nota_interna, ext, texto, number=contato, delay=False)
                M.log_evento(contato, "nota_lead", {"mask": _mask(contato), "enviado": bool(r.get("enviado"))})
        except Exception as e:
            print("[vigia_notas] erro:", e, flush=True)
        await asyncio.sleep(_VIGIA_INTERVALO_S)

FOLLOWUP_MIN_S = int(os.environ.get("FOLLOWUP_MIN_S", "600"))    # 10 min (ordem do dono 25/07)
FOLLOWUP_MAX_S = int(os.environ.get("FOLLOWUP_MAX_S", "14400"))  # até 4h depois; passou disso, esquece

async def _vigia_followup():
    """REGRA DO DONO (25/07): perguntei o endereço pra ver viabilidade e o cliente não respondeu?
    Depois de 10 min mando UMA pergunta simples pra não deixar o lead morrer. Roda sozinho —
    não depende de mensagem nova chegar (o lead calado é justamente quem não manda mais nada)."""
    await asyncio.sleep(60)
    while True:
        try:
            alvos = await asyncio.to_thread(_followup_alvos, FOLLOWUP_MIN_S, FOLLOWUP_MAX_S)
            for a in alvos:
                ext = M.ultimo_external_key(a["contato"]) or a["contato"]
                M.merge_fatos(a["contato"], {"followup_ts": time.time()})   # ANTES: 1x só
                await asyncio.to_thread(FS.responder_texto, ext, FOLLOWUP_TXT,
                                        number=a["contato"], assinar=False, delay=False)
                M.log_evento(a["contato"], "followup_lead",
                             {"mask": _mask(a["contato"]), "min": a["min"], "auto": True})
            # 3 min sem responder "quer ver os planos?" -> manda os planos assim mesmo
            for a in await asyncio.to_thread(_planos_pendentes):
                ext = M.ultimo_external_key(a["contato"]) or a["contato"]
                M.merge_fatos(a["contato"], {"planos_ts": time.time()})   # ANTES: 1x só
                await asyncio.to_thread(
                    FS.executar_decisao, ext,
                    {"acao": "fastreply", "fastReplyId": 1296, "fila": 0,
                     "texto": "Separei os planos pra você dar uma olhada 👇",
                     "nota_interna": ""}, a["contato"])
                M.log_evento(a["contato"], "planos_followup",
                             {"mask": _mask(a["contato"]), "min": a["min"]})
        except Exception as e:
            print("[vigia_followup] erro:", e, flush=True)
        await asyncio.sleep(120)

@app.on_event("startup")
async def _ligar_vigia():
    asyncio.create_task(_vigia_notas())
    asyncio.create_task(_vigia_followup())

# SENTINELA ANTI-DUPLO-BOT (incidente 15-16/07/2026: canal trocado pro chatbot NATIVO da
# FlowSeller e o Pedrao continuou respondendo -> DOIS bots na mesma conversa). Os menus do
# nativo chegam aqui pelo webhook como mensagem do NOSSO numero (fromMe). Ao reconhecer um,
# o Pedrao se PAUSA sozinho por 10 min (renovado a cada menu). Assim a troca do canal na
# FlowSeller vira o UNICO interruptor -- sem precisar lembrar do painel.
_MENU_NATIVO = re.compile(
    r"(\b[123]\s*-\s*(FALAR COM ATENDENTE|PLANOS\s*/?\s*COMERCIAL|FINANCEIRO)\b|"
    r"Escolha uma (op[çc][ãa]o|das op[çc][õo]es)|"
    r"N[ãa]o entendi sua resposta\.?\s*Vamos tentar novamente)", re.I)

# ==================== COPILOTO FINANCEIRO (ordem do dono 24/07/2026) ====================
# Durante o HORÁRIO HUMANO, quem clica "FINANCEIRO" no menu cai na fila 25 e esperava atendente
# até pra pegar 2ª via. O copiloto entrega a fatura (Pix+boleto) na fila, assinado
# "*Financeiro WebFiber*" (sem se apresentar como robô). Regras: atendente ACEITAR não o para
# (aceitam e demoram); atendente DIGITAR qualquer coisa -> silencia naquele ticket na hora.
FILA_FINANCEIRO = C.FILAS.get("financeiro", 25)
_COP_KW = re.compile(r"(financeiro|fatura|boleto|pix|2\s*[ªº°]?\s*via|segunda\s+via|pagamento|"
                     r"c[óo]digo\s+de\s+barras|linha\s+digit|vencimento|pagar)", re.I)
# clique do botão FINANCEIRO (entrada na fila) -> saudação de SETOR, como um humano faria
_BTN_FIN = re.compile(r"^\s*(3\s*-\s*)?financeiro\s*$", re.I)
# botões que já dizem O QUE a pessoa quer -> vai direto pro CPF
_BTN_FATURA = re.compile(r"^\s*(baixar\s+boleto|2\s*[ªº°]?\s*via(\s+da\s+fatura)?|"
                         r"segunda\s+via(\s+da\s+fatura)?|pix)\s*$", re.I)

_BOT_TXT = {}  # contato -> [(ts, texto enviado por nós)] — p/ distinguir humano de bot no fromMe

# O QUE O BOT LEMBRA DE UMA CONVERSA PRA OUTRA. Só identidade/ficha do cliente — nunca estado de
# roteiro (sup/fin/desb/try), que TEM de zerar em atendimento novo. Assim o bot não pergunta de
# novo o CPF que a pessoa deu ontem, mas também não continua um roteiro velho no meio.
# FICHA = quem a pessoa É (sobrevive à sessão nova). "plano_interesse" SAIU daqui em 25/07: é
# estado de funil, não identidade — sobrevivendo, o bot abria conversa nova com "vi que você tem
# interesse em planos — é para a Rua X?" (interesse VELHO, de outra conversa; regra 23: nunca
# afirme o que o cliente não disse NESTA conversa).
_FICHA_KEYS = ("nome", "cpf", "cnpj", "fin_cpf", "endereco", "sup_end", "sup_nome", "bairro",
               "rua", "numero", "complemento", "cpf_fornecido", "plano", "hist_oc",
               "desbloqueio_mes")

def _registra_txt(contato, texto):
    t = (texto or "").strip()
    if not t:
        return
    agora = time.time()
    l = _BOT_TXT.setdefault(contato, [])
    l.append((agora, t))
    del l[:-20]
    # o dicionário nunca soltava contato nenhum: crescia o dia inteiro e _txt_do_bot itera nele.
    # As entradas só valem 1h (janela do próprio _txt_do_bot), então some com o que já venceu.
    if len(_BOT_TXT) > 500:
        for k in [k for k, v in _BOT_TXT.items() if not v or agora - v[-1][0] > 3600]:
            _BOT_TXT.pop(k, None)

def _txt_do_bot(contato, texto) -> bool:
    """True se a mensagem fromMe foi gerada por BOT (nosso ou fluxo nativo) — não por um humano.
    24/07: lista ampliada — o submenu do fluxo ('Selecione uma opção:'), as respostas enlatadas
    (link da área do cliente) e a nossa própria saudação eram classificados como HUMANO e mutavam
    o copiloto injustamente (visto ao vivo: cascata de humano_digitou_silenciei)."""
    t = (texto or "").strip()
    if not t:
        return True
    # 25/07 (ao vivo, ticket 780431): a saudação do copiloto saiu 08:51:56 e 2s depois o ECO dela
    # voltou pelo webhook e foi classificado como HUMANO -> mutou o próprio atendimento; o clique
    # FINANCEIRO seguinte morreu no silêncio. Causa: o eco volta SEM os asteriscos da assinatura
    # ("Financeiro WebFiber" em vez de "*Financeiro WebFiber*"), então nem o startswith nem o cache
    # de texto enviado casavam. Agora a comparação ignora a formatação (* _ ~ `) em vez de exigi-la.
    _t = re.sub(r"[*_~`]", "", t).strip()
    if _t.startswith("Pedrão") or _t.startswith("Financeiro WebFiber"):
        return True
    # a apresentação do Pedrão pode vir com prefixo variável ("Bom dia! Eu sou o Pedrão...") —
    # 25/07 09:36: a reentrega dela foi lida como HUMANO e mutou o próprio ticket
    if re.search(r"eu sou o pedr[ãa]o|agente virtual da webfiber|atendente virtual da webfiber",
                 _t[:160], re.I):
        return True
    # saudação de setor do copiloto (sai sem assinatura em alguns caminhos)
    if re.match(r"^ol[áa]!?\s+aqui\s+[ée]\s+do\s+setor", _t, re.I):
        return True
    if t.startswith("Olá! Eu sou o Pedrão"):   # nossa saudação sai SEM assinatura
        return True
    # NOTAS INTERNAS nossas ecoam pelo webhook como fromMe ("[Copiloto Financeiro] ...",
    # "[Pedrão] ...") — 24/07 14:39: a nota do multi-cadastro foi classificada como HUMANO e
    # mutou o ticket 1s depois da lista; o "3" do cliente ficou sem resposta.
    if t.startswith("["):
        return True
    # menus/fluxo de botão (nativo/submenus): "1 - ...", "Escolha...", "Selecione...", boas-vindas
    if re.search(r"^\s*\d\s*-\s*\S", t, re.M) or re.search(r"escolha|selecione|bem[- ]vindo", t, re.I):
        return True
    # respostas enlatadas do fluxo (link da área do cliente / textos oficiais de fatura)
    if "areadocliente" in t.lower() or "Para baixar a sua Fatura" in t:
        return True
    # pedaços da entrega de fatura sem assinatura (Pix copia-e-cola EMV, linha digitável, avisos)
    if re.match(r"^000201", t) or re.match(r"^[\d\s.]{40,}$", t):
        return True
    if ("Linha digitável" in t or "Pra pagar na hora" in t or "Achei sua fatura" in t
            or "Ou pague pelo boleto" in t or t.startswith("⏱️")):
        return True
    now = time.time()
    for ts, txt in _BOT_TXT.get(contato, []):
        _x = re.sub(r"[*_~`]", "", txt or "").strip()
        if now - ts < 3600 and (_x == _t or (_x and _t.startswith(_x[:60]))):
            return True
    return False

def _norm_txt(s):
    import unicodedata
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()

def _cop_entregar(ev, res):
    """Entrega a régua completa da fatura assinada *Financeiro WebFiber* (sem cara de robô)."""
    contato, ext = ev["contato"], ev["external_key"]
    # 24/07: o copiloto tinha a régua DUPLICADA aqui (delay=False em todas, resultado do envio
    # descartado). Agora usa a MESMA porta do caminho noturno -- mesmo payload, mesma cadência,
    # mesma checagem de entrega. Só muda a assinatura (*Financeiro WebFiber*).
    r = FS.executar_decisao(
        ext,
        {"acao": "faturas", "_envios": res["envios"],
         "nota_interna": "[Copiloto Financeiro] Fatura entregue automaticamente (Pix + boleto) "
                         "pelo CPF/CNPJ informado no chat."},
        contato, marca=FS.ASSIN_FINANCEIRO)
    for e in res["envios"]:
        _registra_txt(contato, e.get("text", ""))
    # antes da unificação o resultado era DESCARTADO: uma fatura que falhava no envio era logada
    # como "entregue" e ninguém via. Agora só é falha quando há erro REAL da API (shadow/piloto
    # devolvem "faria" sem erro e não contam como falha).
    seq = r.get("sequencia") or [r]
    erros = [x.get("erro") for x in seq if isinstance(x, dict) and x.get("erro")]
    M.log_evento(contato, "copiloto", {"mask": _mask(contato),
                                       "acao": "fatura_FALHOU" if erros else "fatura_entregue",
                                       "erros": erros[:3], "envio": r})
    return {"status": "copiloto_fatura_falhou" if erros else "copiloto_fatura_entregue"}

COP_MUTE_JANELA_S = 3600   # atendente digitou -> Pedrão morre nessa conversa por 1h

def _cop_mudo(ev, fatos=None):
    """A atendente humana assumiu esta conversa? Então o Pedrão NÃO fala. Duas travas:
    (1) por TICKET — exata, quando a FlowSeller manda o ticket_id;
    (2) por CONTATO + TEMPO — rede de segurança pra quando o ticket não vem no payload
        (sem ela, um webhook sem ticket_id passava direto por cima da atendente).
    Ordem do dono 25/07: a trava tem que ser FORTE."""
    f = fatos if fatos is not None else M.get_fatos(ev["contato"])
    if str(f.get("cop_mute_ticket") or "") == str(ev.get("ticket_id") or "\x00"):
        return True
    # 25/07 09:45 (ao vivo): a janela por TEMPO valia SEMPRE — um mute falso às 09:36 calou o
    # copiloto por 1h até pra TICKETS NOVOS, e o clique FINANCEIRO caía no Pedrão. A regra do
    # dono é por CONVERSA ("a atendente digitou -> morre NAQUELA conversa"); a janela de tempo
    # é só a rede de segurança pra webhook SEM ticket_id (o propósito original dela). Evento com
    # ticket_id diferente do mutado = conversa nova = copiloto fala.
    if ev.get("ticket_id") is not None:
        return False
    try:
        return (time.time() - float(f.get("cop_mute_ts") or 0)) < COP_MUTE_JANELA_S
    except Exception:
        return False

def _cop_ja_fez(fatos, ev, key_tid, key_ts, janela_s):
    """Anti-repetição do copiloto POR CONVERSA (24/07: a janela por tempo silenciava o cliente
    que abria um ticket NOVO em menos de 30min — visto no teste do dono às 14:18). Regra:
    mesmo ticket -> não repete; ticket NOVO -> pode de novo; sem ticket_id -> janela de tempo."""
    tid = ev.get("ticket_id")
    if tid is not None:
        return str(fatos.get(key_tid) or "") == str(tid)
    try:
        return time.time() - float(fatos.get(key_ts) or 0) < janela_s
    except Exception:
        return False

def _cop_marca(contato, ev, key_tid, key_ts):
    d = {key_ts: time.time()}
    if ev.get("ticket_id") is not None:
        d[key_tid] = str(ev.get("ticket_id"))
    M.merge_fatos(contato, d)

def _copiloto(ev):
    """Atende a fila do Financeiro em modo 'invisível': só fatura, e só até um humano digitar."""
    import mycore as MC
    import respostas as R
    FS.marcar_inicio()   # mesmo orçamento de naturalidade do caminho normal
    contato, ext = ev["contato"], ev["external_key"]
    texto = str(ev["texto"])
    fatos = M.get_fatos(contato)
    # 2ª checagem da trava, JÁ DENTRO do copiloto: entre o gate do webhook e este ponto pode ter
    # chegado uma mensagem da atendente (ela digita enquanto o bot processa). Aqui os fatos são
    # relidos do banco, então pega o que acabou de ser marcado.
    if _cop_mudo(ev, fatos):
        M.log_evento(contato, "copiloto", {"mask": _mask(contato), "acao": "mudo_humano_assumiu"})
        return {"status": "copiloto_mudo_humano"}

    # (0) ESCOLHA DE ENDEREÇO pendente (CPF/CNPJ com mais de um cadastro — ex.: Airbnb com
    #     várias locações): aceita o NÚMERO ("1", "2"...) ou o nome da rua escrito.
    ids_raw = str(fatos.get("cop_ids") or "")
    if ids_raw and ids_raw not in ("-", "0"):
        try:
            opcoes = json.loads(ids_raw)
        except Exception:
            opcoes = []
        escolhido = None
        m = re.fullmatch(r"\s*(\d{1,2})\s*\)?\.?\s*", texto)
        if m and opcoes and 1 <= int(m.group(1)) <= len(opcoes):
            escolhido = opcoes[int(m.group(1)) - 1]
        elif opcoes:  # tentou escrever o endereço: casa por trecho (rua/bairro) com >=4 letras
            tn = _norm_txt(texto)
            cands = [o for o in opcoes if any(len(w) >= 4 and w in tn for w in _norm_txt(o.get("end")).split())]
            if len(cands) == 1:
                escolhido = cands[0]
        if escolhido:
            try:
                res = MC.resolver_fatura(str(fatos.get("cop_cpf") or ""), contato, client_id=escolhido.get("id"))
            except Exception:
                res = {"status": "fallback", "motivo": "excecao"}
            M.merge_fatos(contato, {"cop_ids": "-"})
            if res.get("status") == "entregue":
                return _cop_entregar(ev, res)
            if res.get("status") == "sem_fatura":
                t = "Boa notícia! 😊 Esse cadastro está com tudo em dia — nenhuma fatura em aberto."
                FS.responder_texto(ext, t, number=contato, delay=False, marca=FS.ASSIN_FINANCEIRO,
                                   nota="[Copiloto Financeiro] Cadastro escolhido sem fatura em aberto.")
                _registra_txt(contato, t)
                return {"status": "copiloto_sem_fatura"}
            t = ("Não consegui puxar a fatura desse cadastro agora 😕 Já avisei nossa equipe do "
                 "Financeiro — eles te enviam por aqui mesmo.")
            FS.responder_texto(ext, t, number=contato, delay=False, marca=FS.ASSIN_FINANCEIRO,
                               nota="[Copiloto Financeiro] ⚠️ Falha ao buscar a fatura do cadastro escolhido "
                                    "— ENVIAR MANUALMENTE pro cliente.")
            _registra_txt(contato, t)
            return {"status": "copiloto_fallback"}
        # não entendeu a escolha: re-pergunta UMA vez; na 2ª falha, silencia e deixa pro humano
        if int(fatos.get("cop_esc_try") or 0) >= 1:
            M.merge_fatos(contato, {"cop_ids": "-"})
            M.log_evento(contato, "copiloto", {"mask": _mask(contato), "acao": "escolha_nao_entendida_silencio"})
            return {"status": "copiloto_silencio"}
        linhas = "\n".join(f"*{i+1})* {o.get('end') or o.get('nome') or 'Cadastro'}" for i, o in enumerate(opcoes))
        t = "Só me confirma respondendo com o *número* da opção, por gentileza 😊\n\n" + linhas
        FS.responder_texto(ext, t, number=contato, delay=False, marca=FS.ASSIN_FINANCEIRO)
        _registra_txt(contato, t)
        M.merge_fatos(contato, {"cop_esc_try": 1})
        return {"status": "copiloto_reperguntou_escolha"}

    cpf = MC.extrair_cpf_cnpj(texto)
    if cpf and MC.token_configurado():
        # CPF/CNPJ com MAIS DE UM cadastro? -> lista os endereços numerados e pergunta qual é
        try:
            cadastros = MC.cadastros_por_cpf(cpf)
        except Exception:
            cadastros = []
        if len(cadastros) >= 2:
            ops = [{"id": c.get("id"), "end": (c.get("endereco") or c.get("nome") or "")} for c in cadastros[:9]]
            linhas = "\n".join(f"*{i+1})* {o['end'] or 'Cadastro'}" for i, o in enumerate(ops))
            t = ("Encontrei *mais de um cadastro* no seu CPF/CNPJ 😊 Pra eu enviar a fatura certa, "
                 "me diz qual é o endereço:\n\n" + linhas + "\n\nResponda só com o *número*.")
            FS.responder_texto(ext, t, number=contato, delay=False, marca=FS.ASSIN_FINANCEIRO,
                               nota="[Copiloto Financeiro] CPF/CNPJ com múltiplos cadastros; pedi pra escolher o endereço.")
            _registra_txt(contato, t)
            M.merge_fatos(contato, {"cop_cpf": cpf, "cop_ids": json.dumps(ops, ensure_ascii=False), "cop_esc_try": "0"})
            M.log_evento(contato, "copiloto", {"mask": _mask(contato), "acao": "multi_cadastro_perguntou", "n": len(cadastros)})
            return {"status": "copiloto_escolha_endereco"}
        try:
            res = MC.resolver_fatura(cpf, contato)
        except Exception:
            res = {"status": "fallback", "motivo": "excecao"}
        if res.get("status") == "entregue":
            return _cop_entregar(ev, res)
        if res.get("status") == "sem_fatura":
            t = ("Boa notícia! 😊 Não encontrei nenhuma fatura em aberto no seu CPF — está tudo em dia. "
                 "Precisando de mais alguma coisa do Financeiro, é só falar por aqui.")
            FS.responder_texto(ext, t, number=contato, delay=False, marca=FS.ASSIN_FINANCEIRO,
                               nota="[Copiloto Financeiro] CPF consultado: sem fatura em aberto.")
            _registra_txt(contato, t)
            M.log_evento(contato, "copiloto", {"mask": _mask(contato), "acao": "sem_fatura"})
            return {"status": "copiloto_sem_fatura"}
        # não achou o CPF / MyCore fora: SEM link de área do cliente (ordem do dono 24/07 — nada
        # de "cara de robô"). Pede pra conferir 1x; na 2ª falha, silencia e o humano assume.
        if int(fatos.get("cop_fail") or 0) >= 1:
            M.log_evento(contato, "copiloto", {"mask": _mask(contato), "acao": "cpf_falhou_2x_silencio"})
            return {"status": "copiloto_silencio"}
        t = ("Não localizei o cadastro com esse número 😊 Pode conferir os dígitos do "
             "*CPF ou CNPJ* e me enviar de novo, por gentileza?")
        FS.responder_texto(ext, t, number=contato, delay=False, marca=FS.ASSIN_FINANCEIRO,
                           nota="[Copiloto Financeiro] CPF/CNPJ não localizado; pedi pra conferir.")
        _registra_txt(contato, t)
        M.merge_fatos(contato, {"cop_fail": 1})
        M.log_evento(contato, "copiloto", {"mask": _mask(contato), "acao": "cpf_nao_achado"})
        return {"status": "copiloto_cpf_nao_achado"}
    # clique do botão FINANCEIRO (entrou na fila) -> saudação de SETOR, natural, como um humano
    if _BTN_FIN.match(texto):
        if _cop_ja_fez(fatos, ev, "cop_greet_tid", "cop_greet_ts", 1800):
            return {"status": "copiloto_ja_saudou"}
        t = "Olá! Aqui é do setor *Financeiro* da WebFiber 😊 Em que posso te ajudar?"
        FS.responder_texto(ext, t, number=contato, delay=False, marca=FS.ASSIN_FINANCEIRO)
        _registra_txt(contato, t)
        _cop_marca(contato, ev, "cop_greet_tid", "cop_greet_ts")
        M.log_evento(contato, "copiloto", {"mask": _mask(contato), "acao": "saudacao_setor"})
        return {"status": "copiloto_saudacao_setor"}
    if _BTN_FATURA.match(texto) or _COP_KW.search(texto):
        # pediu fatura/pix/2ª via (botão ou escrito) -> pede o documento. 1x por conversa.
        if _cop_ja_fez(fatos, ev, "cop_ask_tid", "cop_ask_ts", 600):
            return {"status": "copiloto_ja_perguntou"}
        t = ("Claro! Me envia abaixo os números do seu *CPF ou CNPJ* que eu já te mando a "
             "fatura com o *Pix* e o *boleto* 😊")
        FS.responder_texto(ext, t, number=contato, delay=False, marca=FS.ASSIN_FINANCEIRO)
        _registra_txt(contato, t)
        _cop_marca(contato, ev, "cop_ask_tid", "cop_ask_ts")
        M.log_evento(contato, "copiloto", {"mask": _mask(contato), "acao": "pediu_cpf"})
        return {"status": "copiloto_pediu_cpf"}
    # PRIMEIRA fala na fila ainda sem intenção clara ("Ola", "oi, tudo bem?") -> saudação de
    # setor 1x POR CONVERSA (24/07: o clique FINANCEIRO chega ANTES da fila ser marcada, então
    # a saudação não disparava e o cliente ficava no vácuo até dizer "boleto").
    if not _cop_ja_fez(fatos, ev, "cop_greet_tid", "cop_greet_ts", 1800):
        t = "Olá! Aqui é do setor *Financeiro* da WebFiber 😊 Em que posso te ajudar?"
        FS.responder_texto(ext, t, number=contato, delay=False, marca=FS.ASSIN_FINANCEIRO)
        _registra_txt(contato, t)
        _cop_marca(contato, ev, "cop_greet_tid", "cop_greet_ts")
        M.log_evento(contato, "copiloto", {"mask": _mask(contato), "acao": "saudacao_setor"})
        return {"status": "copiloto_saudacao_setor"}
    # ASSUNTO QUE O PEDRÃO NÃO RESOLVE (negociação, prazo, contestação, dúvida) — ordem do dono
    # 25/07: antes era SILÊNCIO ABSOLUTO, e o cliente ficava no vácuo esperando alguém aparecer.
    # Agora ele SEGURA a pessoa com naturalidade ("aguarde um instante enquanto verifico") e
    # deixa uma NOTA INTERNA dizendo ao atendente o que a pessoa quer e como continuar.
    # NUNCA diz que vai transferir nem que é um robô — o cliente acha que é o Financeiro mesmo.
    return _cop_segurar(ev, fatos)

# frases de espera — variam pra não parecer resposta automática se a pessoa escrever 2x
_ESPERAS = (
    "{trat}, só um instante que eu vou verificar isso aqui pra você 😊",
    "{trat}, me dá um minutinho que eu já confiro essa informação pra você.",
    "{trat}, um momento por favor — estou verificando isso aqui.",
)

def _cop_tratamento(contato, fatos, ev):
    """'Sra. Juliana' / 'Sr. Carlos' quando dá pra saber; senão, algo neutro e educado."""
    nome = (fatos.get("nome") or fatos.get("sup_nome") or ev.get("nome") or "").strip()
    prim = nome.split(" ")[0].strip().title() if nome else ""
    if not prim or len(prim) < 3 or not prim.isalpha():
        return "Perfeito"
    return prim

def _cop_segurar(ev, fatos):
    """Segura o cliente com naturalidade + nota interna pro humano assumir. Instantâneo."""
    contato, ext = ev["contato"], ev["external_key"]
    texto = str(ev.get("texto") or "").strip()
    # só uma vez por conversa: se ele escrever de novo, não repete (o humano já foi avisado)
    if _cop_ja_fez(fatos, ev, "cop_hold_tid", "cop_hold_ts", 900):
        M.log_evento(contato, "copiloto", {"mask": _mask(contato), "acao": "ja_segurou_silencio"})
        return {"status": "copiloto_ja_segurou"}
    _t0 = time.time()
    trat = _cop_tratamento(contato, fatos, ev)
    idx = int(time.time()) % len(_ESPERAS)
    t = _ESPERAS[idx].format(trat=trat)
    nota = ("🟡 *ATENDIMENTO PARA CONTINUAR — o cliente está aguardando*\n"
            f"O que ele pediu: \"{texto[:180]}\"\n"
            "Isto está FORA do que o assistente do Financeiro resolve sozinho (ele só envia "
            "Pix/boleto/2ª via pelo CPF). Já respondi pedindo pra aguardar um instante — "
            "é só continuar a conversa normalmente daqui.")
    FS.responder_texto(ext, t, number=contato, delay=False, marca=FS.ASSIN_FINANCEIRO, nota=nota)
    _registra_txt(contato, t)
    _cop_marca(contato, ev, "cop_hold_tid", "cop_hold_ts")
    # quanto tempo o atendente levou pra ver a nota, medido de verdade (o dono perguntou "em
    # quantos segundos?" — agora tem número em cada atendimento, não estimativa)
    M.log_evento(contato, "copiloto", {"mask": _mask(contato), "acao": "segurou_p_humano",
                                       "pedido": texto[:120],
                                       "ms_ate_nota": int((time.time() - _t0) * 1000)})
    return {"status": "copiloto_segurou_para_humano"}

def _dedup(key: str) -> bool:
    now = time.time()
    for k, ts in list(_SEEN.items()):
        if now - ts > _SEEN_TTL: _SEEN.pop(k, None)
    if key in _SEEN: return True
    _SEEN[key] = now
    return False

# dedup pelo ID ÚNICO da mensagem (anti-reentrega). Janela LONGA de propósito: a reentrega
# provada em 25/07 veio 29 MINUTOS depois — o dedup textual (TTL 120s) nunca a pegaria.
_SEEN_ID = {}
_SEEN_ID_TTL = 6 * 3600
IGNORA_MSG_ANTIGA_S = int(os.environ.get("IGNORA_MSG_ANTIGA_S", "600"))

def _dedup_id(msg_id: str) -> bool:
    now = time.time()
    if len(_SEEN_ID) > 5000:
        for k, ts in list(_SEEN_ID.items()):
            if now - ts > _SEEN_ID_TTL: _SEEN_ID.pop(k, None)
    if msg_id in _SEEN_ID:
        _SEEN_ID[msg_id] = now
        return True
    _SEEN_ID[msg_id] = now
    return False

def _mask(tel: str) -> str:
    tel = str(tel or "")
    return (tel[:4] + "***" + tel[-2:]) if len(tel) > 6 else "***"

# ---- extração defensiva do payload (formato exato do webhook = a confirmar no 1º real) ----
def _ts_epoch(v):
    """Timestamp do webhook -> epoch em SEGUNDOS. A FlowSeller manda ora epoch (s ou ms), ora
    ISO-8601 UTC ("2026-07-25T11:46:27.925Z"). O filtro de mensagem antiga fazia float(ts) e,
    com ISO, estourava -> caía no except -> NUNCA filtrou. Sem parse possível, assume agora."""
    if v in (None, ""):
        return time.time()
    try:
        f = float(v)
        return f / 1000.0 if f > 1e12 else f
    except (TypeError, ValueError):
        pass
    try:
        from datetime import datetime
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
    except Exception:
        return time.time()

def _parse_evento(p: dict):
    """Normaliza campos comuns de webhooks estilo Whaticket/FlowSeller. Tolerante a variações."""
    def g(*ks, default=None):
        for k in ks:
            cur = p
            ok = True
            for part in k.split("."):
                if isinstance(cur, dict) and part in cur: cur = cur[part]
                else: ok = False; break
            if ok and cur not in (None, ""): return cur
        return default
    # A FlowSeller embrulha o evento em "message", com o ticket aninhado (message.ticket.contact...).
    numero = str(g("message.ticket.contact.number", "ticket.contact.number", "message.contact.number",
                   "contact.number", "number", "from", default=""))
    ticket_id = g("message.ticketId", "message.ticket.id", "ticket.id", "ticketId")
    contact_id = g("message.contactId", "message.ticket.contactId", "ticket.contactId", "contactId")
    return {
        # externalKey costuma vir null -> endereçamos pelo número (fallback), guardando ids p/ o envio
        "external_key": g("message.externalKey", "message.ticket.externalKey", "externalKey", "ticket.externalKey") or numero,
        "ticket_id": ticket_id,
        "contact_id": contact_id,
        "contato": numero,
        "nome": g("message.ticket.contact.name", "ticket.contact.name", "message.contact.name",
                  "contact.name", "pushName", default=""),
        "texto": g("message.body", "body", "message.caption", "text", "message.text",
                   "interactive.button_reply.title", default=""),
        "from_me": bool(g("message.fromMe", "fromMe", default=False)),
        "is_group": bool(g("message.ticket.isGroup", "message.isGroup", "ticket.isGroup", "isGroup", default=False)),
        "tipo": g("message.mediaType", "event", "type", "mediaType", "message.type", default="chat"),
        "media_url": g("message.mediaUrl", "mediaUrl", default=None),
        # ID ÚNICO da mensagem na FlowSeller (UUID). É a chave anti-REENTREGA: quando um ticket
        # novo nasce, a FlowSeller REENTREGA mensagens antigas do contato com ticket_id NOVO —
        # o dedup por contato+ticket+texto via chave nova e deixava passar (25/07 09:36, provado:
        # o cérebro respondeu "Ola bom diaaaaa" de 29 MINUTOS antes e o Pedrão se apresentou em
        # cima do copiloto). Reentrega vem com o MESMO id -> dedup pega, ticket novo ou não.
        "msg_id": g("message.id", "message.messageId", "messageId", "id", default=None),
        "ts": _ts_epoch(g("message.timestamp", "message.msgCreatedAt", "timestamp", "ts", default=None)),
        # sinais de que um HUMANO/departamento já assumiu (pra o bot NÃO atropelar o atendimento):
        "status": str(g("message.ticket.status", "ticket.status", "status", default="")).lower(),
        "user_id": g("message.ticket.userId", "ticket.userId", "message.userId", "userId", default=None),
        "queue_id": g("message.ticket.queueId", "ticket.queueId", "message.queueId", "queueId", default=None),
        "_raw": p,
    }

_RESUMO_LOCK = threading.Lock()
_RESUMO_EM_CURSO = set()

_RESUMO_PASSO = 6   # depois do 1º resumo, só refaz a cada N mensagens novas

def _resumir_worker(contato):
    try:
        hist = M.historico(contato, n=C.MEM_RESUMO_APOS + 4)
        if len(hist) < C.MEM_RESUMO_APOS:
            return
        # Antes refazia o resumo a CADA mensagem depois da 16ª -- uma chamada de IA por mensagem,
        # pra sempre, numa conversa longa (e essa é a única que não usa cache: paga preço cheio).
        # O resumo não muda a cada frase; refazer a cada 6 mensagens novas dá o mesmo resultado
        # prático por ~1/6 do custo.
        f = M.get_fatos(contato)
        n_ant = int(f.get("resumo_n") or 0)
        if n_ant and len(hist) - n_ant < _RESUMO_PASSO:
            return
        M.set_resumo(contato, B.resumir(hist, M.get_resumo(contato)))
        M.merge_fatos(contato, {"resumo_n": len(hist)})
    except Exception:
        pass
    finally:
        with _RESUMO_LOCK:
            _RESUMO_EM_CURSO.discard(contato)

def _agendar_resumo(contato):
    """Atualiza o resumo da conversa FORA do caminho crítico (o cliente já recebeu a resposta).
    Um por contato de cada vez -- em rajada, não dispara N chamadas de LLM em paralelo."""
    with _RESUMO_LOCK:
        if contato in _RESUMO_EM_CURSO:
            return
        _RESUMO_EM_CURSO.add(contato)
    t = threading.Thread(target=_resumir_worker, args=(contato,), daemon=True)
    t.start()

def _ms(t0):
    return int((time.time() - float(t0 or 0)) * 1000) if t0 else None

def _processar(contato, texto, ctx):
    """Chamado pelo debouncer após agrupar as mensagens do contato."""
    _t_ini = time.time()
    _t_cerebro = _t_envio = None
    FS.marcar_inicio(_t_ini)   # orçamento de naturalidade: o "tempo de digitação" desconta o que
                               # o raciocínio já consumiu, em vez de somar espera por cima
    ext = ctx.get("external_key")
    # SENTINELA — 2ª checagem (pós-debounce), fecha a CORRIDA DO 1º BALÃO: na 1ª mensagem de uma
    # conversa nova, o menu nativo e o Pedrão reagem À MESMA mensagem ao mesmo tempo; no instante
    # do webhook o menu ainda não tinha saído, então a 1ª checagem não pegava. Aqui já passaram os
    # ~2s do agrupamento -> o menu nativo já chegou (fromMe) e marcou o painel -> o Pedrão desiste.
    if PAINEL.bot_nativo_ativo():
        M.log_evento(contato, "pausado_bot_nativo_pos_debounce", {"mask": _mask(contato)})
        return
    # sessão nova/reaberta: a FlowSeller cria um ticket_id novo quando o atendimento anterior
    # foi fechado. Comparamos com o último ticket_id visto pra esse contato -- se mudou (ou é o
    # primeiro contato), sinalizamos pro cérebro cumprimentar do jeito clássico.
    ticket_id_atual = ctx.get("ticket_id")
    ticket_id_anterior = M.get_ultimo_ticket(contato)
    sessao_nova = ticket_id_atual is not None and str(ticket_id_atual) != str(ticket_id_anterior)
    if ticket_id_atual is not None:
        M.set_ultimo_ticket(contato, ticket_id_atual)

    fatos = M.get_fatos(contato)
    # marca o INÍCIO da conversa (o vigia usa isso pra postar a nota do lead 20 min depois)
    if sessao_nova or not fatos.get("lead_ts"):
        _ini = time.time()
        M.merge_fatos(contato, {"lead_ts": _ini, "nota_ok": 0})
        fatos["lead_ts"] = _ini; fatos["nota_ok"] = 0
    hist = M.historico(contato)
    resumo = M.get_resumo(contato)  # memória nível 2 (agora É usada na decisão)
    # humor do cliente (código, sem LLM): adapta o tom, tira o irritado do atalho, e pinta o painel
    _ctx_txt = " ".join(h.get("texto", "") for h in hist[-4:])
    sent = SENT.classificar(texto, _ctx_txt)
    # sessão nova zera qualquer roteiro de suporte pendente (não arrasta estado velho pra conversa nova)
    if sessao_nova and fatos.get("sup") in ("1", "2"):
        M.merge_fatos(contato, {"sup": "fim"}); fatos["sup"] = "fim"
    # ORDEM DO DONO: conversa FECHADA pelo atendente -> a FlowSeller abre um TICKET NOVO
    # (sessao_nova=True) -> o Pedrão começa DO ZERO, SEM a memória da conversa anterior (não
    # recapitula). Se NÃO foi fechada (mesmo ticket), continua com todo o contexto. EXCEÇÃO: se o
    # cliente citar algo dito antes ("você não viu aqui em cima", "já te falei"), aí lê o histórico.
    _fresh = sessao_nova and not B.refere_anterior(texto)
    hist_b = [] if _fresh else hist
    resumo_b = "" if _fresh else resumo
    # A ordem do dono é NÃO RECAPITULAR em voz alta -- não é ficar com amnésia. Antes, a sessão
    # nova zerava TODA a ficha: o bot pedia de novo o nome, o CPF e o endereço que já tinha de
    # ontem. Agora a FICHA (quem é a pessoa) sobrevive; o ESTADO DO ROTEIRO (sup/fin/desb) zera.
    # 25/07 (ao vivo com o dono): o filtro abaixo só valia pra 1ª MENSAGEM da sessão — da 2ª em
    # diante `fatos` voltava INTEIRO do banco, com o roteiro da conversa fechada ("fin": "feito",
    # "sup": "fim", perfil de lead antigo...). Resultado real: o LLM viu "fin: feito" + CPF e
    # CRAVOU "seu CPF não tem fatura pendente" sem consultar nada. Sessão nova agora APAGA do
    # banco o que não é ficha (cop_* fica: é do copiloto, que tem ciclo próprio por ticket).
    if _fresh:
        _lixo = [k for k in fatos if k not in _FICHA_KEYS and not k.startswith("cop_")]
        if _lixo:
            M.remover_fatos(contato, _lixo)
            fatos = {k: v for k, v in fatos.items() if k not in _lixo}
    fatos_b = {k: v for k, v in fatos.items() if k in _FICHA_KEYS} if _fresh else fatos
    _t_cerebro = time.time()
    d = B.fastpath(texto, sessao_nova, hist_b, fatos_b, sentimento=sent, contato=contato)
    if d is None:
        d = B.decidir(texto, historico=hist_b, memoria_cliente=fatos_b, sessao_nova=sessao_nova, resumo=resumo_b, sentimento=sent)
        # se havia roteiro de suporte em andamento e o LLM assumiu, encerra o roteiro (evita ficar preso)
        if fatos.get("sup") in ("1", "2"):
            d.setdefault("dados_coletados", {})["sup"] = "fim"
    _dur_cerebro = int((time.time() - _t_cerebro) * 1000)
    _dur_antes = int((_t_cerebro - _t_ini) * 1000)   # leituras de memória antes de decidir

    # ANTI-DUPLICATA DE PLANOS: se ja mandou o pacote de planos+imagens ha < 3 min, NAO repete
    # (o cliente mandava o endereco em 2 msgs e recebia os planos 2x). So referencia o que ja foi enviado.
    _eh_planos = d.get("acao") == "fastreply" and d.get("fastReplyId") in (1296, 1437, 1438)
    _ult_planos = fatos_b.get("planos_ts")   # fresco na sessão nova (não arrasta do fechado)
    if _eh_planos and _ult_planos and (time.time() - float(_ult_planos)) < 180:
        # ⛔ 25/07 (4 conversas reais): esta frase de cooldown virou LOOP. O cliente respondia
        # "850 mega", "o segundo", "quero o de 1 giga" — que é EXATAMENTE a resposta pedida — e
        # levava a MESMA pergunta de volta, 3x seguidas. O cooldown só pode falar quando o cliente
        # ainda NÃO escolheu; se ele já escolheu (ou perguntou outra coisa), quem responde é o
        # cérebro. Frase fixa repetida é o jeito mais rápido de perder um lead quente.
        # "850MG", "700 mb", "1 giga", "o segundo", "esse" — o jeito real como o cliente escolhe
        _JA_ESCOLHEU = re.compile(
            r"(\d{3,4}\s*(mega|megas|mb|mg|m)\b|\bgigas?\b|\b1\s*g\b|o\s+(primeiro|segundo|"
            r"terceiro|[úu]ltimo)\b|\besse\b|\beste\b|quero\s+o\b|fico\s+com\b|vou\s+(querer|de)\b)", re.I)
        if _JA_ESCOLHEU.search(texto or "") or "?" in (texto or ""):
            pass          # deixa a decisão do cérebro passar — ele responde de verdade
        else:
            d = {"acao": "responder", "fastReplyId": 0, "fila": 0, "intencao": "planos",
                 "texto": "Os planos são esses que te mandei aqui em cima 👆 Qual deles fez mais sentido pra você?",
                 "viabilidade": "naoaplicavel", "motivo": "", "nota_interna": "", "dados_coletados": {},
                 "_alertas": ["cooldown planos (nao repetiu imagens)"], "_fastpath": True,
                 "_viabilidade_sistema": d.get("_viabilidade_sistema", {}), "_render": "💬 (cooldown) planos ja enviados"}
    elif _eh_planos:
        d.setdefault("dados_coletados", {})["planos_ts"] = time.time()

    # ⛔ PROMETEU OS PLANOS -> MANDA OS PLANOS (caso Marcia, 25/07 15:23): o bot escreveu "deixa
    # eu já te mostrar os nossos planos" e NÃO mandou nada. Se o texto promete mostrar/enviar
    # plano e a ação não é o pacote de planos, a promessa vira envio de verdade.
    _PROMETEU_PLANOS = re.compile(
        r"(vou\s+(te\s+)?(mostrar|mandar|enviar|passar)|deixa\s+eu\s+(j[áa]\s+)?te\s+mostrar|"
        r"j[áa]\s+(te\s+)?(mostro|mando|envio)|olha\s+s[óo]\s+(os\s+)?planos|"
        r"aqui\s+(est[ãa]o|v[ãa]o)\s+(os\s+)?(nossos\s+)?planos)[^.!?\n]{0,30}\bplano", re.I)
    if (d.get("acao") in ("responder", "transferir") and d.get("fastReplyId", 0) == 0
            and _PROMETEU_PLANOS.search(d.get("texto") or "")
            and not (fatos_b.get("planos_ts") and (time.time() - float(fatos_b["planos_ts"])) < 180)):
        M.log_evento(contato, "promessa_planos_cumprida", {"mask": _mask(contato)})
        d = dict(d, acao="fastreply", fastReplyId=1296, fila=0)
        d.setdefault("dados_coletados", {})["planos_ts"] = time.time()

    # ⛔ ANTI-REPETIÇÃO GERAL (25/07): "pra empresa a gente tem soluções próprias" saiu 3x
    # seguidas pro mesmo cliente que já tinha respondido "Reside" e "É para residência". Se a
    # resposta é igual à anterior E o cliente escreveu algo no meio, ela NÃO pode sair de novo.
    _ant = (fatos_b.get("ult_resposta") or "").strip()
    _novo_txt = (d.get("texto") or "").strip()
    if _ant and _novo_txt and _novo_txt[:80] == _ant[:80]:
        M.log_evento(contato, "resposta_repetida_bloqueada", {"mask": _mask(contato), "texto": _novo_txt[:70]})
        # 25/07: esta frase dizia "...resolver isso com você AGORA" e saiu 4x num sábado à tarde,
        # quando não há ninguém. "Agora" não existe (ordem do dono) — o certo é o prazo real.
        _setor_rep = "suporte" if B._e_suporte(str(texto or ""), fatos_b) else "comercial"
        d = dict(d, acao="transferir",
                 fila=B._recategorizar(0, d.get("intencao", ""), d.get("motivo", ""), str(texto or "")),
                 fastReplyId=0,
                 texto=("Vou passar sua conversa pro time responsável, com prioridade. "
                        "Eles falam com você " + S.proximo_atendimento(setor=_setor_rep) + ", por aqui mesmo."),
                 nota_interna="[Pedrão] REPETIÇÃO — eu ia mandar a mesma frase de novo e o cliente "
                              "já tinha respondido. Assumam a conversa. Última fala do cliente: "
                              + str(texto or "")[:120])
    if _novo_txt:
        d.setdefault("dados_coletados", {})["ult_resposta"] = _novo_txt[:120]

    # ORDEM DO DONO: nada de nota interna na hora — a nota do lead sai no vigia dos 20 min.
    # EXCEÇÃO: na TRANSFERÊNCIA a nota vai junto (o humano precisa do contexto ao pegar o ticket).
    if d.get("acao") != "transferir" and d.get("nota_interna"):
        d["nota_interna"] = ""

    M.add_mensagem(contato, ext, "cliente", texto)
    if d.get("dados_coletados"):
        M.merge_fatos(contato, d["dados_coletados"])

    # linha do tempo do cliente: o que ele já trouxe. Registra 1x por assunto por atendimento
    # (a chave marca o ticket) -- é o que alimenta o aviso de REINCIDÊNCIA na próxima vez.
    _int = d.get("intencao")
    if _int in ("suporte", "financeiro") and str(fatos.get("oc_ticket") or "") != str(ctx.get("ticket_id")):
        try:
            M.registrar_ocorrencia(contato, _int, texto[:80])
            M.merge_fatos(contato, {"oc_ticket": str(ctx.get("ticket_id") or "")})
        except Exception:
            pass

    # >>> A RESPOSTA VAI PRIMEIRO. <<<
    _t_envio = time.time()
    resultado = FS.executar_decisao(ext, d, contato) if ext else {"erro": "sem external_key"}
    _dur_envio = int((time.time() - _t_envio) * 1000)

    # memória nível 2 (resumo da conversa): é uma 2ª chamada de LLM, ~2s. Até 25/07 ela rodava
    # ANTES do envio -- ou seja, TODO cliente em conversa longa esperava o bot "tomar nota" antes
    # de receber a resposta. Agora sai depois e em thread: o resumo continua sendo atualizado
    # (serve pra próxima mensagem), sem custar 1 segundo de espera pro cliente.
    _agendar_resumo(contato)
    # registra o que NÓS enviamos (o detector de "humano digitou" usa isso pra não nos confundir)
    _registra_txt(contato, d.get("texto"))
    for _e in (d.get("_envios") or []):
        _registra_txt(contato, _e.get("text"))
    if d.get("acao") in ("responder", "fastreply") and d.get("texto"):
        M.add_mensagem(contato, ext, "pedrao", d["texto"])

    M.log_evento(contato, "decisao", {
        "mask": _mask(contato), "modo": C.BOT_MODE, "acao": d.get("acao"), "sessao_nova": sessao_nova,
        "fastpath": bool(d.get("_fastpath")),
        "humor": sent.get("humor"), "cor": sent.get("cor"),
        "viab": d.get("_viabilidade_sistema", {}).get("status"),
        "alertas": d.get("_alertas"), "render": d.get("_render"), "envio": resultado,
        # CRONÔMETRO (25/07): DURAÇÃO de cada fase (não acumulado — a 1ª versão media do início
        # da fase até o log, o que somava tudo o que vinha depois e mascarava o gargalo real).
        # antes = leituras de memória; cerebro = fastpath/LLM (inclui MyCore na fatura);
        # envio = FlowSeller (inclui a pausa de naturalidade); total = o que o cliente esperou.
        "ms_antes": _dur_antes, "ms_cerebro": _dur_cerebro, "ms_envio": _dur_envio,
        "ms_total": _ms(_t_ini),
        "uso_llm": dict(L.ULTIMO_USO) if not d.get("_fastpath") else None,
    })

_DEB = Debouncer(on_flush=_processar)

@app.get("/health")
def health():
    return {"ok": True, "uptime_s": int(time.time() - _START_TS), "config": C.resumo_seguro(),
            "canal": ("ATENDIMENTO + ULTRA PEDRÃO (menu ativo — só o Copiloto Financeiro fala)"
                      if PAINEL.canal_tem_menu() else "ULTRA PEDRÃO puro (o Pedrão atende tudo)"),
            "pedrao_calado": PAINEL.so_copiloto(),
            "atuaria_agora": S.deve_atuar(), "modo_efetivo": PAINEL.modo_efetivo(C.BOT_MODE),
            "proximo_atendimento": S.proximo_atendimento(), "desempenho": _desempenho(),
            # "o Pedrão está esperando alguma coisa pra começar?" — resposta direta
            "espera_ativa": _espera_ativa()}

def _espera_ativa():
    """Diz, em português, se existe alguma coisa segurando o Pedrão agora. O dono perguntou
    (25/07) por que às vezes demorava ~10 min pra 'começar' depois de trocar o canal: era a
    sentinela anti-duplo-bot, que existia porque HAVIA outro bot. Não há mais."""
    p = PAINEL.ler()
    if not p.get("ativo", True):
        return "DESLIGADO no painel"
    if p.get("sentinela_nativo"):
        falta = PAINEL.SENTINELA_JANELA_S - (time.time() - float(p.get("nativo_ts") or 0))
        if falta > 0:
            return f"sentinela ligada: aguardando {int(falta)}s (desligue no painel p/ resposta imediata)"
        return "sentinela ligada, mas sem menu recente — responde na hora"
    return "nenhuma — responde na hora"

def _desempenho(n=200):
    """Velocidade real das últimas respostas + acerto do cache do prompt. Serve pra responder
    'está mais rápido?' com número, não com opinião."""
    try:
        with M._db() as c:
            rows = c.execute("SELECT payload FROM eventos WHERE tipo='decisao' "
                             "ORDER BY id DESC LIMIT ?", (n,)).fetchall()
        tot, ceb, rap, cq, ct = [], [], 0, 0, 0
        for (p,) in rows:
            d = json.loads(p)
            if d.get("ms_total") is None:
                continue
            tot.append(d["ms_total"])
            if d.get("ms_cerebro") is not None:
                ceb.append(d["ms_cerebro"])
            if d.get("fastpath"):
                rap += 1
            u = d.get("uso_llm") or {}
            if u:
                ct += 1
                cq += 1 if (u.get("cache_read") or 0) > 0 else 0
        if not tot:
            return {"amostra": 0, "aviso": "sem respostas medidas ainda"}
        tot.sort()
        return {"amostra": len(tot),
                "total_ms_mediana": tot[len(tot) // 2], "total_ms_pior5pct": tot[int(len(tot) * .95)],
                "cerebro_ms_mediana": (sorted(ceb)[len(ceb) // 2] if ceb else None),
                "pct_sem_llm(atalho)": round(100 * rap / len(tot)),
                "pct_cache_quente": (round(100 * cq / ct) if ct else None)}
    except Exception as e:
        return {"erro": str(e)[:120]}

@app.post("/webhook")
async def webhook(request: Request, x_webhook_secret: str = Header(default=""),
                  authorization: str = Header(default="")):
    if C.FS_WEBHOOK_SECRET:
        # A FlowSeller manda o "Token de autenticação" no header Authorization
        # (com prefixo opcional, ex. "Bearer xxx"); aceitamos também X-Webhook-Secret.
        recebido = (x_webhook_secret or authorization or "").strip()
        for pref in ("bearer ", "token "):
            if recebido.lower().startswith(pref):
                recebido = recebido[len(pref):].strip()
        if recebido != C.FS_WEBHOOK_SECRET:
            raise HTTPException(status_code=401, detail="webhook secret inválido")
    p = await request.json()
    ev = _parse_evento(p)

    # DEBUG: captura o payload cru + como o parser leu (pra validar/ajustar o formato do webhook)
    if C.DEBUG_WEBHOOK:
        M.log_evento(ev.get("contato") or "?", "webhook_raw", {
            "raw": p,
            "parser_leu": {"external_key": ev["external_key"], "tem_texto": bool(ev["texto"]),
                           "texto": (ev["texto"] or "")[:120], "tipo": ev["tipo"],
                           "from_me": ev["from_me"], "is_group": ev["is_group"],
                           "contato_mask": _mask(ev["contato"])},
        })

    # ⛔ ANTI-REENTREGA (25/07 09:36, provado no banco): ao criar ticket NOVO, a FlowSeller
    # REENTREGA mensagens antigas do contato — com ticket_id novo, o dedup textual via chave
    # inédita e deixava passar; o cérebro respondeu "Ola bom diaaaaa" de 29 min antes e o Pedrão
    # se APRESENTOU em cima do copiloto. Duas defesas, AQUI NO TOPO (valem pra todos os cérebros):
    # (1) dedup pelo ID ÚNICO da mensagem (UUID da FlowSeller) — reentrega repete o id;
    if ev.get("msg_id") and _dedup_id(str(ev["msg_id"])):
        return {"status": "duplicado_msg_id"}
    # (2) mensagem velha NUNCA inicia resposta — nem do Pedrão, nem do copiloto, nem muta ticket.
    # (o filtro antigo exigia >1h E anterior ao boot; a reentrega tinha 29 min e passou)
    try:
        if ev["texto"] and (time.time() - float(ev["ts"])) > IGNORA_MSG_ANTIGA_S:
            M.log_evento(ev["contato"], "ignorado_msg_velha",
                         {"mask": _mask(ev["contato"]), "idade_s": int(time.time() - float(ev["ts"])),
                          "texto": str(ev["texto"])[:60]})
            return {"status": "ignorado_msg_velha"}
    except Exception:
        pass

    # SENTINELA: menu do chatbot NATIVO saindo do nosso número -> registra e pausa o Pedrão
    # (ANTES do dedup, pra renovar a janela a cada menu visto)
    if ev["from_me"] and ev["texto"] and _MENU_NATIVO.search(str(ev["texto"])):
        PAINEL.marcar_bot_nativo()
        # o menu é a IMPRESSÃO DIGITAL do canal "ATENDIMENTO + ULTRA PEDRÃO" — com so_copiloto
        # em "auto", é isto que faz o Pedrão se calar sozinho na troca de canal (26/07 09:17:44:
        # o menu passou no segundo exato em que o dono trocou, e ninguém precisou virar chave).
        PAINEL.marcar_menu_canal()
        M.log_evento(ev["contato"], "bot_nativo_detectado", {"mask": _mask(ev["contato"])})
        return {"status": "bot_nativo_detectado_pedrao_em_pausa"}

    # HUMANO DIGITOU nesta conversa? (fromMe que não é nosso nem menu de bot) -> o copiloto
    # silencia NAQUELE ticket na hora (ordem do dono: aceitar não para; digitar para).
    if ev["from_me"] and ev["texto"] and not _txt_do_bot(ev["contato"], str(ev["texto"])):
        # TRAVA FORTE (ordem do dono 25/07: "se a atendente humana começar a digitar, o Pedrão
        # MORRE naquela conversa"). Antes só marcava quando vinha ticket_id -- sem ele, a trava
        # simplesmente não era aplicada e o bot podia responder por cima da atendente. Agora
        # marca SEMPRE: por ticket (quando há) E por contato+tempo (rede de segurança).
        _mute = {"cop_mute_ts": time.time()}
        if ev.get("ticket_id") is not None:
            _mute["cop_mute_ticket"] = str(ev["ticket_id"])
        M.merge_fatos(ev["contato"], _mute)
        M.log_evento(ev["contato"], "copiloto",
                     {"mask": _mask(ev["contato"]), "acao": "humano_digitou_silenciei",
                      "ticket": ev.get("ticket_id"), "por_tempo": ev.get("ticket_id") is None})

    # idempotência (webhook repetido) — SEM o ts: a FlowSeller às vezes reenvia a MESMA mensagem
    # com timestamp diferente, o que gerava resposta duplicada. Dedup por contato+TICKET+texto
    # (ticket na chave: conversa nova nunca é confundida com duplicata da anterior).
    _txt_norm = " ".join(str(ev["texto"]).lower().split())
    key = hashlib.sha256((str(ev["external_key"]) + "|" + str(ev.get("ticket_id") or "") + "|"
                          + _txt_norm).encode()).hexdigest()
    if _txt_norm and _dedup(key):
        return {"status": "duplicado_ignorado"}

    # FILTROS (não responder): própria empresa / grupo / mensagem antiga / vazia
    if ev["from_me"]:   return {"status": "ignorado_from_me"}
    if ev["is_group"]:  return {"status": "ignorado_grupo"}
    # HUMANO/DEPARTAMENTO JÁ ASSUMIU: se o ticket foi aceito por um atendente (status open),
    # atribuído a um humano (userId) ou transferido pra uma fila (queueId), o Pedrão NÃO responde
    # — senão ele atropela o atendimento humano (falha grave: cliente transferido pro Suporte
    # recebia mensagem comercial do bot).
    if ev.get("status") == "open" or ev.get("user_id") or ev.get("queue_id"):
        # COPILOTO FINANCEIRO: fila 25 + copiloto ligado + nenhum humano DIGITOU neste ticket
        # -> o bot entrega a fatura ali mesmo (mesmo com atendente tendo ACEITADO — eles aceitam
        # e demoram; quem manda parar é o humano DIGITAR, tratado no marcador cop_mute_ticket).
        if (str(ev.get("queue_id") or "") == str(FILA_FINANCEIRO)
                and PAINEL.ativo() and PAINEL.copiloto_ativo() and ev["texto"]
                and not _cop_mudo(ev)):
            return await asyncio.to_thread(_copiloto, ev)
        # ⛔ ORDEM DO DONO (25/07): "mesmo se ele falar depois da nota amarela, você CONTINUA a
        # conversa, mesmo tendo recategorizado". Ou seja: a FILA sozinha não cala o Pedrão — ela
        # é só o setor que vai assumir. Quem cala é PESSOA: atendente que pegou o ticket
        # (`user_id`) ou que DIGITOU (`cop_mute`). No canal Pedrão puro (só_copiloto desligado),
        # o cliente que responde depois da transferência continua sendo atendido, não some.
        if (ev.get("queue_id") and not ev.get("user_id") and not _cop_mudo(ev)
                and ev["texto"] and PAINEL.ativo() and not PAINEL.so_copiloto()):
            M.log_evento(ev["contato"], "continua_apos_categoria",
                         {"mask": _mask(ev["contato"]), "queue": ev.get("queue_id")})
        else:
            M.log_evento(ev["contato"], "ignorado_humano_assumiu",
                         {"mask": _mask(ev["contato"]), "status": ev.get("status"),
                          "user": bool(ev.get("user_id")), "queue": ev.get("queue_id")})
            return {"status": "ignorado_humano_assumiu"}
    # liga/desliga pelo painel (o "botão" do dono, sem terminal)
    if not PAINEL.ativo():
        return {"status": "desligado_no_painel"}
    # CLIQUE NO BOTÃO "FINANCEIRO" chega ANTES de a FlowSeller marcar a fila no ticket (visto ao
    # vivo 24/07 13:34: saudação não disparava e o cliente ficava no vácuo). Com o copiloto ligado,
    # o clique dispara a saudação de setor NA HORA — o ticket entra na fila 25 logo em seguida.
    if (PAINEL.copiloto_ativo() and ev["texto"] and _BTN_FIN.match(str(ev["texto"]))
            and not _cop_mudo(ev)):
        return await asyncio.to_thread(_copiloto, ev)
    # ⛔ REGRA DURA (ordem do dono 25/07 09:50): com o copiloto LIGADO, o clique FINANCEIRO é
    # assunto EXCLUSIVO do copiloto — se ele não respondeu acima (mute de atendente real, gate,
    # o que for), a resposta certa é SILÊNCIO, NUNCA o cérebro do Pedrão. Foi exatamente o que
    # aconteceu de manhã: um mute falso tirou o copiloto e o clique caiu no LLM, que "inventou"
    # apresentação e 'vou te encaminhar' no lugar da frase padrão do setor.
    if PAINEL.copiloto_ativo() and ev["texto"] and _BTN_FIN.match(str(ev["texto"])):
        M.log_evento(ev["contato"], "clique_fin_so_copiloto",
                     {"mask": _mask(ev["contato"]), "motivo": "copiloto mudo/gate — Pedrão não assume"})
        return {"status": "clique_financeiro_so_copiloto"}

    # ⛔ SÓ COPILOTO (ordem do dono 25/07, canal "ATENDIMENTO + ULTRA PEDRÃO"): o chatbot normal da
    # FlowSeller é quem atende; o Pedrão NÃO PODE aparecer "em hipótese nenhuma". O que ele viu: o
    # cliente clicou FINANCEIRO, o copiloto saudou certo às 08:51 e 1 minuto depois o Pedrão se
    # APRESENTOU ("Eu sou o Pedrão, atendente virtual...") e ainda ofereceu PLANOS — a mensagem do
    # clique voltou pelo webhook num formato que não casou com ^FINANCEIRO$ (veio junto do texto do
    # menu citado), escapou do caminho do copiloto e caiu no cérebro normal.
    # Daqui pra baixo mora TODO o caminho do Pedrão — então a trava fica aqui, DEPOIS dos dois
    # caminhos do copiloto (fila do Financeiro e clique no botão), que continuam funcionando.
    # É trava de CÓDIGO, não regra de prompt: a lição de 25/07 é que regra escrita não segura o
    # modelo (ele já ignorou as regras 16 e 18 escritas).
    if PAINEL.so_copiloto():
        M.log_evento(ev["contato"], "so_copiloto_silenciou",
                     {"mask": _mask(ev["contato"]), "texto": (str(ev["texto"] or ""))[:60]})
        return {"status": "so_copiloto_pedrao_calado"}

    # chatbot NATIVO da FlowSeller atendendo o canal? -> o Pedrão se cala sozinho (anti-duplo-bot).
    # Some o menu nativo (canal voltou pro fluxo vazio) -> retoma automático em ~10 min.
    if PAINEL.bot_nativo_ativo():
        M.log_evento(ev["contato"], "pausado_bot_nativo", {"mask": _mask(ev["contato"])})
        return {"status": "pausado_bot_nativo_ativo"}
    _modo = PAINEL.modo_efetivo(C.BOT_MODE)
    # modo teste OU piloto: processa só número(s) autorizado(s) — ignora o resto do movimento de produção
    _lista = C.TESTE_SO_NUMERO or (PAINEL.allowlist_efetiva(C.PILOT_ALLOWLIST) if _modo == "pilot" else [])
    if _lista:
        import re as _re
        num = _re.sub(r"\D", "", ev["contato"] or "")
        alvos = [_re.sub(r"\D", "", n) for n in _lista if n]
        # número vazio NUNCA passa (evita bug de ''.endswith casar com tudo)
        if len(num) < 8 or not any(num.endswith(n) or n.endswith(num) for n in alvos if n):
            return {"status": "ignorado_fora_da_allowlist"}
    try:
        if float(ev["ts"]) and (time.time() - float(ev["ts"])) > 3600 and float(ev["ts"]) < _START_TS:
            return {"status": "ignorado_msg_antiga"}
    except Exception:
        pass
    if not ev["texto"] and ev["tipo"] not in ("audio", "ptt", "voice"):
        return {"status": "ignorado_vazio"}

    # horário: Pedrão atua fora do expediente humano. TRAVA (24/07): FORCAR_ATUACAO é flag de
    # TESTE e ficou esquecida no .env -> o Pedrão se apresentou em pleno horário humano por cima
    # da equipe. Em modo LIVE ela passa a ser IGNORADA — só vale em shadow/pilot (teste de verdade).
    # auditoria 24/07: pilot também ENVIA de verdade (só restringe à allowlist) -> a flag de teste
    # agora só vale em SHADOW (que não envia nada). live/pilot ignoram.
    _forcar_teste = C.FORCAR_ATUACAO and PAINEL.modo_efetivo(C.BOT_MODE) == "shadow"
    if not S.deve_atuar() and not _forcar_teste:
        M.log_evento(ev["contato"], "fora_de_atuacao",
                     {"mask": _mask(ev["contato"]), "tem_texto": bool(ev["texto"]), "tipo": ev["tipo"]})
        return {"status": "dentro_horario_humano_nao_atua"}

    # áudio: baixa e transcreve; se falhar, o cérebro pede confirmação por escrito (nunca finge que entendeu)
    texto = ev["texto"]
    if ev["tipo"] in ("audio", "ptt", "voice") and not texto:
        if ev.get("media_url"):
            import transcricao as TR
            # PERF (25/07): rodava DIRETO no handler async -- baixar o áudio + transcrever é I/O
            # de rede de vários segundos e travava o event loop INTEIRO: enquanto um áudio era
            # processado, todos os outros clientes ficavam na fila sem resposta. Agora vai pra
            # thread e o servidor continua atendendo o resto.
            t, erro = await asyncio.to_thread(
                TR.transcrever, ev["media_url"], C.FS_JWT_RESPOSTA or None)
            if t:
                texto = t
                M.log_evento(ev["contato"], "audio_transcrito", {"mask": _mask(ev["contato"]), "chars": len(t)})
            else:
                texto = "[áudio recebido, mas não consegui transcrever — peça ao cliente pra confirmar por escrito]"
                M.log_evento(ev["contato"], "audio_falha", {"mask": _mask(ev["contato"]), "erro": erro})
        else:
            texto = "[áudio recebido sem link de mídia — peça confirmação por escrito]"

    _DEB.add(ev["contato"], texto, ctx={"external_key": ev["external_key"], "nome": ev["nome"], "ticket_id": ev["ticket_id"]})
    return {"status": "enfileirado", "modo": C.BOT_MODE, "contato": _mask(ev["contato"])}

# ---- admin protegido (inspeção do modo sombra) ----
def _admin(tok):
    if not C.ADMIN_TOKEN or tok != C.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="admin token inválido")

# ---- PAINEL DE CONTROLE (web, sem terminal) ----
from fastapi.responses import HTMLResponse, PlainTextResponse

def _auth_painel(tok):
    """Painel aceita: ADMIN_TOKEN (scripts) OU PAINEL_SENHA (env) OU a senha definida no painel."""
    if C.ADMIN_TOKEN and tok == C.ADMIN_TOKEN: return
    if C.PAINEL_SENHA and tok == C.PAINEL_SENHA: return
    if PAINEL.senha_ok(tok): return
    raise HTTPException(status_code=401, detail="senha inválida")

def _sem_senha(d):
    d = dict(d); d.pop("senha", None); return d  # nunca devolve a senha ao navegador

@app.get("/admin/painel")
def painel_get(x_admin_token: str = Header(default="")):
    _auth_painel(x_admin_token)
    return _sem_senha(PAINEL.ler())

@app.post("/admin/painel")
async def painel_post(request: Request, x_admin_token: str = Header(default="")):
    _auth_painel(x_admin_token)
    body = await request.json()
    return _sem_senha(PAINEL.salvar(body))

_PAINEL_PATH = _os.path.join(_os.path.dirname(__file__), "painel.html")
@app.get("/painel", response_class=HTMLResponse)
def painel_html():
    try:
        with open(_PAINEL_PATH, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "<h1>Painel indisponivel</h1>"


_APIKEY_PATH = _os.path.join(_os.path.dirname(__file__), "..", "data", "anthropic_key.txt")

@app.get("/admin/apikey")
def admin_apikey_status(x_admin_token: str = Header(default="")):
    """Status da chave da API (mascarada) — pro painel mostrar se já está configurada."""
    _auth_painel(x_admin_token)
    import llm as L
    k = L._anthropic_key()
    return {"tem_chave": bool(k), "mascara": (k[:11] + "…" + k[-4:]) if k and len(k) > 20 else "",
            "provider": C.LLM_PROVIDER}

@app.post("/admin/apikey")
async def admin_apikey_set(request: Request, x_admin_token: str = Header(default="")):
    """Salva a chave da API (colada no painel) num arquivo protegido — sem terminal.
    Nunca devolve a chave; o llm.py lê esse arquivo a cada chamada (não precisa reiniciar)."""
    _auth_painel(x_admin_token)
    body = await request.json()
    key = (body.get("key") or "").strip()
    if not key.startswith("sk-ant-") or len(key) < 20:
        raise HTTPException(status_code=400, detail="chave inválida (deve começar com sk-ant-)")
    _os.makedirs(_os.path.dirname(_APIKEY_PATH), exist_ok=True)
    with open(_APIKEY_PATH, "w", encoding="utf-8") as f:
        f.write(key)
    try: _os.chmod(_APIKEY_PATH, 0o600)
    except Exception: pass
    M.log_evento("admin", "apikey_set", {"len": len(key), "provider": C.LLM_PROVIDER})
    return {"ok": True, "len": len(key), "provider": C.LLM_PROVIDER}

@app.get("/admin/mycore")
def admin_mycore_status(x_admin_token: str = Header(default="")):
    """Status do token do MyCore (área do cliente) — pro painel mostrar se já está configurado."""
    _auth_painel(x_admin_token)
    import mycore as MC
    return {"tem_token": MC.token_configurado(), "base": MC.BASE_URL}

@app.post("/admin/mycore")
async def admin_mycore_set(request: Request, x_admin_token: str = Header(default="")):
    """Salva o token do MyCore (colado no painel) em arquivo protegido — sem terminal, nunca devolvido."""
    _auth_painel(x_admin_token)
    import mycore as MC
    body = await request.json()
    tok = (body.get("token") or "").strip()
    if len(tok) < 16:
        raise HTTPException(status_code=400, detail="token muito curto (confira)")
    MC.salvar_token(tok)
    M.log_evento("admin", "mycore_token_set", {"len": len(tok)})
    return {"ok": True, "len": len(tok)}

@app.post("/admin/mycore/testar")
async def admin_mycore_testar(request: Request, x_admin_token: str = Header(default="")):
    """Testa o token: busca um CPF e diz se autenticou (sem devolver dado pessoal)."""
    _auth_painel(x_admin_token)
    import mycore as MC
    if not MC.token_configurado():
        return {"ok": False, "erro": "token não configurado"}
    body = await request.json()
    cpf = MC.extrair_cpf_cnpj(body.get("cpf") or "")
    if not cpf:
        return {"ok": False, "erro": "informe um CPF/CNPJ válido pra testar"}
    try:
        clientes = MC.clientes_por_cpf(cpf)
        return {"ok": True, "autenticou": True, "achou_cadastro": len(clientes) > 0, "qtd": len(clientes)}
    except MC.MyCoreErro as e:
        return {"ok": False, "autenticou": e.tipo != "auth", "erro": f"{e.tipo}: {e}"}

@app.get("/admin/eventos")
def admin_eventos(x_admin_token: str = Header(default=""), limite: int = 50):
    _auth_painel(x_admin_token)
    import sqlite3
    con = sqlite3.connect(C.SQLITE_PATH)
    rows = con.execute("SELECT ts,contato,tipo,payload FROM eventos ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
    con.close()
    return [{"ts": r[0], "tipo": r[2], "payload": json.loads(r[3])} for r in rows]

@app.get("/admin/testar-llm")
def admin_testar_llm(x_admin_token: str = Header(default="")):
    """Verifica se o cérebro (LLM/token) está vivo — use pra detectar token de 1 ano vencido."""
    _admin(x_admin_token)
    import llm as L, time as _t
    t0 = _t.time()
    try:
        r = L.gerar("Responda só: OK", "diga OK")
        return {"ok": True, "provider": C.LLM_PROVIDER, "ms": int((_t.time()-t0)*1000), "amostra": (r or "")[:60]}
    except Exception as e:
        return JSONResponse(status_code=503, content={"ok": False, "provider": C.LLM_PROVIDER, "erro": str(e)})

@app.post("/admin/teste-botoes")
async def admin_teste_botoes(request: Request, x_admin_token: str = Header(default="")):
    """ETAPA 4 da investigação dos botões de cópia (24/07): dispara a matriz A/B controlada
    para o NÚMERO DE TESTE, a qualquer hora, sem depender do fluxo noturno.

    Cada variante vai precedida de um rótulo em mensagem SEPARADA, para que o código chegue
    sozinho no balão (condição do teste). Trava: só envia para números do allowlist do piloto
    (ou para TESTE_BOTOES_NUM), nunca para cliente."""
    _auth_painel(x_admin_token)   # mesma trava dos outros /admin (senha do painel)
    body = await request.json()
    import mycore as MC
    numero = re.sub(r"\D", "", str(body.get("numero") or _os.environ.get("TESTE_BOTOES_NUM") or ""))
    permitidos = [re.sub(r"\D", "", n) for n in
                  (PAINEL.allowlist_efetiva(C.PILOT_ALLOWLIST) or []) if n]
    extra = re.sub(r"\D", "", _os.environ.get("TESTE_BOTOES_NUM") or "")
    if extra: permitidos.append(extra)
    na_lista = any(numero.endswith(p) or p.endswith(numero) for p in permitidos if p)
    # com o bot liberado pra todos a allowlist do piloto fica vazia; nesse caso exige confirmação
    # explícita do número na própria chamada (que só sai com o token de admin).
    if not numero or not (na_lista or (not permitidos and body.get("confirmo_numero_de_teste"))):
        raise HTTPException(status_code=400,
                            detail="numero fora do allowlist de teste (use TESTE_BOTOES_NUM, a "
                                   "allowlist do piloto, ou confirmo_numero_de_teste=true)")
    pix = (body.get("pix") or "").strip()
    linha = (body.get("linha") or "").strip()
    if not pix and body.get("cpf"):        # busca uma fatura real no MyCore
        try:
            # client_id: CPF com vários cadastros (o dono só tem boleto no 6817)
            r = MC.resolver_fatura(re.sub(r"\D", "", str(body["cpf"])),
                                   client_id=body.get("client_id"))
            if (r or {}).get("status") != "entregue":
                raise HTTPException(status_code=404,
                                    detail=f"MyCore não devolveu fatura (status={(r or {}).get('status')}, "
                                           f"motivo={(r or {}).get('motivo')})")
            # resolver_fatura devolve a RÉGUA pronta em 'envios'; o Pix e a linha digitável são
            # os itens tipo 'raw' -- é de lá que a matriz A/B tira os códigos.
            for e in (r.get("envios") or []):
                t = (e.get("text") or "").strip()
                if "BR.GOV.BCB.PIX" in t and not pix:
                    pix = t
                elif t.isdigit() and len(t) in (47, 48) and not linha:
                    linha = t
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"MyCore: {e}")
    if not pix and not linha:
        raise HTTPException(status_code=400, detail="informe pix/linha ou um cpf para buscar no MyCore")

    matriz = []
    if pix:
        matriz += [("A", "codigo sozinho, exatamente como veio da Efi", pix),
                   ("D", "codigo PRECEDIDO de descricao na MESMA mensagem", "Segue seu Pix:\n" + pix),
                   ("E", "descricao em mensagem separada, codigo sozinho depois", pix),
                   ("F", "codigo com quebra de linha no FIM", pix + "\n")]
    if linha:
        matriz += [("A-boleto", "linha digitavel sozinha", linha),
                   ("D-boleto", "linha com descricao na MESMA mensagem", "Linha digitável:\n" + linha),
                   ("F-boleto", "linha com quebra de linha no fim", linha + "\n")]
    saida = []
    for cod, desc, texto in matriz:
        FS.responder_texto(numero, f"🧪 TESTE {cod} — {desc}", number=numero,
                           delay=False, assinar=False)
        r = FS.responder_texto(numero, texto, number=numero, delay=False, assinar=False)
        m = ((r.get("resposta") or {}).get("message") or {})
        saida.append({"variante": cod, "enviado": bool(r.get("enviado")), "erro": r.get("erro"),
                      "bytes": len(texto.encode("utf-8")),
                      "sha256": hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16],
                      "fs_id": m.get("id"), "wamid": m.get("messageId"),
                      "mediaType": m.get("mediaType"), "sendType": m.get("sendType"),
                      "typeTemplate": m.get("typeTemplate")})
    return {"numero": _mask(numero), "variantes": saida,
            "observar_no_celular": "qual variante mostrou o botao de copiar",
            "nota": "preview_url/context/template nao existem na API externa da FlowSeller — "
                    "campos ausentes registrados como None no log forense"}

FOLLOWUP_TXT = ("Oi! Passando aqui rapidinho 😊 Vi que você perguntou sobre os nossos planos.\n\n"
                "Qual é o endereço (rua, número e bairro)? É só pra eu verificar a viabilidade "
                "e te passar a informação certa.")
_PEDI_ENDERECO = re.compile(r"(rua,?\s*n[úu]mero\s*e\s*bairro|qual\s+[ée]\s+o\s+endere[çc]o|"
                            r"me\s+passa\s+o\s+endere[çc]o|confirmar?\s+a\s+viabilidade|"
                            r"verificar\s+a\s+viabilidade)", re.I)
# ⛔ ORDEM DO DONO (25/07): "não precisa esperar o SIM quando pergunta se quer que mostre os
# planos — espera 3 minutos e envia do mesmo jeito, como follow-up". Perguntar e ficar esperando
# mata o lead; o material é o que faz ele responder.
_OFERECI_PLANOS = re.compile(
    r"(quer\s+(que\s+eu\s+)?(te\s+)?(mostr|mand|envi|ver)\w*[^.!?\n]{0,25}plano|"
    r"posso\s+(te\s+)?(mostrar|mandar|enviar)[^.!?\n]{0,20}plano|"
    r"j[áa]\s+conhece\s+(os\s+)?(nossos\s+)?planos)", re.I)
PLANOS_ESPERA_S = int(os.environ.get("PLANOS_ESPERA_S", "180"))   # 3 min

def _planos_pendentes():
    """Perguntei 'quer ver os planos?' e o cliente não respondeu em 3 min -> mando assim mesmo."""
    agora = time.time()
    import sqlite3
    con = sqlite3.connect(C.SQLITE_PATH)
    con.row_factory = sqlite3.Row
    alvos = []
    try:
        contatos = [r["contato"] for r in con.execute(
            "SELECT DISTINCT contato FROM mensagens WHERE ts>?", (agora - 7200,)).fetchall()]
        for c in contatos:
            ult = con.execute("SELECT de,texto,ts FROM mensagens WHERE contato=? ORDER BY ts DESC LIMIT 1",
                              (c,)).fetchone()
            if not ult or ult["de"] != "pedrao":
                continue
            idade = agora - float(ult["ts"])
            if not (PLANOS_ESPERA_S <= idade <= 7200) or not _OFERECI_PLANOS.search(ult["texto"] or ""):
                continue
            f = M.get_fatos(c)
            if f.get("cop_mute_ticket") or f.get("cop_mute_ts"):
                continue
            if f.get("planos_ts") and (agora - float(f["planos_ts"])) < 1800:
                continue                      # já mandou o pacote há pouco
            alvos.append({"contato": c, "mask": _mask(c), "min": int(idade // 60)})
    finally:
        con.close()
    return alvos

def _followup_alvos(min_s: float, max_s: float):
    """Leads que ficaram parados depois de eu pedir o endereço. Critérios (todos obrigatórios):
    última fala da conversa é MINHA e pedia endereço · o cliente não escreveu depois ·
    ninguém mais assumiu · ainda não insisti nessa conversa."""
    agora = time.time()
    import sqlite3
    con = sqlite3.connect(C.SQLITE_PATH)
    con.row_factory = sqlite3.Row
    alvos = []
    try:
        contatos = [r["contato"] for r in con.execute(
            "SELECT DISTINCT contato FROM mensagens WHERE ts>?", (agora - max_s,)).fetchall()]
        for c in contatos:
            ult = con.execute("SELECT de,texto,ts FROM mensagens WHERE contato=? ORDER BY ts DESC LIMIT 1",
                              (c,)).fetchone()
            if not ult or ult["de"] != "pedrao":
                continue
            idade = agora - float(ult["ts"])
            if not (min_s <= idade <= max_s) or not _PEDI_ENDERECO.search(ult["texto"] or ""):
                continue
            f = M.get_fatos(c)
            if f.get("followup_ts") or f.get("cop_mute_ticket") or f.get("cop_mute_ts"):
                continue
            alvos.append({"contato": c, "mask": _mask(c), "min": int(idade // 60)})
    finally:
        con.close()
    return alvos

@app.post("/admin/followup-lead")
async def admin_followup_lead(request: Request, x_admin_token: str = Header(default="")):
    """2ª TENTATIVA do lead (ordem do dono 25/07): perguntei o endereço pra ver viabilidade, o
    cliente NÃO respondeu -> depois de ~10-15 min mando UMA pergunta simples pra não deixar o
    lead morrer. Só entra quem: (a) a última fala da conversa foi MINHA e foi pedido de endereço;
    (b) o cliente não escreveu nada depois; (c) ninguém mais falou com ele; (d) 1x só por conversa.
    Body: {"min_min": 10, "max_min": 180, "confirmar": false}"""
    _auth_painel(x_admin_token)
    body = await request.json() if await request.body() else {}
    min_s = float(body.get("min_min", 10)) * 60
    max_s = float(body.get("max_min", 180)) * 60
    confirmar = bool(body.get("confirmar"))
    alvos = await asyncio.to_thread(_followup_alvos, min_s, max_s)
    if not confirmar:
        return {"dry_run": True, "quantos": len(alvos), "alvos": alvos}
    TXT = FOLLOWUP_TXT
    ok = []
    for a in alvos:
        try:
            M.merge_fatos(a["contato"], {"followup_ts": time.time()})
            _ext = M.ultimo_external_key(a["contato"]) or a["contato"]
            await asyncio.to_thread(FS.responder_texto, _ext, TXT,
                                    number=a["contato"], assinar=False, delay=False)
            M.log_evento(a["contato"], "followup_lead", {"mask": a["mask"], "min": a["min"]})
            ok.append(a["mask"])
        except Exception as ex:
            M.log_evento(a["contato"], "followup_falhou", {"erro": str(ex)[:80]})
    return {"dry_run": False, "enviados": len(ok), "detalhe": ok}

def _eventos_desde(desde: float):
    """Eventos (ts, contato, tipo, payload) a partir de um epoch — usado pelo resgate."""
    import sqlite3
    con = sqlite3.connect(C.SQLITE_PATH)
    rows = con.execute("SELECT ts,contato,tipo,payload FROM eventos WHERE ts>=? ORDER BY ts",
                       (desde,)).fetchall()
    con.close()
    out = []
    for ts, contato, tipo, payload in rows:
        try:
            p = json.loads(payload) if payload else {}
        except Exception:
            p = {}
        out.append({"ts": ts, "contato": contato, "tipo": tipo, "payload": p})
    return out

@app.post("/admin/resgate")
async def admin_resgate(request: Request, x_admin_token: str = Header(default="")):
    """RESGATE de quem ficou SEM RESPOSTA NENHUMA (ordem do dono 25/07 15:36, depois que a flag
    `so_copiloto` calou leads reais entre 15:10 e 15:34 — inclusive lead de anúncio pago).

    Regra do dono, literal: só resgata quem NÃO recebeu resposta de ninguém. **Se um atendente
    falou, o Pedrão NÃO responde.** O Pedrão se apresenta e dá continuidade.

    Body: {"desde": "HH:MM" ou epoch, "confirmar": false}
      confirmar=false (padrão) -> DRY-RUN: só lista quem seria resgatado, não manda nada.
    """
    _auth_painel(x_admin_token)
    body = await request.json() if await request.body() else {}
    desde = body.get("desde")
    if isinstance(desde, str) and ":" in desde:
        from datetime import datetime as _dt
        hoje = _dt.now(S._TZ) if S._TZ else _dt.now()
        hh, mm = desde.split(":")[:2]
        desde = hoje.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0).timestamp()
    desde = float(desde or (time.time() - 6 * 3600))
    confirmar = bool(body.get("confirmar"))

    # 1) quem CHEGOU e foi calado no período (a flag registra o texto do cliente)
    silenciados = {}
    for e in _eventos_desde(desde):
        if float(e.get("ts") or 0) < desde:
            continue
        if e.get("tipo") == "so_copiloto_silenciou":
            p = e.get("payload") or {}
            txt = (p.get("texto") or "").strip()
            if txt:                       # o evento sem texto é o gêmeo do webhook (ignorar)
                silenciados.setdefault(e["contato"], {"ts": float(e["ts"]), "texto": txt})
    # 2) quem JÁ TEVE resposta de alguém (nossa OU de atendente) sai da lista — regra do dono
    ATENDIDO = {"decisao", "copiloto", "ignorado_humano_assumiu", "nota_lead"}
    for e in _eventos_desde(desde):
        c = e.get("contato")
        if c not in silenciados or float(e.get("ts") or 0) < silenciados[c]["ts"]:
            continue
        tipo, p = e.get("tipo"), (e.get("payload") or {})
        if tipo in ATENDIDO or (tipo == "copiloto" and p.get("acao")):
            silenciados.pop(c, None)

    # 3) AGRADECIMENTO = prova de que JÁ falou com alguém (ordem do dono 25/07: "'muito obrigado
    # Patrick' mostra que falou com alguém, então esse não dispara"). Mandar "desculpa a demora"
    # pra quem acabou de elogiar o atendimento é pior do que não mandar nada.
    _JA_FALOU = re.compile(
        r"\b(obrigad|agrade[çc]|valeu|excelente\s+atendimento|[óo]timo\s+atendimento|"
        r"muito\s+bom\s+atendimento|resolvido|era\s+isso\s+mesmo|show|perfeito,?\s+obrigad)", re.I)
    for c, v in list(silenciados.items()):
        if _JA_FALOU.search(v["texto"]):
            silenciados.pop(c, None)
    for c in (body.get("excluir") or []):        # exclusão manual, quando o dono mandar
        silenciados.pop(str(c), None)

    alvos = [{"contato": c, "mask": _mask(c), "texto": v["texto"][:70],
              "quando": time.strftime("%H:%M", time.localtime(v["ts"]))}
             for c, v in silenciados.items()]
    if not confirmar:
        return {"dry_run": True, "quantos": len(alvos), "alvos": alvos,
                "obs": "nada foi enviado; repita com confirmar=true para o Pedrão se apresentar"}

    TXT = ("Olá! Eu sou o Pedrão, agente virtual da WebFiber 😊 Desculpa a demora em te responder "
           "aqui — vi sua mensagem e não quero te deixar sem retorno.\n\n"
           "Me conta o que você precisa que eu já resolvo ou chamo a equipe certa pra você.")
    enviados, falhas = [], []
    for a in alvos:
        try:
            r = await asyncio.to_thread(FS.responder_texto, a["contato"], TXT,
                                        number=a["contato"], assinar=False, delay=False)
            (enviados if not r.get("erro") else falhas).append(a["mask"])
            M.log_evento(a["contato"], "resgate_enviado", {"mask": a["mask"]})
        except Exception as ex:
            falhas.append(f'{a["mask"]}: {ex}')
    return {"dry_run": False, "enviados": len(enviados), "falhas": falhas, "detalhe": enviados}

@app.post("/admin/simular")
async def admin_simular(request: Request, x_admin_token: str = Header(default="")):
    """Testa uma mensagem sem passar pela FlowSeller: retorna a decisão do cérebro (e quanto
    tempo ela levou -- é a forma de medir o cérebro puro, sem mandar nada pra ninguém)."""
    _auth_painel(x_admin_token)   # mesma trava dos outros /admin (aceita a senha do painel)
    body = await request.json()
    texto = body.get("texto", "")
    hist = body.get("historico", [])
    mem = body.get("memoria", {})
    nova = bool(body.get("sessao_nova", False))
    sent = SENT.classificar(texto, " ".join(h.get("texto", "") for h in hist[-4:]))
    t0 = time.time()
    # passa pelo MESMO caminho de produção: atalho primeiro, LLM só se o atalho não resolver
    d = await asyncio.to_thread(B.fastpath, texto, nova, hist, mem, sent, None)
    if d is None:
        d = await asyncio.to_thread(B.decidir, texto, hist, mem, nova, "", sent)
    return {"decisao": {k: v for k, v in d.items() if not k.startswith("_")},
            "ms": int((time.time() - t0) * 1000), "atalho_sem_llm": bool(d.get("_fastpath")),
            "humor": sent.get("humor"), "uso_llm": (None if d.get("_fastpath") else dict(L.ULTIMO_USO)),
            "viabilidade_sistema": d.get("_viabilidade_sistema"),
            "alertas": d.get("_alertas"), "render": d.get("_render")}
