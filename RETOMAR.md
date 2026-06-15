# 🔄 RETOMAR — Sites WebFiber (handoff da sessão de 2026-06-11/12)

> Cole na nova sessão: **"Leia C:\Users\AdminUser\WebFiber-LP-700Mega\RETOMAR.md e continue de onde paramos"**

## O que existe (tudo nesta pasta + repo GitHub `barbinhalol/webfiber-promo`)

| Site | Pasta local | Status | URL |
|---|---|---|---|
| LP 700 Mega | raiz desta pasta | 🟢 NO AR | webfiberprovedor.com.br/promo700mega |
| LP 850 Mega + Watch | `850mega/` | 🟢 NO AR | webfiberprovedor.com.br/promo850mega |
| LP 1 Giga + TV completa | `1giga/` | 🟢 NO AR | webfiberprovedor.com.br/promo1giga |
| **NOVO SITE PRINCIPAL** | `novosite/` | 🟢 **NO AR NA RAIZ desde 2026-06-12** (substituiu a SPA antiga COM OK do dono) | **webfiberprovedor.com.br** |
| **SITE EMPRESARIAL** | `empresarial/` | 🟢 **NO AR desde 2026-06-13** (B2B premium azul marinho: internet empresarial, link dedicado, IP fixo) | **webfiberprovedor.com.br/empresarial** |

Preview local: `Abrir LP 700 Mega.bat` (porta 8840; novosite em /novosite/). **A SPA antiga foi backupada em `public_html/backup-spa-20260612/`** (index.html, assets/ inteira, htaccess.txt, robots.txt, placeholder.svg) — rollback = restaurar esses arquivos.

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
2. **TRUQUE VALIDADO 2026-06-12 (sem precisar do dono!):** abrir hPanel (logado no Chrome) em `hpanel.hostinger.com/websites/webfiberprovedor.com.br` numa aba DO GRUPO do Claude → via javascript_tool: `window.open = function(u){ location.href = u; return {closed:false,focus(){},blur(){},close(){}} }` e depois `click()` no botão "Abrir" do card Gerenciador de Arquivos → o File Browser abre NA MESMA ABA (a URL de auth `srv848-files.hstgr.io/auth?token=…` é de uso quase instantâneo — navegar na hora via location.href, NUNCA capturar p/ navegar depois: dá 403). Base da API: `{origin}/dd441dfc9b5ba8a0`.
3. Na aba do File Browser, via javascript_tool: **ponte** `fetch raw.githubusercontent.com/barbinhalol/webfiber-promo/<SHA-DO-COMMIT>/<arquivo>` → `POST {base}/api/resources/public_html/<pasta>/<arquivo>?override=true` com header `X-Auth: localStorage.jwt`. **403 = sessão expirou** (renovar pelo passo 2). Cópia server-side: `PATCH ?action=copy&destination=...`. **CUIDADO: releitura de verificação na mesma URL /api/raw/ vem do CACHE do navegador — sempre conferir com `?nc=Math.random()` + `cache:'no-store'`** (upload "sem efeito" provavelmente FUNCIONOU). fetch p/ raw.githubusercontent tem CORS ok; fetch p/ webfiberprovedor.com.br é bloqueado (testar de fora via PowerShell).
4. Pastas novas: criar com `.htaccess` = `RewriteEngine on` + `DirectoryIndex index.html` (fura o catch-all da SPA da raiz).
5. Testar SEMPRE depois: raiz (3720 bytes), /corrida/, e os 3 promo*.

## ✅ Feito em 2026-06-12 (tarde)

- **Logo corrigida PUBLICADA nos 3 promo** (era a pendência 1 — foi junto com o pacote do pixel, commit `5086ec1`).
- **Meta Pixel `1400292098619943` EM PRODUÇÃO NO DOMÍNIO INTEIRO**: PageView no `<head>` (com guard de domínio — preview e localhost não sujam o dataset) + evento **Lead** SÓ no clique de botão WhatsApp. Cobertura (2026-06-12, noite): raiz (novosite) + /promo700mega + /promo850mega + /promo1giga (Lead via handler [data-wa] no main.js) **+ /corrida (só PageView, é jogo) + /parceriasindico + /promo (Lead por delegação em links wa.me)**. Backups: `index-antes-pixel.html` dentro de corrida/, parceriasindico/ e promo/. Fontes locais de CorridaWebFiber\ e WebFiber-Condominio-Parceiro\ também receberam o pixel (sincronizados c/ servidor). /700mega/ não é página (301 → home).
- **Mobile do novosite**: preço do rotador em 2 linhas limpas (rótulo pequeno em cima, "R$ 159,90/mês" inteiro embaixo, R$ em .5em via `<small>`) — commit `da7e9e3`.

