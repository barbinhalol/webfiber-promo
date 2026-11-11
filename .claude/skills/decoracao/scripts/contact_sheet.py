#!/usr/bin/env python3
"""Monta a folha de contato das miniaturas do catálogo (para revisão visual e para os agentes revisores).

uso:  python3 contact_sheet.py <pasta-das-miniaturas> <saida.png> [colunas] [lado-do-quadro]
      (a pasta vem de thumbs.js e tem os PNGs + _names.json)
"""
import json
import os
import sys

from PIL import Image, ImageDraw

if len(sys.argv) < 3:
    sys.exit(__doc__)
pasta, saida = sys.argv[1], sys.argv[2]
cols = int(sys.argv[3]) if len(sys.argv) > 3 else 7
lado = int(sys.argv[4]) if len(sys.argv) > 4 else 200
nomes = json.load(open(os.path.join(pasta, '_names.json'), encoding='utf-8'))
linhas = (len(nomes) + cols - 1) // cols
folha = Image.new('RGB', (cols * lado, linhas * (lado + 26)), (38, 33, 48))
d = ImageDraw.Draw(folha)
for k, (tipo, nome) in enumerate(nomes):
    im = Image.open(os.path.join(pasta, tipo + '.png')).convert('RGBA').resize((lado - 12, lado - 12), Image.LANCZOS)
    x, y = (k % cols) * lado + 6, (k // cols) * (lado + 26) + 4
    fundo = Image.new('RGBA', im.size, (58, 52, 72, 255))
    fundo.alpha_composite(im)
    folha.paste(fundo.convert('RGB'), (x, y))
    d.text((x + 2, y + lado - 10), nome[:30], fill=(235, 235, 240))
folha.save(saida)
print('folha:', saida, folha.size)
