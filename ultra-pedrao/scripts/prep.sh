#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
WS=$(openssl rand -hex 16); AT=$(openssl rand -hex 16)
cat > .env << ENVEOF
FS_JWT_RESPOSTA=
FS_JWT_TRANSFER=
CLAUDE_CODE_OAUTH_TOKEN=
BOT_MODE=shadow
FS_BASE=https://servapi.flowseller.com.br
FS_APIID_RESPOSTA=6eea7327-b544-44c1-b30b-88b5bf1d2df4
FS_APIID_TRANSFER=8db5ece2-bdc1-460c-b986-6203e7cce6cd
FS_WEBHOOK_SECRET=$WS
ADMIN_TOKEN=$AT
PUBLIC_BASE_URL=https://srv1822151.hstgr.cloud
LLM_PROVIDER=claude_cli
LLM_MODEL=claude-haiku-4-5-20251001
GEMINI_API_KEY=
LLM_TIMEOUT=40
DEBOUNCE_SECONDS=6
SO_FORA_DO_HORARIO=true
TZ=America/Sao_Paulo
VIAB_LIMIAR_PREDIO=3
SQLITE_PATH=/app/data/memoria.db
MEM_RETENCAO_DIAS=90
PORT=8080
ENVEOF
echo "======================================================================"
echo " .env pronto. So faltam 3 tokens (as 3 PRIMEIRAS linhas do arquivo)."
echo ""
echo " AGORA rode:   nano .env"
echo ""
echo " No nano, o cursor abre no TOPO. Para cada uma das 3 primeiras linhas:"
echo "   1) va ate o final da linha (depois do = )"
echo "   2) cole o token (Ctrl+Shift+V, ou botao direito > Colar)"
echo "   linha 1  FS_JWT_RESPOSTA=       -> token da 'resposta ia 2'  (eyJ...)"
echo "   linha 2  FS_JWT_TRANSFER=       -> token do 'transfere p suporte' (eyJ...)"
echo "   linha 3  CLAUDE_CODE_OAUTH_TOKEN= -> token do claude_token.txt (sk-ant-oat...)"
echo ""
echo " Salvar: Ctrl+O e Enter.   Sair: Ctrl+X."
echo " Depois rode:   bash scripts/finish.sh"
echo "======================================================================"
