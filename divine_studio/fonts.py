"""Carregamento de fontes (inclusive variáveis) e das combinações A a N."""
from __future__ import annotations

from functools import lru_cache

from PIL import ImageFont

from .config import ROOT, load


def pasta_fontes():
    return ROOT / load("fontes").get("pasta", "Biblioteca_Fontes/ttf")


@lru_cache(maxsize=256)
def fonte(arquivo: str, tamanho: int, peso: int | None = None) -> ImageFont.FreeTypeFont:
    caminho = pasta_fontes() / arquivo
    if not caminho.exists():
        raise SystemExit(
            f"Fonte não encontrada: {caminho}\nRode: bash Biblioteca_Fontes/baixar_fontes.sh"
        )
    f = ImageFont.truetype(str(caminho), int(tamanho))
    if peso is not None:
        try:
            eixos = f.get_variation_axes()
            valores = []
            for e in eixos:
                nome = e.get("name", b"")
                nome = nome.decode() if isinstance(nome, bytes) else str(nome)
                if nome.lower().startswith(("weight", "wght")):
                    valores.append(max(e["minimum"], min(e["maximum"], peso)))
                else:
                    valores.append(e.get("default", e["minimum"]))
            f.set_variation_by_axes(valores)
        except Exception:
            pass
    return f


def combinacao(codigo: str) -> dict:
    combos = load("fontes")["combinacoes"]
    if codigo not in combos:
        raise SystemExit(f"Combinação de fontes '{codigo}' não existe. Opções: {', '.join(combos)}")
    c = dict(combos[codigo])
    c["codigo"] = codigo
    return c


def todas_combinacoes() -> list:
    return list(load("fontes")["combinacoes"].keys())


def marca(papel: str) -> str:
    return load("fontes")["marca"][papel]
