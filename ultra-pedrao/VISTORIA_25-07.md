# Vistoria completa — Ultra Pedrão (madrugada 24→25/07)

**Tudo já está NO AR.** Deploy feito por mim via terminal, container saudável, bateria **297/297**.
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

## 📊 6. RESULTADO MEDIDO EM PRODUÇÃO (não é estimativa)

Rodei mensagens reais de cliente contra o bot **no ar**, sem enviar nada a ninguém:

| Mensagem do cliente | Tempo do cérebro | Caminho |
|---|---|---|
| "oi boa noite" | **0 ms** | atalho (sem IA) |
| "minha internet caiu" | **11 ms** | atalho |
| "quanto custa o plano de 1 giga?" | **1 ms** | atalho |
| "quero a segunda via da fatura" | **1 ms** | atalho |
| "já paguei e vocês cortaram minha internet" | 3,2 s | IA |
| "contratei 700 mega e o teste dá só 180" | 2,9 s | IA |
| "quero falar com um atendente" | 2,0 s | IA |
| "gostaria de cancelar, vou me mudar" | 2,2 s | IA |

**Cache do prompt: quente em 100% das chamadas** — 20.409 tokens lidos do cache em vez de
reprocessados a cada mensagem.

**Efeito da regra "WhatsApp, não e-mail"** (medido antes/depois na mesma mensagem):

| Mensagem | Antes | Depois |
|---|---|---|
| "contratei 700 mega e o teste dá 180" | 5,3 s | **2,9 s** (-45%) |
| "já paguei e vocês cortaram" | 4,5 s | **3,2 s** (-29%) |
| "quero falar com um atendente" | 2,6 s | **2,0 s** (-20%) |

**Placar geral:** **56% das mensagens são respondidas sem IA nenhuma** (instantâneas e de graça).
O resto responde em ~2 a 3 segundos. Antes, o caminho típico levava 10 a 13 segundos.

### E a qualidade, medida junto

- "já paguei e vocês cortaram" → *"Poxa, que chato isso. Vou registrar que você já pagou e a
  internet foi cortada… encaminho com prioridade pro time de Financeiro"* — **não mandou boleto.**
- "contratei 700 e dá 180" → *"180 é bem menos do que os 700 que você contratou, né. Você testou
  no **cabo de rede** ou pelo **Wi-Fi**?"* — **não mandou tabela de planos.**
- "a luz tá piscando" → *"Entendi que a luz tá piscando…"* — **usou as palavras do cliente**, não
  cravou "luz vermelha".

---

### Teste das regras novas — e 4 erros que ele revelou

Rodei cada regra nova contra o bot no ar. Quatro passaram de primeira; **três falharam**, e um
deles era grave. Os quatro achados:

| # | Erro encontrado | Correção |
|---|---|---|
| 1 | **O bot não sabia que horas eram** — escrevia "Boa tarde!" à meia-noite | Agora recebe data, hora e o prazo já calculado por setor |
| 2 | 🔴 **"Vou me mudar, dá pra levar a internet?"** → *"**Dá sim! A gente leva junto**"* — promessa de cobertura **sem saber o endereço** | Virou resposta fixa: "quem confirma é a nossa equipe" |
| 3 | **"2ª via do contrato"** → *"pra puxar a sua **fatura**, me manda o CPF"* | Contrato/IR/titularidade separados de boleto |
| 4 | **"Quero aumentar meu plano"** → pedia rua e bairro "pra ver viabilidade" de um cliente de anos | Virou resposta fixa: registra e pede só o CPF |

**Detalhe importante:** nos casos 2 e 4 eu **reescrevi a regra e não adiantou** — o modelo continuou
respondendo errado, porque o prompt principal puxa forte para o fluxo de venda. Só resolveu quando
tirei do texto e transformei em **código**. Ficou mais confiável **e** instantâneo (0ms, sem custo).

**Resultado final, medido depois das correções:**

| Cliente | Pedrão |
|---|---|
| "vou me mudar, dá pra levar a internet?" | *"Posso registrar sim! Quem confirma se a gente já atende o endereço novo é a nossa equipe."* **(0ms)** |
| "quero aumentar meu plano pra 1 giga" | *"Vou registrar seu pedido e o Comercial te passa a condição certinha. Me confirma o CPF?"* **(0ms)** |
| "que horas o técnico chega?" | *"Não tenho acesso à agenda… a equipe entra em contato **amanhã (sábado) a partir das 9h**"* |
| "falo pelo meu pai, ele é o titular" | *"Por segurança, dados da conta só vão pro titular… a equipe fala com ele **a partir de segunda**"* |

Repare que os prazos saem **diferentes e corretos**: suporte trabalha sábado, financeiro não.

---

