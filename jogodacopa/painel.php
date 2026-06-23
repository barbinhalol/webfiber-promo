<?php
/* ===========================================================
   PAINEL DE INDICAÇÕES — Copa da Indicação WebFiber
   Troque a SENHA abaixo. Acesso: .../jogodacopa/painel.php
   =========================================================== */
session_start();
$SENHA = '01webfiber01';   // << senha do dono

if(isset($_GET['sair'])){ session_destroy(); header('Location: painel.php'); exit; }
if(isset($_POST['senha'])){ if(hash_equals($SENHA, $_POST['senha'])){ $_SESSION['ok']=true; } else { $erro='Senha incorreta.'; } }

if(empty($_SESSION['ok'])){ ?>
<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Painel • Copa da Indicação</title>
<style>body{margin:0;font-family:system-ui,Segoe UI,sans-serif;background:#071a45;color:#fff;display:flex;min-height:100vh;align-items:center;justify-content:center}
.card{background:#fff;color:#0e1b33;padding:32px;border-radius:18px;width:300px;box-shadow:0 20px 60px rgba(0,0,0,.4);text-align:center}
h1{font-size:18px;margin:0 0 4px}.sub{color:#5b6b85;font-size:13px;margin-bottom:18px}
input{width:100%;padding:12px;border:2px solid #dde6f3;border-radius:10px;font-size:15px;box-sizing:border-box;margin-bottom:12px}
button{width:100%;padding:12px;border:0;border-radius:10px;background:#1565E0;color:#fff;font-weight:800;font-size:15px;cursor:pointer}
.err{color:#d12f2f;font-size:13px;margin-bottom:8px}</style></head>
<body><form class="card" method="post">
<h1>⚽ Painel da Copa</h1><div class="sub">Indicações WebFiber</div>
<?php if(!empty($erro)) echo '<div class="err">'.$erro.'</div>'; ?>
<input type="password" name="senha" placeholder="Senha" autofocus>
<button>Entrar</button></form></body></html>
<?php exit; }

require __DIR__ . '/api/db.php';
$pdo = db();

/* atualizar status de um lead */
if(isset($_POST['lead_id'], $_POST['status'])){
  $ok = ['novo','em atendimento','instalado','pago','cancelado'];
  if(in_array($_POST['status'], $ok, true)){
    $st=$pdo->prepare("UPDATE leads SET status=? WHERE id=?"); $st->execute([$_POST['status'], (int)$_POST['lead_id']]);
  }
  exit('ok');
}

/* export CSV */
if(isset($_GET['csv'])){
  header('Content-Type: text/csv; charset=utf-8');
  header('Content-Disposition: attachment; filename="leads-copa.csv"');
  echo "\xEF\xBB\xBF"; $out=fopen('php://output','w');
  fputcsv($out, ['Data','Nome','WhatsApp','Bairro','Plano','Indicado por','Status'], ';');
  $q=$pdo->query("SELECT l.*, (SELECT nome FROM indicadores i WHERE i.codigo=l.ref) ind FROM leads l ORDER BY l.id DESC");
  foreach($q as $r){ fputcsv($out, [substr($r['criado'],0,10), $r['nome'], $r['whatsapp'], $r['bairro'], $r['plano'], $r['ind'] ?: $r['ref'], $r['status']], ';'); }
  exit;
}

$tot_ind  = $pdo->query("SELECT COUNT(*) FROM indicadores")->fetchColumn();
$tot_abr  = $pdo->query("SELECT COUNT(*) FROM aberturas")->fetchColumn();
$tot_lead = $pdo->query("SELECT COUNT(*) FROM leads")->fetchColumn();
$tot_pago = $pdo->query("SELECT COUNT(*) FROM leads WHERE status='pago'")->fetchColumn();
$indicadores = $pdo->query("SELECT i.codigo,i.nome,i.whatsapp,i.criado,
  (SELECT COUNT(*) FROM aberturas a WHERE a.codigo=i.codigo) ab,
  (SELECT COUNT(*) FROM leads l WHERE l.ref=i.codigo) lc
  FROM indicadores i ORDER BY lc DESC, ab DESC, i.id DESC")->fetchAll(PDO::FETCH_ASSOC);
$leads = $pdo->query("SELECT l.*, (SELECT nome FROM indicadores i WHERE i.codigo=l.ref) ind
  FROM leads l ORDER BY l.id DESC")->fetchAll(PDO::FETCH_ASSOC);
function e($s){ return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }
$cores=['novo'=>'#1565E0','em atendimento'=>'#E0900A','instalado'=>'#7B3FF2','pago'=>'#1f9d4d','cancelado'=>'#b03030'];
?>
<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Painel • Copa da Indicação WebFiber</title>
<style>
:root{--azul:#1565E0;--esc:#071a45}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,Segoe UI,sans-serif;background:#eef2f8;color:#0e1b33}
header{background:linear-gradient(120deg,#0a2a6b,#1565E0);color:#fff;padding:16px 24px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px}
header h1{font-size:18px;margin:0;display:flex;align-items:center;gap:10px}
header a{color:#cfe0ff;text-decoration:none;font-size:13px;font-weight:700}
.wrap{max-width:1200px;margin:0 auto;padding:20px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin-bottom:22px}
.kpi{background:#fff;border-radius:14px;padding:16px 18px;box-shadow:0 4px 14px rgba(10,40,100,.06)}
.kpi b{display:block;font-size:30px;color:var(--azul)}.kpi span{color:#5b6b85;font-size:13px;font-weight:600}
h2{font-size:15px;margin:24px 0 10px;color:#26334d}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 4px 14px rgba(10,40,100,.06);font-size:14px}
th{background:#f4f7fc;text-align:left;padding:11px 12px;color:#42536f;font-size:12px;letter-spacing:.3px}
td{padding:10px 12px;border-top:1px solid #eef2f8}
tr:hover td{background:#fafcff}
.btn{display:inline-block;background:var(--azul);color:#fff;text-decoration:none;padding:8px 14px;border-radius:9px;font-weight:700;font-size:13px}
.zap{color:#1f9d4d;text-decoration:none;font-weight:700}
select.st{border:0;border-radius:20px;color:#fff;padding:5px 10px;font-weight:700;font-size:12px;cursor:pointer;-webkit-appearance:none;appearance:none}
.vazio{background:#fff;border-radius:14px;padding:34px;text-align:center;color:#7a8aa8}
.tag{font-size:11px;background:#eaf1ff;color:var(--azul);padding:2px 8px;border-radius:20px;font-weight:700}
@media(max-width:640px){.hide-m{display:none}}
</style></head>
<body>
<header>
  <h1>⚽ Painel da Copa da Indicação <span class="tag">WebFiber</span></h1>
  <div><a class="btn" href="?csv=leads" style="margin-right:10px">⬇ Exportar leads (CSV)</a><a href="?sair=1">Sair</a></div>
</header>
<div class="wrap">
  <div class="cards">
    <div class="kpi"><b><?=$tot_ind?></b><span>Indicadores no jogo</span></div>
    <div class="kpi"><b><?=$tot_abr?></b><span>Aberturas de link</span></div>
    <div class="kpi"><b><?=$tot_lead?></b><span>Leads recebidos</span></div>
    <div class="kpi"><b><?=$tot_pago?></b><span>Fecharam (pago)</span></div>
  </div>

  <h2>📋 Leads recebidos</h2>
  <?php if(!$leads): ?><div class="vazio">Ainda não chegou nenhum lead. Compartilhe os links de indicação! 🦊</div>
  <?php else: ?>
  <table><tr><th>Data</th><th>Nome</th><th>WhatsApp</th><th class="hide-m">Bairro</th><th class="hide-m">Plano</th><th>Indicado por</th><th>Status</th></tr>
  <?php foreach($leads as $l): $zap=preg_replace('/[^0-9]/','',$l['whatsapp']); if(strlen($zap)<=11) $zap='55'.$zap; ?>
    <tr>
      <td><?=e(substr($l['criado'],0,10))?></td>
      <td><b><?=e($l['nome'])?></b></td>
      <td><a class="zap" href="https://wa.me/<?=e($zap)?>" target="_blank">📲 <?=e($l['whatsapp'])?></a></td>
      <td class="hide-m"><?=e($l['bairro'])?></td>
      <td class="hide-m"><?=e($l['plano'])?></td>
      <td><?=e($l['ind'] ?: $l['ref'] ?: '—')?></td>
      <td><select class="st" data-id="<?=$l['id']?>" style="background:<?=$cores[$l['status']]??'#789'?>">
        <?php foreach(['novo','em atendimento','instalado','pago','cancelado'] as $s): ?>
          <option value="<?=$s?>" <?=$l['status']===$s?'selected':''?>><?=$s?></option>
        <?php endforeach; ?>
      </select></td>
    </tr>
  <?php endforeach; ?>
  </table>
  <?php endif; ?>

  <h2>🏆 Quem está indicando</h2>
  <?php if(!$indicadores): ?><div class="vazio">Nenhum indicador entrou no jogo ainda.</div>
  <?php else: ?>
  <table><tr><th>Nome</th><th>WhatsApp</th><th>Código</th><th>Abriram o link</th><th>Viraram lead</th></tr>
  <?php foreach($indicadores as $i): $zap=preg_replace('/[^0-9]/','',$i['whatsapp']); if($zap&&strlen($zap)<=11)$zap='55'.$zap; ?>
    <tr>
      <td><b><?=e($i['nome'])?></b></td>
      <td><?php if($zap):?><a class="zap" href="https://wa.me/<?=e($zap)?>" target="_blank">📲 <?=e($i['whatsapp'])?></a><?php else:echo '—';endif;?></td>
      <td><span class="tag"><?=e($i['codigo'])?></span></td>
      <td><b><?=$i['ab']?></b> pessoas</td>
      <td><b style="color:#1f9d4d"><?=$i['lc']?></b></td>
    </tr>
  <?php endforeach; ?>
  </table>
  <?php endif; ?>

  <p style="color:#9aa7bd;font-size:12px;margin-top:24px">Atualiza ao recarregar a página. Clique no status pra mudar. O CSV abre no Excel.</p>
</div>
<script>
document.querySelectorAll('select.st').forEach(s=>s.addEventListener('change',function(){
  const c={'novo':'#1565E0','em atendimento':'#E0900A','instalado':'#7B3FF2','pago':'#1f9d4d','cancelado':'#b03030'};
  this.style.background=c[this.value]||'#789';
  fetch('painel.php',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'lead_id='+this.dataset.id+'&status='+encodeURIComponent(this.value)});
}));
</script>
</body></html>
