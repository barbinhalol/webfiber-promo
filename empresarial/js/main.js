/* ==========================================================================
   WEBFIBER · EMPRESARIAL — interações
   ⚙️ CONFIG: tudo que o dono pode querer trocar está aqui no topo.
   ========================================================================== */

const CONFIG = {
  // WhatsApp comercial da WebFiber. Se houver um número EMPRESARIAL dedicado,
  // troque aqui (só dígitos, com 55 + DDD).
  whatsappEmpresarial: "5521985589201",
  // Mensagem padrão dos botões (os botões específicos têm a sua própria via data-wa-msg no HTML)
  whatsappMensagem: "Olá! Gostaria de uma cotação empresarial da WebFiber. Pode verificar a viabilidade para minha empresa?"
};
// Conversão Google Ads + Meta Pixel "Lead" disparam no clique de cada botão [data-wa]
// (ver bloco 1 abaixo), SEM cancelar a navegação nativa do link. Ambos só contam no
// domínio oficial (guard de domínio) — preview/local não sujam o Ads nem o dataset.

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/* --------------------------------------------------------------------------
   1 · Links de WhatsApp — todo [data-wa] vira link com mensagem pronta.
   -------------------------------------------------------------------------- */
document.querySelectorAll("[data-wa]").forEach(el => {
  const msg = el.getAttribute("data-wa-msg") || CONFIG.whatsappMensagem;
  // Enriquecimento: o HTML já tem href real (wa.me) como fallback; aqui só anexamos a mensagem.
  el.href = `https://wa.me/${CONFIG.whatsappEmpresarial}?text=${encodeURIComponent(msg)}`;
  // Tracking dispara no clique SEM cancelar a navegação nativa do link
  // (o CTA funciona mesmo se gtag/fbq falharem ou estiverem bloqueados).
  el.addEventListener("click", () => {
    const oficial = /webfiberprovedor\.com\.br$/.test(location.hostname);
    if (typeof fbq !== "undefined") fbq("track", "Lead");                 // fbq só existe no domínio oficial (guard no <head>)
    if (oficial && typeof gtag === "function") {                          // conversão Ads só no domínio oficial (preview não suja)
      gtag("event", "conversion", { "send_to": "AW-18086861405/Sb-JCLHf9LscEN20vrBD", "transport_type": "beacon" });
    }
  });
});

/* --------------------------------------------------------------------------
   2 · Header ganha fundo ao rolar
   -------------------------------------------------------------------------- */
const topbar = document.getElementById("topbar");
const onScrollHeader = () => topbar.classList.toggle("is-scrolled", window.scrollY > 24);
onScrollHeader();
window.addEventListener("scroll", onScrollHeader, { passive: true });

/* --------------------------------------------------------------------------
   3 · Menu mobile (hambúrguer)
   -------------------------------------------------------------------------- */
const burger = document.getElementById("burger");
const mobileNav = document.getElementById("mobileNav");
if (burger && mobileNav) {
  const toggle = (open, returnFocus = false) => {
    mobileNav.classList.toggle("open", open);
    burger.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) { const first = mobileNav.querySelector("a"); if (first) first.focus(); }
    else if (returnFocus) burger.focus();
  };
  burger.addEventListener("click", () => toggle(!mobileNav.classList.contains("open")));
  mobileNav.querySelectorAll("a").forEach(a => a.addEventListener("click", () => toggle(false)));
  // Esc fecha o menu e devolve o foco ao botão (acessibilidade por teclado)
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && mobileNav.classList.contains("open")) toggle(false, true);
  });
}

/* --------------------------------------------------------------------------
   4 · Reveal on scroll (IntersectionObserver) com cascata
   -------------------------------------------------------------------------- */
const ro = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      const el = e.target;
      const idx = [...el.parentElement.children].indexOf(el);
      el.style.transitionDelay = `${Math.min(idx * 60, 320)}ms`;
      el.classList.add("in");
      ro.unobserve(el);
    }
  });
}, { threshold: 0.12, rootMargin: "0px 0px -6% 0px" });
document.querySelectorAll("[data-rv]").forEach(el => ro.observe(el));

/* --------------------------------------------------------------------------
   5 · Marquee em loop infinito
   -------------------------------------------------------------------------- */
