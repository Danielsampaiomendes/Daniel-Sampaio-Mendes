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

**Atualizar:** os dois `.command` baixam sozinhos a versão nova do GitHub (ramo `claude/ola-8lmaep`), fecham o painel antigo e abrem o novo. No painel, o botão ⟳ Atualizar faz o mesmo sem sair. Arquivos seus que seriam trocados vão antes para `_arquivo/atualizacao-<data>/`; vídeos e fontes não são tocados. Pasta antiga sem git: `python3 divine_studio/atualizar.py` liga ao GitHub (ou rode o comando de instalação da atualização que o Claude passou).

No iPhone: `Divine Studio iPhone.command` (ou `painel --celular`) libera o painel na rede Wi-Fi com um código de 6 dígitos; no Safari, Compartilhar > Adicionar à Tela de Início.

Aba **Edição** do painel: linha do tempo sobre a prévia (efeitos e mensagens no segundo exato, arrastando; ponto do círculo/zoom com um clique no vídeo; vermelho quando dois itens disputam o mesmo momento), hook e combinação de fontes por versão com amostra visual, e textos (selo, CTA, mensagens, fechamento) sem mexer no YAML. O que tem momento fixo tem prioridade: as mensagens em sequência desviam dele.

Tags e objetivo do post no painel; botão **Formatos** (Stories, Feed 4:5/1:1, TV) gera a mesma edição em outros tamanhos (`python3 -m divine_studio formatos <pasta> [--formatos stories,tv] [--final]`); **carrossel** com rascunho por fórmula, editor de cards e exportação em PNG (`carrossel novo|exportar`, regras em `config/carrossel.yaml`).

**Biblioteca** (tela no topo do painel): pastas `assets/marca`, `assets/pessoas`, `assets/tecnologias`, `assets/clinica` e `assets/produtos`, com a lista do que cada uma precisa ter (`config/biblioteca.yaml`). O app mostra o que falta, pede dentro do projeto a foto da tecnologia do tema e usa sozinho: logo oficial em tudo, foto oficial nos cartões e na citação, foto da tecnologia na capa do carrossel e do post. Trocar uma imagem guarda a anterior em `_arquivo/biblioteca/`.

**Post estático** (imagem única): `post novo "tema"` ou "Novo post" no painel; mesmos layouts do carrossel num card só, exportado de uma vez em Feed 4:5, Stories e TV (`post exportar <pasta>`, entrega em `entregas/AAAA-MM/Posts/`).

**Antes e depois (uso interno, nunca postar)**: `antesdepois novo "título"` ou "Antes e depois" no painel. Mande os pares (antes e depois separados ou uma montagem lado a lado) e marque o ângulo: sai no padrão aprovado do Bumbum Up (fotos inteiras, mesmo tamanho, sem zoom nem corte, aviso "Uso exclusivo em consulta" e RT) em TV 16:9 (com vídeo: abertura, um ângulo por vez, grade, fechamento), Stories 9:16 e Feed 4:5. Só gera com `autorizacao_imagem: sim`; arquivos com `NAO-POSTAR` no nome, em `entregas/AAAA-MM/Uso interno (nao postar)/`, na coluna "Uso interno (consulta)" da Programação, e o painel não deixa marcar como postado ou agendado.

**Organização do painel (02/11/2026)**: menu Início · Nova edição · Projetos · Vídeos · Programação · Ideias e IA · Referências · Imagens (no iPhone, barra fixa embaixo). Início mostra atalhos por tipo, "continuar de onde parou", o que está para postar e os últimos vídeos. A lista de projetos só aparece em Projetos. Dentro do projeto: passo a passo (vídeos, ajustes, prévias, escolher, postar), "Edição automática" e "Gerar prévias" à mão e o resto em "⋯ Mais"; o projeto.yaml fica em "Avançado". **Vídeos** é a biblioteca de todos os vídeos (★ Melhores, Finais, Prévias, Postados, Todos), por projeto ou em grade, com Validar, Postei, Salvar e Editar.

**Rodada 02/11/2026 (noite)**
- **Anúncio (conversão)** (Nova edição > Anúncio): roteiro gancho com a dor, problema, solução, prova e um pedido só; texto sempre no topo (o botão do anúncio cobre a parte de baixo); cartão final com o botão ("Saiba mais ›", "Enviar mensagem", "Cadastre-se"); sai em Reels, Stories, Feed 4:5 e 1:1; copy do anúncio em 3 variações (texto principal, título, descrição, botão) em `saida/copy_anuncio.md`, revisada pelo compliance. Regras em `config/anuncios.yaml`.
- **Atenção prevista**: a cada prévia, o app mede (a cada 0,5 s) se há algo novo na tela, movimento e fala; trechos fracos aparecem tracejados em vermelho na linha do tempo e na conversa da versão, com a causa e uma proposta que se aplica com um toque. Depois de postado, o tempo médio assistido do Instagram mostra se a saída bateu com o risco previsto.
- **Edição de editor**: os efeitos automáticos caem na batida da música (trilha Divine pelo bpm; música própria pela análise do andamento) e, quando a fala cita algo que tem foto na Biblioteca (ex.: "Endolaser"), a foto entra naquele segundo num cartão dourado (b-roll automático).
- **Aprende o que evitar**: efeitos com nota negativa nas suas peças saem do sorteio do ritmo; os que funcionam aparecem mais; "Evitar ..." aparece no que o app aprendeu.
- **Tela dividida**: "♻ Usar esta mesma reação com outro vídeo" copia o projeto e troca só o vídeo analisado.

