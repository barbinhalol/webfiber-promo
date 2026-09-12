const { chromium } = require('playwright');
const { spawn } = require('child_process');
const fs = require('fs');
const FF = '/usr/local/lib/python3.11/dist-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2';
const FPS = 30, DUR = 49.13, N = Math.round(DUR * FPS);
const args = process.argv.slice(2);
const preview = args[0] === '--preview' ? args[1].split(',').map(Number) : null;
const out = args[0] === '--out' ? args[1] : 'reels.mp4';
(async () => {
  const b = await chromium.launch({ args: ['--no-sandbox', '--no-proxy-server'] });
  const p = await b.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  p.on('pageerror', e => console.error('PAGEERROR', e.message));
  p.on('console', m => { if (m.type() === 'error') console.error('CONSOLE', m.text()); });
  await p.goto('http://127.0.0.1:8765/index.html?render=1&frames=vframes');
  await p.evaluate(() => window.__ready);
  await p.waitForTimeout(300);
  if (preview) {
    fs.mkdirSync('prev', { recursive: true });
    for (const t of preview) {
      await p.evaluate(t => window.__seek(t), t);
      await p.screenshot({ path: `prev/p_${t.toFixed(2)}.jpg`, type: 'jpeg', quality: 85 });
      console.log('preview', t);
    }
    await b.close(); return;
  }
  const ff = spawn(FF, ['-hide_banner', '-loglevel', 'error', '-y', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-', '-i', 'audio.m4a',
    '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p', '-r', String(FPS), '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const t0 = Date.now();
  for (let i = 0; i < N; i++) {
    const t = i / FPS;
    await p.evaluate(t => window.__seek(t), t);
    const buf = await p.screenshot({ type: 'jpeg', quality: 93 });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (i % 150 === 0) console.log(`frame ${i}/${N} ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  console.log('done', out, ((Date.now() - t0) / 1000).toFixed(0), 's');
  await b.close();
})().catch(e => { console.error('ERR', e); process.exit(1); });
