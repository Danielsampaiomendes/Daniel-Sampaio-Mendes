# Prompt para o Claude Code: Divine Studio (ferramenta de edição de vídeo)

Cole este arquivo na raiz do repositório "Divine Medical Spa Marketing" e, no Claude Code, digite:
`Leia PROMPT_Divine_Studio.md e execute, começando em modo de planejamento.`

---

## 1. Missão

Você vai construir o **Divine Studio**: uma ferramenta local de edição de vídeo que transforma tudo o que já foi feito neste repositório (scripts, templates, skills, bibliotecas de fontes e SFX, bancos de hooks, regras de compliance e referências aprovadas) em um sistema único, repetível e fácil de usar.

Objetivo prático: eu solto os vídeos brutos numa pasta, escolho o template e o tipo de peça, e a ferramenta entrega as versões prontas para Instagram e TV, com legenda, checklist de compliance e registro do que foi usado, sem eu precisar repetir regras a cada pedido.

Toda interface, nomes de arquivos de saída e textos gerados em português do Brasil.

## 2. Fase 0: inventário obrigatório antes de escrever código

Não comece a programar antes de mapear o repositório. Faça:

1. Varra todas as pastas (projetos `video-*`, `tools/`, `Biblioteca_SFX/`, `Biblioteca_Fontes/`, timelines, `cuts.json`, `edited-transcript.json`, `timeline.json`, shots Remotion/TSX, scripts Python/Pillow, comandos FFmpeg, LEIA-ME, docs em `claude/`, skills em `.claude/`).
2. Identifique o que já funciona e foi aprovado (ex.: `tools/bake.py`, `tools/clean_voice.py`, o editor de cortes, o pipeline de legendas animadas, os geradores de artes).
3. Liste duplicações: o mesmo efeito, template ou ajuste de FFmpeg implementado de jeitos diferentes em projetos diferentes.
4. Gere `docs/MAPA_DO_REPOSITORIO.md` com: o que existe, onde está, o que será reaproveitado, o que será unificado e o que será descartado.
5. Me mostre o mapa e o plano de arquitetura e espere meu OK antes da Fase 1.

Regra de ouro: **reaproveitar e unificar, não reinventar**. Se um script aprovado gera o resultado certo, ele vira módulo da ferramenta.

## 3. Arquitetura sugerida (ajuste se o inventário indicar algo melhor)

- **Núcleo em Python** (Pillow com supersampling 2×, numpy, FFmpeg) + **Remotion/TSX** onde já é usado para os shots.
- **CLI** `divine` para tudo (ex.: `divine novo`, `divine cortar`, `divine editar --template divine --versoes 3`, `divine tv`, `divine pacote`, `divine revisar`).
- **Interface web local** simples (FastAPI + front leve) para: arrastar vídeos, escolher template, revisar cortes, comparar as 3 versões lado a lado, aprovar.
- **Configuração em YAML** (`config/`), nunca regras escondidas no código: marca, templates, presets de exportação, compliance, preferências.
- Cada projeto de vídeo numa pasta própria: `projetos/AAAA-MM-DD_tema/` com `bruto/`, `trabalho/`, `saida/`, `projeto.yaml` e `relatorio.md`.

## 4. Módulos do pipeline

