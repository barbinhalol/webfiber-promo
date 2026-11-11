---
name: decoracao
description: Monta simuladores 3D realistas de ambientes (quarto, sala, escritório) a partir de fotos do cômodo real, onde o usuário passeia por dentro, troca móveis de lugar, apaga a luz e deixa no neon, pinta paredes e armários e coloca TV, cama, estante e decoração. Use SEMPRE que o usuário pedir uma "skill de decoração", quiser decorar, redecorar ou simular um cômodo, mandar fotos de um quarto para ver como ficaria com outros móveis, cores, LEDs ou TV, ou pedir um "quarto 3D" ou "simulador de decoração", mesmo que não diga "3D" nem "skill".
---

# Decoração: simulador 3D fiel ao cômodo real

O resultado é uma página 3D que se abre no celular: o cômodo é montado nas medidas reais, e a pessoa mexe nele (arrasta objetos, muda luz e cores, passeia). A fidelidade às fotos é o que o usuário mais cobra, então o trabalho todo gira em medir direito, conferir contra as fotos e não deixar passar erro visível.

## Ponto de partida

O projeto de referência já existe na pasta `quarto3d/` deste repositório (leia o `README.md` dela). Para um cômodo novo, copie a pasta e troque só as medidas (bloco `MEAS` no topo de `js/10-room.js`) e a marcenaria. O catálogo de objetos, as luzes, o passeio, o arraste, os estilos e o salvamento servem para qualquer cômodo. Para ajustar o quarto atual, edite `quarto3d/` direto.

## Fluxo, nesta ordem

1. **Reunir material.** Peça fotos do cômodo vazio (uma de cada parede, e uma do piso com rejunte visível), uma foto de referência da decoração desejada e uma medida conhecida (lajota do piso, porta de 2,10 m). Pergunte o que é fixo (marcenaria, janela, porta) e o que é móvel. Se o usuário mandar foto de um objeto real (cadeira, suporte de TV), modele a partir dela e compare depois.
2. **Medir por conta, não a olho.** A lajota de tamanho conhecido permite achar a homografia do piso e projetar paredes e móveis. Delegue a um agente fork (prompt em `references/agentes.md`) e exija tabela com erro ± e a marca "medido/deduzido". Isso já mudou o projeto: a medição mostrou que a porta estava em outra parede do que eu tinha assumido.
3. **Modelar em escala real** (metros): marcenaria, janela, porta, piso, cores e veio da madeira tirados das fotos. Cada medida vai para `MEAS`, nunca espalhada pelo código.
4. **Objetos como catálogo.** Cada objeto é um `def('id', {...})` em `js/20-objects.js` com `mount` (`floor`, `surface` ou `wall`), superfícies de apoio (`tops`), opções (`controls`) e miniatura. Todo objeto precisa poder ser removido e recolocado, e o que estava em cima dele cai no piso.
5. **Decoração com 3 agentes Haiku**, em paralelo: estilos prontos, inventário de estante/rack a partir da foto de referência, e detalhes de fidelidade do quarto. Os prompts e o formato JSON de resposta estão em `references/agentes.md`.
6. **Testar de verdade**, não só ler o código: navegador headless, capturas de vários ângulos, celular 420×820 com toque. Use os scripts de `scripts/`.
7. **Revisão independente com 2 agentes Sonnet** (arquitetura e design). Entregue um pacote de capturas, a folha de miniaturas e as fotos reais, e não diga o que você acha que está errado. Isso pegou erros que eu tinha deixado passar. Corrija o que apontarem e confira de novo nas capturas.
8. **Publicar.** Link rápido: página única via Artifact (`scripts/bundle_artifact.py`). Link público: pasta estática no GitHub, pull request em rascunho, e só faça o merge depois do usuário confirmar; o GitHub Pages serve a página. Confira a URL pública (a primeira resposta pode ser 404 por 1 a 2 minutos). Ao mudar arquivo publicado, aumente o `?v=` do `index.html` por causa do cache.
9. **Relatar com honestidade.** Diga o que testou e o que não testou (celular real, vídeo do aparelho), o que mudou a partir das revisões e o que decidiu não mudar, com o motivo.

## Regras que evitam erro grosseiro

