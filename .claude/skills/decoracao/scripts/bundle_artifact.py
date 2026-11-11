#!/usr/bin/env python3
"""Junta a pasta estática do simulador numa página única para publicar como Artifact.

O Artifact embrulha a página num esqueleto próprio (já traz doctype, head, body, reset e o espaçamento
de segurança do celular), então a saída não leva essas tags. O bloco "/* base */" do style.css existe só
para a versão estática e é removido aqui para não duplicar o espaçamento.

uso:  python3 bundle_artifact.py <pasta-do-simulador> <saida.html>
ex.:  python3 bundle_artifact.py quarto3d meu-quarto-3d.html
"""
import os
import re
import sys

if len(sys.argv) != 3:
    sys.exit(__doc__)
src, dest = sys.argv[1], sys.argv[2]

index = open(os.path.join(src, 'index.html'), encoding='utf-8').read()
css = open(os.path.join(src, 'style.css'), encoding='utf-8').read()
css = re.sub(r'/\* base \*/.*?\n\n', '', css, count=1, flags=re.S)

titulo = re.search(r'<title>(.*?)</title>', index, re.S).group(1)
fonte = re.search(r'<link rel="stylesheet" href="https://fonts\.googleapis\.com[^>]*>', index).group(0)
corpo = index[index.index('<div id="app">'):index.index('<script src=')].rstrip()
cdn = re.findall(r'<script src="https://cdn\.jsdelivr\.net[^"]*"></script>', index)
local = re.findall(r'<script src="(js/[^"?]+)', index)
if not cdn or not local:
    sys.exit('index.html fora do formato esperado (faltam scripts)')
js = '\n'.join(open(os.path.join(src, f), encoding='utf-8').read() for f in local)
if '</script' in js.lower():
    sys.exit('algum arquivo js contém </script e quebraria a página única')

saida = (
    '<title>%s</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n%s\n<style>\n%s</style>\n\n%s\n\n%s\n<script>\n%s\n</script>\n'
    % (titulo, fonte, css, corpo, '\n'.join(cdn), js)
)
open(dest, 'w', encoding='utf-8').write(saida)
print('ok', dest, len(saida), 'bytes;', len(local), 'arquivos js')
