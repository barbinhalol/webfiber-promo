/* Quarto 3D — o cômodo: paredes, janela, porta e a marcenaria em L (fiel às fotos) */
(function () {
  'use strict';
  const T = THREE, Q = window.Q;
  const TU = 0.64, TV = 1.28;
  let rand = Q.rng(4242);
  const V3 = function (x, y, z) { return new T.Vector3(x, y, z); };

  /* UV em escala real, com o veio na direção pedida */
  function woodUV(g, grain) {
    const p = g.attributes.position, n = g.attributes.normal;
    let uv = g.attributes.uv;
    if (!uv) { uv = new T.BufferAttribute(new Float32Array(p.count * 2), 2); g.setAttribute('uv', uv); }
    const ou = rand(), ov = rand();
    for (let i = 0; i < p.count; i++) {
      const x = p.getX(i), y = p.getY(i), z = p.getZ(i);
      const ax = Math.abs(n.getX(i)), ay = Math.abs(n.getY(i)), az = Math.abs(n.getZ(i));
      let across, along;
      if (grain === 'y') { if (ay > ax && ay > az) { along = z; across = x; } else { along = y; across = ax > az ? z : x; } }
      else if (grain === 'x') { if (ax > ay && ax > az) { along = y; across = z; } else { along = x; across = ay > az ? z : y; } }
      else { if (az > ax && az > ay) { along = y; across = x; } else { along = z; across = ay > ax ? x : y; } }
      uv.setXY(i, across / TU + ou, along / TV + ov);
    }
    return g;
  }
  Q.woodUV = woodUV;

  function Batch() { this.map = {}; }
  Batch.prototype.add = function (key, g, m) {
    if (g.index) { const n = g.toNonIndexed(); g.dispose(); g = n; }
    Object.keys(g.attributes).forEach(function (k) { if (k !== 'position' && k !== 'normal' && k !== 'uv') g.deleteAttribute(k); });
    if (!g.attributes.uv) g.setAttribute('uv', new T.BufferAttribute(new Float32Array(g.attributes.position.count * 2), 2));
    if (m) g.applyMatrix4(m);
    (this.map[key] = this.map[key] || []).push(g);
  };
  Batch.prototype.build = function (mats, group) {
    const out = {};
    for (const key in this.map) {
      const list = this.map[key];
      const geo = T.BufferGeometryUtils.mergeBufferGeometries(list, false);
      list.forEach(function (g) { g.dispose(); });
      const mesh = new T.Mesh(geo, mats[key]);
      const isGlass = key.indexOf('glass') === 0;
      mesh.castShadow = !isGlass; mesh.receiveShadow = !isGlass;
      if (isGlass) { mesh.layers.set(1); mesh.renderOrder = 5; }
      mesh.name = key; group.add(mesh); out[key] = mesh;
    }
    return out;
  };
  Q.Batch = Batch;

  function oct(p, x0, y0, x1, y1, c) {
    p.moveTo(x0 + c, y0); p.lineTo(x1 - c, y0); p.lineTo(x1, y0 + c); p.lineTo(x1, y1 - c);
    p.lineTo(x1 - c, y1); p.lineTo(x0 + c, y1); p.lineTo(x0, y1 - c); p.lineTo(x0, y0 + c); p.lineTo(x0 + c, y0);
  }
  /* moldura almofadada octogonal das portas */
  function molding(x0, x1, y0, y1, c, pw) {
    const s = new T.Shape(); oct(s, x0, y0, x1, y1, c);
    const h = new T.Path(); oct(h, x0 + pw, y0 + pw, x1 - pw, y1 - pw, Math.max(0.004, c - pw * 0.586));
    s.holes.push(h);
    return new T.ExtrudeGeometry(s, { depth: 0.005, bevelEnabled: true, bevelThickness: 0.006, bevelSize: 0.0065, bevelOffset: -0.0065, bevelSegments: 4, curveSegments: 1 });
  }

  /* construtor em coordenadas locais do trecho: u (ao longo da parede), y (altura), w (para fora da parede) */
  function Run(batch, matrix) { this.b = batch; this.m = matrix; }
  Run.prototype.box = function (key, u0, u1, y0, y1, w0, w1, grain) {
    const g = new T.BoxGeometry(Math.abs(u1 - u0), Math.abs(y1 - y0), Math.abs(w1 - w0));
    g.translate((u0 + u1) / 2, (y0 + y1) / 2, (w0 + w1) / 2);
    if (grain) woodUV(g, grain);
    this.b.add(key, g, this.m);
  };
  Run.prototype.geo = function (key, g, grain) { if (grain) woodUV(g, grain); this.b.add(key, g, this.m); };
  Run.prototype.door = function (u0, u1, y0, y1, wF, o) {
    o = o || {};
    const gp = 0.0015, th = 0.019, ins = o.inset || 0.05, pw = o.pw || 0.027, c = o.chamfer || 0.045;
    this.box('wood', u0 + gp, u1 - gp, y0 + gp, y1 - gp, wF - th, wF, 'y');
    const g = molding(u0 + ins, u1 - ins, y0 + ins, y1 - ins, c, pw); g.translate(0, 0, wF + 0.004);
    this.geo('wood', g, 'y');
  };
  Run.prototype.knob = function (u, y, w, kind) {
    let g;
    if (kind === 'fly') { g = new T.SphereGeometry(0.012, 14, 10); g.scale(1.55, 0.72, 0.6); g.translate(u, y, w + 0.016); }
    else { g = new T.SphereGeometry(0.0105, 14, 10); g.scale(1, 1, 0.8); g.translate(u, y, w + 0.016); }
    this.b.add('brass', g, this.m);
    g = new T.CylinderGeometry(0.0035, 0.006, 0.014, 10); g.rotateX(Math.PI / 2); g.translate(u, y, w + 0.007);
    this.b.add('brass', g, this.m);
  };
  Run.prototype.keyhole = function (u, y, w) {
    const g = new T.CylinderGeometry(0.007, 0.007, 0.003, 12); g.rotateX(Math.PI / 2); g.translate(u, y, w + 0.0015);
    this.b.add('brass', g, this.m);
  };
  Run.prototype.shelf = function (u0, u1, y, w0, d) {
    this.box('wood', u0, u1, y, y + 0.022, w0, w0 + d, 'x');
    this.box('wood', u0, u1, y + 0.022, y + 0.036, w0, w0 + d - 0.03, 'x');
  };
  /* bandô recortado no alto dos nichos */
  Run.prototype.valance = function (u0, u1, y0, y1, wF) {
    const a = Math.min(0.10, (u1 - u0) * 0.14), r = 0.05, s = new T.Shape();
    s.moveTo(u0, y0); s.lineTo(u0 + a, y0); s.absarc(u0 + a + r, y0, r, Math.PI, Math.PI / 2, true);
    s.lineTo(u1 - a - r, y0 + r); s.absarc(u1 - a - r, y0, r, Math.PI / 2, 0, true);
    s.lineTo(u1, y0); s.lineTo(u1, y1); s.lineTo(u0, y1); s.lineTo(u0, y0);
    const g = new T.ExtrudeGeometry(s, { depth: 0.02, bevelEnabled: false, curveSegments: 10 });
    g.translate(0, 0, wF - 0.02);
    this.geo('wood', g, 'x');
  };
  /* espelho de tomada antigo (latão envelhecido) */
  Run.prototype.outletBrass = function (u, y, w, round) {
    const s = new T.Shape(), N = 56;
    for (let i = 0; i <= N; i++) {
      const th = (i / N) * Math.PI * 2, cx = Math.cos(th), sy = Math.sin(th);
      const rr = Math.pow(Math.pow(Math.abs(cx), 4) + Math.pow(Math.abs(sy), 4), -0.25), k = 1 + 0.07 * Math.cos(th * 8);
      const px = cx * rr * (round ? 0.036 : 0.039) * k, py = sy * rr * (round ? 0.036 : 0.055) * k;
      i ? s.lineTo(px, py) : s.moveTo(px, py);
    }
    let g = new T.ExtrudeGeometry(s, { depth: 0.002, bevelEnabled: true, bevelThickness: 0.002, bevelSize: 0.002, bevelSegments: 2, curveSegments: 1 });
    g.translate(u, y, w + 0.002); this.b.add('brassDark', g, this.m);
    g = new T.CylinderGeometry(0.018, 0.018, 0.003, 20); g.rotateX(Math.PI / 2); g.translate(u, y, w + 0.0065);
    this.b.add(round ? 'dark' : 'ivory', g, this.m);
  };
  Run.prototype.outletWhite = function (u, y, w) {
    this.box('ivory', u - 0.037, u + 0.037, y - 0.057, y + 0.057, w, w + 0.007);
    const g = new T.CylinderGeometry(0.02, 0.02, 0.003, 20); g.rotateX(Math.PI / 2); g.translate(u, y, w + 0.008);
    this.b.add('ivory', g, this.m);
  };

  function orient(obj, xAxis, emit) {
    const z = emit.clone().negate().normalize(), x = xAxis.clone().normalize();
    const y = new T.Vector3().crossVectors(z, x).normalize(); x.crossVectors(y, z);
    obj.quaternion.setFromRotationMatrix(new T.Matrix4().makeBasis(x, y, z));
  }
  Q.orient = orient;

  /* medidas do quarto real (m), calculadas pelas juntas das lajotas de 80 cm nas fotos (resíduo de 3 a 8 mm) */
  const MEAS = (Q.MEAS = {
    W: 2.53, D: 3.46, H: 2.53, dA: 0.56, dB: 0.565,
    doorZone: 0.81, doorW: 0.62, doorH: 2.1,                       // parede A: vão da porta entre a parede D e a torre
    tower: 0.64, desk: 0.975, drawer: 0.28, corner: 0.475,         // parede A, depois da porta
    bDoor1: 0.495, bDoor2: 0.455, nicheL: 0.03, niche: 0.935, nicheR: 0.055,   // parede B, a partir da quina com A
    winZ0: 0.175, winW: 1.425, winY0: 1.035, winY1: 2.4, acZ0: 0.518, acW: 0.654, acY0: 0.428, acY1: 0.847, acOutletZ: 0.29, acOutletY: 0.37,
    dOutletX: 0.85, tile: 0.8, tileOx: 0.15, tileOz: -0.005,
    shelf1: 1.4, shelf2: 1.69, towerShelf: 1.575, nicheShelf1: 1.46, nicheShelf2: 1.75, yUp: 2.02
  });
  Q.ROOM_DEFAULT = { W: MEAS.W, D: MEAS.D, H: MEAS.H };
  Q.LAMP = 12 * Math.max(1, (MEAS.W * MEAS.D) / 6.6);

  Q.buildRoom = function (dims) {
    rand = Q.rng(4242);
    const W = dims.W, Dp = dims.D, H = dims.H, M = Q.M;
    const dA = MEAS.dA, dB = MEAS.dB, t = 0.02;
    const LA = Dp - dB, LB = W - dA;
    const zA = Math.min(MEAS.doorZone, LA * 0.4), LAr = LA - zA;       // a marcenaria da parede A começa depois da porta
    const kA = LAr / (MEAS.tower + MEAS.desk + MEAS.corner), kB = LB / (MEAS.bDoor1 + MEAS.bDoor2 + MEAS.nicheL + MEAS.niche + MEAS.nicheR);
    const uT = MEAS.tower * kA, uD = uT + MEAS.desk * kA, uDu = uD - t - MEAS.drawer * Math.min(1.15, kA);   // torre | bancada | gaveteiro
    const uN = (MEAS.bDoor1 + MEAS.bDoor2) * kB, uH = MEAS.bDoor1 * kB, nL = MEAS.nicheL, nR = MEAS.nicheR;   // guarda-roupa | nicho
    const yUp = Math.min(MEAS.yUp, H - 0.42);                             // topo da parte de baixo
    const group = new T.Group(), batch = new Batch();
    const basis = function (x, z, o) { return new T.Matrix4().makeBasis(x, V3(0, 1, 0), z).setPosition(o); };
    const mA = basis(V3(0, 0, 1), V3(-1, 0, 0), V3(W, 0, 0));
    const mB = basis(V3(-1, 0, 0), V3(0, 0, -1), V3(W - dA, 0, Dp));
    const mC = basis(V3(0, 0, -1), V3(1, 0, 0), V3(0, 0, Dp));
    const mD = new T.Matrix4();
    const mA2 = mA.clone().multiply(new T.Matrix4().makeTranslation(zA, 0, 0));
    const A = new Run(batch, mA2), AW = new Run(batch, mA), B = new Run(batch, mB), C = new Run(batch, mC), D = new Run(batch, mD);
    const wFu = 0.015;   // quanto os armários altos avançam

    /* ================= PAREDE A (leste): torre + bancada + porta de canto ================= */
    // torre (onde vai o gabinete)
    A.box('wood', 0, t, 0, yUp, 0, dA, 'y');
    A.box('wood', uT - t, uT, 0, yUp, 0, dA, 'y');
    A.box('wood', t, uT - t, 0.75, yUp, 0, 0.012, 'y');
    A.box('wood', t, uT - t, 0, 0.08, 0, dA - 0.015, 'x');
    A.box('wood', t, uT - t, 0.08, 0.75, 0, dA - 0.021, 'y');
    const um = uT / 2;
    A.door(t, um, 0.085, 0.747, dA, { inset: 0.045, chamfer: 0.04 });
    A.door(um, uT - t, 0.085, 0.747, dA, { inset: 0.045, chamfer: 0.04 });
    A.knob(um + 0.03, 0.44, dA, 'round');
    A.box('wood', t, uT - t, 0.75, 0.775, 0, dA, 'x');
    A.box('glass', t + 0.004, uT - t - 0.004, 0.775, 0.779, 0.014, dA - 0.004);
    A.shelf(t, uT - t, MEAS.towerShelf, 0.012, 0.34);
    A.valance(t, uT - t, yUp - 0.13, yUp, dA);
    A.outletBrass(uT * 0.30, 1.69, 0.012); A.outletBrass(uT * 0.40, 0.9, 0.012);
    // bancada (onde fica só a tela)
    A.box('wood', uD - t, uD, 0, yUp, 0, dA, 'y');
    A.box('wood', uT, uD - t, 0, yUp, 0, 0.012, 'y');
    A.box('wood', uT, uD - t, 0.735, 0.765, 0, dA + 0.012, 'x');
    A.box('glass', uT + 0.004, uD - t - 0.004, 0.765, 0.769, 0.014, dA + 0.008);
    A.box('wood', uDu - 0.018, uDu, 0, 0.735, 0, dA - 0.005, 'y');
    A.box('wood', uDu, uD - t, 0.60, 0.735, 0.012, dA - 0.021, 'x');
    A.door(uDu, uD - t, 0.605, 0.732, dA, { inset: 0.02, chamfer: 0.02, pw: 0.013 });
    A.knob((uDu + uD - t) / 2, 0.668, dA, 'round');
    A.box('wood', uDu, uD - t, 0.38, 0.398, 0.012, dA - 0.02, 'x');
    A.box('wood', uDu, uD - t, 0.08, 0.10, 0.012, dA - 0.01, 'x');
    A.box('wood', uDu - 0.018, uD - t, 0, 0.08, 0, dA - 0.02, 'x');
    A.box('wood', uT + 0.02, uDu - 0.035, 0.63, 0.648, 0.13, dA + 0.13, 'x');     // bandeja do teclado
    A.box('wood', uT, uT + 0.02, 0.60, 0.735, 0.10, dA - 0.03, 'z');              // corrediças
    A.box('wood', uDu - 0.053, uDu - 0.018, 0.60, 0.735, 0.10, dA - 0.03, 'z');
    A.shelf(uT, uD - t, MEAS.shelf1, 0.012, 0.28); A.shelf(uT, uD - t, MEAS.shelf2, 0.012, 0.3);
    A.valance(uT, uD - t, yUp - 0.13, yUp, dA);
    // porta alta de canto
    A.box('wood', uD, LAr, 0, 0.08, 0, dA - 0.015, 'x');
    A.box('wood', uD, LAr, 0.08, yUp, 0, dA - 0.021, 'y');
    A.door(uD, LAr, 0.085, yUp - 0.004, dA, {});
    A.knob(uD + 0.036, 1.05, dA, 'fly');
    A.box('wood', LAr, LAr + dB, 0, H, 0, dA - 0.03, 'y');                               // miolo do canto (oculto)
    // régua + armários altos
    A.box('wood', 0, LAr, yUp, yUp + 0.03, 0, dA + 0.006, 'x');
    A.box('wood', 0, LAr, yUp + 0.03, H, 0, dA + wFu - 0.021, 'x');
    const yu0 = yUp + 0.036, yu1 = H - 0.012;
    [[0, um], [um, uT], [uT, (uT + uD) / 2], [(uT + uD) / 2, uD], [uD, LAr]].forEach(function (s, i) {
      A.door(s[0], s[1], yu0, yu1, dA + wFu, { inset: 0.05, chamfer: 0.045 });
      if (i === 4) A.knob((s[0] + s[1]) / 2, yu0 + 0.05, dA + wFu, 'fly');
      else if (i % 2 === 0) A.keyhole(s[1] - 0.03, yu0 + 0.12, dA + wFu);
    });

    /* ================= PAREDE B (sul): guarda-roupa + nicho da cama ================= */
    B.box('wood', 0, uN, 0, 0.08, 0, dB - 0.015, 'x');
    B.box('wood', 0, uN, 0.08, yUp, 0, dB - 0.021, 'y');
    B.door(0, uH, 0.085, yUp - 0.004, dB, {}); B.door(uH, uN, 0.085, yUp - 0.004, dB, {});
    B.knob(uH + 0.036, 1.05, dB, 'fly');
    B.box('wood', uN, uN + nL, 0, yUp, 0, dB, 'y');
    B.box('wood', LB - nR, LB, 0, yUp, 0, dB, 'y');
    B.box('wood', uN + nL, LB - nR, 0, yUp, 0, 0.012, 'y');
    B.box('woodDark', uN + nL, LB - nR, 0, 0.07, 0.012, 0.024, 'x');
    B.shelf(uN + nL, LB - nR, MEAS.nicheShelf1, 0.012, 0.37); B.shelf(uN + nL, LB - nR, MEAS.nicheShelf2, 0.012, 0.37);
    B.valance(uN + nL, LB - nR, yUp - 0.13, yUp, dB);
    const un = uN + (LB - uN) * 0.6;
    B.outletWhite(un, 0.30, 0.012); B.outletBrass(un + 0.11, 0.30, 0.012, true);
    B.box('wood', 0, LB, yUp, yUp + 0.03, 0, dB + 0.006, 'x');
    B.box('wood', 0, LB, yUp + 0.03, H, 0, dB + wFu - 0.021, 'x');
    [[0, uH], [uH, uN], [uN, (uN + LB) / 2], [(uN + LB) / 2, LB]].forEach(function (s, i) {
      B.door(s[0], s[1], yu0, yu1, dB + wFu, { inset: 0.05, chamfer: 0.045 });
      if (i === 0 || i === 3) B.keyhole(i === 0 ? s[1] - 0.03 : s[0] + 0.03, yu0 + 0.12, dB + wFu);
    });

    /* ================= PAREDE C (oeste, lilás): janela + ar-condicionado ================= */
    const win = { z0: MEAS.winZ0, z1: Math.min(MEAS.winZ0 + MEAS.winW, LA - 0.35), y0: MEAS.winY0, y1: Math.min(MEAS.winY1, H - 0.3) };
    const ac = { z0: MEAS.acZ0, z1: Math.min(MEAS.acZ0 + MEAS.acW, win.z1 - 0.05), y0: MEAS.acY0, y1: MEAS.acY1 };
    const sC = function (z) { return Dp - z; };
    const s0 = sC(win.z1), s1 = sC(win.z0), a0 = sC(ac.z1), a1 = sC(ac.z0);
    (function () {
      const sh = new T.Shape(); sh.moveTo(0, 0); sh.lineTo(Dp, 0); sh.lineTo(Dp, H); sh.lineTo(0, H); sh.lineTo(0, 0);
      const h1 = new T.Path(); h1.moveTo(s0, win.y0); h1.lineTo(s1, win.y0); h1.lineTo(s1, win.y1); h1.lineTo(s0, win.y1); h1.lineTo(s0, win.y0);
      const h2 = new T.Path(); h2.moveTo(a0, ac.y0); h2.lineTo(a1, ac.y0); h2.lineTo(a1, ac.y1); h2.lineTo(a0, ac.y1); h2.lineTo(a0, ac.y0);
      sh.holes.push(h1, h2);
      batch.add('wallC', new T.ShapeGeometry(sh), mC);
    })();
    C.box('wallCr', s0 - 0.03, s0, win.y0 - 0.03, win.y1 + 0.03, -0.11, -0.001);
    C.box('wallCr', s1, s1 + 0.03, win.y0 - 0.03, win.y1 + 0.03, -0.11, -0.001);
    C.box('wallCr', s0, s1, win.y1, win.y1 + 0.03, -0.11, -0.001);
    C.box('marble', s0 - 0.012, s1 + 0.012, win.y0 - 0.028, win.y0, -0.11, 0.014);
    const fr = 0.04, n0 = -0.08, n1 = -0.035, yTr = win.y1 - 0.30, sm = (s0 + s1) / 2;
    C.box('alu', s0, s1, win.y1 - fr, win.y1, n0, n1); C.box('alu', s0, s1, win.y0, win.y0 + fr, n0, n1);
    C.box('alu', s0, s0 + fr, win.y0, win.y1, n0, n1); C.box('alu', s1 - fr, s1, win.y0, win.y1, n0, n1);
    C.box('alu', s0, s1, yTr - 0.02, yTr + 0.02, n0, n1);
    C.box('alu', sm - 0.02, sm + 0.02, yTr, win.y1, n0, n1);
    const sash = function (a, b, y0, y1, n) {
      const k = 0.03;
      C.box('alu', a, b, y0, y0 + k, n - 0.011, n + 0.011); C.box('alu', a, b, y1 - k, y1, n - 0.011, n + 0.011);
      C.box('alu', a, a + k, y0, y1, n - 0.011, n + 0.011); C.box('alu', b - k, b, y0, y1, n - 0.011, n + 0.011);
      C.box('glassW', a + k, b - k, y0 + k, y1 - k, n - 0.002, n + 0.002);
    };
    sash(s0 + fr, sm + 0.02, win.y0 + fr, yTr - 0.02, -0.047);
    sash(sm - 0.02, s1 - fr, win.y0 + fr, yTr - 0.02, -0.068);
    C.box('glassW', s0 + fr, sm - 0.02, yTr + 0.02, win.y1 - fr, -0.06, -0.056);
    C.box('glassW', sm + 0.02, s1 - fr, yTr + 0.02, win.y1 - fr, -0.06, -0.056);
    C.box('alu', sm - 0.012, sm + 0.012, win.y0 + 0.5, win.y0 + 0.58, -0.036, -0.022);          // fecho
    C.box('alu', s0 + 0.2, s0 + 0.34, yTr + 0.03, yTr + 0.05, -0.05, -0.028);                   // alavancas do basculante
    C.box('alu', s1 - 0.34, s1 - 0.2, yTr + 0.03, yTr + 0.05, -0.05, -0.028);
    // ar-condicionado de janela
    C.box('woodAC', a0 - 0.028, a0, ac.y0 - 0.028, ac.y1 + 0.028, -0.04, 0.012, 'y');
    C.box('woodAC', a1, a1 + 0.028, ac.y0 - 0.028, ac.y1 + 0.028, -0.04, 0.012, 'y');
    C.box('woodAC', a0, a1, ac.y1, ac.y1 + 0.028, -0.04, 0.012, 'x');
    C.box('woodAC', a0, a1, ac.y0 - 0.028, ac.y0, -0.04, 0.012, 'x');
    C.box('acBody', a0 + 0.004, a1 - 0.004, ac.y0 + 0.004, ac.y1 - 0.004, -0.14, 0.03);
    const lv1 = a0 + (a1 - a0) * 0.7;
    for (let y = ac.y0 + 0.035; y < ac.y1 - 0.03; y += 0.03) C.box('acLouver', a0 + 0.025, lv1 - 0.01, y, y + 0.012, 0.03, 0.04);
    C.box('acLouver', a0 + 0.015, a0 + 0.025, ac.y0 + 0.025, ac.y1 - 0.025, 0.03, 0.042);
    C.box('acLouver', lv1 - 0.01, lv1, ac.y0 + 0.025, ac.y1 - 0.025, 0.03, 0.042);
    C.box('acLouver', lv1 + 0.012, a1 - 0.02, ac.y0 + 0.03, ac.y1 - 0.03, 0.03, 0.036);
    [0.6, 0.36].forEach(function (f) {
      const g = new T.CylinderGeometry(0.02, 0.022, 0.02, 20); g.rotateX(Math.PI / 2);
      g.translate((lv1 + a1) / 2, ac.y0 + (ac.y1 - ac.y0) * f, 0.046); batch.add('darkC', g, mC);
    });
    const so = sC(MEAS.acOutletZ), yo = MEAS.acOutletY;
    C.outletWhite(so, yo, 0);
    (function () {   // cabo de força do ar-condicionado, solto até a tomada
      const pts = [[a1 - 0.07, ac.y0 + 0.03, 0.04], [a1 - 0.05, 0.3, 0.055], [a1 + 0.02, 0.2, 0.05], [so - 0.05, 0.24, 0.035], [so - 0.006, yo - 0.03, 0.02], [so, yo, 0.012]].map(function (q) { return V3(q[0], q[1], q[2]); });
      batch.add('darkC', new T.TubeGeometry(new T.CatmullRomCurve3(pts), 40, 0.0045, 6, false), mC);
    })();
    C.box('woodDark', dB, Dp, 0, 0.07, 0, 0.012, 'x');                                           // rodapé
    // varão da cortina
    (function () {
      const ra = sC(Math.min(win.z1 + 0.2, LA - 0.05)), rb = sC(0.07), yy = Math.min(win.y1 + 0.11, H - 0.1);
      let g = new T.CylinderGeometry(0.014, 0.014, rb - ra, 14); g.rotateZ(Math.PI / 2); g.translate((ra + rb) / 2, yy, 0.07); C.geo('rodC', g, 'x');
      [ra, rb].forEach(function (s) { const b = new T.SphereGeometry(0.024, 14, 10); b.translate(s, yy, 0.07); C.geo('rodC', b, 'x'); });
      [ra + 0.12, rb - 0.12].forEach(function (s) { C.box('rodC', s - 0.012, s + 0.012, yy - 0.014, yy + 0.014, 0, 0.07, 'z'); });
    })();

    /* ================= PAREDE D (norte, branca): lisa de ponta a ponta ================= */
    const dFree = W - MEAS.doorW - 0.01;                                // trecho livre com a folha da porta aberta encostada
    (function () { const g = new T.PlaneGeometry(W, H); g.translate(W / 2, H / 2, 0); batch.add('wallD', g, mD); })();
    D.box('woodDark', 0, W, 0, 0.07, 0, 0.012, 'x');
    D.outletBrass(MEAS.dOutletX, 0.30, 0, true);
    (function () {   // interruptor
      const sx = dFree - 0.09;
      D.box('ivory', sx - 0.037, sx + 0.037, 1.07, 1.185, 0, 0.007); D.box('ivory', sx - 0.011, sx + 0.011, 1.1, 1.155, 0.007, 0.011);
    })();

    /* ================= PAREDE A, trecho da porta (entre a parede D e a torre) ================= */
    const cas = Math.max(0.05, (zA - MEAS.doorW) / 2 - 0.004), dx0 = (zA - MEAS.doorW) / 2 - 0.002, dx1 = dx0 + MEAS.doorW, dh = Math.min(MEAS.doorH, H - 0.25);
    (function () {
      const sh = new T.Shape(); sh.moveTo(0, 0); sh.lineTo(dx0, 0); sh.lineTo(dx0, dh); sh.lineTo(dx1, dh); sh.lineTo(dx1, 0);
      sh.lineTo(Dp, 0); sh.lineTo(Dp, H); sh.lineTo(0, H); sh.lineTo(0, 0);
      batch.add('wallD', new T.ShapeGeometry(sh), mA);
    })();
    AW.box('woodDark', dx0 - cas, dx0, 0, dh + cas, 0, 0.014, 'y');
    AW.box('woodDark', dx1, dx1 + cas, 0, dh + cas, 0, 0.014, 'y');
    AW.box('woodDark', dx0, dx1, dh, dh + cas, 0, 0.014, 'x');
    AW.box('woodDark', dx0 - 0.02, dx0, 0, dh, -0.13, 0.002, 'y');
    AW.box('woodDark', dx1, dx1 + 0.02, 0, dh, -0.13, 0.002, 'y');
    AW.box('woodDark', dx0 - 0.02, dx1 + 0.02, dh, dh + 0.02, -0.13, 0.002, 'x');

    /* paredes ocultas atrás dos armários, teto e piso */
    (function () {
      let g = new T.PlaneGeometry(W, H); g.translate(W / 2 - dA, H / 2, 0); batch.add('wallAB', g, mB);
      g = new T.PlaneGeometry(W, Dp); g.rotateX(Math.PI / 2); g.translate(W / 2, H, Dp / 2); batch.add('ceil', g);
    })();
    const meshes = batch.build(M, group);

    const floorGeo = new T.PlaneGeometry(W, Dp); floorGeo.rotateX(-Math.PI / 2); floorGeo.translate(W / 2, 0, Dp / 2);
    (function () { const p = floorGeo.attributes.position, uv = floorGeo.attributes.uv; for (let i = 0; i < p.count; i++) uv.setXY(i, (p.getX(i) - MEAS.tileOx) / (MEAS.tile * 2), (p.getZ(i) - MEAS.tileOz) / (MEAS.tile * 2)); })();
    const floor = new T.Mesh(floorGeo, M.floor); floor.receiveShadow = true; floor.name = 'floor'; group.add(floor);

    /* porta (folha articulada) + corredor */
    const doorRoot = new T.Group(); doorRoot.applyMatrix4(mA); group.add(doorRoot);
    const doorPivot = new T.Group(); doorPivot.position.set(dx0 + 0.003, 0, 0); doorRoot.add(doorPivot);
    (function () {
      const dw = dx1 - dx0 - 0.006, g = new T.BoxGeometry(dw, dh - 0.012, 0.036); woodUV(g, 'y'); g.translate(dw / 2, dh / 2 + 0.002, -0.022);
      const leaf = new T.Mesh(g, M.doorWood); leaf.castShadow = leaf.receiveShadow = true; doorPivot.add(leaf);
      const hb = new Batch();
      [[-0.004, 1], [-0.04, -1]].forEach(function (f) {
        const zf = f[0], sg = f[1];
        let p = new T.BoxGeometry(0.04, 0.17, 0.006); p.translate(dw - 0.06, 1.0, zf + sg * 0.003); hb.add('m', p);
        p = new T.CylinderGeometry(0.009, 0.009, 0.045, 10); p.rotateX(Math.PI / 2); p.translate(dw - 0.06, 1.04, zf + sg * 0.0225); hb.add('m', p);
        p = new T.BoxGeometry(0.115, 0.017, 0.014); p.translate(dw - 0.06 - 0.05, 1.04, zf + sg * 0.045); hb.add('m', p);
        p = new T.CylinderGeometry(0.014, 0.014, 0.008, 16); p.rotateX(Math.PI / 2); p.translate(dw - 0.06, 0.93, zf + sg * 0.004); hb.add('m', p);
      });
      [0.25, 1.05, 1.85].forEach(function (y) { const p = new T.CylinderGeometry(0.007, 0.007, 0.1, 10); p.translate(0.0, Math.min(y, dh - 0.2), 0.002); hb.add('m', p); });
      hb.build({ m: M.darkMetal }, doorPivot);
    })();
    const hall = new T.Group(); hall.visible = false; doorRoot.add(hall);
    (function () {
      const hx0 = -0.5, hx1 = dx1 + 0.6;
      const hg = new T.BoxGeometry(hx1 - hx0, H, 1.3), hi = Array.from(hg.index.array); hi.splice(24, 6); hg.setIndex(hi);   // sem a face voltada para o quarto
      const box = new T.Mesh(hg, M.hall); box.position.set((hx0 + hx1) / 2, H / 2, -0.13 - 0.65); box.receiveShadow = true; box.castShadow = true; hall.add(box);
      const fg = new T.PlaneGeometry(hx1 - hx0, 1.43); fg.rotateX(-Math.PI / 2); fg.translate((hx0 + hx1) / 2, 0.001, -0.715);
      const p = fg.attributes.position, uv = fg.attributes.uv; for (let i = 0; i < p.count; i++) uv.setXY(i, (W - p.getZ(i) - MEAS.tileOx) / (MEAS.tile * 2), (p.getX(i) - MEAS.tileOz) / (MEAS.tile * 2));
      const fm = new T.Mesh(fg, M.floorHall); fm.receiveShadow = true; hall.add(fm);
      // espessura da parede em volta da porta (bloqueia a luz do quarto)
      const wb = new Batch();
      const add = function (x0, x1, y0, y1) { const g = new T.BoxGeometry(x1 - x0, y1 - y0, 0.125); g.translate((x0 + x1) / 2, (y0 + y1) / 2, -0.066); wb.add('w', g); };
      add(hx0, dx0 - 0.02, 0, H); add(dx1 + 0.02, hx1, 0, H); add(dx0 - 0.02, dx1 + 0.02, dh + 0.02, H);
      const ms = wb.build({ w: M.wallD }, hall);
      ms.w.castShadow = true;
    })();

    /* luminária de teto */
    const lampPos = V3(LB / 2 + 0.12, H - 0.11, LA / 2 + 0.1);
    const fixture = new T.Group(); fixture.position.set(lampPos.x, H, lampPos.z); group.add(fixture);
    const fixBase = new T.Mesh(new T.CylinderGeometry(0.15, 0.15, 0.018, 40), M.fixture); fixBase.position.y = -0.009; fixture.add(fixBase);
    const dome = new T.SphereGeometry(0.14, 36, 14, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2); dome.scale(1, 0.42, 1);
    const fixGlow = new T.Mesh(dome, M.fixture); fixGlow.position.y = -0.016; fixture.add(fixGlow);
    const lamp = new T.PointLight(0xffffff, 12, 0, 2.001);
    lamp.position.copy(lampPos); lamp.castShadow = true;
    lamp.shadow.mapSize.set(1024, 1024); lamp.shadow.camera.near = 0.06; lamp.shadow.camera.far = 8;
    lamp.shadow.bias = -0.0025; lamp.shadow.normalBias = 0.025; lamp.shadow.radius = 2.2;
    group.add(lamp);

    /* sol pela janela (modo dia) + vista */
    const sun = new T.DirectionalLight(0xfff0d8, 0);
    const sunTarget = V3(W * 0.55, 0, (win.z0 + win.z1) / 2 + 0.25), sunDir = V3(1, -1.12, 0.28).normalize();
    sun.position.copy(sunTarget).addScaledVector(sunDir, -6); sun.target.position.copy(sunTarget);
    sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048);
    const se = Math.max(W, Dp) * 1.12, sc = sun.shadow.camera; sc.left = -se; sc.right = se; sc.top = se; sc.bottom = -se; sc.near = 0.5; sc.far = 14;
    sun.shadow.bias = -0.0006; sun.shadow.normalBias = 0.02; sun.shadow.radius = 2.5;
    sun.visible = false; group.add(sun); group.add(sun.target);
    const backMat = Q.mEmis('#ffffff', 0.5);
    const sky = new T.RectAreaLight(0xc4dcff, 0, win.z1 - win.z0, win.y1 - win.y0);
    sky.position.set(0.03, (win.y0 + win.y1) / 2, (win.z0 + win.z1) / 2); sky.lookAt(1, (win.y0 + win.y1) / 2, (win.z0 + win.z1) / 2); sky.visible = false; group.add(sky);
    const backdrop = new T.Mesh(new T.PlaneGeometry(5.2, 3.6), backMat);
    backdrop.rotation.y = Math.PI / 2; backdrop.position.set(-0.75, 1.75, (win.z0 + win.z1) / 2);
    group.add(backdrop);

    /* cortina (voil) */
    const curtain = new T.Group(); curtain.visible = false; group.add(curtain);
    (function () {
      const ra = Math.min(win.z1 + 0.16, LA - 0.07), cw = ra - 0.1, yy = Math.min(win.y1 + 0.11, H - 0.1), ch = yy - 0.86;
      const g = new T.PlaneGeometry(cw, ch, 120, 6), p = g.attributes.position;
      for (let i = 0; i < p.count; i++) {
        const x = p.getX(i), y = p.getY(i), k = 0.55 + 0.45 * (0.5 - y / ch);
        p.setZ(i, (0.026 * Math.sin(x * 57) + 0.011 * Math.sin(x * 131 + 1.3)) * k);
      }
      g.computeVertexNormals();
      const m = new T.Mesh(g, new T.MeshStandardMaterial({ color: '#f4f1ea', roughness: 0.9, side: T.DoubleSide, transparent: true, opacity: 0.86 }));
      m.rotation.y = Math.PI / 2; m.position.set(0.085, yy - ch / 2 - 0.012, 0.1 + cw / 2); m.receiveShadow = true;
      curtain.add(m); curtain.userData.mat = m.material;
    })();

    /* fitas de LED */
    const leds = { cove: [], shelf: [] };
    const emCove = Q.mEmis('#3d6bff', 7), emShelf = Q.mEmis('#ffb46a', 7);
    const strip = function (list, mat, p0, p1, emit) {
      const dir = new T.Vector3().subVectors(p1, p0), len = dir.length(), mid = p0.clone().add(p1).multiplyScalar(0.5);
      const mesh = new T.Mesh(new T.BoxGeometry(len, 0.009, 0.004), mat); orient(mesh, dir, emit); mesh.position.copy(mid);
      const e = emit.clone().normalize();
      mesh.visible = false; group.add(mesh);
      list.push({ mesh: mesh, a: p0.clone().addScaledVector(e, 0.005), b: p1.clone().addScaledVector(e, 0.005), e: e, len: len });
    };
    const yC = H - 0.008;
    strip(leds.cove, emCove, V3(0.014, yC, 0.02), V3(0.014, yC, LA - 0.02), V3(0.38, -1, 0));
    strip(leds.cove, emCove, V3(0.02, yC, 0.014), V3(W - 0.02, yC, 0.014), V3(0, -1, 0.38));
    strip(leds.cove, emCove, V3(W - 0.014, yC, 0.02), V3(W - 0.014, yC, zA - 0.01), V3(-0.38, -1, 0));
    strip(leds.cove, emCove, V3(LB - wFu - 0.014, yC, zA + 0.01), V3(LB - wFu - 0.014, yC, LA - 0.03), V3(-0.38, -1, 0));
    strip(leds.cove, emCove, V3(0.02, yC, LA - wFu - 0.014), V3(LB - 0.03, yC, LA - wFu - 0.014), V3(0, -1, -0.38));
    const sStrip = function (m, u0, u1, y) {
      strip(leds.shelf, emShelf, V3(u0 + 0.015, y - 0.003, 0.034).applyMatrix4(m), V3(u1 - 0.015, y - 0.003, 0.034).applyMatrix4(m), V3(0, -1, 0));
    };
    sStrip(mA2, t, uT - t, yUp); sStrip(mA2, t, uT - t, MEAS.towerShelf);
    sStrip(mA2, uT, uD - t, yUp); sStrip(mA2, uT, uD - t, MEAS.shelf2); sStrip(mA2, uT, uD - t, MEAS.shelf1);
    sStrip(mB, uN + nL, LB - nR, yUp); sStrip(mB, uN + nL, LB - nR, MEAS.nicheShelf2); sStrip(mB, uN + nL, LB - nR, MEAS.nicheShelf1);

    /* ---------- superfícies de apoio, paredes para pendurar e obstáculos ---------- */
    const surfaces = [];
    const surf = function (name, m, u0, u1, w0, w1, y, clear) {
      surfaces.push({ name: name, m: m, inv: m.clone().invert(), u0: u0, u1: u1, w0: w0, w1: w1, y: y, clear: clear, owner: null });
    };
    surf('floor', mD, 0, W, 0, Dp, 0, H);
    surf('torre', mA2, t, uT - t, 0.014, dA, 0.779, MEAS.towerShelf - 0.779);
    surf('torre-prateleira', mA2, t, uT - t, 0.014, 0.34, MEAS.towerShelf + 0.036, yUp - 0.13 - MEAS.towerShelf - 0.036);
    surf('bancada', mA2, uT, uD - t, 0.014, dA + 0.01, 0.769, MEAS.shelf1 - 0.769);
    surf('bandeja', mA2, uT + 0.02, uDu - 0.035, 0.13, dA + 0.13, 0.648, 0.085);
    surf('bancada-prat1', mA2, uT, uD - t, 0.014, 0.28, MEAS.shelf1 + 0.036, MEAS.shelf2 - MEAS.shelf1 - 0.036);
    surf('bancada-prat2', mA2, uT, uD - t, 0.014, 0.3, MEAS.shelf2 + 0.036, yUp - 0.13 - MEAS.shelf2 - 0.036);
    surf('nicho-prat1', mB, uN + nL, LB - nR, 0.014, 0.37, MEAS.nicheShelf1 + 0.036, MEAS.nicheShelf2 - MEAS.nicheShelf1 - 0.036);
    surf('nicho-prat2', mB, uN + nL, LB - nR, 0.014, 0.37, MEAS.nicheShelf2 + 0.036, yUp - 0.13 - MEAS.nicheShelf2 - 0.036);

    const walls = [];
    const wall = function (name, m, n, s0_, s1_, y0, y1) {
      const mm = m.clone().multiply(new T.Matrix4().makeTranslation(0, 0, n));
      walls.push({ name: name, m: mm, inv: mm.clone().invert(), s0: s0_, s1: s1_, y0: y0, y1: y1 });
    };
    wall('janela-esq', mC, 0, dB + 0.03, s0 - 0.05, 0.1, H - 0.04);
    if (a0 - 0.06 - (s0 - 0.05) > 0.25) wall('janela-baixo', mC, 0, s0 - 0.05, a0 - 0.06, 0.1, win.y0 - 0.05);
    wall('porta', mD, 0, 0.02, W - 0.03, 0.1, H - 0.04);
    wall('torre-fundo', mA2, 0.012, t, uT - t, 0.79, MEAS.towerShelf - 0.01);
    wall('torre-fundo2', mA2, 0.012, t, uT - t, MEAS.towerShelf + 0.05, yUp - 0.14);
    wall('bancada-fundo', mA2, 0.012, uT, uD - t, 0.78, MEAS.shelf1 - 0.01);
    wall('nicho-fundo', mB, 0.012, uN + nL, LB - nR, 0.09, MEAS.nicheShelf1 - 0.01);

    const xN = LB - uN;   // limite do nicho em x (mundo)
    const obstacles = [
      { x0: LB, x1: W + 1, z0: zA, z1: zA + uT, y0: 0 },                                   // torre
      { x0: LB + 0.34, x1: W + 1, z0: zA + uT, z1: zA + uDu - 0.018, y0: 0.6 },            // fundo do vão da bancada (objetos altos)
      { x0: W - 0.014, x1: W + 1, z0: zA + uT, z1: zA + uDu - 0.018, y0: 0 },
      { x0: LB, x1: W + 1, z0: zA + uDu - 0.018, z1: Dp + 1, y0: 0 },                      // gaveteiro + porta de canto
      { x0: xN - nL, x1: LB + 0.01, z0: LA, z1: Dp + 1, y0: 0 },                           // guarda-roupa
      { x0: -1, x1: nR, z0: LA, z1: Dp + 1, y0: 0 },                                       // lateral do nicho
      { x0: -1, x1: W + 1, z0: Dp - 0.026, z1: Dp + 1, y0: 0 },                            // fundo do nicho
      { x0: nR, x1: xN - nL, z0: Dp - 0.38, z1: Dp + 1, y0: MEAS.nicheShelf1 - 0.02 }      // prateleiras do nicho
    ];


    const toWorld = function (run, u, y, w) { return V3(u, y, w).applyMatrix4(run === 'A' ? mA2 : run === 'B' ? mB : run === 'C' ? mC : mD); };
    return {
      group: group, W: W, Dp: Dp, H: H, dA: dA, dB: dB, LA: LA, LB: LB, uT: uT, uD: uD, uDu: uDu, uN: uN, yUp: yUp, t: t, xN: xN,
      win: win, meshes: meshes, floor: floor, surfaces: surfaces, walls: walls, obstacles: obstacles, leds: leds,
      emCove: emCove, emShelf: emShelf, lamp: lamp, lampPos: lampPos, fixGlow: fixGlow, sun: sun, sunBase: sun.position.clone(),
      dx0: dFree, zA: zA, nicheC: (nR + xN - nL) / 2, nL: nL, nR: nR, backdrop: backdrop, sky: sky, door: doorPivot, hall: hall, curtain: curtain, toWorld: toWorld,
      center: V3(LB * 0.5, Math.min(1.55, H - 0.6), LA * 0.5)
    };
  };
})();
