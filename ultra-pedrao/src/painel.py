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
    "atualizado_em": 0.0,     # epoch da ultima alteracao (pro painel mostrar a vigencia)
    "senha": "",             # senha amigavel do painel (definida pelo dono; vazio = usa token/env)
}

def senha_ok(tok: str) -> bool:
    s = (ler().get("senha") or "").strip()
    return bool(s) and tok == s

def ler() -> dict:
    try:
        with open(PATH, encoding="utf-8") as f:
            d = json.load(f)
        return {**PADRAO, **d}
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
    return "\n".join(partes)
