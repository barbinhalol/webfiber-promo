#!/usr/bin/env bash
# Volta o container pra imagem anterior e restaura o último backup do banco.
set -euo pipefail
LAST=$(ls -t data/memoria.db.bak.* 2>/dev/null | head -1 || true)
[ -n "$LAST" ] && cp -f "$LAST" data/memoria.db && echo "==> banco restaurado de $LAST"
docker compose down
docker compose up -d
curl -fsS http://127.0.0.1:8080/health && echo " <= rollback ok"
