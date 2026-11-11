// teste de força bruta do suporte articulado da TV: o braço nunca fica na frente/dentro da tela e nada entra na parede
// uso: node quarto3d/tests/suporte-tv.js
const fs = require('fs');
const Q = {}; eval(fs.readFileSync(__dirname + '/../js/20-objects.js', 'utf8').split('/*IK*/')[1]);
const L = 0.3, zS = 0.03, BACK = 0.038;
let n = 0, front = 0, wall = 0, armWall = 0, worst = -9, worstQ = null, minWall = 9, noFace = 0;
for (const pol of [32, 40, 43, 50]) { const hw = 0.965 * (pol / 43) / 2, hh = 0.558 * (pol / 43) / 2;
  for (const lado of [-1, 1]) for (const tilt of [-5, 0, 8, 15, 20]) for (let ext = 0; ext <= 1.0001; ext += 0.05) for (let side = -1; side <= 1.0001; side += 0.2) for (let swv = -90; swv <= 90; swv += 5) {
    const q = { ext, side, swivel: swv, tilt, lado }, r = Q.tvArmIK(q, hw, hh); n++;
    if (ext === 0 && swv === 0 && tilt === 0 && Math.abs(Math.abs(r.hx) - Q.TV_OFF) > 0.002) { console.log('descanso fora do lugar', JSON.stringify(q), r.hx); process.exit(1); }
    if (Math.abs(r.sw - swv * Math.PI / 180) > 1e-6 || Math.abs(r.ti - tilt * Math.PI / 180) > 1e-6) noFace++;
    const sn = Math.sin(r.sw), cs = Math.cos(r.sw), st = Math.sin(r.ti), ct = Math.cos(r.ti);
    const toLocal = (px, py, pz) => { const dx = px - r.hx, dz = pz - r.hz, x1 = dx * cs - dz * sn, z1 = dx * sn + dz * cs; return [x1, py * ct + z1 * st, -py * st + z1 * ct]; };
    let bad = false, aw = false;
    for (let k = 0; k <= 20 && !bad; k++) { const t = k / 20;
      const segs = [[r.ex * t, zS + (r.ez - zS) * t, 0.1525], [r.ex + (r.hx - r.ex) * t, r.ez + (r.hz - r.ez) * t, 0.05]];
      for (const [px, pz, yh] of segs) { if (pz < 0.021) aw = true; if (Math.hypot(px - r.hx, pz - r.hz) < 0.07) continue;
        for (const py of [-yh, 0, yh]) { const [u, v, w] = toLocal(px, py, pz); if (Math.abs(u) <= hw && Math.abs(v) <= hh && w > BACK - 0.021) { bad = true; if (w - BACK > worst) { worst = w - BACK; worstQ = Object.assign({ pol }, q); } } } } }
    if (bad) front++; if (aw) armWall++;
    let w0 = false; for (const su of [-1, 1]) for (const sv of [-1, 1]) { const u = su * hw, v = sv * hh, y1 = v * ct - BACK * st, z1 = v * st + BACK * ct, wzc = r.hz - u * sn + z1 * cs; minWall = Math.min(minWall, wzc); if (wzc < 0.004) w0 = true; }
    if (w0) wall++;
  } }
console.log('poses testadas:', n, '| braço na frente ou dentro da tela:', front, '| tela dentro da parede:', wall, '| braço dentro da parede:', armWall, '| giro/inclinação alterados:', noFace);
console.log('pior invasão (m):', worst === -9 ? 'nenhuma' : worst.toFixed(3) + ' ' + JSON.stringify(worstQ), '| menor folga tela-parede (m):', minWall.toFixed(3));
process.exit(front || wall || armWall ? 1 : 0);
