"""Caixa de entrada: vídeos que chegam do celular (pasta ou Google Drive) viram propostas virais sozinhos.

Para cada vídeo novo (parado há `estavel_s`): projeto novo, cópia em bruto/, edição automática, um formato viral
por versão (Laboratório), referências do Radar no mesmo formato e a proposta em trabalho/proposta_viral.md.
O storyboard é gerado pelo painel logo depois (automação 'video_novo'). Nada é apagado nem movido da origem.
Índice do que já foi processado: projetos/.entrada.json.

  python3 -m divine_studio entrada            # varre as pastas uma vez
"""
from __future__ import annotations

import glob
import json
import shutil
import time
from pathlib import Path

from .config import ROOT, hoje, load, slug

VIDEO = {".mov", ".mp4", ".m4v", ".mkv", ".webm"}
INDICE = ROOT / "projetos" / ".entrada.json"


def _cfg() -> dict:
    return load("entrada")


def pastas() -> list:
    out = []
    for p in _cfg().get("pastas") or []:
        p = str(p)
        base = Path(p).expanduser()
        if not base.is_absolute():
            base = ROOT / base
        achadas = [Path(x) for x in glob.glob(str(base))] if any(c in str(base) for c in "*?[") else [base]
        out += [x for x in achadas if x.is_dir()]
    return out


def garantir_pasta_local() -> Path:
    p = ROOT / "entrada"
    p.mkdir(exist_ok=True)
    return p


