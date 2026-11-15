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


class ErroDeConfig(yaml.YAMLError, ValueError):
    """Arquivo de regras (config/*.yaml) com erro de escrita: a mensagem diz qual arquivo e qual linha."""


@lru_cache(maxsize=None)
def load(name: str) -> dict:
    try:
        with open(CONFIG / f"{name}.yaml", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        marca = getattr(e, "problem_mark", None)
        onde = f", linha {marca.line + 1}" if marca else ""
        raise ErroDeConfig(f"config/{name}.yaml está com erro de escrita{onde}: "
                           f"{getattr(e, 'problem', None) or e}. Corrija esse arquivo (ou volte a versão anterior "
                           "dele) e tente de novo.") from e


def save(name: str, data: dict, header: str = "") -> None:
    from .guardar import gravar_texto
    text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000)
    gravar_texto(CONFIG / f"{name}.yaml", header + text)      # troca atômica: nunca fica um YAML pela metade
    load.cache_clear()


def anexar_item(name: str, chave: str, item: dict) -> bool:
    """Acrescenta um item a uma lista do topo do YAML SEM reescrever o arquivo: os comentários ficam.

    Os arquivos de config são a documentação das regras (cada valor tem o porquê ao lado). Regravar com
    yaml.safe_dump apagava todos os comentários na primeira regra nova. Devolve False se o arquivo não tem o
    formato esperado (quem chama cai no save(), que continua correto, só sem comentários).
    """
    from .guardar import gravar_texto
    arq = CONFIG / f"{name}.yaml"
    try:
        texto = arq.read_text(encoding="utf-8")
        antes = list((yaml.safe_load(texto) or {}).get(chave) or [])
    except (OSError, yaml.YAMLError, TypeError):
        return False
    linhas = texto.split("\n")
    alvo = next((i for i, ln in enumerate(linhas) if re.match(rf"^{re.escape(chave)}:\s*(\[\s*\])?\s*(#.*)?$", ln)), None)
    if alvo is None:
        return False
    linhas[alvo] = re.sub(r":\s*\[\s*\]", ":", linhas[alvo], count=1)
    fim = alvo + 1
    while fim < len(linhas) and (not linhas[fim].strip() or linhas[fim][0] in " \t-#"):
        fim += 1                                   # o bloco da lista vai até a próxima chave do topo
    while fim > alvo + 1 and (not linhas[fim - 1].strip() or linhas[fim - 1].startswith("#")):
        fim -= 1                                   # o item entra depois do último item, antes de linhas em branco
    nova = "  - " + yaml.safe_dump(item, allow_unicode=True, sort_keys=False, width=100000,
                                   default_flow_style=True).strip()
    novo = "\n".join(linhas[:fim] + [nova] + linhas[fim:])
    try:
        depois = yaml.safe_load(novo) or {}
    except yaml.YAMLError:
        return False
    if depois.get(chave) != antes + [item] or {k: v for k, v in depois.items() if k != chave} != \
            {k: v for k, v in (yaml.safe_load(texto) or {}).items() if k != chave}:
        return False                               # só grava se o resultado é exatamente "o de antes + o item"
    gravar_texto(arq, novo)
    load.cache_clear()
    return True


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


def nome_proprio(t: str) -> str:
    """'LASER DE CO2' -> 'Laser de CO2' (siglas e números preservados, conectivos em minúscula)."""
    peq = {"de", "da", "do", "das", "dos", "e", "em", "no", "na", "com", "para"}
    out = []
    for k, w in enumerate(str(t).split()):
        if re.search(r"\d", w):
            out.append(w.upper())
        elif w.lower() in peq and k:
            out.append(w.lower())
        else:
            out.append(w[:1].upper() + w[1:].lower())
    return " ".join(out)


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
