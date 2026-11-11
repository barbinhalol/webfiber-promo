# Agentes da skill de decoração

Estes prompts funcionaram neste projeto. Troque os caminhos e os dados do cômodo. Peça sempre **só JSON** na resposta, para você aproveitar o resultado sem reescrever. Os agentes vêem imagens com a ferramenta Read, então coloque as fotos e capturas numa pasta e passe o caminho completo de cada arquivo.

## 1. Medição pelas lajotas (agente fork, trabalha em uma pasta própria)

Use um agente `fork`: ele herda o contexto e leva um tempo longo (cerca de 30 minutos, dezenas de chamadas). Diga a ele para não mexer no código nem publicar.

> Tarefa isolada de medição. Trabalhe só em `<pasta>/measure/`.
> O usuário informou que cada lajota do porcelanato tem **80 × 80 cm**. Use as fotos reais para medir o cômodo matematicamente.
> Fotos (EXIF já aplicado, resolução cheia): `<lista, com o que cada uma mostra>`.
> Método: localize as juntas do rejunte (recorte e amplie com PIL, desenhe grade de coordenadas), atribua coordenadas inteiras de malha (múltiplos de 0,80 m), ajuste uma câmera calibrada ou homografia do piso (numpy) e projete para o piso os pontos onde móveis e paredes tocam o chão. Cruze ao menos duas fotos por medida e informe o resíduo. As lentes são ultra-wide: prefira pontos perto do centro.
> Devolva, em metros, com erro ± e a marca **medido/deduzido**: largura e comprimento (de alvenaria a alvenaria), profundidade dos armários, larguras de cada módulo ao longo de cada parede, janela e ar-condicionado (posição e tamanho), **em qual parede fica a porta** e a largura do vão, deslocamento das juntas do piso em relação às paredes, e alturas principais (pé-direito, tampo, prateleiras, base dos armários altos, peitoril), dizendo qual referência vertical usou.
> Formato: tabela curta + 3 a 5 linhas de método, fotos que sustentam cada medida e principais incertezas.

## 2. Três agentes Haiku de decoração (em paralelo, na mesma mensagem)

Contexto comum a passar: tamanho aproximado do cômodo, materiais (madeira, cor das paredes, piso), perfil do morador, e as fotos reais.

**a) Estilos prontos.** Peça exatamente 6 temas coesos e diferentes entre si, com cores de tinta realistas (cor forte só em LED, manta e detalhes). Pelo menos 2 mantendo a madeira original, 2 com armários laqueados claros, 1 inspirado na foto de referência, 1 "gamer neon" escuro. Campos de cada tema:

```json
{"temas":[{"id":"","nome":"","descricao":"","paredeJanela":"#","paredePorta":"#","teto":"#","armarios":"madeira|#hex","ledTeto":"#","ledPrateleiras":"#","colcha":"#","manta":"#","tapete":"#|null","cortina":"#|null"}]}
```

**b) Curadoria de estante e rack.** Dê a foto de referência e as medidas conhecidas (porta 80 × 210 cm, lajota 80 × 80 cm) para ele estimar tamanhos. Peça o inventário de cima para baixo e da esquerda para a direita, item a item, só com os tipos que o catálogo tem (`livros`, `boneco`, `luminaria_globo`, `lanterna`, `planta_pendente`, `tv`, `aparelho`, `controle`), posição no nicho, largura, altura e cores em hex. **Para bonecos, peça só o esquema de cores e proíba nomes de personagens ou marcas.** Peça também a iluminação (onde ficam as fitas, cor, intensidade) e 3 dicas de arrumação. Formato: `{"medidas":{...},"estante":{"topo":[],"nichos":[[]]},"rack":{"tampo":[],"nichoAberto":[]},"iluminacao":{},"dicas":[]}`.

**c) Detalhes de fidelidade.** Dê todas as fotos do cômodo vazio e a lista do que o modelo já tem, para ele não repetir. Peça até 14 detalhes reais e visíveis (interruptores, tomadas e alturas, sanca, luminária, desenho do piso, rodapé, cabos, cor exata das paredes em hex), com onde, tamanho, cor, foto de origem e confiança (alta/média/baixa). Diga "não invente: se não aparece claramente, não liste". Tratar com cautela o que vier com confiança baixa: o Haiku errou, por exemplo, o tamanho da lajota (estimou 60 cm) e a existência de um peitoril de cimento.

## 3. Dois agentes Sonnet de revisão (depois de ter capturas)

Monte um pacote em uma pasta, com nomes de arquivo que digam o que a imagem deveria mostrar:

- capturas da maquete em vários ângulos e poses (objeto recolhido e aberto, vista de quem está deitado, vista de cima, vista geral);
- a folha de miniaturas do catálogo (`scripts/thumbs.js` + `scripts/contact_sheet.py`);
- as fotos reais de referência (objeto escolhido pelo usuário, parede, quarto vazio).

**Não escreva a hipótese de erro nem o que você corrigiu.** Peça a procura de defeitos, sem elogio, e que diga "não deu para avaliar" em vez de inventar.

**a) Arquitetura:** orientação e montagem (objeto ao contrário, suporte na frente da tela, peça flutuando, atravessando parede ou móvel), alturas e folgas, uso do espaço, semelhança do suporte com o da referência.

**b) Design e fidelidade:** miniaturas (lado errado, vazia, irreconhecível, nome que não bate), objeto contra a foto real (formato, cor, material), madeira, piso, parede, qualquer erro que o cliente notaria de relance.

Formato de resposta para os dois:

```json
{"erros":[{"gravidade":"grave|medio|leve","imagem":"","o_que_esta_errado":"","como_deveria_ser":""}],
 "confirmado_correto":["..."],"nao_deu_para_avaliar":["..."]}
```

Triagem do resultado: confira cada "grave" olhando a imagem você mesmo. Corrija o que se confirmar, e registre o que decidiu não mudar e por quê (por exemplo, uma sugestão de altura que piora outro uso).
