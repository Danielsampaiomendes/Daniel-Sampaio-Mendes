---
name: "divine-auditoria-atendimentos"
description: "Use quando o Renato pedir para varrer, monitorar, auditar ou corrigir o Divine App: atendimentos, consultas, protocolos, cobranças, estoque, WhatsApp e pacientes parados."
---

# Auditoria e sentinela do Divine App

Duas funções na mesma skill:
1. **Varredura (sentinela):** olhar o sistema inteiro e apontar tudo o que não bate entre agenda, prontuário, protocolo, financeiro, estoque e WhatsApp. Só leitura.
2. **Correção:** resolver caso a caso seguindo os padrões abaixo, com o ok do Renato quando houver dinheiro, cancelamento ou exclusão envolvidos.

Escrever tudo em português do Brasil, sem travessões. Mensagens de WhatsApp para pacientes sem emojis.

## Acesso
- Supabase, projeto `nhtgmjnhaiilvalvacwt`, schema `app`, via `execute_sql`. É mais rápido e completo que navegar no app pelo Chrome (a extensão travou ao percorrer muitos cards).
- A conta do Divine App pode estar sendo usada pelo Renato ou pelo Dr. Daniel.
- Período confiável: a partir de 09/11/2026. Antes disso agendamentos e prontuários vinham do CNN (`source` nulo), sem itens nem insumos. Protocolos antigos ficam em `app.quotes` (status `APROVADO`; nos agendamentos, procedimentos com `quote_cnn_id`).
- Ignorar o paciente de teste Renato do Nascimento e citar uso interno do Dr. Daniel como paciente só numa linha.
- Alternativa sem Supabase: com o Divine App aberto no Chrome do Renato, a mesma base responde em `/api/<tabela>` (estilo PostgREST, autenticado pelo cookie da sessão), via `fetch` com `credentials:'include'`. Nunca exibir tokens ou cookies. Consultas longas: rodar em segundo plano dentro da página, guardar em `window.__x` e ler em blocos.
- Saldo de cada item de protocolo pronto em `v_proposal_progress` (`planned_qty`, `done_qty`, `remaining_qty`, `done_dates`). Comentários da aba CRM do paciente ficam em `patient_comments`. Pagamentos de cada recebível em `finance_payments`.
- Horários no banco estão em UTC; converter para horário de Brasília antes de citar.

## Mapa das tabelas
- `appointments`: agenda. `status` (AGENDADO, FINALIZADO, EM_ANDAMENTO, CANCELADO, REAGENDADO), `staff_id`, `room_id`, `agenda_type_id`, `procedures` jsonb, `proposal_item_id`.
- `consultations`: prontuário, ligado por `appointment_id` (pode existir solto, sem agendamento). `status` draft/finalized, `data` jsonb e `summary` com o texto, `staff_id` de quem escreveu, `agenda_type_id`.
- `consultation_procedures`: itens realizados. `service_id`, `name`, `qty`, `notes`, `proposal_item_id` (liga ao protocolo e dá a baixa da sessão).
- `stock_movements`: insumo baixado (`kind` consumption, `qty` negativa na unidade de compra, `qty_use` na unidade de uso, `lot_id`, `consultation_id`). Não há gatilho: ao inserir, também diminuir `product_lots.qty_remaining`.
- `products` (`fraction_factor`, `fraction_unit`, `sale_price_cents`) e `product_lots` (`unit_cost`, `qty_remaining`, `lot_code`).
- `proposals` (status approved, `number`) e `proposal_items` (`qty`, `sessions`, `unit_price_cents`, `variant_id`). Sessões usadas = quantidade de `consultation_procedures` com aquele `proposal_item_id`.
- `finance_receivables` (source appointment, proposal, manual, cnn_import; status open, partial, paid, canceled; `appointment_id`, `consultation_id`, `proposal_id`, `notes`), `finance_installments`, `finance_receivable_classes`, `finance_receivable_legs`.
- `tasks` (category tecnologia, concierge, clinico, administrativo, comercial, lead; source_kind manual, protocol_scheduling, quote_followup, card_recon, return_reminder etc.; `assigned_to_staff_id`, `patient_id`).
- `whatsapp_conversations` (`last_direction`, `unread_count`, `patient_id`, `wa_account`), `whatsapp_messages`, `appointment_confirmations`.
- `service_variants`, `rooms`, `agenda_types`, `staff`.

