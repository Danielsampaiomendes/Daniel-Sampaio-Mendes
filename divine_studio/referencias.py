"""Referências de outros criadores: você envia o vídeo, o print ou o link com uma nota; a IA faz o raio-X
(skill divine-raio-x-referencia), propõe hooks e efeitos, e o que for bom entra no banco de hooks e na lista de
ideias para virar funcionalidade do app (docs/IDEIAS_DO_APP.md).

Cada referência fica em referencias/AAAA-MM-DD_<nome>/ com meta.yaml, os arquivos e analise.md.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

import yaml

from .config import ROOT, slug

PASTA = ROOT / "referencias"
IDEIAS = ROOT / "docs" / "IDEIAS_DO_APP.md"
VIDEO = {".mp4", ".mov", ".m4v", ".webm"}
IMAGEM = {".jpg", ".jpeg", ".png", ".webp", ".heic"}


def nova(titulo: str, link: str = "", nota: str = "") -> Path:
    pasta = PASTA / f"{_dt.date.today().isoformat()}_{slug(titulo or link or 'referencia', 40)}"
    k = 2
    while pasta.exists():
        pasta = pasta.with_name(f"{pasta.name.rsplit('-v', 1)[0]}-v{k}")
        k += 1
    pasta.mkdir(parents=True)
    (pasta / "meta.yaml").write_text(yaml.safe_dump({"titulo": titulo, "link": link, "nota": nota,
                                                     "data": _dt.date.today().isoformat(), "status": "nova"},
                                                    allow_unicode=True, sort_keys=False), encoding="utf-8")
    return pasta


def listar() -> list:
    out = []
    for meta in sorted(PASTA.glob("*/meta.yaml"), reverse=True):
        d = yaml.safe_load(meta.read_text(encoding="utf-8")) or {}
        arquivos = [f.name for f in meta.parent.iterdir() if f.suffix.lower() in VIDEO | IMAGEM]
        analise = meta.parent / "analise.md"
        out.append({**d, "pasta": meta.parent.name, "arquivos": arquivos,
                    "analise": analise.read_text(encoding="utf-8") if analise.exists() else ""})
    return out


def pasta_de(nome: str) -> Path:
    p = (PASTA / nome).resolve()
    if PASTA.resolve() not in p.parents or not (p / "meta.yaml").exists():
        raise ValueError("referência não encontrada")
    return p


def analisar(nome: str) -> dict:
    """Raio-X com a IA: quadros do vídeo (ou as imagens), fala transcrita quando houver, link e nota."""
    from . import assistente
    pasta = pasta_de(nome)
    meta = yaml.safe_load((pasta / "meta.yaml").read_text(encoding="utf-8")) or {}
    imagens, fala = [], ""
    for f in sorted(pasta.iterdir()):
        if f.suffix.lower() in VIDEO:
            imagens += assistente.quadros_do_video(f, n=8)
            try:
                from .transcricao import motor_disponivel, transcrever
                if motor_disponivel():
                    fala = " ".join(w["texto"] for w in transcrever(f, pasta / "transcricoes"))
            except SystemExit:
                pass
        elif f.suffix.lower() in IMAGEM and f.suffix.lower() != ".heic":
            imagens.append((f.read_bytes(), "image/png" if f.suffix.lower() == ".png" else "image/jpeg"))
    pedido = (
        "Faça o raio-X desta referência seguindo a skill divine-raio-x-referencia: linha do tempo, classificação "
        "(fórmula IG, camadas do gancho, formato, objetivo), por que funcionou (até 4 motivos), alertas do que NÃO "
        "trazer para a Divine e o molde Divine com 3 ganchos (positivo, curiosidade, negativo). Depois, numa seção "
        "'Para o app', liste efeitos visuais ou funcionalidades de edição desta referência que o Divine Studio "
        "deveria ganhar (nome curto + como funcionaria no padrão suave Divine).\n\n"
        f"Título: {meta.get('titulo')}\nLink: {meta.get('link') or '-'}\nNota do Renato: {meta.get('nota') or '-'}\n"
        + (f"Fala transcrita: {fala[:4000]}\n" if fala else "")
        + ("(Sem vídeo ou imagem: analise pelo link e pela nota.)" if not imagens else
           f"(Junto vão {len(imagens)} quadros/imagens da referência.)")
        + "\n\nNo bloco de sugestão, use 'hooks' para os 3 ganchos (nome V1, V2, V3) e acrescente "
          "'efeitos_app': [{\"nome\": ..., \"como\": ...}] com as ideias para o app."
    )
    texto, sug, _ = assistente.perguntar([], pedido, "", imagens[:12])
    (pasta / "analise.md").write_text(f"# Raio-X · {meta.get('titulo')}\n\n{texto}\n", encoding="utf-8")
    meta["status"] = "analisada"
    if sug:
        meta["sugestao"] = sug
    (pasta / "meta.yaml").write_text(yaml.safe_dump(meta, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return {"analise": texto, "sugestao": sug}


def incorporar(nome: str) -> dict:
    """Leva os ganchos para o banco de hooks (bloco E) e as ideias de efeito para docs/IDEIAS_DO_APP.md."""
    from .hooks import adicionar
    pasta = pasta_de(nome)
    meta = yaml.safe_load((pasta / "meta.yaml").read_text(encoding="utf-8")) or {}
    sug = meta.get("sugestao") or {}
    novos = []
    for h in sug.get("hooks") or []:
        batidas = [b.get("titulo", "") for b in h.get("hook") or [] if b.get("titulo")]
        if batidas:
            texto = " → ".join(f"\"{b}\"" for b in batidas)
            novos.append(adicionar(f"{texto} (ref. {meta.get('titulo')})"))
    ideias = sug.get("efeitos_app") or []
    if ideias:
        if not IDEIAS.exists():
            IDEIAS.write_text("# Ideias para o Divine Studio\n\nVindas das referências analisadas. "
                              "Cada item vira funcionalidade quando o Renato aprovar.\n", encoding="utf-8")
        with open(IDEIAS, "a", encoding="utf-8") as f:
            f.write(f"\n## {_dt.date.today():%d/%m/%Y} · {meta.get('titulo')} (`referencias/{pasta.name}`)\n\n")
            for i in ideias:
                f.write(f"- **{i.get('nome', 'ideia')}**: {i.get('como', '')}\n")
    meta["status"] = "incorporada"
    meta["hooks_no_banco"] = novos
    (pasta / "meta.yaml").write_text(yaml.safe_dump(meta, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return {"hooks": novos, "ideias": len(ideias)}
