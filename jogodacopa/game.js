/* ============================================================
   PÊNALTIS PREMIADOS — WebFiber • Copa da Indicação
   100% client-side. Pronto pra plugar no backend PHP da Hostinger.
   ============================================================ */

/* ---------- CONFIG: número comercial e base do link ---------- */
const ZAP_COMERCIAL = "5521985589201";          // WhatsApp da WebFiber
const BASE_LINK     = location.origin + location.pathname; // vira o domínio na Hostinger

/* ---------- PRÊMIOS ---------- */
const PREMIOS = {
  indicador: [
    { ic:"🔥", titulo:"Esquentou!",  premio:"R$10 de desconto", sub:"na sua próxima fatura",
      como:"Envie seu link para 5 amigos", env:5, curto:"R$10 OFF" },
    { ic:"🥅", titulo:"Na rede!",    premio:"R$30 de desconto", sub:"na sua próxima fatura",
      como:"Quando 1 amigo fechar contrato", cond:true, curto:"R$30 OFF" },
    { ic:"🏆", titulo:"GOLAÇO!",     premio:"700 → 850 Mega",   sub:"upgrade por 1 mês, na hora",
      como:"Envie para +5 contatos novos", env:10, curto:"850 Mega" },
  ],
  indicado: [
    { ic:"🎁", titulo:"Boas-vindas!", premio:"R$30 de desconto", sub:"na sua 1ª mensalidade",
      como:"Ao fechar pela indicação", cond:true, curto:"R$30 OFF" },
    { ic:"🔧", titulo:"Instalação!",  premio:"R$50 de desconto", sub:"na taxa de instalação",
      como:"No fechamento do contrato", cond:true, curto:"R$50 instalação" },
    { ic:"🚀", titulo:"Turbo!",       premio:"850 Mega por 1 mês", sub:"contratando o 700 Mega",
      como:"Indicando para +5 pessoas", env:5, curto:"850 Mega" },
  ],
};

/* ---------- ESTADO ---------- */
const params  = new URLSearchParams(location.search);
const refCode = params.get("ref");
const MODO    = refCode ? "indicado" : "indicador";
const LISTA   = PREMIOS[MODO];

const TOTAL_CHUTES = 5;   // 5 pênaltis
const META_GOLS    = 3;   // sempre 3 entram

const estado = {
  chute: 0,            // 0..4
  golsFeitos: 0,       // quantos gols já saíram (indexa o prêmio)
  sequencia: [],       // [bool x5] — true = gol; gerada por jogo
  travado: false,
  desbloqueados: [],   // índices de prêmio liberados nesta sessão
  dados: JSON.parse(localStorage.getItem("wf_penaltis") || "null"),
};

/* gera 5 resultados: 2 gols + 2 defesas embaralhados + golaço final garantido */
function embaralhar(a){ for(let i=a.length-1;i>0;i--){ const j=Math.floor(Math.random()*(i+1)); [a[i],a[j]]=[a[j],a[i]]; } return a; }
function gerarSequencia(){
  const quatro = embaralhar([true,true,false,false]); // 2 gols, 2 defesas
  return [...quatro, true];                            // 5º = sempre gol (golaço)
}

/* nome de quem indicou (decodificado do ref) */
function nomeDoRef(code){
  if(!code) return "um amigo";
  const base = code.split("-")[0] || "amigo";
  return base.charAt(0).toUpperCase() + base.slice(1);
}
const INDICADOR_NOME = nomeDoRef(refCode);
/* registra a abertura do link (pro painel contar) */
if(refCode){ try{ new Image().src = "api/abrir.php?ref=" + encodeURIComponent(refCode) + "&t=" + Date.now(); }catch(e){} }

/* ---------- ATALHOS ---------- */
const $  = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);
const tela = id => { $$(".screen").forEach(t=>t.classList.remove("active")); $("#"+id).classList.add("active"); };

/* ============================================================
   INTRO
   ============================================================ */
function montarIntro(){
  if(MODO==="indicado"){
    $("#intro-titulo").innerHTML = `<b>${INDICADOR_NOME}</b> te convocou! 🎉`;
    $("#intro-sub").innerHTML = `Bata <b>5 pênaltis</b> e libere descontos exclusivos pra ser <b>WebFiber</b>.`;
    $("#btn-comecar").querySelector("span").textContent = "QUERO MEUS DESCONTOS";
  }
  const wrap = $("#premios-preview");
  wrap.innerHTML = LISTA.map(p=>`
    <div class="pp-chip"><i>${p.ic}</i><b>${p.curto}</b><span>${p.titulo}</span></div>`).join("");
}

