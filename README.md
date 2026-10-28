# Divine Studio

Ferramenta de edição de vídeo da Divine Medical Spa. Você solta os vídeos brutos numa pasta, escolhe o template e o tipo de peça, e ela entrega as versões prontas para Instagram e TV, com legenda do post, checklist de compliance e registro do que foi usado, aplicando sozinha todas as regras já aprovadas (marca, Código Viral, CFM, Anvisa, rodízio de fontes e sons).

Tudo o que já foi aprovado de edição está em `docs/CONHECIMENTO_DIVINE.md` e `docs/BANCO_HOOKS.md`; o mapa dos projetos já feitos fica em `docs/MAPA_DO_REPOSITORIO.md`. O guia completo da ferramenta é o `docs/DIVINE_STUDIO.md`.

## Instalação no Mac (uma vez)

```bash
cd "~/Documents/Claude/Projects/Divine Medical Spa Marketing"
brew install ffmpeg                       # vídeo e áudio
pip3 install -r requirements.txt          # Pillow, numpy, PyYAML
pip3 install faster-whisper               # transcrição local (corte limpo e legenda da fala)
bash Biblioteca_Fontes/baixar_fontes.sh   # 33 fontes do banco (Google Fonts, OFL)
python3 Biblioteca_SFX/gerar_kit_sfx.py Biblioteca_SFX/1_kit_original_divine   # se o kit de SFX não estiver lá
python3 -m divine_studio verificar        # confere tudo
```

Opcionais: `brew install tesseract tesseract-lang` (OCR da legenda queimada do George), `pip3 install mediapipe` (texto atrás da pessoa), `export ASSEMBLYAI_API_KEY=...` (transcrição na nuvem), `export ELEVENLABS_API_KEY=...` (limpeza de voz com IA para ruído pesado).

Fotos oficiais de perfil para os cartões de nome: `assets/pessoas/daniel_perfil.png` e `george_perfil.png` (ver `assets/pessoas/LEIA-ME.md`).

## Jeito mais fácil: o painel

```bash
python3 -m divine_studio painel
```

Abre `http://127.0.0.1:8765` no navegador (só na sua máquina). Nele você:

1. Cria o projeto com o tema do vídeo.
2. Arrasta os vídeos brutos e clica em "usar como clipe".
3. Escolhe template, formato e autorização de imagem; pede 3 hooks do banco.
4. Clica em "Revisar" (compliance), "Ver corte" (o que sai e o que fica) e "Gerar prévias".
5. Compara as versões lado a lado, marca as aprovadas e clica em "Aprovar selecionadas e exportar a final".
6. Copia a legenda do post na aba "Relatório e legenda".
7. Ensina uma regra nova quando corrigir alguma coisa: ela passa a valer para os próximos vídeos.

## Pela linha de comando

```bash
python3 -m divine_studio novo "co2 no corpo"                  # cria projetos/AAAA-MM-DD_co2-no-corpo/
python3 -m divine_studio cortar projetos/2026-10-28_co2-no-corpo
python3 -m divine_studio revisar projetos/2026-10-28_co2-no-corpo
python3 -m divine_studio editar projetos/2026-10-28_co2-no-corpo --rapido   # prévias
python3 -m divine_studio editar projetos/2026-10-28_co2-no-corpo            # final + registro
python3 -m divine_studio pacote projetos/2026-10-28_co2-no-corpo --renderizar --rapido
python3 -m divine_studio legenda projetos/2026-10-28_co2-no-corpo
python3 -m divine_studio hooks sortear --tema "laser co2"
python3 -m divine_studio efeitos --prancha prancha.jpg
python3 -m divine_studio regra "CTA antecipado com no máximo duas linhas"
```

## Exemplo de projeto.yaml