def _indice() -> dict:
    try:
        return json.loads(INDICE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _gravar_indice(d: dict) -> None:
    INDICE.parent.mkdir(parents=True, exist_ok=True)
    INDICE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def _chave(arq: Path) -> str:
    st = arq.stat()
    return f"{arq.name}|{st.st_size}"


def pendentes() -> list:
    """Vídeos novos e já estáveis (o Drive terminou de baixar), em ordem de chegada."""
    idx = _indice()
    agora = time.time()
    est = float(_cfg().get("estavel_s", 60))
    out = []
    for pasta in pastas():
        for f in sorted(pasta.iterdir(), key=lambda x: x.stat().st_mtime):
            if f.suffix.lower() not in VIDEO or f.name.startswith(".") or not f.is_file():
                continue
            if _chave(f) in idx:
                continue
            if agora - f.stat().st_mtime < est:
                continue
            out.append(f)
    return out


def processar(arq: Path, conta: str | None = None) -> str:
    """Cria o projeto do vídeo e a proposta viral. Devolve o nome do projeto (relativo a projetos/)."""
    from .cli import main
    titulo = _titulo(arq)
    base, k = slug(titulo), 2
    while (ROOT / "projetos" / f"{hoje()}_{base}").exists():
        base, k = f"{slug(titulo)}-{k}", k + 1
    main(["novo", base])
    pasta = ROOT / "projetos" / f"{hoje()}_{base}"
    shutil.copy2(arq, pasta / "bruto" / arq.name)
    _ajustar_modelo(pasta, titulo, conta or _cfg().get("conta"))
    main(["auto", str(pasta)])
    proposta(pasta)
    idx = _indice()
    idx[_chave(arq)] = {"projeto": str(pasta.relative_to(ROOT / "projetos")), "origem": str(arq), "em": hoje()}
    _gravar_indice(idx)
    return str(pasta.relative_to(ROOT / "projetos"))


def _titulo(arq: Path) -> str:
    t = arq.stem.replace("_", " ").replace("-", " ").strip()
    if t.upper().startswith(("IMG", "VID", "MOV", "PXL")) or len(t) < 3:
        return f"Entrada {arq.stem}"
    return t


def _ajustar_modelo(pasta: Path, titulo: str, conta: str | None) -> None:
    """Tira o exemplo do modelo (clipe IMG_0001, mensagens de exemplo) antes da edição automática."""
    import yaml
    arq = pasta / "projeto.yaml"
    d = yaml.safe_load(arq.read_text(encoding="utf-8")) or {}
    d["titulo"] = titulo
    d["clipes"] = []
    d["template"] = _cfg().get("template", "divine")
    if conta:
        d["conta"] = conta
    d["origem"] = "caixa de entrada"
    arq.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")


def proposta(pasta: Path) -> dict:
    """Formas diferentes de viralizar o mesmo vídeo: uma por versão, com motivo, gancho, estilo e referências."""
    import yaml

    from . import lab, radar
    from .ingest import probe
    d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
    brutos = [f for f in (pasta / "bruto").iterdir() if f.suffix.lower() in VIDEO]
    dur = sum(probe(f)["duracao"] for f in brutos) if brutos else 0
    placar = {x["formato"]: x for x in lab.placar(d.get("conta"))}
    itens = []
    for v in d.get("versoes") or []:
        fmt = v.get("formato_viral")
        f = lab.formatos().get(fmt or "", {})
        refs = radar.em_alta(formato=fmt)[:2] if fmt else []
        hook = v.get("hook")
        if not hook or hook == "auto":                     # sorteado do banco na edição: mostra o modelo do formato
            hook = "modelo do formato: " + _preencher((f.get("ganchos") or [""])[0], d.get("titulo", ""))
        itens.append({"versao": v.get("nome"), "formato": fmt, "nome": f.get("nome", fmt), "ata": f.get("ata"),
                      "motivo": lab._motivo(placar[fmt]) if fmt in placar else "",
                      "estrutura": f.get("estrutura") or [], "estilo_edicao": v.get("estilo_edicao"),
                      "gancho": hook if isinstance(hook, str) else " / ".join(b.get("titulo", "") for b in hook or []),
                      "referencias": [{"link": r.get("link"), "conta": r.get("conta"), "outlier": r.get("outlier")}
                                      for r in refs]})
    dicas = []
    if dur > 75:
        dicas.append(f"O vídeo tem {dur:.0f} s: além das 3 versões, gere os cortes (✂ Cortes do vídeo longo) e teste "
                     "o melhor trecho como Reels curto.")
    if dur and dur < 7:
        dicas.append("Vídeo muito curto: use como b-roll ou junte com outro take.")
    if not d.get("legendas"):
        dicas.append("Sem transcrição da fala: instale o faster-whisper para corte limpo e legenda palavra a palavra.")
    out = {"duracao": round(dur, 1), "versoes": itens, "dicas": dicas}
    (pasta / "trabalho").mkdir(exist_ok=True)
    (pasta / "trabalho" / "proposta_viral.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    md = [f"# Proposta viral · {d.get('titulo')}", "", f"Vídeo de {dur:.0f} s. Cada versão testa um formato diferente; "
          "o Laboratório mede qual vence e aprende para os próximos.", ""]
    for it in itens:
        md += [f"## {it['versao']}: {it['nome']} ({it['ata']})", "", f"- Por quê: {it['motivo']}",
               f"- Gancho: {it['gancho'] or '(sorteado do banco)'}", f"- Estilo de edição: {it['estilo_edicao'] or 'divine'}",
               "- Estrutura: " + " → ".join(it["estrutura"])]
        md += [f"- Referência viral: {r['link']} (@{r['conta']}, {r['outlier']}x)" for r in it["referencias"]]
        md.append("")
    if dicas:
        md += ["## Dicas", ""] + [f"- {x}" for x in dicas]
    (pasta / "trabalho" / "proposta_viral.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return out


def _preencher(t: str, tema: str) -> str:
    try:
        return t.format(tema=tema, dor=tema, acao=f"cuidar de {tema}", obvio="falta de cuidado", objetivo="saúde",
                        pergunta=f"{tema} é para mim", mito="é tudo igual", etapa="a avaliação")
    except (KeyError, IndexError):
        return t


def ler_proposta(pasta: Path) -> dict:
    try:
        return json.loads((pasta / "trabalho" / "proposta_viral.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def varrer(conta: str | None = None) -> list:
    """Processa tudo o que está pendente. Devolve os projetos criados."""
    garantir_pasta_local()
    criados = []
    for arq in pendentes():
        try:
            criados.append(processar(arq, conta))
            print(f"✓ {arq.name} → projetos/{criados[-1]}")
        except (SystemExit, Exception) as e:      # um vídeo com problema não trava os outros
            print(f"  aviso: {arq.name} não processado ({e})")
            idx = _indice()
            idx[_chave(arq)] = {"erro": str(e)[:200], "origem": str(arq), "em": hoje()}
            _gravar_indice(idx)
    return criados