## IDs úteis (conferir com uma leitura antes de usar)
- Serviço Consulta em Nutrologia: `7dce275e-c84d-49e6-9a37-ceadddd17c3c`. Variações: Inicial (R$ 510), Acompanhamento Avulsa (R$ 510), Acompanhamento Protocolo (R$ 0), Retorno (R$ 0), Reativação (R$ 510).
- Serviço Terapias Injetáveis e Soroterapia: `a25f3411-07ee-4dd9-b5fb-bc5fae142053`. Modulação Hormonal: `054a70d0-8eda-46cc-bd38-6fad649a6422`. Inibidores de Apetite (GLP-1): `7f478e7e-b3b4-475d-8cf6-398a3f111f8a`.
- Sala Consultório: `a1feaba9-57f0-4256-a7f8-0b376fa295f0`. Tipo de agenda Consulta de Acompanhamento: `0ead9df7-8951-4483-bb05-c236f78e7722`.
- Categoria financeira de consulta: `9630d49e-9182-419a-972d-f5c88096b105`.
- Staff: Renato `a5b70e59-f7a6-434d-a59b-2adfbf134e1d`, Tiago `c48e6f1b-c743-4508-a993-a328ed5b6cb8`, George `6b9a252f-505a-4e7d-979e-7bc9fd8abe43`. Buscar os outros por nome.

## Parte 1: varredura (rodar todas as checagens)

### A. Atendimento, prontuário e lançamento
1. Atendimento finalizado sem prontuário.
2. Prontuário finalizado do Dr. Daniel sem item de Consulta em Nutrologia. Antes de apontar, procurar recebimento ou item de orçamento de consulta solto em mais ou menos 24 horas. Deixar claro que o atendimento existe e o que falta é o item; nunca dizer que o paciente precisa ser atendido.
3. Prontuário que diz "realizado" (CMSlim, Hybrius, botas, preenchimento, implante, soro) sem item lançado.
4. Insumo baixado sem item lançado.
5. Item lançado sem insumo correspondente (Botox sem toxina, preenchimento sem ácido hialurônico, PDRN sem PDRN, protocolo de glúteo sem kit). Exceção: produto trazido de fora, anotado no item.
6. Prontuário em rascunho há mais de 24 horas; prontuário solto sem agendamento (pode ser registro aberto por engano, com item errado).
7. Agendamento com data passada ainda AGENDADO ou EM_ANDAMENTO.
8. Profissional do agendamento diferente de quem escreveu o prontuário.

### B. Protocolos
1. Item com evidência de execução e saldo não baixado.
2. Duas sessões ligadas ao mesmo item de quantidade 1, com outro item igual zerado.
3. Saldo de protocolo sem agendamento: soro, injetáveis e tecnologias semanais acima de 10 dias; implantes e preenchimentos acima de 30 dias; qualquer item acima de 45 dias é prioridade.
4. Tarefa `protocol_scheduling` vencida, ou saldo sem tarefa nem mensagem recente.
5. Orçamento aprovado sem conta a receber.
6. Preço do orçamento abaixo do custo do insumo (`product_lots.unit_cost`) ou muito abaixo da tabela. Se houver condição especial anotada, só citar.

### C. Financeiro
1. Cobrança avulsa em aberto de item já incluído num protocolo pago.
2. Cobranças duplicadas no mesmo atendimento (mesma descrição e valor, poucos minutos de diferença, normalmente clique duplo).
3. Mesmo item pago duas vezes (orçamento pago e avulso pago).
4. Recebimento manual solto que deveria estar ligado a um atendimento do mesmo dia (acontece quando a recepção cobra um casal junto).
5. Parcelas vencidas em aberto, separando condição especial.

### D. Estoque
1. Tirzepatida: a unidade "ml" do app é 0,1 ml (2,5 mg). Ampola 60 mg = 24 unidades (fator 24), ampola 20 mg = 8 (fator 8). Apontar aplicações baixadas como 0,1 ou 0,2 (o certo é 1 por 2,5 mg) e ampolas inteiras baixadas como 1. O custo exibido por "ml" é o custo do frasco dividido pelo fator e está certo; só o nome da unidade confunde.
2. Fracionados com quantidade incoerente (ex.: bioestimulador corporal com 1 ml por sessão; produto corporal usado em procedimento facial).
3. Produto com venda e sem custo, ou custo que não bate com o lote. O preço real de compra está no estoque por lote (`product_lots.unit_cost`).
4. Lote vencido com saldo; cadastros duplicados do mesmo produto (ex.: Tirzepatida Octalab separada do item principal).

### E. WhatsApp e acompanhamento
1. Paciente com protocolo ativo e mensagem recebida sem resposta há mais de 24 horas. Para responder, usar `divine-whatsapp-sem-resposta`.
2. Paciente com saldo sem mensagem da clínica nos últimos 14 dias.
3. Confirmação de amanhã não enviada ou pedido de remarcação sem tratamento.
4. Follow-up de orçamento (`quote_followup`) vencido.

