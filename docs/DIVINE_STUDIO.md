# Divine Studio

Ferramenta de edição de vídeo da Divine Medical Spa. Transforma os brutos em 3 versões prontas para postar, aplicando sozinha a marca, o template suave/glamour, o rodízio de fontes e SFX, a trilha original e o revisor de compliance.

## Instalação no Mac (uma vez)

```bash
cd "~/Documents/Claude/Projects/Divine Medical Spa Marketing"
brew install ffmpeg                       # se ainda não tiver
pip3 install -r requirements.txt
bash Biblioteca_Fontes/baixar_fontes.sh   # 33 fontes
pip3 install faster-whisper               # transcrição local (corte limpo e legenda da fala)
python3 -m divine_studio verificar        # confere tudo
```

Transcrição na nuvem em vez da local: `export ASSEMBLYAI_API_KEY=...`. Limpeza de voz com IA para ruído pesado: `export ELEVENLABS_API_KEY=...` (sem a chave, usa a redução de ruído do próprio FFmpeg).

## Painel (o jeito mais fácil)

`python3 -m divine_studio painel` abre `http://127.0.0.1:8765` (só na sua máquina): criar projeto, arrastar os brutos, escolher template, revisar, ver o corte, gerar prévias, comparar as versões lado a lado, aprovar e exportar a final, copiar a legenda e ensinar regras novas. Usa só a biblioteca padrão do Python.

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

# vários brutos do mesmo procedimento: pacote por categorias (longo, médio, curto, ultracurto, viral, POV,
# cortes, bastidores, TV e Stories), cada peça numa pasta com nome claro
python3 -m divine_studio pacote projetos/2026-10-28_co2-no-corpo --renderizar --rapido
python3 -m divine_studio pacote projetos/2026-10-28_co2-no-corpo --categorias reels-curto,tv

# legenda do post (também sai sozinha no editar quando o projeto não tem legenda)
python3 -m divine_studio legenda projetos/2026-10-28_co2-no-corpo

# efeitos EC/EV: lista e prancha com todos
python3 -m divine_studio efeitos
python3 -m divine_studio efeitos --prancha prancha_efeitos.jpg

