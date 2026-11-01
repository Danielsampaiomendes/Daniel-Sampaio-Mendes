"""Antes e depois padronizado (USO INTERNO: TV de consulta e celular na consulta; nunca postar, CFM 2.336/2023).

Você manda as fotos (um par por ângulo, ou uma montagem já lado a lado) e sai tudo no padrão aprovado
(Bumbum Up, 24/10/2026): fundo escuro e dourado, logo, título, pares ANTES | DEPOIS com fotos inteiras,
mesmo tamanho, sem zoom e sem corte, CTA, aviso "Uso exclusivo em consulta" e RT.

Tamanhos: TV 16:9 (pares lado a lado), Stories 9:16 e Feed 4:5 (pares empilhados). Para a TV sai também um
vídeo curto: abertura, um ângulo por vez (sem zoom), a grade completa e o fechamento.

projeto.yaml:
  tipo: antes_depois
  titulo: Bumbum Up
  subtitulo: bioestimulação glútea para mais firmeza e sustentação
  formatos: [tv, stories, feed45]
  video: true
  pares:
    - {antes: bruto/antes1.jpg, depois: bruto/depois1.jpg, angulo: PERFIL}
    - {montagem: bruto/montagem2.jpg, angulo: POSTERIOR}      # foto única com antes à esquerda e depois à direita
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .config import ROOT, hexrgb, hoje, load, slug
from .text import Estilo, render

ENTREGA = "Uso interno (nao postar)"


def _cfg() -> dict:
    return load("biblioteca")["antes_depois"]


def _cores() -> dict:
    c = load("marca")["cores"]
    return {k: hexrgb(v) for k, v in c.items()}


def novo(titulo: str, subtitulo: str = "") -> Path:
    from .carrossel import salvar
    pasta = ROOT / "projetos" / f"{hoje()}_antes-depois-{slug(titulo)}"
    if pasta.exists():
        raise SystemExit(f"Já existe: {pasta.relative_to(ROOT)}")
    for sub in ("bruto", "trabalho", "saida"):
        (pasta / sub).mkdir(parents=True)
    salvar(pasta, {"tipo": "antes_depois", "titulo": titulo, "subtitulo": subtitulo, "data": hoje(),
                   "uso_interno": True, "formatos": list(_cfg().get("formatos") or ["tv", "stories", "feed45"]),
                   "video": True, "cta": _cfg().get("cta", "Agende sua avaliação"),
                   "autorizacao_imagem": "pendente", "tags": ["antes e depois", "uso interno"], "pares": []})
    return pasta


# ---------------------------------------------------------------- fotos

def _abrir(pasta: Path, rel: str) -> Image.Image:
    from .carrossel import _abrir_imagem
    arq = pasta / rel
    if not arq.is_file():
        raise SystemExit(f"Foto não encontrada: {rel}")
    return _abrir_imagem(arq)


def fotos_do_par(pasta: Path, par: dict) -> tuple:
    """(antes, depois). Uma montagem é dividida ao meio: lado a lado se for larga, em cima e embaixo se for alta."""
    if par.get("montagem"):
        im = _abrir(pasta, par["montagem"])
        w, h = im.size
        if w >= h * 0.9:
            return im.crop((0, 0, w // 2, h)), im.crop((w - w // 2, 0, w, h))
        return im.crop((0, 0, w, h // 2)), im.crop((0, h - h // 2, w, h))
    if not (par.get("antes") and par.get("depois")):
        raise SystemExit("Cada par precisa de 'antes' e 'depois' (ou de uma 'montagem').")
    return _abrir(pasta, par["antes"]), _abrir(pasta, par["depois"])


def _proporcao(pares_fotos: list) -> float:
    """Mesma caixa para todas as fotos: a proporção mediana (largura/altura), para sobrar o mínimo de borda."""
    ps = sorted(f.width / f.height for par in pares_fotos for f in par)
    return ps[len(ps) // 2] if ps else 0.8


def _moldura(foto: Image.Image, w: int, h: int, cores: dict) -> Image.Image:
    """Foto INTEIRA dentro da caixa (sem zoom, sem corte), borda fina dourada; sobra preenchida com o fundo."""
    caixa = Image.new("RGBA", (w + 8, h + 8), (0, 0, 0, 0))
    interno = Image.new("RGB", (w, h), tuple(min(255, v + 8) for v in cores["fundo"]))
    f = ImageOps.contain(foto.convert("RGB"), (w, h), Image.LANCZOS)
    interno.paste(f, ((w - f.width) // 2, (h - f.height) // 2))
    caixa.paste(interno, (4, 4))
    ImageDraw.Draw(caixa).rectangle((0, 0, w + 7, h + 7), outline=cores["dourado"] + (230,), width=1)
    return caixa


# ---------------------------------------------------------------- desenho

def _txt(texto, arquivo, tam, cor, peso=None, tracking=0.0, caixa_alta=False, largura=1800):
    e = Estilo(arquivo, tam, cor, peso=peso, tracking=tracking, caixa_alta=caixa_alta)
    return render(texto, e, e, largura_max=largura, sombra=False)


def _fundo(W: int, H: int, cores: dict) -> Image.Image:
    img = Image.new("RGBA", (W, H), cores["fundo"] + (255,))
    brilho = Image.new("L", (W, H), 0)
    ImageDraw.Draw(brilho).ellipse((W * 0.29, -H * 0.24, W * 0.71, H * 0.39), fill=40)
    brilho = brilho.filter(ImageFilter.GaussianBlur(max(W, H) / 12))
    img.paste(Image.new("RGBA", (W, H), cores["dourado_escuro"] + (255,)), (0, 0), brilho)
    return img


def desenhar(p: dict, pares_fotos: list, formato: str, so: int | None = None, fase: str = "grade") -> Image.Image:
    """Uma peça. fase: 'abertura' (logo e título), 'grade' (todos os pares ou só o par 'so') ou 'fechamento'."""
    from . import brand
    cfg, cores, marca = _cfg(), _cores(), load("marca")
    f = load("exportacao")["formatos"][formato]
    W, H = int(f["largura"]), int(f["altura"])
    deitado = W > H
    esc = min(W / 1920, H / 1080) if deitado else W / 1080
    img = _fundo(W, H, cores)
    largura_txt = int(W * 0.86)

    def centro_x(im, y):
        img.alpha_composite(im, ((W - im.width) // 2, int(y)))

    if fase == "abertura":
        logo = brand.empilhado(int((230 if deitado else 260) * esc))
        tit = _txt(p.get("titulo", ""), "Italiana-Regular.ttf", 120 * esc, cores["off_white"], largura=largura_txt)
        sub = _txt(p.get("subtitulo", ""), "Lora-Italic[wght].ttf", 40 * esc, cores["dourado"], largura=largura_txt) \
            if p.get("subtitulo") else None
        total = logo.height + 60 * esc + tit.height + ((30 * esc + sub.height) if sub else 0)
        y = (H - total) / 2
        centro_x(logo, y)
        y += logo.height + 60 * esc
        centro_x(tit, y)
        if sub:
            centro_x(sub, y + tit.height + 30 * esc)
    elif fase == "fechamento":
        logo = brand.empilhado(int(200 * esc))
        cta = _txt(p.get("cta") or cfg.get("cta", ""), "Lora-Italic[wght].ttf", 52 * esc, cores["dourado"], peso=500,
                   largura=largura_txt)
        y = (H - logo.height - 50 * esc - cta.height) / 2 - 40 * esc
        centro_x(logo, y)
        centro_x(cta, y + logo.height + 50 * esc)
    else:
        # cabeçalho
        y = 62 * esc if deitado else 150 * esc
        logo = brand.horizontal(int(70 * esc))
        centro_x(logo, y)
        y += logo.height + 26 * esc
        tit = _txt(p.get("titulo", ""), "Italiana-Regular.ttf", (96 if deitado else 84) * esc, cores["off_white"],
                   largura=largura_txt)
        centro_x(tit, y)
        y += tit.height + 18 * esc
        if p.get("subtitulo"):
            sub = _txt(p["subtitulo"], "Lora-Italic[wght].ttf", 30 * esc, cores["dourado"], largura=largura_txt)
            centro_x(sub, y)
            y += sub.height
        topo = y + (70 if deitado else 40) * esc
        # rodapé (de baixo para cima)
        rt = _txt(marca["responsavel_tecnico"]["completo"], "Poppins-Light.ttf", 17 * esc, cores["rodape"],
                  largura=largura_txt)
        aviso = _txt(cfg["aviso"], "Poppins-Light.ttf", 19 * esc, cores["texto"], largura=largura_txt)
        cta = _txt(p.get("cta") or cfg.get("cta", ""), "Lora-Italic[wght].ttf", 34 * esc, cores["dourado"], peso=500,
                   largura=largura_txt)
        base = H - (52 * esc if deitado else 120 * esc)
        centro_x(rt, base - rt.height)
        centro_x(aviso, base - rt.height - 12 * esc - aviso.height)
        y_cta = base - rt.height - aviso.height - 40 * esc - cta.height
        centro_x(cta, y_cta)
        fundo_area = y_cta - 40 * esc
        _grade(img, p, pares_fotos if so is None else [pares_fotos[so]],
               (list(p.get("pares") or [{}] * len(pares_fotos)) if so is None else [(p.get("pares") or [{}])[so]]),
               (int(W * 0.05), int(topo), int(W * 0.90), int(fundo_area - topo)), deitado, esc, cores,
               _proporcao(pares_fotos))
    # borda fina dourada (padrão TV)
    ImageDraw.Draw(img).rectangle((int(28 * esc), int(28 * esc), W - int(28 * esc) - 1, H - int(28 * esc) - 1),
                                  outline=cores["dourado_escuro"] + (160,), width=2)
    return img.convert("RGB")


def _grade(img, p, fotos, pares, area, deitado, esc, cores, prop):
    x0, y0, aw, ah = area
    n = len(fotos)
    if not n:
        aviso = _txt("Envie as fotos de antes e depois", "Lora-Italic[wght].ttf", 40 * esc, cores["dourado"])
        img.alpha_composite(aviso, (x0 + (aw - aviso.width) // 2, y0 + (ah - aviso.height) // 2))
        return
    rot = _cfg().get("rotulos") or ["ANTES", "DEPOIS"]
    lab_h, ang_h = int(46 * esc), int(84 * esc)
    gap_in, gap_out = int(12 * esc), int(40 * esc)

    def tamanho_foto(cols, rows):
        cel_w = (aw - gap_out * (cols - 1)) / cols
        cel_h = (ah - gap_out * (rows - 1)) / rows
        return int(max(40, min((cel_w - gap_in - 16) / 2, (cel_h - lab_h - ang_h - 8) * prop)))

    # a arrumação que deixa as fotos maiores: lado a lado, empilhado ou em 2 colunas
    opcoes = {(n, 1), (1, n), (min(2, n), -(-n // 2))}
    cols, rows = max(opcoes, key=lambda cr: (tamanho_foto(*cr), cr[0] if deitado else -cr[0]))
    pw = tamanho_foto(cols, rows)
    ph = int(pw / prop)
    par_w, par_h = 2 * (pw + 8) + gap_in, lab_h + ph + 8 + ang_h
    tot_w = cols * par_w + (cols - 1) * gap_out
    tot_h = rows * par_h + (rows - 1) * gap_out
    sx, sy = x0 + (aw - tot_w) // 2, y0 + (ah - tot_h) // 2
    dr = ImageDraw.Draw(img)
    for k, ((antes, depois), par) in enumerate(zip(fotos, pares)):
        c, r = k % cols, k // cols
        na_linha = min(cols, n - r * cols)                     # última linha incompleta fica centralizada
        px = sx + (cols - na_linha) * (par_w + gap_out) // 2 + c * (par_w + gap_out)
        py = sy + r * (par_h + gap_out)
        for i, foto in enumerate((antes, depois)):
            fx = px + i * (pw + 8 + gap_in)
            lab = _txt(rot[i], "Jost[wght].ttf", 19 * esc * min(1.0, max(0.6, pw / (160 * esc))), cores["dourado"] if i else cores["texto"], peso=400,
                       tracking=0.3)
            img.alpha_composite(lab, (fx + (pw + 8 - lab.width) // 2, py + (lab_h - lab.height) // 2 - int(6 * esc)))
            img.alpha_composite(_moldura(foto, pw, ph, cores), (fx, py + lab_h))
        if par.get("angulo"):
            cx, yy = px + par_w / 2, py + lab_h + ph + 8 + int(26 * esc)
            dr.line((cx - 60 * esc, yy, cx + 60 * esc, yy), fill=cores["dourado_escuro"] + (200,), width=1)
            ang = _txt(str(par["angulo"]).upper(), "TenorSans-Regular.ttf", 22 * esc, cores["off_white"], tracking=0.22)
            img.alpha_composite(ang, (int(cx - ang.width / 2), int(yy + 12 * esc)))


# ---------------------------------------------------------------- vídeo (TV)

def _video(p: dict, fotos: list, formato: str, destino: Path) -> Path:
    """Abertura, um ângulo por vez (sem zoom), grade completa e fechamento, com fusões suaves. 30 fps."""
    fps = int(load("exportacao").get("fps", 30))
    por_par = float(_cfg().get("video_segundos_por_par", 4))
    cenas = [(desenhar(p, fotos, formato, fase="abertura"), 3.0)]
    if len(fotos) > 1:
        cenas += [(desenhar(p, fotos, formato, so=k), por_par) for k in range(len(fotos))]
    cenas += [(desenhar(p, fotos, formato), max(6.0, por_par + 2)), (desenhar(p, fotos, formato, fase="fechamento"), 4.0)]
    W, H = cenas[0][0].size
    fusao = int(0.7 * fps)
    arr = [np.asarray(c, dtype=np.float32) for c, _ in cenas]
    tmp = destino.with_name(f".{destino.stem}.tmp.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(fps), "-i", "-", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-tune", "stillimage", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(tmp)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        preto = np.zeros_like(arr[0])
        for k, (_, dur) in enumerate(cenas):
            n = int(dur * fps)
            for i in range(n):
                if k == 0 and i < fusao:                       # entra do preto
                    q = (preto + (arr[0] - preto) * (i / fusao))
                elif k > 0 and i < fusao:                      # fusão com a cena anterior
                    a = i / fusao
                    q = arr[k - 1] * (1 - a) + arr[k] * a
                elif k == len(cenas) - 1 and i >= n - fusao:   # sai para o preto
                    q = arr[k] * ((n - i) / fusao)
                else:
                    q = arr[k]
                proc.stdin.write(q.astype(np.uint8).tobytes())
    finally:
        proc.stdin.close()
        proc.wait()
    if proc.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise SystemExit("O FFmpeg falhou ao montar o vídeo do antes e depois.")
    tmp.replace(destino)
    return destino


# ---------------------------------------------------------------- exportar

def textos(p: dict) -> list:
    return [x for x in (p.get("titulo"), p.get("subtitulo"), p.get("cta")) if x] + \
        [str(par.get("angulo")) for par in p.get("pares") or [] if par.get("angulo")]


def exportar(pasta: Path, p: dict) -> dict:
    """PNG de cada tamanho (+ MP4 da TV) com NAO-POSTAR no nome, em saida/ e entregas/AAAA-MM/Uso interno."""
    from . import aprendizado
    from .compliance import revisar
    if p.get("autorizacao_imagem") not in ("sim", "ok", "autorizado", True):
        raise SystemExit("Antes e depois só sai com a autorização de imagem da paciente: marque 'autorizacao_imagem: sim'.")
    fotos = [fotos_do_par(pasta, par) for par in p.get("pares") or []]
    if not fotos:
        raise SystemExit("Envie pelo menos um par de fotos (antes e depois).")
    ach = revisar({**p, "_pasta": pasta, "uso_interno": True}, textos(p))
    for a in ach:
        print("  " + a.linha())
    if any(a.nivel == "erro" for a in ach):
        raise SystemExit("Revisor bloqueou os textos. Corrija acima.")
    saida = pasta / "saida"
    saida.mkdir(exist_ok=True)
    ent = ROOT / "entregas" / str(p.get("data", hoje()))[:7] / ENTREGA
    ent.mkdir(parents=True, exist_ok=True)
    base = f"{p.get('data', hoje())}_antes-depois_{slug(p.get('titulo', ''), 30)}"
    arquivos = []
    for fmt in p.get("formatos") or ["tv"]:
        if fmt not in load("exportacao")["formatos"]:
            continue
        arq = saida / f"{base}_{fmt}_NAO-POSTAR.png"
        desenhar(p, fotos, fmt).save(arq, optimize=True)
        arquivos.append(arq)
        print(f"  {fmt}: {arq.relative_to(pasta)}")
        if fmt == "tv" and p.get("video", True) and shutil.which("ffmpeg"):
            mp4 = _video(p, fotos, fmt, saida / f"{base}_{fmt}_NAO-POSTAR.mp4")
            arquivos.append(mp4)
            print(f"  vídeo TV: {mp4.relative_to(pasta)}")
    for a in arquivos:
        shutil.copy2(a, ent / a.name)
        try:
            versao = a.stem.split("_")[-2] + ("-video" if a.suffix == ".mp4" else "")
            aprendizado.marcar(pasta, versao, arquivo=f"saida/{a.name}", rede="consulta", status="aprovado",
                               entrega=str((ent / a.name).relative_to(ROOT)))
        except Exception as e:
            print(f"  aviso: não registrei na programação ({e})")
    (pasta / "relatorio.md").write_text(
        f"# {p.get('titulo')} · antes e depois (USO INTERNO)\n\n{len(fotos)} par(es) · "
        f"{', '.join(p.get('formatos') or [])}\n\n**Uso exclusivo em consulta. Não postar** (CFM 2.336/2023).\n\n"
        f"Entregue em `{ent.relative_to(ROOT)}`.\n\n" + "\n".join(f"- {a.linha()}" for a in ach) + "\n",
        encoding="utf-8")
    return {"arquivos": [str(a) for a in arquivos]}


def previa(pasta: Path, p: dict, formato: str = "tv", largura: int = 960) -> bytes:
    import io
    completos, fotos = [], []
    for par in p.get("pares") or []:               # prévia mostra só os pares que já têm as fotos
        try:
            fotos.append(fotos_do_par(pasta, par))
            completos.append(par)
        except SystemExit:
            continue
    img = desenhar({**p, "pares": completos}, fotos, formato)
    img = img.resize((largura, int(img.height * largura / img.width)), Image.LANCZOS)
    b = io.BytesIO()
    img.save(b, "JPEG", quality=88)
    return b.getvalue()