### Entrega da varredura
Lista por prioridade: 🔴 dinheiro em risco, 🟠 paciente parado, 🟡 registro errado. Cada linha com paciente, data e hora, profissional, o problema, a evidência (o número que comprova) e a correção proposta. Agrupar casos iguais e propor resolver em lote, separando os casos claros dos que precisam do olho do Renato. Fechar com o padrão de comportamento da equipe (ex.: quem baixa insumo sem lançar sessão; quem escreve no prontuário sem lançar).

## Parte 2: padrões de correção

### Evidência de execução
Insumo baixado, prontuário dizendo "realizado", lançamento avulso ou confirmação do Renato. Prontuário do Dr. Daniel que só planeja ou prescreve não é execução.

### 1. Sessão feita sem baixa no protocolo
1. Se existe atendimento com a evidência, lançar o item nesse atendimento ligado ao `proposal_item_id`.
2. Só quando não existe nenhum atendimento, criar um na agenda do Dr. Daniel na data, finalizado, com prontuário finalizado, e lançar o item.
3. Quando o Renato confirma que foi feito no dia do pagamento, usar o atendimento desse dia.
4. Nota: "Sessão realizada em DD/MM conforme registro. Baixa no protocolo #N feita na auditoria."
5. Se o insumo não foi baixado e saiu do estoque da clínica, inserir o `stock_movement` e diminuir o lote (Tirzepatida: lote Exacta TZ2926 quando não houver indicação). Se o produto veio de fora, só anotar no item.
6. Nunca gerar cobrança avulsa de item que está no protocolo.
7. Ligar só o agendamento ao protocolo não dá baixa: a sessão só conta com uma linha em `consultation_procedures`, de prontuário finalizado, com `proposal_item_id`. Cada linha conta uma sessão, independente do `qty`. Conferir sempre em `v_proposal_progress`.
8. `proposal_item_id` órfão: quando o orçamento é editado, o app recria os itens com outro id e os vínculos antigos param de contar. Procurar ids que não existem mais em `proposal_items` e religar ao item atual (caso Monica Di Stasi, 19/11/2026).
9. Duas áreas ou duas sessões feitas no mesmo atendimento, mas o agendamento só contabiliza uma (caso Norran Rodrigues, Endolaser): criar um segundo atendimento no nome do Dr. Daniel, mesma data e horário, finalizado, com prontuário finalizado e a linha ligada ao item. Nota: "as duas áreas foram feitas na mesma sessão com [profissional], mas o agendamento só permitia contabilizar uma; lançamento posterior, sem novo atendimento".
10. Protocolo aplicado sem atendimento gerado (caso Renan Santos, aplicações da Nayara depois da consulta): criar o atendimento do Dr. Daniel no dia, com nota de quem realizou, o que foi realizado e que os lotes não foram registrados. Doses semanais (Tirzepatida): baixar só a aplicação feita no dia, salvo confirmação de que todas foram entregues.
11. Consulta dentro da vigência de protocolo: variação "Acompanhamento Protocolo" (R$ 0), nunca a Avulsa. Corrigir também o nome do item no prontuário.

### 2. Consulta do Dr. Daniel sem item
1. Procurar recebimento ou item de orçamento solto em 24 horas e vincular (recebível ganha `appointment_id` e `consultation_id`; item de orçamento vira `consultation_procedures` com `proposal_item_id`). Nota: "Consulta realizada e já registrada no prontuário".
2. Sem registro, mostrar a lista e pedir ao Renato a variação de cada paciente (Inicial, Acompanhamento Avulsa, Acompanhamento Protocolo, Retorno, Reativação). Ajuda dar contexto: última consulta, protocolo ativo, cobranças existentes.
3. Lançar a variação com sala Consultório e tipo Consulta de Acompanhamento (no agendamento e no prontuário), salvo outra indicação.
4. Variação com valor: criar a conta a receber em aberto (source appointment, descrição "Atendimento DD de mês de AAAA · Consulta em Nutrologia — Variação", categoria de consulta, uma parcela em aberto, classe Consulta, grupo consulta), sem forma de pagamento, para conciliar. Lançar item direto no banco não gera cobrança sozinho.

### 3. Cobrança em aberto de item já pago
Regra do Renato: cobrança em aberto de item igual ou similar a um já pago em protocolo, ou duplicada no mesmo atendimento, deve ser cancelada. **Sempre mostrar o caso antes** (paciente, valores, horários, quem criou) e esperar o ok, mesmo que ele já tenha autorizado casos parecidos. Ao cancelar: recebível e parcelas como canceladas, com nota explicando. Se houver suspeita de cartão passado duas vezes, pedir conferência na maquininha e falar em estorno.

