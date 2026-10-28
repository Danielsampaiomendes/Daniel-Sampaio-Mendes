# Divine Studio

Ferramenta de edição de vídeo da Divine Medical Spa. Transforma os brutos em 3 versões prontas para postar, aplicando sozinha a marca, o template suave/glamour, o rodízio de fontes e SFX, a trilha original e o revisor de compliance.

## Instalação no Mac (uma vez)

```bash
cd "~/Documents/Claude/Projects/Divine Medical Spa Marketing"
brew install ffmpeg                       # se ainda não tiver
pip3 install -r requirements.txt
bash Biblioteca_Fontes/baixar_fontes.sh   # 32 fontes
pip3 install faster-whisper               # transcrição local (corte limpo e legenda da fala)
python3 -m divine_studio verificar        # confere tudo
```

Transcrição na nuvem em vez da local: `export ASSEMBLYAI_API_KEY=...`. Limpeza de voz com IA para ruído pesado: `export ELEVENLABS_API_KEY=...` (sem a chave, usa a redução de ruído do próprio FFmpeg).

## Uso

```bash
# 1. criar o projeto (pasta com bruto/, trabalho/, saida/ e projeto.yaml modelo)
python3 -m divine_studio novo "co2 no corpo"

# 2. colocar os vídeos em projetos/AAAA-MM-DD_co2-no-corpo/bruto/ e conferir cada um
python3 -m divine_studio info projetos/2026-10-28_co2-no-corpo/bruto/IMG_1234.MOV

# 3. preencher o projeto.yaml (clipes, hooks das 3 versões, mensagens, fechamento, legenda)

#    vídeo falado: ligue corte_limpo e legendas no projeto.yaml e confira o corte antes
python3 -m divine_studio transcrever projetos/2026-10-28_co2-no-corpo   # texto em trabalho/transcricao.md
python3 -m divine_studio cortar projetos/2026-10-28_co2-no-corpo        # o que sai e o que fica em trabalho/cortes.md

#    hooks: sortear 3 do banco (positivo, curiosidade, negativo) ou cadastrar um novo
python3 -m divine_studio hooks sortear --tema "laser co2"
python3 -m divine_studio hooks novo "Frase do hook / com *destaque.*" --tipo curiosidade

# 4. revisar o compliance antes de renderizar
python3 -m divine_studio revisar projetos/2026-10-28_co2-no-corpo

# 5. prévia rápida e, depois de aprovada, a versão final
python3 -m divine_studio editar projetos/2026-10-28_co2-no-corpo --rapido
python3 -m divine_studio editar projetos/2026-10-28_co2-no-corpo

# só algumas versões
python3 -m divine_studio editar projetos/2026-10-28_co2-no-corpo --versoes V1,V3

# registrar um ajuste como regra permanente
python3 -m divine_studio regra "Texto do CTA antecipado sempre em duas linhas no máximo"
```

Saída de cada projeto:
- `saida/AAAA-MM-DD_reels_<tema>_V1_<hook>.mp4` (e V2, V3); `_autorizacao-pendente` no nome quando falta a autorização de imagem; `_PREVIA` nas prévias
- `saida/legenda.txt` pronta para copiar
- `relatorio.md`: hook, código do banco, fontes, SFX, duração, tamanho e a linha de compliance de cada versão
- `trabalho/V1_quadros.jpg`: folha de contato para conferir rápido

## O que a ferramenta faz sozinha

