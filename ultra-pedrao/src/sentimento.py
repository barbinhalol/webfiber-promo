# -*- coding: utf-8 -*-
"""Leitura de sentimento/humor do cliente por CÓDIGO (sem LLM — roda até no fastpath, custo zero).
Serve pra: (a) adaptar o tom do Pedrão, (b) sinalizar escalada quando a temperatura sobe,
(c) mostrar um semáforo 🟢🟡🔴 no painel do dono. É um sinal simples e rápido; a nuance fina
continua com o modelo, mas isso garante que ninguém furioso passe batido."""
import re

# fúria / risco (vermelho) — jurídico, ameaça, xingamento, desistência.
# Sinais REAIS minerados de 16 mil msgs de cliente (conhecimento_conversas.md, seção 4).
_FURIA = re.compile(
    # 24/07: stems tipo "irritad\b" NUNCA batiam — em português o adjetivo sempre continua com
    # a vogal de gênero (irritad+a/o), e o \b logo depois do stem exige que a palavra TERMINE ali.
    # Resultado: quem escrevesse literalmente "estou irritada"/"o advogado vai ver isso" passava
    # batido pelo detector. Trocado \b final por \w* nesses stems (cobre a/o/as/os/inha etc.).
    r"\b(procon|advogad\w*|process(o|ar|ei)|justi[çc]a|c[oó]digo de defesa|absurdo|desca(so|rado)|"
    r"verg(onha|onhoso)|palha[çc]ada|cansei|enchei o saco|p[ée]ssimo|horr[íi]vel|lixo|merda|"
    r"porcaria|revoltad\w*|indignad\w*|nunca mais|cancel(ar|amento|a minha)|reclama[çc]|[óo]dio|"
    r"irritad\w*|puto|inadmiss[íi]vel|rid[íi]cul\w*|descaso|golpe|enrola[çr]|palha[çc]o|"
    r"n[ãa]o aguento|t[oô]\s+cansad\w*|me engana|"
    # ameaça de trocar de operadora (mata-lead / churn real)
    r"vou (pra|para|fazer com|assinar|mudar pra|contratar) (a |o )?(claro|vivo|oi|tim|desktop|net|concorr)|"
    r"vou encerrar (meu|o|a)|vou informar (aos|os) (outros|interessad\w*)|"
    # cliente abandonado no loop do bot (grande fonte de atrito real)
    r"algu[ée]m (pode|vai|consegue)?\s*(responder|atender|me atender|me ajudar|a[íi])|"
    r"tem algu[ée]m (a[íi]|ai)|(oi\?|ol[áa]\?)\s*$|"
    # cobrança do que já pagou (top reclamação financeira)
    r"j[áa] (foi )?pag(o|uei).*(cobra|cobran)|cobrando.*(j[áa] paguei|que paguei))\b", re.I)
# gritaria em CAPS conta como irritação (sinal real: "CAPS/!!")
_CAPS = re.compile(r"[A-ZÀ-Ú]{5,}")
# positivo / caloroso (verde) — satisfação, intenção de fechar
_POSITIVO = re.compile(
    r"\b(obrigad\w*|valeu|agrade[çc]|show|top|maravilh|ador(ei|o)|amei|excelente|perfeito|"
    r"[óo]timo|muito bom|gratid\w*|abra[çc]o|parab[ée]ns|quero sim|fech(ar|ado|a comigo)|"
    r"bora|massa|joia|adorei|que bom|voc[êe]s s[ãa]o [óo]timos|salvou|top demais)\b", re.I)

def _grita(texto):
    """CAPS + excesso de '!!' = gritaria (sinal real de irritação)."""
    t = texto or ""
    if t.count("!") >= 2:
        return True
    letras = [c for c in t if c.isalpha()]
    return len(letras) >= 8 and sum(1 for c in letras if c.isupper()) / len(letras) > 0.7

def classificar(texto, contexto=""):
    """Retorna {'humor','temp'(0-3),'cor'}. temp>=3 = quente/vermelho (priorizar humano)."""
    t = (texto or "") + " " + (contexto or "")
    if _FURIA.search(t) or _grita(texto or ""):
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
