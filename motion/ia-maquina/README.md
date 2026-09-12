# Reels — "I.A. ≠ HUMANO" (motion graphics em HTML)

Teste de motion graphics gerado a partir do vídeo falado (49 s, vertical), no formato Reels 9:16 (1080×1920, 30 fps).

## Arquivos

| Arquivo | O que é |
|---|---|
| `index.html` | A composição inteira (legendas cinéticas, robôs, layout que joga o vídeo pra baixo/pra cima, glitch, HUD). Abre no navegador e toca com som — precisa do `video.mp4` ao lado. |
| `video.mp4` | O vídeo original transcodificado para web (720×1280). |
| `reels-ia-maquina.mp4` | O render final pronto pra postar (1080×1920, H.264 + AAC). |
| `src/template.html` | Fonte da composição antes de embutir as fontes (Anton, Bebas Neue, Space Mono, Space Grotesk — Google Fonts, licença OFL). |
| `src/build.py` | Gera o `index.html` (embute fontes em base64 e o envelope de áudio). |
| `src/render.js` | Renderiza o MP4: Playwright (Chromium) fotografa frame a frame e o ffmpeg monta o vídeo com o áudio original. |
| `src/transcricao-palavras.json` | Transcrição automática com tempo por palavra (Vosk + modelo pt-BR do FalaBrasil/UFPA), base das legendas. |

## Como abrir a versão HTML

Suba um servidor local na pasta (ex.: `python -m http.server 8840`) e abra `http://localhost:8840/motion/ia-maquina/`. Toque na tela para reproduzir com som. Em qualquer tamanho de tela a composição se ajusta ao 9:16.

## Como ajustar

- **Legendas e tempos** → `src/template.html`, array `CAPS` (início, fim, texto, estilo `sm`/`md`/`big`/`huge`, posição, animação `pop`/`slam`/`type`).
- **Quando o vídeo desce/sobe** → array `LAYOUT` (`full`, `bottom`, `top`).
- **Cenas com robôs** (chat, marcha, abraço, carinho/irritação, erro final) → funções `scene(...)`.
- O `build.py` espera as fontes `.ttf` em `../fonts/` e o `env.json` (envelope de áudio, 30 valores/s) em `../`, ambos gerados fora do repositório.
- Depois de editar: `python src/build.py` para gerar o `index.html`; para o MP4, extraia os frames do vídeo em `vframes/f00001.jpg…` (30 fps), sirva a pasta em `http://127.0.0.1:8765` e rode `node src/render.js --out reels-ia-maquina.mp4`.
