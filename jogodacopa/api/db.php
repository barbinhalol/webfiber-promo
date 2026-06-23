<?php
/* Conexão SQLite + schema — Copa da Indicação WebFiber */
function db(){
  $dir = __DIR__ . '/_dados';
  if(!is_dir($dir)) @mkdir($dir, 0700, true);
  $pdo = new PDO('sqlite:' . $dir . '/copa.sqlite');
  $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
  $pdo->exec("CREATE TABLE IF NOT EXISTS indicadores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT UNIQUE, nome TEXT, whatsapp TEXT, criado TEXT)");
  $pdo->exec("CREATE TABLE IF NOT EXISTS aberturas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT, iphash TEXT, criado TEXT)");
  $pdo->exec("CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ref TEXT, nome TEXT, whatsapp TEXT, bairro TEXT, plano TEXT,
    status TEXT DEFAULT 'novo', criado TEXT)");
  return $pdo;
}
function limpa($s,$max=60){ return mb_substr(trim((string)$s), 0, $max); }
function so_num($s,$max=15){ return substr(preg_replace('/[^0-9]/','', (string)$s), 0, $max); }
function so_cod($s,$max=40){ return substr(preg_replace('/[^a-z0-9-]/','', strtolower((string)$s)), 0, $max); }
