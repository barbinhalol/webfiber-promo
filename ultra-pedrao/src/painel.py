# -*- coding: utf-8 -*-
"""Painel de controle em runtime (sem terminal): o dono edita um JSON via web e o cérebro
lê a cada decisão. Assim, ligar/desligar, avisos de rede e ajustes de atendimento têm
efeito IMEDIATO, sem rebuild nem git."""
import json, os, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "..", "data", "painel.json")
_LOCK = threading.Lock()

PADRAO = {
    "ativo": True,            # liga/desliga o Ultra Pedrão (desligado = nao responde ninguem)
    "modo": "",              # ""=usa .env | "shadow" | "pilot" | "live"
    "allowlist": "",         # ""=usa .env | numeros separados por virgula (modo pilot)
    "aviso": "",             # AVISO URGENTE (ex.: rompimento) — injetado no contexto do cerebro
    "aviso_ativo": False,     # o aviso so entra no contexto se estiver ativo
    "ajustes": "",           # instrucoes livres do dono em portugues (anexadas ao cerebro)
    "desbloqueio_confianca": False,  # DESLIGADO por padrao: so o dono liga quando for testar
    "saudacao": "",           # ""=usa a saudacao padrao do codigo | texto custom (ex.: evento/feriado)
    "copiloto_financeiro": False,  # Copiloto: entrega fatura na fila do Financeiro (horario humano),
                                   # assinado "*Financeiro WebFiber*", cala quando um humano DIGITA
    "nativo_ts": 0.0,         # sentinela anti-duplo-bot: quando o menu NATIVO da FlowSeller foi visto
    "sentinela_nativo": False, # DESLIGADA (23/07: dono CANCELOU o Pedrao nativo da FlowSeller ->
                               # nao ha mais outro bot; a espera de 10-30min virou so atraso inutil).
                               # Se um dia voltar a existir outro chatbot no canal, liga aqui.
    "atualizado_em": 0.0,     # epoch da ultima alteracao (pro painel mostrar a vigencia)
    "senha": "",             # senha amigavel do painel (definida pelo dono; vazio = usa token/env)
}

def senha_ok(tok: str) -> bool:
    s = (ler().get("senha") or "").strip()
    return bool(s) and tok == s

# PERF (25/07): ler() era chamado 6-8x por mensagem (ativo, copiloto_ativo, modo_efetivo,
# bot_nativo_ativo, allowlist, ajustes...) e CADA uma abria + parseava o JSON do disco.
# Agora o resultado fica em cache e só é relido quando o arquivo MUDA (mtime+tamanho) --
# o efeito continua IMEDIATO ao salvar pelo painel, sem o I/O repetido.
_CACHE = {"chave": None, "dados": None}

def ler() -> dict:
    try:
        st = os.stat(PATH)
        chave = (st.st_mtime_ns, st.st_size)
        if _CACHE["chave"] == chave and _CACHE["dados"] is not None:
            return dict(_CACHE["dados"])           # cópia: quem chamar não altera o cache
        with open(PATH, encoding="utf-8") as f:
            d = json.load(f)
        cheio = {**PADRAO, **d}
        _CACHE["chave"], _CACHE["dados"] = chave, cheio
        return dict(cheio)
    except Exception:
        return dict(PADRAO)

def salvar(novo: dict) -> dict:
    atual = ler()
    for k in PADRAO:
        if k in novo:
            atual[k] = novo[k]
    atual["atualizado_em"] = time.time()
    with _LOCK:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(atual, f, ensure_ascii=False, indent=1)
    return atual

def ativo() -> bool:
    return bool(ler().get("ativo", True))

def desbloqueio_ativo() -> bool:
    """Desbloqueio em confiança só age quando o dono liga isto no painel."""
    return bool(ler().get("desbloqueio_confianca", False))

# 25/07 (pergunta do dono "esse delay de 10 min pode ser bem menor?"): a espera existia porque
# HAVIA outro bot no canal e era preciso dar tempo do menu dele sair antes do Pedrão falar. O
# agente nativo foi CANCELADO -- não há mais o que esperar. A sentinela já nasce DESLIGADA (o
# Pedrão responde na hora); e se um dia for religada, a espera agora é de 2 min, não 30.
SENTINELA_JANELA_S = int(os.environ.get("SENTINELA_JANELA_S", "120"))

