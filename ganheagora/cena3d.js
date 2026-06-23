/* ============================================================
   CENA 3D — Pênaltis Premiados WebFiber (Three.js)
   Expõe window.WF3D — o game.js (clássico) controla a lógica.
   ============================================================ */
import * as THREE from 'three';

const ZONAS = [   // pontos no plano do gol (x,y); z fixo do gol
  {x:-3.0, y:2.7}, {x:0, y:3.0}, {x:3.0, y:2.7},
  {x:-2.6, y:0.9}, {x:2.6, y:0.9}
];
const GOLZ = -14, GW = 9, GH = 3.4;
const BOLA_REPOUSO = new THREE.Vector3(0, 0.42, -0.4);

let renderer, scene, camera, bola, goleiro, batedor, aneis=[], sol;
let updaters = new Set(), rafId=null, baseCamPos;

function M(c,r=0.78){ return new THREE.MeshStandardMaterial({color:c, roughness:r}); }

/* ---------- texturas canvas ---------- */
function texGramado(){
  const c=document.createElement('canvas'); c.width=512;c.height=512; const x=c.getContext('2d');
  for(let i=0;i<8;i++){ x.fillStyle=i%2?'#2f9f4c':'#34b257'; x.fillRect(0,i*64,512,64); }
  x.strokeStyle='rgba(255,255,255,.5)'; x.lineWidth=4; x.strokeRect(40,40,432,432);
  x.beginPath(); x.arc(256,40,70,0,Math.PI); x.stroke();
  const t=new THREE.CanvasTexture(c); t.colorSpace=THREE.SRGBColorSpace; return t;
}
function texRede(){
  const c=document.createElement('canvas'); c.width=128;c.height=128; const x=c.getContext('2d');
  x.strokeStyle='rgba(255,255,255,.55)'; x.lineWidth=2;
  for(let i=0;i<=128;i+=12){ x.beginPath();x.moveTo(i,0);x.lineTo(i,128);x.moveTo(0,i);x.lineTo(128,i);x.stroke(); }
  const t=new THREE.CanvasTexture(c); t.wrapS=t.wrapT=THREE.RepeatWrapping; t.repeat.set(8,3); return t;
}
function texBola(){
  const c=document.createElement('canvas'); c.width=256;c.height=256; const x=c.getContext('2d');
  x.fillStyle='#fff'; x.fillRect(0,0,256,256); x.fillStyle='#1b2740';
  const pent=(cx,cy,r,rot)=>{ x.beginPath(); for(let i=0;i<5;i++){const a=rot+i/5*6.283-1.57;const px=cx+Math.cos(a)*r,py=cy+Math.sin(a)*r;i?x.lineTo(px,py):x.moveTo(px,py);} x.closePath(); x.fill(); };
  pent(128,128,34,0); [[128,40],[40,150],[216,150],[80,235],[176,235]].forEach(p=>pent(p[0],p[1],19,0.6));
  return new THREE.CanvasTexture(c);
}

