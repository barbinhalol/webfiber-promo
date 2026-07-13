# -*- coding: utf-8 -*-
"""Testa a extração do payload e os filtros (grupo/própria empresa/duplicado) sem subir o servidor."""
import os, sys
os.environ["LLM_PROVIDER"] = "fake"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import server as SV

def run():
    t = []

    # parse tolerante a variações de payload
    ev = SV._parse_evento({"externalKey": "K1", "contact": {"number": "5521999", "name": "Ana"}, "body": "oi"})
    t.append(("parse básico", ev["external_key"] == "K1" and ev["contato"] == "5521999" and ev["texto"] == "oi"))

    ev2 = SV._parse_evento({"message": {"externalKey": "K2", "body": "ola", "fromMe": True}})
    t.append(("parse aninhado + fromMe", ev2["external_key"] == "K2" and ev2["from_me"] is True))

    ev3 = SV._parse_evento({"externalKey": "K3", "isGroup": True, "body": "x"})
    t.append(("detecta grupo", ev3["is_group"] is True))

    # dedup
    SV._SEEN.clear()
    dup1 = SV._dedup("hash-abc")
    dup2 = SV._dedup("hash-abc")
    t.append(("dedup 1ª vez passa, 2ª bloqueia", dup1 is False and dup2 is True))

    # máscara de telefone
    t.append(("máscara telefone", SV._mask("5521964450618").startswith("5521") and "*" in SV._mask("5521964450618")))

    ok = sum(1 for _, r in t if r)
    for nome, r in t: print(("OK " if r else "XX "), nome)
    print(f"\n{ok}/{len(t)} filtros OK")
    return ok == len(t)

if __name__ == "__main__":
    sys.exit(0 if run() else 1)
