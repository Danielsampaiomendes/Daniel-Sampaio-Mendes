---
name: "divine-legendas-animadas"
description: "Use ao colocar legenda falada em qualquer Reels ou Stories da Divine: legenda palavra a palavra sincronizada, com destaque dourado na palavra-chave e animação suave."
---

# Legendas animadas Divine

## Transcrição
1. Extrair o áudio já tratado (voz limpa da divine-video-pro).
2. Transcrever com timestamps por palavra: `pip install --break-system-packages faster-whisper` e rodar modelo `medium` ou `large-v3`, idioma pt, `word_timestamps=True`.
3. Revisar a transcrição: corrigir nomes (Divine, CMSlim, Hybrius, InBody, Dr. Daniel), termos médicos e acentos. Remover da legenda qualquer frase cortada por compliance.

## Estilo (padrão Divine)
- Posição: centro do peito, nunca sobre o rosto, dentro da área segura do Instagram (fora dos 250 px de baixo e da faixa de ícones à direita).
- Blocos de 2 a 4 palavras, no máximo 2 linhas.
- Fonte: Poppins Medium off-white #F5F4F1; palavra-chave do bloco em Lora Itálico dourado #CCBD91.
- Palavra falada no momento: leve aumento (escala 1.00 para 1.06) e brilho dourado sutil; as outras ficam em 85% de opacidade.
- Entrada de cada bloco: fade de 120 ms com deslize de 8 px para cima. Nada de pulo, quique ou cor neon.
- Sombra suave atrás do texto para leitura em qualquer fundo.
- Sem travessões ou tracinhos no texto da tela.

## Escolha das palavras-chave
Destacar em dourado: a dor (gordura localizada, queda, flacidez), a virada (diagnóstico, causa) e o CTA (avaliação, sessão). Uma por bloco, no máximo.

## Render
- Gerar arquivo .ass com karaokê (\k) e estilos, ou renderizar PNGs por bloco e compor com ffmpeg overlay.
- Conferir sincronia em 3 pontos do vídeo; atraso aceitável até 80 ms.
- Exportar também o .srt limpo para usar como legenda nativa quando o Renato preferir.

## Checagem
Texto não toca o rosto, tempo de leitura suficiente, nenhum termo proibido (promessa, nome de medicamento), grafia correta.