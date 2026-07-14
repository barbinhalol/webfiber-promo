# -*- coding: utf-8 -*-
"""Agrupamento (debounce) de mensagens picadas por contato.
Quando chegam várias mensagens em sequência, espera uma janela e processa TODAS juntas,
evitando 3 respostas separadas. Em memória (1 processo). Para múltiplos workers, trocar por Redis.
Também guarda um lock por conversa (não processar 2x a mesma conversa em paralelo)."""
import threading, time
import config as C

class Debouncer:
    def __init__(self, janela=None, on_flush=None):
        self.janela = janela or C.DEBOUNCE_SECONDS
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
                t = threading.Timer(self.janela, self._flush, args=[contato])
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
