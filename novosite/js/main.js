/* ==========================================================================
   WEBFIBER · LANDING EXPERIMENTAL "700 MEGA" — interações
   ⚙️ CONFIG: tudo que o dono pode querer trocar está aqui no topo.
   ========================================================================== */

const CONFIG = {
  whatsappNumero: "5521985589201",
  whatsappMensagem: "Olá! Vim pelo site e quero contratar um plano da WebFiber.",
  velocidadePlano: 1000           // número que o velocímetro do hero atinge
};
// Conversão Google Ads: feita pela função gtag_report_conversion (no <head> do index.html),
// chamada no onclick de cada botão de WhatsApp — padrão oficial do Google Ads.

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/* --------------------------------------------------------------------------
   1 · Links de WhatsApp — todo [data-wa] vira link com mensagem pronta.
       [data-wa-msg] permite mensagem específica (ex.: planos 850/1G).
   -------------------------------------------------------------------------- */
document.querySelectorAll("[data-wa]").forEach(el => {
  const msg = el.getAttribute("data-wa-msg") || CONFIG.whatsappMensagem;
  const url = `https://wa.me/${CONFIG.whatsappNumero}?text=${encodeURIComponent(msg)}`;
  el.href = url;
  // conversão do Google Ads no clique (função definida no <head>);
  // o event_callback garante o envio antes de abrir o WhatsApp
  el.setAttribute("onclick", `return gtag_report_conversion('${url.replace(/'/g, "%27")}');`);
});

/* --------------------------------------------------------------------------
   2 · Header: ganha fundo ao rolar
   -------------------------------------------------------------------------- */
const topbar = document.getElementById("topbar");
const onScrollHeader = () => topbar.classList.toggle("is-scrolled", window.scrollY > 30);
onScrollHeader();
window.addEventListener("scroll", onScrollHeader, { passive: true });

/* --------------------------------------------------------------------------
   3 · Reveal on scroll (IntersectionObserver)
   -------------------------------------------------------------------------- */
const ro = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      // efeito cascata: pequenos atrasos entre vizinhos visíveis juntos
      const el = e.target;
      const idx = [...el.parentElement.children].indexOf(el);
      el.style.transitionDelay = `${Math.min(idx * 70, 350)}ms`;
      el.classList.add("in");
      ro.unobserve(el);
    }
  });
}, { threshold: 0.12, rootMargin: "0px 0px -6% 0px" });
document.querySelectorAll("[data-rv]").forEach(el => ro.observe(el));

/* --------------------------------------------------------------------------
   4 · Marquees em loop infinito (duplica o conteúdo e anima o trilho)
   -------------------------------------------------------------------------- */
function setupMarquee(row, trackClass) {
  const group = row.firstElementChild;
  const track = document.createElement("div");
  track.className = trackClass;
  row.appendChild(track);
  track.appendChild(group);
  track.appendChild(group.cloneNode(true));
}
document.querySelectorAll(".posters__row").forEach(r => setupMarquee(r, "posters__track"));
document.querySelectorAll(".reviews__row").forEach(r => setupMarquee(r, "reviews__track"));
// faixa do topo já nasce com .marquee__track — só duplica o grupo
const mq = document.querySelector(".marquee__track");
if (mq) mq.appendChild(mq.firstElementChild.cloneNode(true));

/* --------------------------------------------------------------------------
   5 · Canvas: fibra óptica viva no hero (leve; pausa fora de cena)
   -------------------------------------------------------------------------- */
