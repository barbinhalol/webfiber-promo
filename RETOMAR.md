# 🔄 RETOMAR — Sites WebFiber (handoff da sessão de 2026-06-11/12)

> Cole na nova sessão: **"Leia C:\Users\AdminUser\WebFiber-LP-700Mega\RETOMAR.md e continue de onde paramos"**

## O que existe (tudo nesta pasta + repo GitHub `barbinhalol/webfiber-promo`)

| Site | Pasta local | Status | URL |
|---|---|---|---|
| LP 700 Mega | raiz desta pasta | 🟢 NO AR | webfiberprovedor.com.br/promo700mega |
| LP 850 Mega + Watch | `850mega/` | 🟢 NO AR | webfiberprovedor.com.br/promo850mega |
| LP 1 Giga + TV completa | `1giga/` | 🟢 NO AR | webfiberprovedor.com.br/promo1giga |
| **NOVO SITE PRINCIPAL** | `novosite/` | 🟡 PRÉVIA (aguarda OK p/ substituir o original) | barbinhalol.github.io/webfiber-promo/novosite/ |

Preview local: `Abrir LP 700 Mega.bat` (porta 8840; novosite em /novosite/). O site oficial atual (SPA antiga) está INTACTO na raiz do domínio.

## O ESTILO (site-modelo — replicar em tudo da WebFiber)

- **LPs promocionais (700/850/1G):** dark premium — fundo azul profundo #02071A→#0064FF, Anton (números-herói) + Poppins, glass, amarelo #FCD400 no preço, magenta #FF2E92 em badges, laranja #FF4E20 só na seção Watch.
- **Novo site principal (`novosite/`):** fundo **azul royal vibrante** (#1166ff→#0a4ad6, igual ao site original) com rodapé/CTA final escuros; planos em **trio de cards brancos** (850 = "★ Mais Popular" com borda amarela).
- **Componentes do kit:** hero com rotador 3D de planos (700 MEGA/850 MEGA/1 GIGA, flip letra a letra + raios de fibra em canvas ao trocar + selo laranja "+ WATCH TV INCLUSO" no 850/1G + valores SÓLIDOS sem sombra) · **Milo no sofá vendo TV** (assets/watch/milo_tv.webp, cropado) em paridade com a oferta · seção TV/streaming logo após o marquee do hero (pôsteres reais em loop duplo + apresentação Watch + **canais em loop ABAIXO do celular da Watch**, chips brancos 95px) · comparador antes/depois (empilha no mobile) · stats + avaliações reais · FAQ `<details>` · CTA final com Milo · stickybar mobile SEMPRE fixa.

## Padrões técnicos (lei)

- HTML/CSS/JS puro; CONFIG no topo do `js/main.js`; todo CTA = `[data-wa]`.
- **Conversão Google Ads oficial**: gtag AW-18086861405 no topo do head + `gtag_report_conversion` (send_to `AW-18086861405/Sb-JCLHf9LscEN20vrBD`) + onclick nos 11 botões; guard: só conta em `*.webfiberprovedor.com.br`.
- **Cache-busting `?v=` no CSS/JS — SEMPRE bump ao republicar.**
- SEO do novosite (2026-06-12, completo): canonical p/ domínio final, OG/Twitter + og-image.jpg, favicons+manifest, robots.txt+sitemap.xml, schema @graph (Org+WebSite+ISP/LocalBusiness com 16 bairros+3 Offers+FAQPage 10 perguntas+Breadcrumb), **H1 sr-only estável** (rotador é `<p aria-hidden>`), **noscript fix** (sem ele o site fica invisível p/ crawler), skip-link, SEO local (16 bairros em texto na Cobertura+footer).

## Regras do dono (NUNCA violar)

- **SEM Paramount e SEM Nickelodeon** (saíram do portfólio). Canais citáveis: Telecine, SporTV, ESPN, CNN, Megapix, Multishow, GloboNews, GNT, AMC, Universal, BIS, Globoplay + abertos.
- Watch TV (Watch Brasil) = parceiro de streaming; 850 = canais abertos + "mais de 30 mil títulos"; 1G = TV completa 60+ canais.
- Bairros (16, lista oficial 2026-06-12): Centro RJ, Tijuca, Vila Isabel, Grajaú, Maracanã, Andaraí, Praça da Bandeira, Rio Comprido, São Cristóvão, Cidade Nova, Santa Teresa, Bairro de Fátima, Catumbi, Lapa, Santo Cristo, São Francisco Xavier. Em SEÇÃO VISUAL: não listar (usar "principais bairros + sempre em expansão" + CTA); em TEXTO SEO/footer/schema: pode listar.
- "Instalação profissional ultra rápida" (não "rapidinha"). Urgência só se real. WhatsApp (21) 98558-9201.

## Como publicar/atualizar na Hostinger (processo validado)

1. Editar local → commit → push (repo `barbinhalol/webfiber-promo`).
2. Abrir hPanel (logado no Chrome) → site webfiberprovedor.com.br → Gerenciador de Arquivos → **clique REAL (coordenadas via getBoundingClientRect) no card "Acessar arquivos de…"** → a aba "My files - File Browser" precisa estar NO GRUPO de abas do Claude (se nascer fora: pedir ao dono 1 clique e arrastar a aba pro grupo).
3. Na aba do File Browser, via javascript_tool: **ponte** `fetch raw.githubusercontent.com/barbinhalol/webfiber-promo/<SHA-DO-COMMIT>/<arquivo>` → `POST {base}/api/resources/public_html/<pasta>/<arquivo>?override=true` com header `X-Auth: localStorage.jwt`. **403 = sessão expirou** (renovar pelo card). Cópia server-side: `PATCH ?action=copy&destination=...`.
4. Pastas novas: criar com `.htaccess` = `RewriteEngine on` + `DirectoryIndex index.html` (fura o catch-all da SPA da raiz).
5. Testar SEMPRE depois: raiz (3720 bytes), /corrida/, e os 3 promo*.

## ⏳ PENDÊNCIAS

1. **Logo do header corrigida (esferas completas) está no GitHub/prévia mas NÃO nos 3 sites publicados** — falta a ponte (sessão expirou; SHA do commit: `9b95805`; arquivos: `index.html` + `assets/logo_mark.png` de cada um para promo700mega/promo850mega/promo1giga).
2. **Publicar o novosite no lugar do site original** — SÓ COM OK EXPLÍCITO do dono. Plano: backup da raiz do public_html (copiar index.html + assets/ da SPA antiga p/ pasta backup-spa-<data>/ via server-copy) → subir o conteúdo de `novosite/` na raiz (manter pastas corrida/, promo*/, parceriasindico/, robots.txt e sitemap.xml vão juntos) → testar tudo → Search Console + sitemap + Rich Results Test (checklist no relatório SEO).
3. DNS do subdomínio promo (opcional, parado): registro A `promo` → 45.132.157.77 na Locaweb (login é do dono).

## Memórias permanentes relacionadas

`reference_site_modelo_webfiber.md` (estilo/kit/SEO) · `project_lp_700mega.md` (histórico técnico completo) · `reference_hostinger_hospedagem.md` · `project_paramount_fora.md` — todas em `C:\Users\AdminUser\.claude\projects\C--Users-AdminUser\memory\`.
