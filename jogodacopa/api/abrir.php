<?php
/* Conta abertura de um link de indicação (1 por IP/dia) — retorna 1px gif */
require __DIR__ . '/db.php';
$cod = so_cod($_GET['ref'] ?? '');
if($cod !== ''){
  try {
    $pdo = db();
    $iphash = hash('sha256', ($_SERVER['REMOTE_ADDR'] ?? '') . '|' . date('Y-m-d') . '|' . $cod);
    // evita contar a mesma pessoa 2x no mesmo dia
    $ja = $pdo->prepare("SELECT 1 FROM aberturas WHERE codigo=? AND iphash=? LIMIT 1");
    $ja->execute([$cod,$iphash]);
    if(!$ja->fetchColumn()){
      $st = $pdo->prepare("INSERT INTO aberturas (codigo,iphash,criado) VALUES (?,?,?)");
      $st->execute([$cod,$iphash,date('c')]);
    }
  } catch(Exception $e){ /* silencioso */ }
}
header('Content-Type: image/gif');
header('Cache-Control: no-store');
echo base64_decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7');