/* ============================================================
   JOGO
   ============================================================ */
function montarHUD(){
  $("#hud-premios").innerHTML = LISTA.map((p,i)=>`
    <div class="hud-slot" id="slot-${i}">
      <span class="check">✔</span><i>${p.ic}</i><b>${p.curto}</b>
    </div>`).join("");
}

function iniciarJogo(){
  estado.chute = 0;
  estado.golsFeitos = 0;
  estado.desbloqueados = [];
  estado.sequencia = gerarSequencia();
  montarHUD();
  tela("tela-jogo");
  if(window.WF3D){ if(!WF3D.pronto) WF3D.init(); else WF3D.onResize(); }
  ambiente(true);                // torcida de fundo
  prepararChute();
}

function prepararChute(){
  estado.travado = false;
  if(window.WF3D && WF3D.pronto){ WF3D.resetChute(); WF3D.posAlvos(); WF3D.mirar(true); }
  $("#campo").classList.add("mirar");
  $("#dica-chute").style.display = "block";
  $("#dica-chute").innerHTML = estado.chute===0
    ? `👆 Toque num <b>canto do gol</b> pra chutar — o goleiro pula pro outro lado!`
    : `👆 Chute <b>${estado.chute+1} de ${TOTAL_CHUTES}</b> — escolha o canto!`;
}

/* ============================================================
   CANVAS DA BOLA — física real (trajetória, perspectiva, rotação)
   ============================================================ */
let cv, ctx, Wc=0, Hc=0, dprC=1, rafBola=null, rotBola=0;

function setupCanvas(){
  cv = $("#bolaCanvas"); if(!cv) return;
  ctx = cv.getContext("2d");
  resizeCanvas();
}
function resizeCanvas(){
  if(!cv || !ctx) return;
  void cv.offsetWidth;                       // força reflow
  let r = cv.getBoundingClientRect();
  let w = r.width, h = r.height;
  if(w < 20 || h < 20){                       // layout ainda não computado → usa container
    const camp = $("#campo") || cv.parentElement;
    const rc = camp ? camp.getBoundingClientRect() : {width:0,height:0};
    const app = $("#app");
    w = rc.width  || (app && app.clientWidth)  || window.innerWidth  || 400;
    h = rc.height || (app && app.clientHeight) || window.innerHeight || 800;
  }
  Wc = w; Hc = h; dprC = Math.min(window.devicePixelRatio||1, 2);
  cv.width = Math.round(Wc*dprC); cv.height = Math.round(Hc*dprC);
  ctx.setTransform(dprC,0,0,dprC,0,0);
}
window.addEventListener("resize", ()=>{ if($("#tela-jogo").classList.contains("active")){ resizeCanvas(); if(!estado.travado) desenharBolaParada(); } });

/* ponto (rel. ao canvas) a partir de um elemento */
function pontoEl(el, fx, fy){
  const r = el.getBoundingClientRect(), c = cv.getBoundingClientRect();
  return { x: r.left + r.width*fx - c.left, y: r.top + r.height*fy - c.top };
}
function pontoInicio(){ return { x: Wc*0.5, y: Hc*0.905 }; }   // à frente das pernas do batedor
function pontoZona(z){ return pontoEl($$(".alvo")[z], 0.5, 0.5); }
function raioBase(){ return Math.max(12, Wc*0.049); }

