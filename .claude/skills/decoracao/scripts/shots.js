// Abre a página do simulador (Chromium sem GPU), executa um trecho de JS em cada passo,
// espera a imagem terminar de refinar e salva uma captura por passo.
//
// uso:  node shots.js <url> <largura> <altura> <amostras> nome=js [nome=js ...]
// ex.:  node shots.js http://127.0.0.1:8765/quarto3d/ 1100 700 6 "geral=" \
//         "bancada=document.querySelector('#tabs [data-tab=quarto]').click()"
// env:  OUT = pasta das capturas (padrão ./shots)
//
// "nome=" sem JS só captura. Cada captura leva de 5 s a 2 min, porque a renderização é por software.
// Servir a pasta antes:  python3 -m http.server 8765 --bind 127.0.0.1   (na raiz do repositório)
const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const [url, w, h, samples, ...steps] = process.argv.slice(2);
  if (!url || !steps.length) { console.log('uso: node shots.js <url> <largura> <altura> <amostras> nome=js ...'); process.exit(2); }
  const out = process.env.OUT || 'shots';
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: +w, height: +h }, deviceScaleFactor: 1 });
  const logs = [];
  page.on('console', m => { if (m.type() === 'error' || (m.type() === 'warning' && !/ReadPixels/.test(m.text()))) logs.push(m.type() + ': ' + m.text().slice(0, 500)); });
  page.on('pageerror', e => logs.push('PAGEERROR: ' + String(e.stack || e).slice(0, 900)));
  await page.goto(url, { waitUntil: 'load' });
  await page.waitForFunction(() => window.Q && window.Q.E && window.Q.E.frames > 2, null, { timeout: 150000 });
  await page.waitForTimeout(900);
  for (const st of steps) {
    const i = st.indexOf('='), name = st.slice(0, i), js = st.slice(i + 1);
    try {
      if (js) await page.evaluate(js);
      await page.waitForTimeout(1100);
      await page.waitForFunction(n => { const E = window.Q.E; return E.envDirty === 0 && E.sample >= Math.min(n, E.opts.maxSamples); }, +samples, { timeout: 300000 });
    } catch (e) { logs.push(name + ' ESPERA: ' + e.message.split('\n')[0]); }
    await page.screenshot({ path: out + '/' + name + '.png', timeout: 240000 });
    const info = await page.evaluate(() => { const E = window.Q.E; return { amostras: E.sample, exposicao: +E.exposure.toFixed(3) }; });
    console.log(name, JSON.stringify(info));
  }
  console.log('erros:', [...new Set(logs)].slice(0, 20).join('\n') || 'nenhum');
  await browser.close();
})();
