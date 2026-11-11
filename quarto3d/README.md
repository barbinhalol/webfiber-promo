# Meu Quarto 3D

Simulador 3D do quarto: passeio por dentro, arrastar objetos, luzes e neon, pintura de paredes e armários,
e TV em suporte articulado. É HTML + JavaScript puro (three.js via CDN), sem etapa de build.

| Arquivo | O que é |
|---|---|
| `index.html` | A página |
| `style.css` | Visual da interface |
| `js/00-core.js` | Texturas, materiais e o filme que passa na TV |
| `js/10-room.js` | O cômodo e a marcenaria — as medidas ficam no bloco `MEAS`, no topo |
| `js/20-objects.js` | Catálogo de objetos (móveis, decoração, luzes, TV) |
| `js/30-engine.js` | Renderização |
| `js/40-app.js` | Interface, passeio, arraste, estilos prontos |
| `tests/suporte-tv.js` | Teste da mecânica do suporte da TV |

Ao alterar o `style.css` ou algum arquivo de `js/`, aumente o `?v=` nas tags do `index.html`
para o navegador não usar a versão antiga.

Teste do suporte (o braço nunca pode ficar na frente da tela nem entrar na parede):

```
node quarto3d/tests/suporte-tv.js
```
