#!/usr/bin/env bash
# Finaliza: gera segredos que faltam, escolhe cerebro (claude se houver token), sobe e testa.
set -uo pipefail
cd "$(dirname "$0")/.."
val() { grep -E "^$1=" .env | head -1 | cut -d= -f2- | awk '{print $1}'; }
# ADMIN_TOKEN precisa existir (senao status.sh nao le eventos). FS_WEBHOOK_SECRET fica VAZIO de proposito
# no teste (assim a FlowSeller nao precisa mandar header). Geramos so o ADMIN.
[ -z "$(val ADMIN_TOKEN)" ] && sed -i "s|^ADMIN_TOKEN=.*|ADMIN_TOKEN=$(openssl rand -hex 16)|" .env && echo "[ok] ADMIN_TOKEN gerado."
CT=$(val CLAUDE_CODE_OAUTH_TOKEN)
if [ ${#CT} -lt 20 ]; then
  echo "[aviso] sem token do Claude -> cerebro PROVISORIO (fake). Cole depois e rode de novo."
  sed -i 's|^LLM_PROVIDER=.*|LLM_PROVIDER=fake|' .env
else
  sed -i 's|^LLM_PROVIDER=.*|LLM_PROVIDER=claude_cli|' .env
  echo "[ok] cerebro REAL (claude_cli)."
fi
echo "[..] subindo..."; docker compose up -d --build ultra-pedrao >/dev/null 2>&1
sleep 8
H=$(curl -s http://127.0.0.1:8080/health); echo "$H"; echo
if echo "$H" | grep -q '"ok"'; then
  AT=$(val ADMIN_TOKEN)
  echo "============================================================"
  echo "  NO AR."
  echo "  Webhook p/ FlowSeller: https://pedrao.webfiberprovedorcliente.cloud/webhook"
  echo "  Ver decisoes:          bash scripts/status.sh"
  echo "============================================================"
else
  echo "[erro] rode: docker compose logs --tail 30 ultra-pedrao"
fi