Causa conhecida: quando a equipe finaliza pela tela um atendimento que não está ligado ao protocolo, o app gera uma nova conta a receber `source = appointment` ("Atendimento DD de mês · Procedimento") em cima do protocolo já pago. Caso Norran (19/11/2026): R$ 1.800 pagos em 8x no orçamento 1124 e uma segunda conta de R$ 1.800 do atendimento, com a 1ª parcela de R$ 225 registrada como paga. Correção aprovada: recebível e parcelas canceladas, pagamento indevido apagado de `finance_payments`, nota explicando. Atualizar o status do agendamento direto no banco não gera cobrança (testado).

### 3b. Protocolo aprovado sem pagamento e sem execução
Se o WhatsApp mostra que o paciente cancelou e não há pagamento nem cobrança (caso Rodrigo Costa Val Pedrosa): orçamento volta para `open` (`approved_at` nulo), agendamento vira CANCELADO com o motivo e cria-se tarefa de follow-up para o Tiago.

### 3c. Sessão feita com orçamento ainda em aberto
Se o orçamento nunca foi aprovado (caso Mariah Feijó, ClassPass), não ligar a sessão sozinho: tarefa para quem está negociando oferecer o fechamento; se fechar, aprovar, lançar o pagamento e ligar a sessão.

### 3d. Agendamentos passados sem baixa (checagem A7)
Cruzar prontuário do dia, recebíveis, outros agendamentos do paciente no dia e depois, e WhatsApp de um dia antes a um dia depois:
- Finalizar com evidência clara (prontuário finalizado, pagamento, outro atendimento finalizado no dia, paciente avisou que chegou, pós-atendimento da equipe no dia seguinte).
- Cancelar quando o WhatsApp mostra falta ou remarcação, ou é agendamento interno duplicado.
- Acrescentar à observação "Baixa em DD/MM/AAAA: [evidência]" ou "Cancelado em DD/MM/AAAA: [motivo]", mantendo o texto anterior.
- Dúvida vira uma tarefa por profissional com a lista dos casos. Prontuário em rascunho é a causa mais comum: finalizar o agendamento não dá baixa no protocolo.

### 4. Pendências que dependem de terceiros
Criar tarefa em `app.tasks` com título claro, descrição com contexto, passos numerados e a instrução de não alterar nada e responder na própria tarefa:
- Conferência de pagamento na maquininha: Tiago, categoria administrativo, source_kind card_recon, prioridade alta.
- Pergunta ao profissional sobre registro duvidoso: Tiago, administrativo, manual.
- Follow-up para agendar saldo de protocolo: concierge, protocol_scheduling, responsável indicado pelo Renato (ex.: Jennifer quando ela vai atender a paciente).

### 5. Ajustes de cadastro
- Corrigir o profissional do agendamento quando o prontuário foi feito por outra pessoa.
- Paciente especial com valor combinado: anotar a condição na conta a receber e no item; não mexer nas parcelas sem pedido.

## Regras gerais
- Ler o estado atual antes de qualquer escrita (a equipe mexe o tempo todo). Escrever em transação, com `where not exists` para não duplicar, e conferir com uma leitura depois.
- Se o Renato interromper durante uma escrita, verificar se ela já foi aplicada e dizer com clareza.
- Não mexer em nada pago sem confirmação no extrato. Não apagar nada sem pedido.
- Ao consultar itens ligados a protocolo, testar `proposal_item_id is not null`; não usar `coalesce` com texto fixo, que marca tudo como ligado.
- Faixa de preço começando em R$ 0 em procedimento com variação Classpass, Retorno, Protocolo ou avaliação inicial é intencional, não é erro.
- Entregar a lista por paciente, com data, hora, profissional e a evidência, para o Renato decidir. Quando ele pedir para investigar, mostrar um caso por vez.
- Antes de propor correção, ler as conversas de WhatsApp do paciente em volta da data: explicam faltas, cancelamentos, remarcações, preços combinados e pedidos de nota fiscal.
- Antes de corrigir em lote, testar em um registro e conferir que não houve efeito colateral (cobrança ou mensagem automática ao paciente).
- Depois de corrigir, registrar comentário na aba CRM do paciente (`patient_comments`, autor Dr. Daniel) com a data, o que foi encontrado e o que foi ajustado. Pendências com paciente viram tarefa para o Tiago (`category` comercial, `source_kind` quote_followup, `patient_id` preenchido).
- Nunca mandar mensagem a paciente sem o ok do Renato.
- Avisar uma vez, se ainda estiver aberto, que tabelas do schema `backup` estão sem RLS (expostas à chave pública); não corrigir sem ok.

## Melhorar a skill
Toda regra nova ou correção de leitura feita pelo Renato vira proposta de edição desta skill, para a próxima varredura já sair certa.