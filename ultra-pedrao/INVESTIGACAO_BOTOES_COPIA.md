# Investigação — sumiço dos botões "Copiar código Pix" / "Copiar código do boleto"

**Aberto:** 24/07/2026 · **Status:** causa **não fechada**; escopo reduzido por eliminação com prova.
**Sintoma:** até 17/07 as mensagens de fatura chegavam no celular com o botão nativo de copiar.
Hoje (24/07) o mesmo tipo de mensagem chega sem o botão. **Os dois botões sumiram juntos.**

> **Correção de um diagnóstico anterior meu.** Eu havia concluído que o botão "não tem como voltar"
> usando o limite de 20 caracteres do `COPY_CODE` (botão de cupom de *template*) como argumento.
> Isso é um erro de categoria: `COPY_CODE` (mecanismo 2) e o reconhecimento automático do app
> (mecanismo 3) são coisas diferentes, e o limite de um não diz nada sobre o outro. Também afirmei,
> sem fonte oficial, que a Meta teria desligado o recurso para favorecer o WhatsApp Pay.
> **As duas afirmações estão retiradas.** O que segue é só o que tem evidência.

Mecanismos que não podem ser confundidos:
1. Botões interativos enviados explicitamente pela API.
2. Botões `COPY_CODE` de templates oficiais.
3. Botão/ação gerado pelo **app** ao reconhecer código Pix ou linha digitável. ← é o nosso caso

---

## ETAPA 1 — Todos os caminhos de envio

Rastreado até a requisição HTTP final. **Não existe fila, worker, nem envio direto à Meta**
(`grep` por `graph.facebook|messaging_product|phone_number_id|wamid` em `src/`: zero ocorrências).

| Caminho | Arquivo/função | Endpoint | Tipo da mensagem | Payload |
|---|---|---|---|---|
| Pedrão noturno (fatura) | `brain.py` fastpath → `flowseller.py::executar_decisao` bloco `faturas` | `POST {FS_BASE}/v1/api/external/{apiId}` | texto (`SendMessageBase`) | `{externalKey, body, number}` |
| Copiloto Financeiro | `server.py::_cop_entregar` → **(antes)** `FS.responder_texto` direto | mesmo | texto | `{externalKey, body, number}` |
| Resposta comum / fastreply | `flowseller.py::executar_decisao` | mesmo | texto | `{externalKey, body, number}` |
| Planos (imagens) | `executar_decisao` → `enviar_midia` | mesmo | mídia | `+ mediaUrl` |
| Transferência | `flowseller.py::transferir` | mesmo (config transfer) | texto | `+ queueId, forceTicketToDepartment` |
| Nota interna | `flowseller.py::nota_interna` | mesmo | nota | `+ onlyNote, note` |

**Ponto único de saída HTTP: `flowseller.py::_post` (linha 16).** Todos os caminhos passam por
`_enviar` → `_post`. Nenhuma transformação do texto depois de `_assinar`; com `assinar=False`
(caso do Pix e da linha digitável) o `_assinar` nem é chamado — o `body` é a string crua.
`_registra_txt` roda **depois** do envio e trabalha numa cópia.

**Templates envolvidos: nenhum.** Não há `templateId`, `typeTemplate` nem `params` em nenhum envio.

---

## ETAPA 2 — Captura do payload real

Implementado `flowseller.py::_forense()`, chamado dentro de `_enviar` imediatamente após cada
requisição. Grava em `eventos` (tipo `envio_forense`), **sem token/JWT/apiId/cookie**:

URL (apiId mascarado) · método · content-type · chaves do payload · tipo da mensagem ·
`template` (bool) · `preview_url` · `tem_context` · **bytes** · **caracteres** · **sha256** ·
**NFC** · **CRLF/LF** · **espaços nas pontas** · **caracteres invisíveis** · **codepoints
início/fim** · `fs_id` · **wamid** (`messageId`) · `mediaType` · `sendType` · `typeTemplate` ·
`templateId` · `params` · `ack` · `channel` · `whatsappId`.