/* ---------- boneco fofo animável ---------- */
function criarBoneco(opt){
  const g=new THREE.Group();
  // tronco — cápsula vertical (atlético, não "bola")
  const corpo=new THREE.Mesh(new THREE.CapsuleGeometry(0.4,0.52,10,18), M(opt.camisa));
  corpo.scale.set(1.06,1,0.66); corpo.position.y=1.4; corpo.castShadow=true; g.add(corpo);
  // quadril/short
  const short=new THREE.Mesh(new THREE.CapsuleGeometry(0.35,0.1,8,14), M(opt.short||opt.perna));
  short.scale.set(1.06,1,0.72); short.position.y=0.98; short.castShadow=true; g.add(short);
  // gola
  const gola=new THREE.Mesh(new THREE.TorusGeometry(0.19,0.05,12,24), M(opt.detalhe||opt.camisa));
  gola.position.y=1.82; gola.rotation.x=Math.PI/2; g.add(gola);
  // cabeça (proporcional)
  const cabeca=new THREE.Mesh(new THREE.SphereGeometry(0.36,28,28), M(0xe9b78c,0.85));
  cabeca.position.y=2.14; cabeca.castShadow=true; g.add(cabeca);
  const cabelo=new THREE.Mesh(new THREE.SphereGeometry(0.38,24,24,0,6.283,0,Math.PI*0.55), M(0x2a1c12,0.9));
  cabelo.position.y=2.18; g.add(cabelo);
  // rosto (frente = +z local)
  [-0.14,0.14].forEach(x=>{ const e=new THREE.Mesh(new THREE.SphereGeometry(0.05,12,12), M(0x201810,0.3)); e.position.set(x,2.16,0.3); g.add(e); });
  const boca=new THREE.Mesh(new THREE.TorusGeometry(0.085,0.022,8,16,Math.PI), M(0x6a3326,0.5));
  boca.position.set(0,2.03,0.32); boca.rotation.z=Math.PI; g.add(boca);
  // pernas (mais longas) — apoio + chute pivotadas no quadril
  function fazPerna(px){
    const grp=new THREE.Group(); grp.position.set(px,0.98,0);
    const coxa=new THREE.Mesh(new THREE.CapsuleGeometry(0.145,0.62,6,12), M(opt.perna)); coxa.position.y=-0.44; coxa.castShadow=true; grp.add(coxa);
    const meia=new THREE.Mesh(new THREE.CapsuleGeometry(0.15,0.2,4,10), M(0xeef2f8)); meia.position.y=-0.84; grp.add(meia);
    const pe=new THREE.Mesh(new THREE.BoxGeometry(0.25,0.16,0.46), M(0x15151c,0.4)); pe.position.set(0,-0.96,0.13); pe.castShadow=true; grp.add(pe);
    return grp;
  }
  const apoio=fazPerna(-0.2); g.add(apoio);
  const chute=fazPerna(0.2); g.add(chute);
  // braços (finos) pivotados no ombro
  function braco(sx){
    const b=new THREE.Group(); b.position.set(sx*0.48,1.66,0);
    const u=new THREE.Mesh(new THREE.CapsuleGeometry(0.115,0.52,6,12), M(opt.braco||opt.camisa)); u.position.y=-0.3; u.castShadow=true; b.add(u);
    const mao=new THREE.Mesh(new THREE.SphereGeometry(opt.luva?0.18:0.13,16,16), M(opt.luva||0xe9b78c)); mao.position.y=-0.6; mao.castShadow=true; b.add(mao);
    b.rotation.z = sx>0?-0.16:0.16;
    return b;
  }
  const bE=braco(-1), bD=braco(1); g.add(bE); g.add(bD);
  // número nas costas
  if(opt.numero){
    const c=document.createElement('canvas'); c.width=128;c.height=128; const x=c.getContext('2d');
    x.fillStyle='#009C3B'; x.font='bold 104px Arial,sans-serif'; x.textAlign='center'; x.textBaseline='middle'; x.fillText(opt.numero,64,72);
    const num=new THREE.Mesh(new THREE.PlaneGeometry(0.46,0.46), new THREE.MeshStandardMaterial({map:new THREE.CanvasTexture(c), transparent:true}));
    num.position.set(0,1.5,-0.46); num.rotation.y=Math.PI; g.add(num);
  }
  g.userData = { chute, apoio, bracoEsq:bE, bracoDir:bD, corpo, cabeca, repousoBraco:{e:0.16, d:-0.16} };
  return g;
}

/* ---------- tween simples (best-effort, baseado no loop) ---------- */
function anima(dur, onUpdate, onDone){
  let start=null;
  const u=(t)=>{ if(start===null)start=t; let k=(t-start)/dur; if(k>1)k=1; onUpdate(k); if(k>=1){ updaters.delete(u); onDone&&onDone(); } };
  updaters.add(u);
}
const easeOut = k=>1-(1-k)*(1-k);
const easeIn  = k=>k*k;

