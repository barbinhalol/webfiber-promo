/* Quarto 3D — aplicativo: estado, passeio, objetos e arraste, luzes, estilos e interface */
(function () {
  'use strict';
  const T = THREE, Q = window.Q, PI = Math.PI, RA = -PI / 2, KEY = 'quarto3d.v4';
  const $ = function (id) { return document.getElementById(id); };
  const app = $('app'), stage = $('stage'), canvas = $('view'), panel = $('panel');
  const V3 = function (x, y, z) { return new T.Vector3(x, y, z); };
  const wide = function () { return window.matchMedia('(min-width: 880px)').matches; };
  let E, room, state, selId = null, tab = 'luzes', paintTarget = 'wallC', dayTex, nightTex, fixEm;
  const insts = new Map(), proxies = [], undoStack = [], thumbs = {};
  const _v = V3(), _o = V3(), _d = V3();

  const WALLS = [['Lilás original', '#c3bfda'], ['Branco neve', '#f4f3ef'], ['Gelo', '#e4e4e0'], ['Areia', '#dccfbb'], ['Cinza claro', '#c7c9ce'], ['Cinza chumbo', '#5b5f69'],
    ['Azul sereno', '#b7cbdf'], ['Azul petróleo', '#2d4f5e'], ['Azul noite', '#1f2a44'], ['Verde sálvia', '#b3c1ac'], ['Verde musgo', '#58694f'], ['Rosa quartzo', '#e8c7c8'],
    ['Rosa antigo', '#cf9aa0'], ['Terracota', '#bd6d4d'], ['Amarelo manteiga', '#efdda9'], ['Preto fosco', '#1e1e22']];
  const CABS = [['Madeira original', 'wood'], ['Branco laqueado', '#f3f2ee'], ['Off-white', '#e8e2d5'], ['Cinza', '#b7b9be'], ['Grafite', '#3a3c42'], ['Preto', '#19191c'],
    ['Azul marinho', '#26355a'], ['Verde', '#3f5a4a'], ['Rosa', '#e3bcc0']];
  const LEDS = [['Azul', '#3d6bff'], ['Ciano', '#19d3ff'], ['Roxo', '#9a4dff'], ['Rosa', '#ff4fa3'], ['Vermelho', '#ff3b3b'], ['Laranja', '#ff8a2a'], ['Âmbar', '#ffb46a'], ['Verde', '#3dff8a'], ['Branco', '#fff1e0']];
  const SOFT = [['Branco', '#f3f1ec'], ['Cinza', '#9a9ca3'], ['Grafite', '#2a2b31'], ['Azul', '#3b4a7a'], ['Azul claro', '#a9c0dc'], ['Verde', '#5d7a62'], ['Rosa', '#d9a6ae'], ['Vinho', '#7a1f2b'], ['Vermelho', '#c81f2a'], ['Mostarda', '#d0a23a'], ['Dourado', '#e0b62b'], ['Terracota', '#c0704f'], ['Marrom', '#8a5a34'], ['Preto', '#151518']];
  const FRAMES = [['Preta', '#151518'], ['Branca', '#f4f1ea'], ['Madeira', '#8a5a34']];
  const TEMPS = [['Quente', '#ffd2a1'], ['Neutra', '#fff1e0'], ['Fria', '#eef4ff']];
  const LIGHT_KEYS = { pc: 1, monitor: 1, teclado: 1, neon: 1, barra_led: 1, abajur: 1, globo: 1, lanterna: 1, tv: 1 };
  /* estilos prontos (curadoria dos agentes de decoração) */
  const THEMES = [
    { nome: 'Original', descricao: 'Como nas fotos: mogno, parede lilás e branco.', paredeJanela: '#c3bfda', paredePorta: '#f0f0ec', teto: '#f6f5f1', armarios: 'madeira', ledTeto: '#3d6bff', ledPrateleiras: '#ffb46a', colcha: '#f3f1ec', manta: '#7a1f2b', tapete: null, cortina: null },
    { nome: 'Rosé e Vinho', descricao: 'Parede rosa clara, colcha clara, manta vinho e luz âmbar.', paredeJanela: '#e3b8b8', paredePorta: '#f4efe9', teto: '#fbf8f4', armarios: 'madeira', ledTeto: '#ffb257', ledPrateleiras: '#ffbf6b', colcha: '#f5f1ea', manta: '#7a1f2b', tapete: '#e9d6cf', cortina: '#fbf6f0' },
    { nome: 'Mogno e Sálvia', descricao: 'Verde-sálvia com o mogno original e detalhes quentes.', paredeJanela: '#8fa39a', paredePorta: '#f2ede4', teto: '#f7f5f0', armarios: 'madeira', ledTeto: '#ffb347', ledPrateleiras: '#ffc978', colcha: '#2f4a5a', manta: '#c8a165', tapete: '#b89f86', cortina: '#f4efe6' },
    { nome: 'Terra Quente', descricao: 'Terracota suave e off-white com LED âmbar.', paredeJanela: '#d2a58a', paredePorta: '#efe6da', teto: '#fbfaf7', armarios: 'madeira', ledTeto: '#ff8c42', ledPrateleiras: '#ffd29a', colcha: '#3d5a4c', manta: '#e0b35a', tapete: '#6f8a7a', cortina: null },
    { nome: 'Branco Clean', descricao: 'Armários brancos, parede azul-névoa e LED frio.', paredeJanela: '#cfd8e0', paredePorta: '#f3efe8', teto: '#ffffff', armarios: '#f5f3ef', ledTeto: '#8ec5ff', ledPrateleiras: '#a8d8ff', colcha: '#e8e1d5', manta: '#7b9fb8', tapete: '#c9bfb0', cortina: '#ffffff' },
    { nome: 'Oliva e Linho', descricao: 'Armários cinza-palha, parede sálvia clara e terracota.', paredeJanela: '#a7b59a', paredePorta: '#ece8df', teto: '#faf9f6', armarios: '#dcdad0', ledTeto: '#5ef2d0', ledPrateleiras: '#7ff5dc', colcha: '#c96b4a', manta: '#f0e2c8', tapete: '#8c9a7c', cortina: '#f7f3ea' },
    { nome: 'Gamer Neon', descricao: 'Ambiente escuro, LED azul e roxo, manta vermelha.', paredeJanela: '#1a1d2e', paredePorta: '#14121f', teto: '#2a2838', armarios: '#1e1e2a', ledTeto: '#3d5bff', ledPrateleiras: '#9b30ff', colcha: '#3a3f66', manta: '#c4161c', tapete: '#101018', cortina: null }
  ];

  /* ---------- estado ---------- */
  function fresh() {
    return { v: 4, seq: 1, dims: Object.assign({}, Q.ROOM_DEFAULT),
      paint: { wallC: '#c3bfda', wallD: '#f0f0ec', ceil: '#f6f5f1', cab: 'wood' },
      lights: { ceiling: { on: true, level: 1, temp: '#fff1e0' }, cove: { on: false, color: '#3d6bff', level: 1 }, shelf: { on: false, color: '#ffb46a', level: 1 }, day: false, exposure: 1 },
      opts: { door: false, curtain: false, curtainColor: '#f4f1ea', quality: 'alta', eye: 1.55, tvInit: true, tvRev: 2 }, objects: null };
  }
  function load() { try { const s = JSON.parse(localStorage.getItem(KEY)); if (s && s.v === 4 && Array.isArray(s.objects)) return s; } catch (e) { /* sem armazenamento */ } return null; }
  let saveT = 0;
  function save() { clearTimeout(saveT); saveT = setTimeout(function () { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* ignora */ } }, 350); }
  function pushUndo() { undoStack.push(JSON.stringify(state)); if (undoStack.length > 40) undoStack.shift(); $('undo').disabled = false; }
  function undo() {
    if (!undoStack.length) return;
    const prev = JSON.parse(undoStack.pop()), dimsChanged = JSON.stringify(prev.dims) !== JSON.stringify(state.dims);
    state = prev; $('undo').disabled = !undoStack.length;
    selId = null;
    if (dimsChanged) buildRoom(); else { applyPaint(); applyLights(); applyOpts(); }
    respawnAll(); select(null); save();
  }

  /* ---------- cômodo ---------- */
  const frameAng = function (m) { return Math.atan2(-m.elements[2], m.elements[0]); };
  const surfByName = function (n) { return room.surfaces.find(function (s) { return s.name === n; }); };
  const wallByName = function (n) { return room.walls.find(function (w) { return w.name === n; }); };
  function buildRoom() {
    room = Q.buildRoom(state.dims); E.setRoom(room);
    room.surfaces.forEach(function (s) { s.ang = frameAng(s.m); });
    room.walls.forEach(function (w) { w.ang = frameAng(w.m); });
    room.backdrop.material.map = state.lights.day ? dayTex : nightTex;
    applyPaint(); applyLights(); applyOpts();
  }
  function applyPaint() {
    const M = Q.M, p = state.paint;
    M.wallC.color.set(p.wallC); M.wallD.color.set(p.wallD); M.wallAB.color.set(p.wallD); M.hall.color.set(p.wallD); M.ceil.color.set(p.ceil);
    if (p.cab === 'wood') { M.wood.map = Q.woodTex; M.wood.color.set('#ffffff'); M.wood.roughness = 0.4; M.wood.clearcoat = 0.55; }
    else { M.wood.map = null; M.wood.color.set(p.cab); M.wood.roughness = 0.36; M.wood.clearcoat = 0.32; }
    M.wood.needsUpdate = true;
    E.touch(false, 4);
  }
  const POWER = { cove: 0.95, shelf: 0.5 }, RANGE = { cove: 4.8, shelf: 1.9 };
  function syncLines() {
    if (!room) return;
    const L = state.lights, list = [], col = new T.Color();
    ['cove', 'shelf'].forEach(function (k) {
      if (!L[k].on) return;
      room.leds[k].forEach(function (s) { list.push({ a: s.a, b: s.b, e: s.e, color: col.set(L[k].color).clone(), power: POWER[k] * L[k].level, range: RANGE[k] }); });
    });
    insts.forEach(function (i) {
      const ls = i.group.userData.lines; if (!ls) return;
      i.group.updateMatrixWorld(true); const m = i.group.matrixWorld;
      ls.forEach(function (l) { list.push({ a: V3(l.a[0], l.a[1], l.a[2]).applyMatrix4(m), b: V3(l.b[0], l.b[1], l.b[2]).applyMatrix4(m), e: V3(l.e[0], l.e[1], l.e[2]).transformDirection(m), color: new T.Color(l.color), power: l.power, range: l.range }); });
    });
    Q.LL.set(list);
    syncFilm(); syncSpot();
  }
  function applyLights() {
    const L = state.lights, r = room, wh = new T.Color(1, 1, 1);
    r.lamp.visible = L.ceiling.on; r.lamp.intensity = Q.LAMP * L.ceiling.level; r.lamp.color.set(L.ceiling.temp);
    if (!fixEm) fixEm = Q.mEmis('#ffffff', 5.5);
    fixEm.userData.emis.c.set(L.ceiling.temp).lerp(wh, 0.25);
    r.fixGlow.material = L.ceiling.on ? fixEm : Q.M.fixture;
    [['cove', r.emCove], ['shelf', r.emShelf]].forEach(function (g) {
      const c = L[g[0]]; g[1].userData.emis.c.set(c.color);
      r.leds[g[0]].forEach(function (s) { s.mesh.visible = c.on; });
    });
    syncLines();
    r.sun.visible = L.day; r.sun.intensity = L.day ? 34 : 0;
    const bm = r.backdrop.material;
    bm.map = L.day ? dayTex : nightTex; bm.userData.emis.k = L.day ? 1.35 : 0.55; bm.needsUpdate = true;
    r.sky.visible = L.day; r.sky.intensity = L.day ? 12 : 0;
    E.userExposure = L.exposure;
    Q.refreshEmis(E.scene); E.touch(true, 4); syncScenes();
  }
  function applyOpts() {
    const o = state.opts;
    room.door.rotation.y = o.door ? -1.5 : 0; E.doorOpen = o.door;
    E.curtainOn = o.curtain; room.curtain.userData.mat.color.set(o.curtainColor);
    E.touch(true, 3);
  }

  /* ---------- objetos ---------- */
  const paramsOf = function (rec) { return Object.assign({}, Q.catalog[rec.type].defaults, rec.p || {}); };
  const topsOf = function (i) { return i.def.topsFor ? i.def.topsFor(paramsOf(i.rec)) : i.def.tops; };
  function putOn(rec, name, u, w) {
    const s = surfByName(name), p = _v.set(u, 0, w).applyMatrix4(s.m);
    rec.x = p.x; rec.z = p.z; rec.y = s.y; rec.surf = name; rec.u = u; rec.w = w; rec.on = null; return rec;
  }
  function putWall(rec, name, s, y) {
    const wl = wallByName(name), p = _v.set(s, y, 0).applyMatrix4(wl.m);
    rec.x = p.x; rec.y = p.y; rec.z = p.z; rec.rot = wl.ang; rec.wall = name; rec.s = s; rec.wy = y; return rec;
  }
  function putTop(rec, owner, k, lx, lz) {   // sobre a k-ésima superfície de outro objeto
    const d = Q.catalog[owner.type], tp = (d.topsFor ? d.topsFor(Object.assign({}, d.defaults, owner.p || {})) : d.tops)[k], c = Math.cos(owner.rot), s = Math.sin(owner.rot);
    rec.x = owner.x + lx * c + lz * s; rec.z = owner.z - lx * s + lz * c; rec.y = owner.y + tp.y; rec.on = owner.id; rec.surf = null; rec.rot = owner.rot; return rec;
  }
  function defaultObjects() {
    const r = room, list = [], dU = (r.uT + r.uD - r.t) / 2;
    const add = function (type, o) { const rec = Object.assign({ id: 'o' + state.seq++, type: type, x: 0, y: 0, z: 0, rot: 0, p: {}, on: null }, o || {}); list.push(rec); return rec; };
    // setup: gabinete na torre da esquerda, só a tela na bancada
    const pc = putOn(add('pc', { rot: RA }), 'torre', r.uT / 2, 0.27);
    putTop(add('console'), pc, 0, 0, 0.02);
    putOn(add('monitor', { rot: RA }), 'bancada', dU, 0.2);
    putOn(add('mousepad', { rot: RA }), 'bancada', dU, 0.36);
    putOn(add('teclado', { rot: RA }), 'bancada', dU - 0.08, 0.39);
    putOn(add('mouse', { rot: RA }), 'bancada', dU + 0.2, 0.39);
    putOn(add('microfone', { rot: RA + 0.5 }), 'bancada', r.uT + 0.12, 0.2);
    add('cadeira', { rot: PI / 2 + 0.1, x: r.LB - 0.21, z: r.zA + (r.uT + r.uDu) / 2 + 0.02 });
    add('cama', { rot: PI, x: r.nicheC, z: r.Dp - 0.03 - 1.004, p: { color: '#f3f1ec', accent: '#7a1f2b' } });
    putOn(add('jiboia', { rot: RA }), 'torre-prateleira', r.uT / 2 + 0.1, 0.24);
    putOn(add('livros', { rot: RA }), 'bancada-prat1', r.uT + 0.2, 0.13);
    const wl = wallByName('janela-esq');
    putWall(add('mobile'), 'janela-esq', wl.s1 - 0.036, Math.min(wl.y1 - 0.4, 1.95));
    putWall(add('tv_braco'), 'janela-esq', wl.s1 - TV_GAP, Math.min(1.5, wl.y1 - 0.32));                 // placa do suporte colada na janela; aberta, a TV fica sobre os pés da cama
    // parede da porta: rack + TV + estante iluminada, como na referência
    const R = r.dx0 - 0.19, eW = 0.66; let gapC = 0.16, rackW = R - gapC - 0.02 - eW;
    if (rackW < 1.0) { gapC = 0.05; rackW = R - gapC - 0.02 - eW; }
    rackW = Math.floor(Q.clamp(rackW, 0.75, 1.3) * 20 + 0.001) / 20;
    if (r.dx0 > 1.5) {
      const rack = add('rack', { x: gapC + rackW / 2, z: 0.215, p: { w: rackW } });
      const tv = putTop(add('tv', { p: { pol: rackW >= 1.15 ? 43 : rackW >= 0.95 ? 40 : 32 } }), rack, 0, 0, -0.02);
      const tvW = 0.965 * (tv.p.pol / 43);
      if (rackW - tvW > 0.2) { putTop(add('boneco', { p: { color: '#2a4fa0', accent: '#c62828' } }), rack, 0, -rackW / 2 + 0.07, 0.07); putTop(add('boneco', { p: { color: '#b3121c', accent: '#1a1a1a' } }), rack, 0, rackW / 2 - 0.07, 0.07); }
      else { putTop(add('boneco', { p: { color: '#2a4fa0', accent: '#c62828' } }), rack, 1, -rackW / 2 + 0.1, 0.1); }
      putTop(add('aparelho'), rack, 1, -rackW / 2 + 0.2, 0.02);
      putTop(add('aparelho', { p: { color: '#17181b' } }), rack, 1, 0.05, 0.02);
      putTop(add('controle'), rack, 1, rackW / 2 - 0.13, 0.05);
      const est = add('estante', { x: gapC + rackW + 0.02 + eW / 2, z: 0.155 });
      putTop(add('jiboia', { p: { color: '#2a2b2e' } }), est, 5, 0.12, 0.0);
      putTop(add('colecao', { p: { style: 1 } }), est, 4, -0.12, 0.03); putTop(add('boneco', { p: { color: '#c8202a', accent: '#d9a325' } }), est, 4, 0.2, 0.05);
      putTop(add('boneco', { p: { color: '#c8102e', accent: '#1f4fa0' } }), est, 3, -0.2, 0.05); putTop(add('colecao', { p: { style: 1 } }), est, 3, 0.12, 0.03);
      putTop(add('colecao', { p: { style: 2 } }), est, 2, -0.12, 0.03); putTop(add('boneco', { p: { color: '#a0804f', accent: '#6b4f2e' } }), est, 2, 0.13, 0.05); putTop(add('lanterna'), est, 2, 0.25, 0.06);
      putTop(add('colecao', { p: { style: 4 } }), est, 1, -0.12, 0.03); putTop(add('globo'), est, 1, 0.2, 0.04);
      putTop(add('colecao', { p: { style: 1, wide: true } }), est, 0, 0, 0.03);
    }
    return list;
  }
  const proxyMat = new T.MeshBasicMaterial({ visible: false }); proxyMat.userData.shared = true;

  /* ---------- TV com suporte articulado: pose, mira na cama, filme e ponto na parede ---------- */
  const POSE = ['ext', 'side', 'swivel', 'tilt'], TV_GAP = 0.135;   // distância da placa do suporte até o fim da parede, do lado da janela
  const spanOf = function (i) { return i.def.spanFor ? i.def.spanFor(paramsOf(i.rec)) : null; };
  const poseOf = function (rec) { const q = paramsOf(rec); return { ext: +q.ext || 0, side: +q.side || 0, swivel: +q.swivel || 0, tilt: +q.tilt || 0 }; };
  function setPose(i, vals, instant) {
    if (!i || !i.pose) return; i.rec.p = i.rec.p || {};
    POSE.forEach(function (k) { if (k in vals) { i.rec.p[k] = vals[k]; if (instant) i.pose[k] = vals[k]; } });
    if (instant) i.group.userData.pose(i.pose);
    needEnv = true; settle = performance.now(); E.touch(true, 0); updateQuick();
  }
  function aimBed(i) {   // vira a tela para o travesseiro da cama
    let tgt = null;
    insts.forEach(function (k) { if (!tgt && k.rec.type === 'cama') { const lz = -0.66; tgt = V3(k.rec.x + lz * Math.sin(k.rec.rot), k.rec.y + 0.66, k.rec.z + lz * Math.cos(k.rec.rot)); } });
    if (!tgt) tgt = V3(room.nicheC, 0.66, room.Dp - 0.6);
    i.group.updateMatrixWorld(true); const l = i.group.worldToLocal(tgt.clone());
    const wz = 0.6, dist = Math.hypot(l.x, l.z - wz);
    return { ext: 1, side: 0, swivel: Math.round(Q.clamp((Math.atan2(l.x, l.z - wz) * 180) / PI, -90, 90)), tilt: Math.round(Q.clamp((Math.atan2(-l.y, dist) * 180) / PI, -5, 15)) };
  }
  const CLOSED = { ext: 0, side: 0, swivel: 0, tilt: 0 };
  function togglePose() {
    const i = insts.get(selId); if (!i || !i.pose) return; pushUndo();
    const open = poseOf(i.rec).ext > 0.3; setPose(i, open ? CLOSED : aimBed(i)); renderPanel(); save();
    if (!open) toast('Tela virada para o travesseiro. Toque em "Ver da cama" para assistir.');
  }
  function updateQuick() {
    const i = insts.get(selId), q = $('quick'), q2 = $('quick2'), open = !!(i && i.pose) && poseOf(i.rec).ext > 0.3;
    q.hidden = !(i && i.pose); q2.hidden = !open; if (i && i.pose) q.textContent = open ? 'Recolher' : 'Virar para a cama';
  }
  function syncFilm() { let on = false; insts.forEach(function (i) { if (i.group.userData.film) on = true; }); if (E.filmOn !== on) { E.filmOn = on; E.touch(); } }
  const spot = new T.Group();   // marca "+ TV" na parede quando a TV foi removida: tocar nela recoloca
  (function () {
    const c = Q.canvas(256, 160), x = c.getContext('2d'), r = 18;
    x.beginPath(); x.moveTo(8 + r, 8); x.arcTo(248, 8, 248, 152, r); x.arcTo(248, 152, 8, 152, r); x.arcTo(8, 152, 8, 8, r); x.arcTo(8, 8, 248, 8, r); x.closePath();
    x.fillStyle = 'rgba(24,20,34,0.5)'; x.fill(); x.strokeStyle = 'rgba(255,255,255,0.95)'; x.lineWidth = 5; x.setLineDash([16, 12]); x.stroke();
    x.setLineDash([]); x.fillStyle = 'rgba(255,255,255,0.96)'; x.font = '600 36px Inter, system-ui, sans-serif'; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText('+ TV', 128, 82);
    const t = new T.CanvasTexture(c); t.encoding = T.sRGBEncoding;
    const m = new T.Mesh(new T.PlaneGeometry(0.62, 0.39), new T.MeshBasicMaterial({ map: t, transparent: true, opacity: 0.9, depthWrite: false })); m.position.z = 0.006; m.layers.set(1); m.renderOrder = 6; spot.add(m);
    const pk = new T.Mesh(new T.PlaneGeometry(0.7, 0.46), proxyMat); pk.position.z = 0.008; pk.visible = false; spot.add(pk); spot.userData.pick = pk;
  })();
  function spotInfo() {
    const o = state.opts.tvSpot, w0 = o && wallByName(o.wall), sp = Q.catalog.tv_braco.spanFor(Q.catalog.tv_braco.defaults);
    if (w0 && w0.s1 - w0.s0 > sp[1] - sp[0] - 0.03) return { wl: w0, s: Q.clamp(o.s, Math.min(w0.s0 - sp[0], w0.s1 - sp[1]), w0.s1 - sp[1]), y: o.y };
    const wl = wallByName('janela-esq'); return { wl: wl, s: wl.s1 - TV_GAP, y: Math.min(1.5, wl.y1 - 0.32) };
  }
  function syncSpot() {
    if (!room || !state.objects) return;
    if (state.objects.some(function (r) { return r.type === 'tv_braco'; })) { if (spot.parent) { E.scene.remove(spot); E.touch(); } return; }
    const sp = spotInfo(); spot.position.copy(_v.set(sp.s - Q.TV_OFF, sp.y, 0).applyMatrix4(sp.wl.m)); spot.rotation.y = sp.wl.ang;
    if (!spot.parent) E.scene.add(spot); E.touch();
  }
  function wallTvRec() { const sp = spotInfo(), rec = { id: 'o' + state.seq++, type: 'tv_braco', x: 0, y: 0, z: 0, rot: 0, p: {}, on: null }; putWall(rec, sp.wl.name, sp.s, sp.y); return rec; }
  function addWallTv() {
    pushUndo(); const rec = wallTvRec(); state.objects.push(rec); spawn(rec); syncLines(); select(rec.id);
    toast('TV no suporte. Toque em "Virar para a cama" para abrir o braço.'); E.touch(true, 2); save();
  }
  function spawn(rec) {
    const d = Q.catalog[rec.type]; if (!d) return null;
    const g = Q.makeObject(rec.type, paramsOf(rec), (Q.hash(rec.id) % 9973) + 1);
    const size = g.userData.size, wm = d.mount === 'wall';
    const pp = g.userData.proxyParent, ps = g.userData.proxySize || size;
    const proxy = new T.Mesh(new T.BoxGeometry(Math.max(ps[0], 0.06), Math.max(ps[1], 0.03), Math.max(ps[2], 0.05)), proxyMat);
    if (pp) { proxy.position.set(0, 0, g.userData.proxyZ || 0); pp.add(proxy); } else { proxy.position.set(0, wm ? 0 : Math.max(size[1], 0.03) / 2, wm ? size[2] / 2 : 0); g.add(proxy); }
    proxy.visible = false; proxy.userData.id = rec.id;
    g.position.set(rec.x, rec.y, rec.z); g.rotation.y = rec.rot || 0;
    E.scene.add(g);
    const inst = { rec: rec, def: d, group: g, proxy: proxy, size: size };
    if (g.userData.pose) { inst.pose = poseOf(rec); g.userData.pose(inst.pose); }
    insts.set(rec.id, inst); proxies.push(proxy); return inst;
  }
  function despawn(id) {
    const i = insts.get(id); if (!i) return;
    E.scene.remove(i.group); Q.disposeObject(i.group); proxies.splice(proxies.indexOf(i.proxy), 1); insts.delete(id);
  }
  function respawnAll() { Array.from(insts.keys()).forEach(despawn); state.objects.forEach(spawn); syncLines(); E.touch(true, 3); }
  function snapTo(i) { i.group.position.set(i.rec.x, i.rec.y, i.rec.z); i.group.rotation.y = i.rec.rot; }
  function dependents(id, set) {
    set = set || new Set();
    insts.forEach(function (i) { if (i.rec.on === id && !set.has(i.rec.id)) { set.add(i.rec.id); dependents(i.rec.id, set); } });
    return set;
  }
  function ext(i, ang) { const c = Math.abs(Math.cos(ang)), s = Math.abs(Math.sin(ang)), hx = i.size[0] / 2, hz = i.size[2] / 2; return [c * hx + s * hz, s * hx + c * hz]; }

  /* piso: mantém dentro do quarto e fora dos armários (e dos outros móveis, se excl for dado) */
  function resolveFloor(x, z, ex, ez, h, flat, excl) {
    const W = room.W, D = room.Dp;
    const cl = function () { x = ex * 2 >= W ? W / 2 : Q.clamp(x, ex, W - ex); z = ez * 2 >= D ? D / 2 : Q.clamp(z, ez, D - ez); };
    cl(); if (flat) return { x: x, z: z };
    let obs = room.obstacles;
    if (excl) {
      obs = obs.slice();
      insts.forEach(function (k) {
        const r = k.rec; if (excl.has(r.id) || k.def.flat || k.def.mount === 'wall' || r.on || r.surf) return;
        const e = ext(k, r.rot); obs.push({ x0: r.x - e[0] + 0.012, x1: r.x + e[0] - 0.012, z0: r.z - e[1] + 0.012, z1: r.z + e[1] - 0.012, y0: 0 });
      });
    }
    for (let it = 0; it < 6; it++) {
      let hit = false;
      for (let k = 0; k < obs.length; k++) {
        const o = obs[k]; if (h <= o.y0) continue;
        const ox = Math.min(x + ex, o.x1) - Math.max(x - ex, o.x0), oz = Math.min(z + ez, o.z1) - Math.max(z - ez, o.z0);
        if (ox > 0.0005 && oz > 0.0005) { hit = true; if (ox < oz) x += x < (o.x0 + o.x1) / 2 ? -ox : ox; else z += z < (o.z0 + o.z1) / 2 ? -oz : oz; }
      }
      cl(); if (!hit) return { x: x, z: z };
    }
    return null;
  }
  function surfaces(excl) {
    const list = room.surfaces.slice();
    insts.forEach(function (i) {
      const tops = topsOf(i); if (!tops || excl.has(i.rec.id)) return;
      const m = new T.Matrix4().makeRotationY(i.rec.rot).setPosition(i.rec.x, 0, i.rec.z), inv = m.clone().invert();
      tops.forEach(function (t) { list.push({ name: 'obj', label: i.def.name, m: m, inv: inv, u0: t.x0, u1: t.x1, w0: t.z0, w1: t.z1, y: i.rec.y + t.y, clear: t.clear, owner: i.rec.id, ang: i.rec.rot }); });
    });
    return list;
  }
  /* encaixa o objeto numa superfície elevada: folga de altura, limites, encosto no fundo e colisão com vizinhos */
  function fitOn(i, s, px, pz, excl, strict) {
    const rec = i.rec, h = i.size[1];
    if (h > s.clear + 0.004) return null;
    _v.set(px, 0, pz).applyMatrix4(s.inv); let u = _v.x, w = _v.z; const tol = 0.09;
    if (strict && (u < s.u0 - tol || u > s.u1 + tol || w < s.w0 - tol || w > s.w1 + tol)) return null;
    const e = ext(i, rec.rot - s.ang), su = s.u1 - s.u0, sw = s.w1 - s.w0;
    if (e[0] * 2 > su * 1.25 + 0.02 || e[1] * 2 > sw * 1.7 + 0.02) return null;
    const cl = function () {
      u = e[0] * 2 >= su ? (s.u0 + s.u1) / 2 : Q.clamp(u, s.u0 + e[0], s.u1 - e[0]);
      w = e[1] * 2 >= sw ? s.w0 + e[1] : Q.clamp(w, s.w0 + e[1], s.w1 - e[1]);
    };
    cl();
    if (!i.def.flat && e[1] * 2 < sw && w - e[1] - s.w0 < 0.028) w = s.w0 + e[1];           // encosta no fundo
    if (!i.def.flat) {
      const nb = [];
      insts.forEach(function (k) {
        const r = k.rec; if (excl.has(r.id) || k.def.flat || k.def.mount === 'wall' || Math.abs(r.y - s.y) > 0.02) return;
        if (s.owner ? r.on !== s.owner : r.surf !== s.name) return;
        _o.set(r.x, 0, r.z).applyMatrix4(s.inv); const ke = ext(k, r.rot - s.ang); nb.push([_o.x, _o.z, ke[0] - 0.006, ke[1] - 0.006]);
      });
      let ok = !nb.length;
      for (let it = 0; it < 5 && !ok; it++) {
        let hit = false;
        for (let k = 0; k < nb.length; k++) {
          const o = nb[k], ou = Math.min(u + e[0], o[0] + o[2]) - Math.max(u - e[0], o[0] - o[2]), ow = Math.min(w + e[1], o[1] + o[3]) - Math.max(w - e[1], o[1] - o[3]);
          if (ou > 0.0005 && ow > 0.0005) { hit = true; if (ou < ow) u += u < o[0] ? -ou : ou; else w += w < o[1] ? -ow : ow; }
        }
        cl(); ok = !hit;
      }
      if (!ok) return null;
    }
    _v.set(u, 0, w).applyMatrix4(s.m);
    return { x: _v.x, z: _v.z, y: s.y, on: s.owner, surf: s.owner ? null : s.name, u: u, w: w, label: s.label || s.name };
  }
  function placeSurface(i, ray, off, excl) {
    const rec = i.rec, h = i.size[1], list = surfaces(excl); let best = null;
    if (ray.direction.y > -0.002) return null;
    for (let k = 0; k < list.length; k++) {
      const s = list[k], fl = s.name === 'floor';
      if (i.def.mount === 'floor' && !fl) continue;
      const tt = (s.y - ray.origin.y) / ray.direction.y; if (tt <= 0 || (best && tt > best.t)) continue;
      const px = ray.origin.x + ray.direction.x * tt + off.x, pz = ray.origin.z + ray.direction.z * tt + off.z;
      let c;
      if (fl) { const e = ext(i, rec.rot), r = resolveFloor(px, pz, e[0], e[1], h, i.def.flat, excl); if (!r) continue; c = { x: r.x, z: r.z, y: 0, on: null, surf: null, label: 'Piso' }; }
      else { c = fitOn(i, s, px, pz, excl, true); if (!c) continue; }
      c.t = tt; best = c;
    }
    return best;
  }
  function placeWall(i, ray, woff) {
    const hw = i.size[0] / 2, hh = i.size[1] / 2, span = spanOf(i); let best = null;
    for (let k = 0; k < room.walls.length; k++) {
      const wl = room.walls[k];
      _o.copy(ray.origin).applyMatrix4(wl.inv); _d.copy(ray.direction).transformDirection(wl.inv);
      if (_d.z > -0.002) continue;
      const tt = -_o.z / _d.z; if (tt <= 0 || (best && tt > best.t)) continue;
      const s = _o.x + _d.x * tt, y = _o.y + _d.y * tt;
      if (s < wl.s0 - 0.12 || s > wl.s1 + 0.12 || y < wl.y0 - 0.12 || y > wl.y1 + 0.12) continue;
      const c = wallAt(wl, s + (woff ? woff.s : 0), y + (woff ? woff.y : 0), hw, hh, span); if (c) { c.t = tt; best = c; }
    }
    return best;
  }
  function wallAt(wl, s, y, hw, hh, span) {   // span = [esquerda, direita] ocupados a partir do ponto de fixação (objetos descentrados, como a TV no suporte)
    const a = span ? -span[0] : hw, b = span ? span[1] : hw;
    if (a + b > wl.s1 - wl.s0 + 0.03 || hh * 2 > wl.y1 - wl.y0 + 0.03) return null;
    const lo = wl.s0 + a, hi = wl.s1 - b, my = (wl.y0 + wl.y1) / 2;
    s = lo > hi ? (lo + hi) / 2 : Q.clamp(s, lo, hi); y = Q.clamp(y, Math.min(wl.y0 + hh, my), Math.max(wl.y1 - hh, my));
    _v.set(s, y, 0).applyMatrix4(wl.m);
    return { x: _v.x, y: _v.y, z: _v.z, rot: wl.ang, wall: wl.name, s: s, wy: y, label: 'Parede' };
  }
  function supportOf(i, excl) {
    const rec = i.rec; if (rec.surf) return surfByName(rec.surf);
    if (rec.on) return surfaces(excl).find(function (s) { return s.owner === rec.on && Math.abs(s.y - rec.y) < 0.02; });
    return null;
  }
  /* tenta levar o objeto para (x, z) no mesmo apoio em que está (ajuste fino, girar, duplicar) */
  function tryMove(i, x, z) {
    const excl = dependents(i.rec.id); excl.add(i.rec.id);
    const s = supportOf(i, excl);
    if (s) return fitOn(i, s, x, z, excl, false);
    const e = ext(i, i.rec.rot), r = resolveFloor(x, z, e[0], e[1], i.size[1], i.def.flat, excl);
    return r ? { x: r.x, z: r.z, y: 0, on: null, surf: null } : null;
  }
  function moveTo(i, c) {
    const rec = i.rec, dx = c.x - rec.x, dy = c.y - rec.y, dz = c.z - rec.z;
    rec.x = c.x; rec.y = c.y; rec.z = c.z;
    if (c.rot !== undefined) rec.rot = c.rot;
    if ('on' in c) { rec.on = c.on; rec.surf = c.surf || null; rec.u = c.u; rec.w = c.w; }
    if ('wall' in c) { rec.wall = c.wall; rec.s = c.s; rec.wy = c.wy; }
    dependents(rec.id).forEach(function (id) { const k = insts.get(id); k.rec.x += dx; k.rec.y += dy; k.rec.z += dz; });
  }
  /* reposiciona tudo depois de mudar as medidas do quarto */
  function relayout() {
    const delta = {};
    state.objects.forEach(function (rec) {
      const d = Q.catalog[rec.type]; if (!d || rec.on) return;
      const ox = rec.x, oy = rec.y, oz = rec.z, size = d.size;
      if (d.mount === 'wall') {
        const wl = wallByName(rec.wall) || wallByName('porta');
        const sp = d.spanFor ? d.spanFor(Object.assign({}, d.defaults, rec.p || {})) : [-size[0] / 2, size[0] / 2], lo = Math.min(wl.s0 - sp[0], wl.s1 - sp[1]);
        putWall(rec, wl.name, Q.clamp(rec.s == null ? (wl.s0 + wl.s1) / 2 : rec.s, lo, Math.max(lo, wl.s1 - sp[1])), Q.clamp(rec.wy == null ? 1.5 : rec.wy, wl.y0 + size[1] / 2, Math.max(wl.y0 + size[1] / 2, wl.y1 - size[1] / 2)));
      } else if (rec.surf && surfByName(rec.surf)) {
        const s = surfByName(rec.surf); putOn(rec, rec.surf, Q.clamp(rec.u, s.u0 + 0.03, s.u1 - 0.03), Q.clamp(rec.w, s.w0 + 0.03, Math.max(s.w0 + 0.03, s.w1 - 0.03)));
      } else {
        const c = Math.abs(Math.cos(rec.rot)), sn = Math.abs(Math.sin(rec.rot)), ex = c * size[0] / 2 + sn * size[2] / 2, ez = sn * size[0] / 2 + c * size[2] / 2;
        const r = resolveFloor(rec.x, rec.z, ex, ez, size[1], d.flat) || { x: room.LB / 2, z: room.LA / 2 };
        rec.x = r.x; rec.z = r.z; rec.y = 0;
      }
      delta[rec.id] = [rec.x - ox, rec.y - oy, rec.z - oz];
    });
    for (let pass = 0; pass < 3; pass++) state.objects.forEach(function (rec) {
      if (rec.on && delta[rec.on] && !delta[rec.id]) { const dl = delta[rec.on]; rec.x += dl[0]; rec.y += dl[1]; rec.z += dl[2]; delta[rec.id] = dl; }
    });
  }

  /* ---------- seleção, marcador e arraste ---------- */
  const ray = new T.Raycaster(), ndc = new T.Vector2();
  const selBox = new T.LineSegments(new T.EdgesGeometry(new T.BoxGeometry(1, 1, 1)), new T.LineBasicMaterial({ color: 0xc8d6ff, transparent: true, opacity: 0.95, depthTest: false }));
  const mark = new T.Group();
  (function () {
    const sq = new T.BufferGeometry().setFromPoints([V3(-0.5, 0, -0.5), V3(0.5, 0, -0.5), V3(0.5, 0, 0.5), V3(-0.5, 0, 0.5)]);
    mark.add(new T.LineLoop(sq, new T.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.95, depthTest: false })));
    const pg = new T.PlaneGeometry(1, 1); pg.rotateX(-PI / 2);
    mark.add(new T.Mesh(pg, new T.MeshBasicMaterial({ color: 0x8aa9ff, transparent: true, opacity: 0.22, depthTest: false, side: T.DoubleSide })));
  })();
  function setRay(ev) { const r = canvas.getBoundingClientRect(); ndc.set(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1); ray.setFromCamera(ndc, E.camera); }
  function pick() {
    const h = ray.intersectObjects(proxies, false); if (!h.length) return null;
    let best = h[0], bv = Infinity;
    for (let k = 0; k < h.length && h[k].distance < h[0].distance + 0.06; k++) { const g = h[k].object.geometry.parameters, v = g.width * g.height * g.depth; if (v < bv) { bv = v; best = h[k]; } }
    return best.object.userData.id;
  }
  function syncSel() {
    const i = insts.get(selId);
    if (!i) { E.overlay.remove(selBox); return; }
    E.overlay.add(selBox); i.group.updateMatrixWorld(true);
    i.proxy.getWorldPosition(selBox.position); i.proxy.getWorldQuaternion(selBox.quaternion);
    const g = i.proxy.geometry.parameters; selBox.scale.set(g.width + 0.025, g.height + 0.025, g.depth + 0.025);
  }
  const IDLE = function () { return nav.mode === 'walk' ? 'Segure um objeto para movê-lo. Arraste a tela para olhar em volta.' : 'Segure um objeto para movê-lo. Arraste a tela para girar a maquete.'; };
  function select(id) {
    selId = id && insts.has(id) ? id : null;
    $('sel').classList.toggle('empty', !selId);
    if (selId) {
      const i = insts.get(selId), wm = i.def.mount === 'wall'; $('selName').textContent = i.def.name;
      $('rotL').hidden = wm; $('rotR').hidden = wm; $('optBtn').hidden = wide();
    } else $('selName').textContent = IDLE();
    updateQuick(); syncSel(); renderPanel(); E.touch();
  }
  let press = null, drag = null, pinch = null, lastTap = { t: 0, x: 0, y: 0 };
  const ptrs = new Map();
  function showMark(i, c) {
    if (!c) { E.overlay.remove(mark); $('tip').hidden = true; return; }
    E.overlay.add(mark);
    const msp = i.def.mount === 'wall' && spanOf(i), mcx = msp ? (msp[0] + msp[1]) / 2 : 0;
    if (i.def.mount === 'wall') { mark.position.set(c.x + Math.cos(c.rot) * mcx, c.y, c.z - Math.sin(c.rot) * mcx); mark.rotation.set(PI / 2, 0, 0); mark.rotation.order = 'YXZ'; mark.rotation.set(PI / 2, c.rot, 0); mark.scale.set((msp ? msp[1] - msp[0] : i.size[0]) + 0.03, 1, i.size[1] + 0.03); }
    else { mark.rotation.set(0, i.rec.rot, 0); mark.position.set(c.x, c.y + 0.004, c.z); mark.scale.set(i.size[0] + 0.02, 1, i.size[2] + 0.02); }
    const tip = $('tip'), p = _v.set(c.x, c.y + (i.def.mount === 'wall' ? i.size[1] / 2 : i.size[1]) + 0.08, c.z).project(E.camera), r = canvas.getBoundingClientRect();
    tip.textContent = c.label || ''; tip.hidden = !c.label; tip.style.left = Q.clamp((p.x * 0.5 + 0.5) * r.width, 50, r.width - 50) + 'px'; tip.style.top = Q.clamp((-p.y * 0.5 + 0.5) * r.height, 70, r.height - 20) + 'px';
  }
  function beginDrag() {
    const i = insts.get(press.hit); if (!i) return;
    pushUndo(); press.drag = true;
    if (selId !== press.hit) select(press.hit);
    drag = { id: press.hit, ids: press.excl, last: null };
    canvas.style.cursor = 'grabbing';
  }
  function dragTo(ev) {
    const i = insts.get(drag.id); if (!i) return;
    setRay(ev);
    const c = i.def.mount === 'wall' ? placeWall(i, ray.ray, press.woff) : placeSurface(i, ray.ray, press.off, press.excl);
    if (c) { moveTo(i, c); drag.last = c; showMark(i, c); }
  }
  function endDrag() { drag = null; showMark(null); canvas.style.cursor = ''; settle = performance.now(); needEnv = true; }
  stage.addEventListener('pointerdown', function (ev) {
    if (ev.target !== canvas) return;
    ptrs.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
    if (ptrs.size === 2) {
      if (press) { clearTimeout(press.timer); if (press.drag) endDrag(); press = null; }
      const a = Array.from(ptrs.values()); pinch = { d: Math.hypot(a[0].x - a[1].x, a[0].y - a[1].y) || 1, zoom: E.zoom };
      E.controls.enabled = nav.mode === 'orbit'; return;
    }
    if (ptrs.size > 2 || ev.button > 1) return;
    nav.glide = null; setRay(ev);
    const hit = ev.button === 0 ? pick() : null;
    press = { x: ev.clientX, y: ev.clientY, ts: ev.timeStamp, hit: hit, pid: ev.pointerId, arm: false, drag: false, moved: false, touch: ev.pointerType !== 'mouse', timer: 0, byTimer: false, prevSel: selId };
    if (hit) {
      const i = insts.get(hit), r = ray.ray, rec = i.rec; let ox = 0, oz = 0;
      if (i.def.mount !== 'wall' && r.direction.y < -0.002) {
        const tt = (rec.y - r.origin.y) / r.direction.y;
        if (tt > 0) { ox = rec.x - (r.origin.x + r.direction.x * tt); oz = rec.z - (r.origin.z + r.direction.z * tt); const m = Math.hypot(ox, oz), lim = Math.max(i.size[0], i.size[2]) * 0.6 + 0.05; if (m > lim) { ox *= lim / m; oz *= lim / m; } }
      }
      press.off = { x: ox, z: oz }; press.excl = dependents(hit); press.excl.add(hit);
      const wl0 = i.def.mount === 'wall' && wallByName(rec.wall);   // parede: guarda onde o dedo pegou, para o objeto não pular
      if (wl0) { _o.copy(r.origin).applyMatrix4(wl0.inv); _d.copy(r.direction).transformDirection(wl0.inv); if (_d.z < -0.002) { const tw = -_o.z / _d.z; press.woff = { s: rec.s - (_o.x + _d.x * tw), y: rec.wy - (_o.y + _d.y * tw) }; } }
      if (!press.touch || hit === selId) { press.arm = true; E.controls.enabled = false; }
      else press.timer = setTimeout(function () {   // toque longo: pega o objeto
        if (!press || press.moved || press.hit !== hit) return;
        press.arm = true; press.byTimer = true; E.controls.enabled = false; select(hit);
        try { if (navigator.vibrate) navigator.vibrate(12); } catch (e) { /* sem vibração */ }
      }, 240);
    }
    try { canvas.setPointerCapture(ev.pointerId); } catch (e) { /* ok */ }
  }, true);
  stage.addEventListener('pointermove', function (ev) {
    const p = ptrs.get(ev.pointerId); if (!p) return;
    const px = p.x, py = p.y; p.x = ev.clientX; p.y = ev.clientY;
    if (pinch && ptrs.size >= 2) {
      if (nav.mode === 'walk') { const a = Array.from(ptrs.values()); setZoom(pinch.zoom * Math.hypot(a[0].x - a[1].x, a[0].y - a[1].y) / pinch.d); }
      return;
    }
    if (!press || ev.pointerId !== press.pid) return;
    const dx = ev.clientX - press.x, dy = ev.clientY - press.y;
    if (!press.moved && dx * dx + dy * dy > (press.touch ? 70 : 20)) {
      press.moved = true;
      if (press.arm && press.byTimer && ev.timeStamp - press.ts < 215) { press.arm = false; E.controls.enabled = nav.mode === 'orbit'; select(press.prevSel); }   // era um deslize rápido
      if (press.arm) beginDrag(); else clearTimeout(press.timer);
    }
    if (press.drag) { dragTo(ev); return; }
    if (press.moved && nav.mode === 'walk') look(ev.clientX - px, ev.clientY - py);
  }, true);
  const release = function (ev) {
    ptrs.delete(ev.pointerId); if (ptrs.size < 2) pinch = null;
    if (!press || ev.pointerId !== press.pid) return;
    clearTimeout(press.timer); const p = press; press = null; E.controls.enabled = nav.mode === 'orbit';
    if (p.drag) { endDrag(); return; }
    if (p.moved) return;
    if (p.hit) { select(p.hit); return; }
    if (spot.parent && spot.visible) { setRay(ev); if (ray.intersectObject(spot.userData.pick, false).length) { addWallTv(); return; } }
    const now = performance.now();
    if (nav.mode === 'walk' && now - lastTap.t < 340 && Math.hypot(ev.clientX - lastTap.x, ev.clientY - lastTap.y) < 34) { walkToPointer(ev); lastTap.t = 0; }
    else { lastTap = { t: now, x: ev.clientX, y: ev.clientY }; if (selId) select(null); }
  };
  stage.addEventListener('pointerup', release, true); stage.addEventListener('pointercancel', release, true);
  canvas.addEventListener('contextmenu', function (ev) { ev.preventDefault(); });
  canvas.addEventListener('wheel', function (ev) {
    if (nav.mode !== 'walk') return; ev.preventDefault();
    if (ev.ctrlKey) { setZoom(E.zoom * Math.exp(-ev.deltaY * 0.004)); return; }
    const k = -Q.clamp(ev.deltaY, -120, 120) * 0.0035, c = Math.cos(nav.yaw), s = Math.sin(nav.yaw);
    stepTo(nav.x - s * k, nav.z - c * k);
  }, { passive: false });

  function rotateSel(dir, abs) {
    const i = insts.get(selId); if (!i || i.def.mount === 'wall') return;
    pushUndo(); const rec = i.rec, old = rec.rot;
    rec.rot = abs != null ? abs : Math.round((old + dir * PI / 12) / (PI / 12)) * (PI / 12);
    const c = tryMove(i, rec.x, rec.z);
    if (c) moveTo(i, c); else { rec.rot = old; toast('Sem espaço para girar aqui'); }
    needEnv = true; save();
  }
  function nudge(dx, dy) {   // 1 cm por toque, na direção da tela
    const i = insts.get(selId); if (!i) return; pushUndo();
    const rec = i.rec, st = 0.01;
    if (i.def.mount === 'wall') {
      const wl = wallByName(rec.wall); if (!wl) return;
      E.camera.getWorldDirection(_d); const sx = (-_d.z * wl.m.elements[0] + _d.x * wl.m.elements[2]) >= 0 ? 1 : -1;
      const c = wallAt(wl, rec.s + dx * st * sx, rec.wy + dy * st, i.size[0] / 2, i.size[1] / 2, spanOf(i)); if (c) moveTo(i, c);
    } else {
      E.camera.getWorldDirection(_d); let fx = _d.x, fz = _d.z; if (Math.abs(fx) > Math.abs(fz)) { fx = Math.sign(fx); fz = 0; } else { fz = Math.sign(fz) || -1; fx = 0; }
      const c = tryMove(i, rec.x + (-fz * dx + fx * dy) * st, rec.z + (fx * dx + fz * dy) * st);
      if (c) moveTo(i, c); else toast('Encostou em algo');
    }
    needEnv = true; save();
  }
  function deleteSel() {
    const i = insts.get(selId); if (!i) return;
    pushUndo(); const id = selId;
    insts.forEach(function (k) {
      if (k.rec.on !== id) return;
      const e = ext(k, k.rec.rot), r = resolveFloor(k.rec.x, k.rec.z, e[0], e[1], k.size[1], k.def.flat) || { x: room.LB / 2, z: room.LA / 2 };
      moveTo(k, { x: r.x, y: 0, z: r.z, on: null });
    });
    if (i.rec.type === 'tv_braco') state.opts.tvSpot = { wall: i.rec.wall, s: i.rec.s, y: i.rec.wy };
    despawn(id); state.objects = state.objects.filter(function (r) { return r.id !== id; }); syncLines();
    select(null); E.touch(true, 2); save();
    if (i.rec.type === 'tv_braco') toast('TV removida. Toque em "+ TV" na parede para recolocar.');
  }
  function duplicateSel() {
    const i = insts.get(selId); if (!i) return;
    pushUndo(); const rec = JSON.parse(JSON.stringify(i.rec)); rec.id = 'o' + state.seq++;
    state.objects.push(rec); const k = spawn(rec);
    if (i.def.mount === 'wall') { const wl = wallByName(rec.wall), c = wl && wallAt(wl, rec.s + i.size[0] + 0.05, rec.wy, i.size[0] / 2, i.size[1] / 2, spanOf(i)); if (c) moveTo(k, c); }
    else { const st = Math.max(i.size[0], 0.1) + 0.03, c = tryMove(k, rec.x + st * Math.cos(rec.rot), rec.z - st * Math.sin(rec.rot)) || tryMove(k, rec.x - st * Math.cos(rec.rot), rec.z + st * Math.sin(rec.rot)) || tryMove(k, rec.x + 0.3, rec.z + 0.3); if (c) moveTo(k, c); }
    snapTo(k); syncLines(); select(rec.id); E.touch(true, 2); save();
  }
  function addObject(type) {
    if (type === 'tv_braco') { addWallTv(); if (!wide()) app.classList.add('nopanel'); return; }
    const d = Q.catalog[type]; pushUndo();
    const rec = { id: 'o' + state.seq++, type: type, x: 0, y: 0, z: 0, rot: 0, p: {}, on: null }, sz = d.size;
    // nasce à frente da câmera, no piso; itens de parede vão para a parede da porta
    E.camera.getWorldDirection(_d); const fx = nav.mode === 'walk' ? nav.x + _d.x * 1.1 : room.LB * 0.5, fz = nav.mode === 'walk' ? nav.z + _d.z * 1.1 : room.LA * 0.45;
    if (d.mount === 'wall') { const wl = wallByName('porta'); putWall(rec, 'porta', (wl.s0 + wl.s1) / 2, Math.min(1.55, wl.y1 - sz[1] / 2)); }
    else { const e = Math.max(sz[0], sz[2]) / 2, r = resolveFloor(fx, fz, e, e, sz[1], d.flat, new Set()) || resolveFloor(room.LB / 2, room.LA / 2, e, e, sz[1], d.flat) || { x: room.LB / 2, z: room.LA / 2 }; rec.x = r.x; rec.z = r.z; rec.rot = Math.round(Math.atan2(-_d.x, -_d.z) / (PI / 2)) * (PI / 2); }
    state.objects.push(rec); spawn(rec); syncLines(); select(rec.id); toast(d.name + ' no quarto. Segure e arraste para posicionar.');
    if (!wide()) app.classList.add('nopanel');
    E.touch(true, 2); save();
  }
  function setParam(key, val, noUndo) {
    const i = insts.get(selId); if (!i) return;
    if (!noUndo) pushUndo();
    i.rec.p = i.rec.p || {}; i.rec.p[key] = val;
    const rec = i.rec; despawn(rec.id); spawn(rec); syncLines(); syncSel(); E.touch(true, 2); save();
  }

  /* ---------- navegação: passeio (primeira pessoa) e maquete (órbita) ---------- */
  const nav = { mode: 'walk', x: 1, z: 1, yaw: 0, pitch: 0, cy: 0, cp: 0, cx: 1, cz: 1, eye: 1.55, ce: 1.55, glide: null, anim: null };
  const joy = { x: 0, y: 0, pid: null }, keys = {};
  function setZoom(z) { E.zoom = Q.clamp(z, 1, 3.2); E.refitFov(); }
  function look(dx, dy) {
    const k = ((E.camera.fov * PI) / 180) / Math.max(200, canvas.clientHeight) * 1.05;
    nav.yaw += dx * k; nav.pitch = Q.clamp(nav.pitch + dy * k, -1.25, 1.25);
  }
  function stepTo(x, z) { const r = resolveFloor(x, z, 0.2, 0.2, 1.7) ; if (r) { nav.x = r.x; nav.z = r.z; return true; } return false; }
  function walkToPointer(ev) {
    setRay(ev); const r = ray.ray; if (r.direction.y > -0.03) return;
    const tt = -r.origin.y / r.direction.y, c = resolveFloor(r.origin.x + r.direction.x * tt, r.origin.z + r.direction.z * tt, 0.2, 0.2, 1.7);
    if (c) nav.glide = { x: c.x, z: c.z };
  }
  function views() {
    const r = room, W = r.W, D = r.Dp, dz = r.zA + (r.uT + r.uD) / 2;
    return {
      entrada: { p: [r.LB - 0.3, r.zA * 0.5], t: [r.nicheC + 0.1, 0.95, D - 0.3] },
      bancada: { p: [Math.max(0.5, r.LB - 1.7), dz + 0.75], t: [W - 0.2, 1.05, dz - 0.15] },
      cama: { p: [r.nicheC + 0.8, Math.max(0.5, D - 3.0)], t: [r.nicheC, 0.7, D - 0.5] },
      janela: { p: [r.LB - 0.35, r.LA - 0.35], t: [0, 1.3, (r.win.z0 + r.win.z1) / 2] },
      tv: { p: [Math.min(r.LB - 0.35, r.dx0 * 0.5 + 0.45), Math.min(r.LA - 0.3, 2.55)], t: [r.dx0 * 0.5 + 0.05, 1.0, 0] },
      deitado: { p: [r.nicheC, D - 0.6], t: [0.6, 1.4, D - 1.75], eye: 0.84 }
    };
  }
  function goView(n, instant) {
    if (n === 'geral' || n === 'planta') { setMode('orbit', n, instant); return; }
    const v = views()[n]; if (!v) return;
    if (nav.mode !== 'walk') setMode('walk', null, true);
    if (n === 'deitado') {   // deitado: abre o braço da TV para a cama e olha para a tela
      let tvI = null; insts.forEach(function (i) { if (!tvI && i.pose) tvI = i; });
      if (tvI) { const q = aimBed(tvI); if (poseOf(tvI.rec).ext < 0.3) { pushUndo(); setPose(tvI, q); save(); } tvI.group.updateMatrixWorld(true); const w = tvI.group.localToWorld(V3(q.swivel < 0 ? -0.05 : 0.05, -0.04, 0.6)); v.t = [w.x, w.y, w.z]; }
    }
    nav.eye = v.eye || state.opts.eye;
    const eye = nav.eye, c = resolveFloor(v.p[0], v.p[1], 0.2, 0.2, 1.7) || { x: v.p[0], z: v.p[1] };
    const dx = v.t[0] - c.x, dy = v.t[1] - eye, dzz = v.t[2] - c.z, to = { x: c.x, z: c.z, yaw: Math.atan2(-dx, -dzz), pitch: Math.atan2(dy, Math.hypot(dx, dzz)) };
    setZoom(1); nav.glide = null;
    if (instant) { nav.x = nav.cx = to.x; nav.z = nav.cz = to.z; nav.yaw = nav.cy = to.yaw; nav.pitch = nav.cp = to.pitch; nav.anim = null; E.touch(); return; }
    let dyaw = to.yaw - nav.yaw; dyaw = Math.atan2(Math.sin(dyaw), Math.cos(dyaw));
    nav.anim = { t0: performance.now(), a: { x: nav.x, z: nav.z, yaw: nav.yaw, pitch: nav.pitch }, b: { x: to.x, z: to.z, yaw: nav.yaw + dyaw, pitch: to.pitch } };
  }
  function orbitView(n) {
    const r = room, a = E.camera.aspect, vf = (E.camera.fov * PI) / 360, hf = Math.atan(Math.tan(vf) * a);
    const f = (0.84 * 0.5 * Math.hypot(r.W, r.Dp, r.H)) / Math.sin(Math.min(vf, hf)) / 4.2, c = V3(r.LB * 0.56, 0.95, r.LA * 0.54);
    return n === 'planta' ? { t: V3(r.W / 2, 0, r.Dp / 2), p: V3(r.W / 2, 4.6 * f, r.Dp / 2 + 0.03) } : { t: c, p: V3(c.x - 3.25 * f, c.y + 2.2 * f, c.z - 0.55 * f) };
  }
  function setMode(m, view, instant) {
    const was = nav.mode; nav.mode = m; nav.anim = null; nav.glide = null;
    E.orbit = m === 'orbit'; E.walk = m === 'walk'; E.controls.enabled = E.orbit; E.zoom = 1; E.refitFov();
    $('joy').hidden = m !== 'walk';
    document.querySelectorAll('#modes button').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.mode === m)); });
    if (m === 'orbit') {
      const v = orbitView(view || 'geral');
      if (instant || was !== 'orbit') { E.camera.position.copy(v.p); E.controls.target.copy(v.t); E.controls.update(); }
      else nav.anim = { t0: performance.now(), orbit: true, p0: E.camera.position.clone(), q0: E.controls.target.clone(), p1: v.p, q1: v.t };
    } else if (was !== 'walk') goView(view || 'entrada', true);
    if (!selId) $('selName').textContent = IDLE();
    E.touch();
  }
  let lastT = 0, settle = 0, needEnv = false;
  function frame() {
    const now = performance.now(), dt = Math.min(0.1, (now - lastT) / 1000 || 0.016); lastT = now;
    const cam = E.camera;
    if (nav.anim) {
      const a = nav.anim, k = Math.min(1, (now - a.t0) / 750), e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      if (a.orbit) { cam.position.lerpVectors(a.p0, a.p1, e); E.controls.target.lerpVectors(a.q0, a.q1, e); cam.lookAt(E.controls.target); }
      else { nav.x = a.a.x + (a.b.x - a.a.x) * e; nav.z = a.a.z + (a.b.z - a.a.z) * e; nav.yaw = a.a.yaw + (a.b.yaw - a.a.yaw) * e; nav.pitch = a.a.pitch + (a.b.pitch - a.a.pitch) * e; }
      E.dirty = true; if (k >= 1) nav.anim = null;
    }
    if (nav.mode === 'walk') {
      let mx = joy.x + (keys.d || keys.arrowright ? 1 : 0) - (keys.a || keys.arrowleft ? 1 : 0), mz = joy.y + (keys.s || keys.arrowdown ? 1 : 0) - (keys.w || keys.arrowup ? 1 : 0);
      const ml = Math.hypot(mx, mz);
      if (ml > 0.05) {
        if (ml > 1) { mx /= ml; mz /= ml; }
        const sp = 1.5 * dt, c = Math.cos(nav.yaw), s = Math.sin(nav.yaw), nx = nav.x + (c * mx + s * mz) * sp, nz = nav.z + (-s * mx + c * mz) * sp;
        nav.glide = null; if (nav.eye < 1.2) nav.eye = state.opts.eye; if (!stepTo(nx, nz)) { if (!stepTo(nx, nav.z)) stepTo(nav.x, nz); }
      }
      if (nav.glide) { const gx = nav.glide.x - nav.x, gz = nav.glide.z - nav.z, gl = Math.hypot(gx, gz), st = 2.2 * dt; if (gl < st) { nav.x = nav.glide.x; nav.z = nav.glide.z; nav.glide = null; } else { nav.x += gx / gl * st; nav.z += gz / gl * st; } }
      const sm = nav.anim ? 1 : 1 - Math.exp(-dt * 26), ex = nav.x - nav.cx, ez = nav.z - nav.cz, ey = nav.yaw - nav.cy, ep = nav.pitch - nav.cp;
      if (Math.abs(ex) + Math.abs(ez) + Math.abs(ey) + Math.abs(ep) > 0.0004) { nav.cx += ex * sm; nav.cz += ez * sm; nav.cy += ey * sm; nav.cp += ep * sm; E.dirty = true; }
      else if (ex || ez || ey || ep) { nav.cx = nav.x; nav.cz = nav.z; nav.cy = nav.yaw; nav.cp = nav.pitch; E.dirty = true; }
      const de = nav.eye - nav.ce; if (Math.abs(de) > 0.0008) { nav.ce += de * (1 - Math.exp(-dt * 7)); E.dirty = true; } else nav.ce = nav.eye;
      cam.position.set(nav.cx, nav.ce, nav.cz); cam.rotation.order = 'YXZ'; cam.rotation.set(nav.cp, nav.cy, 0);
    }
    // movimento suave dos objetos (e leve "levantada" enquanto arrasta)
    let moving = false, lines = false;
    insts.forEach(function (i) {
      const r = i.rec, g = i.group, lift = drag && drag.ids.has(r.id) && i.def.mount !== 'wall' ? 0.022 : 0;
      const dx = r.x - g.position.x, dy = r.y + lift - g.position.y, dz = r.z - g.position.z; let dr = r.rot - g.rotation.y; dr = Math.atan2(Math.sin(dr), Math.cos(dr));
      const m = Math.abs(dx) + Math.abs(dy) + Math.abs(dz);
      if (m < 1e-6 && Math.abs(dr) < 1e-5) return;
      if (m < 0.0012 && Math.abs(dr) < 0.004) { g.position.set(r.x, r.y + lift, r.z); g.rotation.y = r.rot; }
      else { const k = 1 - Math.exp(-dt * 24); g.position.x += dx * k; g.position.y += dy * k; g.position.z += dz * k; g.rotation.y += dr * k; }
      moving = true; if (g.userData.lines) lines = true;
    });
    insts.forEach(function (i) {
      if (!i.pose) return; const tg = poseOf(i.rec); let ch = false;
      POSE.forEach(function (k) {
        const d = tg[k] - i.pose[k]; if (Math.abs(d) < 1e-4) return;
        const st = Math.max(Math.abs(d) * (1 - Math.exp(-dt * 5)), (k === 'ext' || k === 'side' ? 0.3 : 26) * dt);
        i.pose[k] += Math.abs(d) <= st ? d : Math.sign(d) * st; ch = true;
      });
      if (ch) { i.group.userData.pose(i.pose); moving = true; }
    });
    if (moving) { if (lines) syncLines(); syncSel(); E.touch(true, 0); settle = now; needEnv = true; }
    else if (needEnv && !drag && now - settle > 140) { needEnv = false; E.touch(true, 2); save(); }
  }
  function cull(cp) {
    const inC = !cp || cp.x > 0.02;   // na maquete, esconde janela e ar-condicionado quando a câmera está atrás da parede lilás
    ['alu', 'glassW', 'marble', 'acBody', 'acLouver', 'wallCr', 'woodAC', 'rodC', 'darkC'].forEach(function (k) { if (room.meshes[k]) room.meshes[k].visible = inC; });
    if (spot.parent) spot.visible = !cp || (cp.x - spot.position.x) * Math.sin(spot.rotation.y) + (cp.z - spot.position.z) * Math.cos(spot.rotation.y) > 0;
    insts.forEach(function (i) {
      if (i.def.mount !== 'wall') return;
      const r = i.rec; i.group.visible = !cp || !!i.pose || (cp.x - r.x) * Math.sin(r.rot) + (cp.z - r.z) * Math.cos(r.rot) > 0;
    });
  }
  (function () {   // joystick
    const el = $('joy'), knob = el.firstElementChild;
    const set = function (ev) { const r = el.getBoundingClientRect(); let x = (ev.clientX - r.left - r.width / 2) / 30, y = (ev.clientY - r.top - r.height / 2) / 30; const l = Math.hypot(x, y); if (l > 1) { x /= l; y /= l; } joy.x = x; joy.y = y; knob.style.transform = 'translate(' + x * 27 + 'px,' + y * 27 + 'px)'; };
    el.addEventListener('pointerdown', function (ev) { joy.pid = ev.pointerId; try { el.setPointerCapture(ev.pointerId); } catch (e) { /* ok */ } set(ev); ev.preventDefault(); });
    el.addEventListener('pointermove', function (ev) { if (ev.pointerId === joy.pid) set(ev); });
    const end = function (ev) { if (ev.pointerId !== joy.pid) return; joy.pid = null; joy.x = joy.y = 0; knob.style.transform = ''; };
    el.addEventListener('pointerup', end); el.addEventListener('pointercancel', end);
  })();

  /* ---------- interface ---------- */
  function h(tag, a) {
    const el = document.createElement(tag);
    if (a) for (const k in a) {
      const v = a[k];
      if (k === 'text') el.textContent = v; else if (k === 'on') { for (const e in v) el.addEventListener(e, v[e]); }
      else if (k === 'style') el.style.cssText = v; else if (v !== false && v != null) el.setAttribute(k, v === true ? '' : v);
    }
    for (let n = 2; n < arguments.length; n++) { const c = arguments[n]; if (Array.isArray(c)) c.forEach(function (x) { if (x) el.append(x); }); else if (c) el.append(c); }
    return el;
  }
  let toastT = 0;
  function toast(msg) { const t = $('toast'); t.textContent = msg; t.classList.add('on'); clearTimeout(toastT); toastT = setTimeout(function () { t.classList.remove('on'); }, 2600); }
  function sw(id, on, label, fn) {
    return h('button', { type: 'button', class: 'sw', id: id, role: 'switch', 'aria-checked': on ? 'true' : 'false', 'aria-label': label, on: { click: function () { fn(this.getAttribute('aria-checked') !== 'true'); } } });
  }
  function swatches(id, pal, cur, fn) {
    const box = h('div', { class: 'sws', id: id }); let armed = false;
    pal.forEach(function (c) {
      box.append(h('button', { type: 'button', class: 'swatch' + (c[1] === 'wood' ? ' wood' : ''), title: c[0], 'aria-label': c[0], 'aria-pressed': String(c[1].toLowerCase() === String(cur).toLowerCase()), style: c[1] === 'wood' ? '' : 'background:' + c[1], on: { click: function () { fn(c[1], false); } } }));
    });
    const inp = h('input', { type: 'color', id: id + '-c', value: /^#[0-9a-f]{6}$/i.test(cur) ? cur : '#8899ff', 'aria-label': 'Outra cor', on: { input: function () { fn(this.value, armed); armed = true; }, change: function () { armed = false; } } });
    box.append(h('span', { class: 'pick', title: 'Outra cor' }, inp));
    return box;
  }
  function range(id, label, min, max, step, val, fn, fmt) {
    let armed = false;
    const out = fmt ? h('output', { text: fmt(val) }) : null;
    const inp = h('input', { type: 'range', id: id, min: min, max: max, step: step, value: val, 'aria-label': label, on: {
      input: function () { if (!armed) { pushUndo(); armed = true; } if (out) out.textContent = fmt(+this.value); fn(+this.value, false); },
      change: function () { armed = false; fn(+this.value, true); save(); } } });
    return h('label', { class: 'rng' + (fmt ? ' val' : '') }, h('span', { text: label }), inp, out);
  }
  function chips(list, cur, fn, cls) {
    return h('div', { class: 'chips' }, list.map(function (c) { return h('button', { type: 'button', class: 'chip' + (cls ? ' ' + cls : ''), 'aria-pressed': String(c[1] === cur), text: c[0], on: { click: function () { fn(c[1]); } } }); }));
  }
  const head = function (title, ctl) { return h('div', { class: 'head' }, h('h3', { text: title }), ctl); };
  const pal = function (key, type) { return key === 'frame' ? FRAMES : key === 'ledColor' || (LIGHT_KEYS[type] && key === 'color' && type !== 'tv') ? LEDS : SOFT; };
  const ARW = { l: 'M15 6l-6 6 6 6', r: 'M9 6l6 6-6 6', u: 'M6 15l6-6 6 6', d: 'M6 9l6 6 6-6' };
  const arrow = function (k, label, dx, dy) { const b = h('button', { type: 'button', class: 'act', title: label, 'aria-label': label, on: { click: function () { nudge(dx, dy); } } }); b.innerHTML = '<svg viewBox="0 0 24 24"><path d="' + ARW[k] + '"/></svg>'; return b; };

  /* opções do objeto selecionado (no topo do painel) */
  function selGroup() {
    const i = insts.get(selId); if (!i) return null;
    const p = paramsOf(i.rec), ctl = i.def.controls || {}, wm = i.def.mount === 'wall';
    const g = h('div', { class: 'grp objsel' }, h('div', { class: 'head' }, h('h3', { text: i.def.name })));
    Object.keys(ctl).forEach(function (key) {
      if (key === 'pose') {
        const q = poseOf(i.rec), open = q.ext > 0.3, cur = function () { return insts.get(selId); };
        g.append(h('p', { class: 'lab', text: ctl[key] }), h('div', { class: 'chips' },
          h('button', { type: 'button', class: 'chip', 'aria-pressed': String(!open), text: 'Recolhida', on: { click: function () { pushUndo(); setPose(cur(), CLOSED); renderPanel(); save(); } } }),
          h('button', { type: 'button', class: 'chip', 'aria-pressed': String(open), text: 'Virada para a cama', on: { click: function () { pushUndo(); setPose(cur(), aimBed(cur())); renderPanel(); save(); } } })),
          range('sp-ext', 'Afastar', 0, 100, 1, Math.round(q.ext * 100), function (v) { setPose(cur(), { ext: v / 100 }, true); }, function (v) { return v + '%'; }),
          range('sp-side', 'Deslocar', -100, 100, 1, Math.round(q.side * 100), function (v) { setPose(cur(), { side: v / 100 }, true); }, function (v) { return v + '%'; }),
          range('sp-sw', 'Girar', -90, 90, 1, Math.round(q.swivel), function (v) { setPose(cur(), { swivel: v }, true); }, function (v) { return v + '°'; }),
          range('sp-ti', 'Inclinar', -5, 20, 1, Math.round(q.tilt), function (v) { setPose(cur(), { tilt: v }, true); }, function (v) { return v + '°'; }));
        return;
      }
      if (i.pose && (key === 'text' || key === 'color' || key === 'accent')) return;
      if (key === 'color' || key === 'accent' || key === 'frame' || key === 'ledColor') { if (key === 'ledColor' && !p.led) return; g.append(h('p', { class: 'lab', text: ctl[key] }), swatches('sc-' + key, pal(key, i.rec.type), p[key], function (v, live) { setParam(key, v, live); if (!live) renderPanel(); })); }
      else if (key === 'film') {
        g.append(h('div', { class: 'line' }, h('span', { class: 'lab', text: ctl[key] }), sw('sc-film', p.film, ctl[key], function (v) { setParam('film', v); renderPanel(); })));
        if (p.film && p.on) {
          const hv = Q.film.hasVideo();
          g.append(h('div', { class: 'chips' },
            h('button', { type: 'button', class: 'chip', text: hv ? 'Trocar o vídeo' : 'Usar um vídeo do meu aparelho', on: { click: function () { $('vidFile').click(); } } }),
            hv ? h('button', { type: 'button', class: 'chip', text: 'Voltar à animação', on: { click: function () { Q.film.clearVideo(); renderPanel(); E.touch(); } } }) : null));
          if (hv) g.append(h('div', { class: 'line' }, h('span', { class: 'lab', text: 'Som do vídeo' }), sw('sc-som', Q.film.sound(), 'Som do vídeo', function (v) { Q.film.sound(v); renderPanel(); })));
          else g.append(h('p', { class: 'lab', text: 'A animação é original. Um vídeo seu toca só neste aparelho e não vai junto com o link.' }));
        }
      }
      else if (key === 'on' || key === 'head' || key === 'led' || key === 'wide') g.append(h('div', { class: 'line' }, h('span', { class: 'lab', text: ctl[key] }), sw('sc-' + key, p[key], ctl[key], function (v) { setParam(key, v); renderPanel(); })));
      else if (key === 'shape') g.append(h('div', { class: 'chips' }, h('button', { type: 'button', class: 'chip', text: ctl[key], on: { click: function () { const l = Q.neonShapes; setParam('shape', l[(l.indexOf(p.shape) + 1) % l.length]); renderPanel(); } } })));
      else if (key === 'style') g.append(h('div', { class: 'chips' }, h('button', { type: 'button', class: 'chip', text: ctl[key], on: { click: function () { setParam('style', (p.style % 4) + 1); renderPanel(); } } })));
      else if (key === 'lado') g.append(h('p', { class: 'lab', text: ctl[key] }), chips([['À esquerda da placa', -1], ['À direita da placa', 1]], p.lado > 0 ? 1 : -1, function (v) {
        setParam('lado', v); const k = insts.get(selId), wl = k && wallByName(k.rec.wall), c = wl && wallAt(wl, k.rec.s, k.rec.wy, k.size[0] / 2, k.size[1] / 2, spanOf(k)); if (c) { moveTo(k, c); snapTo(k); } renderPanel(); save();
      }));
      else if (key === 'pol') g.append(h('p', { class: 'lab', text: ctl[key] }), chips([['32"', 32], ['40"', 40], ['43"', 43], ['50"', 50]], p.pol, function (v) { setParam('pol', v); renderPanel(); }));
      else if (key === 'w') g.append(h('p', { class: 'lab', text: ctl[key] }), chips([['80 cm', 0.8], ['1,00 m', 1], ['1,20 m', 1.2], ['1,40 m', 1.4]], p.w, function (v) { setParam('w', v); renderPanel(); }));
      else if (key === 'text' && (i.rec.type !== 'neon' || p.shape === 'texto')) g.append(h('p', { class: 'lab', text: ctl[key] }), h('input', { type: 'text', class: 'txt', id: 'sc-text', maxlength: 14, value: p.text, 'aria-label': ctl[key], on: { change: function () { setParam('text', this.value.trim()); renderPanel(); } } }));
    });
    g.append(h('p', { class: 'lab', text: 'Ajuste fino (1 cm por toque)' }), h('div', { class: 'fine' },
      h('div', { class: 'pad' }, h('span'), arrow('u', wm ? 'Subir' : 'Afastar', 0, 1), h('span'), arrow('l', 'Para a esquerda', -1, 0), arrow('d', wm ? 'Descer' : 'Aproximar', 0, -1), arrow('r', 'Para a direita', 1, 0)),
      wm ? null : h('div', { style: 'flex:1;min-width:150px' }, range('sc-rot', 'Giro', -180, 180, 5, Math.round((Math.atan2(Math.sin(i.rec.rot), Math.cos(i.rec.rot)) * 180) / PI / 5) * 5, function (v) { const k = insts.get(selId); if (!k) return; const old = k.rec.rot; k.rec.rot = (v * PI) / 180; const c = tryMove(k, k.rec.x, k.rec.z); if (c) moveTo(k, c); else k.rec.rot = old; needEnv = true; }, function (v) { return v + '°'; }))));
    return g;
  }
  function applyTheme(t) {
    pushUndo(); const p = state.paint, L = state.lights, o = state.opts;
    p.wallC = t.paredeJanela; p.wallD = t.paredePorta; p.ceil = t.teto; p.cab = t.armarios === 'madeira' ? 'wood' : t.armarios;
    L.cove.color = t.ledTeto; L.shelf.color = t.ledPrateleiras;
    o.curtain = !!t.cortina; if (t.cortina) o.curtainColor = t.cortina;
    let rug = false;
    state.objects.forEach(function (r) {
      r.p = r.p || {};
      if (r.type === 'cama') { r.p.color = t.colcha; r.p.accent = t.manta; }
      else if (r.type === 'tapete_red' || r.type === 'tapete_ret') { rug = true; if (t.tapete) r.p.color = t.tapete; }
      else if (r.type === 'estante' || r.type === 'rack') r.p.ledColor = t.ledPrateleiras;
    });
    if (t.tapete && !rug) { const e = 0.7, r = resolveFloor(room.xN + 0.75, room.LA * 0.62, e, 0.45, 0.02, true); state.objects.push({ id: 'o' + state.seq++, type: 'tapete_ret', x: r.x, y: 0, z: r.z, rot: 0, p: { color: t.tapete }, on: null }); }
    selId = null; applyPaint(); applyOpts(); respawnAll(); applyLights(); select(null); save(); toast('Estilo ' + t.nome + ' aplicado');
  }
  function paneLuzes() {
    const L = state.lights, set = function (fn) { return function (v) { pushUndo(); fn(v); applyLights(); renderPanel(); save(); }; };
    const led = function (key, title) {
      const c = L[key];
      return h('div', { class: 'grp' }, head(title, sw('l-' + key, c.on, title, set(function (v) { c.on = v; }))),
        swatches('l-' + key + '-cor', LEDS, c.color, function (v, live) { if (!live) pushUndo(); c.color = v; c.on = true; applyLights(); if (!live) renderPanel(); save(); }),
        range('l-' + key + '-lv', 'Brilho', 0.2, 2.5, 0.05, c.level, function (v) { c.level = v; applyLights(); }));
    };
    return h('div', { class: 'pane' },
      h('div', { class: 'grp' }, head('Luz do teto', sw('l-teto', L.ceiling.on, 'Luz do teto', set(function (v) { L.ceiling.on = v; }))),
        range('l-teto-lv', 'Intensidade', 0.2, 2, 0.05, L.ceiling.level, function (v) { L.ceiling.level = v; applyLights(); }),
        chips(TEMPS, L.ceiling.temp, set(function (v) { L.ceiling.temp = v; }))),
      led('cove', 'Fita LED no teto'), led('shelf', 'Fita LED nas prateleiras'),
      h('div', { class: 'grp' }, head('Luz do dia pela janela', sw('l-dia', L.day, 'Luz do dia', set(function (v) { L.day = v; }))),
        h('p', { class: 'sub', text: 'Sol entrando pela janela; desligado, a vista fica noturna.' })),
      h('div', { class: 'grp' }, range('l-exp', 'Exposição', 0.4, 2.2, 0.05, L.exposure, function (v) { L.exposure = v; E.setUserExposure(v); }),
        h('div', { class: 'chips' }, h('button', { type: 'button', class: 'chip', text: 'Usar a cor da fita do teto em todos os neons', on: { click: function () {
          pushUndo(); const c = L.cove.color; L.shelf.color = c;
          state.objects.forEach(function (r) { r.p = r.p || {}; if (LIGHT_KEYS[r.type] && r.type !== 'abajur' && r.type !== 'tv') r.p.color = c; if (r.type === 'estante' || r.type === 'rack') r.p.ledColor = c; });
          selId = null; respawnAll(); applyLights(); select(null); save(); toast('Cor aplicada em todos os neons');
        } } }))));
  }
  function panePintar() {
    const p = state.paint, o = state.opts, cab = paintTarget === 'cab', list = cab ? CABS : WALLS, cur = p[paintTarget];
    const nm = list.find(function (c) { return c[1].toLowerCase() === String(cur).toLowerCase(); });
    return h('div', { class: 'pane' },
      h('div', { class: 'grp' }, h('div', { class: 'head' }, h('h3', { text: 'Estilos prontos' })), h('p', { class: 'sub', text: 'Um toque troca paredes, armários, LEDs e roupa de cama. Dá para desfazer.' }),
        h('div', { class: 'themes' }, THEMES.map(function (t) {
          return h('button', { type: 'button', class: 'theme', title: t.descricao, on: { click: function () { applyTheme(t); } } },
            h('span', { class: 'dots' }, [t.paredeJanela, t.paredePorta, t.armarios === 'madeira' ? '#8a4a2c' : t.armarios, t.colcha, t.manta, t.ledTeto].map(function (c) { return h('i', { style: 'background:' + c }); })), h('b', { text: t.nome }));
        }))),
      h('div', { class: 'grp' }, h('div', { class: 'head' }, h('h3', { text: 'Pintar' })),
        chips([['Parede da janela', 'wallC'], ['Parede da porta', 'wallD'], ['Teto', 'ceil'], ['Armários', 'cab']], paintTarget, function (v) { paintTarget = v; renderPanel(); }),
        swatches('p-cor', list, cur, function (v, live) { if (!live) pushUndo(); p[paintTarget] = v; applyPaint(); if (!live) renderPanel(); save(); }),
        h('p', { class: 'sub pname', text: nm ? nm[0] : 'Cor personalizada ' + cur })),
      h('div', { class: 'grp' }, head('Cortina', sw('o-cortina', o.curtain, 'Cortina', function (v) { pushUndo(); o.curtain = v; applyOpts(); renderPanel(); save(); })),
        o.curtain ? swatches('o-cortina-cor', [['Voil branco', '#f4f1ea'], ['Linho', '#d9cdb8'], ['Cinza', '#9a9ca3'], ['Azul', '#3b4a7a'], ['Rosa', '#d9a6ae'], ['Grafite', '#2a2b31']], o.curtainColor, function (v, live) { if (!live) pushUndo(); o.curtainColor = v; applyOpts(); if (!live) renderPanel(); save(); }) : null),
      h('div', { class: 'grp' }, head('Porta aberta', sw('o-porta', o.door, 'Porta aberta', function (v) { pushUndo(); o.door = v; applyOpts(); renderPanel(); save(); }))));
  }
  let thumbQ = [], thumbBusy = false;
  function pumpThumbs() {
    if (thumbBusy || !thumbQ.length) return; thumbBusy = true;
    requestAnimationFrame(function step() {
      const t = thumbQ.shift();
      if (t) { try { if (!thumbs[t]) thumbs[t] = E.thumb(t); } catch (e) { thumbs[t] = ''; } const im = document.querySelector('img[data-th="' + t + '"]'); if (im && thumbs[t]) { im.src = thumbs[t]; im.hidden = false; } }
      if (thumbQ.length) requestAnimationFrame(step); else thumbBusy = false;
    });
  }
  function paneObjetos() {
    const pane = h('div', { class: 'pane' }); thumbQ = [];
    pane.append(h('p', { class: 'sub', text: 'Toque para colocar no quarto. Depois segure o objeto e arraste: ele encaixa no piso, na bancada, nas prateleiras, em cima de outros móveis ou na parede.' }));
    Q.catOrder.forEach(function (cat) {
      const grid = h('div', { class: 'cat' });
      Object.keys(Q.catalog).forEach(function (id) {
        const d = Q.catalog[id]; if (d.cat !== cat) return;
        const im = h('img', { alt: '', 'data-th': id, hidden: !thumbs[id], src: thumbs[id] || false });
        if (!thumbs[id]) thumbQ.push(id);
        grid.append(h('button', { type: 'button', class: 'item', on: { click: function () { addObject(id); } } }, h('span', { class: 'th' }, im), h('span', { text: d.name })));
      });
      pane.append(h('div', { class: 'grp' }, h('div', { class: 'head' }, h('h3', { text: cat })), grid));
    });
    setTimeout(pumpThumbs, 60);
    return pane;
  }
  let resetArmed = false;
  function paneQuarto() {
    const d = state.dims, o = state.opts, m = function (v) { return v.toFixed(2).replace('.', ',') + ' m'; };
    const dim = function (key, label, min, max) { return range('d-' + key, label, min, max, 0.01, d[key], function (v, done) { d[key] = v; if (done) relayoutRoom(); }, m); };
    return h('div', { class: 'pane' },
      h('div', { class: 'grp' }, h('div', { class: 'head' }, h('h3', { text: 'Passear pelo quarto' })),
        chips([['Da porta', 'entrada'], ['Bancada', 'bancada'], ['Cama', 'cama'], ['Janela', 'janela'], ['TV e estante', 'tv'], ['Deitado na cama', 'deitado']], null, function (v) { goView(v); if (!wide()) app.classList.add('nopanel'); }, 'ghost'),
        h('p', { class: 'sub', text: 'Ande com o controle redondo (ou teclas W A S D), arraste para olhar, pinça para aproximar e dois toques no piso para ir até lá.' }),
        range('o-eye', 'Altura do olhar', 0.9, 2.0, 0.01, o.eye, function (v) { o.eye = v; nav.eye = v; E.touch(); }, m)),
      h('div', { class: 'grp' }, h('div', { class: 'head' }, h('h3', { text: 'Maquete' })),
        chips([['Vista geral', 'geral'], ['De cima', 'planta']], null, function (v) { goView(v); if (!wide()) app.classList.add('nopanel'); }, 'ghost')),
      h('div', { class: 'grp' }, h('div', { class: 'head' }, h('h3', { text: 'Qualidade da imagem' })),
        chips([['Leve', 'leve'], ['Alta', 'alta'], ['Ultra', 'ultra']], o.quality, function (v) { o.quality = v; E.setQuality(v); renderPanel(); save(); }),
        h('p', { class: 'sub', text: 'A imagem refina sozinha quando a vista para. Use Leve se o aparelho travar.' })),
      h('div', { class: 'grp' }, h('div', { class: 'head' }, h('h3', { text: 'Medidas do quarto' })),
        h('p', { class: 'sub', text: 'Calculadas pelas lajotas de 80 cm das fotos. Se medir com a trena, ajuste aqui e os armários acompanham.' }),
        dim('W', 'Largura', 2.4, 4.4), dim('D', 'Comprimento', 2.6, 4.8), dim('H', 'Pé-direito', 2.45, 3.0)),
      h('div', { class: 'grp' }, h('div', { class: 'chips' }, h('button', { type: 'button', class: 'chip danger', id: 'reset', text: resetArmed ? 'Confirmar: apagar tudo e voltar ao original' : 'Voltar ao quarto original', on: { click: function () {
        if (!resetArmed) { resetArmed = true; renderPanel(); setTimeout(function () { if (resetArmed) { resetArmed = false; if (tab === 'quarto') renderPanel(); } }, 4000); return; }
        resetArmed = false; pushUndo(); const q = state.opts.quality; state = fresh(); state.opts.quality = q;
        selId = null; buildRoom(); state.objects = defaultObjects(); respawnAll(); select(null); goView('entrada'); save(); toast('Quarto original restaurado');
      } } }))));
  }
  function relayoutRoom() { selId = null; buildRoom(); relayout(); respawnAll(); select(null); if (nav.mode === 'walk') goView('entrada'); else setMode('orbit', 'geral', true); save(); }
  function renderPanel() {
    const sc = panel.scrollTop; panel.textContent = '';
    const pane = tab === 'luzes' ? paneLuzes() : tab === 'pintar' ? panePintar() : tab === 'objetos' ? paneObjetos() : paneQuarto(), sg = selGroup();
    if (sg) pane.prepend(sg);
    panel.append(pane); panel.scrollTop = sc;
    document.querySelectorAll('#tabs button').forEach(function (b) { b.setAttribute('aria-selected', String(b.dataset.tab === tab)); });
  }
  function syncScenes() {
    const L = state.lights, cur = L.day && !L.ceiling.on && !L.cove.on ? 'dia' : L.ceiling.on && !L.cove.on && !L.shelf.on && !L.day ? 'acesa' : !L.ceiling.on && L.cove.on && !L.day ? 'neon' : '';
    document.querySelectorAll('#scenes button').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.scene === cur)); });
  }
  function setScene(n) {
    pushUndo(); const L = state.lights;
    L.ceiling.on = n === 'acesa'; L.cove.on = L.shelf.on = n === 'neon'; L.day = n === 'dia';
    applyLights(); if (tab === 'luzes') renderPanel(); save();
  }

  /* ---------- início ---------- */
  function fail(msg) { $('loadMsg').textContent = msg; const b = document.querySelector('#load .bar'); if (b) b.hidden = true; }
  function start(data) {
    try { Q.initMaterials(); E = Q.createEngine(canvas); }
    catch (e) { fail(e && e.message === 'webgl2' ? 'Este navegador não tem WebGL 2, necessário para o 3D. Tente no Chrome ou Safari atualizados.' : 'Não foi possível iniciar o 3D neste aparelho.'); return; }
    Q.E = E; Q.nav = nav;
    dayTex = Q.makeBackdrop(true); nightTex = Q.makeBackdrop(false);
    state = (data && data.state && data.state.v === 4 && data.state) || load() || fresh();
    if (!state.opts.eye) state.opts.eye = 1.55;
    buildRoom();
    if (!state.objects) state.objects = defaultObjects();
    if (!state.opts.tvInit) { state.opts.tvInit = true; if (!state.objects.some(function (r) { return r.type === 'tv_braco'; })) {   // quem já tinha um arranjo salvo ganha a TV nova
        state.objects.push(wallTvRec()); const wj = wallByName('janela-esq');
        state.objects.forEach(function (r) { if (r.type === 'mobile' && r.wall === 'janela-esq' && r.s > wj.s1 - 0.16) putWall(r, 'janela-esq', wj.s1 - 0.036, r.wy); });   // enfeite vai para o lado da janela
      } }
    if (state.opts.tvRev !== 2) {
      state.opts.tvRev = 2; delete state.opts.tvSpot; const wj = wallByName('janela-esq');
      state.objects.forEach(function (r) { if (r.type === 'tv_braco') { r.p = r.p || {}; if (r.p.lado == null) { r.p.lado = -1; putWall(r, 'janela-esq', wj.s1 - TV_GAP, Math.min(1.5, wj.y1 - 0.32)); } } });
    }
    nav.eye = nav.ce = state.opts.eye;
    E.onFilm = function (now) { Q.film.draw(now / 1000); insts.forEach(function (i) { const l = i.group.userData.filmLight; if (l) l.color.copy(Q.film.avg); }); };
    state.objects.forEach(spawn); syncLines();
    E.onCull = cull; E.onFrame = frame;
    const prog = $('prog');
    E.onProgress = function (k) { prog.style.width = k * 100 + '%'; prog.classList.toggle('on', k > 0 && k < 1); };
    const fit = function () { E.setSize(stage.clientWidth, stage.clientHeight); };
    if (window.ResizeObserver) new ResizeObserver(fit).observe(stage); else window.addEventListener('resize', fit);
    if (!wide()) app.classList.add('nopanel');
    E.setQuality(state.opts.quality || 'alta'); fit();
    nav.mode = 'orbit'; setMode('walk', 'entrada', true);
    select(null); syncScenes(); E.start();
    const wait = function () { if (E.frames > 3) { const l = $('load'); l.style.opacity = 0; setTimeout(function () { l.hidden = true; }, 650); } else setTimeout(wait, 80); };
    wait();
  }

  document.querySelectorAll('#tabs button').forEach(function (b) {
    b.addEventListener('click', function () { if (tab === b.dataset.tab && !wide()) app.classList.toggle('nopanel'); else { tab = b.dataset.tab; app.classList.remove('nopanel'); panel.scrollTop = 0; } renderPanel(); });
  });
  document.querySelectorAll('#scenes button').forEach(function (b) { b.addEventListener('click', function () { setScene(b.dataset.scene); }); });
  document.querySelectorAll('#modes button').forEach(function (b) { b.addEventListener('click', function () { if (b.dataset.mode !== nav.mode) setMode(b.dataset.mode, null, false); }); });
  $('undo').addEventListener('click', undo);
  $('photo').addEventListener('click', function () { app.classList.add('photo'); $('back').hidden = false; });
  $('back').addEventListener('click', function () { app.classList.remove('photo'); $('back').hidden = true; });
  $('rotL').addEventListener('click', function () { rotateSel(1); }); $('rotR').addEventListener('click', function () { rotateSel(-1); });
  $('optBtn').addEventListener('click', function () { app.classList.remove('nopanel'); panel.scrollTop = 0; });
  $('quick').addEventListener('click', togglePose);
  $('quick2').addEventListener('click', function () { select(null); goView('deitado'); if (!wide()) app.classList.add('nopanel'); });
  $('vidFile').addEventListener('change', function () {
    const f = this.files && this.files[0]; this.value = ''; if (!f) return;
    toast('Abrindo o vídeo…');
    Q.film.setVideo(f, function (ok) { toast(ok ? 'Vídeo passando na TV' : 'Não foi possível abrir este vídeo aqui. Tente um arquivo MP4.'); renderPanel(); E.touch(); });
  });
  $('dup').addEventListener('click', duplicateSel); $('del').addEventListener('click', deleteSel); $('desel').addEventListener('click', function () { select(null); });
  window.addEventListener('keydown', function (ev) {
    if (/^(INPUT|TEXTAREA)$/.test(ev.target.tagName) && ev.target.type !== 'range') return;
    const k = ev.key.toLowerCase();
    if ((ev.ctrlKey || ev.metaKey) && k === 'z') { ev.preventDefault(); undo(); return; }
    if (ev.ctrlKey || ev.metaKey || ev.altKey) return;
    if (k === 'delete' || k === 'backspace') { if (selId) { ev.preventDefault(); deleteSel(); } }
    else if (k === 'escape') select(null);
    else if (k === 'r') rotateSel(ev.shiftKey ? -1 : 1);
    else if (/^(w|a|s|d|arrowup|arrowdown|arrowleft|arrowright)$/.test(k)) { if (ev.target.type === 'range') return; keys[k] = true; if (k.indexOf('arrow') === 0) ev.preventDefault(); }
  });
  window.addEventListener('keyup', function (ev) { keys[ev.key.toLowerCase()] = false; });
  window.addEventListener('blur', function () { for (const k in keys) keys[k] = false; });

  const hot = window.claude && window.claude.hot;
  if (hot && hot.snapshot) { try { hot.snapshot(function () { return { state: state }; }); } catch (e) { /* ok */ } }
  const boot = function (d) { setTimeout(function () { start(d || {}); }, 40); };
  if (hot && hot.ready) hot.ready(boot); else boot(hot && hot.data);
})();
