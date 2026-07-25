# Vistoria completa — Ultra Pedrão (madrugada 24→25/07)

**Tudo já está NO AR.** Deploy feito por mim via terminal, container saudável, bateria **220/220**.
Você não precisa colar nada. Este documento é só pra você conferir o que mudou.

---

## 🚨 1. O ERRO QUE VOCÊ PEGOU AO VIVO (22:16) — resolvido

**O que o cliente viu:** dois balões vermelhos "Erro / Tentar novamente" e duas notas amarelas
"[Pedrão] transferência automática — JSON inválido do modelo".

**O que aconteceu, comprovado no banco de produção:**

1. O modelo escreveu uma resposta longa e bateu no teto de tokens → o JSON veio **cortado no meio**.
2. O leitor de JSON era estrito: não entendeu o texto cortado e devolveu "nada".
3. Sem resposta, o sistema caiu no plano B: **transferir o ticket** — com o texto **vazio**.
4. A FlowSeller gravou a mensagem com corpo `""` (achei o registro exato) e o WhatsApp recusou.

**As cinco correções, do sintoma até a causa:**

| # | Correção |
|---|---|
| 1 | **Trava anti-balão-vazio**: mensagem de texto sem conteúdo nunca mais sai. Foto com legenda vazia e nota interna continuam passando normalmente. |
| 2 | **Transferência sem texto** agora manda uma frase de verdade, com o dia certo em que a equipe volta — nunca um balão vazio. |
| 3 | **Leitor de JSON tolerante**: se vier cortado, ele repara; se não der, resgata a resposta por partes. Testado com o caso real — recupera. |
| 4 | **Teto de tokens 1024 → 2000** e o modelo agora já começa a resposta no formato certo (não escreve conversa antes do JSON). |
| 5 | **Falha de rede não vira mais transferência**: tenta de novo uma vez, rápido, antes de desistir. |

---

## 🧠 2. O BUG DA "LUZ VERMELHA" TINHA 4 PORTAS — não uma

Ontem eu corrigi **uma**. Uma auditoria dedicada rodou as regras contra frases reais de cliente e
mostrou que o mesmo estrago continuava acontecendo por outros caminhos:

| O cliente escrevia | O que o bot respondia (errado) |
|---|---|
| "a luz tá **piscando**" | "Essa **luz vermelha**… Problema: sem sinal" |
| "a luz **não está vermelha**, tá verde" | idem — ignorava o "não" |
| "o aparelho tá **sem luz nenhuma**" | idem |
| "**voltou mas** tá muito lenta ainda" | "**Que ótimo que voltou!**" e encerrava o caso |
| "voltou mas **caiu de novo**" | idem — e essa é justamente a queda intermitente, que é prioridade |

Agora: só fecha com o diagnóstico de fibra quem **disse** vermelha/LOSS, sem negação. Quem relatou
outro sinal, ou "voltou mas...", ou "não tô em casa", vai para conversa de verdade.

E o fechamento **pergunta em vez de cravar**: "só confere se anotei certo" — com as palavras do
cliente, o dia real em que a equipe volta, e sem o 💙 (que a própria regra 8 proibia — o código
estava quebrando a própria regra).

---

## 💸 3. DOIS CASOS QUE GERAVAM FÚRIA E PROCON

**Boleto para quem acabou de dizer que pagou.** Estas frases pediam CPF e entregavam a fatura **em
aberto**:
- "eu já paguei essa fatura e vocês cortaram minha internet"
- "meu nome foi negativado por vocês"
- "estão me cobrando um valor que não reconheço"
- "queria um desconto"

Agora vão para o Financeiro humano (é o que a regra 6 já mandava). **Pedido limpo de 2ª via
continua sendo atendido na hora** — testei.

**Tabela de planos para cliente de anos.** "Contratei 700 mega e o teste dá só 180" recebia os
planos + pedido de endereço "pra verificar viabilidade". Agora é tratado como reclamação técnica.

---

## 🧩 4. O QUE MAIS FOI CORRIGIDO NA INTELIGÊNCIA

- **Manda reiniciar quem já reiniciou** — o atalho recebia o histórico da conversa e **nunca lia**.
  Agora lê: quem disse "já reiniciei 3 vezes" (mesmo 3 mensagens atrás) não ouve isso de novo.
- **Rompimento em massa** — com o aviso ligado no painel, o atalho ignorava e mandava dezenas de
  clientes tirarem o roteador da tomada. Agora respeita o aviso.
- **Pediu atendente humano** — sai do roteiro na hora, sem insistir.
- **"Quero cancelar, vou me mudar"** era classificado como **fúria**, e o modelo recebia instrução
  de "ser mais seco" com um cliente educado. Virou categoria própria, com tom calmo e sem sermão.
- **O nome do cliente podia ser a mensagem crua dele** — quando o cadastro não era encontrado, a
  nota da equipe saía como "Nome: já reiniciei tudo e não funciona". Corrigido.
- **O bot esquecia quem era o cliente** quando a conversa era reaberta: pedia de novo nome, CPF e
  endereço de ontem. Agora a **ficha** sobrevive; só o roteiro zera.