`preview_url`, `context` e `template` **não existem** na API externa da FlowSeller — ficam
registrados como `None`, documentando a ausência.

---

## ETAPA 3 — Comparação byte a byte (evidência mais forte desta investigação)

Fonte: banco de eventos de produção, `GET /admin/eventos?limite=60000` →
**10.873 eventos, de 13/07 16:09 a 24/07 15:44**. O campo `envio.sequencia[].body` guarda o
**corpo exato** de cada requisição. Extraídos **19 envios de Pix + 19 de linha digitável**.

### Payload — nosso lado

| | 14/07 (com botão) | 24/07 (sem botão) |
|---|---|---|
| Chaves do payload | `externalKey`, `body`, `number` | idênticas |
| Pix — caracteres / bytes | 171 / 171 | 171 / 171 |
| Linha — caracteres / bytes | 47 / 47 | 47 / 47 |
| Espaço no início / fim | 0 / 0 | 0 / 0 |
| CRLF | 0 | 0 |
| Caracteres invisíveis (Cf/Cc) | nenhum | nenhum |
| Normalização | NFC | NFC |
| Prefixo / sufixo / assinatura | nenhum | nenhum |
| Markdown no balão do código | nenhum | nenhum |

Verificado em **todos os 19 envios**, sem exceção. Diferença entre os códigos: apenas o hash da
transação (32 chars) e o CRC (4 chars) — 33 posições de 171. **CRC16 validado e correto nos dois**
(`9C92` e `58CF`). Linha digitável: 47 dígitos puros nos dois.

### Resposta da FlowSeller — o que ela fez com a mensagem

| campo | 14/07 20:41 | 24/07 08:57 |
|---|---|---|
| `whatsappId` (conexão) | **20** | **20** |
| `channel` | **waba** | **waba** |
| `mediaType` | **chat** | **chat** |
| `sendType` | **API** | **API** |
| `typeTemplate` / `templateId` / `params` | null | null |
| `body` armazenado | = código enviado | = código enviado |

**Idêntico nos 19 envios dos 11 dias.** Painel confirma "Atendimento por canal: **100% waba**".

### Caso natural de controle

O Pix terminado em `630458CF` foi enviado **duas vezes para o mesmo aparelho** (5521964450618):
**23/07 19:52 pelo caminho noturno** e **24/07 14:49 pelo copiloto**. Mesmo código, mesmo celular,
mesma conversa. Essas duas mensagens estão uma abaixo da outra e resolvem sozinhas Caso 3 × Caso 4:

- botão na de 23/07 e não na de 24/07 → **é o caminho** (Caso 3);
- sem botão nas duas → **não é o caminho** (Caso 4).

**Esta observação ainda não foi feita** — só é visível no aparelho.

---

## ETAPA 4 — Teste A/B · **EXECUTADO 24/07, resultado: NENHUMA variante gerou botão**

Disparado via `POST /admin/teste-botoes` para 5521964450618 (número do dono), 2 rodadas,
**28 mensagens**, todas com `enviado=true` e `erro=null`. Código Pix usado: `sha 158494abc7` —
**o mesmo** que foi entregue no dia 23/07 19:52 nessa mesma conversa.

| Variante | Conteúdo | bytes | sha256 | Botão? |
|---|---|---|---|---|
| A | Pix sozinho, como veio da Efí | 171 | `158494abc7` | **não** |
| D | Pix com descrição na mesma mensagem | 186 | `b60ce56c38` | **não** |
| E | descrição separada + Pix sozinho | 171 | `158494abc7` | **não** |
| F | Pix + quebra de linha no fim | 172 | `606d0abcd4` | **não** |
| A-boleto | 47 dígitos sozinhos | 47 | `e103e9d846` | **não** |
| D-boleto | 47 dígitos com texto junto | 65 | `3593e03f21` | **não** |
| F-boleto | 47 dígitos + quebra de linha | 48 | `bc39ce197d` | **não** |

