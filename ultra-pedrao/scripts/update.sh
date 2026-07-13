#!/usr/bin/env bash
set -euo pipefail
echo "==> backup do banco antes de atualizar"; cp -f data/memoria.db "data/memoria.db.bak.$(date +%s)" 2>/dev/null || true
git pull --ff-only 2>/dev/null || echo "(sem git; suba os arquivos novos manualmente)"
docker compose up -d --build
sleep 3; curl -fsS http://127.0.0.1:8080/health && echo " <= atualizado"