const mq = document.querySelector(".marquee__track");
if (mq) mq.appendChild(mq.firstElementChild.cloneNode(true));

/* --------------------------------------------------------------------------
   6 · Parallax leve (desktop) — fundo e cards flutuantes
   -------------------------------------------------------------------------- */
(function parallax() {
  if (reduceMotion) return;
  const items = [...document.querySelectorAll("[data-parallax]")];
  if (!items.length) return;
  let ticking = false;
  const update = () => {
    const y = window.scrollY;
    items.forEach(el => {
      const speed = parseFloat(el.dataset.parallax) || 0;
      el.style.transform = `translate3d(0, ${y * speed}px, 0)`;
    });
    ticking = false;
  };
  window.addEventListener("scroll", () => {
    if (!ticking) { requestAnimationFrame(update); ticking = true; }
  }, { passive: true });
  update();
})();

/* --------------------------------------------------------------------------
   7 · Canvas: linhas de fibra óptica vivas no hero (leve; pausa fora de cena)
   -------------------------------------------------------------------------- */
(function fiberCanvas() {
  const cv = document.getElementById("fiberCanvas");
  if (!cv || reduceMotion || window.innerWidth < 760) { cv && cv.remove(); return; }
  const ctx = cv.getContext("2d");
  const DPR = Math.min(window.devicePixelRatio || 1, 1.6);
  let W = 0, H = 0, fibers = [], running = true, raf = 0;

  function resize() {
    W = cv.clientWidth; H = cv.clientHeight;
    cv.width = W * DPR; cv.height = H * DPR;
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    build();
  }
  function build() {
    const n = 11;
    fibers = Array.from({ length: n }, (_, i) => ({
      y: (H / (n + 1)) * (i + 1),
      drop: H * (.06 + Math.random() * .18),
      amp: 12 + Math.random() * 26,
      len: .5 + Math.random() * .8,
      hue: Math.random() < .82 ? "0,163,255" : "214,178,94",
      alpha: .08 + Math.random() * .08,
      pulse: Math.random(),
      speed: .0008 + Math.random() * .0015
    }));
  }
  function wave(f, x) {
    const t = x / W;
    return f.y + t * f.drop - f.drop / 2 + Math.sin(t * Math.PI * 2 * f.len + f.pulse * Math.PI * 2) * f.amp;
  }
  function draw() {
    if (!running) return;
    ctx.clearRect(0, 0, W, H);
    for (const f of fibers) {
      f.pulse = (f.pulse + f.speed) % 1;
      ctx.beginPath();
      for (let x = 0; x <= W; x += 26) {
        const y = wave(f, x);
        x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      }
      ctx.strokeStyle = `rgba(${f.hue},${f.alpha})`;
      ctx.lineWidth = 1.2; ctx.stroke();
      const px = f.pulse * W, py = wave(f, px);
      ctx.beginPath();
      for (let x = Math.max(0, px - 90); x <= px; x += 12) {
        const y = wave(f, x);
        x <= px - 88 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      }
      ctx.strokeStyle = `rgba(${f.hue},.5)`; ctx.lineWidth = 2.1; ctx.stroke();
      const g = ctx.createRadialGradient(px, py, 0, px, py, 12);
      g.addColorStop(0, `rgba(${f.hue},.85)`); g.addColorStop(1, `rgba(${f.hue},0)`);
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(px, py, 12, 0, Math.PI * 2); ctx.fill();
    }
    raf = requestAnimationFrame(draw);
  }
  function setRunning(on) { if (on === running) return; running = on; on ? draw() : cancelAnimationFrame(raf); }
  new IntersectionObserver(([e]) => setRunning(e.isIntersecting && !document.hidden)).observe(cv);
  document.addEventListener("visibilitychange", () => setRunning(!document.hidden && cv.getBoundingClientRect().bottom > 0));
  window.addEventListener("resize", resize, { passive: true });
  resize(); draw();
})();

/* --------------------------------------------------------------------------
   8 · Ano do rodapé
   -------------------------------------------------------------------------- */
const ano = document.getElementById("anoAtual");
if (ano) ano.textContent = new Date().getFullYear();
