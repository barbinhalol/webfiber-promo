/* Quarto 3D — catálogo de objetos (modelados em 3D, medidas reais em metros) */
(function () {
  'use strict';
  const T = THREE, Q = window.Q, PI = Math.PI;
  const C = (Q.catalog = {});
  const def = function (id, o) { o.id = id; C[id] = o; };

  const V3 = function (x, y, z) { return new T.Vector3(x, y, z); };
  const mk = function (geo, mat, x, y, z) { const m = new T.Mesh(geo, mat); m.position.set(x || 0, y || 0, z || 0); return m; };
  const box = function (w, h, d) { return new T.BoxGeometry(w, h, d); };
  const rbox = function (w, h, d, r, s) { return new T.RoundedBoxGeometry(w, h, d, s || 3, r); };
  const cyl = function (rt, rb, h, seg) { return new T.CylinderGeometry(rt, rb, h, seg || 24); };
  const sph = function (r, a, b) { return new T.SphereGeometry(r, a || 20, b || 14); };
  function tint(g, color) {
    const c = color.isColor ? color : new T.Color(color), n = g.attributes.position.count, a = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) { a[i * 3] = c.r; a[i * 3 + 1] = c.g; a[i * 3 + 2] = c.b; }
    g.setAttribute('color', new T.BufferAttribute(a, 3)); return g;
  }
  function clean(g) {
    if (g.index) { const n = g.toNonIndexed(); g.dispose(); g = n; }
    Object.keys(g.attributes).forEach(function (k) { if (['position', 'normal', 'uv', 'color'].indexOf(k) < 0) g.deleteAttribute(k); });
    if (!g.attributes.uv) g.setAttribute('uv', new T.BufferAttribute(new Float32Array(g.attributes.position.count * 2), 2));
    if (!g.attributes.normal) g.computeVertexNormals();
    return g;
  }
  function merge(list) { const l = list.map(clean), g = T.BufferGeometryUtils.mergeBufferGeometries(l, false); l.forEach(function (x) { x.dispose(); }); return g; }
  function roundRect(w, d, r) {
    const s = new T.Shape(), x = -w / 2, y = -d / 2;
    s.moveTo(x + r, y); s.lineTo(x + w - r, y); s.absarc(x + w - r, y + r, r, -PI / 2, 0, false);
    s.lineTo(x + w, y + d - r); s.absarc(x + w - r, y + d - r, r, 0, PI / 2, false);
    s.lineTo(x + r, y + d); s.absarc(x + r, y + d - r, r, PI / 2, PI, false);
    s.lineTo(x, y + r); s.absarc(x + r, y + r, r, PI, PI * 1.5, false);
    return s;
  }
  function slab(w, d, r, h) { const g = new T.ExtrudeGeometry(roundRect(w, d, r), { depth: h, bevelEnabled: false, curveSegments: 8 }); g.rotateX(-PI / 2); return g; }
  function planarUV(g, s) { const p = g.attributes.position, uv = g.attributes.uv; for (let i = 0; i < p.count; i++) uv.setXY(i, p.getX(i) * s, p.getZ(i) * s); return g; }

  /* junta as malhas de um objeto por material (poucas chamadas de desenho) */
  Q.optimize = function (group) {
    group.updateMatrixWorld(true);
    const inv = group.matrixWorld.clone().invert(), buckets = {}, keep = [], src = [];
    group.traverse(function (o) {
      if (o === group) return;
      if (o.isMesh && !o.userData.keep) src.push(o);
      else if (o.isLight || (o.isMesh && o.userData.keep)) keep.push({ o: o, m: new T.Matrix4().multiplyMatrices(inv, o.matrixWorld) });
    });
    src.forEach(function (o) {
      const g = clean(o.geometry.clone());
      g.applyMatrix4(new T.Matrix4().multiplyMatrices(inv, o.matrixWorld));
      const key = o.material.uuid + '|' + (g.attributes.color ? 1 : 0) + '|' + o.layers.mask + '|' + (o.castShadow ? 1 : 0) + '|' + o.renderOrder;
      (buckets[key] = buckets[key] || { o: o, list: [] }).list.push(g);
      o.geometry.dispose();
    });
    group.clear();
    Object.keys(buckets).forEach(function (k) {
      const b = buckets[k], g = b.list.length > 1 ? T.BufferGeometryUtils.mergeBufferGeometries(b.list, false) : b.list[0];
      if (b.list.length > 1) b.list.forEach(function (x) { x.dispose(); });
      const m = new T.Mesh(g, b.o.material);
      m.castShadow = b.o.castShadow; m.receiveShadow = b.o.receiveShadow; m.layers.mask = b.o.layers.mask; m.renderOrder = b.o.renderOrder;
      group.add(m);
    });
    keep.forEach(function (k) { k.m.decompose(k.o.position, k.o.quaternion, k.o.scale); group.add(k.o); });
    return group;
  };

  Q.makeObject = function (type, p, seed) {
    const d = C[type], g = d.build(p || {}, seed || 1);
    g.traverse(function (o) {
      if (!o.isMesh) return;
      const m = o.material, soft = m.isMeshBasicMaterial || m.transparent;
      o.castShadow = !soft && !o.userData.noShadow; o.receiveShadow = !soft;
      if (m.transparent) { o.layers.set(1); o.renderOrder = 6; }
    });
    if (!d.articulated) Q.optimize(g);
    g.userData.size = g.userData.size || d.size;
    return g;
  };
  Q.disposeObject = function (g) {
    g.traverse(function (o) {
      if (o.geometry) o.geometry.dispose();
      const m = o.material;
      if (m && !m.userData.shared) { if (m.map && m.userData.ownMap) m.map.dispose(); m.dispose(); }
    });
  };

  const SHARED = function (m) { m.userData.shared = true; return m; };

  /* ---------------- SETUP ---------------- */
  function fan(em, white, dark) {
    const g = new T.Group();
    g.add(mk(rbox(0.116, 0.02, 0.116, 0.008, 2), white, 0, 0.01, 0));
    g.add(mk(cyl(0.052, 0.052, 0.003, 32), dark, 0, 0.0215, 0));
    g.add(mk(cyl(0.017, 0.017, 0.008, 20), white, 0, 0.025, 0));
    for (let i = 0; i < 7; i++) {
      const b = mk(box(0.032, 0.002, 0.02), white, 0, 0.025, 0), a = (i / 7) * PI * 2;
      b.position.set(Math.cos(a) * 0.031, 0.025, Math.sin(a) * 0.031); b.rotation.set(0.35, -a, 0, 'YXZ'); g.add(b);
    }
    const ring = mk(new T.TorusGeometry(0.0505, 0.004, 8, 40), em, 0, 0.024, 0); ring.rotation.x = PI / 2; g.add(ring);
    return g;
  }
  def('pc', {
    name: 'Gabinete', cat: 'Setup', size: [0.285, 0.405, 0.44], mount: 'surface',
    defaults: { color: '#3d6bff', on: true }, controls: { color: 'Cor do RGB', on: 'RGB ligado' },
    tops: [{ x0: -0.14, x1: 0.14, z0: -0.21, z1: 0.21, y: 0.405, clear: 0.6 }],
    build: function (p) {
      const g = new T.Group(), w = 0.285, h = 0.405, d = 0.44, xs = 0.04, cx = (-w / 2 + xs) / 2;
      const white = Q.mPlastic('#f3f3f1', 0.42), dark = Q.mPlastic('#141518', 0.6), gray = Q.mPlastic('#c9cacd', 0.5);
      const em = p.on ? Q.mEmis(p.color, 3.2) : gray;
      g.add(mk(rbox(w, 0.034, d, 0.006, 2), white, 0, 0.029, 0));
      g.add(mk(rbox(w, 0.02, d, 0.006, 2), white, 0, h - 0.01, 0));
      g.add(mk(box(w, h - 0.06, 0.012), white, 0, h / 2 + 0.006, -d / 2 + 0.006));
      g.add(mk(rbox(w / 2 - xs, h - 0.03, d, 0.006, 2), white, (xs + w / 2) / 2, h / 2 + 0.006, 0));
      for (let k = 0; k < 5; k++) g.add(mk(box(0.0045, h - 0.13, 0.002), gray, xs + 0.018 + k * 0.017, h / 2 + 0.006, d / 2 + 0.0006));
      g.add(mk(box(0.012, h - 0.05, 0.012), white, -w / 2 + 0.006, h / 2 + 0.006, d / 2 - 0.006));
      [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(function (s) { g.add(mk(cyl(0.012, 0.012, 0.012, 12), dark, s[0] * (w / 2 - 0.03), 0.006, s[1] * (d / 2 - 0.04))); });
      // interior
      g.add(mk(box(0.004, h - 0.09, d - 0.07), dark, xs - 0.002, h / 2 + 0.012, -0.012));
      g.add(mk(rbox(0.13, 0.042, 0.27, 0.006, 2), white, xs - 0.07, 0.185, -0.03));
      g.add(mk(box(0.003, 0.008, 0.23), em, xs - 0.1365, 0.185, -0.03));
      const pump = mk(cyl(0.032, 0.032, 0.03, 28), dark, xs - 0.02, 0.3, -0.03); pump.rotation.z = PI / 2; g.add(pump);
      const pr = mk(new T.TorusGeometry(0.026, 0.004, 8, 32), em, xs - 0.037, 0.3, -0.03); pr.rotation.y = PI / 2; g.add(pr);
      [0.05, 0.066].forEach(function (z) { g.add(mk(box(0.03, 0.1, 0.006), dark, xs - 0.018, 0.3, z)); g.add(mk(box(0.031, 0.01, 0.0062), em, xs - 0.018, 0.354, z)); });
      [-0.135, -0.012, 0.111].forEach(function (z) { const f = fan(em, white, dark); f.position.set(cx, 0.046, z); g.add(f); });
      [-0.075, 0.06].forEach(function (z) { const f = fan(em, white, dark); f.rotation.x = PI; f.position.set(cx, h - 0.02, z); g.add(f); });
      const rf = fan(em, white, dark); rf.rotation.x = PI / 2; rf.position.set(cx, 0.3, -d / 2 + 0.012); g.add(rf);
      g.add(mk(box(w / 2 + xs - 0.01, h - 0.062, 0.004), SHARED(Q.M.glassPC), cx - 0.001, h / 2 + 0.006, d / 2 - 0.002));
      g.add(mk(box(0.004, h - 0.062, d - 0.016), SHARED(Q.M.glassPC), -w / 2 + 0.002, h / 2 + 0.006, 0));
      if (p.on) { const l = new T.PointLight(p.color, 0.1, 0.7, 2); l.position.set(cx - 0.02, 0.21, 0.05); g.add(l); }
      return g;
    }
  });

  def('monitor', {
    name: 'Monitor', cat: 'Setup', size: [0.615, 0.46, 0.2], mount: 'surface',
    defaults: { color: '#3d6bff', on: true }, controls: { color: 'Cor da tela', on: 'Tela ligada' },
    build: function (p) {
      const g = new T.Group(), black = Q.mPlastic('#0c0c0e', 0.5);
      g.add(mk(rbox(0.25, 0.012, 0.19, 0.005, 2), black, 0, 0.006, -0.005));
      const neck = mk(box(0.052, 0.25, 0.02), black, 0, 0.135, -0.07); neck.rotation.x = -0.1; g.add(neck);
      const pn = new T.Group(); pn.position.set(0, 0.277, -0.012); pn.rotation.x = -0.06; g.add(pn);
      pn.add(mk(rbox(0.614, 0.364, 0.014, 0.004, 2), black, 0, 0, 0));
      pn.add(mk(rbox(0.38, 0.22, 0.03, 0.012, 2), black, 0, -0.01, -0.02));
      let sm;
      if (p.on) { sm = Q.mEmis('#ffffff', 2.1, { map: Q.makeWallpaper(p.color) }); sm.userData.ownMap = true; }
      else sm = new T.MeshStandardMaterial({ color: '#030304', roughness: 0.12 });
      pn.add(mk(new T.PlaneGeometry(0.598, 0.337), sm, 0, 0.006, 0.0074));
      if (p.on) {
        const l = new T.RectAreaLight(new T.Color(p.color).lerp(new T.Color(1, 1, 1), 0.45), 17, 0.598, 0.337);
        l.position.set(0, 0.006, 0.02); l.rotation.y = PI; pn.add(l);
      }
      return g;
    }
  });

  def('teclado', {
    name: 'Teclado', cat: 'Setup', size: [0.318, 0.03, 0.108], mount: 'surface',
    defaults: { color: '#3d6bff', on: true }, controls: { color: 'Cor da luz', on: 'Luz ligada' },
    build: function (p) {
      const g = new T.Group(), white = Q.mPlastic('#f4f4f2', 0.5);
      g.add(mk(rbox(0.318, 0.018, 0.108, 0.006, 2), white, 0, 0.009, 0));
      const rows = [[1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1], [1.5, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1.5, 1], [1.75, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2.25, 1],
        [2.25, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1.75, 1, 1], [1.25, 1.25, 1.25, 6.25, 1, 1, 1, 1, 1]], u = 0.019, keys = [];
      rows.forEach(function (row, r) {
        let x = -0.152;
        row.forEach(function (k) { const kg = box(k * u - 0.0026, 0.0075, u - 0.0026); kg.translate(x + (k * u) / 2, 0.0225, -0.038 + r * u); keys.push(kg); x += k * u; });
      });
      g.add(mk(merge(keys), Q.mPlastic('#fbfbfa', 0.55)));
      if (p.on) g.add(mk(box(0.305, 0.001, 0.096), Q.mEmis(p.color, 1.5), 0, 0.0186, 0));
      return g;
    }
  });

  def('mouse', {
    name: 'Mouse', cat: 'Setup', size: [0.062, 0.036, 0.112], mount: 'surface', defaults: {}, controls: {},
    build: function () {
      const g = new T.Group(), s = sph(1, 24, 16); s.scale(0.031, 0.021, 0.056);
      g.add(mk(s, Q.mPlastic('#f4f4f2', 0.4), 0, 0.014, 0));
      const wl = mk(cyl(0.006, 0.006, 0.006, 12), Q.mPlastic('#2a2a2d', 0.6), 0, 0.031, -0.022); wl.rotation.z = PI / 2; g.add(wl);
      return g;
    }
  });

  def('mousepad', {
    name: 'Mousepad', cat: 'Setup', size: [0.78, 0.004, 0.3], mount: 'surface', thumbDir: [0.3, 1.1, 1], defaults: { color: '#1b1b21' }, controls: { color: 'Cor' },
    build: function (p) { const g = new T.Group(); g.add(mk(planarUV(slab(0.78, 0.3, 0.012, 0.0035), 6), Q.mFabric(p.color))); return g; }
  });

  def('cadeira', {
    name: 'Cadeira gamer', cat: 'Setup', size: [0.66, 1.3, 0.66], mount: 'floor', thumbDir: [-0.75, 0.4, -1], defaults: { color: '#fbfbfa' }, controls: { color: 'Cor da estrutura' },
    build: function (p) {
      const g = new T.Group(), white = Q.mPlastic(p.color, 0.4), black = Q.mPlastic('#111113', 0.6), fab = new T.MeshStandardMaterial({ color: '#0e0e10', roughness: 0.9 });   // tela (mesh) lisa, sem textura de ruído
      // base estrela: cinco pés afilados, rodízios duplos pretos com calota branca
      for (let i = 0; i < 5; i++) {
        const a = (i / 5) * PI * 2 + 0.3, leg = new T.Group(); leg.rotation.y = a; g.add(leg);
        const l1 = mk(rbox(0.058, 0.04, 0.18, 0.012, 2), white, 0, 0.097, 0.1); l1.rotation.x = 0.13; leg.add(l1);
        const l2 = mk(rbox(0.042, 0.03, 0.17, 0.011, 2), white, 0, 0.076, 0.245); l2.rotation.x = 0.1; leg.add(l2);
        leg.add(mk(cyl(0.01, 0.01, 0.04, 10), black, 0, 0.052, 0.315));
        leg.add(mk(rbox(0.03, 0.02, 0.05, 0.006, 2), black, 0, 0.046, 0.315));
        [-1, 1].forEach(function (sd) {
          const wh = mk(cyl(0.028, 0.028, 0.02, 22), black, sd * 0.016, 0.028, 0.318); wh.rotation.z = PI / 2; leg.add(wh);
          const hub = mk(cyl(0.017, 0.017, 0.006, 18), white, sd * 0.028, 0.028, 0.318); hub.rotation.z = PI / 2; leg.add(hub);
        });
      }
      g.add(mk(cyl(0.05, 0.06, 0.05, 28), white, 0, 0.105, 0));
      g.add(mk(cyl(0.023, 0.023, 0.14, 20), black, 0, 0.2, 0));
      [0.275, 0.305, 0.335, 0.365].forEach(function (y, k) { g.add(mk(cyl(0.036 - k * 0.002, 0.038 - k * 0.002, 0.03, 20), black, 0, y, 0)); });
      g.add(mk(rbox(0.24, 0.04, 0.26, 0.012, 2), black, 0, 0.412, 0.0));
      const lever = mk(cyl(0.006, 0.006, 0.16, 8), black, 0.17, 0.405, 0.03); lever.rotation.z = PI / 2; g.add(lever);
      g.add(mk(rbox(0.05, 0.016, 0.03, 0.005, 2), Q.mPlastic('#c8202a', 0.45), 0.25, 0.405, 0.03));
      // assento preto, espesso, com a frente arredondada
      g.add(mk(rbox(0.5, 0.12, 0.49, 0.056, 6), fab, 0, 0.48, 0.025));
      g.add(mk(rbox(0.46, 0.03, 0.44, 0.014, 2), black, 0, 0.432, 0.02));
      // braços brancos em T
      [-1, 1].forEach(function (sd) {
        g.add(mk(rbox(0.04, 0.05, 0.16, 0.012, 2), white, sd * 0.262, 0.44, 0.0));
        g.add(mk(rbox(0.036, 0.2, 0.056, 0.012, 2), white, sd * 0.285, 0.555, -0.01));
        g.add(mk(rbox(0.085, 0.03, 0.25, 0.013, 3), white, sd * 0.285, 0.672, 0.01));
        g.add(mk(rbox(0.074, 0.008, 0.22, 0.004, 2), Q.mPlastic('#d9d9d6', 0.75), sd * 0.285, 0.69, 0.01));
      });
      // suporte do encosto
      const br = mk(rbox(0.1, 0.16, 0.04, 0.014, 2), black, 0, 0.47, -0.225); br.rotation.x = -0.2; g.add(br);
      // encosto: tela preta + casca branca facetada, como na foto: espinha central em quilha, duas aberturas de cada lado
      // (triângulo em cima, quadrilátero embaixo) separadas por uma travessa diagonal, ombros salientes e cauda que desce atrás do assento
      const bk = new T.Group(); bk.position.set(0, 0.52, -0.25); bk.rotation.x = -0.13; g.add(bk);
      const V2 = function (q) { return new T.Vector2(q[0], q[1]); };
      const contour = [[0, -0.2], [0.045, -0.185], [0.075, -0.03], [0.11, 0.045], [0.205, 0.08], [0.238, 0.17], [0.242, 0.36], [0.234, 0.5], [0.256, 0.575], [0.216, 0.632], [0.2, 0.74], [0.186, 0.83], [0.13, 0.876],
        [0, 0.886], [0, 0.74], [0, 0.6], [0, 0.47], [0, 0.33], [0, 0.19], [0, 0.05]].map(V2);
      const holes = [[[0.078, 0.15], [0.19, 0.176], [0.198, 0.405], [0.1, 0.318]].map(V2), [[0.082, 0.475], [0.112, 0.395], [0.2, 0.53]].map(V2),
        [[0.09, 0.7]].map(V2), [[0.07, 0.585]].map(V2), [[0.14, 0.115]].map(V2), [[0.05, 0.1]].map(V2), [[0.035, -0.08]].map(V2), [[0.15, 0.79]].map(V2)];   // pontos extras = mais facetas
      const pts = [].concat.apply(contour, holes), tris = T.ShapeUtils.triangulateShape(contour, holes), nC = contour.length;
      const hsh = function (x, y) { const v = Math.sin(Math.round(x * 1000) * 12.9898 + Math.round(y * 1000) * 78.233) * 43758.5453; return v - Math.floor(v); };
      const rim = pts.map(function (q, k) { return k < 14 && q.x > 0.001; });       // borda externa
      const zOut = pts.map(function (q, k) {
        let d = 0.125 * (1 - Math.pow(Math.min(1, q.x / 0.25), 1.3));
        if (q.y > 0.62) d *= 0.72; if (q.y < 0.06) d *= 0.62;
        if (q.x < 0.001) d += (hsh(0, q.y) - 0.5) * 0.05; else if (!rim[k]) d += (hsh(q.x, q.y) - 0.4) * 0.062; else d = -0.03 - hsh(q.x, q.y) * 0.014;   // a borda dobra para a frente e abraça o encosto
        return -d;
      });
      const zIn = zOut.map(function (z) { return Math.min(z + 0.036, 0.046); });
      const pos = [], P3 = function (k, inner, mir) { return [mir ? -pts[k].x : pts[k].x, pts[k].y, inner ? zIn[k] : zOut[k]]; };
      [false, true].forEach(function (mir) {
        tris.forEach(function (f) { pos.push(P3(f[0], 0, mir), P3(f[1], 0, mir), P3(f[2], 0, mir), P3(f[0], 1, mir), P3(f[2], 1, mir), P3(f[1], 1, mir)); });
        const wall = function (i0, i1) { pos.push(P3(i0, 0, mir), P3(i1, 0, mir), P3(i1, 1, mir), P3(i0, 0, mir), P3(i1, 1, mir), P3(i0, 1, mir)); };
        for (let k = 0; k < nC; k++) { const k2 = (k + 1) % nC; if (pts[k].x > 0.001 || pts[k2].x > 0.001) wall(k, k2); }
        let o = nC; holes.forEach(function (hl) { if (hl.length > 2) for (let k = 0; k < hl.length; k++) wall(o + k, o + ((k + 1) % hl.length)); o += hl.length; });
      });
      const sg2 = new T.BufferGeometry(); sg2.setAttribute('position', new T.BufferAttribute(new Float32Array([].concat.apply([], pos)), 3)); sg2.computeVertexNormals();
      bk.add(mk(sg2, new T.MeshStandardMaterial({ color: p.color, roughness: 0.5, flatShading: true, side: T.DoubleSide }), 0, 0, 0));
      bk.add(mk(rbox(0.43, 0.8, 0.03, 0.014, 2), fab, 0, 0.44, 0.03));             // tela preta do encosto, inteiriça até o alto (sem almofada separada)
      return g;
    }
  });

  def('console', {
    name: 'Console', cat: 'Setup', size: [0.275, 0.065, 0.151], mount: 'surface', defaults: {}, controls: {},
    build: function () {
      const g = new T.Group();
      g.add(mk(rbox(0.275, 0.065, 0.151, 0.008, 2), Q.mPlastic('#f3f3f1', 0.45), 0, 0.0325, 0));
      g.add(mk(cyl(0.058, 0.058, 0.002, 36), Q.mPlastic('#0d0d0f', 0.7), 0.066, 0.0655, 0));
      g.add(mk(box(0.09, 0.004, 0.002), Q.mPlastic('#0d0d0f', 0.7), -0.06, 0.04, 0.0758));
      return g;
    }
  });

  def('microfone', {
    name: 'Microfone', cat: 'Setup', size: [0.1, 0.26, 0.1], mount: 'surface', defaults: {}, controls: {},
    build: function () {
      const g = new T.Group(), bm = Q.mMetal('#161618', 0.45), bp = Q.mPlastic('#0e0e10', 0.7);
      g.add(mk(cyl(0.05, 0.052, 0.012, 32), bm, 0, 0.006, 0));
      g.add(mk(cyl(0.006, 0.006, 0.12, 12), bm, 0, 0.07, 0));
      const cap = new T.Group(); cap.position.set(0, 0.185, 0); cap.rotation.x = 0.22; g.add(cap);
      cap.add(mk(cyl(0.026, 0.026, 0.1, 28), bp, 0, 0, 0));
      const top = sph(0.026, 24, 12); top.scale(1, 0.6, 1); cap.add(mk(top, bp, 0, 0.05, 0));
      cap.add(mk(cyl(0.0275, 0.0275, 0.012, 28), bm, 0, -0.02, 0));
      const yk = mk(new T.TorusGeometry(0.036, 0.004, 8, 28, PI), bm, 0, -0.03, 0); yk.rotation.z = PI; cap.add(yk);
      return g;
    }
  });

  def('caixa_som', {
    name: 'Caixa de som', cat: 'Setup', size: [0.11, 0.18, 0.12], mount: 'surface', defaults: {}, controls: {},
    build: function () {
      const g = new T.Group(), dk = Q.mPlastic('#19191b', 0.55), cone = Q.mPlastic('#2c2c30', 0.4);
      g.add(mk(rbox(0.11, 0.18, 0.12, 0.01, 2), dk, 0, 0.09, 0));
      [[0.065, 0.036], [0.14, 0.015]].forEach(function (s) {
        const c = mk(cyl(s[1], s[1], 0.004, 28), cone, 0, s[0], 0.061); c.rotation.x = PI / 2; g.add(c);
        const t = mk(new T.TorusGeometry(s[1], 0.003, 8, 28), Q.mMetal('#8a8c92', 0.3), 0, s[0], 0.062); g.add(t);
      });
      return g;
    }
  });

  Q.makeTvScreen = function (hex, banner, text) {
    const W = 768, H = 432, c = Q.canvas(W, H), ctx = c.getContext('2d'), r = Q.rng(Q.hash(hex) % 977 + 5);
    const hsl = {}; new T.Color(hex).getHSL(hsl);
    const mkc = function (dh, s, l) { return '#' + new T.Color().setHSL((hsl.h + dh + 1) % 1, s, l).getHexString(); };
    ctx.fillStyle = mkc(0, 0.5, 0.1); ctx.fillRect(0, 0, W, H);
    for (let i = 0; i < 110; i++) {   // colagem abstrata em tons da cor escolhida
      ctx.fillStyle = mkc((r() - 0.5) * 0.05, 0.3 + r() * 0.3, 0.12 + r() * 0.2); ctx.strokeStyle = mkc(0, 0.5, 0.07); ctx.lineWidth = 2.5;
      const x = r() * W, y = r() * H, s = 26 + r() * 70; ctx.beginPath(); ctx.ellipse(x, y, s, s * (0.5 + r() * 0.6), r() * 3.1, 0, 6.3); ctx.fill(); ctx.stroke();
    }
    const vg = ctx.createRadialGradient(W / 2, H / 2, H * 0.2, W / 2, H / 2, W * 0.62); vg.addColorStop(0, 'rgba(0,0,0,0)'); vg.addColorStop(1, 'rgba(0,0,0,0.55)'); ctx.fillStyle = vg; ctx.fillRect(0, 0, W, H);
    if (text) {
      const fs = 112; ctx.font = '800 ' + fs + 'px "Sora", "Arial Black", Impact, sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      const tw = Math.min(W * 0.66, ctx.measureText(text).width), bw = tw + 44, bh = fs * 1.08;
      ctx.fillStyle = banner; ctx.fillRect((W - bw) / 2, (H - bh) / 2, bw, bh); ctx.fillStyle = '#ffffff'; ctx.fillText(text, W / 2, H / 2 + fs * 0.05, W * 0.66);
    }
    const t = new T.CanvasTexture(c); t.encoding = T.sRGBEncoding; t.anisotropy = 4; return t;
  };
  def('tv', {
    name: 'TV', cat: 'Setup', size: [0.97, 0.62, 0.21], mount: 'surface',
    defaults: { color: '#2a4f9e', accent: '#d4202a', text: 'PLAY', pol: 43, on: true, film: false }, controls: { on: 'Tela ligada', film: 'Filme passando', text: 'Texto da tela', color: 'Cor do fundo', accent: 'Cor da faixa', pol: 'Tamanho' },
    build: function (p) {
      const g = new T.Group(), k = (p.pol || 43) / 43, w = 0.965 * k, h = 0.558 * k, black = Q.mPlastic('#0b0b0d', 0.45);
      g.add(mk(rbox(0.26 * k, 0.012, 0.19, 0.005, 2), black, 0, 0.006, 0));
      g.add(mk(box(0.05, 0.06, 0.03), black, 0, 0.04, -0.01));
      const pn = new T.Group(); pn.position.set(0, 0.055 + h / 2, 0.0); g.add(pn);
      pn.add(mk(rbox(w, h, 0.022, 0.004, 2), black, 0, 0, 0));
      pn.add(mk(rbox(w * 0.6, h * 0.55, 0.03, 0.01, 2), black, 0, -h * 0.08, -0.022));
      let sm;
      if (p.on && p.film) sm = Q.mEmis('#ffffff', 2.0, { map: Q.film.tex() });
      else if (p.on) { sm = Q.mEmis('#ffffff', 2.0, { map: Q.makeTvScreen(p.color, p.accent, String(p.text || '').toUpperCase().slice(0, 12)) }); sm.userData.ownMap = true; }
      else sm = new T.MeshStandardMaterial({ color: '#030304', roughness: 0.1 });
      pn.add(mk(new T.PlaneGeometry(w - 0.016, h - 0.016), sm, 0, 0, 0.0115));
      if (p.on) { const l = new T.RectAreaLight(new T.Color(p.color).lerp(new T.Color(1, 1, 1), 0.5), 9, w - 0.02, h - 0.02); l.position.set(0, 0, 0.03); l.rotation.y = PI; pn.add(l); if (p.film) { g.userData.film = true; g.userData.filmLight = l; } }
      g.userData.size = [w + 0.005, 0.06 + h, 0.21];
      return g;
    }
  });

  /* cinemática do suporte articulado (referencial da parede: x ao longo da parede, z para fora).
     Regras físicas: 1) a tela nunca entra na parede; 2) a placa de parede e os braços ficam sempre ATRÁS do painel, nunca na frente da tela. */
  /*IK*/
  Q.TV_OFF = 0.593;   // recolhida, a TV fica deslocada este tanto da placa de parede (braço esticado rente à parede, atrás dela)
  Q.tvArmIK = function (q, hw, hh) {
    const L = 0.3, zS = 0.03, back = 0.038, R = 2 * L - 0.004, zMax = zS + 2 * L - 0.014, cl = function (v, a, b) { return Math.min(b, Math.max(a, v)); };
    const lado = q.lado > 0 ? 1 : -1, rz = zS + 0.06, rx = lado * Math.sqrt(R * R - 0.06 * 0.06) * 0.9995;      // descanso: a placa fica numa ponta da TV
    const sw0 = (cl(+q.swivel || 0, -90, 90) * Math.PI) / 180, ti0 = (cl(+q.tilt || 0, -5, 20) * Math.PI) / 180, ex = cl(+q.ext || 0, 0, 1), sd = cl(+q.side || 0, -1, 1);
    const attempt = function (sw, ti) {
      const sn = Math.sin(sw), cs = Math.cos(sw), st = Math.sin(ti), ct = Math.cos(ti), tt = Math.abs(st / ct);
      // regra 1: nenhum canto do painel (girado e inclinado) encosta na parede
      const need = hw * Math.abs(sn) + cs * (hh * Math.abs(st) - back * ct) + 0.02; if (need > zMax) return null;
      const wz = cl(Math.max(rz + ex * (zMax - rz), need), rz, zMax), reachX = Math.sqrt(Math.max(0, R * R - (wz - zS) * (wz - zS)));
      // regra 2: a placa de parede fica atrás do plano do painel, com folga (a inclinação recua a parte de baixo do painel)
      const lim = Math.abs(sn) > 0.02 ? ((wz - zS) * cs + Math.min(-0.045, back / ct - 0.155 * tt - 0.05)) / Math.abs(sn) : 1e9;
      const solve = function (x, sgn) {
        const d = Math.max(0.02, Math.hypot(x, wz - zS)), a = Math.atan2(x, wz - zS), t1 = a + sgn * Math.acos(cl(d / (2 * L), -1, 1));
        return { t1: t1, ex: Math.sin(t1) * L, ez: zS + Math.cos(t1) * L, hx: Math.sin(a) * d, hz: zS + Math.cos(a) * d, sw: sw, ti: ti };
      };
      const hit = function (r, px, pz, yh) {   // o ponto do braço (meia-altura yh) invade o painel ou fica na frente dele?
        const dx = px - r.hx, dz = pz - r.hz; if (Math.hypot(dx, dz) < 0.07) return false;
        const u = dx * cs - dz * sn, z1 = dx * sn + dz * cs; if (Math.abs(u) > hw + 0.015) return false;
        for (let k = -1; k <= 1; k++) { const dy = k * yh, v = dy * ct + z1 * st, w = -dy * st + z1 * ct; if (Math.abs(v) <= hh + 0.015 && w > back - 0.03) return true; }
        return false;
      };
      const ok = function (r) {
        for (let k = 1; k <= 14; k++) {
          const t = k / 14, x1 = r.ex * t, z1 = zS + (r.ez - zS) * t, x2 = r.ex + (r.hx - r.ex) * t, z2 = r.ez + (r.hz - r.ez) * t;
          if (z1 < 0.024 || z2 < 0.024 || hit(r, x1, z1, 0.155) || hit(r, x2, z2, 0.05)) return false;
        }
        return true;
      };
      let wx = cl(rx * (1 - ex) + sd * 0.3 * ex, -reachX, reachX);
      for (let it = 0; it < 18; it++) {
        const x = sn < -0.02 ? Math.min(wx, lim) : sn > 0.02 ? Math.max(wx, -lim) : wx; if (Math.abs(x) > reachX + 1e-9) return null;
        const pref = sn > 0.02 ? -1 : sn < -0.02 ? 1 : x > 0 ? -1 : 1;                 // o cotovelo dobra para o lado de trás da tela
        const r = solve(x, pref); if (ok(r)) return r; const r2 = solve(x, -pref); if (ok(r2)) return r2; wx *= 0.7;
      }
      return null;
    };
    for (let k = 0; k <= 12; k++) { const f = 1 - k / 12, r = attempt(sw0 * f, ti0 * f); if (r) return r; }   // pose impossível: reduz giro e inclinação até caber
    const a0 = Math.atan2(rx, rz - zS), d0 = Math.hypot(rx, rz - zS), t0 = a0 - lado * Math.acos(Math.min(1, d0 / (2 * L)));
    return { t1: t0, ex: Math.sin(t0) * L, ez: zS + Math.cos(t0) * L, hx: rx, hz: rz, sw: 0, ti: 0 };
  };
  /*IK*/

  def('tv_braco', {
    name: 'TV com suporte articulado', cat: 'Setup', size: [0.97, 0.56, 0.12], mount: 'wall', articulated: true,
    defaults: { pol: 43, on: true, film: true, color: '#2a4f9e', accent: '#d4202a', text: 'PLAY', ext: 0, side: 0, swivel: 0, tilt: 0, lado: -1 },
    controls: { pose: 'Posição do suporte', lado: 'Recolhida, a TV fica', on: 'Tela ligada', film: 'Filme passando', pol: 'Tamanho' },
    spanFor: function (p) { const e = Q.TV_OFF + (0.965 * (p.pol || 43)) / 43 / 2; return p.lado > 0 ? [-0.075, e] : [-e, 0.075]; },   // quanto ocupa de parede para cada lado da placa
    build: function (p) {
      const g = new T.Group(), k = (p.pol || 43) / 43, w = 0.965 * k, h = 0.558 * k, hw = w / 2, L = 0.3, zS = 0.03, tz = 0.05;
      const metal = Q.mMetal('#1c1d21', 0.42), cap = Q.mPlastic('#26272b', 0.7), black = Q.mPlastic('#0b0b0d', 0.45);
      // suporte como o do anúncio: espinha de parede com duas sapatas grandes, braço duplo robusto com capas, antebraço central e grade VESA com trilhos longos
      const grip = Q.mPlastic('#34363b', 0.9);
      g.add(mk(rbox(0.06, 0.4, 0.016, 0.004, 2), metal, 0, 0, 0.008));
      [0.165, -0.165].forEach(function (y) {
        g.add(mk(rbox(0.13, 0.1, 0.044, 0.02, 4), cap, 0, y, 0.024)); g.add(mk(rbox(0.09, 0.06, 0.006, 0.003, 2), grip, 0, y, 0.048));
        [-0.045, 0.045].forEach(function (x) { g.add(mk(cyl(0.008, 0.008, 0.006, 10), metal, x, y, 0.047).rotateX(PI / 2)); });
      });
      g.add(mk(cyl(0.015, 0.015, 0.36, 14), metal, 0, 0, zS));
      const a1 = new T.Group(); a1.position.set(0, 0, zS); g.add(a1);                 // braço duplo (ombro)
      [0.11, -0.11].forEach(function (y) {
        a1.add(mk(rbox(0.03, 0.07, L + 0.03, 0.012, 3), metal, 0, y, L / 2)); a1.add(mk(rbox(0.04, 0.084, L * 0.6, 0.016, 3), cap, 0, y, L * 0.5));
        a1.add(mk(rbox(0.043, 0.05, L * 0.42, 0.006, 2), grip, 0, y, L * 0.5));
      });
      a1.add(mk(cyl(0.016, 0.016, 0.31, 14), metal, 0, 0, L));                        // eixo do cotovelo
      const a2 = new T.Group(); g.add(a2);                                             // antebraço
      a2.add(mk(rbox(0.032, 0.09, L + 0.03, 0.012, 3), metal, 0, 0, L / 2)); a2.add(mk(rbox(0.042, 0.1, L * 0.58, 0.016, 3), cap, 0, 0, L * 0.5));
      a2.add(mk(rbox(0.045, 0.06, L * 0.4, 0.006, 2), grip, 0, 0, L * 0.5));
      const cabo = new T.CatmullRomCurve3([V3(0, -0.06, 0.02), V3(0, -0.13, L * 0.5), V3(0, -0.07, L - 0.02)]); a2.add(mk(new T.TubeGeometry(cabo, 12, 0.006, 6, false), black));
      const head = new T.Group(); head.rotation.order = 'YXZ'; g.add(head);            // cabeça: gira e inclina
      head.add(mk(cyl(0.017, 0.017, 0.16, 14), metal, 0, 0, 0));
      head.add(mk(rbox(0.09, 0.15, 0.03, 0.008, 2), metal, 0, 0, 0.012));
      head.add(mk(rbox(0.16, 0.16, 0.008, 0.003, 2), metal, 0, 0, 0.026));
      const rl = Math.min(0.5 * k, h * 0.9);
      [-1, 1].forEach(function (sd) { head.add(mk(box(0.03, rl, 0.012), metal, sd * 0.2 * k, 0, 0.032)); for (let j = -3; j <= 3; j++) head.add(mk(box(0.012, 0.03, 0.002), black, sd * 0.2 * k, (j * rl) / 8, 0.0255)); });
      [0.1, -0.1].forEach(function (y) { head.add(mk(box(0.44 * k, 0.036, 0.01), metal, 0, y * k, 0.027)); });
      head.add(mk(rbox(w, h, 0.024, 0.004, 2), black, 0, 0, tz));
      head.add(mk(rbox(w * 0.55, h * 0.5, 0.018, 0.008, 2), black, 0, -h * 0.05, tz - 0.016));
      let sm;
      if (p.on && p.film) sm = Q.mEmis('#ffffff', 2.0, { map: Q.film.tex() });
      else if (p.on) { sm = Q.mEmis('#ffffff', 2.0, { map: Q.makeTvScreen(p.color, p.accent, String(p.text || '').toUpperCase().slice(0, 12)) }); sm.userData.ownMap = true; }
      else sm = new T.MeshStandardMaterial({ color: '#030304', roughness: 0.1 });
      head.add(mk(new T.PlaneGeometry(w - 0.016, h - 0.016), sm, 0, 0, tz + 0.0125));
      if (p.on) { const l = new T.RectAreaLight(new T.Color(p.color).lerp(new T.Color(1, 1, 1), 0.5), 10, w - 0.02, h - 0.02); l.position.set(0, 0, tz + 0.03); l.rotation.y = PI; head.add(l); if (p.film) { g.userData.film = true; g.userData.filmLight = l; } }
      /* cinemática do braço: ext 0..1 (afastar), side -1..1 (deslocar), swivel e tilt em graus */
      g.userData.pose = function (q) {
        const r = Q.tvArmIK({ ext: q.ext, side: q.side, swivel: q.swivel, tilt: q.tilt, lado: p.lado }, hw, h / 2);
        a1.rotation.y = r.t1; a2.position.set(r.ex, 0, r.ez); a2.rotation.y = Math.atan2(r.hx - r.ex, r.hz - r.ez);
        head.position.set(r.hx, 0, r.hz); head.rotation.set(r.ti, r.sw, 0);
      };
      g.userData.pose(p);
      g.userData.proxyParent = head; g.userData.proxyZ = tz; g.userData.proxySize = [w, h, 0.06]; g.userData.thumbPose = { ext: 1, side: 0, swivel: 0, tilt: 0 };
      g.userData.size = [w + 0.005, h, 0.12];
      return g;
    }
  });

  def('controle', {
    name: 'Controle de videogame', cat: 'Setup', size: [0.155, 0.05, 0.105], mount: 'surface', defaults: { color: '#141416' }, controls: { color: 'Cor' },
    build: function (p) {
      const g = new T.Group(), m = Q.mPlastic(p.color, 0.5), dk = Q.mPlastic('#060607', 0.55), gr = Q.mPlastic('#3b3c41', 0.5);
      g.add(mk(rbox(0.15, 0.028, 0.062, 0.013, 3), m, 0, 0.022, -0.012));
      [-1, 1].forEach(function (s) {
        const grip = mk(rbox(0.04, 0.03, 0.07, 0.014, 3), m, s * 0.056, 0.018, 0.022); grip.rotation.y = -s * 0.28; grip.rotation.x = 0.18; g.add(grip);
        g.add(mk(cyl(0.011, 0.012, 0.012, 18), dk, s * 0.03, 0.042, 0.004 + (s < 0 ? -0.014 : 0.006)));
        g.add(mk(cyl(0.008, 0.008, 0.006, 12), gr, s * 0.064, 0.038, -0.03));
      });
      [[0, -0.01], [0.012, 0], [-0.012, 0], [0, 0.01]].forEach(function (q) { g.add(mk(cyl(0.0048, 0.0048, 0.004, 12), gr, 0.052 + q[0], 0.038, -0.012 + q[1])); });
      g.add(mk(box(0.022, 0.004, 0.007), gr, -0.052, 0.038, -0.004)); g.add(mk(box(0.007, 0.004, 0.022), gr, -0.052, 0.038, -0.004));
      return g;
    }
  });

  def('aparelho', {
    name: 'Aparelho (console ou blu-ray)', cat: 'Setup', size: [0.3, 0.048, 0.22], mount: 'surface', defaults: { color: '#101012' }, controls: { color: 'Cor' },
    tops: [{ x0: -0.14, x1: 0.14, z0: -0.1, z1: 0.1, y: 0.048, clear: 0.5 }],
    build: function (p) {
      const g = new T.Group(), m = new T.MeshPhysicalMaterial({ color: p.color, roughness: 0.28, clearcoat: 0.6, clearcoatRoughness: 0.15 });
      g.add(mk(rbox(0.3, 0.04, 0.22, 0.006, 2), m, 0, 0.026, 0));
      [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(function (s) { g.add(mk(cyl(0.008, 0.008, 0.006, 10), Q.mPlastic('#050505', 0.8), s[0] * 0.125, 0.003, s[1] * 0.085)); });
      g.add(mk(box(0.14, 0.004, 0.002), Q.mPlastic('#2c2d31', 0.4), -0.04, 0.03, 0.1105));
      g.add(mk(box(0.006, 0.003, 0.002), Q.mEmis('#9fd0ff', 2.2), 0.125, 0.022, 0.1105));
      return g;
    }
  });

  /* ---------------- MÓVEIS ---------------- */
  def('cama', {
    name: 'Cama de solteiro', cat: 'Móveis', size: [0.92, 1.08, 2.0], mount: 'floor',
    defaults: { color: '#f3f1ec', accent: '#7a1f2b', head: true }, controls: { color: 'Colcha', accent: 'Cabeceira e almofada', head: 'Cabeceira' },
    tops: [{ x0: -0.4, x1: 0.4, z0: -0.35, z1: 0.9, y: 0.508, clear: 0.8 }],
    build: function (p) {
      const g = new T.Group(), w = 0.88, L = 1.92, base = Q.mLacquer('#efede8'), wf = Q.mFabric('#f5f3ef'), cf = Q.mFabric(p.color), af = Q.mFabric(p.accent);
      [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(function (s) { g.add(mk(cyl(0.022, 0.018, 0.05, 12), Q.mPlastic('#2a2320', 0.5), s[0] * (w / 2 - 0.06), 0.025, s[1] * (L / 2 - 0.06))); });
      g.add(mk(rbox(w, 0.2, L, 0.015, 2), base, 0, 0.15, 0));
      g.add(mk(rbox(w - 0.02, 0.2, L - 0.03, 0.055, 5), wf, 0, 0.35, 0));
      const quilt = Q.mFabric(p.color); quilt.normalMap = Q.quiltN; quilt.normalScale.set(0.9, 0.9);
      const dv = rbox(w + 0.03, 0.078, L * 0.7, 0.036, 5), dp = dv.attributes.position, du = dv.attributes.uv;
      for (let k = 0; k < dp.count; k++) du.setXY(k, dp.getX(k) * 1.4, dp.getZ(k) * 1.4 + dp.getY(k) * 1.4);
      g.add(mk(dv, quilt, 0, 0.468, L * 0.15));
      const pl = mk(rbox(0.6, 0.12, 0.38, 0.056, 5), wf, 0, 0.5, -L / 2 + 0.25); pl.rotation.x = 0.1; g.add(pl);
      const cu = mk(rbox(0.36, 0.12, 0.34, 0.056, 5), af, 0, 0.6, -L / 2 + 0.4); cu.rotation.x = 1.05; g.add(cu);
      g.add(mk(rbox(w + 0.04, 0.03, 0.42, 0.014, 3), af, 0, 0.521, L / 2 - 0.36));
      if (p.head) for (let i = 0; i < 6; i++) g.add(mk(rbox(0.143, 0.64, 0.07, 0.03, 3), af, -0.3625 + i * 0.145, 0.74, -L / 2 - 0.008));
      return g;
    }
  });

  const EST_Y = [0.08, 0.454, 0.828, 1.202, 1.576], EST_H = 1.95;
  def('estante', {
    name: 'Estante iluminada', cat: 'Móveis', size: [0.66, EST_H, 0.3], mount: 'floor', thumbDir: [0.42, 0.22, 1],
    defaults: { color: '#f4f3ef', led: true, ledColor: '#ffc878' }, controls: { color: 'Cor do móvel', led: 'LED nos nichos', ledColor: 'Cor do LED' },
    tops: EST_Y.map(function (y) { return { x0: -0.308, x1: 0.308, z0: -0.135, z1: 0.14, y: y, clear: 0.35 }; }).concat([{ x0: -0.32, x1: 0.32, z0: -0.14, z1: 0.14, y: EST_H, clear: 0.9 }]),
    build: function (p) {
      const g = new T.Group(), m = Q.mLacquer(p.color), em = p.led ? Q.mEmis(p.ledColor, 6) : null, lines = [];
      [-1, 1].forEach(function (s) { g.add(mk(box(0.02, EST_H, 0.3), m, s * 0.32, EST_H / 2, 0)); });
      g.add(mk(box(0.62, 0.06, 0.28), m, 0, 0.03, -0.005));
      EST_Y.concat([EST_H]).forEach(function (y, k) {
        g.add(mk(box(0.62, 0.02, 0.292), m, 0, y - 0.01, 0.002));
        if (k > 0 && p.led) {
          g.add(mk(box(0.59, 0.004, 0.008), em, 0, y - 0.022, 0.118));
          lines.push({ a: [-0.29, y - 0.027, 0.118], b: [0.29, y - 0.027, 0.118], e: [0, -1, -0.45], color: p.ledColor, power: 0.5, range: 0.7 });
        }
      });
      g.add(mk(box(0.62, EST_H - 0.06, 0.006), m, 0, EST_H / 2 + 0.03, -0.145));
      if (lines.length) g.userData.lines = lines;
      return g;
    }
  });

  def('rack', {
    name: 'Rack de TV', cat: 'Móveis', size: [1.2, 0.722, 0.42], mount: 'floor',
    defaults: { color: '#f4f3ef', w: 1.2, led: true, ledColor: '#ffc878' }, controls: { color: 'Cor do móvel', w: 'Largura', led: 'LED no nicho', ledColor: 'Cor do LED' },
    topsFor: function (p) { const w = p.w || 1.2; return [{ x0: -w / 2 + 0.01, x1: w / 2 - 0.01, z0: -0.2, z1: 0.2, y: 0.722, clear: 2 }, { x0: -w / 2 + 0.03, x1: w / 2 - 0.03, z0: -0.17, z1: 0.195, y: 0.52, clear: 0.176 }]; },
    build: function (p) {
      const g = new T.Group(), w = p.w || 1.2, d = 0.42, m = Q.mLacquer(p.color), gap = Q.mPlastic('#8d8c88', 0.8);
      g.add(mk(box(w - 0.04, 0.06, d - 0.05), m, 0, 0.03, -0.01));
      g.add(mk(box(w, 0.44, d - 0.022), m, 0, 0.28, -0.011));
      const n = w > 1.05 ? 3 : 2, dw = (w - 0.006) / n;
      for (let k = 0; k < n; k++) g.add(mk(rbox(dw - 0.004, 0.432, 0.02, 0.003, 1), m, -w / 2 + 0.003 + dw * (k + 0.5), 0.28, d / 2 - 0.01));
      for (let k = 1; k < n; k++) g.add(mk(box(0.003, 0.43, 0.004), gap, -w / 2 + 0.003 + dw * k, 0.28, d / 2 - 0.004));
      g.add(mk(box(w, 0.02, d), m, 0, 0.51, 0));
      [-1, 1].forEach(function (s) { g.add(mk(box(0.022, 0.18, d), m, s * (w / 2 - 0.011), 0.61, 0)); });
      g.add(mk(box(w - 0.04, 0.18, 0.008), m, 0, 0.61, -d / 2 + 0.004));
      g.add(mk(box(w, 0.022, d), m, 0, 0.711, 0));
      if (p.led) {
        g.add(mk(box(w - 0.08, 0.004, 0.008), Q.mEmis(p.ledColor, 6), 0, 0.697, -0.15));
        g.userData.lines = [{ a: [-w / 2 + 0.05, 0.692, -0.15], b: [w / 2 - 0.05, 0.692, -0.15], e: [0, -1, 0.35], color: p.ledColor, power: 0.5, range: 0.8 }];
      }
      g.userData.size = [w, 0.722, d];
      return g;
    }
  });

  def('criado', {
    name: 'Criado-mudo', cat: 'Móveis', size: [0.42, 0.5, 0.36], mount: 'floor', defaults: { color: '#f2f1ed' }, controls: { color: 'Cor' },
    tops: [{ x0: -0.2, x1: 0.2, z0: -0.17, z1: 0.17, y: 0.5, clear: 1 }],
    build: function (p) {
      const g = new T.Group(), m = Q.mLacquer(p.color);
      [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(function (s) { g.add(mk(cyl(0.016, 0.01, 0.12, 12), Q.mPlastic('#8a5a34', 0.5), s[0] * 0.17, 0.06, s[1] * 0.14)); });
      g.add(mk(rbox(0.42, 0.38, 0.36, 0.012, 2), m, 0, 0.31, 0));
      g.add(mk(box(0.39, 0.003, 0.003), Q.mPlastic('#3a3a3d', 0.6), 0, 0.31, 0.1802));
      [0.4, 0.21].forEach(function (y) { g.add(mk(sph(0.011, 14, 10), Q.mMetal('#b8904a', 0.3), 0, y, 0.19)); });
      return g;
    }
  });

  def('pufe', {
    name: 'Pufe', cat: 'Móveis', size: [0.42, 0.38, 0.42], mount: 'floor', defaults: { color: '#c97b8b' }, controls: { color: 'Cor' },
    tops: [{ x0: -0.14, x1: 0.14, z0: -0.14, z1: 0.14, y: 0.38, clear: 1 }],
    build: function (p) {
      const g = new T.Group(), pts = [];
      [[0, 0], [0.17, 0], [0.2, 0.02], [0.21, 0.08], [0.21, 0.3], [0.195, 0.36], [0.15, 0.38], [0, 0.38]].forEach(function (q) { pts.push(new T.Vector2(q[0], q[1])); });
      g.add(mk(new T.LatheGeometry(new T.SplineCurve(pts).getPoints(28), 40), Q.mFabric(p.color)));
      return g;
    }
  });

  def('tapete_red', {
    name: 'Tapete redondo', cat: 'Móveis', size: [1.2, 0.02, 1.2], mount: 'floor', flat: true, defaults: { color: '#d9a6ae' }, controls: { color: 'Cor' },
    build: function (p) {
      const g = new T.Group(), pts = [[0.6, 0], [0.59, 0.013], [0.56, 0.018], [0, 0.018]].map(function (q) { return new T.Vector2(q[0], q[1]); });   // de fora para o centro: a face de cima fica virada para cima
      const m = mk(planarUV(clean(new T.LatheGeometry(pts, 72)), 5), Q.mFabric(p.color, true)); m.userData.noShadow = true; g.add(m);
      return g;
    }
  });
  def('tapete_ret', {
    name: 'Tapete retangular', cat: 'Móveis', size: [1.4, 0.02, 0.9], mount: 'floor', flat: true, defaults: { color: '#2c3558' }, controls: { color: 'Cor' },
    build: function (p) { const g = new T.Group(), m = mk(planarUV(slab(1.4, 0.9, 0.03, 0.016), 5), Q.mFabric(p.color, true)); m.userData.noShadow = true; g.add(m); return g; }
  });

  /* ---------------- DECORAÇÃO ---------------- */
  function leafGeo(len, wid) {
    const s = new T.Shape(); s.moveTo(0, 0);
    s.bezierCurveTo(wid * 0.9, len * 0.08, wid * 1.05, len * 0.62, 0, len); s.bezierCurveTo(-wid * 1.05, len * 0.62, -wid * 0.9, len * 0.08, 0, 0);
    const g = new T.ShapeGeometry(s, 6), p = g.attributes.position;
    for (let i = 0; i < p.count; i++) { const x = p.getX(i), y = p.getY(i); p.setZ(i, Math.abs(x) * 0.5 - (y / len) * (y / len) * len * 0.18); }
    g.computeVertexNormals(); return g;
  }
  def('jiboia', {
    name: 'Jiboia pendente', cat: 'Decoração', size: [0.2, 0.2, 0.2], mount: 'surface', defaults: { color: '#f1efe9' }, controls: { color: 'Cor do vaso' },
    build: function (p, seed) {
      const g = new T.Group(), r = Q.rng(seed * 31 + 7), pot = Q.mPlastic(p.color, 0.35);
      g.add(mk(cyl(0.07, 0.052, 0.11, 28), pot, 0, 0.055, 0));
      const rim = mk(new T.TorusGeometry(0.07, 0.006, 8, 32), pot, 0, 0.11, 0); rim.rotation.x = PI / 2; g.add(rim);
      g.add(mk(cyl(0.064, 0.064, 0.004, 24), Q.mPlastic('#2b2019', 0.9), 0, 0.104, 0));
      const leaves = [], stems = [], E = new T.Euler(), q = new T.Quaternion(), m4 = new T.Matrix4(), sc = new T.Vector3(), col = new T.Color();
      const addLeaf = function (pos, yaw, pitch, s) {
        const lg = leafGeo(0.07, 0.03); E.set(pitch, yaw, (r() - 0.5) * 0.7, 'YXZ'); q.setFromEuler(E); sc.set(s, s, s);
        lg.applyMatrix4(m4.compose(pos, q, sc));
        col.setHSL(0.27 + r() * 0.07, 0.5 + r() * 0.2, 0.1 + r() * 0.1); leaves.push(tint(lg, col));
      };
      for (let k = 0; k < 9; k++) { const a = r() * PI * 2; addLeaf(new T.Vector3(Math.cos(a) * 0.035, 0.105, Math.sin(a) * 0.035), -a + PI / 2, 0.35 + r() * 0.7, 0.8 + r() * 0.5); }
      for (let v = 0; v < 7; v++) {
        const a = (r() - 0.5) * 2.5, len = 0.28 + r() * 0.42, dx = Math.sin(a), dz = Math.cos(a), pts = [];
        for (let i = 0; i <= 10; i++) {
          const tt = i / 10, out = 0.06 + 0.07 * Math.min(1, tt * 3.2) + 0.02 * Math.sin(tt * 7 + v), y = 0.11 + 0.035 * Math.sin(Math.min(1, tt * 3.2) * PI) - len * Math.max(0, tt - 0.26) / 0.74;
          pts.push(new T.Vector3(dx * out + Math.sin(tt * 9 + v) * 0.012, y, dz * out + Math.cos(tt * 8 + v * 2) * 0.012));
        }
        const cv = new T.CatmullRomCurve3(pts);
        stems.push(tint(new T.TubeGeometry(cv, 20, 0.0018, 5, false), '#3f5a23'));
        const n = Math.floor(len / 0.045) + 3;
        for (let i = 1; i <= n; i++) addLeaf(cv.getPoint(i / n), a + (r() - 0.5) * 2.4, 1.5 + r() * 1.0, 0.75 + r() * 0.55);
      }
      g.add(mk(merge(leaves.concat(stems)), new T.MeshStandardMaterial({ vertexColors: true, side: T.DoubleSide, roughness: 0.5 })));
      return g;
    }
  });

  def('espada', {
    name: 'Espada-de-são-jorge', cat: 'Decoração', size: [0.13, 0.34, 0.13], mount: 'surface', defaults: { color: '#c96f4a' }, controls: { color: 'Cor do vaso' },
    build: function (p, seed) {
      const g = new T.Group(), r = Q.rng(seed * 17 + 3), list = [], col = new T.Color();
      g.add(mk(cyl(0.056, 0.044, 0.09, 26), Q.mPlastic(p.color, 0.6), 0, 0.045, 0));
      g.add(mk(cyl(0.051, 0.051, 0.004, 22), Q.mPlastic('#2b2019', 0.9), 0, 0.086, 0));
      for (let k = 0; k < 8; k++) {
        const h = 0.16 + r() * 0.1, bg = new T.PlaneGeometry(0.034, h, 2, 6), pp = bg.attributes.position, lean = 0.08 + r() * 0.25;
        for (let i = 0; i < pp.count; i++) { const y = pp.getY(i) + h / 2, f = y / h; pp.setXYZ(i, pp.getX(i) * (1 - f * f * 0.9), y, f * f * h * lean + Math.abs(pp.getX(i)) * 0.4); }
        bg.computeVertexNormals(); bg.rotateY(r() * PI * 2); bg.translate((r() - 0.5) * 0.05, 0.085, (r() - 0.5) * 0.05);
        col.setHSL(0.29 + r() * 0.05, 0.5, 0.08 + r() * 0.08); list.push(tint(bg, col));
      }
      g.add(mk(merge(list), new T.MeshStandardMaterial({ vertexColors: true, side: T.DoubleSide, roughness: 0.45 })));
      return g;
    }
  });

  def('livros', {
    name: 'Livros', cat: 'Decoração', size: [0.2, 0.25, 0.16], mount: 'surface', defaults: {}, controls: {},
    build: function (p, seed) {
      const g = new T.Group(), r = Q.rng(seed * 13 + 1), list = [];
      const pal = ['#22304f', '#7a1f2b', '#e9e4d8', '#1d1d22', '#c9a227', '#2f5d50', '#d4d0c8', '#8b3a62', '#3d6bff', '#e07a3f'];
      let x = -0.095;
      while (x < 0.075) {
        const w = 0.018 + r() * 0.017, h = 0.17 + r() * 0.07, d = 0.125 + r() * 0.03, c = pal[Math.floor(r() * pal.length)], z0 = 0.075 - d;
        let b = box(0.0025, h, d); b.translate(x + 0.00125, h / 2, z0 + d / 2); list.push(tint(b, c));
        b = box(0.0025, h, d); b.translate(x + w - 0.00125, h / 2, z0 + d / 2); list.push(tint(b, c));
        b = box(w, h, 0.0025); b.translate(x + w / 2, h / 2, 0.075 - 0.00125); list.push(tint(b, c));
        b = box(w - 0.005, h - 0.008, d - 0.006); b.translate(x + w / 2, h / 2, z0 + d / 2 - 0.002); list.push(tint(b, '#efe9d9'));
        x += w + 0.0008;
      }
      g.add(mk(merge(list), new T.MeshStandardMaterial({ vertexColors: true, roughness: 0.72 })));
      return g;
    }
  });

  function frameParts(g, w, h, p, seed, z0) {
    const fm = Q.mPlastic(p.frame || '#151518', 0.5), b = 0.016, dp = 0.022;
    [[0, h / 2 - b / 2, w, b], [0, -h / 2 + b / 2, w, b], [-w / 2 + b / 2, 0, b, h - 2 * b], [w / 2 - b / 2, 0, b, h - 2 * b]].forEach(function (s) { g.add(mk(box(s[2], s[3], dp), fm, s[0], s[1], z0 + dp / 2)); });
    g.add(mk(box(w - 2 * b, h - 2 * b, 0.004), Q.mPlastic('#f4f1ea', 0.9), 0, 0, z0 + 0.008));
    const am = new T.MeshStandardMaterial({ map: Q.makeArt(p.style || 1, p.color, seed), roughness: 0.85 }); am.userData.ownMap = true;
    g.add(mk(new T.PlaneGeometry(w - 2 * b - 0.05, h - 2 * b - 0.06), am, 0, 0, z0 + 0.0105));
  }
  def('quadro', {
    name: 'Quadro', cat: 'Decoração', size: [0.32, 0.42, 0.03], mount: 'wall', defaults: { color: '#e0704a', style: 1, frame: '#151518' },
    controls: { color: 'Cor da arte', style: 'Trocar arte', frame: 'Moldura' },
    build: function (p, seed) { const g = new T.Group(); frameParts(g, 0.32, 0.42, p, seed, 0); return g; }
  });
  def('porta_retrato', {
    name: 'Porta-retrato', cat: 'Decoração', size: [0.16, 0.21, 0.08], mount: 'surface', defaults: { color: '#3d6bff', style: 4, frame: '#f4f1ea' },
    controls: { color: 'Cor da arte', style: 'Trocar arte', frame: 'Moldura' },
    build: function (p, seed) {
      const g = new T.Group(), f = new T.Group(); f.position.set(0, 0.103, 0.012); f.rotation.x = -0.2; g.add(f);
      frameParts(f, 0.15, 0.2, p, seed, -0.011);
      const st = mk(box(0.03, 0.15, 0.004), Q.mPlastic('#222', 0.6), 0, 0.07, -0.03); st.rotation.x = 0.33; g.add(st);
      return g;
    }
  });

  def('pelucia', {
    name: 'Pelúcia', cat: 'Decoração', size: [0.17, 0.13, 0.17], mount: 'surface', defaults: { color: '#d7263d' }, controls: { color: 'Cor' },
    build: function (p) {
      const g = new T.Group(), f = Q.mFabric(p.color), b = sph(0.064, 24, 18); b.scale(1, 0.86, 1);
      g.add(mk(b, f, 0, 0.066, 0));
      for (let i = 0; i < 7; i++) { const a = (i / 7) * PI * 2 + 0.2; g.add(mk(sph(0.023, 14, 10), f, Math.cos(a) * 0.062, 0.02, Math.sin(a) * 0.062)); }
      [-1, 1].forEach(function (s) {
        g.add(mk(sph(0.0095, 12, 10), Q.mPlastic('#0b0b0c', 0.2), s * 0.024, 0.078, 0.057));
        g.add(mk(sph(0.003, 8, 6), Q.mPlastic('#ffffff', 0.3), s * 0.021, 0.082, 0.0655));
      });
      return g;
    }
  });

  def('boneco', {
    name: 'Boneco de coleção', cat: 'Decoração', size: [0.09, 0.165, 0.08], mount: 'surface', defaults: { color: '#c81f2a', accent: '#e0b62b' }, controls: { color: 'Cor principal', accent: 'Cor dos detalhes' },
    build: function (p) {
      const g = new T.Group(), c = Q.mLacquer(p.color), a = Q.mLacquer(p.accent), dk = Q.mPlastic('#111114', 0.35), wh = Q.mPlastic('#f6f6f4', 0.3);
      g.add(mk(cyl(0.038, 0.04, 0.008, 32), dk, 0, 0.004, 0));
      [-1, 1].forEach(function (s) {
        g.add(mk(rbox(0.02, 0.034, 0.024, 0.006, 2), c, s * 0.0125, 0.027, 0));
        g.add(mk(rbox(0.022, 0.012, 0.03, 0.005, 2), a, s * 0.0125, 0.014, 0.003));
        const arm = mk(rbox(0.014, 0.04, 0.016, 0.006, 2), c, s * 0.034, 0.064, 0.002); arm.rotation.z = s * 0.25; g.add(arm);
        g.add(mk(sph(0.0085, 12, 10), a, s * 0.04, 0.044, 0.004));
        g.add(mk(sph(0.0075, 12, 10), wh, s * 0.017, 0.123, 0.0335));
        g.add(mk(sph(0.0035, 8, 8), dk, s * 0.017, 0.123, 0.0395));
      });
      g.add(mk(rbox(0.05, 0.046, 0.032, 0.01, 2), c, 0, 0.066, 0));
      g.add(mk(cyl(0.011, 0.011, 0.004, 16), a, 0, 0.07, 0.0165).rotateX(PI / 2));
      const head = sph(0.039, 28, 20); head.scale(1, 0.94, 0.95); g.add(mk(head, c, 0, 0.124, 0));
      g.add(mk(rbox(0.058, 0.03, 0.012, 0.006, 2), a, 0, 0.123, 0.031));
      return g;
    }
  });

  def('colecao', {
    name: 'Coleção de livros', cat: 'Decoração', size: [0.34, 0.25, 0.17], mount: 'surface', defaults: { style: 1, wide: false }, controls: { style: 'Trocar estilo', wide: 'Fileira inteira' },
    build: function (p, seed) {
      const g = new T.Group(), r = Q.rng(seed * 7 + (p.style || 1) * 101), list = [], W = p.wide ? 0.55 : 0.34;
      const sets = { 1: { sp: ['#191b24', '#20222c', '#15161d', '#262833'], bd: ['#c4202c', '#2f5fd0', '#e0b62b', '#e8e6df'] }, 2: { sp: ['#22304f', '#7a1f2b', '#2f5d50', '#c9a227', '#8b3a62', '#e07a3f', '#1d1d22', '#3d6bff'], bd: ['#f1ede2', '#111114'] },
        3: { sp: ['#efe9dc', '#e2dccd', '#d6cfc0', '#f5f1e8'], bd: ['#b9a98a', '#8c8473', '#c96f4a'] }, 4: { sp: ['#7a1f2b', '#5c1620', '#8e2332', '#3a0f15'], bd: ['#e0b62b', '#f1ede2'] } };
      const st = sets[p.style] || sets[1], h0 = 0.205 + r() * 0.02; let x = -W / 2;
      while (x < W / 2 - 0.016) {
        const w = Math.min(0.02 + r() * 0.012, W / 2 - x), h = h0 + (r() - 0.5) * 0.014, d = 0.15, c = st.sp[Math.floor(r() * st.sp.length)], bc = st.bd[Math.floor(r() * st.bd.length)], z0 = 0.085 - d;
        let b = box(0.0025, h, d); b.translate(x + 0.00125, h / 2, z0 + d / 2); list.push(tint(b, c));
        b = box(0.0025, h, d); b.translate(x + w - 0.00125, h / 2, z0 + d / 2); list.push(tint(b, c));
        b = box(w, h, 0.0025); b.translate(x + w / 2, h / 2, 0.085 - 0.00125); list.push(tint(b, c));
        b = box(w - 0.005, h - 0.008, d - 0.006); b.translate(x + w / 2, h / 2, z0 + d / 2 - 0.002); list.push(tint(b, '#efe9d9'));
        b = box(w - 0.004, 0.022, 0.001); b.translate(x + w / 2, h * 0.8, 0.0856); list.push(tint(b, bc));
        b = box(w - 0.004, 0.006, 0.001); b.translate(x + w / 2, h * 0.2, 0.0856); list.push(tint(b, bc));
        b = box(w - 0.008, 0.05, 0.001); b.translate(x + w / 2, h * 0.5, 0.0856); list.push(tint(b, new T.Color(c).lerp(new T.Color(bc), 0.22)));
        x += w + 0.0006;
      }
      g.add(mk(merge(list), new T.MeshStandardMaterial({ vertexColors: true, roughness: 0.62 })));
      g.userData.size = [W, 0.25, 0.17];
      return g;
    }
  });

  def('mobile', {
    name: 'Enfeite de elefantes', cat: 'Decoração', size: [0.07, 0.74, 0.04], mount: 'wall', defaults: {}, controls: {},
    build: function () {
      const g = new T.Group(), list = [], cols = ['#1fa3a0', '#e0b62b', '#7bbf3a', '#e2702a', '#8a55c8'];
      let b = cyl(0.0012, 0.0012, 0.7, 5); b.translate(0, 0.01, 0.014); list.push(tint(b, '#7a6a4a'));
      cols.forEach(function (c, i) {
        const y = 0.27 - i * 0.125;
        b = rbox(0.05, 0.034, 0.018, 0.008, 2); b.translate(0, y, 0.015); list.push(tint(b, c));
        b = sph(0.013, 12, 10); b.translate(0.026, y + 0.008, 0.015); list.push(tint(b, c));
        b = box(0.006, 0.02, 0.006); b.translate(0.036, y - 0.006, 0.015); list.push(tint(b, c));
        [-0.014, 0.012].forEach(function (x) { const l = box(0.009, 0.014, 0.012); l.translate(x, y - 0.022, 0.015); list.push(tint(l, c)); });
        b = sph(0.006, 8, 6); b.translate(0, y + 0.036, 0.014); list.push(tint(b, '#d94f2b'));
        b = sph(0.005, 8, 6); b.translate(0, y + 0.05, 0.014); list.push(tint(b, '#e8c44a'));
      });
      b = cyl(0.004, 0.012, 0.02, 12); b.translate(0, -0.345, 0.014); list.push(tint(b, '#b8904a'));
      g.add(mk(merge(list), new T.MeshStandardMaterial({ vertexColors: true, roughness: 0.4, metalness: 0.25 })));
      return g;
    }
  });

  /* ---------------- LUZ ---------------- */
  const NEON = {
    nuvem: { pts: [[-0.15, -0.07], [-0.05, -0.075], [0.06, -0.075], [0.15, -0.07], [0.185, -0.03], [0.165, 0.015], [0.125, 0.03], [0.115, 0.075], [0.06, 0.105], [0.01, 0.085], [-0.03, 0.115], [-0.09, 0.095], [-0.105, 0.045], [-0.15, 0.035], [-0.185, 0.0], [-0.18, -0.04]], t: 0.5 },
    raio: { pts: [[0.025, 0.15], [-0.075, -0.01], [-0.005, -0.01], [-0.045, -0.15], [0.08, 0.03], [0.012, 0.03], [0.07, 0.15]], t: 0.04 },
    estrela: { pts: (function () { const a = []; for (let i = 0; i < 10; i++) { const r = i % 2 ? 0.062 : 0.15, th = PI / 2 + (i / 10) * PI * 2; a.push([Math.cos(th) * r, Math.sin(th) * r]); } return a; })(), t: 0.04 },
    coracao: { pts: (function () { const a = []; for (let i = 0; i < 40; i++) { const t = (i / 40) * PI * 2; a.push([0.0095 * 16 * Math.pow(Math.sin(t), 3), 0.0095 * (13 * Math.cos(t) - 5 * Math.cos(2 * t) - 2 * Math.cos(3 * t) - Math.cos(4 * t)) + 0.02]); } return a; })(), t: 0.5 },
    lua: { pts: (function () { const a = []; for (let i = 0; i <= 22; i++) { const th = PI * 0.3 + (i / 22) * PI * 1.4; a.push([Math.cos(th) * 0.14, Math.sin(th) * 0.14]); } for (let i = 0; i <= 16; i++) { const th = PI * 1.56 - (i / 16) * PI * 1.12; a.push([0.075 + Math.cos(th) * 0.115, Math.sin(th) * 0.115]); } return a; })(), t: 0.4 }
  };
  Q.neonShapes = ['nuvem', 'raio', 'coracao', 'estrela', 'lua', 'texto'];
  def('neon', {
    name: 'Neon de parede', cat: 'Luz', size: [0.42, 0.34, 0.04], mount: 'wall', defaults: { color: '#3d6bff', shape: 'nuvem', text: 'GG', on: true },
    controls: { color: 'Cor', shape: 'Trocar forma', text: 'Texto', on: 'Ligado' },
    build: function (p) {
      const g = new T.Group(), em = p.on ? Q.mEmis(p.color, 4.2) : Q.mPlastic('#d8d8dc', 0.3);
      let W = 0.42, H = 0.34;
      if (p.shape === 'texto') {
        const tx = Q.makeNeonText((p.text || 'GG').slice(0, 14)); H = 0.2; W = Math.min(0.95, H * tx.aspect);
        const m = p.on ? Q.mEmis(p.color, 3.4, { map: tx.tex, transparent: true, blending: T.AdditiveBlending, depthWrite: false })
          : new T.MeshBasicMaterial({ map: tx.tex, transparent: true, opacity: 0.5, depthWrite: false });
        m.userData.ownMap = true;
        g.add(mk(new T.PlaneGeometry(W, H), m, 0, 0, 0.014));
      } else {
        const s = NEON[p.shape] || NEON.nuvem, cv = new T.CatmullRomCurve3(s.pts.map(function (q) { return new T.Vector3(q[0], q[1], 0.016); }), true, 'catmullrom', s.t);
        g.add(mk(new T.TubeGeometry(cv, 200, 0.0055, 8, true), em));
        [0, 0.33, 0.66].forEach(function (f) { const q = cv.getPoint(f), c = mk(cyl(0.003, 0.003, 0.012, 8), Q.mPlastic('#cfcfd4', 0.4), q.x, q.y, 0.006); c.rotation.x = PI / 2; g.add(c); });
      }
      if (p.on) {
        g.add(mk(new T.PlaneGeometry(W * 2.5, H * 2.7), Q.mEmis(p.color, 0.42, { map: Q.glowTex, transparent: true, blending: T.AdditiveBlending, depthWrite: false }), 0, 0, 0.003));
        const l = new T.PointLight(p.color, 1.5, 2.6, 2); l.position.set(0, 0, 0.14); g.add(l);
      }
      g.userData.size = [W, H, 0.04];
      return g;
    }
  });

  def('abajur', {
    name: 'Abajur', cat: 'Luz', size: [0.22, 0.36, 0.22], mount: 'surface', defaults: { color: '#ffcf8f', on: true }, controls: { color: 'Cor da luz', on: 'Ligado' },
    build: function (p) {
      const g = new T.Group(), bm = Q.mMetal('#b8904a', 0.3);
      g.add(mk(cyl(0.058, 0.062, 0.014, 32), bm, 0, 0.007, 0));
      g.add(mk(cyl(0.007, 0.007, 0.2, 12), bm, 0, 0.11, 0));
      const sm = p.on ? Q.mEmis(new T.Color(p.color).lerp(new T.Color(1, 1, 1), 0.35), 1.7, { side: T.DoubleSide }) : new T.MeshStandardMaterial({ color: '#efe6d4', roughness: 0.9, side: T.DoubleSide });
      const sh = mk(new T.CylinderGeometry(0.072, 0.108, 0.15, 36, 1, true), sm, 0, 0.285, 0); sh.userData.noShadow = true; g.add(sh);
      if (p.on) { const l = new T.PointLight(p.color, 3.4, 0, 2); l.position.set(0, 0.275, 0); g.add(l); }
      return g;
    }
  });

  def('barra_led', {
    name: 'Barra de LED', cat: 'Luz', size: [0.2, 1.45, 0.2], mount: 'floor', defaults: { color: '#b04dff', on: true }, controls: { color: 'Cor', on: 'Ligada' },
    build: function (p) {
      const g = new T.Group(), bk = Q.mPlastic('#121214', 0.5);
      g.add(mk(cyl(0.09, 0.095, 0.02, 32), bk, 0, 0.01, 0));
      g.add(mk(box(0.028, 1.4, 0.022), bk, 0, 0.72, 0));
      g.add(mk(box(0.02, 1.36, 0.006), p.on ? Q.mEmis(p.color, 5) : Q.mPlastic('#d8d8dc', 0.4), 0, 0.73, -0.0135));
      if (p.on) g.userData.lines = [{ a: [0, 0.07, -0.02], b: [0, 1.4, -0.02], e: [0, 0, -1], color: p.color, power: 1.5, range: 3.2 }];
      return g;
    }
  });

  def('globo', {
    name: 'Luminária globo', cat: 'Luz', size: [0.13, 0.155, 0.13], mount: 'surface', defaults: { color: '#ffc27a', on: true }, controls: { color: 'Cor da luz', on: 'Ligada' },
    build: function (p) {
      const g = new T.Group();
      g.add(mk(cyl(0.046, 0.05, 0.022, 32), Q.mPlastic('#9a6a3c', 0.55), 0, 0.011, 0));
      const sp = sph(0.06, 36, 26), pos = sp.attributes.position, n = Q.lattice(91, 9, 9);
      for (let i = 0; i < pos.count; i++) { const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i), k = 1 + (n(Math.atan2(z, x) * 1.43 + 4.5, y * 60 + 3) - 0.5) * 0.035; pos.setXYZ(i, x * k, y * k, z * k); }
      sp.computeVertexNormals();
      const m = p.on ? Q.mEmis(new T.Color(p.color).lerp(new T.Color(1, 1, 1), 0.3), 1.7) : new T.MeshPhysicalMaterial({ color: '#efe6d6', roughness: 0.35, clearcoat: 0.4 });
      const ball = mk(sp, m, 0, 0.079, 0); ball.userData.noShadow = true; g.add(ball);
      if (p.on) { const l = new T.PointLight(p.color, 0.42, 1.5, 2); l.position.set(0, 0.08, 0); g.add(l); }
      return g;
    }
  });

  def('lanterna', {
    name: 'Lanterna decorativa', cat: 'Luz', size: [0.075, 0.135, 0.075], mount: 'surface', defaults: { color: '#ff9a3c', on: true }, controls: { color: 'Cor da luz', on: 'Ligada' },
    build: function (p) {
      const g = new T.Group(), bm = Q.mMetal('#1a1a1c', 0.5);
      g.add(mk(cyl(0.034, 0.036, 0.012, 20), bm, 0, 0.006, 0));
      const gm = p.on ? Q.mEmis(p.color, 1.9) : new T.MeshPhysicalMaterial({ color: '#c98a4a', roughness: 0.2, transparent: true, opacity: 0.5 });
      const glass = mk(cyl(0.026, 0.026, 0.075, 20), gm, 0, 0.05, 0); glass.userData.noShadow = true; g.add(glass);
      for (let i = 0; i < 4; i++) { const a = (i / 4) * PI * 2 + 0.78; g.add(mk(cyl(0.0022, 0.0022, 0.078, 6), bm, Math.cos(a) * 0.029, 0.05, Math.sin(a) * 0.029)); }
      g.add(mk(cyl(0.012, 0.034, 0.02, 20), bm, 0, 0.098, 0));
      const ring = mk(new T.TorusGeometry(0.012, 0.0022, 6, 18), bm, 0, 0.118, 0); g.add(ring);
      if (p.on) { const l = new T.PointLight(p.color, 0.16, 0.9, 2); l.position.set(0, 0.05, 0); g.add(l); }
      return g;
    }
  });

  Q.catOrder = ['Setup', 'Móveis', 'Decoração', 'Luz'];
})();
