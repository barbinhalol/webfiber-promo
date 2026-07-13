# -*- coding: utf-8 -*-
"""Respostas prontas reproduzidas (a API externa não dispara fastReply por ID).
Reproduzimos o conteúdo real dos atalhos da FlowSeller — com *negrito* (asterisco = WhatsApp)
para dar relevância, exatamente como o /planos configurado. Texto fixo = instantâneo (sem LLM)."""
import os
import config as C

HERE = os.path.dirname(os.path.abspath(__file__))
PLANOS_DIR = os.path.join(HERE, "..", "data", "planos")

def _planos_imagens():
    """URLs das 3 imagens do /planos. Ordem de prioridade:
    1) env PLANOS_IMAGENS (lista explícita de URLs);
    2) arquivos em data/planos/ servidos pela própria VPS (PUBLIC_BASE_URL) — tudo num lugar só."""
    env = [u.strip() for u in os.environ.get("PLANOS_IMAGENS", "").split(",") if u.strip()]
    if env:
        return env
    if C.PUBLIC_BASE_URL and os.path.isdir(PLANOS_DIR):
        arqs = sorted(f for f in os.listdir(PLANOS_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")))
        return [f"{C.PUBLIC_BASE_URL}/planos/{f}" for f in arqs]
    return []

# Texto oficial do /planos — EXATAMENTE como o atendimento humano envia (asteriscos = negrito no WhatsApp)
PLANOS_TEXTO = (
    "Esses são os nossos planos residenciais disponíveis atualmente 😊\n"
    "▪︎*700MB → Ideal para uso do dia a dia, como TV, celulares, filmes e navegação comum*.\n"
    "⚠️ Este plano não inclui canais e streamings.\n\n"
    "▪︎*850MB → Recomendado para casas com mais pessoas conectadas, home office, jogos, streaming e uso mais intenso* (canais basicos AO VIVO)\n"
    "Incluso cortesia de canais + streamings.\n\n"
    "▪︎*1GB→ Nosso plano mais completo, indicado para alto desempenho, muitos dispositivos conectados e máxima estabilidade*.\n"
    "Incluso cortesia de canais + streamings.\n\n"
    "📺 *Os streamings permitem acesso em até 4 telas simultâneas* e são compatíveis com smart TVs, celulares e tablets.\n\n"
    "⚠️ Importante: os aplicativos dos streamings dependem da compatibilidade da SMART TV"
)

# Fichas e textos reproduzidos (fonte: prints das mensagens rápidas da FlowSeller)
CADASTRO_RESIDENCIAL = (
    "*FICHA DE CADASTRO RESIDENCIAL* 🏠\n"
    "• Nome completo:\n• CPF:\n• Endereço completo:\n• Complemento:\n• E-mail:\n"
    "• Data de vencimento: ( )7  ( )17\n• Telefone:\n• Plano desejado:\n"
    "• Instalação/ativação: R$100,00 ( ) PIX  ou  ( ) R$130,00 em 3x no cartão"
)

def planos_payloads(external_key, legenda=None):
    """Devolve a sequência de envios do /planos: 1 texto + N imagens (como o atalho manda tudo de uma vez)."""
    imgs = _planos_imagens()
    envios = [{"tipo": "texto", "externalKey": external_key, "text": (legenda + "\n\n" if legenda else "") + PLANOS_TEXTO}]
    for url in imgs:
        envios.append({"tipo": "midia", "externalKey": external_key, "mediaUrl": url})
    if not imgs:
        envios.append({"tipo": "_aviso", "detalhe": "sem imagens — ponha os 3 arquivos em data/planos/ e defina PUBLIC_BASE_URL, ou use PLANOS_IMAGENS"})
    return envios
