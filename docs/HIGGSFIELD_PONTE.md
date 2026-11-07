# Ponte Divine Studio ↔ Higgsfield (para o Claude executar os pedidos)

O Divine Studio monta os pedidos; o Claude, com o conector do Higgsfield, executa. Use esta página quando o Renato pedir
"processe os pedidos do Higgsfield" (o botão **Copiar para o Claude** na tela Higgsfield gera o pedido pronto).

## Onde estão as coisas
- Fila: `projetos/.higgsfield_fila.json` (lista de pedidos: `id`, `projeto`, `tipo` efeito|modelo|ferramenta, `alvo`,
  `nome`, `entrada.arquivo` relativo à pasta do projeto, `prompt`, `params`, `status`).
- Catálogo e regras de prompt: `config/higgsfield.yaml`.
- Arquivo de entrada: `projetos/<projeto>/<entrada.arquivo>`.

## Passo a passo (para cada pedido `pendente`)
1. Marque como gerando: `python3 -m divine_studio higgsfield status <id> gerando`.
2. Envie a entrada: `media_upload` do arquivo local (PUT do arquivo, depois `media_confirm`).
3. Calcule o custo antes:
   - **efeito**: abra com `get_presets(source="viral", preset_id=<alvo>, initial_inputs=...)` e confira `execution.readiness`.
   - **modelo / ferramenta**: `generate_video` com `get_cost: true`.
4. **Mostre o custo em créditos ao Renato e espere o ok.** Nada é gerado sem o ok dele.
5. Gere:
   - **efeito**: `execute_preset`.
   - **modelo / ferramenta**: `generate_video` com `model=<alvo>`, `prompt=<prompt>`, `medias` com o media_id e `aspect_ratio` de `params` (9:16).
   - **virality_predictor**: use a ferramenta `virality_predictor` (`action="create"`).
6. Espere com `jobs_wait` e pegue o link do resultado.
7. Devolva para o projeto:
   - Com acesso à pasta do Mac: `python3 -m divine_studio higgsfield pronto <id> <link-ou-arquivo> --job <job_id> --creditos <n>`. O app baixa o resultado para `bruto/`.
   - Numa sessão na nuvem, sem acesso ao Mac: passe o link para o Renato colar no app, em Higgsfield > Pedidos > "Colar resultado".
8. Se der erro: `python3 -m divine_studio higgsfield status <id> erro --nota "motivo"`.

## Regras
- Compliance CFM/Anvisa: nada de antes e depois, não alterar rosto ou corpo de paciente, sem promessa de resultado.
  Só pessoas da equipe com autorização de imagem.
- Ao postar algo gerado por IA, ligar o rótulo "Feito com IA" do Instagram.
- Sem logos de outras marcas. Formato vertical 9:16 por padrão.
- Virality Predictor: registre a nota no projeto (`trabalho/higgsfield_viralidade.json`) para o Laboratório comparar com
  o resultado real depois de postar.
