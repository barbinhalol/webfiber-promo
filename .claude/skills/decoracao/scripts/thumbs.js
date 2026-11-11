// Gera a miniatura de cada objeto do catálogo (a mesma que aparece na aba Objetos) e salva em PNG,
// mais um _names.json com [id, nome]. Depois monte a folha de contato com contact_sheet.py.
//
// uso:  node thumbs.js <url> <pasta-de-saida>
// ex.:  node thumbs.js http://127.0.0.1:8765/quarto3d/ shots/thumbs
const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const [url, dir] = process.argv.slice(2);
  if (!url || !dir) { console.log('uso: node thumbs.js <url> <pasta-de-saida>'); process.exit(2); }
  fs.mkdirSync(dir, { recursive: true });
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: 700, height: 460 } });
  page.on('pageerror', e => console.log('PAGEERROR: ' + String(e.stack || e).slice(0, 600)));
  await page.goto(url, { waitUntil: 'load' });
  await page.waitForFunction(() => window.Q && window.Q.E && window.Q.E.frames > 2 && window.Q.E.envDirty === 0, null, { timeout: 180000 });
  const tipos = await page.evaluate(() => Object.keys(Q.catalog).map(k => [k, Q.catalog[k].name]));
  for (const [t] of tipos) {
    const dataUrl = await page.evaluate(t => Q.E.thumb(t), t);
    fs.writeFileSync(dir + '/' + t + '.png', Buffer.from(dataUrl.split(',')[1], 'base64'));
  }
  fs.writeFileSync(dir + '/_names.json', JSON.stringify(tipos));
  console.log('miniaturas:', tipos.length, '->', dir);
  await browser.close();
})();