## ✅ NOVOSITE PUBLICADO NA RAIZ (2026-06-12, noite — OK explícito do dono)

- 71 arquivos do commit `a609a06` subidos via ponte; **index.html por último = troca sem downtime**.
- `.htaccess` da raiz TROCADO (o antigo catch-all da SPA está no backup): força HTTPS + www→apex (301), URLs antigas da SPA → 301 p/ home, mod_expires (imgs 30d, css/js 7d) + deflate. Brotli ativo no LiteSpeed (HTML 52,5KB → 11,5KB). Subpastas (promo*/corrida/parceriasindico) têm .htaccess próprio e ficaram intactas — TODAS testadas 200 após a troca.
- **Search Console CONFIGURADO na conta marketingwebfiber**: propriedade `https://webfiberprovedor.com.br` verificada por arquivo HTML (`googlebbf6f8f3c52729db.html` na raiz — NÃO REMOVER); sitemap.xml enviado e **Processado (4 páginas: home + 3 promo)**; indexação prioritária da home solicitada via Inspeção de URL.
- sitemap.xml agora lista home + as 3 LPs; robots.txt novo na raiz.

## ✅ Feito em 2026-06-13 (Site Empresarial)

- **`/empresarial` PUBLICADO** (commit `60f897d`): site B2B premium azul marinho (Sora+Inter, sem Milo), 14 seções + blocos SEO + schema `LocalBusiness`/`FAQPage`/`BreadcrumbList`. Pasta `empresarial/` no repo com `.htaccess` próprio (DirectoryIndex, fura o catch-all da SPA). Fonte de trabalho separada também em `C:\Users\AdminUser\WebFiber-Empresarial\` (a do repo é a canônica/deployada). WhatsApp (21) 98558-9201; gtag+pixel com guard de domínio; CTAs com href real (robusto sem JS).
- **Link "Empresarial"** no menu (header) e no rodapé do `novosite` (aponta p/ `/empresarial`) — discreto. `index.html` da raiz re-publicado (backup em `index-backup-antes-empresarial.html`); `sitemap.xml` agora lista `/empresarial`.
- Auditoria multi-agente (36 agentes, 23 achados aplicados) antes do deploy. Logo oficial colorida **aparada** + favicon dedicado do símbolo (16/32/apple-touch). og-empresarial.jpg gerado.
- ⏳ Pré-existente p/ enriquecer depois (opcional): `address` do JSON-LD só tem cidade/UF (sem rua/CEP — não inventado); versão monocromática da logo é opção do dono.

## ✅ Feito em 2026-06-13 (botão Baixe sua Fatura)

- **Botão "Baixe sua Fatura" PUBLICADO na raiz** (commit `81dd632`): no hero do `novosite`, ENTRE "Chamar no WhatsApp" e "Ver benefícios". Classe `.btn--fatura` (amarelo #FCD400 da marca, ícone de fatura), `target=_blank`, link `https://areadocliente.webfiberprovedor.com.br/`. Cache CSS `?v=fatura1`. Deploy via ponte (base da sessão: `8ee212e2fa0a0a09`; index.html + css/styles.css em public_html/ raiz). Testado: raiz + 3 promo + empresarial + corrida = 200.

## ⏳ PENDÊNCIAS

1. DNS do subdomínio promo (opcional, parado): registro A `promo` → 45.132.157.77 na Locaweb (login é do dono).
2. Limpeza futura (sem pressa): assets órfãos da SPA antiga ainda misturados em `public_html/assets/` (inofensivos; o backup tem cópia) e os 2 index-backup-*.html soltos na raiz.

## Memórias permanentes relacionadas

`reference_site_modelo_webfiber.md` (estilo/kit/SEO) · `project_lp_700mega.md` (histórico técnico completo) · `reference_hostinger_hospedagem.md` · `project_paramount_fora.md` — todas em `C:\Users\AdminUser\.claude\projects\C--Users-AdminUser\memory\`.
