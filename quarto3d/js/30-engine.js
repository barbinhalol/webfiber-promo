/* Quarto 3D — motor de render: HDR, sombras suaves, reflexo no piso, oclusão, bloom e refino progressivo */
(function () {
  'use strict';
  const T = THREE, Q = window.Q;
  const VS = 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }';
  const halton = function (i, b) { let f = 1, r = 0; while (i > 0) { f /= b; r += f * (i % b); i = Math.floor(i / b); } return r; };

  Q.createEngine = function (canvas) {
    const renderer = new T.WebGLRenderer({ canvas: canvas, antialias: false, alpha: false, stencil: false, powerPreference: 'high-performance' });
    if (!renderer.capabilities.isWebGL2) throw new Error('webgl2');
    renderer.physicallyCorrectLights = true;
    renderer.outputEncoding = T.LinearEncoding; renderer.toneMapping = T.NoToneMapping;
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = T.PCFSoftShadowMap; renderer.shadowMap.autoUpdate = false;
    renderer.setClearColor(0x0b0a0f, 1);
    Q.maxAniso = Math.min(8, renderer.capabilities.getMaxAnisotropy());
    T.RectAreaLightUniformsLib.init();
    const gl = renderer.getContext();
    const rtOK = function (o) {
      const rt = new T.WebGLRenderTarget(8, 8, o); renderer.setRenderTarget(rt); renderer.clear();
      const ok = gl.checkFramebufferStatus(gl.FRAMEBUFFER) === gl.FRAMEBUFFER_COMPLETE; renderer.setRenderTarget(null); rt.dispose(); return ok;
    };
    let hdr = T.HalfFloatType, msaa = 4;
    if (!rtOK({ type: hdr, samples: 4 })) { msaa = 0; if (!rtOK({ type: hdr })) hdr = T.UnsignedByteType; }

    const scene = new T.Scene(); scene.background = new T.Color('#0b0a0f');
    const overlay = new T.Scene();
    const camera = new T.PerspectiveCamera(58, 1, 0.05, 40); camera.layers.enable(1);
    const controls = new T.OrbitControls(camera, canvas);
    controls.enableDamping = true; controls.dampingFactor = 0.14; controls.rotateSpeed = 0.75; controls.zoomSpeed = 0.9; controls.panSpeed = 0.9;
    controls.minDistance = 0.2; controls.maxDistance = 9; controls.maxPolarAngle = Math.PI * 0.63;
    controls.touches = { ONE: T.TOUCH.ROTATE, TWO: T.TOUCH.DOLLY_PAN };

    /* ---------- alvos de render ---------- */
    const mkRT = function (o) { return new T.WebGLRenderTarget(4, 4, o); };
    const sceneRT = mkRT({ type: hdr, samples: msaa });
    const gRT = mkRT({ minFilter: T.NearestFilter, magFilter: T.NearestFilter });
    gRT.depthTexture = new T.DepthTexture(4, 4); gRT.depthTexture.minFilter = gRT.depthTexture.magFilter = T.NearestFilter;
    const aoRT = mkRT({ minFilter: T.LinearFilter, magFilter: T.LinearFilter }), aoRT2 = mkRT({ minFilter: T.LinearFilter, magFilter: T.LinearFilter });
    const colorRT = mkRT({ type: hdr, depthBuffer: false });
    const ldrRT = mkRT({ depthBuffer: false });
    let accA = mkRT({ type: hdr, depthBuffer: false }), accB = mkRT({ type: hdr, depthBuffer: false });
    const reflRT = mkRT({ type: hdr, generateMipmaps: true, minFilter: T.LinearMipmapLinearFilter, magFilter: T.LinearFilter });
    const cubeRT = new T.WebGLCubeRenderTarget(128, { type: hdr, generateMipmaps: true, minFilter: T.LinearMipmapLinearFilter });
    const cubeCam = new T.CubeCamera(0.05, 30, cubeRT); cubeCam.children.forEach(function (c) { c.layers.enable(1); });
    const lumRT = mkRT({ depthBuffer: false, minFilter: T.NearestFilter, magFilter: T.NearestFilter }); lumRT.setSize(1, 1);
    const pmrem = new T.PMREMGenerator(renderer); let envRT = null;

    const bloom = new T.UnrealBloomPass(new T.Vector2(256, 256), 0.36, 0.6, 1.0);
    [bloom.renderTargetBright].concat(bloom.renderTargetsHorizontal, bloom.renderTargetsVertical).forEach(function (rt) { rt.texture.type = hdr; });

    /* ---------- passes de tela cheia ---------- */
    const SM = function (fs, u) { return new T.ShaderMaterial({ vertexShader: VS, fragmentShader: fs, uniforms: u, depthTest: false, depthWrite: false }); };
    const kernel = (function () {
      const k = [], r = Q.rng(5);
      for (let i = 0; i < 16; i++) {
        let v; do { v = new T.Vector3(r() * 2 - 1, r() * 2 - 1, r()); } while (v.lengthSq() > 1 || v.z < 0.1);
        v.normalize(); const s = i / 16; k.push(v.multiplyScalar((0.1 + 0.9 * s * s) * (0.4 + 0.6 * r())));
      }
      return k;
    })();
    const aoMat = SM([
      'uniform sampler2D tDepth; uniform sampler2D tNormal; uniform mat4 uProj; uniform mat4 uProjInv; uniform vec3 uKernel[16];',
      'uniform float uRadius; uniform float uSeed; varying vec2 vUv;',
      'vec3 vpos(vec2 uv){ float d = texture2D(tDepth, uv).x; vec4 c = uProjInv * vec4(uv*2.0-1.0, d*2.0-1.0, 1.0); return c.xyz/c.w; }',
      'float ign(vec2 p){ return fract(52.9829189*fract(dot(p, vec2(0.06711056, 0.00583715)))); }',
      'void main(){',
      '  float d = texture2D(tDepth, vUv).x; if (d > 0.99995) { gl_FragColor = vec4(1.0); return; }',
      '  vec3 P = vpos(vUv); vec3 N = normalize(texture2D(tNormal, vUv).xyz*2.0-1.0);',
      '  float a = ign(gl_FragCoord.xy + uSeed*vec2(31.7, 17.3))*6.2831853; vec3 rv = vec3(cos(a), sin(a), 0.0);',
      '  vec3 Tn = normalize(rv - N*dot(rv, N)); vec3 Bn = cross(N, Tn); mat3 TBN = mat3(Tn, Bn, N);',
      '  float rad = min(uRadius, -P.z*0.35); float occ = 0.0;',
      '  for (int i=0;i<16;i++){',
      '    vec3 sp = P + TBN*uKernel[i]*rad; vec4 o = uProj*vec4(sp,1.0); vec2 suv = o.xy/o.w*0.5+0.5;',
      '    float sz = vpos(suv).z; float rc = smoothstep(0.0, 1.0, rad/abs(P.z - sz));',
      '    occ += step(sp.z + 0.012 + 0.004*abs(P.z), sz)*rc;',
      '  }',
      '  gl_FragColor = vec4(vec3(1.0 - occ/16.0), 1.0);',
      '}'].join('\n'), { tDepth: { value: null }, tNormal: { value: null }, uProj: { value: new T.Matrix4() }, uProjInv: { value: new T.Matrix4() }, uKernel: { value: kernel }, uRadius: { value: 0.28 }, uSeed: { value: 0 } });
    const blurMat = SM([
      'uniform sampler2D tAO; uniform sampler2D tDepth; uniform vec2 uTexel; uniform float uNear; uniform float uFar; varying vec2 vUv;',
      'float lin(float d){ return uNear*uFar/(uFar - d*(uFar-uNear)); }',
      'void main(){ float dc = lin(texture2D(tDepth, vUv).x); float s = 0.0; float w = 0.0;',
      '  for (int x=-2;x<2;x++) for (int y=-2;y<2;y++){ vec2 o = (vec2(float(x),float(y))+0.5)*uTexel; float a = texture2D(tAO, vUv+o).x;',
      '    float dd = lin(texture2D(tDepth, vUv+o).x); float k = max(0.0, 1.0 - abs(dd-dc)/(0.03*dc+0.015)); s += a*k; w += k; }',
      '  gl_FragColor = vec4(vec3(s/max(w,1e-4)),1.0); }'].join('\n'), { tAO: { value: null }, tDepth: { value: null }, uTexel: { value: new T.Vector2() }, uNear: { value: 0.05 }, uFar: { value: 40 } });
    const compMat = SM([
      'uniform sampler2D tColor; uniform sampler2D tAO; uniform float uAO; varying vec2 vUv;',
      'void main(){ vec3 c = texture2D(tColor, vUv).rgb; float ao = texture2D(tAO, vUv).x; float l = dot(c, vec3(0.2126,0.7152,0.0722));',
      '  ao = pow(ao, 1.35); float k = mix(1.0, ao, uAO); gl_FragColor = vec4(c*mix(vec3(k), vec3(1.0), 0.0), 1.0); }'].join('\n'), { tColor: { value: null }, tAO: { value: null }, uAO: { value: 1 } });
    const finalMat = SM([
      'uniform sampler2D tColor; uniform float uExposure; uniform float uVig; varying vec2 vUv;',
      'vec3 fit(vec3 v){ vec3 a = v*(v+0.0245786)-0.000090537; vec3 b = v*(0.983729*v+0.4329510)+0.238081; return a/b; }',
      'vec3 aces(vec3 c){ const mat3 mi = mat3(vec3(0.59719,0.07600,0.02840), vec3(0.35458,0.90834,0.13383), vec3(0.04823,0.01566,0.83777));',
      '  const mat3 mo = mat3(vec3(1.60475,-0.10208,-0.00327), vec3(-0.53108,1.10813,-0.07276), vec3(-0.07367,-0.00605,1.07602));',
      '  c *= 1.0/0.6; c = mi*c; c = fit(c); c = mo*c; return clamp(c, 0.0, 1.0); }',
      'vec3 srgb(vec3 c){ return mix(c*12.92, 1.055*pow(max(c, vec3(0.0)), vec3(1.0/2.4)) - 0.055, step(vec3(0.0031308), c)); }',
      'void main(){ vec3 c = max(texture2D(tColor, vUv).rgb, vec3(0.0))*uExposure; c = srgb(aces(c)); vec2 q = vUv-0.5; c *= 1.0 - uVig*dot(q,q);',
      '  gl_FragColor = vec4(c, 1.0); }'].join('\n'), { tColor: { value: null }, uExposure: { value: 1 }, uVig: { value: 0.32 } });
    const accMat = SM('uniform sampler2D tPrev; uniform sampler2D tNew; uniform float uW; varying vec2 vUv; void main(){ gl_FragColor = mix(texture2D(tPrev, vUv), texture2D(tNew, vUv), uW); }',
      { tPrev: { value: null }, tNew: { value: null }, uW: { value: 1 } });
    const blitMat = SM([
      'uniform sampler2D tTex; uniform float uSeed; varying vec2 vUv;',
      'float ign(vec2 p){ return fract(52.9829189*fract(dot(p, vec2(0.06711056, 0.00583715)))); }',
      'void main(){ vec3 c = texture2D(tTex, vUv).rgb; c += (ign(gl_FragCoord.xy + uSeed) - 0.5)/255.0; gl_FragColor = vec4(c, 1.0); }'].join('\n'), { tTex: { value: null }, uSeed: { value: 0 } });
    const lumMat = SM([
      'uniform samplerCube tCube; varying vec2 vUv;',
      'void main(){ vec3 s = vec3(0.0);',
      '  for (int x=-1;x<=1;x++) for (int y=-1;y<=1;y++) for (int z=-1;z<=1;z++){ if (x==0 && y==0 && z==0) continue;',
      '    s += textureCubeLodEXT(tCube, normalize(vec3(float(x),float(y),float(z))), 4.0).rgb; }',
      '  float L = dot(s/26.0, vec3(0.2126,0.7152,0.0722)); float v = clamp((log2(max(L,1e-6))+14.0)/24.0, 0.0, 1.0)*255.0;',
      '  gl_FragColor = vec4(floor(v)/255.0, fract(v), 0.0, 1.0); }'].join('\n'), { tCube: { value: cubeRT.texture } });
    const fsq = new T.FullScreenQuad(compMat);
    const pass = function (mat, rt) { fsq.material = mat; renderer.setRenderTarget(rt); fsq.render(renderer); };
    const normalMat = new T.MeshNormalMaterial();

    /* ---------- reflexo planar no piso ---------- */
    const vcam = new T.PerspectiveCamera(); vcam.layers.enable(1);
    const floorUni = { tex: { value: reflRT.texture }, mat: { value: new T.Matrix4() }, k: { value: 0 } };
    Q.M.floor.onBeforeCompile = function (sh) {
      T.Material.prototype.onBeforeCompile.call(this, sh);
      sh.uniforms.uReflTex = floorUni.tex; sh.uniforms.uReflMat = floorUni.mat; sh.uniforms.uReflK = floorUni.k;
      sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nuniform mat4 uReflMat;\nvarying vec4 vReflUv;')
        .replace('#include <project_vertex>', '#include <project_vertex>\nvReflUv = uReflMat * (modelMatrix * vec4(transformed, 1.0));');
      sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nuniform sampler2D uReflTex;\nuniform float uReflK;\nvarying vec4 vReflUv;')
        .replace('#include <output_fragment>', [
          'vec2 rUv = vReflUv.xy / vReflUv.w; float rG = 1.0 - roughnessFactor;',
          'vec3 rCol = texture2DLodEXT(uReflTex, rUv, 0.4 + roughnessFactor * 6.0).rgb;',
          'float rF = 0.05 + 0.95 * pow(1.0 - saturate(dot(normalize(vViewPosition), normal)), 5.0);',
          'outgoingLight += rCol * rF * rG * rG * uReflK * 1.5;',
          '#include <output_fragment>'].join('\n'));
    };
    const _p = new T.Vector3(), _l = new T.Vector3(), _u = new T.Vector3(), _rot = new T.Matrix4(), _pl = new T.Plane(), _cp = new T.Vector4(), _q = new T.Vector4();
    const _bias = new T.Matrix4().set(0.5, 0, 0, 0.5, 0, 0.5, 0, 0.5, 0, 0, 0.5, 0.5, 0, 0, 0, 1);
    function renderReflection() {
      _p.setFromMatrixPosition(camera.matrixWorld); _rot.extractRotation(camera.matrixWorld);
      _l.set(0, 0, -1).applyMatrix4(_rot).add(_p); _u.set(0, 1, 0).applyMatrix4(_rot);
      vcam.position.set(_p.x, -_p.y, _p.z); vcam.up.set(_u.x, -_u.y, _u.z); vcam.lookAt(_l.x, -_l.y, _l.z);
      vcam.far = camera.far; vcam.updateMatrixWorld(); vcam.projectionMatrix.copy(camera.projectionMatrix);
      floorUni.mat.value.copy(_bias).multiply(vcam.projectionMatrix).multiply(vcam.matrixWorldInverse);
      _pl.set(_u.set(0, 1, 0), 0); _pl.applyMatrix4(vcam.matrixWorldInverse);
      _cp.set(_pl.normal.x, _pl.normal.y, _pl.normal.z, _pl.constant);
      const pm = vcam.projectionMatrix, e = pm.elements;
      _q.x = (Math.sign(_cp.x) + e[8]) / e[0]; _q.y = (Math.sign(_cp.y) + e[9]) / e[5]; _q.z = -1; _q.w = (1 + e[10]) / e[14];
      _cp.multiplyScalar(2 / _cp.dot(_q));
      e[2] = _cp.x; e[6] = _cp.y; e[10] = _cp.z + 1 - 0.003; e[14] = _cp.w;
      const room = E.room; room.floor.visible = false;
      renderer.setRenderTarget(reflRT); renderer.render(scene, vcam);
      room.floor.visible = true;
    }

    /* ---------- estado ---------- */
    const E = {
      renderer: renderer, scene: scene, overlay: overlay, camera: camera, controls: controls, canvas: canvas, room: null,
      opts: { ao: true, refl: true, maxSamples: 36, maxPix: 2.1e6, intPix: 1.35e6, minS: 0.8 },
      exposure: 1, userExposure: 1, lum: 0.5, dirty: true, shadowsDirty: true, envDirty: 3, sample: 0,
      doorOpen: false, curtainOn: false, onFrame: null, onCull: null, onProgress: null, frames: 0, orbit: true, walk: false, zoom: 1, filmOn: false, onFilm: null
    };
    let cssW = 2, cssH = 2, bw = 2, bh = 2, iw = 2, ih = 2, scaleNow = 1, sI = 0.7, jittered = false, streak = 0, lastDirty = 0, seed = 0;

    function alloc(scale) {
      scaleNow = scale; iw = Math.max(2, Math.round(bw * scale)); ih = Math.max(2, Math.round(bh * scale));
      [sceneRT, gRT, aoRT, aoRT2, colorRT, ldrRT, accA, accB].forEach(function (rt) { rt.setSize(iw, ih); });
      reflRT.setSize(Math.max(2, iw >> 1), Math.max(2, ih >> 1)); bloom.setSize(iw, ih);
      blurMat.uniforms.uTexel.value.set(1 / iw, 1 / ih);
    }
    function fitFov() {
      const a = camera.aspect, deg = 180 / Math.PI;
      let f = E.walk ? Math.min(92, Math.max(60, 2 * Math.atan(0.9 / a) * deg)) : Math.min(88, Math.max(56, 2 * Math.atan(0.6 / a) * deg));
      if (E.zoom !== 1) f = 2 * Math.atan(Math.tan(f / deg / 2) / E.zoom) * deg;
      camera.fov = f; camera.updateProjectionMatrix();
    }
    E.setSize = function (w, h) {
      cssW = Math.max(2, w); cssH = Math.max(2, h);
      const dpr = Math.min(window.devicePixelRatio || 1, 2), pr = Math.max(0.6, Math.min(dpr, Math.sqrt(E.opts.maxPix / (cssW * cssH))));
      renderer.setPixelRatio(pr); renderer.setSize(cssW, cssH, false);
      bw = Math.floor(cssW * pr); bh = Math.floor(cssH * pr);
      sI = Q.clamp(Math.sqrt(E.opts.intPix / (bw * bh)), E.opts.minS, 1);
      camera.aspect = cssW / cssH; fitFov(); alloc(1); E.dirty = true;
    };
    E.refitFov = function () { fitFov(); E.dirty = true; };
    E.setQuality = function (q) {
      const o = E.opts;
      if (q === 'leve') { o.ao = false; o.refl = false; o.maxSamples = 12; o.maxPix = 1.1e6; o.intPix = 0.7e6; o.minS = 0.62; }
      else if (q === 'ultra') { o.ao = true; o.refl = true; o.maxSamples = 72; o.maxPix = 3.6e6; o.intPix = 2.2e6; o.minS = 0.9; }
      else { o.ao = true; o.refl = true; o.maxSamples = 36; o.maxPix = 2.1e6; o.intPix = 1.35e6; o.minS = 0.8; }
      E.setSize(cssW, cssH);
    };

    E.setRoom = function (room) {
      if (E.room) {
        scene.remove(E.room.group);
        E.room.group.traverse(function (o) { if (o.geometry) o.geometry.dispose(); });
      }
      E.room = room; scene.add(room.group);
      E.envDirty = 4; E.shadowsDirty = true; E.dirty = true;
    };

    /* captura o ambiente (luz indireta + reflexos) a partir do centro do quarto */
    function captureEnv() {
      const room = E.room; if (!room) return;
      const fk = floorUni.k.value; floorUni.k.value = 0;
      room.hall.visible = E.doorOpen; room.curtain.visible = E.curtainOn; if (E.onCull) E.onCull(null);
      room.lamp.position.copy(room.lampPos); room.sun.position.copy(room.sunBase);
      cubeCam.position.copy(room.center);
      cubeCam.update(renderer, scene);
      envRT = pmrem.fromCubemap(cubeRT.texture, envRT);
      scene.environment = envRT.texture;
      floorUni.k.value = fk;
      pass(lumMat, lumRT);
      const b = new Uint8Array(4); renderer.readRenderTargetPixels(lumRT, 0, 0, 1, 1, b);
      E.lum = Math.pow(2, ((b[0] + b[1] / 255) / 255) * 24 - 14);
      renderer.setRenderTarget(null);
      updateExposure();
    }
    function updateExposure() {
      const e = Q.clamp(0.55 / Math.pow(Math.max(E.lum, 1e-4), 0.72), 0.35, 14) * E.userExposure;
      if (Math.abs(e - E.exposure) / E.exposure > 0.012) {
        E.exposure = e; Q.emisScale = 1 / e; Q.refreshEmis(scene);
      }
    }
    E.setUserExposure = function (v) { E.userExposure = v; updateExposure(); E.envDirty = Math.max(E.envDirty, 1); E.dirty = true; };

    function renderFrame(s) {
      const room = E.room, film = E.filmOn && s > 0, js = film ? 1 + (s % 8) : s;
      if (s > 0) camera.setViewOffset(iw, ih, halton(js, 2) - 0.5, halton(js, 3) - 0.5, iw, ih); else if (camera.view) camera.clearViewOffset();
      if (s > 0 && !film) {
        const a = halton(s, 5) * 6.2832, r = Math.sqrt(halton(s, 7));
        room.lamp.position.set(room.lampPos.x + Math.cos(a) * r * 0.075, room.lampPos.y, room.lampPos.z + Math.sin(a) * r * 0.075);
        room.sun.position.set(room.sunBase.x, room.sunBase.y + Math.cos(a) * r * 0.07, room.sunBase.z + Math.sin(a) * r * 0.07);
        renderer.shadowMap.needsUpdate = true; jittered = true;
      } else {
        room.lamp.position.copy(room.lampPos); room.sun.position.copy(room.sunBase);
        if (jittered || E.shadowsDirty) renderer.shadowMap.needsUpdate = true;
        jittered = false; E.shadowsDirty = false;
      }
      const cp = camera.position;
      room.hall.visible = E.doorOpen && cp.x < room.W - 0.02; room.curtain.visible = E.curtainOn && cp.x > 0.1;
      if (E.onCull) E.onCull(cp);
      const refl = E.opts.refl && cp.y > 0.06;
      floorUni.k.value = refl ? 1 : 0;
      if (refl) renderReflection();
      renderer.setRenderTarget(sceneRT); renderer.render(scene, camera);
      if (E.opts.ao) {
        const bg = scene.background; scene.background = null; scene.overrideMaterial = normalMat; camera.layers.set(0);
        renderer.setRenderTarget(gRT); renderer.render(scene, camera);
        scene.overrideMaterial = null; scene.background = bg; camera.layers.enable(1);
        const u = aoMat.uniforms; u.tDepth.value = gRT.depthTexture; u.tNormal.value = gRT.texture;
        u.uProj.value.copy(camera.projectionMatrix); u.uProjInv.value.copy(camera.projectionMatrixInverse); u.uSeed.value = s;
        pass(aoMat, aoRT);
        blurMat.uniforms.tAO.value = aoRT.texture; blurMat.uniforms.tDepth.value = gRT.depthTexture;
        blurMat.uniforms.uNear.value = camera.near; blurMat.uniforms.uFar.value = camera.far;
        pass(blurMat, aoRT2);
      }
      compMat.uniforms.tColor.value = sceneRT.texture; compMat.uniforms.tAO.value = aoRT2.texture; compMat.uniforms.uAO.value = E.opts.ao ? 1 : 0;
      pass(compMat, colorRT);
      bloom.threshold = 1.7 / E.exposure; bloom.highPassUniforms.smoothWidth.value = 1.2 / E.exposure;
      bloom.render(renderer, null, colorRT, 0, false);
      finalMat.uniforms.tColor.value = colorRT.texture; finalMat.uniforms.uExposure.value = E.exposure;
      pass(finalMat, ldrRT);
      accMat.uniforms.tPrev.value = accA.texture; accMat.uniforms.tNew.value = ldrRT.texture; accMat.uniforms.uW.value = film ? Math.max(1 / (s + 1), 0.3) : 1 / (s + 1);
      pass(accMat, accB); const tmp = accA; accA = accB; accB = tmp;
      blitMat.uniforms.tTex.value = accA.texture; blitMat.uniforms.uSeed.value = (seed = (seed + 7.31) % 64);
      pass(blitMat, null);
      if (camera.view) camera.clearViewOffset();
      if (overlay.children.length) { renderer.autoClear = false; renderer.clearDepth(); renderer.render(overlay, camera); renderer.autoClear = true; }
      E.frames++;
    }

    let tPrev = 0, ema = 30, lastFilm = 0;
    function loop() {
      requestAnimationFrame(loop);
      if (!E.room || cssW < 4) return;
      if (E.orbit) { controls.update(); if (camera.position.y < 0.06) camera.position.y = 0.06; }
      if (E.onFrame) E.onFrame();
      const now = performance.now();
      let tick = false;
      if (E.filmOn && E.onFilm && now - lastFilm >= 64) { lastFilm = now; E.onFilm(now); tick = true; }
      if (E.envDirty > 0) { captureEnv(); E.envDirty--; E.dirty = true; }
      if (E.dirty) {
        E.dirty = false; streak++;
        if (streak >= 2) { const dt = now - tPrev; ema = ema * 0.8 + dt * 0.2; if (ema > 70 && sI > E.opts.minS) sI = Math.max(E.opts.minS, sI * 0.96); }
        tPrev = now; lastDirty = now;
        if (streak >= 3 && Math.abs(scaleNow - sI) > 0.04 && sI < 0.97) alloc(sI);
        renderFrame(0); E.sample = 1;
        if (E.onProgress) E.onProgress(0);
      } else {
        streak = 0;
        if (scaleNow !== 1) { if (now - lastDirty > 170) { alloc(1); renderFrame(0); E.sample = 1; } }
        else if (E.filmOn) { if (tick) { renderFrame(E.sample); E.sample = Math.min(E.sample + 1, 4000); if (E.onProgress) E.onProgress(1); } }
        else if (E.sample < E.opts.maxSamples && now - lastDirty > 60) {
          renderFrame(E.sample); E.sample++;
          if (E.onProgress) E.onProgress(E.sample / E.opts.maxSamples);
        }
      }
    }
    E.start = function () { requestAnimationFrame(loop); };
    controls.addEventListener('change', function () { E.dirty = true; });
    E.touch = function (shadows, env) { E.dirty = true; if (shadows) E.shadowsDirty = true; if (env) E.envDirty = Math.max(E.envDirty, env); };

    /* miniaturas do catálogo */
    const tScene = new T.Scene(), tCam = new T.PerspectiveCamera(28, 1, 0.01, 30), tRT = new T.WebGLRenderTarget(168, 168, { samples: msaa });
    tScene.add(new T.HemisphereLight(0xffffff, 0x4a4560, 0.7));
    const tKey = new T.DirectionalLight(0xffffff, 2.4); tKey.position.set(2.2, 3, 1.6); tScene.add(tKey);
    E.thumb = function (type) {
      const d = Q.catalog[type], p = Object.assign({}, d.defaults);
      const g = Q.makeObject(type, p, 3); if (g.userData.thumbPose) { g.userData.pose(g.userData.thumbPose); g.updateMatrixWorld(true); }
      const box = new T.Box3().setFromObject(g), c = box.getCenter(new T.Vector3()), sp = box.getBoundingSphere(new T.Sphere());
      tScene.add(g); tScene.environment = null;
      const dir = d.thumbDir ? new T.Vector3().fromArray(d.thumbDir) : g.userData.thumbPose ? new T.Vector3(0.95, 0.5, 0.75) : d.flat ? new T.Vector3(0.3, 1.1, 1) : d.mount === 'wall' ? new T.Vector3(0.35, 0.15, 1) : new T.Vector3(0.75, 0.55, 1); dir.normalize();
      tCam.position.copy(c).addScaledVector(dir, (sp.radius / Math.sin((14 * Math.PI) / 180)) * 1.02); tCam.lookAt(c); tCam.updateProjectionMatrix();
      const es = Q.emisScale; Q.emisScale = 0.4; Q.refreshEmis(g);
      renderer.setClearColor(0x000000, 0); renderer.setRenderTarget(tRT); renderer.clear(); renderer.render(tScene, tCam);
      const px = new Uint8Array(168 * 168 * 4); renderer.readRenderTargetPixels(tRT, 0, 0, 168, 168, px);
      renderer.setRenderTarget(null); renderer.setClearColor(0x0b0a0f, 1);
      Q.emisScale = es; tScene.remove(g); Q.disposeObject(g);
      const cv = Q.canvas(168, 168), cx = cv.getContext('2d'), im = cx.createImageData(168, 168);
      for (let y = 0; y < 168; y++) for (let x = 0; x < 168; x++) {
        const i = ((167 - y) * 168 + x) * 4, o = (y * 168 + x) * 4, a = px[i + 3] / 255;
        for (let k = 0; k < 3; k++) { let v = px[i + k] / 255; v = a > 0.001 ? v / a : 0; v = v / (v + 0.45) * 1.42; im.data[o + k] = Math.pow(Math.min(1, v), 1 / 2.2) * 255; }
        im.data[o + 3] = px[i + 3];
      }
      cx.putImageData(im, 0, 0);
      E.dirty = true; E.shadowsDirty = true;
      return cv.toDataURL('image/png');
    };
    return E;
  };
})();
