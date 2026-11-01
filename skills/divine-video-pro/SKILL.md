---
name: "divine-video-pro"
description: "Use ao editar qualquer vídeo da Divine ou do Dr. Daniel para elevar a qualidade: áudio tratado automaticamente, profundidade 2.5D/3D, perspectiva dinâmica, texto atrás da pessoa e acabamento premium."
---

# Divine Video Pro

Camada de acabamento aplicada DEPOIS do corte e ANTES dos textos finais, em todo vídeo da Divine (template Divine, Daniel e George). Mantém as regras já aprovadas: edição suave e elegante, nada brusco na abertura, SFX baixos, 3 versões com hooks diferentes, compliance CFM/Anvisa.

## Ordem de execução (pipeline)
1. Diagnóstico do bruto (ffprobe: resolução, fps, loudness com ebur128, ruído de fundo).
2. Limpeza de imagem: estabilização, denoise, nitidez, cor.
3. Áudio automático (sempre, sem o Renato pedir).
4. Profundidade: recorte da pessoa + parallax 2.5D + texto atrás da pessoa.
5. Movimento de câmera virtual (perspectiva, push in, tilt).
6. Acabamento premium (glow dourado, sombra nos textos, light leak, grão fino).
7. Export Instagram e checagem visual de frames (abrir 4 a 6 frames e olhar).

Instalar o que faltar: `pip install --break-system-packages rembg[cpu] mediapipe opencv-python transformers torch` e checar `ffmpeg -filters | grep -E 'vidstab|arnndn|lut3d'`.

## 1. Áudio automático (aplicar em toda fala)
Cadeia padrão de voz (ffmpeg -af):
```
highpass=f=80,lowpass=f=14000,
afftdn=nr=12:nf=-30,
equalizer=f=200:t=q:w=1:g=-2,equalizer=f=3500:t=q:w=1.2:g=2.5,
deesser=i=0.4,
acompressor=threshold=-20dB:ratio=3:attack=8:release=120:makeup=3,
alimiter=limit=0.95
```
- Ruído forte (ar, rua, aparelho ligado): trocar afftdn por `arnndn=m=rnnoise.rnnn` (modelo RNNoise) ou separar a voz com Demucs (`demucs --two-stems=vocals`).
- Trilha com fala: ducking automático com `sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400`, trilha sempre bem abaixo da voz.
- Loudness final em duas passadas: `loudnorm=I=-14:TP=-1.5:LRA=9` (padrão Instagram/Reels). TV da recepção: I=-16.
- Emendas de fala sempre com crossfade de 15 a 30 ms (acrossfade) para não estalar.
- SFX da Biblioteca_SFX sempre de 12 a 18 dB abaixo da voz.

## 2. Imagem limpa
- Estabilizar celular: `vidstabdetect=shakiness=5` e depois `vidstabtransform=smoothing=20,unsharp=5:5:0.6`.
- Denoise leve em luz baixa: `hqdn3d=1.5:1.5:6:6`.
- Nitidez de pele elegante (sem exagero): `cas=0.35`.
- Cor: contraste e calor sutis, `eq=contrast=1.05:saturation=1.05`, curva levemente quente; nunca alterar tom de pele de forma que pareça resultado de procedimento (CFM).
- Slow motion suave: `minterpolate=fps=60:mi_mode=mci` ou RIFE se disponível.

## 3. Profundidade 2.5D (efeito tridimensional)
**Recorte da pessoa por frame:** mediapipe selfie segmentation (rápido) ou rembg (mais preciso). Salvar máscara alfa por frame.

**Texto atrás da pessoa (alto alcance):** camadas fundo, texto, pessoa recortada por cima. O título fica entre o fundo e o corpo, parecendo estar no ambiente. Regra Divine: texto nunca cobre o rosto; usar no terço superior atrás da cabeça/ombros.

**Parallax 2.5D em foto ou frame congelado:** gerar mapa de profundidade com Depth Anything (transformers, `depth-anything/Depth-Anything-V2-Small-hf`), deslocar pixels proporcionalmente à profundidade ao longo de um movimento lento (3 a 5 s). Ótimo para capas animadas, fotos da clínica, aparelhos (CMSlim, InBody, CO2) e TV 16:9.

**Fundo com profundidade de campo:** desfocar só o fundo pela máscara (`gblur=sigma=6` no fundo) para efeito de lente cara.

## 4. Câmera virtual e perspectiva
Sempre com easing (ease in out), nunca linear, nunca tremor:
- Push in lento na fala importante: escala 1.00 para 1.08 em 2 a 3 s.
- Punch in suave no corte de ênfase: 1.00 para 1.12 em 6 frames com ease out (substitui o corte seco sem ser brusco).
- Tilt 3D de cartões, laudos e prints: filtro `perspective` animado (x0..y3) para o objeto inclinar de 8 a 12 graus enquanto entra.
- Dolly zoom leve (pessoa fixa, fundo se afasta) usando a máscara: fundo escala 1.10 para 1.00 enquanto pessoa escala 1.00 para 1.04.
- Rotação de texto em 3D: renderizar o texto em PNG e aplicar perspective animado, ou Three.js/Remotion headless quando precisar de giro real.
- Abertura: movimento já começa em andamento e suave (regra: sem slam, sem shake, sem flash forte).

## 5. Acabamento premium
- Sombra suave atrás dos textos (offset 0, blur 18 px, preto 45%): dá volume e leitura.
- Glow dourado fino em palavras-chave (#B8A169/#CCBD91), duplicar a camada de texto com gblur e opacidade 40%.
- Light leak dourado discreto nas transições (overlay em blend screen, opacidade até 25%).
- Grão de filme fino (`noise=alls=4:allf=t`) no final para unificar celular e gráficos.
- Vinheta leve (`vignette=PI/5`).
- Brilho sutil na área tratada em ilustrações de corpo (silhueta dourada contínua).

## 6. Export
- Reels/Stories: 1080x1920, 30 fps (ou 60 em slow), H.264 High, `-crf 17 -preset slow -pix_fmt yuv420p -movflags +faststart`, AAC 48 kHz 192k.
- TV: 1920x1080, mudo ou trilha a -16 LUFS.
- Prévia leve para galeria: 540p.

## Checagem antes de entregar
- Ouvir início, meio e fim: voz clara, sem chiado, sem estalo, trilha abaixo.
- Abrir frames: máscara sem borda serrilhada, texto não toca o rosto, áreas seguras do Instagram livres.
- Movimentos suaves, nada brusco na abertura.
- Compliance: sem antes/depois, sem promessa, RT presente, autorização de imagem confirmada.

## Entrega
Informar em uma linha o que foi aplicado (ex.: "voz limpa e nivelada a -14 LUFS, texto atrás da pessoa no hook, push in na frase principal") e seguir o padrão de 3 versões com hooks diferentes.