- **Objeto articulado (TV com braço, luminária de braço):** escreva a cinemática como função pura e rode um teste de força bruta antes de publicar (`quarto3d/tests/suporte-tv.js` é o modelo). A regra física de um suporte de TV: a placa e os braços ficam sempre atrás do painel, e nenhum canto da tela entra na parede. Controles manuais também têm de respeitar a regra, não só o botão automático.
- **Olhe a folha de miniaturas do catálogo.** Uma miniatura com a face de cima invertida (tapete só com a borda aparecendo) passou despercebida por várias versões.
- **Compare cada captura com a foto real.** O nome do arquivo diz o que deveria aparecer; se a imagem não mostra isso, a câmera ou o objeto está errado.
- **Posição de móvel que o usuário marcou é lei.** Quando ele aponta na captura onde algo deve ficar ("colado na janela", "sobre os pés da cama"), mova exatamente para lá e confira na mesma vista.
- **Mudou posição ou medida padrão?** O arranjo salvo no navegador do usuário não se atualiza sozinho. Troque a chave de armazenamento ou migre o estado (como `tvRev` em `40-app.js`).
- **Conteúdo protegido:** não use trechos de filmes, logotipos nem personagens de terceiros, e não dá para embutir YouTube na página. Ofereça uma animação original e a opção de tocar um vídeo do próprio aparelho (ele não vai junto com o link).
- **Falha de carregamento tem de aparecer na tela.** Uma página que fica "carregando" para sempre impede o diagnóstico à distância. Mantenha `js/guard.js` na página e, ao mexer no carregamento, teste simulando CDN bloqueada, erro de código, aparelho sem WebGL e demora.
- **Não afirme desempenho em celular real** sem ter medido. O teste headless é sem placa de vídeo.

## Convenções técnicas (para não reaprender)

- three.js r147 pelo jsDelivr, sem bundler. A página funciona como pasta estática.
- Paredes: A é a da bancada (leste), B a do guarda-roupa (sul), C a lilás da janela (oeste), D a branca (norte). Cada trecho tem coordenadas locais `u` (ao longo da parede), `y` e `w` (para fora).
- Luz: lâmpada de teto pontual com sombra; fitas de LED como luzes lineares analíticas (até 24, ver `Q.LL`); materiais emissivos compensam a exposição automática; o filme da TV redesenha a ~15 quadros por segundo com mistura temporal.
- Interação: toque longo (240 ms) pega o objeto e arrasta; deslize rápido gira a vista; ajuste fino de 1 cm; desfazer.
- Artifact: a página não leva doctype/html/head/body, o título tem 2 a 4 palavras, e só carrega scripts de CDNs permitidas e fontes do Google Fonts.
- Teste sem GPU: Chromium com `--use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader --ignore-gpu-blocklist`, servindo a pasta com `python3 -m http.server`. Espere `Q.E.envDirty === 0` e `Q.E.sample` antes de capturar.

## Jogo (próxima etapa, ainda sem definição)

O usuário disse que depois vai querer um jogo em cima disto, mas não definiu as regras. Não invente mecânica. Quando ele começar, pergunte o que o jogo é (objetivo, pontuação, desafios, quem joga). O que já serve de base: estado em JSON (`state`, salvo no navegador), catálogo `Q.catalog`, estilos prontos (`THEMES` em `40-app.js`), medidas em `MEAS` e as regras de encaixe dos objetos.

## Arquivos da skill

| Arquivo | Para que serve |
|---|---|
| `references/agentes.md` | Prompts prontos dos agentes (medição, 3 Haiku de decoração, 2 Sonnet de revisão) e o formato de resposta |
| `references/licoes.md` | Erros já cometidos neste projeto e como foram pegos |
| `scripts/shots.js` | Abre a página e salva capturas depois de executar um trecho de JS em cada passo |
| `scripts/smoke.js` | Teste rápido de uma URL no tamanho de celular: carrega, conta objetos, lista respostas com erro |
| `scripts/thumbs.js` e `scripts/contact_sheet.py` | Gera as miniaturas do catálogo e a folha de contato para revisão |
| `scripts/bundle_artifact.py` | Junta `quarto3d/` em uma página única para publicar como Artifact |
