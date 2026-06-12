# WebFiber — Landing Experimental "700 Mega" (PRÉVIA)

Landing page nova, isolada e experimental focada na oferta **700 Mega por R$ 99,90**,
com conversão total para o WhatsApp **(21) 98558-9201**.

⚠️ **Esta pasta NÃO toca o site oficial** (webfiberprovedor.com.br). É uma prévia local
para avaliação. Nada foi publicado.

## Como abrir a prévia

Clique 2x em **`Abrir LP 700 Mega.bat`** (sobe um servidor local na porta 8840 e abre o
navegador em `http://localhost:8840/`).

Para ver no celular (mesma rede Wi-Fi): abra `http://192.168.131.16:8840/` no navegador
do celular com a prévia rodando no PC.

## Estrutura (tudo editável)

| Arquivo | O que é |
|---|---|
| `index.html` | A página inteira, seção por seção, com comentários |
| `css/styles.css` | Visual completo — cores da marca nas variáveis do topo |
| `js/main.js` | Interações — **CONFIG no topo** (WhatsApp, mensagem, velocidade) |
| `assets/` | Logo, Milo, fotos e avaliações reais (todas otimizadas) |
| `_build/` | Scripts internos de produção (screenshots, otimização) — pode apagar |

### O que dá pra trocar em segundos
- **Número/mensagem do WhatsApp** → `js/main.js`, bloco `CONFIG` no topo.
- **Preços e textos** → direto no `index.html` (procure "700", "99,90"…).
- **Cores** → `css/styles.css`, variáveis `:root` no topo.

## Como publicar depois (se aprovar)

A página é 100% estática (HTML+CSS+JS, sem build). Três caminhos:

1. **Subdomínio de teste** (recomendado): criar `promo.webfiberprovedor.com.br`
   (ou `/promo700`) na hospedagem atual e subir o CONTEÚDO desta pasta
   (`index.html`, `css/`, `js/`, `assets/`). O site principal continua intocado.
2. **GitHub Pages** (grátis, já validado na conta `barbinhalol`): publicar a pasta
   e apontar um CNAME.
3. **Substituir o site atual** (só com aprovação total): subir estes arquivos na raiz
   da hospedagem — fazer backup do site atual antes.

### Checklist antes de publicar
- [ ] Remover a linha `<meta name="robots" content="noindex,nofollow">` do `index.html`.
- [ ] Em `js/main.js`, mudar `ativarRastreio: false` para `true` (liga a conversão do
      Google Ads no clique do WhatsApp — mesmo padrão do site atual) e adicionar a tag
      gtag do Google Ads no `<head>` (copiar do site atual).
- [ ] Conferir preço/oferta vigentes.

## Conteúdo

Textos reescritos a partir do site oficial (benefícios, FAQ, números, avaliações).
Dados comerciais usados: planos 700/850/1G (R$ 99,90 / 129,90 / 159,90), sem fidelidade,
100% fibra, bairros atendidos, contatos — tudo de fontes oficiais da marca.
As avaliações são os prints REAIS do Google usados no site atual.
