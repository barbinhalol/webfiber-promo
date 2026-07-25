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

_DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira",
         "sábado", "domingo"]

def proximo_atendimento(dt=None, setor="suporte"):
    """QUANDO a equipe volta, em português, calculado de verdade (não pelo modelo).
    A regra 5b ('nunca diga só próximo dia útil, diga O DIA') vivia só no prompt -- ou seja,
    dependia do LLM acertar a conta. Agora é código: qualquer texto do bot usa isto.
    suporte: seg-sex 9-20, sáb 9-15. comercial/financeiro: seg-sex, 9h."""
    dt = dt or _agora()
    wd, h = dt.weekday(), dt.hour + dt.minute / 60
    sab_ok = (setor == "suporte")          # só o suporte trabalha sábado
    # ainda dá tempo HOJE?
    if wd <= 4 and h < 9:
        return "hoje a partir das 9h"
    if wd == 5 and sab_ok and h < 9:
        return "hoje (sábado) a partir das 9h"
    # senão, procura o próximo dia que atende
    for somar in range(1, 8):
        d = (wd + somar) % 7
        if d <= 4 or (d == 5 and sab_ok):
            nome = ("amanhã" + (" (sábado)" if d == 5 else "")) if somar == 1 else _DIAS[d]
            return f"{nome} a partir das 9h"
    return "no próximo dia útil, a partir das 9h"

def periodo_do_dia(dt=None):
    """'Bom dia'/'Boa tarde'/'Boa noite' pelo relógio; madrugada = None (saudação neutra)."""
    dt = dt or _agora()
    h = dt.hour
    if 5 <= h < 12: return "Bom dia"
    if 12 <= h < 18: return "Boa tarde"
    if 18 <= h < 24: return "Boa noite"
    return None