1. **Ingestão**: detectar resolução, fps, HDR/HLG; converter HDR para SDR (zscale, tonemap hable); `-map 0:a:0` em .mov. Se a fonte for de baixa resolução ou cena clara, ativar automaticamente o **modo alta qualidade**: sem zoom, denoise leve (hqdn3d), upscale Lanczos + unsharp, grade limpo sem levantar pretos, intermediário crf 13, final HEVC (hvc1) em 2 passes abaixo de 30 MB.
2. **Transcrição**: AssemblyAI (ou Whisper local como alternativa), com tempo por palavra; OCR para vídeos que já vêm com legenda queimada (caso George).
3. **Corte limpo**: unificar o fluxo do `clean-cut` (cortes de enrolação, takes ruins, pausas naturais de ~0,5 s), com o editor de cortes local.
4. **Áudio**: limpeza de voz (unificar `clean_voice.py`: ElevenLabs Voice Isolator ou RNNoise conforme o ruído), highpass, loudnorm −16 LUFS, trilha lounge sintetizada original (~84 bpm) com ducking sob a fala.
5. **Templates visuais** (cada um em YAML + módulo de render):
   - **Divine suave/glamour** (padrão Reels)
   - **Daniel** (@drdanielmendess, foto oficial de perfil, selo verificado, verde-petróleo #143A3F nos posts)
   - **George** (azul-marinho #0E194A + dourado, "Enf." e COREN, placa que cobre a legenda queimada)
   - **TV 16:9** (janela 4:5 central com cantoneiras douradas, painel esquerdo de mensagens, painel direito fixo, tela final, rodapé RT, loop ~23 s, margens de segurança de TV)
   - **Tela dividida / React** (legenda logo acima da cabeça de quem fala)
   - **Pessoal do Renato** (sem nenhuma marca Divine; Bodoni Moda + Great Vibes)
6. **Hooks**: ler os bancos de hooks do repositório/docs, sortear 3 diferentes por vídeo (positivo, curiosidade, negativo), registrar quais foram usados, e permitir adicionar hooks novos ao banco.
7. **Fontes**: rodízio das combinações A a N de `Biblioteca_Fontes`, no máximo 2 fontes por vídeo (3 só se indispensável); cada versão sai com uma combinação diferente; header da marca e legenda fixos.
8. **SFX**: biblioteca `Biblioteca_SFX/1_kit_original_divine` (só sons livres para uso comercial; nunca os extraídos de memes). Rodízio com histórico: 3 a 4 famílias por vídeo, não repetir a variação usada nos últimos vídeos, no máximo 1 impacto grave, tudo bem abaixo da trilha, sem ping a cada texto.
9. **Efeitos cinéticos**: biblioteca de módulos EC01 a EC16 e EV01 a EV17 como overlays PNG com alfa (Pillow ou HTML + Playwright quadro a quadro), easing cubic in out, recorte de pessoa com rembg/mediapipe onde precisar (texto atrás da pessoa, órbita, quebra de moldura, capa de revista). No máximo um efeito a cada 1,5 a 2 s.
10. **Legendas animadas na tela**: entrada e saída só com fade/deslize lento, nunca piscando ou pulando; tempo de leitura suficiente; zona segura do Instagram (topo 220 px, base 380 px, lateral direita 140 px); texto nunca sobre o rosto.
11. **Exportação**: presets Reels/Stories 1080×1920, Feed 1080×1350 e 1080×1080, TV 1920×1080; x264 slow, tune film, aq-mode=3; teto de 30 MB quando for para envio; arquivo final com metadados limpos.
12. **Pacote por categorias**: quando eu mandar vários vídeos do mesmo procedimento, gerar Reels longo, médio, curto e ultracurto, viral, POV, cortes, bastidores, versão TV e alguns Stories, com nomes claros para eu validar.
13. **Legenda do post**: gerar legenda em parágrafos corridos, gancho na 1ª linha, CTA antecipado, aviso "Resultados variam de pessoa para pessoa", assinatura do RT, 8 a 12 hashtags; salvar em `.txt` pronto para copiar.
14. **Registro**: atualizar o índice de vídeos editados (`claude/indice-videos-editados.md` ou equivalente) com data, tema, versões, hooks, fontes, SFX e legenda de cada peça.

## 5. Identidade visual (fixa em `config/marca.yaml`)

- Fundo #12110F, dourados #CCBD91 e #B8A169, off-white #F5F4F1, texto corrido #CDCDCB.
- Fontes da marca: Italiana, Lora Italic, Poppins Light/Medium, Jura Medium; wordmark "DIVINE" em Cormorant Garamond espaçado sobre "MEDICAL SPA" em Jost Light.
- Logo oficial (trevo dourado, PNG RGBA) visível em todo quadro; horizontal no topo, empilhado no fechamento. Nunca escrever "Divine Medical Spa" em texto comum: sempre a logomarca.
- Endereço sempre como: "Av. Paulista 1636 - Ao lado do MASP".
- Ilustrações de corpo: silhueta contínua, contorno dourado fino, brilho suave na área tratada.

## 6. Regras de edição (fixas em `config/preferencias.yaml`)

- Estilo suave e glamouroso: nada brusco na abertura (sem slam, tremor ou flash forte), textos em fade/deslize lento, transições em dissolve, zoom lento contínuo.
- Unir isso ao método Código Viral: assunto visível no 1º quadro, frase de ~5 palavras antes de 4 s, CTA antecipado curto, mudança visual a cada ~2 s, uma ideia por vídeo, final "porta na cara" sem despedida para gerar replay, duração alvo de 25 a 40 s.
- Estrutura falada: gancho, CTA antecipado, promessa, contexto, CTA final.
- Sem numeração na tela (01, 02, 03), só no roteiro.
- Evitar travessões e tracinhos em todo texto gerado: usar vírgula, ponto ou dois-pontos.
- Nunca pedir para comentar uma palavra (ex.: "Comenta ESTRIA").
- Para cortes que terminam secos: cena final "Quer entender mais sobre [assunto]? Leia na legenda".
- Sempre 3 versões de cada vídeo, cada uma com hook, combinação de fontes e SFX diferentes.
- **Aprendizado contínuo**: toda correção que eu fizer num vídeo vira regra no YAML (com data) e vale para os próximos até eu mudar. Criar o comando `divine regra "texto da regra"`.

## 7. Compliance (módulo `revisor`, bloqueia a exportação se falhar)

Lint automático de todo texto na tela, roteiro e legenda:
- CFM 2.336/2023: sem percentuais, prazos garantidos, promessa de resultado, sensacionalismo ou comparação com outros profissionais; preferir "estímulo", "auxilia", "pode contribuir".
- Sem antes e depois de pacientes em nada que vá ao Instagram (só "Mito vs Verdade", "Expectativa vs Realidade", educativo, bastidores). Antes e depois só no template de uso interno de consulta, marcado como "não postar".
- Anvisa RDC 96/2008: bloquear nomes de medicamentos de prescrição e marcas (GLP-1, tirzepatida, semaglutida e similares) em peças promocionais.
- Termos: "reposição hormonal" e "pellets", nunca "implante hormonal"; "gastroenterologista"; "nutrólogo" só com RQE.
- RT obrigatório em conteúdo médico: Dr. Daniel Sampaio Mendes, CRM/SP 186.470.
- Pessoa aparecendo: campo "autorização de imagem" obrigatório no `projeto.yaml`; sem ele, a exportação sai marcada como pendente.
- Músicas: só trilhas originais sintetizadas ou liberadas para uso comercial.
- Saída: nota de revisão viral (hook, retenção, leitura, áudio, glamour, compliance) e a linha "OK CFM / OK Anvisa / autorização de imagem: ...".

## 8. Entregáveis e ordem de construção

1. **Fase 0**: `docs/MAPA_DO_REPOSITORIO.md` + plano (esperar meu OK).
2. **Fase 1**: estrutura do projeto, configs YAML, CLI, ingestão, exportação e o template Divine suave funcionando de ponta a ponta com um vídeo real do repositório.
3. **Fase 2**: corte, áudio, transcrição, legendas animadas, hooks, fontes e SFX com rodízio e histórico.
4. **Fase 3**: templates Daniel, George, TV, React e Pessoal; revisor de compliance.
5. **Fase 4**: efeitos EC/EV, pacote por categorias, legenda do post, registro no índice.
6. **Fase 5**: interface web local e `README.md` em português com exemplos de uso.

A cada fase: rodar num vídeo real, salvar frames de verificação (início, meio, fim) e comparar com as referências aprovadas do repositório (TV "CO2 em manchas senis", Reels lipedema na versão suave, Reels do George, Endolaser). Testes automáticos para o revisor de compliance e para o rodízio de fontes/SFX.

## 9. Como trabalhar comigo

- Minhas mensagens são curtas: deduza o contexto pelo repositório e mostre resultado, não listas de opções.
- Pergunte só o indispensável, uma pergunta por vez.
- Não apague nada do repositório: mova o que for descartado para `_arquivo/`.
- Faça commits pequenos por fase, com mensagem em português.
