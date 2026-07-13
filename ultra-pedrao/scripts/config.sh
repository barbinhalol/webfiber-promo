#!/usr/bin/env bash
# Preenche o .env perguntando um valor por vez (Enter mantém o que já está).
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || cp .env.example .env
ask() { # var, pergunta, s=oculto
  local var="$1" q="$2" sec="${3:-}" v cur
  cur=$(grep -E "^${var}=" .env | head -1 | cut -d= -f2-)
  [ -n "$cur" ] && q="$q (Enter mantém o atual)"
  if [ "$sec" = "s" ]; then read -r -s -p "$q: " v; echo; else read -r -p "$q: " v; fi
  [ -n "$v" ] && sed -i "s|^${var}=.*|${var}=${v}|" .env
  return 0
}
echo "== Configuração do Ultra Pedrão =="
ask FS_APIID_RESPOSTA  "1/5 Código da config 'resposta ia 2' (o que vem depois de /external/ na URL)"
ask FS_JWT_RESPOSTA    "2/5 Token longo (eyJhb...) da config 'resposta ia 2'" s
ask FS_APIID_TRANSFER  "3/5 Código da config 'Pedrão transfere p suporte' (ou Enter p/ pular)"
ask FS_JWT_TRANSFER    "4/5 Token da config de transferência (ou Enter p/ pular)" s
ask CLAUDE_CODE_OAUTH_TOKEN "5/5 Token Claude de 1 ano (sk-ant-oat..., do arquivo claude_token.txt)" s
grep -qE '^FS_WEBHOOK_SECRET=.+' .env || sed -i "s|^FS_WEBHOOK_SECRET=.*|FS_WEBHOOK_SECRET=$(openssl rand -hex 16)|" .env
grep -qE '^ADMIN_TOKEN=.+' .env      || sed -i "s|^ADMIN_TOKEN=.*|ADMIN_TOKEN=$(openssl rand -hex 16)|" .env
sed -i "s|^PUBLIC_BASE_URL=.*|PUBLIC_BASE_URL=https://srv1822151.hstgr.cloud|" .env
sed -i "s|^LLM_PROVIDER=.*|LLM_PROVIDER=claude_cli|" .env
docker compose restart ultra-pedrao >/dev/null 2>&1 || docker compose up -d ultra-pedrao
sleep 6
echo "== RESULTADO =="
curl -s http://127.0.0.1:8080/health || echo "(health não respondeu — rode: docker compose logs --tail 20 ultra-pedrao)"
echo
echo ">> Webhook p/ colar na FlowSeller:  https://srv1822151.hstgr.cloud/webhook"
echo ">> Guarde o ADMIN_TOKEN:            $(grep '^ADMIN_TOKEN=' .env | cut -d= -f2)"
