# Divine Studio

Ferramenta de edição de vídeo da Divine Medical Spa. Transforma os brutos em 3 versões prontas para postar, aplicando sozinha a marca, o template suave/glamour, o rodízio de fontes e SFX, a trilha original e o revisor de compliance.

## Pontos "!" na linha do tempo, previsão de público e dublagem de trecho (08/11/2026)

- **"!" na linha do tempo** (aba Ajustar) e no cartão de cada versão do passo 3: cada ponto mostra o segundo, o
  motivo e o que fazer com um toque. Os pontos são **da versão** que está na linha do tempo (seletor "Versão na linha
  do tempo"; tocar em "Resolver na linha do tempo da V2" no passo 3 já abre a V2). Cores: vermelho = refazer (pode
  quebrar o engajamento) ou compliance (não dá para ignorar), laranja = **confira esta frase** (pode ser promessa),
  dourado = **possivelmente dublar** (fala difícil de entender, voz baixa, frase recomeçada), cinza = vale conferir
  (fala corrida, efeitos demais, leitura antiga do Higgsfield). Ações: ✦ pôr o efeito proposto, ✂ tirar a frase (vai para
  `remover_trechos`), 🎙 dublar este trecho, Aa corrigir a legenda, Ignorar (guardado em `alertas_ignorados`).
  Regras e limites: `config/alertas.yaml`; código: `divine_studio/alertas.py`.
- **🎙 Dublar este trecho**: abre o gravador com a frase no teleprompter, começando no segundo certo e mostrando
  quantos segundos o trecho tem. Só aquele trecho fica com a voz original muda (`audio.dublagem[].fim`); o resto do
  vídeo mantém a sua voz, e a legenda passa a ser a da gravação nova. Ao enviar, o app tira o silêncio do começo e do
  fim da gravação e ajusta até 15% de velocidade, sem mudar o tom, para caber no trecho (`config/preferencias.yaml >
  dublagem`). Se mesmo assim passar, a voz original fica muda até o fim da gravação e o painel avisa; se ficar curta
  demais, também avisa. A gravação inteira fica guardada em `trabalho/dublagem/voz_*.wav`.
- **Dublagens e efeitos presos à fala** (`divine_studio/ancoras.py`): cada dublagem e cada efeito guarda as palavras
  do trecho. Depois de um corte (✂ Tirar esta frase, corte limpo), a prévia seguinte põe cada um onde as palavras
  dele estão agora e grava os segundos novos no projeto.yaml. Se a frase saiu do vídeo, o item fica de fora daquela
  edição (nada é apagado) e aparece um "!" "A dublagem ficou de fora". ✂ num projeto sem corte limpo liga
  `corte_limpo: so_frases`: só as frases marcadas saem, sem mexer em pausas e muletas.
- **✓ Aprovar** só anota o pedido. A versão conta como aprovada, gostei e validada (Galeria e aprendizado) quando a
  final sai pelo revisor. Se a final for barrada, o cartão da versão diz por quê.
- **🎙 Gravar o pedido final**: entra logo depois da última palavra, soma à sua voz (não cala nada) e pode seguir por
  cima do cartão final.
- **🎬 Regravar** (abertura longa, fala corrida): dublar não muda o tempo da imagem, então esses pontos pedem gravar o
  vídeo de novo, com o texto pronto para copiar.