Forense de todas: `mediaType=chat`, `sendType=API`, `typeTemplate=null`, `preview_url=null`,
NFC ok, zero CRLF, zero espaço nas pontas; os únicos invisíveis são os `U+000A` que a própria
matriz injetou nas variantes D e F.

**O que isso elimina, agora com teste controlado e não por dedução:** formatação do texto,
posição do código no balão, texto acompanhando o código, quebra de linha, e diferença entre os
caminhos de envio. Nenhum desses fatores é a causa.

**O que ainda não foi medido:** as duas observações que só existem no aparelho —
(a) a mensagem antiga de 23/07, com o **mesmo código**, ainda mostra o botão hoje?
(b) o mesmo código, enviado de um WhatsApp **pessoal** (fora da conta WABA), mostra o botão?
(a) separa "renderização em tempo de exibição" de "classificação na entrega";
(b) separa "aparelho/app" de "nossa conta WABA". Sem elas, qualquer conclusão é chute.

**Disparador criado:** `POST /admin/teste-botoes` (`server.py`), com trava — só envia para número
do allowlist do piloto ou `TESTE_BOTOES_NUM`. Cada variante vai precedida de rótulo em **mensagem
separada**, para o código chegar sozinho no balão.

| Variante | O que testa | Executável por nós |
|---|---|---|
| A | código sozinho, como veio da Efí | ✅ |
| D | código precedido de descrição na **mesma** mensagem | ✅ |
| E | descrição em mensagem separada + código sozinho | ✅ |
| F | código com quebra de linha no fim | ✅ |
| G | código sem quebra de linha (= A) | ✅ |
| A/D/F-boleto | idem com os 47 dígitos | ✅ |
| B / C (`preview_url` false/true) | — | ❌ campo não existe na API externa |
| H / I (noturno × copiloto) | — | ⚠️ deixaram de ser variantes: os caminhos foram unificados |
| J (direto pela Meta) | — | ❌ não temos credencial da Cloud API no projeto |
| K (envio manual pelo painel) | — | 🖐️ manual, no painel |

Depois do deploy:

```bash
curl -s -X POST https://pedrao.webfiberprovedorcliente.cloud/admin/teste-botoes -H "x-admin-token: 01webfiber01" -H "content-type: application/json" -d '{"numero":"5521964450618","cpf":"SEU_CPF_AQUI"}'
```

---

## ETAPA 5 — Inspeção da FlowSeller

Painel aberto e autenticado (`app.flowseller.com.br`, backend `appapi.flowseller.com.br`),
capturador de `fetch`/`XHR` instalado. **Parcial:** a leitura direta da API interna foi barrada
(CORS/token protegido) e o envio manual (variante K) não foi disparado.

Confirmado no painel: canal único **waba**, 100% dos atendimentos. Filas e motivos de fechamento
carregados do tenant 9.

**Sobre "a API só aceita `body`":** verificado no código que **nós** só mandamos
`externalKey`/`body`/`number`/`mediaUrl`/`note`/`queueId`. Que a API não aceite **mais nada** ainda
**não está provado** — falta a documentação do parceiro. Fica em aberto.

### Inspeção do bundle do painel (24/07) — três achados

1. **São DUAS APIs distintas.** `externalKey` **não aparece em nenhum** dos 9 bundles do painel.
   O painel usa a **API interna**: `POST /messages/{ticketId}` (e `/messages/{id}/resend`).
   O nosso bot usa a **API externa**: `POST /v1/api/external/{apiId}`. Caminhos diferentes dentro
   da FlowSeller — logo, "envio manual pelo painel" e "envio do bot" **não são comparáveis por
   suposição**, têm que ser testados.
2. **O painel conhece `interactive`, `buttons`, `templateId`, `typeTemplate`, `params`,
   `mentions`, `scheduleDate`, `sendType`, `mediaType`.** Ou seja, a plataforma **tem vocabulário
   de mensagem interativa**. Nada disso é expressável na API externa que usamos hoje. Isso
   fortalece a hipótese 2 (existe capacidade que não estamos usando) e é o que deve ser
   perguntado ao suporte, com nome de campo.
