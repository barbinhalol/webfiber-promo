#!/usr/bin/env bash
# Mostra o payload cru mais recente + as ULTIMAS 3 decisoes do cerebro (legivel).
cd "$(dirname "$0")/.."
TOK=$(grep '^ADMIN_TOKEN=' .env | cut -d= -f2 | awk '{print $1}')
curl -s -H "X-Admin-Token: $TOK" "http://127.0.0.1:8080/admin/eventos?limite=400" | python3 -c '
import sys, json
try: e = json.load(sys.stdin)
except Exception: print("(nao consegui ler /admin/eventos — ADMIN_TOKEN certo?)"); sys.exit()
raw = [x for x in e if x.get("tipo")=="webhook_raw"]
dec = [x for x in e if x.get("tipo")=="decisao"]
if raw:
    print("===== ULTIMO PAYLOAD CRU (parser leu) =====")
    print(json.dumps(raw[0].get("payload",{}).get("parser_leu",{}), indent=2, ensure_ascii=False))
print("\n===== ULTIMAS 3 DECISOES DO CEREBRO =====")
if not dec: print("(nenhuma decisao ainda)")
for d in dec[:3]:
    p = d.get("payload",{})
    print("-"*50)
    print("contato:", p.get("mask"), "| acao:", p.get("acao"), "| viab:", p.get("viab"))
    print("render :", p.get("render"))
'
