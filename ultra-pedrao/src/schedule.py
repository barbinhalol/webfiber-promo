# -*- coding: utf-8 -*-
"""Horário de atendimento humano (America/Sao_Paulo). Define se o Pedrão deve ATUAR agora
(ele atua fora do horário humano, se SO_FORA_DO_HORARIO=true)."""
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("America/Sao_Paulo")
except Exception:
    _TZ = None
import config as C

# janelas humanas padrão (podem virar env/painel depois)
# comercial: seg-sex 9-18 ; técnico: seg-sex 9-20, sáb 9-15 ; dom/feriado: fechado
def _agora():
    return datetime.now(_TZ) if _TZ else datetime.now()

def dentro_horario_humano(dt=None):
    dt = dt or _agora()
    wd = dt.weekday()  # 0=seg ... 6=dom
    h = dt.hour + dt.minute/60
    if wd <= 4:   # seg-sex
        return 9 <= h < 20      # cobre comercial(18) e técnico(20)
    if wd == 5:   # sábado
        return 9 <= h < 15
    return False  # domingo

def deve_atuar(dt=None):
    """True se o Pedrão deve responder agora."""
    if not C.SO_FORA_DO_HORARIO:
        return True
    return not dentro_horario_humano(dt)

def texto_horario():
    return ("Nosso time atende de segunda a sexta, das 9h às 18h no comercial, "
            "e o técnico vai até 20h (sábado até 15h).")