**Rodada 02/11/2026 (tarde)**
- **Cortes de vídeo longo** (Nova edição > Cortes de vídeo longo, ou `python3 -m divine_studio cortes <pasta>`): o vídeo longo vira 3 curtos (12 a 25 s), 2 médios (28 a 45 s), 1 longo (55 a 90 s), "melhores momentos" (as frases mais fortes de partes diferentes, em ordem) e 2 Stories. Com a fala transcrita, cada corte é de frases inteiras começando pela mais forte (pergunta, número, "você", palavras de força); sem transcrição, segue as pausas. Os cortes se espalham pelo vídeo. Regras em `config/cortes.yaml`.
- **Conversa sobre cada edição** (💬 nas Versões; abre sozinha depois da final): o app dá nota, veredito ("vai viralizar?") e o que mudaria nesta versão e no próximo vídeo; com a chave da IA, um comentário olhando o vídeo. Você responde com reações rápidas (vai viralizar, média, mais/menos efeitos, mais/menos sons, mais rápido/calmo, texto maior), estrelas e texto livre. Isso muda os próximos vídeos: intervalo dos efeitos automáticos, volume dos sons e tamanho dos textos (`divine_studio/feedback.py`); o texto entra em "Regras aprendidas".
- **Tela dividida** (Nova edição > Tela dividida): você em Vídeos brutos e o vídeo analisado no cartão "Tela dividida". Automático: vídeo vertical → cabecinha (vídeo em tela cheia, você no círculo do canto); quadrado → 60% vídeo, 40% você; deitado → vídeo inteiro em 50% sobre fundo desfocado. Dá para escolher.
- **Divine TV** (`/tv`, botão 📺 TV): passa em loop infinito os vídeos de TV finais e os marcados 📺 Na TV na biblioteca Vídeos, com fusão entre eles; duplo toque = tela cheia.
- **Crescimento** (menu): por perfil, seguidores (Instagram ou anotados), ritmo e projeção para 30 e 90 dias contra a meta, plano de hoje, metas da semana (Reels, carrossel, Stories, dias sem postar, envios e salvamentos por alcance) e o que o algoritmo valoriza agora (`config/algoritmo.yaml`, revisado toda semana).
- **Integrações** (Ideias e IA): 📸 Quadro na Edição tira o quadro para Higgsfield/Canva; Nano Banana edita a imagem direto do app com `GEMINI_API_KEY` (`config/integracoes.yaml`).

**Efeitos e sons virais (02/11/2026)**: 9 efeitos no estilo dos edits que mais viralizam (zoom na batida, flash branco ou dourado, glitch RGB, giro 360°, tremor de impacto, zoom blur, pulso no ritmo, revelar do desfoque, P&B que volta a cor; `divine_studio/efeitos_viral.py`), cada um com som sugerido; **velocity** no clipe (acelera, câmera lenta, acelera); 8 transições a mais (vento, pixelizar, espremer, cortina, diagonal, grãos, cinza, fatias). Kit de **sons virais** sintetizado pelo app, sem direitos autorais (boom grave, drop sub, whoosh rápido, glitch, flash, scratch, coração, zap, estalo de dedos, riser de tensão; `divine_studio/sfx_viral.py`), criado sozinho na primeira vez. O ritmo viral usa os mais elegantes; o Vídeo Épico usa todos e alterna uma transição por corte.

**Dois perfis do Instagram (02/11/2026)**: @dvmedicalspa e @drdanielmendess (`config/contas.yaml`). Cada projeto vai para o perfil do template (Daniel = @drdanielmendess, o resto = @dvmedicalspa; "Perfil do Instagram" na aba Projeto troca). Programação > Conectar Instagram aceita um token que alcança as duas Páginas ou um token por perfil (somam); métricas puxadas da conta certa; Programação e Vídeos filtram por perfil; o aprendizado e a versão IA usam o histórico do perfil (com 3+ peças). Programação mostra a semana (o que está agendado em cada dia). Avisos discretos no canto e atalhos na Edição (espaço, ← →, S, Delete, ⌘S).

