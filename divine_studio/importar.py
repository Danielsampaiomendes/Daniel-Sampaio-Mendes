"""Importa para o Divine Studio tudo o que já foi feito na pasta "Divine Medical Spa Marketing" (brutos e editados).

  python3 -m divine_studio importar                      # procura a pasta sozinho
  python3 -m divine_studio importar "~/Documents/Claude/Projects/Divine Medical Spa Marketing" --simular
  python3 -m divine_studio importar <pasta> --copiar     # copia os arquivos (padrão: atalho, não ocupa espaço)

Cada pasta de tema (Videos/<tema>/, os pacotes soltos na raiz e as pastas de uso interno) vira um projeto em
projetos/, com:
  - bruto/: os vídeos brutos (IMG_..., pastas bruto/brutos/originais), prontos para reeditar
  - saida/: os vídeos editados (cada arquivo vira uma peça na aba Versões)
  - "Pronto para postar" entra como aprovado (vai para a Galeria e para a Programação)
  - legendas e copies (*.md, *.txt) copiados para a pasta do projeto
Nada é apagado nem movido na pasta de origem. Rodar de novo só acrescenta o que é novo.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shutil
from pathlib import Path

import yaml

from .config import ROOT, slug

VIDEO = {".mp4", ".mov", ".m4v"}
IMAGEM = {".png", ".jpg", ".jpeg", ".webp"}
TEXTO = {".md", ".txt"}
PULAR = re.compile(r"^(_versoes anteriores|_arquivo|trilhas|\.|__)", re.I)
PAPEL = re.compile(r"(pronto para postar|vers[aã]o pro|brutos?|raw|originais|capas?|legendas?|^\d+_|reels|stories|tv|feed|"
                   r"carross|flyers?|guia|template_codigo|pdf)", re.I)
BRUTO_PASTA = re.compile(r"(^|/)(brutos?|raw|originais|grava[cç][oõ]es)(/|$)", re.I)
BRUTO_NOME = re.compile(r"^(IMG_|VID_|MVI_|DJI_|PXL_|GX\d|GOPR|C\d{4})", re.I)
PACOTES_RAIZ = re.compile(r"(pacote|pov|repost|stories|pellets|uso interno|v[ií]deo explicativo)", re.I)
LOCAL_PADRAO = Path("~/Documents/Claude/Projects/Divine Medical Spa Marketing").expanduser()
INDICE = ROOT / "projetos" / ".importacao.json"


def achar_origem() -> Path | None:
    for p in (ROOT, LOCAL_PADRAO):
        if (p / "Videos").is_dir():
            return p
    return None


def _grupos(origem: Path) -> list:
    """[(titulo, pasta, subpastas_que_viraram_projeto_proprio)] de cada projeto a importar."""
    out = []
    videos = origem / "Videos"
    if videos.is_dir():
        for tema in sorted(p for p in videos.iterdir() if p.is_dir() and not PULAR.match(p.name)):
            subs = [s for s in sorted(tema.iterdir()) if s.is_dir() and not PULAR.match(s.name) and not PAPEL.search(s.name)
                    and any(f.suffix.lower() in VIDEO for f in s.rglob("*"))]
            for s in subs:                                          # "Laser CO2/Pacote 2026-10-20" vira projeto próprio
                out.append((f"{tema.name} · {s.name}", s, []))
            soltos = [f for f in tema.rglob("*") if f.suffix.lower() in VIDEO
                      and not any(s == f.parent or s in f.parents for s in subs)]
            if soltos or not subs:
                out.append((tema.name, tema, subs))
    for p in sorted(origem.iterdir()):
        if p.is_dir() and p.name not in ("Videos", "projetos", "assets", "divine_studio", "entregas") \
                and not PULAR.match(p.name) and PACOTES_RAIZ.search(p.name):
            out.append((p.name, p, []))
    return out


def _data(arquivos: list) -> str:
    datas = sorted(m.group(0) for f in arquivos for m in [re.search(r"20\d\d-\d\d-\d\d", f.name)] if m)
    if datas:
        return datas[0]
    if arquivos:
        return _dt.date.fromtimestamp(min(f.stat().st_mtime for f in arquivos)).isoformat()
    return _dt.date.today().isoformat()


def _versao(f: Path, usados: set) -> str:
    """Rótulo único da peça (aparece na aba Versões e na Galeria)."""
    base = re.sub(r"20\d\d-\d\d-\d\d_?", "", f.stem)
    base = re.sub(r"(?i)^(reels|stories|tv|feed\d*)_", "", base)
    rot = slug(base, 34) or "peca"
    k, final = 2, rot
    while final in usados:
        final, k = f"{rot}-{k}", k + 1
    usados.add(final)
    return final


def _ligar(src: Path, dst: Path, copiar: bool) -> None:
    if dst.exists() or dst.is_symlink():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if copiar:
        shutil.copy2(src, dst)
    else:
        os.symlink(src.resolve(), dst)


def importar(origem: Path | None = None, copiar: bool = False, simular: bool = False) -> dict:
    from . import aprendizado
    from .carrossel import salvar
    origem = Path(origem).expanduser() if origem else achar_origem()
    if not origem or not origem.is_dir():
        raise SystemExit("Não achei a pasta 'Divine Medical Spa Marketing'. Passe o caminho: "
                         "python3 -m divine_studio importar \"<pasta>\"")
    indice = json.loads(INDICE.read_text(encoding="utf-8")) if INDICE.exists() else {}
    relatorio = []
    for titulo, pasta_origem, excluir in _grupos(origem):
        arquivos = [f for f in pasta_origem.rglob("*") if f.is_file() and not f.name.startswith(".")
                    and not any(PULAR.match(x) for x in f.relative_to(pasta_origem).parts[:-1])
                    and not any(e in f.parents for e in excluir)]
        vids = [f for f in arquivos if f.suffix.lower() in VIDEO]
        if not vids:
            continue
        rel = lambda f: str(f.relative_to(pasta_origem))                         # noqa: E731
        brutos = [f for f in vids if BRUTO_PASTA.search(rel(f)) or BRUTO_NOME.match(f.name)]
        editados = [f for f in vids if f not in brutos]
        prontos = {f for f in editados if re.search(r"pronto para postar", rel(f), re.I)}
        interno = bool(re.search(r"uso interno", str(pasta_origem.relative_to(origem)), re.I))
        chave = str(pasta_origem.relative_to(origem))
        nome = indice.get(chave) or f"{_data(vids)}_import-{slug(titulo, 44)}"
        relatorio.append({"titulo": titulo, "projeto": nome, "brutos": len(brutos), "editados": len(editados),
                          "prontos": len(prontos), "uso_interno": interno, "origem": chave})
        if simular:
            continue
        pasta = ROOT / "projetos" / nome
        for sub in ("bruto", "saida", "trabalho"):
            (pasta / sub).mkdir(parents=True, exist_ok=True)
        mapa_arq = pasta / "trabalho" / "importados.json"
        mapa = json.loads(mapa_arq.read_text(encoding="utf-8")) if mapa_arq.exists() else {}
        usados = set(mapa.values())
        for f in brutos:
            _ligar(f, pasta / "bruto" / f.name, copiar)
        novos = []
        for f in sorted(editados):
            destino = pasta / "saida" / f.name
            if destino.name not in mapa:
                mapa[destino.name] = _versao(f, usados)
                novos.append((f, destino))
            _ligar(f, destino, copiar)
        for f in arquivos:
            if f.suffix.lower() in TEXTO:                          # legendas e copies: cópia (são pequenos)
                if not (pasta / f.name).exists():
                    shutil.copy2(f, pasta / f.name)
            elif f.suffix.lower() in IMAGEM:
                _ligar(f, pasta / "saida" / "imagens" / f.name, copiar)
        mapa_arq.write_text(json.dumps(mapa, indent=1, ensure_ascii=False), encoding="utf-8")
        yml = pasta / "projeto.yaml"
        if not yml.exists():
            tags = ["importado", slug(titulo.split(" · ")[0], 30).replace("-", " ")] + (["uso interno"] if interno else [])
            salvar(pasta, {"titulo": titulo, "data": _data(vids), "template": "tv" if all(
                re.search(r"(?i)(^|_)tv(_|$)|16x9", f.stem) for f in editados) and editados else "divine",
                "formato": "reels", "importado": True, "origem": chave, "uso_interno": interno or None,
                "autorizacao_imagem": "pendente", "tags": tags,
                "clipes": [{"arquivo": f"bruto/{f.name}"} for f in sorted(brutos)[:12]],
                "versoes": [{"nome": "V1", "hook": "auto"}, {"nome": "V2", "hook": "auto"}, {"nome": "V3", "hook": "auto"}]})
            d = yaml.safe_load(yml.read_text(encoding="utf-8"))
            salvar(pasta, {k: v for k, v in d.items() if v is not None})
        for f, destino in novos:
            aprendizado.marcar(pasta, mapa[destino.name], arquivo=f"saida/{destino.name}",
                               status="aprovado" if f in prontos else "rascunho",
                               rede="consulta" if interno else ("tv" if re.search(r"(?i)tv|16x9", f.stem) else "instagram"),
                               origem=rel(f))
        indice[chave] = nome
    if not simular:
        INDICE.parent.mkdir(parents=True, exist_ok=True)
        INDICE.write_text(json.dumps(indice, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"origem": str(origem), "modo": "simulação" if simular else ("cópia" if copiar else "atalhos"),
            "projetos": relatorio}