/* desenho da bola (pentágono central + gomos radiais) */
function pent(cx,cy,rad){ ctx.beginPath(); for(let i=0;i<5;i++){const a=i/5*6.2832-1.5708; const px=cx+Math.cos(a)*rad, py=cy+Math.sin(a)*rad; i?ctx.lineTo(px,py):ctx.moveTo(px,py);} ctx.closePath(); ctx.fill(); }
function drawBola(x,y,r,alpha,rot){
  ctx.save(); ctx.globalAlpha=alpha; ctx.translate(x,y); ctx.rotate(rot);
  const g=ctx.createRadialGradient(-r*0.32,-r*0.36,r*0.12,0,0,r);
  g.addColorStop(0,"#ffffff"); g.addColorStop(1,"#c9d3e1");
  ctx.beginPath(); ctx.arc(0,0,r,0,6.2832); ctx.fillStyle=g; ctx.fill();
  ctx.lineWidth=Math.max(1,r*0.05); ctx.strokeStyle="#94a2b6"; ctx.stroke();
  ctx.fillStyle="#1b2740"; pent(0,0,r*0.4);
  ctx.strokeStyle="#1b2740"; ctx.lineWidth=Math.max(1,r*0.075);
  for(let i=0;i<5;i++){const a=i/5*6.2832-1.5708; ctx.beginPath(); ctx.moveTo(Math.cos(a)*r*0.38,Math.sin(a)*r*0.38); ctx.lineTo(Math.cos(a)*r*0.95,Math.sin(a)*r*0.95); ctx.stroke();}
  ctx.restore();
}
function drawSombra(x,y,r,sobe){
  ctx.save(); ctx.globalAlpha=Math.max(0.05,0.32-sobe*0.0018);
  ctx.fillStyle="#0a3a1e"; ctx.beginPath(); ctx.ellipse(x,y,r*1.55,r*0.5,0,0,6.2832); ctx.fill(); ctx.restore();
}
function desenharBolaParada(){
  if(!ctx) return;
  const i=pontoInicio(), r=raioBase();
  ctx.clearRect(0,0,Wc,Hc);
  drawSombra(i.x, i.y+r*0.55, r, 0);
  drawBola(i.x, i.y, r, 1, rotBola);
}

/* voo da bola: arco + perspectiva + rastro (animação best-effort; retorna o ponto final) */
function voarBola(zona, ehGol){
  if(rafBola) cancelAnimationFrame(rafBola);
  const ini = pontoInicio(), alvo = pontoZona(zona);
  const fim = ehGol ? alvo : { x: ini.x+(alvo.x-ini.x)*0.72, y: ini.y+(alvo.y-ini.y)*0.72 };
  const dur = 600, r0 = raioBase(), r1 = Math.max(6, Wc*0.022);
  const arcoMax = Hc*0.06*(ehGol?1:0.6);
  const trail=[]; let start=null;
  (function frame(ts){
    if(start===null) start=ts;
    let t=(ts-start)/dur; if(t>1)t=1;
    const te=1-(1-t)*(1-t);                 // easeOutQuad
    const x=ini.x+(fim.x-ini.x)*te;
    const yb=ini.y+(fim.y-ini.y)*te;
    const sobe=arcoMax*Math.sin(Math.PI*t);
    const r=r0+(r1-r0)*te;
    rotBola+=0.5;
    ctx.clearRect(0,0,Wc,Hc);
    drawSombra(x, yb+r*0.3, r, sobe);
    trail.push({x,y:yb-sobe,r}); if(trail.length>7)trail.shift();
    trail.forEach((p,i)=> drawBola(p.x,p.y,p.r*0.9,(i/trail.length)*0.25,rotBola-(trail.length-i)*0.4));
    drawBola(x, yb-sobe, r, 1, rotBola);
    if(t<1) rafBola=requestAnimationFrame(frame);
  })(0);
  return fim;
}

/* quique da bola após defesa (best-effort) */
function quiqueDefesa(de){
  if(rafBola) cancelAnimationFrame(rafBola);
  const dur=320; let start=null;
  const fimx=de.x+(de.x<Wc/2?-1:1)*Wc*0.07, fimy=de.y+Hc*0.14, r=Math.max(8,Wc*0.032);
  (function fr(ts){ if(start===null)start=ts; let t=(ts-start)/dur; if(t>1)t=1;
    const x=de.x+(fimx-de.x)*t, y=de.y+(fimy-de.y)*t - Hc*0.07*Math.sin(Math.PI*t);
    ctx.clearRect(0,0,Wc,Hc); drawSombra(x,fimy,r,0); drawBola(x,y,r,1,rotBola+=0.3);
    if(t<1) rafBola=requestAnimationFrame(fr);
  })(0);
}

function balancarRede(){
  const tw=$(".trave-wrap"); if(!tw) return;
  tw.classList.add("rede-shake"); setTimeout(()=>tw.classList.remove("rede-shake"),420);
}

