/* ==========================================================================
   WEBFIBER · LANDING EXPERIMENTAL "700 MEGA" — interações
   ⚙️ CONFIG: tudo que o dono pode querer trocar está aqui no topo.
   ========================================================================== */

const CONFIG = {
  whatsappNumero: "5521985589201",
  whatsappMensagem: "Olá! Quero contratar o plano de 700 Mega por R$ 99,90 da WebFiber.",
  velocidadePlano: 700,          // número que o velocímetro do hero atinge
  // Conversão Google Ads (mesmo padrão do site oficial — dispara ao clicar em WhatsApp)
  googleAdsSendTo: "AW-18086861405/Sb-JCLHf9LscEN20vrBD",
  // só conta conversão no domínio oficial (testes em localhost/github.io não contaminam o Ads)
  ativarRastreio: /webfiberprovedor\.com\.br$/.test(location.hostname)
};

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/* --------------------------------------------------------------------------
   1 · Links de WhatsApp — todo [data-wa] vira link com mensagem pronta.
       [data-wa-msg] permite mensagem específica (ex.: planos 850/1G).
   -------------------------------------------------------------------------- */
document.querySelectorAll("[data-wa]").forEach(el => {
  const msg = el.getAttribute("data-wa-msg") || CONFIG.whatsappMensagem;
  el.href = `https://wa.me/${CONFIG.whatsappNumero}?text=${encodeURIComponent(msg)}`;
  el.target = "_blank";
  el.rel = "noopener";
});

/* Rastreador de conversão (idêntico ao do site oficial; ativar ao publicar) */
if (CONFIG.ativarRastreio) {
  let lastFire = 0;
  document.addEventListener("click", ev => {
    const a = ev.target.closest("a");
    if (!a || !/wa\.me|whatsapp|5521985589201/i.test(a.href || "")) return;
    const now = Date.now();
    if (now - lastFire < 1500 || typeof gtag !== "function") return;
    lastFire = now;
    gtag("event", "conversion", { send_to: CONFIG.googleAdsSendTo });
  }, true);
}

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
    // o NÚMERO fica cravado em 700; só o ponteiro vibra de leve (tela viva).
    // Pausa fora da viewport para não gastar bateria.
    if (breathing) return;
    breathing = true;
    val.textContent = MAX;
    const t0 = performance.now();
    (function frame(now) {
      if (!visible || document.hidden) { breathing = false; render(1, false); return; }
      render(.992 + Math.sin((now - t0) / 800) * .008, false);
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
  const scene = document.querySelector("[data-tilt-scene]");
  const stage = document.querySelector("[data-tilt]");
  if (!scene || !stage) return;
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

/* --------------------------------------------------------------------------
   10 · Busca de bairros
   -------------------------------------------------------------------------- */
(function bairros() {
  const input = document.getElementById("bairroInput");
  const chips = [...document.querySelectorAll("#bairroChips li")];
  const found = document.getElementById("bairroFound");
  const notFound = document.getElementById("bairroNotFound");
  if (!input) return;

  const norm = s => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

  input.addEventListener("input", () => {
    const q = norm(input.value);
    let any = false;
    chips.forEach(li => {
      const hit = q && norm(li.textContent).includes(q);
      li.classList.toggle("match", hit);
      li.classList.toggle("dim", q && !hit);
      if (hit) any = true;
    });
    found.hidden = !(q && any);
    notFound.hidden = !(q.length >= 3 && !any);
  });
})();

/* --------------------------------------------------------------------------
   11 · Barra fixa mobile: aparece depois do hero
   -------------------------------------------------------------------------- */
(function stickybar() {
  const bar = document.getElementById("stickybar");
  if (!bar) return;
  const show = () => bar.classList.toggle("show", window.scrollY > window.innerHeight * .72);
  show();
  window.addEventListener("scroll", show, { passive: true });
})();

/* --------------------------------------------------------------------------
   12 · Detalhe: ano do rodapé
   -------------------------------------------------------------------------- */
const ano = document.getElementById("anoAtual");
if (ano) ano.textContent = new Date().getFullYear();
