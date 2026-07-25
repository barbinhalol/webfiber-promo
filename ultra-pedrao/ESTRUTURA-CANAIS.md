# ESTRUTURA DOS CANAIS — validada pelo dono em 25/07/2026 10:25 ("tá perfeito")

> ⛔ NÃO ALTERAR esta semântica sem ordem explícita do dono. Ela foi fechada depois de uma
> manhã inteira de caça a bugs ao vivo (reentrega da FlowSeller, mutes falsos, vazamento de
> trava). Cada regra abaixo tem um motivo e um teste na bateria (`auditoria/harness.py`).

## Os dois canais da FlowSeller e a chave que os controla

A FlowSeller tem dois chatbots que o dono alterna no canal "WebFiber Provedor".
O NOSSO comportamento é controlado por UMA flag do painel: **`so_copiloto`**.

| Canal na FlowSeller          | `so_copiloto` | Quem fala o quê |
|------------------------------|---------------|-----------------|
| **ATENDIMENTO + ULTRA PEDRÃO** (menu 1/2/3 + equipe humana) | **true**  | Menu do fluxo recebe saudações/conversa. **Pedrão 100% MUDO.** Só o **Copiloto Financeiro** fala: clique FINANCEIRO → frase padrão; pedido de fatura → CPF → enumera cadastros → entrega Pix+boleto assinado *Financeiro WebFiber*. |
| **Ultra Pedrão** (fluxo vazio, bot atende tudo)             | **false** | **Pedrão atende tudo** (fastpath + LLM). Copiloto continua valendo na fila 25. |

**Trocar de canal = trocar a flag.** `POST /admin/painel {"so_copiloto": true|false}` — efeito
imediato, sem deploy. Esquecer a flag ligada no canal Pedrão deixa o bot MUDO; esquecer
desligada no canal Atendimento faz o Pedrão falar em cima do menu/atendentes.

## Regras permanentes (ordem do dono)

1. **Horário NUNCA decide SE o bot responde — só O QUE ele diz.** `SO_FORA_DO_HORARIO=false`
   é definitivo. O `schedule` serve pro bot saber se tem equipe humana no local e falar de
   acordo ("a equipe já está aí" vs "falam com você sábado a partir das 9h").
2. **Clique FINANCEIRO é assunto EXCLUSIVO do copiloto** (com copiloto ligado). Se o copiloto
   não puder falar (atendente real digitou), a resposta é SILÊNCIO — nunca o Pedrão. Regra
   dura no `server.py` (`clique_financeiro_so_copiloto`).
3. **Frase padrão do clique** (intocável, existe desde 24/07 13:37):
   *"Olá! Aqui é do setor Financeiro da WebFiber 😊 Em que posso te ajudar?"*
4. **Mute de atendente é POR CONVERSA** (ticket exato). Janela por tempo só quando o webhook
   vem sem ticket_id. Atendente digitou no ticket A ≠ copiloto mudo no ticket B.
5. **Status de cobrança só sai de CONSULTA real** ao MyCore. Texto do LLM afirmando
   "não tem fatura"/"em dia"/"sem débito" é bloqueado por guard (`_STATUS_COBRANCA`).
6. **Cérebro do bot: Haiku 4.5 (dia-a-dia) + Sonnet 5 effort low (escalada). FABLE 5 NUNCA.**
7. **Sessão nova apaga o roteiro velho NO BANCO** (fin/sup/perfil/interesse). Ficha de
   identidade (nome, CPF, endereço confirmado) sobrevive. `plano_interesse` NÃO sobrevive.

## Blindagens do webhook (a FlowSeller faz isso de verdade)

- **Reentrega**: ao criar ticket novo, a FlowSeller REENTREGA mensagens antigas com ticket_id
  novo → dedup pelo **UUID da mensagem** (`_dedup_id`, janela 6h) + **mensagem com >10 min
  nunca inicia resposta** (`IGNORA_MSG_ANTIGA_S`, e `_ts_epoch` normaliza ISO/epoch/ms).
- **Eco**: nossas próprias mensagens voltam como fromMe SEM a formatação (`*`) → detector
  ignora formatação e tem fingerprints por conteúdo ("eu sou o pedrão", saudação de setor).
- **Pilot bloqueia ENVIO do copiloto também** (`_num_permitido_piloto`): em modo pilot,
  cliente fora da allowlist não recebe nem fatura. Pilot é só pra teste curto e consciente.

## Estado validado (25/07 10:25)

```
painel: ativo=true · modo=live · copiloto_financeiro=true · so_copiloto=true
.env:   LLM_MODEL=claude-haiku-4-5-20251001 · LLM_MODEL_SMART=claude-sonnet-5
        SO_FORA_DO_HORARIO=false · DEBUG_WEBHOOK=false · DEBOUNCE_SECONDS=2
canal:  ATENDIMENTO + ULTRA PEDRÃO
bateria: 355/355 (rodar SEMPRE isolada: docker run --rm --network none …)
```