(function fiberCanvas() {
  const cv = document.getElementById("fiberCanvas");
  // celular fica com o gradiente estático: mais leve e sem ruído sobre o texto
  if (!cv || reduceMotion || window.innerWidth < 720) { cv && cv.remove(); return; }
  if (!cv.clientWidth) { cv.remove(); return; }  // tema royal oculta o canvas — sai antes de desenhar
  const ctx = cv.getContext("2d");
  const DPR = Math.min(window.devicePixelRatio || 1, 1.6);
  let W = 0, H = 0, fibers = [], running = true, raf = 0;

  function resize() {
    W = cv.clientWidth; H = cv.clientHeight;
    cv.width = W * DPR; cv.height = H * DPR;
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    buildFibers();
  }

  function buildFibers() {
    const n = 12;
    fibers = Array.from({ length: n }, (_, i) => ({
      y: (H / (n + 1)) * (i + 1),
      drop: H * (.08 + Math.random() * .2),   // inclinação descendo p/ a direita
      amp: 14 + Math.random() * 30,
      len: .5 + Math.random() * .8,
      hue: Math.random() < .8 ? "0,224,255" : (Math.random() < .5 ? "252,212,0" : "255,46,146"),
      alpha: .10 + Math.random() * .10,
      pulse: Math.random(),
      speed: .0009 + Math.random() * .0017
    }));
  }

  function wavePoint(f, x) {
    const t = x / W;
    return f.y + t * f.drop - f.drop / 2 +
      Math.sin(t * Math.PI * 2 * f.len + f.pulse * Math.PI * 2) * f.amp;
  }

  function draw() {
    if (!running) return;
    ctx.clearRect(0, 0, W, H);
    for (const f of fibers) {
      f.pulse = (f.pulse + f.speed) % 1;
      // o cabo de fibra
      ctx.beginPath();
      for (let x = 0; x <= W; x += 26) {
        const y = wavePoint(f, x);
        x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      }
      ctx.strokeStyle = `rgba(${f.hue},${f.alpha})`;
      ctx.lineWidth = 1.3;
      ctx.stroke();
      // pulso de luz compacto, com rastro
      const px = f.pulse * W;
      const py = wavePoint(f, px);
      ctx.beginPath();
      for (let x = Math.max(0, px - 90); x <= px; x += 12) {
        const y = wavePoint(f, x);
        x <= px - 88 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      }
      ctx.strokeStyle = `rgba(${f.hue},.5)`;
      ctx.lineWidth = 2.2;
      ctx.stroke();
      const g = ctx.createRadialGradient(px, py, 0, px, py, 13);
      g.addColorStop(0, `rgba(${f.hue},.9)`);
      g.addColorStop(1, `rgba(${f.hue},0)`);
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(px, py, 13, 0, Math.PI * 2);
      ctx.fill();
    }
    raf = requestAnimationFrame(draw);
  }

  function setRunning(on) {
    if (on === running) return;
    running = on;
    if (on) draw(); else cancelAnimationFrame(raf);
  }

  // pausa quando o hero sai da tela ou a aba fica oculta
  new IntersectionObserver(([e]) => setRunning(e.isIntersecting && !document.hidden))
    .observe(cv);
  document.addEventListener("visibilitychange", () => {
    setRunning(!document.hidden && cv.getBoundingClientRect().bottom > 0);
  });

  window.addEventListener("resize", resize, { passive: true });
  resize();
  draw();
})();

/* --------------------------------------------------------------------------
   6 · Velocímetro do hero: 0 → 700 com easing + “respiração” contínua
   -------------------------------------------------------------------------- */
(function speedometer() {
  const bar = document.getElementById("gaugeBar");
  const needle = document.getElementById("gaugeNeedle");
  const val = document.getElementById("speedVal");
  if (!bar || !needle || !val) return;

  const LEN = 251.3;                 // comprimento do arco (dasharray)
  const MAX = CONFIG.velocidadePlano;
  const easeOut = t => 1 - Math.pow(1 - t, 3);
  let started = false, visible = false, breathing = false, raf = 0;

  function render(p, withText = true) {  // p: 0..1
    bar.style.strokeDashoffset = LEN * (1 - p);
    needle.style.transform = `rotate(${-90 + 180 * p}deg)`;
    if (withText) val.textContent = Math.round(MAX * p);
  }
  render(0);

  function animate() {
    const t0 = performance.now(), dur = 2200;
    (function frame(now) {
      const t = Math.min((now - t0) / dur, 1);
      render(easeOut(t));
      if (t < 1) raf = requestAnimationFrame(frame);
      else if (!reduceMotion) startBreathe();
    })(t0);
  }

  function startBreathe() {
    // a fibra "bate" continuamente entre 990 e 1000 (não zera) — tela viva dentro da TV.
    // Pausa fora da viewport para não gastar bateria.
    if (breathing) return;
    breathing = true;
    const t0 = performance.now();
    (function frame(now) {
      if (!visible || document.hidden) { breathing = false; render(1); return; }
      // oscila 0.99→1.00 → número 990↔1000, com leve "tremor" pra parecer medição real
      const base = 0.99 + (Math.sin((now - t0) / 360) * 0.5 + 0.5) * 0.01;
      const jitter = Math.sin((now - t0) / 70) * 0.0012;
      render(Math.min(1, base + jitter));
      raf = requestAnimationFrame(frame);
    })(t0);
  }

  new IntersectionObserver(([e]) => {
    visible = e.isIntersecting;
    if (visible && !started) {
      started = true;
      reduceMotion ? render(1) : animate();
    } else if (visible && started && !reduceMotion) {
      startBreathe();
    }
  }, { threshold: .4 }).observe(document.getElementById("gauge"));
})();

