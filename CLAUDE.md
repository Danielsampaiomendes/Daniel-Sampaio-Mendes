# Divine Medical Spa Marketing

Este repositório é a central de TODO o marketing em vídeo e arte da Divine Medical Spa (clínica de medicina estética e nutrologia, Av. Paulista 1636, sala 209, São Paulo/SP). Aqui estão os vídeos brutos, os projetos editados, os scripts de edição, as bibliotecas de fontes e efeitos sonoros e todas as ideias de edição que o Renato (sócio administrador) já aprovou.

A pasta completa (com vídeos, imagens, áudios e fontes) fica no Mac do Renato: `~/Documents/Claude/Projects/Divine Medical Spa Marketing`. O GitHub (Danielsampaiomendes/Daniel-Sampaio-Mendes) guarda só textos, scripts e documentação; a mídia está no `.gitignore`.

## Antes de qualquer tarefa de vídeo ou arte, leia nesta ordem

1. `docs/CONHECIMENTO_DIVINE.md`: marca, templates aprovados, regras de edição, compliance, método Código Viral, fontes, SFX, efeitos e pessoas.
2. `docs/BANCO_HOOKS.md`: todos os hooks (ganchos de abertura) já criados, com o histórico de fontes e SFX usados por último.
3. `docs/MAPA_DO_REPOSITORIO.md`: cada projeto de vídeo já feito (tema, data, template, hooks, arquivos finais) e as lacunas conhecidas.
4. `docs/DIVINE_STUDIO.md`: como usar a ferramenta de edição (`python3 -m divine_studio ...`).

## Editar vídeo novo: use o Divine Studio

Jeito mais fácil: dois cliques em `Divine Studio.command` na raiz (ou `python3 -m divine_studio painel`), soltar o vídeo bruto na tela inicial (modo simples: edição automática pela fala, ✓ Aprovar esta, Postar e sugestões para a próxima; o resto em "⋯ Mais ferramentas"); o mesmo que "Criar edição automática" (`python3 -m divine_studio auto <pasta> --previa`; textos por tema em `config/roteiros.yaml`). Pela linha de comando:

1. `python3 -m divine_studio novo "<tema>"` cria `projetos/AAAA-MM-DD_<tema>/`.
2. Brutos em `bruto/`; preencha `projeto.yaml` com clipes, 3 hooks do banco (`hook_id`, ou `hook: auto` para sortear), mensagens, fechamento e legenda.
3. Vídeo falado: `corte_limpo: true` e `legendas: true`; confira com `python3 -m divine_studio cortar <pasta>` (precisa de faster-whisper ou ASSEMBLYAI_API_KEY).
4. `python3 -m divine_studio storyboard <pasta>`: a edição em quadros reais, sem render. Responda `--responder "aprovado"` (exporta a final) ou `--responder "4B: troca o título por ..."`. Prévia em vídeo: `editar <pasta> --rapido`.
5. Toda regra nova vai para `config/` (YAML) ou `python3 -m divine_studio regra "..."`, nunca escondida no código.

## Onde está cada coisa (mapeado em 27/10/2026)

