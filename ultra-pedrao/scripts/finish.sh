#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
ok=1
for k in FS_JWT_RESPOSTA CLAUDE_CODE_OAUTH_TOKEN; do
  v=$(grep -E "^$k=" .env | cut -d= -f2-)
  if [ ${#v} -lt 20 ]; then echo "[FALTA] $k parece vazio/curto — rode 'nano .env' e cole o token."; ok=0; fi
done
[ $ok -eq 1 ] || { echo "Corrija e rode 'bash scripts/finish.sh' de novo."; exit 1; }
echo "[1/3] consertando HTTPS..."; bash scripts/fix_https.sh || true
echo "[2/3] subindo o cerebro..."; docker compose up -d --build ultra-pedrao >/dev/null 2>&1
sleep 8
echo "[3/3] testando..."
H=$(curl -s http://127.0.0.1:8080/health)
echo "$H"
echo
if echo "$H" | grep -q '"ok"'; then
  echo "====================================================="
  echo " NO AR (modo sombra). Cole este webhook na FlowSeller:"
  echo "   https://srv1822151.hstgr.cloud/webhook"
  echo " (config 'resposta ia 2' > campo Webhook)"
  echo " Ver decisoes:  bash scripts/status.sh"
  echo "====================================================="
else
  echo "[erro] health nao respondeu. Rode: docker compose logs --tail 30 ultra-pedrao"
fi
