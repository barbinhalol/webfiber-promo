#!/usr/bin/env bash
cd "$(dirname "$0")/.."
TOK=$(grep '^ADMIN_TOKEN=' .env | cut -d= -f2)
echo "== SAÚDE ==" && curl -s http://127.0.0.1:8080/health && echo
echo "== ÚLTIMOS EVENTOS (o que o Pedrão faria) ==" && curl -s -H "X-Admin-Token: $TOK" http://127.0.0.1:8080/admin/eventos
echo
