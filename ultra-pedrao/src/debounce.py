# -*- coding: utf-8 -*-
"""Agrupamento (debounce) de mensagens picadas por contato.
Quando chegam várias mensagens em sequência, espera uma janela e processa TODAS juntas,
evitando 3 respostas separadas. Em memória (1 processo). Para múltiplos workers, trocar por Redis.
Também guarda um lock por conversa (não processar 2x a mesma conversa em paralelo)."""
import re, threading, time
import config as C

# 25/07 — JANELA ADAPTATIVA. A janela existe pra agrupar mensagem picada ("oi" / "tudo bem?" /
# "queria saber do plano"), mas era cobrada de TODO mundo: quem escreve a frase inteira de uma
# vez também esperava a janela cheia sem motivo. Agora quem claramente TERMINOU de falar é
# atendido quase na hora; só quem parece estar no meio da digitação continua sendo agrupado.
_COMPLETA = re.compile(
    r"[.!?]\s*$|"                                    # terminou com pontuação final
    r"\?\s*$|"                                       # pergunta
    r"^\s*\d[\d.\-/\s]{9,}$|"                        # CPF/CNPJ/protocolo digitado sozinho
    r"[\d.\-/]{11,}\s*$|"                            # frase QUE TERMINA no documento ("meu cpf é 109.766.417-12")
    r"^\s*\d\s*$|"                                   # escolha de menu ("2")
    r"\b(obrigad\w*|valeu|era\s+isso|s[óo]\s+isso|por\s+favor|pfv|pv)\s*[.!]?\s*$", re.I)
# frases curtas e sem pontuação são o caso clássico de "ainda estou digitando"
_MIN_PALAVRAS_COMPLETA = 4

def _parece_completa(texto):
    t = (texto or "").strip()
    if not t:
        return False
    if _COMPLETA.search(t):
        return True
    return len(t.split()) >= _MIN_PALAVRAS_COMPLETA and len(t) >= 25

class Debouncer:
    def __init__(self, janela=None, on_flush=None, janela_curta=None):
        self.janela = janela or C.DEBOUNCE_SECONDS
        # janela para quem já terminou a frase (ajustável por env; nunca maior que a normal)
        self.janela_curta = min(
            float(janela_curta if janela_curta is not None else C.DEBOUNCE_CURTA_S), self.janela)
        self.on_flush = on_flush            # callback(contato, [textos], ctx)
        self._buf = {}                      # contato -> {"msgs":[...], "timer":Timer, "ctx":{}}
        self._locks = {}                    # contato -> Lock
        self._g = threading.Lock()

    def _lock(self, contato):
        with self._g:
            self._locks.setdefault(contato, threading.Lock())
            return self._locks[contato]

    def add(self, contato, texto, ctx=None):
        flush_now = False
        with self._g:
            b = self._buf.get(contato)
            if not b:
                b = {"msgs": [], "ctx": ctx or {}}
                self._buf[contato] = b
            b["msgs"].append(texto)
            if ctx: b["ctx"].update(ctx)
            if b.get("timer"): b["timer"].cancel()
            if len(b["msgs"]) >= C.DEBOUNCE_MAX:
                flush_now = True
            else:
                # frase terminada -> espera só o mínimo (o suficiente pra pegar um "obrigado"
                # colado). Frase pela metade -> janela cheia, pra não responder no meio.
                espera = self.janela_curta if _parece_completa(texto) else self.janela
                t = threading.Timer(espera, self._flush, args=[contato])
                t.daemon = True
                b["timer"] = t
                t.start()
        # _flush tenta readquirir self._g (pop do buffer) -- precisa ser chamado
        # FORA do "with self._g" acima, senao trava (Lock nao e reentrante).
        if flush_now:
            self._flush(contato)

    def _flush(self, contato):
        with self._g:
            b = self._buf.pop(contato, None)
        if not b or not b["msgs"]:
            return
        lock = self._lock(contato)
        with lock:  # serializa por conversa
            texto = "\n".join(b["msgs"])
            if self.on_flush:
                self.on_flush(contato, texto, b["ctx"])