3. **Canal waba exige TEMPLATE para iniciar conversa.** No diálogo "Criar Atendimento", ao
   escolher o canal *WebFiber Provedor*, o painel **substitui o campo de mensagem livre por um
   seletor de Template obrigatório**. É a regra da janela de 24h da Meta. Consequência prática:
   o envio manual de texto livre (variante K) só é possível **dentro** de uma conversa com janela
   aberta — não dá para iniciar uma.

**Bloqueio da variante K:** para comparar "envio manual × envio do bot" com o mesmo código, é
preciso uma janela de 24h aberta com o número de teste (o cliente precisa ter mandado alguma
mensagem). Sem isso o painel só deixa mandar template.

**Acesso à API interna por script: bloqueado.** O ambiente protege o token de sessão do
navegador (leitura recusada) — não foi contornado, por decisão.

---

## Evidência da Meta

**Nenhuma coletada.** O projeto não fala com a Cloud API — quem fala é a FlowSeller. O `wamid`
(`messageId`) vinha `null` na resposta de criação (a mensagem nasce `pending`); com o log forense
agora instalado, ele passa a ser capturado quando disponível.

---

## Causa — hipóteses ordenadas por evidência

1. **Renderização client-side deixou de acontecer** (não é o nosso envio) — *forte, não fechada*.
   Sustentação: payload idêntico em bytes por 11 dias; mesma conexão/canal/tipo; **e a linha
   digitável, que não tem URL nenhuma, perdeu o botão junto com o Pix**. Falta: a observação do
   par 23/07 × 24/07 no aparelho.
2. **A API externa aceita um campo que não usamos** e que muda a classificação da mensagem —
   *aberta*. Cai se a leitura do bundle/documentação não achar nada.
3. **Diferença de caminho (noturno × copiloto)** — *praticamente descartada*: payload provado
   idêntico. Mesmo assim os caminhos foram unificados, para eliminar a variável.
4. **Conteúdo/formatação do código** — *descartada*: CRC válido, 171/47, NFC, sem invisíveis,
   sem espaço, sem CRLF, sem markdown, código sozinho no balão.
5. **Mudança do lado da Meta/app** — *não investigável por nós sem fonte oficial*. Só entra em
   consideração depois que a Etapa 4 fechar, e nunca como afirmação sem evidência.

---

## Correção aplicada

1. **Log forense** (`flowseller.py::_forense`) em toda requisição — a próxima ocorrência vira prova.
2. **Unificação dos caminhos** — `_cop_entregar` agora chama `FS.executar_decisao`, a mesma porta
   do noturno. Mesmo payload, mesma cadência (`delay=primeiro`), mesma nota. Adicionado `marca`
   em `executar_decisao` para o copiloto manter a assinatura `*Financeiro WebFiber*`.
   Lógica duplicada eliminada.
3. **Bug corrigido de quebra:** o copiloto **descartava** o resultado do envio e gravava
   `fatura_entregue` mesmo quando os 6 POSTs falhavam. Agora distingue erro real de simulação
   (shadow/piloto) e grava `fatura_FALHOU` com os erros.
4. **`POST /admin/teste-botoes`** — matriz A/B disparável a qualquer hora, com trava de número.

**Bateria de regressão: 145/145 (100%).**

---

## Teste final — Pix e boleto

**Pix:** 4 variantes enviadas, **0 com botão**. **Boleto:** 3 variantes enviadas, **0 com botão**.
Ambos com o código chegando isolado no balão, payload limpo e conferido no log forense.

---

## Plano B

**Ainda não acionado.** A condição ("o botão automático não pode ser reproduzido") está
**parcialmente** satisfeita: nenhuma variante nossa reproduz. Falta a medição (b) — o mesmo código
saindo de um WhatsApp **pessoal**, fora da conta WABA. Se lá o botão aparecer, o problema é da
nossa conta e tem endereço certo para cobrar; se lá também não aparecer, o recurso não está sendo
desenhado no aparelho e o Plano B vira a solução: página própria de "copia e cola" (botão + QR)
em domínio nosso.
