# Divine Medical Spa Marketing

Este repositório é a central de TODO o marketing em vídeo e arte da Divine Medical Spa (clínica de medicina estética e nutrologia, Av. Paulista 1636, sala 209, São Paulo/SP). Aqui estão os vídeos brutos, os projetos editados, os scripts de edição, as bibliotecas de fontes e efeitos sonoros e todas as ideias de edição que o Renato (sócio administrador) já aprovou.

A pasta completa (com vídeos, imagens, áudios e fontes) fica no Mac do Renato: `~/Documents/Claude/Projects/Divine Medical Spa Marketing`. O GitHub (Danielsampaiomendes/Daniel-Sampaio-Mendes) guarda só textos, scripts e documentação; a mídia está no `.gitignore`.

## Antes de qualquer tarefa de vídeo ou arte, leia nesta ordem

1. `docs/CONHECIMENTO_DIVINE.md`: marca, templates aprovados, regras de edição, compliance, método Código Viral, fontes, SFX, efeitos e pessoas.
2. `docs/BANCO_HOOKS.md`: todos os hooks (ganchos de abertura) já criados, com o histórico de fontes e SFX usados por último.
3. `docs/MAPA_DO_REPOSITORIO.md`: cada projeto de vídeo já feito (tema, data, template, hooks, arquivos finais) e as lacunas conhecidas.
4. `docs/DIVINE_STUDIO.md`: como usar a ferramenta de edição (`python3 -m divine_studio ...`).

## Editar vídeo novo: use o Divine Studio

Jeito mais fácil: `python3 -m divine_studio painel` (interface no navegador). Pela linha de comando:

1. `python3 -m divine_studio novo "<tema>"` cria `projetos/AAAA-MM-DD_<tema>/`.
2. Brutos em `bruto/`; preencha `projeto.yaml` com clipes, 3 hooks do banco (`hook_id`, ou `hook: auto` para sortear), mensagens, fechamento e legenda.
3. Vídeo falado: `corte_limpo: true` e `legendas: true`; confira com `python3 -m divine_studio cortar <pasta>` (precisa de faster-whisper ou ASSEMBLYAI_API_KEY).
4. `python3 -m divine_studio editar <pasta> --rapido` para prévia; sem `--rapido` para a final.
5. Toda regra nova vai para `config/` (YAML) ou `python3 -m divine_studio regra "..."`, nunca escondida no código.

## Onde está cada coisa (mapeado em 27/10/2026)

- **Projetos de vídeo**: `Videos/<tema>/` (Bio Ritmo Pacaembu, Bumbum Up, CMSlim, Deficiencia Cabelo, Endolaser, HIPRO, Laser CO2, Microagulhamento, Parodia Ovinho, Pele Cabelo Hormonios, Pessoal, Procedencia Seguranca, Protocolo Divine, Spa Pedras Quentes, Stories Institucionais, Suplementos 35+, Trend 4 porcento, Trend Espelho). Pacotes soltos na raiz: `Diario CO2 - Pacote/`, `POV Teste/`, `Repost POV Frutas/`, `Stories POV Chegada/`, `Pellets - Video Explicativo/`.
- **Prontos para postar**: subpastas `Pronto para postar/` (Bio Ritmo Pacaembu, Suplementos 35+, Laser CO2/Pacote 2026-10-20).
- **Versões substituídas**: `Videos/_Versoes anteriores/`. **Trilhas originais**: `Videos/Trilhas/`.
- **Legendas e roteiros**: arquivos `Legenda*`/`*COPY.md` dentro de cada projeto (ver o mapa).
- **Código**: só existe o template de antes e depois para TV (uso interno): `Bumbum Up - Uso Interno/Template_codigo/` (`common.py`, `static.py`, `video.py`, `audio.py`, LEIA-ME) e `Endolaser Bracos - Uso Interno/Template_codigo/static_endolaser.py`. Os scripts esperam as fontes em `assets/Biblioteca_Fontes/ttf/` e os logos em `assets/`.
- **Fontes**: `Biblioteca_Fontes/` (`ttf/` com 33 fontes, `previews/`, `baixar_fontes.sh` baixa tudo, `LEIA-ME.md` com as combinações A a N).
- **Efeitos sonoros**: `Biblioteca_SFX/` (`1_kit_original_divine/` com 28 WAV livres, `2_extraidos_referencia/` só referência, `gerar_kit_sfx.py` regenera o kit, `teste_combinacoes_sfx.mp3`, `LEIA-ME.md`).
- **Marca**: `Logo_Divine.svg`, `Logo_com_nome_vertical2.png`, `divine-simbolo-1024.png`, `Logo-Preto.png` (raiz).
- **Uso interno (nunca postar)**: `Bumbum Up - Uso Interno/`, `Endolaser Bracos - Uso Interno/`.
- **Tráfego pago (jun/2026)**: briefings Meta, plano Google Ads e ClassPass na raiz.
- **Divine Studio**: `divine_studio/` (código), `config/` (regras em YAML), `tests/`, `projetos/` (um projeto por vídeo; exemplo: `projetos/2026-10-28_teste-co2-loops/`).
- **Templates do Divine Studio**: `divine` (suave), `daniel`, `george`, `tv`, `react`, `pessoal` (ver `docs/DIVINE_STUDIO.md`); fotos oficiais de perfil em `assets/pessoas/` (só no Mac).
- **Índice de vídeos editados pelo Divine Studio**: `docs/INDICE_VIDEOS_EDITADOS.md` (atualizado sozinho a cada exportação final). Os índices antigos `claude/indice-videos-editados*.md` estão só no projeto do app.

## Regras que valem sempre

- Português do Brasil em tudo. Evitar travessões e tracinhos nos textos: usar vírgula, ponto ou dois-pontos.
- Compliance (CFM 2.336/2023 e Anvisa RDC 96/2008) prevalece sobre qualquer pedido. Ver seção 6 do conhecimento.
- Todo vídeo sai em 3 versões, cada uma com hook, combinação de fontes e SFX diferentes.
- Um ajuste pedido em um vídeo vira regra para os próximos: registre em `docs/CONHECIMENTO_DIVINE.md` (seção "Regras aprendidas", com data).
- Hook novo criado: acrescente em `docs/BANCO_HOOKS.md` com o próximo número livre e atualize o histórico de fontes e SFX.
- Projeto novo: acrescente uma linha em `docs/MAPA_DO_REPOSITORIO.md`.
- Não apagar nada: o que for descartado vai para `_arquivo/`.
- Perguntar o mínimo: deduzir pelo repositório e entregar resultado.