## 📏 7. COMO VOCÊ ACOMPANHA SOZINHO

Abra: `https://pedrao.webfiberprovedorcliente.cloud/health`

Tem um bloco `desempenho` com:
- **mediana** e **pior 5%** do tempo de resposta
- tempo só do "pensar"
- **% de respostas sem IA** (atalho — instantâneas e de graça)
- **% de cache quente** (se o cache do prompt está funcionando)

Também mostra o **modo efetivo** e o **próximo atendimento** calculado.

Deixei um monitor rodando: assim que houver movimento suficiente, eu te trago os números reais.

---

## 🧹 8. LIMPEZA

- **Erro vermelho no fim de todo deploy** eliminado: havia um Caddy no `docker-compose` que
  disputava as portas 80/443 com o nginx da VPS e por isso **nunca subiu uma única vez** (confirmei:
  status "created", nunca iniciado). Quem publica o domínio é o nginx. Removido.
- Tabelas que **cresciam para sempre** (fatos, resumo, sessão) agora respeitam a retenção + VACUUM.
- Vazamento de memória no detector de "humano digitou" — corrigido.
- Log forense byte a byte (da investigação dos botões, já encerrada) saiu do caminho quente: agora
  só roda em erro, ou ligando `FS_FORENSE=1`.

---

## ✅ Bateria de testes: 297/297

De 145 para **297 verificações**. As novas cobrem **cada frase real** que produzia resposta errada —
então esses erros não voltam sem o teste apitar.

---

## 🎯 Mais duas rodadas de caça (e mais 6 erros)

Continuei jogando mensagens difíceis contra o bot no ar. Cada rodada achou coisa nova:

**2ª rodada — 10 mensagens:**

| Cliente escreveu | O bot respondia (errado) |
|---|---|
| 🔴 "vocês fazem instalação em qual bairro? moro na tijuca" | *"**A gente atende na Tijuca sim!**"* — afirmou cobertura |
| 🔴 "quero o valor dos planos **e também** me manda minha fatura" | respondia só sobre planos, **ignorando metade da mensagem** |
| 🔴 "posso pagar semana que vem? tô sem grana" | *"me passa teu endereço que eu já adiantar teu atendimento"* — incoerente |

**3ª rodada — mais 10 mensagens:**

| Cliente escreveu | O bot respondia (errado) |
|---|---|
| 🔴 "quero mudar a **senha** do meu wifi" | *"me passa o **endereço novo**"* — caiu no fluxo de mudança de casa (regressão minha) |
| 🔴 "vocês cobram taxa de instalação?" | *"Sim, cobramos — mas **dá pra parcelar em até 3x no cartão**"* — **inventou** condição comercial |
| 🟡 "vocês trabalham no domingo?" | *"É pra contratar ou outro assunto?"* — não respondeu, e a informação existe no sistema |

Todos corrigidos e virados teste. Destaques:

- O **guard de cobertura** só pegava "atende na *rua*" — afirmação com **nome de bairro** passava.
  Ampliei, tomando o cuidado de **não apagar a frase certa** ("quem confirma *se* a gente atende é
  a equipe"), que casava no mesmo padrão.
- Criei um **guard novo** para condição comercial inventada (taxa, parcelamento, fidelidade,
  "é grátis") — o guard de preço não pegava, porque não tem "R$" na frase.
- "Senha do Wi-Fi" agora **registra e encaminha**. O bot chegou a ensinar o cliente a *"acessar o
  roteador direto"* — pior que executar: se a pessoa erra, perde a conexão inteira.
- "Horário de atendimento" virou resposta instantânea, com a fronteira certa: *"que horas o
  **técnico** chega"* continua sendo tratado como visita agendada, sem chutar horário.

---

## 🔁 4ª rodada — o pior erro da noite (só aparece em CONVERSA)

Até aqui eu testava **mensagens isoladas**. Quando testei uma **conversa de verdade**, com vários
turnos, achei o pior problema de todos:

> **Cliente:** minha internet caiu
> **Pedrão:** *(pede nome e CPF)*
> **Cliente:** já reiniciei o roteador 3 vezes
> **Pedrão:** *"Pra eu já achar seu cadastro… me confirma nome e CPF?"* ← **ignorou o que ele disse**
> **Cliente:** e agora? continua sem nada
> **Pedrão:** *"Pra eu já achar seu cadastro… me confirma nome e CPF?"* ← **palavra por palavra igual**
> **Cliente:** mas quanto tempo? já faz 2 dias
> **Pedrão:** *"Faz o seguinte: tira o roteador da tomada…"* ← **sem CPF, do nada**

Três defeitos no mesmo trecho de código:

1. A verificação de "já reiniciei" (regra 5) vinha **depois** do pedido de CPF — quem dizia que já
   tinha reiniciado era tratado como se não tivesse falado nada.
2. O pedido de CPF **se repetia idêntico**, mesmo quando o cliente perguntava outra coisa (regra 9).
3. Esgotadas as tentativas, ele **mandava reiniciar sem ter identificado ninguém** e sem responder
   a pergunta.

**Como ficou agora, no mesmo diálogo:**

> **Cliente:** já reiniciei o roteador 3 vezes
> **Pedrão:** *"Ótimo, você já fez o básico então. Deixa eu registrar isso aqui com prioridade."*
> **Cliente:** e agora? continua sem nada
> **Pedrão:** *"Relaxa que já tá registrado. Como você já reiniciou 3 vezes e continua sem nada, a
> equipe de SUPORTE entra em contato **hoje (sábado) a partir das 9h**."*

O atalho agora pede o CPF **uma vez**; se o cliente pergunta algo, quem assume é o modelo — que
responde o que a pessoa falou. O fluxo bom não mudou: quem manda só o nome continua recebendo o
pedido do CPF que falta.

A bateria ganhou uma seção que roda **conversas inteiras**, não mensagens soltas.

---

## 🔬 O método que usei (e o que ele revelou)

Trabalhei em ciclos: **medir → corrigir → medir de novo**. Isso pegou coisas que uma leitura de
código sozinha não pegaria — inclusive **erros meus**:

0. Testei só mensagens isoladas por 3 rodadas → **a 4ª, com conversa de verdade, achou o pior erro de todos**.
1. Corrigi o bug da luz vermelha ontem → **a auditoria mostrou 3 portas ainda abertas**.
2. Escrevi 9 regras novas → **testei ao vivo e 3 falharam**, porque o prompt principal vence a
   regra escrita. Só resolveu virando código.
3. Criei o atalho de upgrade → **na medição seguinte peguei que ele "vendia" para quem estava
   reclamando de velocidade**. Regressão minha, corrigida na mesma noite.
4. Dei o relógio ao modelo → **ele abriu conversa com "Opa, madrugada!"**. Corrigido.

Cada um desses virou teste na bateria. É por isso que ela saiu de 145 para **242 verificações**:
não são testes decorativos, é cada erro real que apareceu, congelado para não voltar.

**Uma medição que mudou minha prioridade:** o tempo de resposta é praticamente **linear no número
de tokens que o modelo escreve** (~60 por segundo). 119 tokens = 1,9s; 347 tokens = 5,1s. Ou seja:
mandar o bot ser conciso não é só melhor de ler no celular — é a alavanca mais barata de
velocidade que existe aqui.

---

## 🔙 Se algo der errado (reverter em 1 comando)

Tudo entrou em commits pequenos e separados. Para voltar ao estado de **antes da madrugada**:

```bash
cd ~/up/ultra-pedrao && git reset --hard 6605d41 && docker compose up -d --build
```

Para voltar só um passo (desfazer o último commit e manter o resto):

```bash
cd ~/up/ultra-pedrao && git reset --hard HEAD~1 && docker compose up -d --build
```

E se quiser **desligar tudo na hora**, sem terminal: o botão no painel
(`pedrao.webfiberprovedorcliente.cloud/painel`, senha `01webfiber01`) continua funcionando igual.

### Ajustes finos que você pode mudar sem mexer em código (no `.env` da VPS)

| Variável | Hoje | O que faz |
|---|---|---|
| `FS_DELAY_MIN_S` / `FS_DELAY_MAX_S` | 0,6 / 1,2 | Pausa antes de responder (para não parecer robô). **Quer mais rápido ainda? Baixe para 0.3/0.6** — o atalho hoje leva 1,2s e ~1,1s disso é essa pausa. |
| `FS_NATURAL_ALVO_S` | 2,0 | Tempo total que soa natural. Acima disso, não espera mais nada. |
| `DEBOUNCE_CURTA_S` | 0,8 | Espera de quem já terminou a frase. |
| `DEBOUNCE_SECONDS` | 2 | Espera de quem está digitando em pedaços. |
| `FS_FORENSE` | (desligado) | `1` liga o log byte a byte de cada envio (só para diagnóstico). |

---

## 📌 O que eu deixaria para uma próxima

1. **Comprovante de pagamento** (o que você perguntou antes de dormir): o webhook já recebe a foto,
   o nome e o telefone. Falta decidir se lê **toda** imagem ou só as de contexto de pagamento, e se
   a planilha vai para o Google Sheets. Está desenhado, não implementado.
2. **`resumir()` sem cache** — é a única chamada de IA que ainda paga preço cheio.
3. **Vários processos (workers)** — hoje **não dá**: o agrupamento e o anti-duplicata vivem na
   memória de um processo só. Precisaria de Redis antes. Não é gargalo hoje.
