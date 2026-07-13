#!/usr/bin/env bash
# Instalação do Ultra Pedrão (VPS Hostinger). Uso: bash scripts/install.sh
set -euo pipefail
cd "$(dirname "$0")/.."
echo "==> Ultra Pedrão :: instalação"
if [ ! -f data/enderecos.json ]; then
  read -r -s -p "Senha do pacote de dados (fornecida no chat): " UP_PASS; echo
  openssl enc -d -aes-256-cbc -pbkdf2 -in data/privado.tar.gz.enc -pass pass:"$UP_PASS" | tar -xzf -
  echo "==> dados decriptados"
fi
command -v docker >/dev/null 2>&1 || { echo "==> instalando Docker..."; curl -fsSL https://get.docker.com | sh; }
[ -f .env ] || { cp .env.example .env; echo "==> .env criado — rode: nano .env  (tokens) e depois: docker compose restart"; }
docker compose up -d --build
sleep 8; curl -fsS http://127.0.0.1:8080/health && echo "" && echo "==> NO AR (modo sombra). Edite o .env e rode 'docker compose restart ultra-pedrao'."
