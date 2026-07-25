# -*- coding: utf-8 -*-
"""Configuração central — tudo por variável de ambiente (nada de segredo no código)."""
import os, re

def _b(v, d=False):
    return str(os.environ.get(v, str(d))).strip().lower() in ("1", "true", "yes", "on", "sim")

def _i(v, d):
    try: return int(os.environ.get(v, d))
    except Exception: return d

def _segredo(v):
    """Env de segredo: alguns parsers de .env entregam o comentário inline ('X=   # dica')
    como parte do valor — o que vira um 'segredo fantasma' e bloqueia tudo com 401.
    Corta o comentário e espaços; segredo real nunca contém '#'."""
    s = os.environ.get(v, "")
    return s.split("#", 1)[0].strip()

# ---------------- MODO DE OPERAÇÃO ----------------
# shadow  = recebe, decide, NÃO envia (só registra o que faria) — padrão seguro
# pilot   = envia SÓ para os números da allowlist (equipe/teste)
# live    = envia para todos (só com decisão explícita do dono)
BOT_MODE = os.environ.get("BOT_MODE", "shadow").strip().lower()
PILOT_ALLOWLIST = [n.strip() for n in os.environ.get("PILOT_ALLOWLIST", "").split(",") if n.strip()]

# ---------------- FLAGS DE TESTE/VALIDAÇÃO (temporárias) ----------------
# DEBUG_WEBHOOK: registra o payload CRU que a FlowSeller manda (pra confirmar/ajustar o parser).
#   Use só durante o teste com a SUA própria mensagem; desligue depois (evita guardar dados de cliente).
DEBUG_WEBHOOK = str(os.environ.get("DEBUG_WEBHOOK", "false")).strip().lower() in ("1", "true", "yes", "sim", "on")
# FORCAR_ATUACAO: ignora o gate de horário pra ver a decisão completa do cérebro AGORA (continua shadow, não envia).
FORCAR_ATUACAO = str(os.environ.get("FORCAR_ATUACAO", "false")).strip().lower() in ("1", "true", "yes", "sim", "on")
# TESTE_SO_NUMERO: se preenchido, o Pedrão processa SÓ mensagens desse número (ignora todo o resto).
#   Use nos testes pra não rodar o cérebro em cima do movimento de produção. Vazio = processa todos.
TESTE_SO_NUMERO = [re.sub(r"\D", "", n) for n in os.environ.get("TESTE_SO_NUMERO", "").split(",") if n.strip()]

# ---------------- FLOWSELLER (API externa) ----------------
FS_BASE = os.environ.get("FS_BASE", "https://servapi.flowseller.com.br")
# apiId (UUID) + JWT de cada config da tela API/Webhook. NUNCA commitar valores reais.
FS_APIID_RESPOSTA = os.environ.get("FS_APIID_RESPOSTA", "")   # config "resposta ia" (manter aberto)
FS_JWT_RESPOSTA   = os.environ.get("FS_JWT_RESPOSTA", "")
FS_APIID_TRANSFER = os.environ.get("FS_APIID_TRANSFER", "")   # config "transfere p suporte" (opcional)
FS_JWT_TRANSFER   = os.environ.get("FS_JWT_TRANSFER", "")
# segredo que a FlowSeller manda no webhook de entrada (validação de origem) — a confirmar no 1º payload
FS_WEBHOOK_SECRET = _segredo("FS_WEBHOOK_SECRET")

# Filas (queueId) e departamentos — reaproveitados da API interna já mapeada
FILAS = {"comercial": 23, "suporte": 24, "financeiro": 25, "atendimento": 112, "outros": 26}