/* --------------------------------------------------------------------------
   7 · Contadores animados da seção Confiança
   -------------------------------------------------------------------------- */
(function counters() {
  const els = document.querySelectorAll("[data-count]");
  if (!els.length) return;
  const fmt = (el, v) => {
    const dec = +el.dataset.decimals || 0;
    let txt = dec ? v.toFixed(dec).replace(".", ",") : Math.round(v).toString();
    if (el.dataset.format === "mil") txt = Math.round(v).toLocaleString("pt-BR");
    el.textContent = txt + (el.dataset.suffix || "");
  };
  const io = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      const el = e.target, target = parseFloat(el.dataset.count);
      io.unobserve(el);
      if (reduceMotion) return fmt(el, target);
      const t0 = performance.now(), dur = 1800;
      (function frame(now) {
        const t = Math.min((now - t0) / dur, 1);
        fmt(el, target * (1 - Math.pow(1 - t, 3)));
        if (t < 1) requestAnimationFrame(frame);
      })(t0);
    });
  }, { threshold: .5 });
  els.forEach(el => io.observe(el));
})();

/* --------------------------------------------------------------------------
   8 · Tilt 3D no palco do hero (desktop, ponteiro fino)
   -------------------------------------------------------------------------- */
(function tilt() {
  if (reduceMotion || !window.matchMedia("(pointer:fine)").matches) return;
  document.querySelectorAll("[data-tilt-scene]").forEach(scene => {
    const stage = scene.querySelector("[data-tilt]");
    if (!stage) return;
    let raf = 0;
    scene.addEventListener("pointermove", ev => {
      const r = scene.getBoundingClientRect();
      const x = (ev.clientX - r.left) / r.width - .5;
      const y = (ev.clientY - r.top) / r.height - .5;
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        stage.style.transform = `rotateY(${x * 9}deg) rotateX(${y * -8}deg)`;
      });
    });
    scene.addEventListener("pointerleave", () => {
      cancelAnimationFrame(raf);
      stage.style.transform = "";
    });
  });
})();

/* --------------------------------------------------------------------------
   9 · Comparador antes/depois (arrastável com mouse, toque e teclado)
   -------------------------------------------------------------------------- */
(function compare() {
  const box = document.getElementById("cmp");
  const handle = document.getElementById("cmpHandle");
  if (!box || !handle) return;
  let cut = 50, dragging = false;

  function apply(v) {
    cut = Math.max(6, Math.min(94, v));
    box.style.setProperty("--cut", cut + "%");
    handle.setAttribute("aria-valuenow", Math.round(cut));
  }
  apply(50);

  function fromEvent(ev) {
    const r = box.getBoundingClientRect();
    apply(((ev.clientX - r.left) / r.width) * 100);
  }

  handle.addEventListener("pointerdown", ev => {
    dragging = true;
    handle.setPointerCapture(ev.pointerId);
  });
  handle.addEventListener("pointermove", ev => dragging && fromEvent(ev));
  handle.addEventListener("pointerup", () => dragging = false);
  box.addEventListener("pointerdown", ev => {     // clique em qualquer ponto
    if (ev.target.closest(".cmp__handle")) return;
    fromEvent(ev);
  });
  handle.addEventListener("keydown", ev => {
    if (ev.key === "ArrowLeft") { apply(cut - 6); ev.preventDefault(); }
    if (ev.key === "ArrowRight") { apply(cut + 6); ev.preventDefault(); }
  });

  // convite sutil: balança a alça quando entra na tela
  if (!reduceMotion) {
    new IntersectionObserver(([e], obs) => {
      if (!e.isIntersecting) return;
      obs.disconnect();
      let i = 0;
      const wiggle = setInterval(() => {
        apply(50 + Math.sin(i * 1.2) * (14 - i * 2));
        if (++i > 6) { clearInterval(wiggle); apply(50); }
      }, 160);
    }, { threshold: .5 }).observe(box);
  }
})();

/* (Barra fixa mobile: SEMPRE visível — regra do dono; controlada 100% pelo CSS) */