/* ---------- API ---------- */
window.WF3D = {
  pronto:false,

  init(){
    const canvas = document.getElementById('c3d'); if(!canvas) return;
    try{ renderer = new THREE.WebGLRenderer({canvas, antialias:true}); }
    catch(e){ console.warn('WebGL indisponível, jogo segue sem 3D', e); this.pronto=false; return; }
    renderer.setPixelRatio(Math.min(devicePixelRatio,2));
    renderer.shadowMap.enabled=true; renderer.shadowMap.type=THREE.PCFSoftShadowMap;
    renderer.outputColorSpace=THREE.SRGBColorSpace;
    scene=new THREE.Scene(); scene.background=new THREE.Color(0x4ea0ff);
    scene.fog=new THREE.Fog(0x9fd0ff,24,48);
    camera=new THREE.PerspectiveCamera(46,1,0.1,200);

    scene.add(new THREE.HemisphereLight(0xcfeaff,0x4a7a3a,0.95));
    sol=new THREE.DirectionalLight(0xfff4e0,1.5); sol.position.set(6,12,6); sol.castShadow=true;
    sol.shadow.mapSize.set(2048,2048); sol.shadow.camera.near=1; sol.shadow.camera.far=40;
    sol.shadow.camera.left=-14; sol.shadow.camera.right=14; sol.shadow.camera.top=14; sol.shadow.camera.bottom=-14; sol.shadow.bias=-0.0004;
    scene.add(sol);
    const fill=new THREE.DirectionalLight(0xbcd8ff,0.5); fill.position.set(-6,5,4); scene.add(fill);

    const gramado=new THREE.Mesh(new THREE.PlaneGeometry(60,60), new THREE.MeshStandardMaterial({map:texGramado(),roughness:1}));
    gramado.rotation.x=-Math.PI/2; gramado.receiveShadow=true; scene.add(gramado);

    const branco=new THREE.MeshStandardMaterial({color:0xffffff,roughness:.5,metalness:.05});
    const mkP=(x,w,h,d,y)=>{ const m=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),branco); m.position.set(x,y,GOLZ); m.castShadow=true; scene.add(m); };
    mkP(-GW/2,0.22,GH,0.22,GH/2); mkP(GW/2,0.22,GH,0.22,GH/2);
    const trav=new THREE.Mesh(new THREE.BoxGeometry(GW+0.22,0.22,0.22),branco); trav.position.set(0,GH,GOLZ); trav.castShadow=true; scene.add(trav);
    const redeMat=new THREE.MeshStandardMaterial({map:texRede(),transparent:true,opacity:.5,side:THREE.DoubleSide,depthWrite:false});
    const rf=new THREE.Mesh(new THREE.PlaneGeometry(GW,GH),redeMat); rf.position.set(0,GH/2,GOLZ-1.4); scene.add(rf);
    const rt=new THREE.Mesh(new THREE.PlaneGeometry(GW,1.4),redeMat); rt.rotation.x=-Math.PI/2; rt.position.set(0,GH,GOLZ-0.7); scene.add(rt);
    this._rede = rf;

    bola=new THREE.Mesh(new THREE.SphereGeometry(0.42,32,32), new THREE.MeshStandardMaterial({map:texBola(),roughness:.35}));
    bola.castShadow=true; bola.position.copy(BOLA_REPOUSO); scene.add(bola);

    goleiro=criarBoneco({camisa:0x1c3f73,detalhe:0x0e2547,perna:0x12233f,short:0x06122c,braco:0x1c3f73,luva:0xff7a1a});
    goleiro.position.set(0,0,GOLZ+0.6); scene.add(goleiro);
    goleiro.userData.bracoEsq.rotation.z=0.7; goleiro.userData.bracoDir.rotation.z=-0.7;

    batedor=criarBoneco({camisa:0xFFDD00,detalhe:0x009C3B,perna:0xe9b78c,short:0x002776,braco:0xFFDD00,numero:'9'});
    batedor.position.set(0,0,3.6); batedor.rotation.y=Math.PI; batedor.scale.setScalar(0.92); scene.add(batedor);

    // (mira agora é feita pelos anéis CSS sobre o gol — estilo 2D)

    this.onResize();
    addEventListener('resize',()=>this.onResize());
    baseCamPos = camera.position.clone();
    // loop
    const loop=(t)=>{ updaters.forEach(u=>{ try{ u(t); }catch(e){ updaters.delete(u); } }); try{ renderer.render(scene,camera); }catch(e){} rafId=requestAnimationFrame(loop); };
    rafId=requestAnimationFrame(loop);
    this.pronto=true;
  },

  onResize(){
    const cv=document.getElementById('c3d'); if(!cv) return;
    const w=cv.clientWidth||cv.parentElement.clientWidth||innerWidth;
    const h=cv.clientHeight||cv.parentElement.clientHeight||innerHeight;
    renderer.setSize(w,h,false);
    const portrait=h>w;
    camera.position.set(0,portrait?5.6:4.6,portrait?9.4:8);
    camera.lookAt(0,0.6,-5.5); camera.aspect=w/h; camera.updateProjectionMatrix();
    baseCamPos=camera.position.clone();
    this.posAlvos();
  },

  // projeta as zonas 3D → % de tela e posiciona os botões .alvo
  posAlvos(){
    const cv=document.getElementById('c3d'); if(!cv||!camera) return;
    const r=cv.getBoundingClientRect();
    document.querySelectorAll('.alvo').forEach((btn,i)=>{
      const z=ZONAS[i]; const v=new THREE.Vector3(z.x,z.y,GOLZ).project(camera);
      btn.style.left=((v.x*0.5+0.5)*100)+'%';
      btn.style.top=((-v.y*0.5+0.5)*100)+'%';
    });
  },

  mirar(on){
    aneis.forEach(a=>{ a.material.opacity = on?0.9:0; });
    if(on){ let ph=0; const u=(t)=>{ if(!aneis[0]||aneis[0].material.opacity<0.05){updaters.delete(u);return;} ph+=0.08; aneis.forEach(a=>a.scale.setScalar(1+Math.sin(ph)*0.12)); }; updaters.add(u); }
  },

  resetChute(){
    bola.position.copy(BOLA_REPOUSO); bola.rotation.set(0,0,0);
    goleiro.position.set(0,0,GOLZ+0.6); goleiro.rotation.set(0,0,0);
    goleiro.userData.bracoEsq.rotation.z=0.7; goleiro.userData.bracoDir.rotation.z=-0.7;
    batedor.position.set(0,0,3.6); batedor.rotation.set(0,Math.PI,0);
    batedor.userData.chute.rotation.x=0;
    batedor.userData.bracoEsq.rotation.set(0,0,0.16); batedor.userData.bracoDir.rotation.set(0,0,-0.16);
  },

  // anima o chute (visual). NÃO resolve — o game.js resolve por timer.
  chutar(zona, ehGol){
    const z=ZONAS[zona]||ZONAS[1];
    const alvo=new THREE.Vector3(z.x,z.y,GOLZ+0.4);
    const fim = ehGol ? alvo : new THREE.Vector3().copy(BOLA_REPOUSO).lerp(alvo,0.7);
    const ini=BOLA_REPOUSO.clone();
    const ch=batedor.userData.chute;
    // windup
    anima(160, k=>{ ch.rotation.x = 0.5*easeOut(k); }, ()=>{
      // kick
      anima(120, k=>{ ch.rotation.x = 0.5 - 1.2*easeOut(k); });
      // voo da bola
      const arco = ehGol?1.4:1.0;
      anima(600, k=>{
        const e=easeOut(k);
        bola.position.lerpVectors(ini,fim,e);
        bola.position.y += arco*Math.sin(Math.PI*k);
        bola.rotation.x -= 0.35; bola.rotation.z -= 0.12;
      });
      // goleiro reage
      setTimeout(()=>this._pulaGoleiro(zona,ehGol), 80);
    });
  },

  _pulaGoleiro(zona,ehGol){
    const lado=(zona===0||zona===3)?-1:(zona===2||zona===4)?1:0;
    const baixo=(zona>=3);
    // gol → pula errado; defesa → pula certo
    const dir = ehGol ? -lado : lado;
    const destX = dir*2.6, destY = baixo?0.2:(lado===0?0.4:0.9), tilt = -dir*0.7;
    const ini={x:goleiro.position.x,y:goleiro.position.y,z:goleiro.position.z};
    anima(300, k=>{
      const e=easeOut(k);
      goleiro.position.x = ini.x + (destX-ini.x)*e;
      goleiro.position.y = ini.y + (destY-ini.y)*e + (lado===0?0:Math.sin(Math.PI*k)*0.5);
      goleiro.rotation.z = tilt*e;
    });
  },

  // comemoração do gol: batedor pula + braços ao alto, rede balança, câmera treme
  comemorar(){
    const b=batedor.userData;
    anima(170, k=>{ b.bracoEsq.rotation.z=0.16+ (2.5-0.16)*k; b.bracoDir.rotation.z=-0.16-(2.5-0.16)*k; });
    let jumps=0;
    const pular=()=>{ if(jumps++>=3) return; anima(260, k=>{ batedor.position.y=Math.sin(Math.PI*k)*0.6; }, pular); };
    pular();
    // rede treme
    if(this._rede){ let ph=0; const u=(t)=>{ ph+=0.5; this._rede.position.z=GOLZ-1.4 - Math.max(0,Math.sin(ph))*0.25; if(ph>6){this._rede.position.z=GOLZ-1.4; updaters.delete(u);} }; updaters.add(u); }
    this.tremor(0.45,420);
  },

  reacaoDefesa(){
    // goleiro abraça a bola: já pulou pro lado; pequeno "segura"
    this.tremor(0.18,260);
  },

  tremor(intens,dur){
    if(!baseCamPos) return;
    anima(dur, k=>{
      const d=(1-k)*intens;
      camera.position.set(baseCamPos.x+(Math.random()-0.5)*d, baseCamPos.y+(Math.random()-0.5)*d, baseCamPos.z);
    }, ()=>camera.position.copy(baseCamPos));
  }
};
