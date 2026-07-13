#!/usr/bin/env bash
# Aplica o novo prompt-mestre (v3) do Ultra Pedrao. Uso: bash scripts/novo_cerebro.sh <SENHA_DO_PACOTE>
set -euo pipefail
cd "$(dirname "$0")/.."
PASS="${1:-}"
[ -z "$PASS" ] && { echo "uso: bash scripts/novo_cerebro.sh <senha do pacote>"; exit 1; }
[ -f data/pedrao_prompt.md ] && cp -f data/pedrao_prompt.md "data/pedrao_prompt.md.bak.$(date +%s)"
openssl enc -d -aes-256-cbc -pbkdf2 -in data/pedrao_prompt.md.enc -pass pass:"$PASS" -out data/pedrao_prompt.md
echo "[ok] prompt novo aplicado ($(wc -l < data/pedrao_prompt.md) linhas). Rebuild..."
docker compose up -d --build ultra-pedrao >/dev/null 2>&1
sleep 8
curl -s http://127.0.0.1:8080/health && echo && echo "[ok] Ultra Pedrao no ar com o cerebro v3 (modo sombra)."