/* --------------------------------------------------------------------------
   10 · Detalhe: ano do rodapé
   -------------------------------------------------------------------------- */
const ano = document.getElementById("anoAtual");
if (ano) ano.textContent = new Date().getFullYear();


/* --------------------------------------------------------------------------
   ROTADOR 3D DE PLANOS (hero do site principal)
   Alterna 700 MEGA / 850 MEGA / 1 GIGA com flip 3D letra a letra + parallax.
   -------------------------------------------------------------------------- */
(function rotadorPlanos() {
  const elNum = document.getElementById("rotNum");
  if (!elNum) return;
  const elUnit = document.getElementById("rotUnit");
  const elPre = document.getElementById("rotPre");
  const elPreco = document.getElementById("rotPreco");
  const elExtra = document.getElementById("rotExtra");
  const dotsBox = document.getElementById("rotDots");
  const rot = document.getElementById("rotador");

  const PLANOS = [
    { num: "700", unit: "MEGA", pre: "por apenas",       preco: "R$ 99,90",  extra: "SÓ INTERNET TURBO",  watch: false },
    { num: "850", unit: "MEGA", pre: "+ streaming por",  preco: "R$ 129,90", extra: "+ WATCH TV INCLUSO", watch: true },
    { num: "1",   unit: "GIGA", pre: "+ TV completa por", preco: "R$ 159,90", extra: "+ WATCH TV INCLUSO", watch: true }
  ];
  let idx = 0, timer = null, trocando = false;

  /* --- efeito "conexões de fibra chegando" ao trocar de plano (canvas leve) --- */
  const fx = document.getElementById("rotFx");
  let fxCtx = null, fxParts = [], fxRaf = 0, fxW = 0, fxH = 0, fxLast = 0;
  const FX_DPR = Math.min(window.devicePixelRatio || 1, 2);
  function fxResize() {
    if (!fx) return;
    fxW = fx.clientWidth; fxH = fx.clientHeight;
    fx.width = fxW * FX_DPR; fx.height = fxH * FX_DPR;
    fxCtx = fx.getContext("2d");
    fxCtx.setTransform(FX_DPR, 0, 0, FX_DPR, 0, 0);
  }
  function dispararRaios() {
    if (!fx || reduceMotion) return;
    if (!fxCtx) fxResize();
    const cx = fxW * 0.31, cy = fxH * 0.45;        // perto do número-herói
    const cores = ["0,224,255", "252,212,0", "255,255,255", "120,180,255"];
    const n = fxW < 480 ? 11 : 17;
    for (let i = 0; i < n; i++) {
      fxParts.push({
        ang: (Math.PI * 2 * i) / n + (i % 2 ? 0.18 : -0.16),
        len: 9 + Math.random() * 24,
        reach: fxW * (0.16 + Math.random() * 0.22),
        t: 0, dur: 420 + Math.random() * 280,
        cor: cores[(Math.random() * cores.length) | 0],
        seg: 2 + ((Math.random() * 3) | 0), cx, cy
      });
    }
    for (let i = 0; i < 6; i++) {                   // pontos de "conexão" piscando
      fxParts.push({ node: true, x: cx + (Math.random() - .5) * fxW * .5, y: cy + (Math.random() - .5) * fxH * .6, t: 0, dur: 480 + Math.random() * 320, cor: "0,224,255" });
    }
    if (!fxRaf) { fxLast = performance.now(); fxRaf = requestAnimationFrame(loopFx); }
  }
  function loopFx() {
    const now = performance.now(), dt = now - fxLast; fxLast = now;
    fxCtx.clearRect(0, 0, fxW, fxH);
    fxParts = fxParts.filter(p => (p.t += dt) < p.dur);
    for (const p of fxParts) {
      const k = p.t / p.dur, fade = 1 - k;
      if (p.node) {
        const r = 2.4 + Math.sin(k * Math.PI) * 2.6;
        fxCtx.beginPath(); fxCtx.arc(p.x, p.y, r, 0, Math.PI * 2);
        fxCtx.fillStyle = "rgba(" + p.cor + "," + (Math.sin(k * Math.PI) * .8).toFixed(3) + ")";
        fxCtx.fill();
        continue;
      }
      const grow = Math.min(1, k * 1.6);
      const dx = Math.cos(p.ang), dy = Math.sin(p.ang);
      let x = p.cx, y = p.cy;
      fxCtx.beginPath(); fxCtx.moveTo(x, y);
      for (let s = 1; s <= p.seg; s++) {
        const d = (p.reach * grow) * (s / p.seg);
        x = p.cx + dx * d + (-dy) * (Math.sin(s * 2 + p.ang) * p.len * .5);
        y = p.cy + dy * d + (dx) * (Math.sin(s * 2 + p.ang) * p.len * .5);
        fxCtx.lineTo(x, y);
      }
      fxCtx.strokeStyle = "rgba(" + p.cor + "," + (fade * .9).toFixed(3) + ")";
      fxCtx.lineWidth = 1.6;
      fxCtx.shadowColor = "rgba(" + p.cor + "," + fade.toFixed(3) + ")";
      fxCtx.shadowBlur = 8;
      fxCtx.stroke();
      fxCtx.shadowBlur = 0;
      fxCtx.beginPath(); fxCtx.arc(x, y, 1.8 * fade + .6, 0, Math.PI * 2);
      fxCtx.fillStyle = "rgba(255,255,255," + fade.toFixed(3) + ")";
      fxCtx.fill();
    }
    if (fxParts.length) fxRaf = requestAnimationFrame(loopFx);
    else { fxRaf = 0; fxCtx.clearRect(0, 0, fxW, fxH); }
  }
  if (fx) window.addEventListener("resize", fxResize, { passive: true });

  function chars(el, txt) {
    el.innerHTML = "";
    [...txt].forEach((ch, i) => {
      const s = document.createElement("i");
      s.className = "ch";
      s.style.fontStyle = "normal";
      s.textContent = ch === " " ? " " : ch;
      s.style.transitionDelay = (i * 60) + "ms";
      el.appendChild(s);
    });
  }
  function setAll(p) {
    chars(elNum, p.num);
    chars(elUnit, p.unit);
    chars(elPreco, p.preco);
    elPre.textContent = p.pre + " ";
    elExtra.innerHTML = '<span class="rot-extra__pill' + (p.watch ? " rot-extra__pill--watch" : "") + '">' + p.extra + "</span>";
  }
  function marcaDot() { [...dotsBox.children].forEach((d, i) => d.classList.toggle("on", i === idx)); }

  function flipTo(n) {
    if (n === idx || trocando) return;
    trocando = true;
    [elNum, elUnit, elPreco].forEach(el => el.classList.add("out"));
    elExtra.classList.add("out");
    setTimeout(() => {
      setAll(PLANOS[n]);
      idx = n;
      marcaDot();
      dispararRaios();   // conexões de fibra "chegam" junto com o novo plano
      requestAnimationFrame(() => requestAnimationFrame(() => {
        [elNum, elUnit, elPreco].forEach(el => el.classList.remove("out"));
        elExtra.classList.remove("out");
        trocando = false;
      }));
    }, 600);
  }

  PLANOS.forEach((_, i) => {
    const d = document.createElement("button");
    d.type = "button";
    d.className = "rot-dot";
    d.setAttribute("aria-label", "Ver plano " + PLANOS[i].num + " " + PLANOS[i].unit);
    d.addEventListener("click", () => { para(); flipTo(i); arma(); });
    dotsBox.appendChild(d);
  });

  function arma() { if (!reduceMotion) { clearInterval(timer); timer = setInterval(() => flipTo((idx + 1) % PLANOS.length), 4000); } }
  function para() { clearInterval(timer); }
  rot.addEventListener("pointerenter", para);
  rot.addEventListener("pointerleave", arma);
  document.addEventListener("visibilitychange", () => document.hidden ? para() : arma());

  // parallax 3D: o bloco inteiro acompanha o mouse (desktop)
  if (!reduceMotion && window.matchMedia("(pointer:fine)").matches) {
    const copy = rot.closest(".hero__copy") || rot;
    let raf = 0;
    copy.addEventListener("pointermove", ev => {
      const r = copy.getBoundingClientRect();
      const x = (ev.clientX - r.left) / r.width - .5;
      const y = (ev.clientY - r.top) / r.height - .5;
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        rot.style.transform = "rotateY(" + (x * 6) + "deg) rotateX(" + (y * -5) + "deg)";
        rot.style.transformStyle = "preserve-3d";
      });
    });
    copy.addEventListener("pointerleave", () => { cancelAnimationFrame(raf); rot.style.transform = ""; });
  }

  setAll(PLANOS[0]);
  marcaDot();
  arma();
})();

