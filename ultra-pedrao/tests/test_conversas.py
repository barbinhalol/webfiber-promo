# -*- coding: utf-8 -*-
"""Simulador de conversas multi-turno (modo sombra, LLM fake). Valida roteamento, régua de 3
e persistência de memória entre turnos. Imprime a conversa lado a lado com a decisão."""
import os, sys, tempfile
os.environ["LLM_PROVIDER"] = "fake"
os.environ["BOT_MODE"] = "shadow"
os.environ["SQLITE_PATH"] = os.path.join(tempfile.gettempdir(), "up_sim.db")
if os.path.exists(os.environ["SQLITE_PATH"]): os.remove(os.environ["SQLITE_PATH"])
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import brain as B, memory as M
M.init()

CONVERSAS = [
    ("Cliente novo — endereço confirmado (prédio)", "5521900000001", [
        ("oi boa noite", "responder"),
        ("queria uma internet boa", "responder"),
        ("moro na Rua Ubaldino do Amaral 80, é pra trabalhar de casa", "fastreply"),
    ]),
    ("Suporte técnico — sem internet", "5521900000002", [
        ("minha internet caiu desde ontem, luz vermelha", "responder"),
    ]),
    ("Cancelamento", "5521900000003", [
        ("quero cancelar meu plano", "transferir"),
    ]),
    ("Endereço provável (rua conhecida, nº diferente)", "5521900000004", [
        ("vocês atendem na Rua do Rezende 999999?", "responder"),
    ]),
]

def run():
    total = ok = 0
    for titulo, contato, turnos in CONVERSAS:
        print(f"\n=== {titulo} ===")
        for msg, esperado in turnos:
            hist = M.historico(contato)
            fatos = M.get_fatos(contato)
            d = B.decidir(msg, historico=hist, memoria_cliente=fatos)
            M.add_mensagem(contato, "EXT", "cliente", msg)
            if d.get("texto"): M.add_mensagem(contato, "EXT", "pedrao", d["texto"])
            if d.get("dados_coletados"): M.merge_fatos(contato, d["dados_coletados"])
            total += 1
            acao_ok = d["acao"] == esperado
            ok += 1 if acao_ok else 0
            marca = "OK " if acao_ok else "XX "
            print(f"  {marca}Cliente: {msg}")
            print(f"      -> {d.get('_render')}  [viab={d.get('_viabilidade_sistema',{}).get('status')}]")
    print(f"\n{ok}/{total} turnos com ação esperada")
    return ok == total

if __name__ == "__main__":
    sys.exit(0 if run() else 1)
