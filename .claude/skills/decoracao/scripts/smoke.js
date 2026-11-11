// Teste rápido de uma URL do simulador, no tamanho de celular (420 x 820, com toque).
// Confere: a página carrega, o 3D inicia, conta os objetos, o filme da TV roda, não há rolagem lateral,
// nenhuma resposta 4xx/5xx e nenhum erro de console. Salva uma captura.
//
// uso:  node smoke.js <url> [captura.png]
// ex.:  node smoke.js https://barbinhalol.github.io/webfiber-promo/quarto3d/ publico.png
const { chromium } = require('playwright');

(async () => {
  const [url, png = 'smoke.png'] = process.argv.slice(2);
  if (!url) { console.log('uso: node smoke.js <url> [captura.png]'); process.exit(2); }
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const ctx = await browser.newContext({ viewport: { width: 420, height: 820 }, hasTouch: true, isMobile: true, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const erros = [], respostas = [];
  page.on('console', m => { if (m.type() === 'error') erros.push('console: ' + m.text().slice(0, 300)); });
  page.on('pageerror', e => erros.push('PAGEERROR: ' + String(e.stack || e).slice(0, 600)));
  page.on('response', r => { if (r.status() >= 400) respostas.push(r.status() + ' ' + r.url()); });
  page.on('requestfailed', r => respostas.push('falhou ' + r.url()));
  await page.goto(url, { waitUntil: 'load' });
  await page.waitForFunction(() => window.Q && window.Q.E && window.Q.E.frames > 2 && window.Q.E.envDirty === 0, null, { timeout: 180000 });
  await page.waitForTimeout(1500);
  const info = await page.evaluate(() => {
    let objetos = 0; Q.E.scene.traverse(m => { if (m.isMesh && m.userData.id) objetos++; });
    return { titulo: document.title, objetos, filme: Q.E.filmOn, carregando: getComputedStyle(document.getElementById('load')).display,
      semRolagemLateral: document.documentElement.scrollWidth <= innerWidth, quadros: Q.E.frames };
  });
  console.log(JSON.stringify(info));
  await page.screenshot({ path: png, timeout: 200000 });
  console.log('respostas com erro:', respostas.join(' | ') || 'nenhuma');
  console.log('erros de console:', erros.join(' | ') || 'nenhum');
  await browser.close();
  process.exit(erros.length || respostas.length || info.carregando !== 'none' ? 1 : 0);
})();
