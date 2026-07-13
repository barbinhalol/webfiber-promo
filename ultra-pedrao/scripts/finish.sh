#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
JR=$(grep -E '^FS_JWT_RESPOSTA=' .env | cut -d= -f2-)
CT=$(grep -E '^CLAUDE_CODE_OAUTH_TOKEN=' .env | cut -d= -f2-)
[ ${#JR} -lt 40 ] && echo "[ATENÇÃO] token da 'resposta ia 2' ainda falta (nano .env, linha 1) — sigo mesmo assim (sombra não envia nada)."
if [ ${#CT} -lt 20 ]; then
  echo "[ATENÇÃO] sem token do Claude — subindo com cérebro PROVISÓRIO (respostas de treino). Cole depois e rode este script de novo."
  sed -i 's|^LLM_PROVIDER=.*|LLM_PROVIDER=fake|' .env
else
  sed -i 's|^LLM_PROVIDER=.*|LLM_PROVIDER=claude_cli|' .env
fi
echo "[1/3] HTTPS..."; bash scripts/fix_https.sh || true
echo "[2/3] subindo o cérebro..."; docker compose up -d --build ultra-pedrao >/dev/null 2>&1
sleep 8
echo "[3/3] testando..."
H=$(curl -s http://127.0.0.1:8080/health); echo "$H"; echo
if echo "$H" | grep -q '"ok"'; then
  echo "==========================================================="
  echo "  NO AR (modo sombra — não envia nada ao cliente)."
  echo "  Webhook p/ FlowSeller:  https://srv1822151.hstgr.cloud/webhook"
  echo "  Ver decisões:           bash scripts/status.sh"
  echo "==========================================================="
else
  echo "[erro] rode: docker compose logs --tail 30 ultra-pedrao   e mande o print"
fi
