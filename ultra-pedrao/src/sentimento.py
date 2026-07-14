# -*- coding: utf-8 -*-
"""Leitura de sentimento/humor do cliente por CÓDIGO (sem LLM — roda até no fastpath, custo zero).
Serve pra: (a) adaptar o tom do Pedrão, (b) sinalizar escalada quando a temperatura sobe,
(c) mostrar um semáforo 🟢🟡🔴 no painel do dono. É um sinal simples e rápido; a nuance fina
continua com o modelo, mas isso garante que ninguém furioso passe batido."""
import re

# fúria / risco (vermelho) — inclui jurídico, ameaça, xingamento, desistência
_FURIA = re.compile(
    r"\b(procon|advogad|process(o|ar|ei)|justi[çc]a|c[oó]digo de defesa|absurdo|desca(so|rado)|"
    r"verg(onha|onhoso)|palha[çc]ada|cansei|enchei o saco|p[ée]ssimo|horr[íi]vel|lixo|merda|"
    r"porcaria|revoltad|indignad|nunca mais|cancel(ar|amento|a minha)|reclama[çc]|[óo]dio|"
    r"irritad|puto|inadmiss[íi]vel|rid[íi]cul|descaso|golpe|enrola[çr]|palha[çc]o|"
    r"n[ãa]o aguento|t[oô] cansad|me engana)\b", re.I)
# positivo / caloroso (verde) — satisfação, intenção de fechar
_POSITIVO = re.compile(
    r"\b(obrigad|valeu|agrade[çc]|show|top|maravilh|ador(ei|o)|amei|excelente|perfeito|"
    r"[óo]timo|muito bom|gratid|abra[çc]o|parab[ée]ns|quero sim|fech(ar|ado|a comigo)|"
    r"bora|massa|joia|adorei|que bom|voc[êe]s s[ãa]o [óo]timos|salvou|top demais)\b", re.I)

def classificar(texto, contexto=""):
    """Retorna {'humor','temp'(0-3),'cor'}. temp>=3 = quente/vermelho (priorizar humano)."""
    t = (texto or "") + " " + (contexto or "")
    if _FURIA.search(t):
        return {"humor": "irritado", "temp": 3, "cor": "🔴"}
    if _POSITIVO.search(t):
        return {"humor": "animado", "temp": 0, "cor": "🟢"}
    return {"humor": "neutro", "temp": 1, "cor": "🟡"}

def hint_tom(s):
    """Diretriz de TOM injetada no contexto do modelo conforme o humor lido."""
    h = (s or {}).get("humor")
    if h == "irritado":
        return ("[HUMOR DO CLIENTE: IRRITADO/TENSO — acolha a frustração de forma genuína, seja mais "
                "seco, direto e RESOLUTIVO, foque em resolver, corte emoji em excesso e enrolação. "
                "Se não der pra resolver na hora, encaminhe pro time com prioridade e tranquilize.]")
    if h == "animado":
        return ("[HUMOR DO CLIENTE: ANIMADO/POSITIVO — pode ser caloroso e, se fizer sentido, conduza "
                "pro próximo passo (fechar plano, agendar), aproveitando a boa energia sem forçar.]")
    return ""