- **Projetos de vídeo**: `Videos/<tema>/` (Bio Ritmo Pacaembu, Bumbum Up, CMSlim, Deficiencia Cabelo, Endolaser, HIPRO, Laser CO2, Microagulhamento, Parodia Ovinho, Pele Cabelo Hormonios, Pessoal, Procedencia Seguranca, Protocolo Divine, Spa Pedras Quentes, Stories Institucionais, Suplementos 35+, Trend 4 porcento, Trend Espelho). Pacotes soltos na raiz: `Diario CO2 - Pacote/`, `POV Teste/`, `Repost POV Frutas/`, `Stories POV Chegada/`, `Pellets - Video Explicativo/`.
- **Prontos para postar**: subpastas `Pronto para postar/` (Bio Ritmo Pacaembu, Suplementos 35+, Laser CO2/Pacote 2026-10-20).
- **Versões substituídas**: `Videos/_Versoes anteriores/`. **Trilhas originais**: `Videos/Trilhas/`.
- **Legendas e roteiros**: arquivos `Legenda*`/`*COPY.md` dentro de cada projeto (ver o mapa).
- **Código**: só existe o template de antes e depois para TV (uso interno): `Bumbum Up - Uso Interno/Template_codigo/` (`common.py`, `static.py`, `video.py`, `audio.py`, LEIA-ME) e `Endolaser Bracos - Uso Interno/Template_codigo/static_endolaser.py`. Os scripts esperam as fontes em `assets/Biblioteca_Fontes/ttf/` e os logos em `assets/`.
- **Fontes**: `Biblioteca_Fontes/` (`ttf/` com 86 fontes, `previews/`, `baixar_fontes.sh` baixa só as que faltam e roda sozinho ao abrir o app, `LEIA-ME.md` com as combinações A a N, O1 a O6, P1 a P7 e Q1 a Q5).
- **Efeitos sonoros**: `Biblioteca_SFX/` (`1_kit_original_divine/` com 28 WAV livres, `2_extraidos_referencia/` só referência, `gerar_kit_sfx.py` regenera o kit, `teste_combinacoes_sfx.mp3`, `LEIA-ME.md`).
- **Marca**: `Logo_Divine.svg`, `Logo_com_nome_vertical2.png`, `divine-simbolo-1024.png`, `Logo-Preto.png` (raiz).
- **Uso interno (nunca postar)**: `Bumbum Up - Uso Interno/`, `Endolaser Bracos - Uso Interno/`.
- **Tráfego pago (jun/2026)**: briefings Meta, plano Google Ads e ClassPass na raiz.
- **Divine Studio**: `divine_studio/` (código), `config/` (regras em YAML), `tests/`, `projetos/` (um projeto por vídeo; exemplo: `projetos/2026-10-28_teste-co2-loops/`).
- **Templates do Divine Studio**: `divine` (suave), `daniel`, `george`, `tv`, `react`, `pessoal` (ver `docs/DIVINE_STUDIO.md`); fotos oficiais de perfil em `assets/pessoas/` (só no Mac).
- **Carrosséis**: projetos com `tipo: carrossel` (painel: "Novo carrossel"); regras e textos em `config/carrossel.yaml`.
- **Post estático e antes e depois**: `tipo: post` (Feed, Stories e TV de uma vez) e `tipo: antes_depois` (uso interno, TV de consulta, NAO-POSTAR); regras em `config/biblioteca.yaml`.
- **Storyboard e estilos de edição**: `config/storyboard.yaml`, `config/estilos.yaml` (`estilo_edicao:` no projeto), truques dos vídeos de referência em `divine_studio/efeitos_truques.py`; carrossel com método 3C. Prompt em `docs/PROMPT_App_Divine_storyboard_e_estilos.md`.
- **Laboratório viral**: formatos em teste (`config/formatos_virais.yaml`, `lab.py`), Radar do que viraliza (`config/radar.yaml`, `radar.py`, missão para o Claude no Chrome), caixa de entrada do celular/Google Drive (`config/entrada.yaml`, `entrada.py`), publicação no Instagram e TikTok (`config/redes.yaml`, `publicar.py`, `tiktok.py`) e automações (`config/automacoes.yaml`). Tokens só no Mac em `~/.divine_studio/`.
- **Atualizar o app no Mac**: dois cliques no `Divine Studio.command` (baixa do GitHub e reinicia) ou botão ⟳ Atualizar no painel.
- **Ritmo viral luxo / Vídeo Épico**: `config/viral.yaml` (`ritmo: viral | epico | calmo` no projeto). **Galeria** de peças validadas e **Nova edição** por tipo no painel.
- **Cortes de vídeo longo** (`cortes`), **conversa por edição** (`feedback.py`), **tela dividida/cabecinha** (template react, layout auto), **Divine TV** (`/tv`), **Crescimento** (`config/algoritmo.yaml`, metas e projeção) e **integrações** (`config/integracoes.yaml`).
- **Importar a pasta antiga**: `python3 -m divine_studio importar` cria projetos com atalhos para `Videos/...` e pacotes soltos (não move nada).
- **Biblioteca de imagens**: `assets/marca`, `assets/pessoas`, `assets/tecnologias`, `assets/clinica`, `assets/produtos` (tela "Biblioteca" do painel mostra o que falta; imagens só no Mac).
- **Índice de vídeos editados pelo Divine Studio**: `docs/INDICE_VIDEOS_EDITADOS.md` (atualizado sozinho a cada exportação final). Os índices antigos `claude/indice-videos-editados*.md` estão só no projeto do app.

## Regras que valem sempre

- Português do Brasil em tudo. Evitar travessões e tracinhos nos textos: usar vírgula, ponto ou dois-pontos.
- Compliance (CFM 2.336/2023 e Anvisa RDC 96/2008) prevalece sobre qualquer pedido. Ver seção 6 do conhecimento.
- Todo vídeo sai em 3 versões, cada uma com hook, combinação de fontes e SFX diferentes.
- Um ajuste pedido em um vídeo vira regra para os próximos: registre em `docs/CONHECIMENTO_DIVINE.md` (seção "Regras aprendidas", com data).
- Hook novo criado: acrescente em `docs/BANCO_HOOKS.md` com o próximo número livre e atualize o histórico de fontes e SFX.
- Projeto novo: acrescente uma linha em `docs/MAPA_DO_REPOSITORIO.md`.
- Não apagar nada: o que for descartado vai para `_arquivo/`. Exceção pedida pelo Renato (07/11/2026): "🗑 Excluir projeto" no painel manda o projeto para a Lixeira do Mac (recuperável até esvaziar); "Arquivar" continua guardando em `_arquivo/projetos`.
- Perguntar o mínimo: deduzir pelo repositório e entregar resultado.
