<?php
/* Registra indicador OU lead (POST JSON) — Copa da Indicação */
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
require __DIR__ . '/db.php';

$in = json_decode(file_get_contents('php://input'), true);
if(!is_array($in)){ http_response_code(400); echo json_encode(['erro'=>'sem dados']); exit; }

try {
  $pdo = db();
  $now = date('c');
  $tipo = $in['tipo'] ?? '';

  if($tipo === 'indicador'){
    $cod  = so_cod($in['codigo'] ?? '');
    $nome = limpa($in['nome'] ?? '');
    $zap  = so_num($in['whatsapp'] ?? '');
    if($cod === '' || $nome === ''){ http_response_code(400); echo json_encode(['erro'=>'invalido']); exit; }
    $st = $pdo->prepare("INSERT OR IGNORE INTO indicadores (codigo,nome,whatsapp,criado) VALUES (?,?,?,?)");
    $st->execute([$cod,$nome,$zap,$now]);
    echo json_encode(['ok'=>true]); exit;
  }

  if($tipo === 'envio'){
    $cod = so_cod($in['codigo'] ?? '');
    if($cod === ''){ http_response_code(400); echo json_encode(['erro'=>'invalido']); exit; }
    $pdo->prepare("UPDATE indicadores SET envios = envios + 1 WHERE codigo = ?")->execute([$cod]);
    $q = $pdo->prepare("SELECT envios FROM indicadores WHERE codigo = ?"); $q->execute([$cod]);
    echo json_encode(['ok'=>true, 'envios'=>(int)$q->fetchColumn()]); exit;
  }

  if($tipo === 'lead'){
    $ref    = so_cod($in['ref'] ?? '');
    $nome   = limpa($in['nome'] ?? '');
    $zap    = so_num($in['whatsapp'] ?? '');
    $bairro = limpa($in['bairro'] ?? '');
    $plano  = limpa($in['plano'] ?? '', 40);
    if($nome === '' || $zap === ''){ http_response_code(400); echo json_encode(['erro'=>'invalido']); exit; }
    $st = $pdo->prepare("INSERT INTO leads (ref,nome,whatsapp,bairro,plano,criado) VALUES (?,?,?,?,?,?)");
    $st->execute([$ref,$nome,$zap,$bairro,$plano,$now]);
    echo json_encode(['ok'=>true]); exit;
  }

  http_response_code(400); echo json_encode(['erro'=>'tipo invalido']);
} catch(Exception $e){
  http_response_code(500); echo json_encode(['erro'=>'falha']);
}