| Etapa | Regra aplicada (fonte: docs/CONHECIMENTO_DIVINE.md) |
|---|---|
| Transcrição | Tempo por palavra (AssemblyAI ou Whisper local), em cache; corrigir palavra em `trabalho/transcricoes/*.editado.json` ou `correcoes:` no projeto |
| Corte limpo | Tira muletas ("hum", "ééé"), a tentativa anterior quando a pessoa recomeça a frase, e encurta pausas acima de 0,9 s para ~0,5 s; corte seco entre trechos do mesmo take, dissolve entre clipes diferentes; `remover_trechos` para o que o automático não pegar |
| Voz | Mede o ruído e escolhe a limpeza: só highpass, leve (redução FFT + compressor), forte (RNNoise) ou ElevenLabs Voice Isolator; loudnorm −16 LUFS na exportação |
| Legenda da fala | Fonte fixa da marca, blocos de até 4 palavras, palavra falada em dourado, fade curto sem piscar, acima do CTA e fora da UI; some no fechamento; passa pelo revisor |
| Mensagens na fala | `na_fala: "frase"` faz a mensagem entrar quando a frase é dita (nunca em cima do hook) |
| Hooks | `hook_id` sozinho usa a frase do banco; `hook: auto` sorteia positivo, curiosidade e negativo fora dos usados por último e guarda a escolha em `trabalho/hooks_sorteados.json` |
| Ingestão | HDR/HLG para SDR (tonemap hable); recorte no formato com foco ajustável; câmera lenta com mescla de quadros; dissolve curto entre clipes; zoom lento "respirando"; leve grade quente e vinheta |
| Modo alta qualidade | Liga sozinho quando a fonte é menor que 1080p: denoise leve, upscale Lanczos, nitidez, intermediário crf 13 e final HEVC (hvc1) |
| Marca | Logo oficial (trevo PNG; SVG como reserva) no topo em todo quadro e empilhado no fechamento; nunca "Divine Medical Spa" em texto comum |
| Texto | `*palavra*` vira destaque dourado; `/` quebra linha; entra com fade e deslize lento, sai com fade; tempo de leitura automático; escurecimento suave atrás; área segura do Instagram |
| Fontes | 3 combinações diferentes por vídeo, evitando as 6 últimas usadas (config/historico.yaml) |
| SFX | Um som leve na abertura, um whoosh bem baixo na troca entre clipes diferentes (no máximo 3, longe um do outro) e um no fechamento; nunca o mesmo som duas vezes na versão, até 4 famílias e 1 impacto por vídeo, variações fora das usadas por último; sem ping a cada texto |
| Trilha | Lounge original sintetizada (84 bpm), entrada gradual, ducking automático sob a fala |
| Fechamento | 2,6 s: logo empilhado, frase, pill de CTA, endereço oficial, aviso de resultados e RT; escurece para o loop |
| Compliance | Bloqueia percentual, promessa, prazo garantido, comparação, medicamento, "implante hormonal", "nutrólogo" e "comenta PALAVRA"; avisa travessão, numeração, antes e depois e linguagem promocional; exige aviso e RT na legenda |
| Exportação | x264 slow, tune film, aq-mode=3, crf 17; −16 LUFS; refaz em 2 passes se passar de 30 MB |

## Arquivos

- `divine_studio/`: código (cli, ingest, transcricao, corte, voz, legendas, hooks, templates/divine, text, brand, compositor, render, audio, exportar, compliance, rodizio)
- `config/`: tudo que é regra fica aqui, em YAML (marca, fontes, sfx, exportacao, compliance, preferencias, historico)
- `tests/`: `python3 -m pytest tests -q`

## Roteiro das próximas fases

1. **Fase 2 (feita em 28/10/2026)**: transcrição com tempo por palavra, corte limpo, limpeza de voz, legenda da fala palavra a palavra, mensagens sincronizadas com a fala, sorteio e cadastro de hooks, SFX de transição com limite de famílias. Falta: OCR para vídeo com legenda queimada (entra com o template George, fase 3).
2. **Fase 3**: templates TV 16:9 (janela 4:5 com cantoneiras, painéis laterais), Daniel (foto oficial, selo verificado), George (navy + legenda que cobre a queimada), React/tela dividida e pessoal.
3. **Fase 4**: efeitos EC/EV com recorte da pessoa (texto atrás da cabeça, capa de revista, card 3D, círculo + freeze + spoiler), pacote por categorias, registro automático no índice de vídeos.
4. **Fase 5**: interface web local para arrastar vídeos, comparar as 3 versões lado a lado e aprovar.
