---
name: "divine-fontes"
description: "Use ao escolher a tipografia de qualquer vídeo, Reels, Stories ou arte da Divine, do Dr. Daniel ou do George: padrão CAIXA ALTA + cursiva fina, prancha PNG de opções antes de editar, banco de combinações, máximo de 2 fontes e rodízio."
---

# Tipografia Divine: banco de combinações de fontes

## Padrão obrigatório (desde 31/10/2026, "de agora em diante")
- **Título sempre grande e em CAIXA ALTA**, fonte encorpada.
- **Texto de apoio em cursiva fina logo embaixo**, colado ao título (pode encostar levemente na base), menor que o título.
- Estilo da referência (vídeo "Combinações de letras para títulos no CapCut"): dourado em degradê (#F5E9BE → #D6BE7D → #B09458) com sombra escura suave sobre o vídeo.
- Entrada suave: fade + deslize lento; a cursiva pode "escrever" com máscara da esquerda para a direita. Nada piscando.

## Fluxo obrigatório: prancha PNG antes de editar
1. Antes de editar QUALQUER vídeo, gerar uma **prancha PNG** com 4 a 6 opções de tipografia no padrão acima, usando o título/hook real do vídeo (testa acentos ç, ã, õ, é).
2. Cada card: amostra 9:16 com o texto aplicado + caixinha com ID, nome, fonte do título e fonte de apoio.
3. Enviar a prancha e **esperar o Renato escolher** antes de editar.
4. Priorizar opções que não foram usadas no vídeo anterior (rodízio). Conferir no índice de vídeos editados (doc do projeto) qual foi usada por último e anotar a nova ao terminar.

## Regra de famílias
- **No máximo 2 famílias de fonte por vídeo**: título + apoio. Uma 3ª só se realmente necessária. Nunca 4.
- Pesos e itálico da mesma família contam como a mesma fonte.
- O header DIVINE / MEDICAL SPA (Cormorant Garamond + Jost) e o logo são marca e **não contam** no limite.
- Legenda dinâmica falada: nunca em script; usar uma fonte legível (de preferência da mesma família do título ou do apoio, se for legível).
- Antes de entregar, contar as famílias usadas no vídeo inteiro (hook, títulos, legenda, CTA, tela final). Se passou, unificar.

## Banco principal: CAIXA ALTA + cursiva fina (prancha de 31/10)
| ID | Nome | Título (caixa alta) | Apoio (cursiva fina) | Origem |
|---|---|---|---|---|
| O1 | Coroa | Cinzel Bold (wght 800) | Great Vibes | referência CapCut |
| O2 | Revista | Playfair Display Black (900) | Playfair Display Itálico 400 | referência (Montserrat trocada por itálico, pois não é cursiva) |
| O3 | Editorial | Abril Fatface | Cormorant Garamond Itálico 500 | referência CapCut |
| O4 | Impacto | Bebas Neue | Dancing Script 500 | referência CapCut |
| O5 | Vogue | Bodoni Moda Bold (eixos [800, 40]) | Great Vibes | já aprovada (perfil pessoal) |
| O6 | Doce chique | Abril Fatface | Pinyon Script | nova |

Do banco antigo, também se encaixam no padrão (título em caixa alta + script): E Assinatura (Italiana + Mrs Saint Delafield), H Impacto chique (Bebas Neue + Pinyon Script), K Doce (Rubik Black 900 + Allura), L Romântica ousada (Dela Gothic One + Monsieur La Doulaise), N Moderna (Unbounded Black 900 + Aguafina Script).

## Banco antigo (fora do padrão novo; só se o Renato pedir)
| ID | Nome | Título | Apoio | Melhor para |
|---|---|---|---|---|
| A | Bilhete | Instrument Serif caixa alta | Caveat | visual hooks, bastidores |
| B | Vogue antiga | Bodoni Moda | Jost Light espaçado | glamour, tecnologias premium |
| C | Revista antiga | Playfair Display Bold + itálico | Poppins Light | educativo, ciência |
| D | Clássico quente | DM Serif Display | Lora Itálico | dores, storytelling |
| F | Contemporâneo | Fraunces | Manrope | opinião, frases fortes, Dr. Daniel |
| G | Diário | Gloock | Courier Prime | relato, diário de recuperação |
| I | Spa minimal | Tenor Sans espaçado | Lora Itálico | ambiente, spa, TV |
| J | Bilhete noturno | Instrument Serif Itálico | Caveat | empatia, gancho duplo |
| M | Editorial condensado | Abril Fatface condensada (~74% largura) | Titillium Web Light | nome do procedimento, revelação |

K a N vieram do vídeo de referência do app Edits (Kotka + Sweetheart, Big Sexy Sans + Hopeless Romantic, Sunflower + Magari, Airone + Aquafina). A Sunflower do Google não tem ç/ã, por isso M usa Titillium Web.

## Composições que funcionam
- **Caixa alta + cursiva colada embaixo** (padrão atual): título grande dourado, cursiva fina centralizada logo abaixo.
- **Pesada + script cruzando:** palavra pesada grande; script fino em dourado claro #E6D9A8 ou #CCBD91 sobreposto à base (K, L, N, H).
- **Etiquetas:** duas palavras em caixas escuras lado a lado (Mito vs. Verdade).
- Script sempre grande o bastante para ler no celular; nunca script em texto longo ou legenda.

## Onde estão os arquivos
Pasta do projeto no computador do Renato: `Divine Medical Spa Marketing/Biblioteca_Fontes/`
- `ttf/`: todas as fontes (Google Fonts, OFL, uso comercial livre)
- `previews/`: exemplos aplicados no estilo Divine
- `baixar_fontes.sh`: baixa de `raw.githubusercontent.com/google/fonts/main/ofl/...`. Se a pasta não estiver acessível, baixar direto no container.
- Caminhos das fontes novas: cinzel/Cinzel[wght].ttf, greatvibes/GreatVibes-Regular.ttf, playfairdisplay/PlayfairDisplay[wght].ttf e PlayfairDisplay-Italic[wght].ttf, abrilfatface/AbrilFatface-Regular.ttf, cormorantgaramond/CormorantGaramond-Italic[wght].ttf, bebasneue/BebasNeue-Regular.ttf, dancingscript/DancingScript[wght].ttf, bodonimoda/BodoniModa[opsz,wght].ttf, pinyonscript/PinyonScript-Regular.ttf (colchetes na URL como %5B %5D).
- Fontes variáveis no Pillow: conferir a ordem real com `font.get_variation_axes()` antes de `set_variation_by_axes` (BodoniModa é [wght, opsz], não a ordem do nome do arquivo; Rubik[wght] → [900]).

## Novas referências
Quando o Renato mandar vídeo ou print com fontes: extrair quadros, identificar os pares, achar no Google Fonts ou o equivalente livre, adaptar ao padrão CAIXA ALTA + cursiva fina, testar acentos, montar prévia no estilo Divine, acrescentar como nova letra/ID nesta tabela, no LEIA-ME e no `baixar_fontes.sh`, e salvar a prévia em `previews/`.