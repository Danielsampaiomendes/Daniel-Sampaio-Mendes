"""Biblioteca de imagens: logomarcas, fotos das pessoas, das tecnologias, da clínica e dos produtos.

As categorias e o que cada uma precisa ter estão em config/biblioteca.yaml. O app:
  - mostra o que falta enviar (tela Biblioteca e aviso dentro do projeto quando o tema pede uma foto)
  - usa sozinho: logo oficial na marca, foto de perfil nos cartões, foto da tecnologia na capa do carrossel/post
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from .config import ROOT, load, slug

IMAGEM = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}


def _cfg() -> dict:
    return load("biblioteca")


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def pasta(cat: str) -> Path:
    c = _cfg()["categorias"].get(cat)
    if not c:
        raise ValueError("categoria desconhecida")
    p = ROOT / c["pasta"]
    p.mkdir(parents=True, exist_ok=True)
    return p


def _arquivos(p: Path) -> list:
    if not p.exists():
        return []
    return sorted(f for f in p.iterdir() if f.is_file() and f.suffix.lower() in IMAGEM and not f.name.startswith("."))


def achar(cat: str, nome_item: str) -> Path | None:
    """O arquivo de um item (pelo nome sem extensão, ou começando com ele: 'laser-co2-2.jpg' também vale)."""
    c = _cfg()["categorias"].get(cat)
    if not c:
        return None
    alvo = slug(nome_item, 60)
    fs = _arquivos(ROOT / c["pasta"])
    exato = [f for f in fs if slug(f.stem, 60) == alvo]
    if exato:
        return exato[0]
    return next((f for f in fs if slug(f.stem, 60).startswith(alvo)), None)


def listar() -> list:
    """Categorias com os itens esperados (tem / falta), os arquivos e a dica de como fotografar."""
    out = []
    for chave, c in _cfg()["categorias"].items():
        fs = _arquivos(ROOT / c["pasta"])
        itens, usados = [], set()
        for it in c.get("itens") or []:
            f = achar(chave, it["arquivo"])
            if f:
                usados.add(f.name)
            itens.append({**it, "tem": f.name if f else None})
        out.append({"chave": chave, "nome": c["nome"], "pasta": c["pasta"], "dica": c.get("dica", ""),
                    "itens": itens, "arquivos": [f.name for f in fs],
                    "extras": [f.name for f in fs if f.name not in usados],
                    "faltam": sum(1 for i in itens if not i["tem"]),
                    "faltam_obrigatorios": sum(1 for i in itens if not i["tem"] and i.get("obrigatorio"))})
    return out


def pedidos(tema: str = "", tipo: str = "video") -> list:
    """O que pedir ao Renato agora: o essencial que falta e a foto da tecnologia do tema, se não tiver."""
    out = []
    t = _norm(tema)
    for cat in listar():
        for it in cat["itens"]:
            if it["tem"]:
                continue
            temas = [_norm(x) for x in it.get("temas") or []]
            do_tema = bool(t) and any(re.search(rf"\b{re.escape(x)}\b", t) for x in temas if x)
            if do_tema or (it.get("obrigatorio") and cat["chave"] in ("marca", "pessoas")):
                out.append({"categoria": cat["chave"], "arquivo": it["arquivo"], "nome": it["nome"],
                            "por_que": f"o tema é {tema}" if do_tema else it.get("uso", ""), "dica": cat["dica"]})
    return out


def foto_do_tema(tema: str) -> Path | None:
    """Foto da biblioteca que combina com o tema (tecnologia, sala, produto), para fundo de capa e post."""
    t = _norm(tema)
    if not t:
        return None
    melhor, tam = None, 0
    for chave, c in _cfg()["categorias"].items():
        if chave in ("marca", "pessoas"):
            continue
        for it in c.get("itens") or []:
            for x in it.get("temas") or []:
                n = _norm(x)
                if n and re.search(rf"\b{re.escape(n)}\b", t) and len(n) > tam:
                    f = achar(chave, it["arquivo"])
                    if f:
                        melhor, tam = f, len(n)
    return melhor


def logo(item: str) -> Path | None:
    return achar("marca", item)


def foto_pessoa(chave: str) -> Path | None:
    return achar("pessoas", f"{chave}_perfil")


def salvar(cat: str, nome: str, dados_ou_stream, n: int | None = None, item: str | None = None) -> Path:
    """Grava a imagem na categoria. Com 'item', renomeia para o nome esperado (ex.: endolaser.jpg).
    Se já existir, a anterior vai para _arquivo/biblioteca/ (nunca apaga)."""
    import os
    import shutil
    import time
    ext = Path(nome).suffix.lower()
    if ext not in IMAGEM:
        raise ValueError("só imagens (.jpg, .png, .webp, .heic)")
    destino_dir = pasta(cat)
    base = slug(item, 60) if item else slug(Path(nome).stem, 60)
    destino = destino_dir / f"{base}{ext}"
    parcial = destino_dir / f".{destino.name}.parcial"
    with open(parcial, "wb") as fh:
        if isinstance(dados_ou_stream, (bytes, bytearray)):
            fh.write(dados_ou_stream)
        else:
            falta = n or 0
            while falta > 0:
                bloco = dados_ou_stream.read(min(1 << 20, falta))
                if not bloco:
                    break
                fh.write(bloco)
                falta -= len(bloco)
            if falta != 0:
                fh.close()
                parcial.unlink(missing_ok=True)
                raise ValueError("o envio foi interrompido; mande de novo")
    antigos = [f for f in _arquivos(destino_dir) if slug(f.stem, 60) == base] if item else \
        ([destino] if destino.exists() else [])
    for f in antigos:
        arq = ROOT / "_arquivo" / "biblioteca" / cat
        arq.mkdir(parents=True, exist_ok=True)
        shutil.move(str(f), arq / f"{f.stem}_{time.strftime('%Y%m%d-%H%M%S')}{f.suffix}")
    os.replace(parcial, destino)
    from . import brand
    for fn in (brand.simbolo, brand.horizontal, brand.empilhado):
        fn.cache_clear()
    return destino


def miniatura(cat: str, nome: str, largura: int = 320) -> bytes:
    import io
    from PIL import Image, ImageOps
    f = (pasta(cat) / Path(nome).name)
    if not f.is_file():
        raise ValueError("imagem não encontrada")
    from .carrossel import _abrir_imagem
    im = _abrir_imagem(f) if f.suffix.lower() in (".heic", ".heif") else ImageOps.exif_transpose(Image.open(f))
    fundo_transparente = im.mode in ("RGBA", "LA", "P")
    im = im.convert("RGBA")
    im.thumbnail((largura, largura * 2), Image.LANCZOS)
    b = io.BytesIO()
    if fundo_transparente:
        im.save(b, "PNG")
    else:
        im.convert("RGB").save(b, "JPEG", quality=85)
    return b.getvalue()
