# Erros já cometidos neste projeto (e como foram pegos)

Leia antes de mexer em algo parecido. Cada item vale uma conferência específica.

| O que deu errado | Como foi pego | Como evitar |
|---|---|---|
| **TV no suporte com o braço na frente da tela** ao "virar para a cama": eu deslocava a TV para o lado da janela e a girava de volta, deixando a placa entre a pessoa e a tela | O usuário viu na miniatura do link | Cinemática como função pura + teste de força bruta (341 mil poses). Regra: placa e braços sempre atrás do painel; controles manuais também obedecem |
| **Posição da TV em cima da cabeça de quem está deitado** | O usuário desenhou na captura onde queria | A placa do suporte fica colada na janela; recolhida, a TV fica ao lado, com o braço esticado atrás. Quando o usuário marca na imagem, mover exatamente ali |
| **Porta na parede errada** | A medição pelas lajotas mostrou que o vão ficava na parede da bancada, não na parede branca | Medir antes de modelar; perguntar/verificar em qual parede fica cada abertura |
| **Tapete redondo com a face de cima invertida** (só a borda aparecia) | Revisor de design, na folha de miniaturas | Olhar a folha de miniaturas de todo o catálogo a cada mudança de geometria |
| **Miniatura da TV articulada sem o suporte** | Revisor de design | Dar ao objeto uma pose própria para a miniatura (`thumbPose`) e uma direção de câmera (`thumbDir`) |
| **Cadeira parecendo caveira**: aberturas pequenas e simétricas, almofada de cabeça preta separada | Revisor de design comparando com a foto | Comparar contra a foto real de perfil e de costas; abrir mais a casca, tela preta lisa, sem ruído |
| **Arranjo salvo no navegador ignorava as novas medidas** | Teste de migração com estado antigo | Trocar a chave de armazenamento ou migrar (`tvRev`), e testar recarregando com estado antigo |
| **Toque rápido para girar a vista movia o objeto** | Teste de toque no celular emulado | Toque longo (240 ms) para pegar o objeto; decidir pelo relógio do evento, não do temporizador |
| **Lâmpada de teto estourando o forro** | Captura com exposição estourada | Limitar a emissão da luminária para baixo e compensar a exposição dos emissivos |
| **Cabo e peças da janela aparecendo atrás da parede na maquete** | Captura da vista geral | Malhas separadas por material para poder escondê-las quando a câmera está atrás da parede |
| **Página parada em "Montando o quarto…" sem explicar nada** quando a CDN não baixa ou o aparelho não suporta o 3D; o usuário só disse "não abre" | Mensagem do usuário, sem como diagnosticar | `quarto3d/js/guard.js` mostra o motivo na tela (arquivo que não baixou, erro de código, sem WebGL, demora) e oferece "Tentar de novo". Teste simulando as falhas: rota abortada na CDN, sem WebGL, relógio acelerado |
| **Haiku estimando lajota de 60 cm** | Medição com fork deu 80 cm, conforme o usuário disse | A informação do usuário (80 cm) é dado, não estimativa; dar a medida ao agente |

## Do que o usuário gostou (manter)

- Passeio em primeira pessoa em tela cheia, com controle redondo para andar.
- Arrastar com toque longo, marcador de onde o objeto vai pousar, ajuste fino de 1 cm.
- Cenas de luz (acesa, neon, dia) e estilos prontos de um toque.
- Vista "Deitado na cama" e botão "Virar para a cama" na TV.
- Tudo removível, com desfazer.