function goleiroPula(ehGol, lado, baixo){
  const gole=$("#goleiro");
  if(ehGol){                                   // pula pro lado ERRADO → entra
    const errado = lado==="esq" ? (baixo?"pula-baixo-dir":"pula-dir")
                 : lado==="dir" ? (baixo?"pula-baixo-esq":"pula-esq")
                 : (Math.random()<.5?"pula-esq":"pula-dir");
    gole.classList.add(errado);
  } else {                                      // pula pro lado CERTO → defende
    const certo = lado==="esq" ? (baixo?"pula-baixo-esq":"pula-esq")
                : lado==="dir" ? (baixo?"pula-baixo-dir":"pula-dir")
                : "pula-cima";
    gole.classList.add(certo);
  }
}

/* ============================================================
   CHUTE — lógica por timers garantidos; animação é best-effort (rAF)
   ============================================================ */
function chutar(zona){
  if(estado.travado) return;
  estado.travado = true;
  $("#campo").classList.remove("mirar");
  $("#dica-chute").style.display = "none";
  if(window.WF3D && WF3D.pronto) WF3D.mirar(false);

  const ehGol = estado.sequencia[estado.chute];
  somChute();
  if(window.WF3D && WF3D.pronto) WF3D.chutar(zona, ehGol);     // anima 3D (best-effort)
  setTimeout(()=> resolverChute(zona, ehGol), 820);            // resolução GARANTIDA por timer
}

function resolverChute(zona, ehGol){
  if(ehGol){
    somGol();
    if(window.WF3D && WF3D.pronto) WF3D.comemorar();
    confete();
    const idx=estado.golsFeitos; estado.golsFeitos++;
    setTimeout(()=> revelarPremio(idx), 700);     // deixa a comemoração rolar
  } else {
    somDefesa();
    if(window.WF3D && WF3D.pronto) WF3D.reacaoDefesa();
    const frases=["🧤 DEFENDEU!","😬 NA TRAVE!","🧤 PEGOU!"];
    toastResultado(frases[Math.floor(Math.random()*frases.length)], "Quase! Próximo chute →");
    setTimeout(avancarChute, 1300);
  }
}

function avancarChute(){
  estado.chute++;
  if(estado.chute >= TOTAL_CHUTES){ montarFim(); tela("tela-fim"); }
  else prepararChute();
}

/* toast central de resultado (defesa) */
function toastResultado(tit, sub){
  const t = document.createElement("div");
  t.className = "toast-res";
  t.innerHTML = `<b>${tit}</b><span>${sub}</span>`;
  $("#campo").appendChild(t);
  setTimeout(()=> t.classList.add("show"), 20);
  setTimeout(()=>{ t.classList.remove("show"); setTimeout(()=>t.remove(), 320); }, 1050);
}

/* ============================================================
   PRÊMIO
   ============================================================ */
function revelarPremio(i){
  const p = LISTA[i];
  estado.desbloqueados.push(i);

  // acende o slot da HUD
  const slot = $("#slot-"+i);
  if(slot) slot.classList.add("on");

  $("#mp-icone").textContent = p.ic;
  $("#mp-premio").textContent = p.premio;
  $("#mp-sub").textContent = p.sub;
  $("#mp-tag").textContent = p.env ? "ENVIE PRA LIBERAR" : (p.cond ? "AO FECHAR" : "LIBERADO");
  $("#mp-tag").style.background = (p.env || p.cond) ? "#E0900A" : "#1f9d4d";
  $("#mp-como").innerHTML = (p.env ? "📲 " : p.cond ? "✅ " : "🎁 ") + p.como;

  // texto do botão depende do modo
  const btn = $("#mp-enviar").querySelector("span");
  btn.textContent = MODO==="indicado" ? "GARANTIR ESTE DESCONTO" : "ENVIAR PRA LIBERAR 👇";

  $("#mp-depois").textContent = (i<2) ? "Pular (não libera) →" : "Ver meus cupons →";
  $("#modal-premio").classList.add("show");
}

function fecharPremioEseguir(){
  $("#modal-premio").classList.remove("show");
  avancarChute();
}

/* ============================================================
   AÇÃO DO BOTÃO VERDE (enviar / garantir)
   ============================================================ */
function acaoEnviar(){
  if(MODO==="indicado"){
    $("#modal-cadastro").classList.add("show");      // por cima do prêmio (não fecha)
  } else {
    if(!estado.dados){
      $("#modal-dados").classList.add("show");        // por cima do prêmio (não fecha)
    } else {
      compartilharLink();
      fecharPremioEseguir();                          // já compartilhou → segue o jogo
    }
  }
}

/* ---------- gera/usa link do indicador ---------- */
function slug(s){ return s.trim().toLowerCase().normalize("NFD").replace(/[^a-z]/g,"").slice(0,12) || "amigo"; }
function rand(){ return Math.random().toString(36).slice(2,6); }

