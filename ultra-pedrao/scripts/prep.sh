#!/usr/bin/env bash
# Monta o .env definitivo, RECUPERANDO tokens que o dono já tenha colado antes (limpa lixo tipo ^V / ^[[200~).
set -euo pipefail
cd "$(dirname "$0")/.."
old() { grep -E "^$1=" .env 2>/dev/null | head -1 | cut -d= -f2-; }
salvage_jwt() { local v="$1"; v="${v#"${v%%eyJ*}"}"; [[ "$v" == eyJ* && ${#v} -gt 40 ]] && printf '%s' "$v" || printf ''; }
salvage_oat() { local v="$1"; v="${v#"${v%%sk-ant*}"}"; [[ "$v" == sk-ant* ]] && printf '%s' "$v" || printf ''; }
JR=$(salvage_jwt "$(old FS_JWT_RESPOSTA)")
JT=$(salvage_jwt "$(old FS_JWT_TRANSFER)")
CT=$(salvage_oat "$(old CLAUDE_CODE_OAUTH_TOKEN)")
WS=$(old FS_WEBHOOK_SECRET); [ ${#WS} -ge 16 ] || WS=$(openssl rand -hex 16)
AT=$(old ADMIN_TOKEN);       [ ${#AT} -ge 16 ] || AT=$(openssl rand -hex 16)
cat > .env << ENVEOF
FS_JWT_RESPOSTA=$JR
FS_JWT_TRANSFER=$JT
CLAUDE_CODE_OAUTH_TOKEN=$CT
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
TRANSCRICAO_PROVIDER=none
LLM_TIMEOUT=40
DEBOUNCE_SECONDS=6
SO_FORA_DO_HORARIO=true
TZ=America/Sao_Paulo
VIAB_LIMIAR_PREDIO=3
SQLITE_PATH=/app/data/memoria.db
MEM_RETENCAO_DIAS=90
PORT=8080
ENVEOF
echo "==================== SITUAÇÃO DOS TOKENS ===================="
[ -n "$JR" ] && echo " token 'resposta ia 2'      : RECUPERADO (${#JR} chars)" || echo " token 'resposta ia 2'      : FALTA (linha 1 do nano)"
[ -n "$JT" ] && echo " token 'transfere p suporte': RECUPERADO (${#JT} chars)" || echo " token 'transfere p suporte': falta (linha 2 — opcional)"
[ -n "$CT" ] && echo " token Claude (sk-ant-oat)  : OK (${#CT} chars)"        || echo " token Claude (sk-ant-oat)  : FALTA (linha 3 do nano)"
echo "============================================================="
echo "Se algo FALTA: rode  nano .env  , cole na linha indicada (depois do =), Ctrl+O Enter Ctrl+X."
echo "Depois rode:  bash scripts/finish.sh"
