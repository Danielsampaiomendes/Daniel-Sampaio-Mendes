# Template: Antes e Depois para TV (uso interno em consulta)

Aprovado em 24/10/2026 (Bumbum Up). Peças 16:9 1920x1080 no padrão Divine escuro e dourado.

Arquivos:
- common.py: cores, fontes, logo oficial (recortado de Logo_com_nome_vertical2.png e divine-simbolo-1024.png), recortes das fotos (CROPS) e textos de aviso e RT
- static.py: arte estática (logo, título, 3 pares ANTES e DEPOIS lado a lado, CTA, aviso, RT)
- video.py: vídeo (hook de abertura em 3 versões, cartão de título, um ângulo por vez sem zoom, grade completa, fechamento com logo empilhado)
- audio.py: trilha lounge suave sintetizada + SFX discretos da Biblioteca_SFX (converter os wav para 16 bits antes)

Regras aprovadas:
- Fotos sempre inteiras, mesmo tamanho e proporção, sem zoom e sem corte que esconda o corpo
- Marca d'água de app apagada na própria foto, nunca cortando a imagem
- Texto fixo: "Resultados variam de pessoa para pessoa. Imagens de paciente, com autorização. Uso exclusivo em consulta." + RT
- Uso interno: não publicar em galerias nem redes

Para reusar: trocar p1/p2/p3.jpg pelas montagens novas, ajustar CROPS e ANGLES em common.py e os textos do título; rodar static.py, video.py body e video.py 1/2/3, juntar com ffmpeg concat e mixar o audio.