function salvarDados(nome, zap){
  const code = slug(nome.split(" ")[0]) + "-" + rand();
  estado.dados = { nome, zap, code, criado:new Date().toISOString() };
  localStorage.setItem("wf_penaltis", JSON.stringify(estado.dados));
  fetch("api/save.php",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({tipo:"indicador",codigo:code,nome,whatsapp:zap})}).catch(()=>{});
}

function meuLink(){
  return BASE_LINK + "?ref=" + (estado.dados ? estado.dados.code : "amigo-"+rand());
}

function compartilharLink(){
  const link = meuLink();
  const msg = `⚽ Tô na *Copa da Indicação da WebFiber*!\n`
            + `Se você quer fibra que não trava nos jogos, contrata pelo meu link e *nós dois ganhamos desconto*. 🟦\n\n`
            + `👉 ${link}\n\n`
            + `É só bater os pênaltis e garantir. 🦊`;
  if(navigator.share){
    navigator.share({title:"Copa da Indicação WebFiber", text:msg, url:link}).catch(()=>{});
  } else {
    window.open("https://wa.me/?text="+encodeURIComponent(msg), "_blank");
  }
  registrarEnvio();
}

/* ---------- contagem de envios + progresso gamificado ---------- */
function registrarEnvio(){
  if(!estado.dados) return;
  estado.dados.envios = (estado.dados.envios||0) + 1;
  localStorage.setItem("wf_penaltis", JSON.stringify(estado.dados));
  fetch("api/save.php",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({tipo:"envio",codigo:estado.dados.code})}).catch(()=>{});
  setTimeout(mostrarProgressoEnvios, 550);
}
const META_R10 = 5, META_850 = 10;   // R$10 aos 5 envios; upgrade 850 aos 10
function mostrarProgressoEnvios(){
  const n = (estado.dados && estado.dados.envios) || 0;
  const meta = n < META_R10 ? META_R10 : META_850;
  $("#prog-contador").textContent = `${Math.min(n,meta)} de ${meta}`;
  $("#prog-barra").style.width = Math.min(100, Math.round(n/meta*100)) + "%";
  if(n >= META_850){
    $("#prog-icone").textContent = "🏆";
    $("#prog-titulo").textContent = "TUDO LIBERADO! 🎉";
    $("#prog-sub").innerHTML = `Você mandou pra <b>10+ amigos</b> — <b>R$10</b> e o <b>upgrade pra 850 Mega</b> garantidos! 🚀<br>Agora é só os amigos fecharem pros <b>R$30</b>.`;
    $("#prog-btn").querySelector("span").textContent = "MANDAR PRA MAIS GENTE 💪";
    somGol();
  } else if(n >= META_R10){
    $("#prog-icone").textContent = "🎉";
    $("#prog-titulo").textContent = "R$10 GARANTIDO! 🟦";
    $("#prog-sub").innerHTML = `Mandou pra <b>5 amigos</b> — seu <b>R$10</b> tá no bolso!<br>Falta <b>${META_850-n}</b> pro <b>upgrade 700→850 Mega</b>. Bora? 🚀`;
    $("#prog-btn").querySelector("span").textContent = `MANDAR PRA MAIS (falta ${META_850-n} pro 850)`;
    somGol();
  } else {
    $("#prog-icone").textContent = "🔥";
    $("#prog-titulo").textContent = `Você já mandou pra ${n} de ${META_R10}!`;
    $("#prog-sub").innerHTML = `Falta só <b>${META_R10-n}</b> pra desbloquear seu <b>R$10 de desconto</b>. Não para agora! 🟦`;
    $("#prog-btn").querySelector("span").textContent = `ENVIAR PRA MAIS UM (falta ${META_R10-n})`;
  }
  $("#modal-progresso").classList.add("show");
}

/* ============================================================
   CADASTRO DO INDICADO → cai no comercial
   ============================================================ */