def marcar_bot_nativo():
    """SENTINELA ANTI-DUPLO-BOT: registra que o chatbot NATIVO da FlowSeller acabou de mandar
    um menu (detectado no webhook como mensagem do nosso proprio numero). Enquanto isso estiver
    'fresco', o Pedrao se cala sozinho -- nunca mais dois bots na mesma conversa.
    Com a sentinela DESLIGADA (padrao), nao grava nada: no canal novo o chatbot manda menu o
    tempo todo, e isso virava escrita em disco a cada mensagem, sem servir pra nada."""
    if not ler().get("sentinela_nativo", False):
        return
    salvar({"nativo_ts": time.time()})

def bot_nativo_ativo(janela_s: int = None) -> bool:
    """True se o menu nativo foi visto nos ultimos janela_s segundos (30 min por padrao -- subiu de
    10 pra 30 porque um VALE de movimento > janela reabria a brecha da 1a mensagem: a janela
    expirava e a 1a msg de uma conversa nova passava antes do menu nativo daquela conversa sair).
    Trocar o canal na FlowSeller vira o interruptor: ligou o nativo -> Pedrao pausa; voltou pro fluxo
    vazio -> clique "Retomar Pedrao agora" no painel (ou espera ~30 min sem menu).
    23/07: SO age com sentinela_nativo LIGADA no painel — o Pedrao nativo foi CANCELADO, entao por
    padrao nao ha o que esperar e o Ultra Pedrao responde IMEDIATAMENTE."""
    try:
        p = ler()
        if not p.get("sentinela_nativo", False):
            return False
        return (time.time() - float(p.get("nativo_ts") or 0)) < (janela_s or SENTINELA_JANELA_S)
    except Exception:
        return False

def copiloto_ativo() -> bool:
    """Copiloto Financeiro: entrega fatura na fila do Financeiro durante o horario humano."""
    return bool(ler().get("copiloto_financeiro", False))

def saudacao_custom() -> str:
    """Saudação customizada (ex.: evento/feriado). Vazio = usa a padrão do código (brain._ABERTURA).
    Lida a cada mensagem -> troca (e o botão "restaurar padrão" no painel) valem na hora, sem deploy."""
    return (ler().get("saudacao") or "").strip()

def modo_efetivo(env_modo: str) -> str:
    """Modo do painel tem prioridade sobre o .env (shadow/pilot/live)."""
    m = (ler().get("modo") or "").strip().lower()
    return m or env_modo

def allowlist_efetiva(env_list):
    """Allowlist do painel tem prioridade sobre o .env."""
    import re
    a = (ler().get("allowlist") or "").strip()
    if a:
        return [re.sub(r"\D", "", n) for n in a.split(",") if n.strip()]
    return env_list

def contexto_extra() -> str:
    """Texto que o cérebro recebe além do prompt: aviso urgente + ajustes do dono."""
    p = ler()
    partes = []
    if p.get("aviso_ativo") and (p.get("aviso") or "").strip():
        partes.append(
            "[AVISO OPERACIONAL DO DONO — vale AGORA, priorize ao responder quem tocar no assunto: "
            + p["aviso"].strip() + " — acolha, informe com naturalidade e NÃO prometa horário exato de "
            "retorno além do que o dono disse; registre e reporte ao time.]")
    if (p.get("ajustes") or "").strip():
        partes.append("[AJUSTES DE ATENDIMENTO definidos pelo dono (siga à risca): " + p["ajustes"].strip() + "]")
    sc = (p.get("saudacao") or "").strip()
    if sc:
        partes.append(
            "[SAUDAÇÃO OFICIAL VIGENTE — se esta for a PRIMEIRA mensagem de um atendimento novo (sessão nova), "
            "abra EXATAMENTE com este texto, sem alterar nada: \"" + sc + "\"]")
    return "\n".join(partes)