- **Reincidência**: quem trouxe o mesmo problema 2x+ em 7 dias agora é reconhecido ("vi que você já
  tinha falado disso"), não leva pedido de reinício, e a equipe recebe a nota marcada como crônico.
- **9 regras novas** (15 a 23) para situações que caíam no vazio: falar com humano, mudança de
  endereço, cancelamento, upgrade de plano, velocidade contratada × entregue, visita agendada,
  documentos, quem não é titular, e "nunca afirme o que o cliente não disse".

---

## ⚡ 5. VELOCIDADE

### O que estava roubando tempo

| Achado | Custo |
|---|---|
| **2ª chamada de IA escondida** — o bot "tomava nota" da conversa **antes** de responder | **~2s em toda conversa longa** |
| Cache do prompt durava 5 min — e o Pedrão trabalha de madrugada, quando o intervalo é maior | reprocessava ~13k tokens do zero |
| Busca de fatura **em fila**: CPF com 4 cadastros = 8 requisições uma após a outra | **~3,6s** |
| A **mesma** busca de cadastro era feita 2× por fatura | ~0,4s |
| Cada chamada à IA abria conexão nova (handshake do zero) | ~0,25s por mensagem |
| Banco abria conexão nova **dezenas de vezes** por mensagem | picos |
| Painel era lido e interpretado do disco **6-8× por mensagem** | picos |
| Áudio travava **o servidor inteiro** enquanto baixava e transcrevia | até 90s para todos |
| A janela de espera era cobrada até de quem já tinha terminado a frase | ~1,2s |
| O modelo escrevia uma "nota interna" em toda resposta — e o código **jogava fora** | ~1s |

### O que foi feito

- **Resposta primeiro, anotação depois**: a nota da conversa agora roda em segundo plano.
- **Cache do prompt de 1h** em vez de 5 min.
- **Buscas de fatura em paralelo**, com a ordem preservada — medido: **3,6s → 1,25s**.
- **Cache de 30s** no cadastro: fim da busca duplicada — fluxo real caiu para **0,80s**.
- **Conexão reaproveitada** com a IA (pool), com volta automática ao método antigo se faltar a lib.
- **Banco com uma conexão só** + índices novos; **painel em cache** que recarrega sozinho quando
  você salva (o efeito continua imediato).
- **Áudio saiu do caminho** que travava o servidor.
- **Janela de espera inteligente**: quem termina a frase (pontuação, CPF, escolha de menu,
  "obrigado") é atendido em **0,8s**; quem está digitando em pedaços continua sendo agrupado.
  Medido: 2,0s → **0,81s**.
- **Delay de digitação virou orçamento**: desconta o tempo que o raciocínio já gastou, em vez de
  somar espera por cima.

> ⚠️ **Não toquei no envio de faturas** (a régua, o formato, o Pix), como você pediu. O que mudou
> ali foi só a **busca** ficar paralela — a fatura escolhida é exatamente a mesma.

---

## 📏 6. AGORA DÁ PRA MEDIR (não é mais opinião)

Abra: `https://pedrao.webfiberprovedorcliente.cloud/health`

Tem um bloco `desempenho` com:
- **mediana** e **pior 5%** do tempo de resposta
- tempo só do "pensar"
- **% de respostas sem IA** (atalho — instantâneas e de graça)
- **% de cache quente** (se o cache do prompt está funcionando)

Também mostra o **modo efetivo** e o **próximo atendimento** calculado.

Deixei um monitor rodando: assim que houver movimento suficiente, eu te trago os números reais.

---

## 🧹 7. LIMPEZA

- **Erro vermelho no fim de todo deploy** eliminado: havia um Caddy no `docker-compose` que
  disputava as portas 80/443 com o nginx da VPS e por isso **nunca subiu uma única vez** (confirmei:
  status "created", nunca iniciado). Quem publica o domínio é o nginx. Removido.
- Tabelas que **cresciam para sempre** (fatos, resumo, sessão) agora respeitam a retenção + VACUUM.
- Vazamento de memória no detector de "humano digitou" — corrigido.
- Log forense byte a byte (da investigação dos botões, já encerrada) saiu do caminho quente: agora
  só roda em erro, ou ligando `FS_FORENSE=1`.

---

## ✅ Bateria de testes: 220/220

De 145 para **220 verificações**. As novas cobrem **cada frase real** que produzia resposta errada —
então esses erros não voltam sem o teste apitar.

---

## 📌 O que eu deixaria para uma próxima

1. **Comprovante de pagamento** (o que você perguntou antes de dormir): o webhook já recebe a foto,
   o nome e o telefone. Falta decidir se lê **toda** imagem ou só as de contexto de pagamento, e se
   a planilha vai para o Google Sheets. Está desenhado, não implementado.
2. **`resumir()` sem cache** — é a única chamada de IA que ainda paga preço cheio.
3. **Vários processos (workers)** — hoje **não dá**: o agrupamento e o anti-duplicata vivem na
   memória de um processo só. Precisaria de Redis antes. Não é gargalo hoje.