function enviarCadastro(){
  const nome   = $("#cad-nome").value.trim();
  const zap    = $("#cad-zap").value.trim();
  const bairro = $("#cad-bairro").value.trim();
  const plano  = $("#cad-plano").value;
  const ok     = $("#cad-aceite").checked;
  const erro   = $("#cad-erro");
  if(nome.length<2 || zap.length<8 || bairro.length<2){ erro.textContent="Preencha nome, WhatsApp e bairro."; return; }
  if(!ok){ erro.textContent="Marque o aceite pra continuar."; return; }
  erro.textContent="";

  fetch("api/save.php",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({tipo:"lead",ref:refCode,nome,whatsapp:zap,bairro,plano})}).catch(()=>{});

  const msg = `Olá! Vim pela *Copa da Indicação* (indicado por ${INDICADOR_NOME}). Quero garantir meus descontos 👇\n\n`
            + `*Nome:* ${nome}\n*WhatsApp:* ${zap}\n*Bairro:* ${bairro}\n*Plano:* ${plano}\n`
            + `*Indicação:* ${refCode || "-"}`;
  window.open("https://wa.me/"+ZAP_COMERCIAL+"?text="+encodeURIComponent(msg), "_blank");

  $("#modal-cadastro").classList.remove("show");
  // vira indicador também (loop viral)
  montarFim(true);
  tela("tela-fim");
}

/* ============================================================
   TELA FINAL (sacola)
   ============================================================ */
function montarFim(cadastrou=false){
  ambiente(false);              // desliga torcida de fundo
  $("#fim-titulo").textContent = MODO==="indicado" ? "Tá feito! ⚽" : "Que craque! 👏";
  const envF = (estado.dados && estado.dados.envios) || 0;
  const faltaEnvio = LISTA.some(p => p.env && envF < p.env);
  $("#fim-sub").innerHTML = MODO==="indicado"
      ? "Seus descontos ficam vinculados à indicação:"
      : (faltaEnvio
          ? "⚠️ Pra <b>LIBERAR</b> seus prêmios, você precisa <b>ENVIAR seu link</b>! 👇"
          : "Você liberou seus prêmios! 🎉 (não somem)");

  $("#sacola").innerHTML = LISTA.map((p,i)=>{
    let label, cls;
    if(p.env){                                  // precisa ENVIAR pra liberar
      if(envF >= p.env){ label='LIBERADO'; cls='lib'; }
      else { label=`FALTA ENVIAR`; cls='falta'; }
    } else if(p.cond){ label='AO FECHAR'; cls='cond'; }
    else { label='LIBERADO'; cls='lib'; }
    return `<div class="sacola-item">
      <span class="si-ic">${p.ic}</span>
      <span class="si-tx"><b>${p.premio}</b><span>${p.sub} — ${p.como.toLowerCase()}</span></span>
      <span class="si-status ${cls}">${label}</span>
    </div>`;
  }).join("");

  const acoes = $("#fim-acoes");
  if(MODO==="indicado"){
    acoes.innerHTML = `
      <button class="btn-principal btn-zap" id="fim-garantir"><span>${cadastrou?'JÁ ENVIEI — FALAR COM A EQUIPE':'GARANTIR MEUS DESCONTOS'}</span><i>📲</i></button>
      <button class="btn-principal" id="fim-indicar"><span>GANHAR MAIS: INDICAR AMIGOS</span><i>🔗</i></button>`;
    $("#fim-garantir").onclick = ()=> cadastrou
        ? window.open("https://wa.me/"+ZAP_COMERCIAL,"_blank")
        : $("#modal-cadastro").classList.add("show");
    $("#fim-indicar").onclick = ()=> { if(!estado.dados){$("#modal-dados").classList.add("show");} else compartilharLink(); };
  } else {
    const env = (estado.dados && estado.dados.envios) || 0;
    let aviso = '';
    if(estado.dados){
      if(env < META_R10) aviso = `<div class="fim-aviso">⚠️ Falta <b>${META_R10-env}</b> pra garantir seu <b>R$10</b>! Você mandou pra ${env} de ${META_R10}.</div>`;
      else if(env < META_850) aviso = `<div class="fim-aviso ok">✅ R$10 garantido! Falta <b>${META_850-env}</b> pro upgrade <b>850 Mega</b>. 🚀</div>`;
      else aviso = `<div class="fim-aviso ok">✅ Você liberou R$10 + 850 Mega! Agora rumo aos R$30! 🎉</div>`;
    }
    acoes.innerHTML = aviso + `
      <button class="btn-principal btn-zap" id="fim-enviar"><span>${env<META_R10?'ENVIAR PRA LIBERAR MEU R$10':'MANDAR PRA MAIS GENTE'}</span><i>📲</i></button>
      <button class="btn-ghost" id="fim-copiar" style="color:#9fc0ff">📋 Copiar meu link</button>`;
    $("#fim-enviar").onclick = ()=> { if(!estado.dados){$("#modal-dados").classList.add("show");} else compartilharLink(); };
    $("#fim-copiar").onclick = ()=>{
      if(!estado.dados){ $("#modal-dados").classList.add("show"); return; }
      navigator.clipboard.writeText(meuLink()).then(()=> $("#fim-copiar").textContent="✅ Link copiado!");
    };
  }
}