- **Compliance na fala, em três camadas** (`compliance.achados_na_fala`, regras em `config/compliance.yaml`):
  Antes de conferir, os números falados viram algarismos ("em duas semanas" = "em 2 semanas"), para a mesma promessa
  ter o mesmo nível dos dois jeitos.
  1. **Vermelho** (porcentagem, também falada; promessa direta como "você vai perder 5 kg"; prazo + resultado + alvo do
     tratamento na mesma frase, como "na primeira sessão a gordura some" ou "em quinze dias você vê a diferença"):
     trava o ✓ Aprovar, a final e o postar sozinho até a frase sair ou ser dublada. Não se ignora.
  2. **Laranja, "Confira esta frase"** (prazo ou quantidade sem alvo de tratamento, que também aparece em frase
     correta: "o roxinho desaparece em três dias"; e o vermelho que vem negado, como "nenhum tratamento tem resultado
     garantido", ou como orientação, "antes e depois da sessão, beba água"): trava até você tocar em **✓ Conferi:
     é informação, não promessa** (fica anotado em `compliance_conferido`, com a data), tirar ou dublar. Exame,
     consulta, retorno e medidas não perguntam. A frase também é conferida junto com a seguinte, para pegar a promessa
     cortada por uma pausa.
  3. **Toda saída da final pelo app** (🤖 postar sozinho, 🚀 Publicar agora e ⬇ Salvar no iPhone) pede que você leia
     a fala inteira da final uma vez. O revisor por regras pega os jeitos comuns de prometer, não todos; antes de ir ao
     ar, uma pessoa leu. Se a final mudar, o app pede a leitura de novo. Cada final grava `trabalho/fala_final_<versão>.json` (a fala
     e o arquivo da final daquela versão): postar a V1 confere a fala da V1, e só se for do mesmo arquivo que vai ao ar.
- **Vídeo com fala sem transcrição** (modelo de fala ausente ou com falha): o "!" vermelho **"A fala deste vídeo ainda
  não foi lida"** aparece no começo da linha do tempo, e o ✓ Aprovar, a final e o postar ficam travados até a
  transcrição existir (🎤 Instalar a transcrição). O app sabe que há fala pelo som de cada bruto (`tem_fala`, gravado
  pela edição automática), não pela legenda ligada: sem transcrição a edição automática desliga a legenda e o corte
  limpo, e antes a fala passava sem ninguém ler. As prévias continuam saindo, para você ver a edição.
- **Quem desmente uma promessa** ("é mito que a celulite some em duas semanas", "cuidado com quem promete que...", "a
  gordura não some em uma sessão") pede **Confira**, não trava sem saída. Duas frases inteiras seguidas ("O retorno é
  em duas semanas." "A celulite melhora com o tratamento certo.") não viram uma promessa juntas.
- **👥 Previsão de público** em cada versão do passo 3: "De 100 pessoas, cerca de X passam dos 3 s, Y chegam à metade
  e Z veem até o fim". É uma estimativa para comparar as versões. Três tipos de público (`config/previsao.yaml`).
  Depois de 3 peças postadas com o tempo médio assistido (puxado do Instagram, ou digitado em Programação > Postado:
  "seg. assistidos"), o **ritmo de saída** se ajusta para o modelo reproduzir o tempo médio real das suas peças, por
  perfil, sempre com a previsão da final **que foi ao ar** (congelada ao marcar como postado em
  `trabalho/previsao_postada_<versão>.json`; prévias novas não mudam a conta). Só o tempo médio é calibrado (é a única medida que a Meta entrega); 3 s, metade e por público continuam
  estimativa e aparecem arredondados de 5 em 5. Reels curto que roda em loop (tempo médio acima de 85% da duração,
  porque o Instagram conta as repetições) fica fora da calibração e a frase diz quantas peças ficaram de fora. A peça
  que segura muito, mas não é loop (60 s com 37 s de média), **entra** e puxa a previsão para cima.
- **Aprendizado**: a retenção de cada peça é "tempo médio real / o que o modelo esperava para aquele vídeo" (um vídeo
  curto não ganha só por ser curto); loop não conta como retenção; o alcance é comparado na mesma idade (7 dias), e
  um post com menos de 3 dias ainda não entra nessa comparação (`config/preferencias.yaml > aprendizado`).
- **Equilíbrio**: com fala, o efeito do meio nasce do que a frase diz, sem sorteio: pergunta aproxima, alerta bate,
  virada muda a luz, dado foca, nome do tratamento revela com brilho. Frase sem motivo fica sem efeito; no máximo 2 a
  cada 10 s (`config/viral.yaml > equilibrio.por_motivo`). Cada motivo tem 3 efeitos ou mais que o modo viral permite: V1, V2 e V3 usam um diferente na mesma frase,
  e a versão IA percorre os mesmos efeitos em outra ordem (pela posição da versão, não pelo número do nome).
- **Higgsfield na linha do tempo**: a leitura do Virality Predictor só vira "!" na versão e no render que foram
  analisados. Depois de tirar uma frase e gerar de novo, ela vira um aviso cinza "leitura de uma prévia antiga".
- **Transcrição**: `modelo_whisper: auto` usa o modelo preciso (`large-v3-turbo`) só quando ele já foi baixado pelo
  botão **🎯 Transcrição mais precisa** do passo 3 (1,6 GB, uma vez, com o passo a passo visível); até lá, o rápido
  (`small`). Uma edição nunca fica parada baixando o modelo. Se o preciso levar mais de 90 s por minuto de fala no
  Mac, as próximas voltam para o rápido sozinhas (`projetos/.transcricao_estado.json`). Brutos já transcritos não são
  refeitos sozinhos (mudaria os cortes de uma edição já aprovada): `transcrever <pasta> --refazer`. Também: silêncio
  ignorado, nomes da clínica como dica e correções que valem em todo projeto (`config/preferencias.yaml > transcricao`).
- **Aprendizado pela retenção**: o tempo médio assistido (da API ou digitado) dividido pela duração entra na nota de
  cada peça, comparado com a mediana das suas peças; "linha cai em" antes de 3 s tira ponto do hook. Isso muda o que o
  sorteio de hooks, fontes e efeitos e a versão IA preferem (`config/preferencias.yaml > aprendizado`).

## Começar a usar (modo simples, 07/11/2026)

1. Dois cliques em `Divine Studio.command`. Na primeira vez depois desta atualização ele prepara o Python próprio do app
   (Python 3.12 em `.venv`, porque o Python do Xcode é antigo) e instala a transcrição: leva alguns minutos. Se aparecer
   aviso, feche e abra de novo.
2. Tela inicial: **solte o vídeo bruto** no quadro (escreva o tema se quiser). O app cria o projeto, envia, transcreve,
   corta, escreve hooks e textos pela sua fala, põe legenda e gera as versões V1, V2, V3 e IA (a aposta do app).
3. No projeto, assista e toque em **✓ Aprovar esta** na melhor. O app exporta a final e guarda o que você gostou
   (fontes, hook, sons, duração): as próximas edições e a versão IA puxam para isso.
4. **Postar**: Baixar o vídeo, Copiar a legenda do post, ✓ Já postei (com o link, o app aprende com as visualizações).
5. **💡 Para a próxima ficar ainda melhor**: o que regravar ou trocar na fala (abertura lenta, apresentação antes do
   assunto, sem pedido no final), o que cortar e o que já funcionou com você. **✦ Pedir mais ideias ao Claude** (com a
   chave da API) e **🔮 Análise de viralidade (Higgsfield)**: copia o pedido para colar no Claude, que roda o Virality
   Predictor e devolve a leitura para o projeto.

Ajustes finos: aba **Ajustar** (linha do tempo, textos, **Aa Estilo legenda**). Laboratório, Radar, Crescimento, IA,
Referências, Imagens, TV, Storyboard e o projeto.yaml continuam no app, em **⋯ Mais ferramentas** (topo).

Prévias em paralelo: cada versão renderiza num processo (metade dos núcleos do Mac), então as 4 saem perto do tempo de 2.

## "O app ainda não entende a sua fala" (08/11/2026)

Aparece quando a transcrição não está no Python que roda o painel. No projeto, toque em **⬇ Instalar a transcrição
agora** (ou `python3 -m divine_studio instalar-fala`): o app arranja o uv (pelo pip ou pelo instalador oficial), cria o
Python 3.12 do app em `.venv` (sem uv, usa o Python do Homebrew), instala as bibliotecas uma por uma, baixa o modelo de
fala e **reabre o painel sozinho** no Python novo. Daí em diante o painel sempre abre nele, mesmo que o
`Divine Studio.command` comece pelo Python do Mac. Se parar com erro, a janela da tarefa mostra cada passo: mande um
print. Alternativa sem instalar nada: transcrição na nuvem com `ASSEMBLYAI_API_KEY`.

## No iPhone (08/11/2026)

O app roda no Mac; o iPhone é o controle. O `Divine Studio.command` já abre liberado para o iPhone.

1. No Mac, toque em **📱 iPhone** no topo do painel: aparece um **QR code**. Aponte a Câmera do iPhone (mesmo Wi-Fi).
   O endereço usa o nome do Mac (`http://<nome-do-mac>.local:8765`), então não muda quando o roteador troca o IP.
2. Primeira vez: digite o código de 6 dígitos. Depois, **Compartilhar ⬆ > Adicionar à Tela de Início**: vira um app.
3. Solte o vídeo (barra de progresso; deixe a tela acesa até terminar), aprove, toque em **Baixar** (abre o vídeo:
   Compartilhar > Salvar Vídeo vai para o Fotos) e **Copiar a legenda** (funciona no Safari mesmo sem https).
4. Fechou o Safari no meio da edição? Ao voltar, a tela atualiza sozinha com o que ficou pronto.

O Mac não dorme enquanto o painel está aberto (`caffeinate`; a tela pode apagar), então o iPhone sempre alcança o Mac e
as automações continuam. **Fora de casa (4G):** mande o vídeo para `Google Drive > Divine Studio > Entrada` pelo app do
Drive: o Mac cria o projeto, edita pela fala e gera as versões sozinho (automação "Vídeo do celular já sai editado");
quando voltar ao Wi-Fi, é só aprovar. Para abrir o painel na rua, instale o **Tailscale** (grátis) no Mac e no iPhone:
o painel mostra o endereço dele também. Aviso no celular quando a edição termina ainda não existe (precisaria de https);
dá para ligar a regra "Avisar no Zapier" para mandar um WhatsApp.

## Instalação no Mac (uma vez)

```bash
cd "~/Documents/Claude/Projects/Divine Medical Spa Marketing"
brew install ffmpeg                       # se ainda não tiver
# o Divine Studio.command faz tudo sozinho (Python 3.12 em .venv, bibliotecas, transcrição e 86 fontes)
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

## Primeiro vídeo (passo a passo)

1. **Nova edição** (menu de cima) > **✦ Vídeo Épico** (ou **Vídeo (Reels)**). Escreva o tema e toque em **Criar**.
2. Na aba **Projeto**, **solte os vídeos brutos** no quadro "Solte os vídeos aqui".
3. Cada vídeo vira um cartão com player: **dê play** e toque em **Tirar da edição** no que não quer usar. **Descartar** guarda o arquivo em `_arquivo/bruto` (nada é apagado).
4. No quadro **Próximo passo** (logo abaixo), confira **✦ Vídeo Épico** e toque em **✦ Criar edição automática (3 prévias)**. O app monta tudo e gera as 3 versões em alguns minutos (o andamento aparece na barra de tarefa).
5. Aba **Versões**: assista às 3 prévias.
6. Para mudar alguma coisa, você tem dois caminhos:
   - aba **Edição**, na linha do tempo: arraste para percorrer, dois cliques para pôr efeito, texto ou som;
   - **▦ Storyboard**: responda "4B: troca o título por ...".
7. Gostou? Em **Versões**, aprove a melhor e exporte a final. Ela vai para **Programação**, para postar ou agendar.

## Laboratório viral (aprender e testar formatos)

Menu **🧪 Laboratório viral**. A ideia: cada Reels é um teste de formato; o app mede, compara e decide o próximo.

- **Formatos** (`config/formatos_virais.yaml`): alto contraste, tutorial prático, nega o óbvio, erro comum, mito x verdade, pergunta de paciente, analogia com objeto, bastidor, lista que se monta, reação, história com virada e tendência (só apoio). Base: skills de modelos de Reels e método Lucureau.
- **Testes da semana**: um formato por dia. O app equilibra o que já vence com o que ainda precisa ser testado (amostragem de Thompson) e explora pelo menos um formato novo por semana. "Criar este teste" abre o projeto já com o formato.
- **Placar**: para cada formato e perfil, testes, vitórias (melhor que a mediana do próprio perfil), alcance, envios, salvos, retenção (tempo médio / duração) e seguidores. Alimentado pelas métricas do Instagram e do TikTok.
- **Edição automática**: cada uma das 3 versões testa um formato diferente, com o estilo de edição do formato.
- `python3 -m divine_studio lab [--conta drdanielmendess]` mostra o placar e o plano no terminal.

### Radar viral

O que está viralizando agora no nicho (`config/radar.yaml`). Três fontes:
1. **API oficial do Instagram**: perfis de referência (método 5x3) e hashtags. Botão "Buscar pela API do Instagram" ou `python3 -m divine_studio radar buscar`. A busca por hashtag precisa do login pelo Facebook.
2. **Claude no Chrome**: "Pesquisar com o Claude no Chrome" gera a missão (Instagram ou TikTok). Você cola na extensão, ele navega no seu navegador só olhando, e você cola a resposta em "Colar resultado".
**Pesquisa ao vivo com o Claude no Chrome (Instagram ao lado):**
1. No Divine Studio aberto no Chrome, vá em Laboratório viral > **✦ Pesquisar com o Claude (Instagram ao lado)**.
2. Escreva o tema (opcional) e, se quiser, marque **Incluir o Higgsfield**.
3. Toque em **↗ Abrir ao lado** (o Instagram ou o TikTok abre numa janela na metade direita) e em **Copiar missão**.
4. Cole a missão na extensão do Claude no Chrome. Ele pesquisa só olhando, volta para a aba do Divine Studio, cola tudo no Radar e sugere os 3 melhores para virar roteiro.

Com o Higgsfield marcado, ele sugere efeitos para viralizar no site do Higgsfield, mostra o custo e só gera com o seu ok, dentro do teto de `config/higgsfield.yaml` (`orcamento`: 60 créditos por vídeo, 250 por semana).

3. **Colar à mão**: links com números ("1,2 mi views", "35 mil curtidas").

O app não roda robô no Instagram nem no TikTok: isso viola os termos e pode bloquear a conta. Cada item ganha o formato e "quantas vezes acima do normal do perfil". "Roteiro para a Divine" adapta o formato ao seu tema: ganchos, sequência de gravação, fala para o teleprompter, CTA e legenda. Com a IA ligada, quem escreve é o Claude; sem ela, o app usa o modelo do formato. Sempre passa pelo revisor. "Criar projeto" já sai com `roteiro.md`, a fala no teleprompter e os 3 ganchos nas versões.

### Caixa de entrada (celular e Google Drive)

Solte vídeos em `entrada/` (na pasta do app) ou em **Google Drive > Meu Drive > Divine Studio > Entrada** (com o Google Drive para computador instalado). Com o painel aberto, cada vídeo novo vira um projeto: edição automática, um formato viral por versão, proposta em `trabalho/proposta_viral.md` (com referências do Radar) e o storyboard para você aprovar. O original nunca é apagado nem movido. Pelo terminal: `python3 -m divine_studio entrada`.

### Publicar nas redes e automações

- **Instagram**: "🚀 Publicar agora" na Programação publica o Reels direto do arquivo do Mac (sem link público). Carrossel e foto ainda são publicação assistida.
- **TikTok**: Laboratório viral > TikTok. Crie um app em developers.tiktok.com (Login Kit e Content Posting API), cadastre a URL de retorno `http://127.0.0.1:8765/tiktok/retorno`, cole a chave e o segredo e conecte. Por padrão, o vídeo vai como **rascunho**: chega no app do TikTok e você toca em Publicar. Apps sem auditoria do TikTok só publicam direto como "só eu". Métricas dos vídeos entram no placar.
- **Agendar** (DD/MM HH:MM) e marcar **🤖 postar sozinho**. Com o painel aberto no Mac, a peça é publicada no horário.
- **Travas** (`publicar.pode_publicar`): você ligou "postar sozinho" ou tocou em "Publicar agora"; não é uso interno, TV, prévia nem NAO-POSTAR; autorização de imagem resolvida; revisor de compliance sem erro; perfil conectado.
- **Automações** (`config/automacoes.yaml`, no estilo do Zapier):
  - vídeo novo vira proposta e depois storyboard
  - postar no horário
  - métricas 24 h e 7 dias depois
  - Radar toda segunda
  - webhook para o Zapier ou o Make (cole a URL do "Catch Hook")
  
  Liga e desliga no painel; o histórico mostra o que aconteceu.

## Edição automática pela fala (roteirista)

A "Criar edição automática" transcreve o que você fala e escreve as 3 versões em cima disso: hooks tirados das suas frases,
mensagens na tela no momento exato da fala (`na_fala`), efeitos só onde reforçam o que é dito, legenda do post sobre o assunto.
Com `ANTHROPIC_API_KEY` quem escreve é o Claude; sem ela, regras do app sobre a própria fala. Sem transcrição (falta o
faster-whisper) o painel mostra um alerta: o ⟳ Atualizar instala sozinho. O botão **✦ Pedir a edição ao Claude** copia o pedido
para colar no Claude (app do Mac ou Cowork), do mesmo jeito que você edita no chat.

## Estilo da legenda (como no CapCut)

Aba Edição, botão **Aa Estilo legenda** (ou "Aa estilo da legenda" ao tocar numa legenda da faixa): posição, tamanho, fonte,
cor do texto, cor da palavra-chave, fundo, brilho, CAIXA ALTA e palavras por vez. O quadro ao lado é a legenda real no ponto
da agulha; toque nele para pôr a legenda ali. **Aplicar e salvar** grava no `projeto.yaml` (`legendas: {...}`);
**Usar nos próximos vídeos** vira o padrão da edição automática.

## Storyboard (antes do render)

`python3 -m divine_studio storyboard <pasta>` (ou o botão **▦ Storyboard** no projeto) monta a edição em quadros reais, por cena e momento, sem renderizar nada (segundos). Cada quadro é exatamente o que vai sair naquele instante. Responda na aba Storyboard ou com `--responder`:

- `aprovado` (ou "tudo aprovado, finaliza"): exporta a final.
- `4B: troca o título por "Pele *renovada*"` · `7: tira` · `2A: entra mais cedo` (ou `mais tarde 1s`) · `3: mais longo` · `5B: troca o efeito por flash` · `2: em cima` · `1B: sem som` · `3: troca a fonte`.

Cada mudança guarda o projeto anterior em `trabalho/` e refaz o storyboard. Efeito automático ou do estilo que você tira não volta (`efeitos_evitar`).

## Estilos de edição (`estilo_edicao:` no projeto.yaml)

`divine` (padrão), `editorial`, `glow`, `papel`, `prova`, `telao`, `garrafal`, `revista`, `dividida` (tecnologia em cena), `neon`, `viral16`. Cada um muda a legenda (caixa escura, brilho, fonte), o ritmo, a lista de efeitos automáticos e coloca as peças do estilo. Tudo em `config/estilos.yaml`. Por versão: `versoes: [{nome: V1, estilo_edicao: papel}, ...]`. Seletor "Estilo de edição" na aba Projeto do painel.

Truques novos na linha do tempo: `manchetes`, `zoom_atravessa`, `vertigem`, `tela_verde`, `celular`, `visor`, `recorte_papel`, `interface`, `orbita`, `quebra_moldura`, `rabisco`, `adesivo`, `antes_depois` (só da edição), `profundidade`, `recuo_revela`, `balao`, `mural`, `saiba_mais`, `ticket`, `seta_mao`, `cartela_tempo`. Para recortar a pessoa (tela verde, órbita, recorte de papel), instale `pip3 install mediapipe`; sem ele o app usa uma elipse no centro.

Mais efeitos (06/11/2026, `divine_studio/efeitos_mais.py`):
- **Da referência "24 efeitos":** `ascii`, `capa_revista`, `grade_cards`, `desinstalando`, `deletar_app`, `retro`, `barra_prompt`, `notas_dinheiro`, `conta_gotas`, `palavras_caindo`, `pausado`, `grafico_linha`, `projetor`, `pixel`, `pasteis`, `negativo`, `linha_tempo_edicao`, `capas_reels`, `mural_titulos`, `conquista`, `estudio_edicao`, `pilula_link`, `card_titulo`.
- **Em alta nos apps de edição:** `holofote`, `lupa`, `rastro`, `triptico`, `vhs`, `dupla_exposicao`, `brilhos`, `desfoque_fundo`.

**Linha do tempo estilo CapCut** (aba Edição):
- O vídeo fica em cima, com uma agulha branca fixa no meio.
- Arrastar a linha do tempo percorre o vídeo; enquanto toca, ela anda sozinha.
- Zoom com − / +, ⤢ para ver tudo, ou pinça no trackpad.
- Faixas separadas:
  - **Vídeo:** tira de miniaturas e clipes; toque para aparar, dividir, velocidade e transição.
  - **Texto:** o hook e as mensagens.
  - **Legendas:** a fala em blocos; toque para corrigir o texto, e a correção vale para o vídeo inteiro.
  - **Efeitos:** os seus e os automáticos (tracejados).
  - **Áudio:** sons e voz.
- Dois cliques numa faixa (no iPhone, segure o dedo) põem ali um item daquela faixa.
- Barra de ferramentas embaixo: Dividir, Efeitos, Texto, Legendas, Áudio, Voz, Filtros e Quadro.

**Pôr efeito com um clique:** dois cliques na linha do tempo (no iPhone, segure o dedo) abrem o seletor naquele segundo. O seletor tem categorias (texto, câmera e 3D, transições, cor e filtros, papel e colagem, apps e interface, dados, pessoa recortada, final e CTA) e busca; as categorias ficam em `config/efeitos.yaml`.

Carrossel: método 3C automático (capa até 12 palavras, "toca 2x na tela" no 4º card, convite para o link da bio no último).

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