```yaml
titulo: "Laser de CO2 no corpo"
template: divine              # divine | daniel | george | tv | react | pessoal
formato: reels                # reels | stories | feed45 | feed11 | tv
autorizacao_imagem: sim       # sim | pendente | nao_aparece | proprio
corte_limpo: true             # tira "hum", takes repetidos e pausas longas
legendas: true                # legenda da fala, palavra a palavra
clipes:
  - {arquivo: bruto/IMG_1234.MOV}
  - {arquivo: bruto/IMG_1240.MOV, velocidade: 0.72, mudo: true}
selo: "LASER DE CO2 · CORPO"
cta_antecipado: "Manda pra amiga que vive *adiando o CO2.*"
mensagens:
  - {titulo: "Estímulo / ao *colágeno.*", na_fala: "estimula o colágeno"}
efeitos:
  - {tipo: circulo, inicio: 6, ponto: [0.5, 0.55], texto: "*Spoiler:* é só a mira"}
fechamento:
  frase: "Cada pele tem o *seu tempo.*"
versoes:
  - {nome: V1, hook_id: A-H18}
  - {nome: V2, hook: auto}
  - {nome: V3, hook: auto}
```

Sem `legenda:` no projeto, a legenda do post é gerada sozinha (gancho, CTA antecipado, corpo corrido, WhatsApp e endereço, aviso de resultados, RT e hashtags) e passa pelo revisor.

## O que sai de cada projeto

- `saida/AAAA-MM-DD_reels_<tema>_V1_<hook>.mp4` (V2, V3), com `_PREVIA` nas prévias, `_autorizacao-pendente` quando falta a autorização e `_USO-INTERNO-NAO-POSTAR` no uso interno
- `saida/legenda.txt` pronta para copiar
- `relatorio.md` com hook, fontes, SFX, duração, tamanho, nota de revisão viral e a linha "OK CFM / OK Anvisa / autorização de imagem"
- `trabalho/cortes.md` (corte limpo) e `trabalho/V1_quadros.jpg` (folha de conferência)
- Na final: registro em `docs/INDICE_VIDEOS_EDITADOS.md`, no histórico do `docs/BANCO_HOOKS.md` e no `docs/MAPA_DO_REPOSITORIO.md`

## Onde fica cada regra

| Arquivo | O que define |
|---|---|
| `config/marca.yaml` | cores, logo, endereço, RT, aviso, área segura |
| `config/preferencias.yaml` | animação, leitura, fechamento, trilha, corte, voz, legenda da fala, regras aprendidas |
| `config/compliance.yaml` | o que bloqueia e o que avisa (CFM, Anvisa, termos), nota viral |
| `config/fontes.yaml` | combinações A a N e fixas (TV, pessoal) |
| `config/sfx.yaml` | rodízio de sons e limites por vídeo |
| `config/templates.yaml` | medidas e textos fixos de cada template |
| `config/pessoas.yaml` | Dr. Daniel, Enf. George, Dra. Isis (nome, registro, @, foto, cor) |
| `config/efeitos.yaml` | códigos EC/EV e o módulo de cada um |
| `config/pacote.yaml` | categorias do pacote e duração alvo |
| `config/legenda.yaml` | CTAs, hashtags por tema |
| `config/exportacao.yaml` | formatos, x264/HEVC, −16 LUFS, teto de 30 MB |
| `config/historico.yaml` | últimas fontes, sons e hooks usados (atualizado sozinho) |

## Testes

```bash
python3 -m pytest tests -q
```

Cobrem o revisor de compliance, o rodízio de fontes e SFX, o corte limpo, a legenda sincronizada, os hooks, os templates, os efeitos, o pacote, a legenda do post, o registro e o painel.

## Estrutura

```
divine_studio/      código (cli, painel, ingest, transcricao, corte, voz, legendas, hooks, efeitos, pacote,
                    legenda_post, registro, compliance, rodizio, render, exportar, templates/)
divine_studio/web/  interface do painel
config/             regras em YAML
projetos/           um projeto por vídeo (bruto/, trabalho/, saida/, projeto.yaml, relatorio.md)
docs/               conhecimento aprovado, banco de hooks, mapa, índice e guia da ferramenta
Biblioteca_Fontes/  fontes do banco (baixar_fontes.sh)
Biblioteca_SFX/     kit de sons original (gerar_kit_sfx.py)
assets/pessoas/     fotos oficiais de perfil (só no Mac)
tests/              testes automáticos
```