/* ============================================================
   SONS (Web Audio sintetizado)
   ============================================================ */
let AC;
function ac(){ AC = AC || new (window.AudioContext||window.webkitAudioContext)(); return AC; }
function beep(f,t,type="sine",g=.15,dur=.12){
  try{ const c=ac(),o=c.createOscillator(),v=c.createGain();
    o.type=type;o.frequency.value=f;o.connect(v);v.connect(c.destination);
    v.gain.setValueAtTime(g,c.currentTime+t);v.gain.exponentialRampToValueAtTime(.001,c.currentTime+t+dur);
    o.start(c.currentTime+t);o.stop(c.currentTime+t+dur);}catch(e){}
}
/* torcida = ruído filtrado com envelope (simula multidão) */
function torcida(dur=1.5, vol=0.3){
  try{ const c=ac(); const n=Math.floor(c.sampleRate*dur); const buf=c.createBuffer(1,n,c.sampleRate); const d=buf.getChannelData(0);
    for(let i=0;i<n;i++) d[i]=(Math.random()*2-1)*0.6;
    const src=c.createBufferSource(); src.buffer=buf;
    const flt=c.createBiquadFilter(); flt.type="bandpass"; flt.frequency.value=950; flt.Q.value=0.6;
    const g=c.createGain(); g.gain.setValueAtTime(0.001,c.currentTime);
    g.gain.exponentialRampToValueAtTime(vol,c.currentTime+0.18);
    g.gain.exponentialRampToValueAtTime(0.001,c.currentTime+dur);
    src.connect(flt); flt.connect(g); g.connect(c.destination); src.start(); src.stop(c.currentTime+dur);
  }catch(e){}
}
function apito(){ beep(2050,0,"square",.10,.12); beep(2050,.16,"square",.10,.22); }
function somChute(){ beep(150,0,"triangle",.25,.08); beep(85,0,"sine",.22,.12); }

/* 🔊 GOL = seu mp3 "gol do Brasil" + apito */
let golAud=null;
function tocarGolMp3(){ try{ if(!golAud){ golAud=new Audio("assets/gol-de-brasil.mp3"); golAud.volume=0.92; } golAud.currentTime=0; golAud.play().catch(()=>{}); }catch(e){} }
function somGol(){ apito(); tocarGolMp3(); }

function somDefesa(){
  beep(120,0,"sawtooth",.22,.16); beep(82,.06,"sawtooth",.2,.22);   // thud
  torcida(0.7,0.12);                                 // "ohhh" da torcida
}

/* torcida de fundo (ambiente de estádio em loop) — inspirado no sound design do pk-shootout, 100% sintetizado */
let ambSrc=null, ambGain=null;
function ambiente(on){
  try{ const c=ac();
    if(on){
      if(ambSrc) return;
      const n=Math.floor(c.sampleRate*2.2); const buf=c.createBuffer(1,n,c.sampleRate); const d=buf.getChannelData(0);
      let last=0; for(let i=0;i<n;i++){ const w=Math.random()*2-1; last=(last+0.018*w)/1.018; d[i]=last*4; }
      ambSrc=c.createBufferSource(); ambSrc.buffer=buf; ambSrc.loop=true;
      const flt=c.createBiquadFilter(); flt.type="bandpass"; flt.frequency.value=520; flt.Q.value=0.5;
      ambGain=c.createGain(); ambGain.gain.value=0.0001; ambGain.gain.linearRampToValueAtTime(0.06,c.currentTime+0.9);
      ambSrc.connect(flt); flt.connect(ambGain); ambGain.connect(c.destination); ambSrc.start();
    } else if(ambSrc){
      try{ ambGain && ambGain.gain.linearRampToValueAtTime(0.0001,c.currentTime+0.4); const s=ambSrc; setTimeout(()=>{try{s.stop()}catch(e){}},450); }catch(e){}
      ambSrc=null;
    }
  }catch(e){}
}

/* ============================================================
   CONFETE
   ============================================================ */
