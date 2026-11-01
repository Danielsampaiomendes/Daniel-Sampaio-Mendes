---
name: "divine-efeitos-17"
description: "Use ao editar qualquer vídeo da Divine ou do Dr. Daniel para aplicar os 17 efeitos de motion (gancho digitado, queda de letras, prompt, storyboard, cartão de vídeo, CTA WhatsApp etc.) no padrão Divine."
---

# Divine Efeitos 17

Motor de efeitos (Python + Pillow + ffmpeg) que aplica, por uma timeline JSON, os 17 efeitos aprendidos da referência @amandamoita.ia (out/2026), redesenhados no padrão Divine: fundo #12110F, dourados #CCBD91/#B8A169, off-white #F5F4F1, Italiana + Cormorant + Lora Italic + Poppins + Jost, tudo entrando com fade/deslize e easing, nada brusco na abertura. Usar junto com divine-video-pro (áudio, profundidade), divine-sfx (SFX baixos) e o banco de hooks.

## Preparar o ambiente (início de cada sessão)
1. Baixar o motor do projeto: Projects project_read `claude/divine_fx.py` e `claude/divine_fx_timeline_exemplo.json`; salvar em `divine-efeitos-17/scripts/divine_fx.py` e `divine-efeitos-17/exemplos/`.
2. Fontes em `divine-efeitos-17/fonts/` (o script lê dessa pasta):
   - Poppins Light/Medium/Regular e Lora Italic: copiar de `/usr/share/fonts/truetype/google-fonts/` (Poppins-Light.ttf, Poppins-Medium.ttf, Poppins-Regular.ttf, Lora-Italic-Variable.ttf).
   - Italiana, Cormorant Garamond e Jost: `npm pack @fontsource/italiana @fontsource/cormorant-garamond @fontsource/jost`, extrair e converter os woff2 com fontTools (`pip install brotli`): italiana-latin-400-normal → Italiana-Regular.ttf; cormorant-garamond-latin-500-normal → CormorantGaramond-Medium.ttf; cormorant-garamond-latin-500-italic → CormorantGaramond-Italic.ttf; jost-latin-300-normal → Jost-Light.ttf (TTFont(src); f.flavor=None; f.save(dst)). GitHub raw de fontes costuma dar 403, usar npm.
3. Logomarca: se o vídeo escreve "Divine Medical Spa", usar a logo oficial (PNG dourado) via campo `logo` da timeline; nunca o nome em texto comum.

## Rodar
`python3 divine-efeitos-17/scripts/divine_fx.py entrada.mp4 timeline.json saida.mp4`
Pré-visualização sem vídeo: `--demo timeline.json saida.mp4`. Entrada em qualquer formato vira 1080x1920; áudio original é mantido; SFX opcionais por evento (`sfx`, `sfx_db` padrão -18). Velocidade ≈ 6 s de render por segundo de vídeo.

## Timeline
```json
{"fps":30, "logo":"caminho/logo.png", "logo_y":150, "logo_window":[0,2.5],
 "indice": {"items":["..."], "times":[0,2.4], "t":0.2, "end":20},
 "events":[{"fx":"gancho","t":0,"d":2.4,"kicker":"...","text":"PÓS CO2"}]}
```
Cada evento: `fx`, `t` (início s), `d` (duração s) + parâmetros. `*palavra*` no `chip` sai em Lora Italic dourada.

## Os 17 efeitos (fx e parâmetros)
1. `gancho` Gancho dinâmico: título digitado com cursor dourado + kicker itálico. text (\n quebra), kicker, y, size, cps.
2. `queda` Queda gravitacional: letras caem uma a uma, subtítulo itálico. text, sub, y, size.
3. `legenda_gigante` Legendas gigantes: chip nasce no peito e cresce inclinado. words [lista].
4. `prompt` Caixa de prompt: dúvida da paciente digitada, enviar vira check dourado. text, y, cps.
5. `storyboard` Painel de storyboard: miniaturas do próprio vídeo sobem em leque e alinham. n, times.
6. `icones_riscados` Lista de ícones: traço dourado risca mitos. labels, word.
7. `subir_arquivo` Subir arquivo: card (exame/laudo) cai na zona tracejada e vira miniatura. file, size, zone, chip.
8. `timeline` Linha do tempo: painel com miniaturas, waveform dourada e playhead. label, y.
9. `exclusao_app` Exclusão de app: ícones tremem de leve e somem, fica 1. labels, keep (índice que fica).
10. `controle_cor` Controle de cor: cortina com alça revela correção de cor. strength. COMPLIANCE: nunca em paciente/resultado (só ambiente/cor do vídeo).
11. `conta_gotas` Ajuste com conta-gotas: cursor toca pontos e mostra paleta com HEX real. points [[x,y]], names, y.
12. `cinematografico` Estilo cinematográfico: grade quente, vinheta, grão, barras pretas. strength, bars.
13. `frame_titulo` Frame de título: tela #12110F com timecode e título Italiana. text, tc.
14. `grade_videos` Grade de vídeos em reprodução: mural de miniaturas tocando. n, offsets.
15. `feed_reels` Feed de reels: vídeo encolhe numa moldura de Reels. handle, caption.
16. `cartao_video` Cartão de vídeo: card com borda fina, play, título itálico, progresso dourado. title.
17. `mensagem` CTA mensagem: WhatsApp digitando "Quero agendar minha avaliação" + resposta da Divine. text, reply. Substitui o "Comenta EU QUERO" da referência (regra: nunca pedir para comentar palavra).
Extras: `chip` (legenda de apoio), `zoom` (punch in suave: scale, cx, cy).

Índice lateral "Neste vídeo" (opcional, bom para vídeo de lista/aula): itens ganham check dourado, sem numeração. Com ele ligado, os efeitos vão automaticamente para a coluna livre à direita, menores (exceto chip, conta_gotas e timeline). Desligar o índice para vídeos comuns.

## Regras de uso
- No máximo 1 efeito novo a cada 1,5 a 2 s; texto fica tempo suficiente para leitura; texto nunca sobre o rosto (gancho/queda acima da cabeça, chip no peito ~y 1300 a 1400).
- Áreas seguras: topo 220 px, base 380 px, lateral direita 140 px.
- Abertura sempre suave: gancho/queda entram com fade; nada de flash ou tremor.
- Sem travessões nos textos; sem numeração de cards; sem "comenta PALAVRA".
- Compliance CFM: sem antes/depois, sem promessa, sem percentuais; controle_cor e cinematografico nunca para mostrar pele "melhorada".
- Entregar 3 versões com hooks diferentes (banco de hooks) e registrar novos hooks.
- Checar 6 a 8 frames numa folha de contato antes de entregar (ffmpeg select + tile).

## Ordem no pipeline Divine
Corte → divine-video-pro (áudio, limpeza, profundidade) → divine_fx (efeitos) → SFX baixos (divine-sfx) → export 1080x1920 CRF 17 → folha de contato.