**Linha do tempo estilo CapCut / Edits (02/11/2026)**: trilha de **clipes** (toque para aparar início e fim, velocidade de 0,25x a 3x, reverso, volume, zoom, sem som, transição na entrada: dissolver, corte seco, preto, flash, deslizar, subir, zoom, círculo, desfoque, radial; mover, duplicar, remover) e **✂ Dividir aqui** no ponto do vídeo. Efeitos e sons automáticos (ritmo viral e rodízio) aparecem **tracejados**; "Trazer para a linha do tempo" vira tudo item normal, editável (o projeto fica com `ritmo_fixo: true` e `sfx_automaticos: false`). Cartões **Cor e filtro** (natural, dourado, cinema, suave, clínico, filme antigo, P&B + brilho, contraste, saturação, temperatura) e **Áudio** (volume do som do vídeo, trilha liga/desliga e volume, música sua com licença). Filtros e transições em `config/edicao.yaml`.

**Padrão viral luxo** (todo Reels e Stories; `config/viral.yaml`): câmera elegante no vídeo inteiro e uma interrupção de padrão a cada 2,6 a 3,4 s (desfoque de lente, zoom, luz dourada, congelar), luz dourada na abertura e pausa antes do CTA, só onde você não colocou efeito e diferente em cada versão. A lista de retenção e as regras de cara de luxo ficam no mesmo arquivo. `ritmo: calmo` desliga; a TV fica sempre calma.

**Vídeo Épico** (`ritmo: epico`, ou "Vídeo Épico" no menu Nova edição e no seletor Ritmo): abertura com cartão 3D girando e luz dourada, chicote em cada corte, vertigem, cartão 3D, parallax e congelar a cada 1,3 a 1,9 s, câmera elegante mais forte, cor de cinema e som em cada movimento.

**Nova edição** (botão no topo da lista): Vídeo, Vídeo Épico, Stories, Carrossel, Post, TV e Antes e depois; cada um cria o projeto já no formato certo. A lista de projetos filtra por tipo.

**Galeria**: só as peças validadas (★ Validar nas versões, final exportada ou postada), com capa, vídeo tocando ao passar o mouse e "Editar" para voltar ao projeto.

**Copy para a dublagem**: "🎙 Gravar voz aqui" abre a copy sugerida (sua copy salva, o *COPY.md do projeto ou montada do gancho, mensagens e fechamento), editável, com "✦ Melhorar com IA"; ao gravar, a copy rola num teleprompter com contagem de 3 s.

**Importar o que já existe**: `python3 -m divine_studio importar ["<pasta Divine Medical Spa Marketing>"] [--simular] [--copiar]` (ou "Trazer o que já existe" em Nova edição). Cada tema vira um projeto com atalhos para os brutos e editados, "Pronto para postar" entra aprovado, legendas e copies vêm junto. Nada é movido nem apagado; rodar de novo só acrescenta.

**Efeitos 3D e espaciais** (na linha do tempo, com miniatura): câmera elegante (perspectiva + zoom que deriva devagar), cartão 3D (o vídeo vira um cartão de borda dourada que inclina ou gira), parallax 2.5D e efeito vertigem (o fundo anda/aproxima e a pessoa fica; precisam do recorte com mediapipe), transição chicote (whip pan com borrão de movimento), congelar e aproximar, desfoque de lente (modo retrato) e luz dourada (light leak). `camera_elegante: true` no projeto (ou "Câmera elegante" no painel) aplica a câmera no vídeo inteiro, mudando a direção a cada take. Código em `divine_studio/efeitos3d.py`.

**Qualidade máxima** (`qualidade: maxima` ou "Qualidade máxima" no painel): estabilização vid.stab em 2 passes, redução de ruído (hqdn3d ou nlmeans forte), upscale até a resolução da peça (Real-ESRGAN com IA se `realesrgan-ncnn-vulkan` estiver instalado; senão Lanczos + nitidez) e câmera lenta suave (minterpolate) nos clipes com `velocidade` menor que 1. Cache em `trabalho/qualidade/`; ajustes em `config/exportacao.yaml > qualidade`.

Incorporado das skills Divine (01/11/2026): fontes no padrão CAIXA ALTA em degradê dourado + cursiva (O1 a O6, rodízio em `config/fontes.yaml`), legenda da fala com palavra falada maior e palavra-chave em Lora itálico, voz com a cadeia da video-pro e −14 LUFS no Instagram (−16 na TV), grão fino, revisão anti cara de IA e dobra de 125 caracteres, CORTE com "Leia na legenda", durações do pacote da skill de categorias, 5 efeitos da skill dos 17 (gancho digitado, prompt, CTA WhatsApp, frame de título, chip; códigos D01 a D17 em `config/efeitos.yaml`).

## Uso

```bash
# edição automática: com os vídeos em bruto/, monta o projeto.yaml inteiro (tema, cortes, hooks, textos)
# e já gera as 3 prévias; textos por tema em config/roteiros.yaml
python3 -m divine_studio auto projetos/2026-10-28_co2-no-corpo --previa

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
