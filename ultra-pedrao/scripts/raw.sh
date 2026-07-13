#!/usr/bin/env bash
# Mostra, de forma legível, o payload CRU mais recente da FlowSeller + a decisão mais recente do cérebro.
cd "$(dirname "$0")/.."
TOK=$(grep '^ADMIN_TOKEN=' .env | cut -d= -f2 | awk '{print $1}')
DATA=$(curl -s -H "X-Admin-Token: $TOK" "http://127.0.0.1:8080/admin/eventos?limite=400")
echo "$DATA" | python3 -c '
import sys, json
try: e = json.load(sys.stdin)
except Exception: print("(nao consegui ler /admin/eventos — ADMIN_TOKEN certo?)"); sys.exit()
raw = [x for x in e if x.get("tipo")=="webhook_raw"]
dec = [x for x in e if x.get("tipo")=="decisao"]
if raw:
    print("===== PAYLOAD CRU DA FLOWSELLER (mais recente) =====")
    print(json.dumps(raw[0].get("payload",{}).get("raw",{}), indent=2, ensure_ascii=False)[:3500])
    print("\n----- como o parser leu -----")
    print(json.dumps(raw[0].get("payload",{}).get("parser_leu",{}), indent=2, ensure_ascii=False))
else:
    print("(sem webhook_raw ainda — confirme DEBUG_WEBHOOK=true e mande UMA mensagem NOVA)")
if dec:
    print("\n===== DECISAO DO CEREBRO (mais recente) =====")
    print(json.dumps(dec[0].get("payload",{}), indent=2, ensure_ascii=False)[:2500])
'