# ---------------- IA / LLM ----------------
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic").strip().lower()  # anthropic | openai | gemini | claude_cli | fake
LLM_MODEL = os.environ.get("LLM_MODEL", "claude-haiku-4-5-20251001")
# modelo "pensante" p/ casos complexos (cliente irritado, empresa/PJ, conversa longa, negociação):
# o brain escala Haiku -> Sonnet 5 automaticamente nesses casos (ordem do dono 23/07/2026)
LLM_MODEL_SMART = os.environ.get("LLM_MODEL_SMART", "claude-sonnet-5")
# ESFORÇO do modelo esperto. O Sonnet 5 liga "adaptive thinking" sozinho e roda em effort=high
# por padrão -- medido em 25/07: 14,5s por resposta e ~1000 tokens de saída (a maior parte
# pensamento invisível), mesmo com o cache quente. Num WhatsApp isso parece que o bot morreu.
# "low" mantém a escalada valendo a pena (modelo melhor nos casos difíceis) sem o pensamento
# longo que o prompt do Pedrão -- já estruturado e com roteiro -- não precisa.
LLM_EFFORT_SMART = os.environ.get("LLM_EFFORT_SMART", "low").strip().lower()
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
LLM_TIMEOUT = _i("LLM_TIMEOUT", 40)

# URL pública da própria VPS (pra servir as imagens do /planos localmente — tudo num lugar só)
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")

# ---------------- DEBOUNCE / AGRUPAMENTO ----------------
DEBOUNCE_SECONDS = _i("DEBOUNCE_SECONDS", 6)   # janela p/ agrupar msgs picadas (3–8s)
# janela curta: quando a mensagem já parece uma frase TERMINADA (pontuação final, CPF, escolha
# de menu), não faz sentido cobrar a janela inteira de quem não vai digitar mais nada.
DEBOUNCE_CURTA_S = float(os.environ.get("DEBOUNCE_CURTA_S", "0.8"))
DEBOUNCE_MAX = _i("DEBOUNCE_MAX", 20)          # teto de msgs agrupadas

# ---------------- HORÁRIO (America/Sao_Paulo) ----------------
TZ = os.environ.get("TZ", "America/Sao_Paulo")
HORARIO_COMERCIAL = os.environ.get("HORARIO_COMERCIAL", "seg-sex 9-18")
HORARIO_TECNICO = os.environ.get("HORARIO_TECNICO", "seg-sex 9-20; sab 9-15")
# Se true, o bot só atua FORA do horário humano (comportamento do Pedrão). Se false, atua sempre.
SO_FORA_DO_HORARIO = _b("SO_FORA_DO_HORARIO", True)

# ---------------- MEMÓRIA / BANCO ----------------
DB_URL = os.environ.get("DB_URL", "")  # postgres://...  (vazio = usa SQLite local)
SQLITE_PATH = os.environ.get("SQLITE_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "memoria.db"))
MEM_MSGS_JANELA = _i("MEM_MSGS_JANELA", 24)     # nº de msgs recentes no contexto (subiu 12->24: cache barateia o input)
MEM_RESUMO_APOS = _i("MEM_RESUMO_APOS", 16)     # resume a conversa depois de N msgs
MEM_RETENCAO_DIAS = _i("MEM_RETENCAO_DIAS", 90) # LGPD: expurgo

# ---------------- SERVIDOR ----------------
PORT = _i("PORT", 8080)
ADMIN_TOKEN = _segredo("ADMIN_TOKEN")   # protege /admin/* (scripts)
PAINEL_SENHA = _segredo("PAINEL_SENHA")  # senha amigável do painel web (opcional)

def resumo_seguro() -> dict:
    """Config visível em /health SEM vazar segredo."""
    return {
        "bot_mode": BOT_MODE,
        "llm_provider": LLM_PROVIDER,
        "llm_model": LLM_MODEL,
        "debounce_s": DEBOUNCE_SECONDS,
        "so_fora_do_horario": SO_FORA_DO_HORARIO,
        "tz": TZ,
        "flowseller_config": {
            "resposta": bool(FS_APIID_RESPOSTA and FS_JWT_RESPOSTA),
            "transfer": bool(FS_APIID_TRANSFER and FS_JWT_TRANSFER),
            "webhook_secret": bool(FS_WEBHOOK_SECRET),
        },
        "llm_key": bool(ANTHROPIC_API_KEY or OPENAI_API_KEY or GEMINI_API_KEY),
        "pilot_allowlist_n": len(PILOT_ALLOWLIST),
    }
