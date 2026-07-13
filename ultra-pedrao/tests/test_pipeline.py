# -*- coding: utf-8 -*-
"""Pipeline ponta-a-ponta em modo sombra com LLM fake (sem rede)."""
import os, sys
os.environ["LLM_PROVIDER"] = "fake"
os.environ["BOT_MODE"] = "shadow"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import brain as B, flowseller as FS

def run():
    casos = [
        ("oi boa noite", "responder"),
        ("moro na Rua Ubaldino do Amaral 80, é pra home office", "fastreply"),
        ("quero cancelar meu plano", "transferir"),
        ("minha internet caiu, luz vermelha", "responder"),
    ]
    ok = 0
    for texto, esp in casos:
        d = B.decidir(texto)
        r = FS.executar_decisao("EXT-TESTE", d)
        acao_ok = d["acao"] == esp
        shadow_ok = (r.get("enviado") is False and r.get("modo") == "shadow")
        marca = "OK " if (acao_ok and shadow_ok) else "XX "
        if acao_ok and shadow_ok: ok += 1
        print(f"{marca} '{texto[:40]}' -> acao={d['acao']} viab={d.get('_viabilidade_sistema',{}).get('status')} "
              f"| shadow={shadow_ok} | {d.get('_render')}")
        if d.get("_alertas"): print("      alertas:", d["_alertas"])
    # guard: garante que NADA foi enviado em shadow
    print(f"\n{ok}/{len(casos)} casos OK (ação esperada + nada enviado em shadow)")
    return ok == len(casos)

if __name__ == "__main__":
    sys.exit(0 if run() else 1)
