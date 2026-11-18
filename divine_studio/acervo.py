"""Acervo: todas as imagens da pasta Divine Medical Spa Marketing catalogadas e ligadas ao app (config/acervo.yaml).

- varrer(): índice incremental (só relê o que mudou) em assets/.acervo.json, com tamanho, categoria, palavras do nome,
  se é clara ou escura e se foi feita com IA (Canva).
- abastecer(): copia para a Biblioteca (assets/) a melhor versão de cada logo e os fundos de IA novos. Nada é movido
  nem apagado: o arquivo trocado por um melhor vai para _arquivo/assets/.
- buscar(): acha imagem por palavras ("laser co2", "fundo esferas"), para o campo de pedidos e para o painel.
- fundos(): o banco de fundos Liquid Glass (assets/fundos), separado em escuros e claros pelo que a imagem é.
"""
from __future__ import annotations

import json
import shutil
import time
import unicodedata
from pathlib import Path

from .config import ROOT, load

INDICE = ROOT / "assets" / ".acervo.json"


def cfg() -> dict:
    try:
        return load("acervo")
    except FileNotFoundError:
        return {}


def _norm(t: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", str(t)) if unicodedata.category(c) != "Mn").lower()
    return "".join(ch if ch.isalnum() or ch in "/." else " " for ch in s)


def ler() -> dict:
    try:
        return json.loads(INDICE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"imagens": {}, "em": ""}


def _medir(arq: Path) -> dict | None:
    from PIL import Image
    try:
        with Image.open(arq) as im:
            w, h = im.size
            mini = im.convert("L").resize((16, 16))
            claro = sum(mini.tobytes()) / 256 > 140
    except Exception:
        return None
    return {"w": w, "h": h, "claro": claro}


def _categoria(caminho: str) -> str:
    for regra in cfg().get("categorias") or []:
        if any(_norm(p).strip() in caminho for p in regra.get("palavras") or []):
            return regra["nome"]
    return "outras"


def varrer(raiz: Path | None = None, limite_s: float = 120.0) -> dict:
    """Atualiza o índice. Devolve {"total", "novas", "ia", "em"}. Para depois de `limite_s` e continua na próxima."""
    raiz = Path(raiz or ROOT)
    c = cfg()
    ignorar = {str(x).lower() for x in c.get("ignorar") or []}
    exts = {str(x).lower() for x in c.get("extensoes") or [".png", ".jpg", ".jpeg", ".webp"]}
    minimo = int(c.get("tamanho_minimo_px", 300))
    marcas_ia = [_norm(x).strip() for x in c.get("ia") or []]
    antigo = ler().get("imagens") or {}
    novo, novas, t0 = {}, 0, time.time()
    pilha = [raiz]
    while pilha:
        pasta = pilha.pop()
        try:
            itens = sorted(pasta.iterdir())
        except OSError:
            continue
        for f in itens:
            if f.name.startswith("."):
                continue
            if f.is_dir():
                if f.name.lower() not in ignorar and not f.is_symlink():
                    pilha.append(f)
                continue
            if f.suffix.lower() not in exts:
                continue
            rel = str(f.relative_to(raiz))
            try:
                mt = int(f.stat().st_mtime)
            except OSError:
                continue
            velho = antigo.get(rel)
            if velho and velho.get("mt") == mt:
                novo[rel] = velho
                continue
            if time.time() - t0 > limite_s:               # pasta muito grande: o resto entra na próxima abertura
                continue
            m = _medir(f)
            if not m or min(m["w"], m["h"]) < minimo:
                continue
            cam = _norm(rel)
            novo[rel] = {**m, "mt": mt, "cat": _categoria(cam), "ia": any(x and x in cam for x in marcas_ia)}
            novas += 1
    dados = {"imagens": novo, "em": time.strftime("%Y-%m-%d %H:%M")}
    try:
        INDICE.parent.mkdir(parents=True, exist_ok=True)
        tmp = INDICE.with_suffix(".tmp")
        tmp.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        tmp.replace(INDICE)
    except OSError:
        pass
    return {"total": len(novo), "novas": novas, "ia": sum(1 for x in novo.values() if x.get("ia")), "em": dados["em"]}


def buscar(texto: str = "", categoria: str | None = None, n: int = 24, so_ia: bool = False) -> list:
    """Imagens que casam com as palavras, as maiores primeiro. Sem texto: as mais recentes."""
    palavras = [p for p in _norm(texto).split() if len(p) > 2 and p not in ("uma", "foto", "imagem", "com", "para", "dos", "das")]
    out = []
    for rel, x in (ler().get("imagens") or {}).items():
        if categoria and x.get("cat") != categoria:
            continue
        if so_ia and not x.get("ia"):
            continue
        cam = _norm(rel)
        pontos = sum(1 for p in palavras if p in cam)
        if palavras and not pontos:
            continue
        out.append((pontos, min(x["w"], x["h"]) if palavras else x.get("mt", 0), rel, x))
    out.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [{"arquivo": rel, **x} for _, _, rel, x in out[:n]]


def _guardar_antigo(arq: Path) -> None:
    destino = ROOT / "_arquivo" / "assets" / arq.parent.name
    destino.mkdir(parents=True, exist_ok=True)
    shutil.move(str(arq), str(destino / f"{time.strftime('%Y%m%d-%H%M%S')}_{arq.name}"))


def abastecer() -> list:
    """Leva para a Biblioteca o que o acervo tem de melhor. Devolve a lista do que entrou (para o registro)."""
    from PIL import Image

    from . import biblioteca
    c = cfg().get("abastecer") or {}
    imagens = ler().get("imagens") or {}
    fator = float(c.get("melhor_se_maior", 1.3))
    preferidas = [_norm(x).strip() for x in c.get("pastas_preferidas") or []]
    feitos = []
    pasta_marca = biblioteca.pasta("marca")
    for item, grupos in (c.get("marca") or {}).items():
        cands = []
        for rel, x in imagens.items():
            if rel.startswith("assets/marca/") or rel.startswith("_arquivo/"):
                continue
            cam = _norm(rel)
            if not any(all(_norm(p).strip() in cam for p in grupo) for grupo in grupos):
                continue
            pasta_rel = _norm(str(Path(rel).parent))
            na_preferida = any(p and p in pasta_rel for p in preferidas)
            if "divine" not in cam and not na_preferida and "/" in rel:
                continue                                   # logo de outra marca não entra (na raiz, é da Divine)
            bonus = 1 if na_preferida else 0
            cands.append((bonus, min(x["w"], x["h"]), rel))
        if not cands:
            continue
        cands.sort(reverse=True)
        _, lado, rel = cands[0]
        atual = biblioteca.logo(item)
        lado_atual = 0
        if atual:
            try:
                with Image.open(atual) as im:
                    lado_atual = min(im.size)
            except Exception:
                lado_atual = 0
        if atual and lado < lado_atual * fator:
            continue
        origem = ROOT / rel
        if atual:
            _guardar_antigo(atual)
        shutil.copy2(origem, pasta_marca / f"{item}{origem.suffix.lower()}")
        feitos.append(f"{item}: {rel} ({lado} px)")
    if c.get("fundos", True):                              # fundos de IA novos entram no banco do Liquid Glass
        destino = ROOT / "assets" / "fundos"
        destino.mkdir(parents=True, exist_ok=True)
        tem = {f.stem.lower() for f in destino.iterdir() if f.is_file()}
        for rel, x in imagens.items():
            if rel.startswith("assets/fundos/") or rel.startswith("_arquivo/") or x.get("cat") != "fundos" or not x.get("ia"):
                continue
            if x["h"] < x["w"] * 1.5 or min(x["w"], x["h"]) < 1000:
                continue                                   # só vertical (Stories) e em boa resolução
            nome = "_".join(_norm(Path(rel).stem).split())[:50]
            if nome in tem:
                continue
            shutil.copy2(ROOT / rel, destino / f"{nome}{Path(rel).suffix.lower()}")
            tem.add(nome)
            feitos.append(f"fundo: {rel}")
    return feitos


def fundos() -> dict:
    """{"escura": [nomes], "clara": [nomes]}: tudo o que está em assets/fundos (verticais), pelo brilho da imagem."""
    pasta = ROOT / "assets" / "fundos"
    out = {"escura": [], "clara": []}
    if not pasta.exists():
        return out
    idx = ler().get("imagens") or {}
    for f in sorted(pasta.iterdir()):
        if not f.is_file() or f.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp") or f.name.startswith("."):
            continue
        x = idx.get(f"assets/fundos/{f.name}") or _medir(f)
        if not x or x["w"] > x["h"]:                       # horizontal é da TV
            continue
        out["clara" if x.get("claro") else "escura"].append(f.stem)
    return out


def saude() -> dict:
    """Resumo para a Saúde do app: quantas imagens, quantas de IA e se as logos estão em alta."""
    from PIL import Image

    from . import biblioteca
    idx = ler()
    imagens = idx.get("imagens") or {}
    minimo = int((cfg().get("abastecer") or {}).get("minimo_marca_px", 800))
    baixas = []
    for item in ((cfg().get("abastecer") or {}).get("marca") or {}):
        f = biblioteca.logo(item)
        if not f:
            continue
        try:
            with Image.open(f) as im:
                if max(im.size) < minimo:               # logo horizontal é larga: vale o lado maior
                    baixas.append(f"{item} ({max(im.size)} px)")
        except Exception:
            pass
    return {"total": len(imagens), "ia": sum(1 for x in imagens.values() if x.get("ia")), "em": idx.get("em", ""),
            "logos_baixas": baixas, "por_categoria": {k: sum(1 for x in imagens.values() if x.get("cat") == k)
                                                      for k in sorted({x.get("cat") for x in imagens.values()})}}


def atualizar() -> dict:
    """Varre e abastece (chamado quando o painel abre). Nunca derruba o app."""
    try:
        r = varrer()
        r["entraram"] = abastecer()
        if r["entraram"]:
            varrer()
        return r
    except Exception as e:                                 # acervo é ajuda: erro aqui não pode travar o painel
        return {"erro": str(e)}