function confete(){
  const cf=$("#confete"); cf.classList.add("on");
  const cx=cf.getContext("2d"); cf.width=innerWidth; cf.height=innerHeight;
  const cores=["#FFC400","#1565E0","#7B3FF2","#43d854","#fff"];
  let ps=Array.from({length:90},()=>({x:innerWidth/2,y:innerHeight*.35,
    vx:(Math.random()-.5)*11,vy:Math.random()*-13-4,
    s:Math.random()*7+4,c:cores[Math.floor(Math.random()*cores.length)],
    rot:Math.random()*6,vr:(Math.random()-.5)*.3,life:1}));
  let t=0;
  (function loop(){
    cx.clearRect(0,0,cf.width,cf.height); t++;
    ps.forEach(p=>{p.vy+=.4;p.x+=p.vx;p.y+=p.vy;p.rot+=p.vr;p.life-=.012;
      cx.save();cx.globalAlpha=Math.max(p.life,0);cx.translate(p.x,p.y);cx.rotate(p.rot);
      cx.fillStyle=p.c;cx.fillRect(-p.s/2,-p.s/2,p.s,p.s*.6);cx.restore();});
    if(t<120) requestAnimationFrame(loop); else cf.classList.remove("on");
  })();
}

/* ============================================================
   LIGAÇÕES (eventos)
   ============================================================ */
$("#btn-comecar").onclick = ()=>{ ac(); iniciarJogo(); };
$$(".alvo").forEach(a=> a.addEventListener("click",()=> chutar(+a.dataset.zona)) );
$("#mp-enviar").onclick = acaoEnviar;
$("#mp-depois").onclick = fecharPremioEseguir;
$("#cad-enviar").onclick = enviarCadastro;
$("#prog-btn").onclick = ()=>{ $("#modal-progresso").classList.remove("show"); compartilharLink(); };
$("#prog-fechar").onclick = ()=> $("#modal-progresso").classList.remove("show");
$("#md-confirmar").onclick = ()=>{
  const nome=$("#in-nome").value.trim(), zap=$("#in-zap").value.trim(), ok=$("#in-aceite").checked;
  const erro=$("#md-erro");
  if(nome.length<2){ erro.textContent="Digite seu nome."; return; }
  if(zap.length<8){ erro.textContent="Digite um WhatsApp válido."; return; }
  if(!ok){ erro.textContent="Marque o aceite pra continuar."; return; }
  erro.textContent="";
  salvarDados(nome, zap);
  $("#modal-dados").classList.remove("show");
  compartilharLink();
  if($("#modal-premio").classList.contains("show")) fecharPremioEseguir();   // segue o jogo
};

/* fechar modal tocando fora do card — o prêmio AVANÇA o jogo (não trava!) */
$$(".modal").forEach(m=> m.addEventListener("click", e=>{ if(e.target===m){
  if(m.id==="modal-premio"){ fecharPremioEseguir(); }
  else { m.classList.remove("show"); }
}}));

/* ---------- start ---------- */
montarIntro();

/* ---------- DEBUG p/ screenshots: ?ver=jogo|chute|premio|fim (&zona=0..4) ---------- */
const ver = params.get("ver");
if(ver){
  const zona = +(params.get("zona")||1);
  const start = ()=>{
    if(ver==="jogo"){ iniciarJogo(); }
    if(ver==="chute"){ estado.sequencia=[true,true,true,true,true]; iniciarJogo(); estado.sequencia=[true,true,true,true,true]; setTimeout(()=> chutar(zona), 500); }
    if(ver==="premio"){ iniciarJogo(); setTimeout(()=>{ estado.chute=0; revelarPremio(0); }, 250); }
    if(ver==="prog"){ estado.dados={nome:'Bruno',zap:'21999990000',code:'bruno-x1',envios:+(params.get('n')||2)}; tela('tela-fim'); setTimeout(mostrarProgressoEnvios,150); }
    if(ver==="fim"){ iniciarJogo(); estado.desbloqueados=[0,1,2]; const e=params.get('env'); if(e) estado.dados={nome:'B',zap:'21',code:'b-1',envios:+e}; LISTA.forEach((_,i)=>{const s=$("#slot-"+i); if(s)s.classList.add("on");}); montarFim(); tela("tela-fim"); }
  };
  let tries=0; (function wait(){ if(window.WF3D || tries++>60) start(); else setTimeout(wait,40); })();
}
