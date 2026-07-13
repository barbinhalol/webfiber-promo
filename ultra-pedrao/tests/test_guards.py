# -*- coding: utf-8 -*-
"""Testa os GUARDS de código forçando o modelo a devolver JSON ruim (monkeypatch do llm)."""
import os, sys, json
os.environ["LLM_PROVIDER"] = "fake"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import llm as L
import brain as B

def _fixar(resp_json):
    B.L.gerar = lambda system, user: json.dumps(resp_json)

def run():
    testes = []

    # 1) preço digitado em texto -> bloqueado
    _fixar({"acao": "responder", "texto": "O plano 700 custa R$ 99,90 pra você", "intencao": "preco"})
    d = B.decidir("quanto custa?")
    testes.append(("preço digitado bloqueado", "R$" not in d["texto"] and any("preço" in a.lower() for a in d["_alertas"])))

    # 2) placeholder não resolvido -> removido
    _fixar({"acao": "responder", "texto": "Show, [nome]! Seu plano [plano] é ótimo", "intencao": "contratar"})
    d = B.decidir("quero contratar")
    testes.append(("placeholder removido", "[" not in d["texto"]))

    # 3) fastReplyId inválido -> vira transferência comercial
    _fixar({"acao": "fastreply", "fastReplyId": 9999, "intencao": "preco"})
    d = B.decidir("me manda os planos")
    testes.append(("fastReply inválido -> transfere 23", d["acao"] == "transferir" and d["fila"] == 23))

    # 4) modelo afirma cobertura sem o sistema confirmar -> rebaixa
    _fixar({"acao": "responder", "texto": "Atendemos sim no seu endereço!", "viabilidade": "confirmada_predio", "intencao": "viabilidade"})
    d = B.decidir("moro na Rua Inventada das Flores 12345")
    testes.append(("cobertura sem veredito rebaixada", d["viabilidade"] != "confirmada_predio" and "atendemos sim" not in d["texto"].lower()))

    # 5) fila inválida em transferência -> deduz pela intenção (suporte)
    _fixar({"acao": "transferir", "fila": 777, "intencao": "suporte", "motivo": "internet caiu"})
    d = B.decidir("tô sem internet")
    testes.append(("fila inválida deduzida p/ suporte", d["fila"] == 24))

    # 6) confirma cobertura QUANDO o sistema confirma (não deve rebaixar)
    _fixar({"acao": "fastreply", "fastReplyId": 1296, "viabilidade": "confirmada_predio", "intencao": "viabilidade"})
    d = B.decidir("Rua Ubaldino do Amaral 80")
    testes.append(("cobertura real mantida", d["viabilidade"] == "confirmada_predio" and d["acao"] == "fastreply"))

    ok = sum(1 for _, r in testes if r)
    for nome, r in testes:
        print(("OK " if r else "XX "), nome)
    print(f"\n{ok}/{len(testes)} guards OK")
    return ok == len(testes)

if __name__ == "__main__":
    sys.exit(0 if run() else 1)
