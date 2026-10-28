"""Carrega as configurações YAML e resolve caminhos a partir da raiz do repositório."""
from __future__ import annotations

import datetime as _dt
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"


@lru_cache(maxsize=None)
def load(name: str) -> dict:
    with open(CONFIG / f"{name}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save(name: str, data: dict, header: str = "") -> None:
    load.cache_clear()
    text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000)
    with open(CONFIG / f"{name}.yaml", "w", encoding="utf-8") as f:
        f.write(header + text)


def hexrgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def cor(nome: str) -> tuple:
    """Cor da marca pelo nome (dourado, fundo, off_white...) ou hex direto."""
    if nome.startswith("#"):
        return hexrgb(nome)
    return hexrgb(load("marca")["cores"][nome])


def slug(texto: str, maximo: int = 40) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-").lower()
    return t[:maximo].strip("-") or "video"


def hoje() -> str:
    return _dt.date.today().isoformat()


def ler_projeto(pasta: Path) -> dict:
    arq = Path(pasta) / "projeto.yaml"
    if not arq.exists():
        raise SystemExit(f"Não achei {arq}. Crie com: python3 -m divine_studio novo <nome>")
    with open(arq, encoding="utf-8") as f:
        p = yaml.safe_load(f) or {}
    p["_pasta"] = Path(pasta).resolve()
    return p
