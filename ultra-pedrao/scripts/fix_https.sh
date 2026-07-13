#!/usr/bin/env bash
# Resolve o HTTPS automaticamente conforme o que já ocupa as portas 80/443 nesta VPS.
set -uo pipefail
cd "$(dirname "$0")/.."
DOMAIN="${1:-srv1822151.hstgr.cloud}"
EMAIL="${2:-marketingwebfiber@gmail.com}"
docker compose up -d ultra-pedrao >/dev/null 2>&1
OCC80=$(ss -tlnp 2>/dev/null | awk '$4 ~ /:80$/  {print; exit}')
OCC443=$(ss -tlnp 2>/dev/null | awk '$4 ~ /:443$/ {print; exit}')
if [ -z "$OCC80" ] && [ -z "$OCC443" ]; then
  docker compose up -d caddy && echo "[OK] HTTPS pelo Caddy (80+443 livres)" && exit 0
fi
if [ -z "$OCC443" ]; then
  sed -i 's/ports: \["80:80", "443:443"\]/ports: ["443:443"]/' docker-compose.yml
  docker compose up -d caddy && echo "[OK] HTTPS pelo Caddy só na 443 (80 estava ocupada)" && exit 0
fi
if echo "$OCC80 $OCC443" | grep -qi nginx && command -v nginx >/dev/null 2>&1; then
  apt-get install -y -qq certbot python3-certbot-nginx >/dev/null 2>&1 || true
  cat > /etc/nginx/sites-available/ultra-pedrao.conf <<NG
server {
    listen 80;
    server_name $DOMAIN;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NG
  ln -sf ../sites-available/ultra-pedrao.conf /etc/nginx/sites-enabled/ultra-pedrao.conf
  nginx -t >/dev/null 2>&1 && systemctl reload nginx
  certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL" --redirect >/dev/null 2>&1 \
    && echo "[OK] HTTPS pelo nginx existente + certificado emitido" && exit 0
  echo "[PARCIAL] nginx encaminhando na porta 80 (certificado falhou — me mande esta linha no chat)"; exit 0
fi
echo "[PRECISO DE VOCÊ] Portas 80/443 ocupadas por outro programa. Cole esta saída no chat:"
ss -tlnp | grep -E ':(80|443) '
