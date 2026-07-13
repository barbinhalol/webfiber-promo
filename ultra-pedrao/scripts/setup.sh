#!/usr/bin/env bash
# Configuração à prova de colagem: desliga bracketed-paste e limpa lixo de cada valor.
set -uo pipefail
cd "$(dirname "$0")/.."
printf '\e[?2004l'                      # desliga o modo colagem que insere ^[[200~
cp -f .env.example .env
clean() { printf '%s' "$1" | tr -d '\r\n' | sed -E 's/\x1b\[20[01]~//g; s/~$//; s/^[[:space:]]+|[[:space:]]+$//g'; }
setv()  { sed -i "s|^$1=.*|$1=$(clean "$2")|" .env; }
echo "== Configuração do Ultra Pedrão =="
echo "Cole cada valor e tecle Enter. O valor APARECE na tela pra você conferir."
echo
read -r -p "1/5  codigo da 'resposta ia 2' (UUID):        " A
read -r -p "2/5  token da 'resposta ia 2' (eyJ...):        " B
read -r -p "3/5  codigo do 'transfere p suporte' (UUID):  " C
read -r -p "4/5  token do 'transfere p suporte' (eyJ...):  " D
read -r -p "5/5  token Claude (sk-ant-oat...):             " E
setv FS_APIID_RESPOSTA      "$A"
setv FS_JWT_RESPOSTA        "$B"
setv FS_APIID_TRANSFER      "$C"
setv FS_JWT_TRANSFER        "$D"
setv CLAUDE_CODE_OAUTH_TOKEN "$E"
setv FS_WEBHOOK_SECRET "$(openssl rand -hex 16)"
setv ADMIN_TOKEN       "$(openssl rand -hex 16)"
setv PUBLIC_BASE_URL   "https://srv1822151.hstgr.cloud"
setv LLM_PROVIDER      "claude_cli"
echo; echo "== Conferindo o que foi salvo (sem mostrar segredo) =="
awk -F= '/^FS_APIID_RESPOSTA=/{print "resposta ia 2 (codigo):", $2}
         /^FS_JWT_RESPOSTA=/{print "resposta ia 2 (token):", (length($2)>20?"OK ("length($2)" chars)":"CURTO/VAZIO!")}
         /^FS_APIID_TRANSFER=/{print "transfere (codigo):", $2}
         /^FS_JWT_TRANSFER=/{print "transfere (token):", (length($2)>20?"OK ("length($2)" chars)":"vazio")}
         /^CLAUDE_CODE_OAUTH_TOKEN=/{print "claude token:", (length($2)>20?"OK ("length($2)" chars)":"CURTO/VAZIO!")}' .env
echo; echo "== Subindo e testando =="
docker compose restart ultra-pedrao >/dev/null 2>&1 || docker compose up -d ultra-pedrao >/dev/null 2>&1
sleep 6
curl -s http://127.0.0.1:8080/health; echo
echo ">> Se apareceu {\"ok\": true...} acima, o cérebro está no ar."
