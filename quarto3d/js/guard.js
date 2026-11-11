/* Quarto 3D: se algo impedir o 3D de abrir, mostra o motivo na tela de carregamento
   (em vez de ficar "Montando o quarto…" para sempre) e oferece "Tentar de novo". */
(function () {
  'use strict';
  var semRede = false;   // se um arquivo não baixou, os erros seguintes são consequência dele: não sobrescrever o aviso
  function rodando() { return !!(window.Q && window.Q.E && window.Q.E.frames > 3); }
  function arquivo(u) { return String(u || '').split('/').pop().split('?')[0]; }
  function aviso(texto, grave) {
    if (rodando()) return;
    var msg = document.getElementById('loadMsg'), load = document.getElementById('load');
    if (!msg || !load) return;
    load.hidden = false; load.style.opacity = 1;
    msg.textContent = texto;
    if (!grave) return;
    var bar = document.querySelector('#load .bar'); if (bar) bar.hidden = true;
    if (!document.getElementById('retry')) {
      var b = document.createElement('button');
      b.type = 'button'; b.id = 'retry'; b.className = 'act'; b.textContent = 'Tentar de novo'; b.style.marginTop = '16px';
      b.addEventListener('click', function () { location.reload(); });
      msg.parentNode.appendChild(b);
    }
  }
  window.addEventListener('error', function (e) {
    var t = e.target;
    if (t && t !== window && t.tagName === 'SCRIPT') { if (!semRede) aviso('Não consegui baixar "' + arquivo(t.src) + '". Verifique a internet, ou tente outra rede, e toque em Tentar de novo.', true); semRede = true; }
    else if (!semRede && e.message && !/^ResizeObserver/.test(e.message)) aviso('Erro ao iniciar: ' + e.message + (e.filename ? ' (' + arquivo(e.filename) + ':' + e.lineno + ')' : ''), true);
  }, true);
  window.addEventListener('unhandledrejection', function (e) {
    if (!semRede) aviso('Erro ao iniciar: ' + String((e.reason && e.reason.message) || e.reason || 'desconhecido'), true);
  });
  setTimeout(function () { aviso('Ainda carregando. Em aparelhos mais lentos pode levar até 1 minuto.', false); }, 30000);
  setTimeout(function () { aviso('Está demorando demais. Feche, abra de novo no Chrome atualizado e, se continuar, mande uma captura desta tela.', true); }, 90000);
})();