# registrar um ajuste como regra permanente
python3 -m divine_studio regra "Texto do CTA antecipado sempre em duas linhas no máximo"
```

Saída de cada projeto:
- `saida/AAAA-MM-DD_reels_<tema>_V1_<hook>.mp4` (e V2, V3); `_autorizacao-pendente` no nome quando falta a autorização de imagem; `_PREVIA` nas prévias
- `saida/legenda.txt` pronta para copiar
- `relatorio.md`: hook, código do banco, fontes, SFX, duração, tamanho e a linha de compliance de cada versão
- `trabalho/V1_quadros.jpg`: folha de contato para conferir rápido

## Templates (`template:` no projeto.yaml)

| Template | Para quê | O que muda |
|---|---|---|
| `divine` | Reels e Stories da clínica (padrão) | Suave/glamour: header, hook, CTA antecipado, mensagens, fechamento com logo, endereço, aviso e RT |
| `daniel` | Vídeos do @drdanielmendess | Placas verde-petróleo; cartão com a foto oficial, nome, selo verificado e @ (≈3,5 a 9 s e antes do fim) |
| `george` | Vídeos do Enf. George | Placas navy; selo do tema a partir de 3,3 s; cartão com COREN; placa navy 100% opaca no terço de baixo cobrindo a legenda queimada (a nova vai em cima; `texto_da_fala: ocr` lê a queimada) |
| `tv` | TV 16:9 da clínica | Janela 4:5 com cantoneiras sobre o vídeo desfocado, painel esquerdo com mensagens a cada 4 s, painel direito fixo (`tv: {tratamento, indicacao}`), tela final de 6 s, rodapé com RT; 1 versão, 0,72× e dissolve 0,8 s |
| `react` | Tela dividida | `clipes_referencia` em cima (com `credito` fixo), quem fala embaixo, legenda logo acima da cabeça |
| `pessoal` | Perfil pessoal do Renato | Sem nenhuma marca Divine; Bodoni Moda caixa alta + Great Vibes; traço fino (linha, arco ou moldura, um por versão); sem RT |

Medidas e textos fixos de cada template ficam em `config/templates.yaml`; pessoas (nome, registro, @, foto, cor) em `config/pessoas.yaml`.

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
| Efeitos EC/EV | 21 módulos na versão suave (camadas, letra a letra, riscado, digitando, checklist, contador, linha do tempo, círculo + spoiler, notificação, artigo, tweet, pergunta, chat, gráfico, zoom digital, PiP, cortina, filme, vidro, texto atrás da pessoa); `efeitos:` no projeto ou na versão, por `tipo` ou `codigo` (EC06, EV17...); no máximo um a cada 1,5 s, o anterior sai quando o próximo entra |
| Pacote | Uma pasta por peça em `projetos/<projeto>-pacote/NN_categoria/`, com duração alvo por frases inteiras da fala (ou o miolo dos clipes), hooks sorteados sem repetir entre peças e legenda própria |
| Legenda do post | Gancho na 1ª linha, CTA antecipado, corpo corrido, CTA final com WhatsApp e endereço, aviso, RT e 8 a 12 hashtags (config/legenda.yaml); passa pelo revisor |
| Registro | Ao exportar a final: `docs/INDICE_VIDEOS_EDITADOS.md`, histórico de fontes e SFX no `docs/BANCO_HOOKS.md` (com a sugestão do próximo) e linha nova no `docs/MAPA_DO_REPOSITORIO.md` |
| Revisão viral | Nota de 0 a 10 por versão (hook, retenção, leitura, áudio, glamour, compliance) com dicas no `relatorio.md` |
| Compliance | Bloqueia antes e depois fora do uso interno, "Dr. George", marca Divine no template pessoal, música de fora sem licença, percentual, promessa, prazo garantido, comparação, medicamento, "implante hormonal", "nutrólogo" e "comenta PALAVRA"; avisa travessão, numeração, antes e depois e linguagem promocional; exige aviso e RT na legenda |
| Exportação | x264 slow, tune film, aq-mode=3, crf 17; −16 LUFS; refaz em 2 passes se passar de 30 MB |

## Arquivos

- `divine_studio/`: código (cli, ingest, transcricao, corte, voz, legendas, hooks, templates/divine, text, brand, compositor, render, audio, exportar, compliance, rodizio)
- `config/`: tudo que é regra fica aqui, em YAML (marca, fontes, sfx, exportacao, compliance, preferencias, historico)
- `tests/`: `python3 -m pytest tests -q`

## Roteiro das próximas fases

1. **Fase 2 (feita em 28/10/2026)**: transcrição com tempo por palavra, corte limpo, limpeza de voz, legenda da fala palavra a palavra, mensagens sincronizadas com a fala, sorteio e cadastro de hooks, SFX de transição com limite de famílias.
2. **Fase 3 (feita em 28/10/2026)**: templates Daniel, George (com OCR da legenda queimada), TV, React e Pessoal; revisor ampliado e nota de revisão viral.
3. **Fase 4 (feita em 28/10/2026)**: efeitos EC/EV (21 módulos; os sem módulo estão marcados em `config/efeitos.yaml`), recorte da pessoa opcional (mediapipe ou rembg), pacote por categorias, legenda do post e registro automático.
4. **Fase 5 (feita em 28/10/2026)**: painel web local (arrastar vídeos, revisar, comparar as versões lado a lado, aprovar) e `README.md`.

### Próximos passos sugeridos
- Rodar cada template num vídeo real no Mac e comparar com as referências aprovadas (TV "CO2 em manchas senis", Reels lipedema suave, Reels do George, Endolaser); ajustar medidas em `config/templates.yaml`.
- Colocar as fotos oficiais em `assets/pessoas/` e o logo PNG oficial na raiz.
- Efeitos ainda sem módulo (marcados em `config/efeitos.yaml`): órbita de cards, parede de imagens, quebra de moldura, vertigem e similares.
