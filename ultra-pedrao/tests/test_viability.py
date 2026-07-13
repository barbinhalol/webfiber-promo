# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import viability as V

def run():
    casos = [
        # (texto, status esperado)
        ("moro na Rua Ubaldino do Amaral, 80, é pra home office", V.CONFIRMADA_PREDIO),
        ("Rua Carlos de Carvalho 34", V.CONFIRMADA_PREDIO),
        ("Rua do Rezende 119 centro", V.CONFIRMADA_PREDIO),   # testa REZENDE->RESENDE
        ("Av. Henrique Valadares, 17", V.CONFIRMADA_PREDIO),
        ("é na rua ubaldino do amaral numero 5", V.PROVAVEL), # rua existe, nº com <3
        ("Rua das Acácias 80, Realengo, pega aí?", V.FORA_BASE),
        ("oi boa noite quanto custa", V.SEM_ENDERECO),
        ("quero plano na tijuca", V.SEM_ENDERECO),            # bairro sem rua/número
    ]
    ok = 0
    for texto, esperado in casos:
        v = V.checar(texto)
        got = v["status"]
        marca = "OK " if got == esperado else "XX "
        if got == esperado: ok += 1
        print(f"{marca} esperado={esperado:18} got={got:18} | {texto[:45]!r} -> {v['evidencia']}")
    print(f"\n{ok}/{len(casos)} casos OK")
    return ok == len(casos)

if __name__ == "__main__":
    sys.exit(0 if run() else 1)
