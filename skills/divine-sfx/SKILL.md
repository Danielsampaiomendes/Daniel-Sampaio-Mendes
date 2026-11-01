---
name: "divine-sfx"
description: "Use ao colocar efeitos sonoros em qualquer vídeo da Divine, do Dr. Daniel ou do George, ou ao extrair efeitos de um vídeo de referência para a biblioteca de SFX."
---

# Efeitos sonoros Divine (SFX)

Objetivo: efeitos que aumentam o engajamento sem quebrar o padrão suave e com glamour da Divine, e que **variam de um vídeo para outro** (repetir sempre os mesmos sons fica monótono e afasta seguidores).

## Onde está a biblioteca
Pasta do projeto no computador do Renato: `Divine Medical Spa Marketing/Biblioteca_SFX/`
- `1_kit_original_divine/`: 28 sons sintetizados do zero, livres para uso comercial. **Só estes vão para os vídeos publicados.**
- `2_extraidos_referencia/`: sons tirados de vídeos de referência (faah, vine boom, taco bell, discord, dexter, cha-ching etc.). Só para ouvir e comparar; memes e sons de marca não têm licença comercial.
- `gerar_kit_sfx.py`: recria o kit original (`python3 gerar_kit_sfx.py <pasta_saida>`, precisa de numpy e soundfile). Use se a pasta não estiver acessível.
- `teste_combinacoes_sfx.mp3` e `LEIA-ME.md`.

Para usar: pedir acesso à pasta do projeto (device_request_folder_access) e trazer para o container só os WAVs necessários (device_stage_files). Se o computador não estiver acessível, regenerar o kit com o script (copiar do projeto ou reescrever a síntese equivalente).

## Famílias do kit (variações a/b/c para rodízio)
| Família | Variações | Quando usar |
|---|---|---|
| whoosh_suave | a, b, c | zoom in/out, texto deslizando, troca de cena |
| brilho_dourado | a, b, c | revelação, partículas douradas na tela |
| ding_suave | a, b, c | informação importante, dica, check |
| notificacao_suave | a, b | card de pergunta/comentário/DM entrando |
| tick_suave | a, b, c | itens de lista aparecendo |
| pop_suave | a, b, c | selo, ícone, pílula de texto surgindo |
| camera_shutter | a, b_duplo | transições rápidas, sequência de bastidores |
| impacto_grave_suave | a, b, c | ênfase no hook (versão elegante do vine boom) |
| riser_suave | a, b | suspense antes de revelar |
| swell_reverso | a, b | respiro antes de um texto importante |
| cristal | a, b | preço/condição, tela final, CTA |

## Receitas por situação
- **Hook (captar atenção):** swell_reverso, depois impacto_grave_suave baixo, depois brilho_dourado. Nunca slam ou som brusco na abertura.
- **Revelação:** riser_suave + brilho_dourado + cristal, sincronizado com partículas/brilho dourado na imagem.
- **Zoom in e zoom out:** whoosh_suave, com variação diferente na entrada e na saída, sincronizado com o movimento.
- **Transições rápidas:** camera_shutter em cada corte (no máximo 3 a 4 seguidos).
- **Pergunta de seguidora / notificação:** pop_suave + notificacao_suave junto com o card aparecendo.
- **Lista na tela:** tick_suave em cada item, ding_suave no último.
- **Preço/condição:** pop_suave + cristal (nunca cha-ching em peça médica).
- **Tela final / CTA:** whoosh_suave + brilho_dourado + ding_suave.

## Regras de rodízio (obrigatórias)
1. Cada vídeo usa só 3 ou 4 famílias, nunca todas.
2. O som do hook alterna a cada vídeo: impacto, brilho, swell, notificação, shutter, e repete o ciclo.
3. Não repetir a mesma variação (a/b/c) da mesma família em dois vídeos seguidos.
4. No máximo 1 impacto grave por vídeo.
5. Vídeo calmo/educativo: whoosh + tick + cristal. Vídeo de captação/viral: hook + revelação + notificação.
6. Ao entregar as 3 versões de hook, cada versão usa um som de abertura diferente.
7. Antes de escolher, verificar no histórico (memória do projeto, biblioteca-sfx, índice de vídeos editados) quais famílias/variações saíram no último vídeo e evitar repetir. Ao terminar, anotar no índice do vídeo quais SFX foram usados.

## Mixagem (preferência fixa do Renato: efeitos sutis, nunca fortes)
- SFX sempre bem abaixo da trilha e da voz: ganho típico 0,25 a 0,5 em relação ao pico do WAV (que vem normalizado em -1 dBFS); impactos graves no máximo 0,55.
- Com voz: SFX cerca de 10 a 15 dB abaixo da voz; nunca cobrir palavra-chave.
- Exemplo FFmpeg para posicionar um efeito no tempo 2,4 s com ganho 0,4:
  `[1:a]adelay=2400|2400,volume=0.4[s1]; [0:a][s1]amix=inputs=2:normalize=0[a]`
- No numpy: somar o array do WAV na posição `int(t*SR)` multiplicado pelo ganho, e normalizar o mix final para pico de cerca de -1 dBFS.

## Extrair efeitos de um novo vídeo de referência
1. `ffmpeg -i video.mp4 -vn -ac 2 -ar 44100 audio.wav`; gerar espectrograma (`showspectrumpic`) e uma grade de quadros com o tempo escrito (`fps=2..4,drawtext=%{pts\:flt},tile`) para ler os nomes dos sons na tela.
2. Medir o envelope (RMS, energia em graves e agudos com librosa) para achar início e fim de cada som.
3. Cortar com fade de entrada de 4 ms e saída de 20 a 30 ms, normalizar pico em -1 dBFS, salvar WAV 24 bit em `2_extraidos_referencia/` numerado na sequência.
4. Anotar no LEIA-ME e na memória `biblioteca-sfx` a **situação** em que o vídeo usa cada som (isso é o mais valioso).
5. Se o som for meme, de marca ou de série/filme, marcar como só referência e criar um equivalente original no kit (acrescentar a função no `gerar_kit_sfx.py`, com variações a/b/c).

## Compliance
Instagram da Divine é conta comercial: só sons originais do kit ou com licença comercial. Avisar em uma linha se o Renato pedir um som de meme/marca e entregar o equivalente do kit.