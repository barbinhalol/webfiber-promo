/* Quarto 3D — núcleo: utilitários, texturas procedurais e materiais */
(function () {
  'use strict';
  const T = THREE;
  if (T.ColorManagement) T.ColorManagement.legacyMode = false;
  const Q = (window.Q = { T: T });

  /* luminária de teto: emite para baixo (decay > 2.0005 marca a luz), evitando estourar o forro */
  (function () {
    const k = 'light.color *= getDistanceAttenuation( lightDistance, pointLight.distance, pointLight.decay );', c = T.ShaderChunk.lights_pars_begin;
    if (c.indexOf(k) >= 0) T.ShaderChunk.lights_pars_begin = c.replace(k, k + '\n\t\tif ( pointLight.decay > 2.0005 ) light.color *= smoothstep( -0.1, 0.42, dot( light.direction, normalize( ( viewMatrix * vec4( 0.0, 1.0, 0.0, 0.0 ) ).xyz ) ) );');
  })();

  /* fitas de LED como luzes lineares analíticas (leves): difuso exato de segmento + especular por ponto representativo */
  (function () {
    const LL = (Q.LL = { A: [], B: [], E: [], C: [], N: { value: 0 } });
    for (let i = 0; i < 24; i++) { LL.A.push(new T.Vector4()); LL.B.push(new T.Vector4()); LL.E.push(new T.Vector3(0, -1, 0)); LL.C.push(new T.Vector3()); }
    LL.uA = { value: LL.A }; LL.uB = { value: LL.B }; LL.uE = { value: LL.E }; LL.uC = { value: LL.C };
    LL.set = function (list) {
      const n = Math.min(24, list.length);
      for (let i = 0; i < n; i++) {
        const l = list[i];
        LL.A[i].set(l.a.x, l.a.y, l.a.z, l.range); LL.B[i].set(l.b.x, l.b.y, l.b.z, 0); LL.E[i].copy(l.e).normalize();
        LL.C[i].set(l.color.r * l.power, l.color.g * l.power, l.color.b * l.power);
      }
      LL.N.value = n;
    };
    T.Material.prototype.onBeforeCompile = function (sh) {
      if (!this.isMeshStandardMaterial) return;
      sh.uniforms.qLA = LL.uA; sh.uniforms.qLB = LL.uB; sh.uniforms.qLE = LL.uE; sh.uniforms.qLC = LL.uC; sh.uniforms.qLN = LL.N;
    };
    T.ShaderChunk.lights_pars_begin += '\n#ifdef STANDARD\nuniform vec4 qLA[ 24 ];\nuniform vec4 qLB[ 24 ];\nuniform vec3 qLE[ 24 ];\nuniform vec3 qLC[ 24 ];\nuniform int qLN;\n#endif\n';
    T.ShaderChunk.lights_fragment_begin += [
      '', '#ifdef STANDARD', 'if ( qLN > 0 ) {',
      '  vec3 qWP = ( vec4( geometry.position, 0.0 ) * viewMatrix ).xyz + cameraPosition;',
      '  vec3 qWN = inverseTransformDirection( geometry.normal, viewMatrix );',
      '  vec3 qWV = inverseTransformDirection( geometry.viewDir, viewMatrix );',
      '  vec3 qR = reflect( - qWV, qWN );',
      '  float qAl = max( material.roughness, 0.09 ); qAl *= qAl;',
      '  float qNV = saturate( dot( qWN, qWV ) );',
      '  for ( int i = 0; i < 24; i ++ ) {',
      '    if ( i >= qLN ) break;',
      '    vec3 qa = qLA[ i ].xyz - qWP; vec3 qab = qLB[ i ].xyz - qLA[ i ].xyz; float qlen = length( qab ); vec3 qt = qab / qlen;',
      '    float qt0 = - dot( qa, qt ); vec3 qcp = qa + qt * clamp( qt0, 0.0, qlen ); float qdc = length( qcp ); float qrg = qLA[ i ].w;',
      '    if ( qdc > qrg ) continue;',
      '    vec3 qdv = qa + qt * qt0; float qd2 = max( dot( qdv, qdv ), 1e-5 );',
      '    float qs1 = - qt0; float qs2 = qlen - qt0; float qi1 = inversesqrt( qd2 + qs1 * qs1 ); float qi2 = inversesqrt( qd2 + qs2 * qs2 );',
      '    float qE = max( 0.0, dot( qWN, qdv ) / qd2 * ( qs2 * qi2 - qs1 * qi1 ) - dot( qWN, qt ) * ( qi2 - qi1 ) );',
      '    float qw = 1.0 - pow( qdc / qrg, 4.0 ); qw *= qw;',
      '    float qlobe = smoothstep( - 0.08, 0.55, dot( qLE[ i ], - qcp / max( qdc, 1e-4 ) ) );',
      '    vec3 qcol = qLC[ i ] * ( qlobe * qw );',
      '    reflectedLight.directDiffuse += qcol * qE * BRDF_Lambert( material.diffuseColor );',
      '    float qrt = dot( qR, qt ); float qss = clamp( ( dot( qa, qR ) * qrt - dot( qa, qt ) ) / max( 1.0 - qrt * qrt, 1e-4 ), 0.0, qlen );',
      '    vec3 qlp = qa + qt * qss; float qdl = max( length( qlp ), 1e-3 ); vec3 qld = qlp / qdl; float qNL = saturate( dot( qWN, qld ) );',
      '    if ( qNL > 0.0 ) {',
      '      vec3 qh = normalize( qld + qWV ); float qNH = saturate( dot( qWN, qh ) ); float qa2 = qAl * qAl; float qdn = qNH * qNH * ( qa2 - 1.0 ) + 1.0;',
      '      float qD = qa2 / ( PI * qdn * qdn ); float qap = saturate( qAl + qlen / ( 3.0 * qdl ) ); float qnorm = qAl / qap;',
      '      vec3 qF = material.specularColor + ( 1.0 - material.specularColor ) * pow( 1.0 - saturate( dot( qh, qWV ) ), 5.0 );',
      '      float qsp = min( qD * qnorm * 0.25 / ( qNL * qNV + 0.08 ) * qNL * qlen / ( qdl * qdl + 0.02 ), 30.0 );',
      '      reflectedLight.directSpecular += qcol * qF * qsp;',
      '    }', '  }', '}', '#endif', ''].join('\n');
  })();

  Q.rng = function (seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  };
  Q.hash = function (s) {
    let h = 2166136261;
    for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    return h >>> 0;
  };
  Q.clamp = function (v, a, b) { return Math.min(b, Math.max(a, v)); };

  /* ruído de valor 2D, periódico (px × py células) */
  function lattice(seed, px, py) {
    const r = Q.rng(seed), g = new Float32Array(px * py);
    for (let i = 0; i < g.length; i++) g[i] = r();
    return function (x, y) {
      const xf = Math.floor(x), yf = Math.floor(y);
      let fx = x - xf, fy = y - yf;
      fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy);
      const x0 = ((xf % px) + px) % px, x1 = (x0 + 1) % px;
      const y0 = ((yf % py) + py) % py, y1 = (y0 + 1) % py;
      const a = g[y0 * px + x0], b = g[y0 * px + x1], c = g[y1 * px + x0], d = g[y1 * px + x1];
      return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy;
    };
  }
  Q.lattice = lattice;

  function canvas(w, h) { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; }
  Q.canvas = canvas;
  function tex(c, srgb) {
    const t = new T.CanvasTexture(c);
    t.wrapS = t.wrapT = T.RepeatWrapping;
    if (srgb) t.encoding = T.sRGBEncoding;
    t.anisotropy = Q.maxAniso || 8;
    return t;
  }
  Q.tex = tex;

  /* ---------- madeira: folheado de mogno com veios e listras (ribbon) ---------- */
  Q.makeWoodTexture = function () {
    const W = 2048, H = 1024, c = canvas(W, H), ctx = c.getContext('2d');
    const img = ctx.createImageData(W, H), d = img.data;
    const nR = lattice(11, 14, 3), nW = lattice(12, 4, 4), nF = lattice(13, 420, 14);
    const nF2 = lattice(14, 1024, 40), nP = lattice(15, 2048, 96), nC = lattice(16, 5, 5), nB = lattice(17, 40, 2);
    const dk = [54, 30, 19], md = [94, 55, 33], lt = [128, 82, 50];
    for (let y = 0; y < H; y++) {
      const v = y / H;
      for (let x = 0; x < W; x++) {
        const u = x / W;
        const uu = u + (nW(u * 4, v * 4) - 0.5) * 0.014;
        let rib = nR(uu * 14, v * 3); rib = rib * rib * (3 - 2 * rib);
        const band = nB(uu * 40, v * 2) - 0.5;
        const fine = nF(uu * 256, v * 8) - 0.5;
        const fine2 = nF2(uu * 512, v * 24) - 0.5;
        const pore = nP(uu * 1024, v * 48);
        const cloud = nC(u * 5, v * 5) - 0.5;
        let t = 0.5 + (rib - 0.5) * 0.34 + band * 0.13 + fine * 0.22 + fine2 * 0.2 + cloud * 0.16;
        if (pore > 0.8) t -= (pore - 0.8) * 1.5;
        t = t < 0 ? 0 : t > 1 ? 1 : t;
        let r, g, b;
        if (t < 0.5) { const k = t * 2; r = dk[0] + (md[0] - dk[0]) * k; g = dk[1] + (md[1] - dk[1]) * k; b = dk[2] + (md[2] - dk[2]) * k; }
        else { const k = (t - 0.5) * 2; r = md[0] + (lt[0] - md[0]) * k; g = md[1] + (lt[1] - md[1]) * k; b = md[2] + (lt[2] - md[2]) * k; }
        const i = (y * W + x) * 4;
        d[i] = r; d[i + 1] = g; d[i + 2] = b; d[i + 3] = 255;
      }
    }
    ctx.putImageData(img, 0, 0);
    return tex(c, true);
  };

  /* ---------- piso: porcelanato claro 60×60 com rejunte fino (textura cobre 2×2 peças) ---------- */
  Q.makeFloorTextures = function () {
    const S = 1024, c = canvas(S, S), ctx = c.getContext('2d'), cr = canvas(S, S), cx2 = cr.getContext('2d');
    const img = ctx.createImageData(S, S), d = img.data, ir = cx2.createImageData(S, S), dr = ir.data;
    const n1 = lattice(21, 6, 6), n2 = lattice(22, 28, 28), n3 = lattice(23, 160, 160), n4 = lattice(24, 9, 40);
    const tone = [1.0, 0.985, 0.992, 1.008];
    for (let y = 0; y < S; y++) {
      for (let x = 0; x < S; x++) {
        const u = x / S, v = y / S, i = (y * S + x) * 4;
        const tx = x % 512, ty = y % 512;
        const e = Math.min(tx, 511 - tx, ty, 511 - ty);
        const tl = tone[(x >= 512 ? 1 : 0) + (y >= 512 ? 2 : 0)];
        let m = (n1(u * 6, v * 6) - 0.5) * 0.05 + (n2(u * 28, v * 28) - 0.5) * 0.035 + (n3(u * 160, v * 160) - 0.5) * 0.02;
        const vein = Math.abs(n4(u * 9, v * 40) - 0.5); if (vein < 0.02) m -= (0.02 - vein) * 0.8;
        let r = 212 * tl * (1 + m), g = 206 * tl * (1 + m), b = 194 * tl * (1 + m * 1.1), ro = 0.2 + (n2(u * 28, v * 28) - 0.5) * 0.08 + (n3(u * 160, v * 160) - 0.5) * 0.05;
        if (e < 3.0) { const k = e < 2.0 ? 1 : 1 - (e - 2.0); r = r + (126 - r) * k; g = g + (121 - g) * k; b = b + (113 - b) * k; ro = ro + (0.92 - ro) * k; }
        d[i] = r; d[i + 1] = g; d[i + 2] = b; d[i + 3] = 255;
        const rv = Math.max(0, Math.min(255, ro * 255));
        dr[i] = rv; dr[i + 1] = rv; dr[i + 2] = rv; dr[i + 3] = 255;
      }
    }
    ctx.putImageData(img, 0, 0); cx2.putImageData(ir, 0, 0);
    return { map: tex(c, true), rough: tex(cr, false) };
  };

  /* mapa de normais a partir de ruído (tecidos, tapete) */
  Q.makeNoiseNormal = function (seed, cells, strength) {
    const S = 256, c = canvas(S, S), ctx = c.getContext('2d'), img = ctx.createImageData(S, S), d = img.data;
    const n = lattice(seed, cells, cells), n2 = lattice(seed + 1, cells * 3, cells * 3);
    const h = function (x, y) { return n(x / S * cells, y / S * cells) + 0.5 * n2(x / S * cells * 3, y / S * cells * 3); };
    for (let y = 0; y < S; y++) for (let x = 0; x < S; x++) {
      const dx = (h(x + 1, y) - h(x - 1, y)) * strength, dy = (h(x, y + 1) - h(x, y - 1)) * strength;
      const l = Math.sqrt(dx * dx + dy * dy + 1), i = (y * S + x) * 4;
      d[i] = (-dx / l * 0.5 + 0.5) * 255; d[i + 1] = (dy / l * 0.5 + 0.5) * 255; d[i + 2] = (1 / l * 0.5 + 0.5) * 255; d[i + 3] = 255;
    }
    ctx.putImageData(img, 0, 0);
    return tex(c, false);
  };

  /* matelassê em losangos (colcha) */
  Q.makeQuiltNormal = function () {
    const S = 256, c = canvas(S, S), ctx = c.getContext('2d'), img = ctx.createImageData(S, S), d = img.data;
    const hgt = function (x, y) { const u = ((x + y) / S * 4) % 1, v = ((x - y) / S * 4 + 8) % 1, a = Math.min(u, 1 - u), b = Math.min(v, 1 - v), e = Math.min(a, b); return Math.pow(Math.min(1, e * 5), 0.55); };
    for (let y = 0; y < S; y++) for (let x = 0; x < S; x++) {
      const dx = (hgt(x + 1, y) - hgt(x - 1, y)) * 2.6, dy = (hgt(x, y + 1) - hgt(x, y - 1)) * 2.6, l = Math.sqrt(dx * dx + dy * dy + 1), i = (y * S + x) * 4;
      d[i] = (-dx / l * 0.5 + 0.5) * 255; d[i + 1] = (dy / l * 0.5 + 0.5) * 255; d[i + 2] = (1 / l * 0.5 + 0.5) * 255; d[i + 3] = 255;
    }
    ctx.putImageData(img, 0, 0); return tex(c, false);
  };

  /* halo radial para brilho de neon em parede */
  Q.makeGlowTexture = function () {
    const S = 128, c = canvas(S, S), ctx = c.getContext('2d');
    const g = ctx.createRadialGradient(S / 2, S / 2, 0, S / 2, S / 2, S / 2);
    g.addColorStop(0, 'rgba(255,255,255,1)'); g.addColorStop(0.25, 'rgba(255,255,255,0.45)');
    g.addColorStop(0.6, 'rgba(255,255,255,0.1)'); g.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = g; ctx.fillRect(0, 0, S, S);
    const t = new T.CanvasTexture(c); t.encoding = T.sRGBEncoding; return t;
  };

  /* vista da janela: noite (luzes da cidade) e dia (céu) */
  Q.makeBackdrop = function (day) {
    const S = 512, c = canvas(S, S), ctx = c.getContext('2d'), r = Q.rng(day ? 71 : 72);
    const g = ctx.createLinearGradient(0, 0, 0, S);
    if (day) { g.addColorStop(0, '#5f9fe6'); g.addColorStop(0.55, '#b9d8f5'); g.addColorStop(0.72, '#e9f1f6'); g.addColorStop(1, '#cfd6cf'); }
    else { g.addColorStop(0, '#070b1c'); g.addColorStop(0.55, '#141632'); g.addColorStop(0.75, '#2a1f3f'); g.addColorStop(1, '#0b0a14'); }
    ctx.fillStyle = g; ctx.fillRect(0, 0, S, S);
    // morros e prédios ao fundo
    ctx.fillStyle = day ? '#9fb0a6' : '#0c0d1a';
    ctx.beginPath(); ctx.moveTo(0, S * 0.74);
    for (let x = 0; x <= S; x += 16) ctx.lineTo(x, S * (0.70 + 0.05 * Math.sin(x * 0.011 + 1.2) + 0.02 * Math.sin(x * 0.043)));
    ctx.lineTo(S, S); ctx.lineTo(0, S); ctx.fill();
    for (let i = 0; i < 22; i++) {
      const bw = 14 + r() * 26, bh = 30 + r() * 110, bx = r() * S, by = S * 0.86 - bh * 0.5 + r() * 40;
      ctx.fillStyle = day ? 'rgba(' + (150 + r() * 50 | 0) + ',' + (158 + r() * 40 | 0) + ',' + (160 + r() * 40 | 0) + ',1)' : '#0a0b16';
      ctx.fillRect(bx, by, bw, bh + 200);
      if (!day) for (let k = 0; k < bh / 5; k++) if (r() > 0.55) {
        ctx.fillStyle = r() > 0.3 ? 'rgba(255,214,150,' + (0.5 + r() * 0.5) + ')' : 'rgba(170,200,255,' + (0.5 + r() * 0.5) + ')';
        ctx.fillRect(bx + 2 + Math.floor(r() * (bw - 5)), by + 3 + Math.floor(r() * bh), 2, 2);
      }
    }
    if (!day) for (let i = 0; i < 260; i++) {
      const x = r() * S, y = S * (0.66 + r() * 0.22), a = 0.35 + r() * 0.65, s = r() > 0.92 ? 2.2 : 1.1;
      ctx.fillStyle = r() > 0.35 ? 'rgba(255,205,140,' + a + ')' : (r() > 0.5 ? 'rgba(200,180,255,' + a + ')' : 'rgba(255,255,255,' + a + ')');
      ctx.beginPath(); ctx.arc(x, y, s, 0, 6.3); ctx.fill();
    }
    const t = new T.CanvasTexture(c); t.encoding = T.sRGBEncoding; return t;
  };

  /* papel de parede do monitor */
  Q.makeWallpaper = function (hex) {
    const W = 512, H = 288, c = canvas(W, H), ctx = c.getContext('2d');
    const col = new T.Color(hex), hsl = {}; col.getHSL(hsl);
    const mk = function (dh, s, l) { const k = new T.Color().setHSL((hsl.h + dh + 1) % 1, s, l); return '#' + k.getHexString(); };
    ctx.fillStyle = mk(0.02, 0.6, 0.07); ctx.fillRect(0, 0, W, H);
    const blobs = [[0.22, 0.75, 0.55, 0, 0.9, 0.5], [0.72, 0.3, 0.6, 0.1, 0.85, 0.45], [0.55, 0.95, 0.5, -0.08, 0.9, 0.6], [0.95, 0.85, 0.4, 0.18, 0.8, 0.5]];
    ctx.globalCompositeOperation = 'lighter';
    blobs.forEach(function (b) {
      const g = ctx.createRadialGradient(b[0] * W, b[1] * H, 0, b[0] * W, b[1] * H, b[2] * W);
      g.addColorStop(0, mk(b[3], b[4], b[5])); g.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    });
    ctx.globalCompositeOperation = 'source-over';
    ctx.strokeStyle = 'rgba(255,255,255,0.16)'; ctx.lineWidth = 1.2;
    for (let k = 0; k < 7; k++) { ctx.beginPath(); for (let x = 0; x <= W; x += 8) { const y = H * (0.42 + k * 0.045) + Math.sin(x * 0.012 + k * 0.7) * (26 - k * 2); x ? ctx.lineTo(x, y) : ctx.moveTo(x, y); } ctx.stroke(); }
    ctx.fillStyle = 'rgba(10,10,18,0.55)'; ctx.fillRect(0, H - 13, W, 13);
    ctx.fillStyle = 'rgba(255,255,255,0.8)'; for (let k = 0; k < 6; k++) ctx.fillRect(W / 2 - 42 + k * 15, H - 10, 8, 7);
    const t = new T.CanvasTexture(c); t.encoding = T.sRGBEncoding; t.anisotropy = 4; return t;
  };

  /* arte abstrata para quadros */
  Q.makeArt = function (style, hex, seed) {
    const W = 384, H = 512, c = canvas(W, H), ctx = c.getContext('2d'), r = Q.rng(seed || 5);
    const col = new T.Color(hex), hsl = {}; col.getHSL(hsl);
    const mk = function (dh, s, l) { return '#' + new T.Color().setHSL((hsl.h + dh + 1) % 1, s, l).getHexString(); };
    ctx.fillStyle = '#f3efe6'; ctx.fillRect(0, 0, W, H);
    if (style === 1) { // sol e colinas
      ctx.fillStyle = mk(0.04, 0.75, 0.62); ctx.beginPath(); ctx.arc(W * 0.5, H * 0.36, W * 0.24, 0, 6.3); ctx.fill();
      for (let k = 0; k < 4; k++) {
        ctx.fillStyle = mk(-0.03 * k, 0.5, 0.52 - k * 0.1); ctx.beginPath(); ctx.moveTo(0, H);
        for (let x = 0; x <= W; x += 12) ctx.lineTo(x, H * (0.56 + k * 0.1) + Math.sin(x * 0.014 + k * 1.9) * 26);
        ctx.lineTo(W, H); ctx.fill();
      }
    } else if (style === 2) { // geométrico
      const cols = [mk(0, 0.7, 0.55), mk(0.08, 0.6, 0.7), mk(-0.1, 0.5, 0.35), '#1d1b22', mk(0.5, 0.45, 0.6)];
      for (let k = 0; k < 9; k++) {
        ctx.fillStyle = cols[k % cols.length]; const x = r() * W * 0.8, y = r() * H * 0.8, s = 50 + r() * 130;
        if (k % 3 === 0) { ctx.beginPath(); ctx.arc(x + s / 2, y + s / 2, s / 2, 0, 6.3); ctx.fill(); }
        else if (k % 3 === 1) ctx.fillRect(x, y, s, s * (0.4 + r()));
        else { ctx.beginPath(); ctx.arc(x + s / 2, y + s / 2, s / 2, 0, 3.15); ctx.fill(); }
      }
    } else if (style === 3) { // linhas
      ctx.fillStyle = mk(0, 0.35, 0.14); ctx.fillRect(0, 0, W, H);
      ctx.lineWidth = 2.2;
      for (let k = 0; k < 26; k++) {
        ctx.strokeStyle = mk(k * 0.006, 0.8, 0.45 + k * 0.012); ctx.beginPath();
        for (let x = -10; x <= W + 10; x += 8) { const y = H * 0.2 + k * 13 + Math.sin(x * 0.02 + k * 0.33) * 30 * Math.sin(k * 0.21 + 0.6); x > -10 ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }
        ctx.stroke();
      }
    } else { // campo de cor
      const g = ctx.createLinearGradient(0, 0, W, H); g.addColorStop(0, mk(-0.06, 0.7, 0.62)); g.addColorStop(0.5, mk(0.02, 0.75, 0.5)); g.addColorStop(1, mk(0.12, 0.7, 0.32));
      ctx.fillStyle = g; ctx.fillRect(28, 28, W - 56, H - 56);
      ctx.fillStyle = 'rgba(255,255,255,0.85)'; ctx.beginPath(); ctx.arc(W * 0.68, H * 0.3, 34, 0, 6.3); ctx.fill();
    }
    const t = new T.CanvasTexture(c); t.encoding = T.sRGBEncoding; t.anisotropy = 4; return t;
  };

  /* texto em tubo de neon (mapa de emissão) */
  Q.makeNeonText = function (text) {
    const c = canvas(1024, 256), ctx = c.getContext('2d');
    const font = '600 150px "Sora", "Trebuchet MS", system-ui, sans-serif';
    ctx.font = font; const m = Math.min(980, ctx.measureText(text).width + 60);
    c.width = Math.max(128, Math.ceil(m)); c.height = 256;
    const x = c.getContext('2d'); x.font = font; x.textAlign = 'center'; x.textBaseline = 'middle';
    x.lineJoin = 'round'; x.lineCap = 'round';
    x.shadowColor = '#fff'; x.shadowBlur = 22; x.strokeStyle = 'rgba(255,255,255,0.55)'; x.lineWidth = 9; x.strokeText(text, c.width / 2, 128, 960);
    x.shadowBlur = 0; x.strokeStyle = '#fff'; x.lineWidth = 6; x.strokeText(text, c.width / 2, 128, 960);
    const t = new T.CanvasTexture(c); t.encoding = T.sRGBEncoding; t.anisotropy = 4;
    return { tex: t, aspect: c.width / c.height };
  };

  /* ---------- filme animado original (ação/heróis, sem personagens de terceiros) desenhado em tempo real ---------- */
  Q.film = (function () {
    const W = 480, H = 270, r = Q.rng(2024), avg = new T.Color(0.3, 0.35, 0.6);
    let c = null, ctx, tex, bl, st, sp;
    const hsh = function (a, b, d) { const v = Math.sin(a * 127.1 + b * 311.7 + d * 74.7) * 43758.5453; return v - Math.floor(v); };
    function glow(x, y, rad, col, a) { const g = ctx.createRadialGradient(x, y, 0, x, y, rad); g.addColorStop(0, col); g.addColorStop(1, 'rgba(0,0,0,0)'); ctx.globalAlpha = a; ctx.fillStyle = g; ctx.fillRect(x - rad, y - rad, rad * 2, rad * 2); ctx.globalAlpha = 1; }
    function streak(u, amp, phase, col, core) {
      for (let k = 22; k >= 0; k--) {
        const uu = u - k * 0.011, x = -50 + uu * (W + 100), y = H * (0.52 - amp * Math.sin(uu * Math.PI)) + Math.sin(uu * 9 + phase) * 6, a = (1 - k / 23);
        glow(x, y, 5 + a * 16, k ? col : core, 0.14 + a * a * 0.7);
      }
    }
    function city(t, u) {
      let g = ctx.createLinearGradient(0, 0, 0, H); g.addColorStop(0, '#12183a'); g.addColorStop(0.5, '#6e3460'); g.addColorStop(0.78, '#ee8648'); g.addColorStop(1, '#ffcf8a'); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
      ctx.globalCompositeOperation = 'lighter'; glow(W * 0.68, H * 0.78, 130, 'rgba(255,205,130,1)', 0.75); ctx.globalCompositeOperation = 'source-over';
      for (let L = 0; L < 3; L++) {
        const off = (7 + L * 15) * t, col = ['#3d2c52', '#231b38', '#0d0a1a'][L], base = H * (0.84 + L * 0.06);
        for (let i = 0; i < bl[L].length; i++) {
          const b = bl[L][i], x = (((b[0] - off) % (W * 2)) + W * 2) % (W * 2) - 50; if (x > W) continue;
          ctx.fillStyle = col; ctx.fillRect(x, base - b[2], b[1], b[2] + 70);
          if (L) { ctx.fillStyle = L === 2 ? 'rgba(255,220,160,0.85)' : 'rgba(255,200,150,0.5)'; for (let wy = 6; wy < b[2] - 4; wy += 8) for (let wx = 3; wx < b[1] - 4; wx += 6) if (hsh(b[3], wx, wy) > 0.62) ctx.fillRect(x + wx, base - b[2] + wy, 2.6, 3.6); }
        }
      }
      ctx.globalCompositeOperation = 'lighter';
      streak(u * 1.25, 0.3, 0, 'rgba(90,200,255,1)', 'rgba(240,250,255,1)'); streak(u * 1.25 - 0.13, 0.22, 2, 'rgba(255,90,60,1)', 'rgba(255,230,200,1)');
      ctx.globalCompositeOperation = 'source-over';
      return [1.0, 0.62, 0.42, 0.9];
    }
    function space(t, u) {
      ctx.fillStyle = '#03040d'; ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = '#fff'; for (let i = 0; i < st.length; i++) { const q = st[i], x = (((q[0] - t * 9 * q[2]) % W) + W) % W; ctx.globalAlpha = q[3]; ctx.fillRect(x, q[1], q[2], q[2]); } ctx.globalAlpha = 1;
      const px = W * 0.76 - u * 14, py = H * 0.4, pr = 64;
      let g = ctx.createRadialGradient(px - 22, py - 20, 6, px, py, pr); g.addColorStop(0, '#ffd9a0'); g.addColorStop(0.5, '#c8683e'); g.addColorStop(1, '#2a1020'); ctx.fillStyle = g; ctx.beginPath(); ctx.arc(px, py, pr, 0, 6.3); ctx.fill();
      ctx.strokeStyle = 'rgba(255,225,180,0.75)'; ctx.lineWidth = 3; ctx.beginPath(); ctx.ellipse(px, py, pr * 1.75, pr * 0.42, -0.35, 0.25, Math.PI - 0.25); ctx.stroke();
      ctx.fillStyle = '#c9d2e6'; for (let i = 0; i < 5; i++) { const x = W + 40 - ((t * (38 + i * 9) + i * 97) % (W + 120)), y = H * (0.2 + i * 0.13) + Math.sin(t * 1.3 + i) * 5; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + 18, y - 5); ctx.lineTo(x + 14, y); ctx.lineTo(x + 18, y + 5); ctx.fill(); }
      const cx = W * 0.4, cy = H * 0.58, pulse = 0.6 + 0.4 * Math.sin(t * 13);
      ctx.globalCompositeOperation = 'lighter'; ctx.lineCap = 'round';
      [[0, H * 0.96, 'rgba(70,150,255,', 1], [W, H * 0.12, 'rgba(255,150,50,', -1]].forEach(function (b) {
        for (let k = 0; k < 3; k++) { ctx.strokeStyle = b[2] + (0.22 + k * 0.3) + ')'; ctx.lineWidth = (14 - k * 5.5) * (0.8 + 0.2 * pulse); ctx.beginPath(); ctx.moveTo(b[0], b[1]); ctx.lineTo(cx, cy); ctx.stroke(); }
      });
      glow(cx, cy, 60 + pulse * 26, 'rgba(255,255,255,1)', 0.95); glow(cx, cy, 120, 'rgba(180,160,255,1)', 0.5);
      ctx.globalCompositeOperation = 'source-over';
      return [0.5, 0.6, 1.0, 0.75 + 0.3 * pulse];
    }
    function impact(t, u) {
      const cx = W / 2, cy = H * 0.56; let g = ctx.createRadialGradient(cx, cy, 10, cx, cy, W * 0.7); g.addColorStop(0, '#5a2a6e'); g.addColorStop(1, '#0a0614'); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
      ctx.globalCompositeOperation = 'lighter';
      for (let k = 0; k < 4; k++) { const rr = (u * 1.5 - k * 0.2) * W * 0.62; if (rr <= 0) continue; ctx.strokeStyle = 'rgba(255,190,90,' + Math.max(0, 0.9 - rr / (W * 0.75)) + ')'; ctx.lineWidth = 7 - k; ctx.beginPath(); ctx.ellipse(cx, cy, rr, rr * 0.5, 0, 0, 6.3); ctx.stroke(); }
      ctx.fillStyle = 'rgba(255,225,150,0.95)';
      for (let i = 0; i < sp.length; i++) { const q = sp[i], d = u * q[1] * 300, x = cx + Math.cos(q[0]) * d, y = cy + Math.sin(q[0]) * d * 0.6 + u * u * 110 * q[2]; ctx.globalAlpha = Math.max(0, 1 - u * 1.15); ctx.fillRect(x, y, 2.4, 2.4); }
      ctx.globalAlpha = 1; glow(cx, cy, 90 * (1 - u * 0.5), 'rgba(255,240,200,1)', Math.max(0, 0.95 - u));
      ctx.globalCompositeOperation = 'source-over';
      const fl = Math.max(0, 1 - u * 7); if (fl > 0) { ctx.fillStyle = 'rgba(255,255,255,' + fl + ')'; ctx.fillRect(0, 0, W, H); }
      return [1.0, 0.76, 0.5, 0.7 + fl * 0.8];
    }
    function nebula(t, u) {
      ctx.fillStyle = '#060414'; ctx.fillRect(0, 0, W, H);
      ctx.save(); const z = 1 + u * 0.1; ctx.translate(W / 2, H / 2); ctx.scale(z, z); ctx.translate(-W / 2, -H / 2);
      ctx.globalCompositeOperation = 'lighter';
      [[0.3, 0.4, 150, 'rgba(160,60,220,1)'], [0.66, 0.55, 170, 'rgba(40,120,230,1)'], [0.5, 0.25, 110, 'rgba(240,90,150,1)'], [0.82, 0.3, 90, 'rgba(60,220,200,1)']].forEach(function (b, i) { glow(W * b[0] + Math.sin(t * 0.5 + i * 2) * 22, H * b[1] + Math.cos(t * 0.4 + i) * 12, b[2], b[3], 0.55); });
      ctx.fillStyle = '#fff'; for (let i = 0; i < st.length; i += 2) { const q = st[i]; ctx.globalAlpha = q[3] * (0.6 + 0.4 * Math.sin(t * 3 + i)); ctx.fillRect(q[0], q[1], q[2], q[2]); } ctx.globalAlpha = 1;
      const fx = -80 + u * (W + 160);
      glow(fx, H * 0.475, 44, 'rgba(255,245,230,1)', 0.85);
      ctx.restore(); ctx.globalCompositeOperation = 'source-over';
      return [0.75, 0.45, 0.95, 0.8];
    }
    const shots = [city, space, impact, nebula], LEN = 6;
    function init() {
      c = canvas(W, H); ctx = c.getContext('2d');
      tex = new T.CanvasTexture(c); tex.encoding = T.sRGBEncoding; tex.generateMipmaps = false; tex.minFilter = T.LinearFilter; tex.magFilter = T.LinearFilter;
      bl = [0, 1, 2].map(function (L) { const a = []; let x = 0; while (x < W * 2) { const w = 14 + r() * 26; a.push([x, w, 26 + r() * (54 + L * 34), r() * 9]); x += w + 1 + r() * 4; } return a; });
      st = []; for (let i = 0; i < 110; i++) st.push([r() * W, r() * H, 0.4 + r() * 1.3, 0.3 + r() * 0.7]);
      sp = []; for (let i = 0; i < 70; i++) sp.push([r() * 6.283, 0.3 + r() * 0.9, r()]);
      draw(1.5);
    }
    let vid = null, sm = null, sx = null;
    function clearVideo() { if (vid) { try { vid.pause(); URL.revokeObjectURL(vid.src); } catch (e) { /* ok */ } vid = null; } }
    function setVideo(file, done) {   // vídeo escolhido pela pessoa, tocado só neste aparelho
      clearVideo();
      const v = document.createElement('video'); v.muted = true; v.loop = true; v.playsInline = true; v.setAttribute('playsinline', ''); v.preload = 'auto';
      let settled = false; const fin = function (ok) { if (settled) return; settled = true; if (!ok && vid === v) clearVideo(); if (done) done(ok); };
      v.addEventListener('error', function () { fin(false); }); v.addEventListener('playing', function () { fin(true); });
      try { v.src = URL.createObjectURL(file); vid = v; const pr = v.play(); if (pr && pr.catch) pr.catch(function () { fin(false); }); } catch (e) { fin(false); }
      setTimeout(function () { fin(!!(vid === v && v.readyState >= 2)); }, 6000);
    }
    function drawVideo() {
      const vw = vid.videoWidth, vh = vid.videoHeight, k = Math.min(W / vw, H / vh), dw = vw * k, dh = vh * k;
      ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
      ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H); ctx.drawImage(vid, (W - dw) / 2, (H - dh) / 2, dw, dh);
      try {
        if (!sm) { sm = canvas(4, 4); sx = sm.getContext('2d', { willReadFrequently: true }); }
        sx.drawImage(c, 0, 0, 4, 4); const d = sx.getImageData(0, 0, 4, 4).data; let r0 = 0, g0 = 0, b0 = 0;
        for (let i = 0; i < 64; i += 4) { r0 += d[i]; g0 += d[i + 1]; b0 += d[i + 2]; }
        avg.setRGB(Math.pow(r0 / 4080, 2.2) * 2.2 + 0.03, Math.pow(g0 / 4080, 2.2) * 2.2 + 0.03, Math.pow(b0 / 4080, 2.2) * 2.2 + 0.03);
      } catch (e) { avg.setRGB(0.6, 0.6, 0.7); }
      tex.needsUpdate = true;
    }
    function draw(t) {
      if (!c) { init(); return; }
      if (vid && vid.readyState >= 2 && vid.videoWidth) { drawVideo(); return; }
      const tt = ((t % (LEN * shots.length)) + LEN * shots.length) % (LEN * shots.length), k = Math.floor(tt / LEN), lt = tt - k * LEN;
      ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
      const a = shots[k](lt + k * 3.7, lt / LEN), fade = Math.min(1, lt / 0.22, (LEN - lt) / 0.22);
      if (fade < 1) { ctx.fillStyle = 'rgba(0,0,0,' + (1 - fade) + ')'; ctx.fillRect(0, 0, W, H); }
      const vg = ctx.createRadialGradient(W / 2, H / 2, H * 0.35, W / 2, H / 2, W * 0.62); vg.addColorStop(0, 'rgba(0,0,0,0)'); vg.addColorStop(1, 'rgba(0,0,0,0.5)'); ctx.fillStyle = vg; ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, 20); ctx.fillRect(0, H - 20, W, 20);
      const sec = Math.floor(tt), tc = '0' + Math.floor(sec / 60) + ':' + (sec % 60 < 10 ? '0' : '') + (sec % 60);
      ctx.fillStyle = 'rgba(255,255,255,0.86)'; ctx.font = '600 11px Inter, system-ui, sans-serif'; ctx.textBaseline = 'middle';
      ctx.textAlign = 'left'; ctx.fillText('\u25B6  FILME DE DEMONSTRA\u00C7\u00C3O', 12, H - 10); ctx.textAlign = 'right'; ctx.fillText(tc, W - 12, H - 10);
      const m = Math.min(1.25, a[3]) * fade; avg.setRGB(a[0] * m, a[1] * m, a[2] * m);
      tex.needsUpdate = true;
    }
    return { draw: draw, avg: avg, tex: function () { if (!c) init(); return tex; }, setVideo: setVideo, clearVideo: clearVideo, hasVideo: function () { return !!vid; },
      sound: function (on) { if (vid && on !== undefined) { vid.muted = !on; if (on) { const pr = vid.play(); if (pr && pr.catch) pr.catch(function () { /* ok */ }); } } return !!vid && !vid.muted; } };
  })();

  /* ---------- materiais ---------- */
  Q.initMaterials = function () {
    const M = (Q.M = {});
    const wood = (Q.woodTex = Q.makeWoodTexture());
    const fl = Q.makeFloorTextures();
    Q.fabricN = Q.makeNoiseNormal(31, 48, 2.2);
    Q.rugN = Q.makeNoiseNormal(41, 24, 5.0);
    Q.quiltN = Q.makeQuiltNormal();
    Q.glowTex = Q.makeGlowTexture();
    const phys = function (o) { return new T.MeshPhysicalMaterial(o); }, std = function (o) { return new T.MeshStandardMaterial(o); };
    M.wood = phys({ map: wood, roughness: 0.4, clearcoat: 0.55, clearcoatRoughness: 0.13 });
    M.woodDark = phys({ map: wood, color: new T.Color(0.36, 0.3, 0.3), roughness: 0.45, clearcoat: 0.45, clearcoatRoughness: 0.18 });
    M.doorWood = phys({ map: wood, color: new T.Color(0.92, 0.84, 0.78), roughness: 0.42, clearcoat: 0.5, clearcoatRoughness: 0.15 });
    M.wallC = std({ color: '#c3bfda', roughness: 0.93 });
    M.wallD = std({ color: '#f1efea', roughness: 0.93 });
    M.wallAB = std({ color: '#f1efea', roughness: 0.93 });
    M.ceil = std({ color: '#f6f5f1', roughness: 0.95 });
    M.hall = std({ color: '#efece5', roughness: 0.93, side: T.BackSide });
    M.floor = std({ map: fl.map, roughnessMap: fl.rough, roughness: 1, metalness: 0 });
    M.floorHall = std({ map: fl.map, roughnessMap: fl.rough, roughness: 1, metalness: 0 });
    M.brass = std({ color: '#b8904a', metalness: 1, roughness: 0.32 });
    M.brassDark = std({ color: '#5d4c2c', metalness: 0.9, roughness: 0.5 });
    M.alu = std({ color: '#0d0d0f', metalness: 0.55, roughness: 0.42 });
    M.darkMetal = std({ color: '#141416', metalness: 0.8, roughness: 0.4 });
    M.chrome = std({ color: '#d0d3d8', metalness: 1, roughness: 0.18 });
    M.ivory = std({ color: '#e9e4d6', roughness: 0.5 });
    M.dark = std({ color: '#0c0c0d', roughness: 0.6 });
    M.marble = std({ color: '#e4e0d8', roughness: 0.25 });
    M.acBody = std({ color: '#26272a', roughness: 0.55 });
    M.acLouver = std({ color: '#3c3d41', roughness: 0.5 });
    M.fixture = std({ color: '#f2f2f0', roughness: 0.6 });
    const glass = function (op) {
      return phys({ color: 0x000000, roughness: 0.03, metalness: 0, transparent: true, opacity: op, depthWrite: false,
        blending: T.CustomBlending, blendSrc: T.OneFactor, blendDst: T.OneMinusSrcAlphaFactor, blendEquation: T.AddEquation });
    };
    M.wallCr = M.wallC; M.woodAC = M.wood; M.rodC = M.woodDark; M.darkC = M.dark;   // mesmos materiais, malhas separadas (somem na maquete)
    M.glass = glass(0.05);    // tampos de vidro
    M.glassW = glass(0.07);   // janela
    M.glassPC = glass(0.12);  // gabinete (leve fumê)
    return M;
  };

  /* materiais de objetos (uma instância por uso, para permitir troca de cor) */
  Q.mPlastic = function (c, rough) { return new T.MeshStandardMaterial({ color: c, roughness: rough == null ? 0.45 : rough }); };
  Q.mMetal = function (c, rough) { return new T.MeshStandardMaterial({ color: c, metalness: 1, roughness: rough == null ? 0.3 : rough }); };
  Q.mFabric = function (c, rug) {
    const m = new T.MeshPhysicalMaterial({ color: c, roughness: 0.96, sheen: 0.6, sheenRoughness: 0.6, sheenColor: new T.Color(c).lerp(new T.Color(1, 1, 1), 0.5),
      normalMap: rug ? Q.rugN : Q.fabricN });
    m.normalScale.set(rug ? 1.0 : 0.28, rug ? 1.0 : 0.28);
    return m;
  };
  Q.mLacquer = function (c) { return new T.MeshPhysicalMaterial({ color: c, roughness: 0.38, clearcoat: 0.35, clearcoatRoughness: 0.2 }); };
  /* emissivo com compensação de exposição: a cor exibida é base × k / exposição */
  Q.emisScale = 1;
  Q.mEmis = function (c, k, opts) {
    const m = new T.MeshBasicMaterial(opts || {});
    m.userData.emis = { c: new T.Color(c), k: k };
    m.color.copy(m.userData.emis.c).multiplyScalar(k * Q.emisScale);
    return m;
  };
  Q.refreshEmis = function (root) {
    root.traverse(function (o) {
      const m = o.material;
      if (m && m.userData && m.userData.emis) m.color.copy(m.userData.emis.c).multiplyScalar(m.userData.emis.k * Q.emisScale);
    });
  };
})();
