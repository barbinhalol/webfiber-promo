#!/usr/bin/env bash
# Ativa HTTPS (certificado gratis) no dominio informado. Uso: bash scripts/dominio.sh SEU.DOMINIO
set -uo pipefail
cd "$(dirname "$0")/.."
DOM="${1:-}"
[ -z "$DOM" ] && { echo "uso: bash scripts/dominio.sh pedrao.webfiberprovedorcliente.cloud"; exit 1; }
IP=$(curl -s https://api.ipify.org || echo "?")
RES=$(getent hosts "$DOM" | awk '{print $1}' | head -1)
echo "IP da VPS: $IP  |  $DOM aponta para: ${RES:-nada}"
if [ "$RES" != "$IP" ]; then
  echo "[PARE] O dominio ainda NAO aponta pra esta VPS."
  echo " No painel Hostinger > Dominios > $DOM > Gerenciar DNS, crie um registro:"
  echo "   Tipo A   |   Nome/Host: ${DOM%%.*}   |   Aponta para: $IP   |   TTL padrao"
  echo " Espere uns minutos e rode este comando de novo."
  exit 1
fi
apt-get install -y -qq certbot python3-certbot-nginx >/dev/null 2>&1 || true
cat > /etc/nginx/sites-available/ultra-pedrao.conf <<NG
server {
    listen 80;
    server_name $DOM;
    location / { proxy_pass http://127.0.0.1:8080; proxy_set_header Host \$host; proxy_set_header X-Forwarded-Proto \$scheme; }
}
NG
ln -sf ../sites-available/ultra-pedrao.conf /etc/nginx/sites-enabled/ultra-pedrao.conf
nginx -t >/dev/null 2>&1 && systemctl reload nginx
certbot --nginx -d "$DOM" --non-interactive --agree-tos -m marketingwebfiber@gmail.com --redirect \
  && sed -i "s|^PUBLIC_BASE_URL=.*|PUBLIC_BASE_URL=https://$DOM|" .env \
  && docker compose restart ultra-pedrao >/dev/null 2>&1 \
  && echo "==================================================" \
  && echo " HTTPS OK. Novo webhook p/ FlowSeller:" \
  && echo "   https://$DOM/webhook" \
  && echo "==================================================" \
  && curl -s "https://$DOM/health" && echo \
  || echo "[erro no certificado] me mande as ultimas linhas que apareceram."
