"""Higgsfield AI como extensão do Divine Studio.

O app monta os PEDIDOS: efeito viral, modelo ou ferramenta do Higgsfield, mais o quadro ou o clipe do projeto, mais o
prompt no padrão Divine (config/higgsfield.yaml). Quem executa é o Claude com o conector do Higgsfield. Ele lê a fila
(projetos/.higgsfield_fila.json), mostra o custo em créditos, pede o seu ok, gera e devolve o resultado:
  python3 -m divine_studio higgsfield pronto <id> <arquivo ou link do Higgsfield>
O resultado entra em bruto/ do projeto e pode ir para a linha do tempo com um toque. Passo a passo para o Claude:
docs/HIGGSFIELD_PONTE.md.
"""
from __future__ import annotations

import datetime as _dt
import json
import shutil
import threading
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import yaml

from .config import ROOT, load, slug

FILA = ROOT / "projetos" / ".higgsfield_fila.json"
VIDEO = {".mp4", ".mov", ".m4v", ".webm"}
IMAGEM = {".jpg", ".jpeg", ".png", ".webp"}
STATUS = ("pendente", "gerando", "pronto", "erro", "cancelado")
_TRAVA = threading.Lock()


def _cfg() -> dict:
    return load("higgsfield")


def catalogo() -> dict:
    c = _cfg()
    return {"efeitos": c.get("efeitos") or [], "modelos": c.get("modelos") or [], "ferramentas": c.get("ferramentas") or []}


def _item(tipo: str, alvo: str) -> dict:
    lista = catalogo().get({"efeito": "efeitos", "modelo": "modelos", "ferramenta": "ferramentas"}.get(tipo, ""), [])
    it = next((x for x in lista if x["id"] == alvo), None)
    if not it:
        raise ValueError(f"{tipo} '{alvo}' não está no catálogo do Higgsfield")
    return it


def ler() -> list:
    try:
        return json.loads(FILA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _gravar(itens: list) -> None:
    FILA.parent.mkdir(parents=True, exist_ok=True)
    FILA.write_text(json.dumps(itens, ensure_ascii=False, indent=1), encoding="utf-8")


def _pasta(projeto: str) -> Path:
    p = (ROOT / "projetos" / projeto).resolve()
    if (ROOT / "projetos").resolve() not in p.parents or not (p / "projeto.yaml").exists():
        raise ValueError("projeto não encontrado")
    return p


def prompt_divine(texto: str) -> str:
    regras = str(_cfg().get("regras_prompt", "")).strip()
    return (texto.strip() + "\n\n" + regras).strip() if texto.strip() else regras


def criar(projeto: str, tipo: str, alvo: str, arquivo: str = "", t: float | None = None, prompt: str = "",
          params: dict | None = None) -> dict:
    """Novo pedido na fila. Efeito viral pede FOTO: se vier um vídeo, o app tira o quadro no segundo t."""
    pasta = _pasta(projeto)
    it = _item(tipo, alvo)
    entrada = {}
    if arquivo:
        f = (pasta / arquivo).resolve()
        if pasta not in f.parents or not f.exists():
            raise ValueError("arquivo do projeto não encontrado")
        if tipo == "efeito" and f.suffix.lower() in VIDEO:
            from .integracoes import quadro
            destino = pasta / "bruto" / f"quadro_{slug(it['nome'], 20)}_{int((t or 1) * 10):04d}.jpg"
            quadro(f, float(t if t is not None else 1.0), destino)
            f = destino
        entrada = {"arquivo": str(f.relative_to(pasta)), "tipo": "foto" if f.suffix.lower() in IMAGEM else "video"}
    elif tipo != "modelo":
        raise ValueError("escolha a foto ou o clipe do projeto que vai para o Higgsfield")
    pedido = {"id": uuid.uuid4().hex[:8], "projeto": projeto, "tipo": tipo, "alvo": alvo, "nome": it["nome"],
              "entrada": entrada, "prompt": prompt_divine(prompt), "params": {"aspect_ratio": _cfg().get("formato_padrao", "9:16"),
                                                                             **(params or {})},
              "status": "pendente", "criado_em": _dt.datetime.now().isoformat(timespec="minutes")}
    with _TRAVA:
        itens = ler()
        itens.append(pedido)
        _gravar(itens)
    return pedido


def pedido(id_: str) -> dict:
    p = next((x for x in ler() if x["id"] == id_), None)
    if not p:
        raise ValueError("pedido do Higgsfield não encontrado")
    return p


def atualizar(id_: str, **campos) -> dict:
    with _TRAVA:
        itens = ler()
        for x in itens:
            if x["id"] == id_:
                if campos.get("status") and campos["status"] not in STATUS:
                    raise ValueError("status inválido")
                x.update(campos)
                x["atualizado_em"] = _dt.datetime.now().isoformat(timespec="minutes")
                _gravar(itens)
                return x
    raise ValueError("pedido do Higgsfield não encontrado")


def listar(status: str | None = None, projeto: str | None = None) -> list:
    return [x for x in reversed(ler()) if (not status or x["status"] == status) and (not projeto or x["projeto"] == projeto)]


def _host_ok(url: str) -> bool:
    u = urllib.parse.urlparse(url)
    return u.scheme == "https" and (u.hostname or "").endswith(("higgsfield.ai", "cloudfront.net", "amazonaws.com"))


def receber(id_: str, origem: str, job_id: str = "", creditos: float | None = None) -> dict:
    """Resultado do Higgsfield: um arquivo já baixado no Mac ou o link do Higgsfield (o app baixa).
    Vai para bruto/ do projeto e o pedido fica 'pronto'."""
    p = pedido(id_)
    pasta = _pasta(p["projeto"])
    origem = origem.strip()
    ext = Path(urllib.parse.urlparse(origem).path).suffix.lower() or ".mp4"
    if ext not in VIDEO | IMAGEM:
        ext = ".mp4"
    destino = pasta / "bruto" / f"higgsfield_{slug(p['nome'], 24)}_{p['id']}{ext}"
    destino.parent.mkdir(exist_ok=True)
    if origem.startswith("http"):
        if not _host_ok(origem):
            raise ValueError("só aceito links do Higgsfield (https://...higgsfield.ai)")
        req = urllib.request.Request(origem, headers={"User-Agent": "DivineStudio/1.0"})
        with urllib.request.urlopen(req, timeout=300) as r, open(destino, "wb") as f:
            shutil.copyfileobj(r, f)
    else:
        src = Path(origem).expanduser()
        if not src.exists():
            raise ValueError("arquivo do resultado não encontrado")
        shutil.copy2(src, destino)
    extra = {k: v for k, v in {"job_id": job_id, "creditos": creditos}.items() if v not in ("", None)}
    return atualizar(id_, status="pronto", resultado={"arquivo": str(destino.relative_to(pasta)), "origem": origem, **extra})


def usar(id_: str, onde: str = "fim") -> dict:
    """Põe o vídeo gerado na edição: como clipe no começo (abertura de impacto) ou no fim."""
    p = pedido(id_)
    if p["status"] != "pronto" or not (p.get("resultado") or {}).get("arquivo"):
        raise ValueError("o pedido ainda não tem resultado")
    arq = p["resultado"]["arquivo"]
    if Path(arq).suffix.lower() not in VIDEO:
        raise ValueError("o resultado é uma imagem: use na Biblioteca ou como foto (insert_foto)")
    pasta = _pasta(p["projeto"])
    d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
    clipes = [c for c in d.get("clipes") or [] if isinstance(c, dict) and c.get("arquivo") != "bruto/IMG_0001.MOV"]
    novo = {"arquivo": arq, "foco": [0.5, 0.4], "origem": "higgsfield", "transicao": "dissolver"}
    if any(c.get("arquivo") == arq for c in clipes):
        return {"ja_estava": True}
    clipes = [novo] + clipes if onde == "comeco" else clipes + [novo]
    d["clipes"] = clipes
    (pasta / "trabalho").mkdir(exist_ok=True)
    (pasta / "trabalho" / "projeto.yaml.antes-do-higgsfield").write_text(
        (pasta / "projeto.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    (pasta / "projeto.yaml").write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False, width=1000),
                                        encoding="utf-8")
    atualizar(id_, usado_em=onde)
    return {"ok": True, "clipes": len(clipes)}


def creditos_semana() -> float:
    """Créditos gastos nos pedidos desta semana (segunda a domingo)."""
    hoje = _dt.date.today()
    seg = (hoje - _dt.timedelta(days=hoje.weekday())).isoformat()
    return round(sum(float((x.get("resultado") or {}).get("creditos") or 0) for x in ler()
                     if str(x.get("atualizado_em") or x.get("criado_em", ""))[:10] >= seg), 1)


def orcamento() -> dict:
    o = _cfg().get("orcamento") or {}
    semana = float(o.get("por_semana", 250))
    usado = creditos_semana()
    return {"por_video": float(o.get("por_video", 60)), "por_semana": semana, "usado_semana": usado,
            "resta_semana": round(max(0.0, semana - usado), 1)}


def instrucao_claude(ids: list | None = None) -> str:
    """Texto para colar no Claude (desktop, com o conector do Higgsfield e a pasta do Divine Studio liberada)."""
    pend = [x for x in listar("pendente") if not ids or x["id"] in ids]
    linhas = [f"- {x['id']}: {x['nome']} ({x['tipo']}) · projeto {x['projeto']} · entrada {x['entrada'].get('arquivo', '(só texto)')}"
              for x in pend]
    return (
        "Processe os pedidos do Higgsfield do Divine Studio, seguindo docs/HIGGSFIELD_PONTE.md.\n"
        f"Fila: projetos/.higgsfield_fila.json ({len(pend)} pendente(s)):\n" + "\n".join(linhas or ["- (nenhum)"]) +
        f"\nTeto: até {orcamento()['por_video']:.0f} créditos por vídeo e {orcamento()['resta_semana']:.0f} restantes nesta semana. "
        "Antes de gerar, me mostre o custo em créditos de cada um e espere o meu ok. Quando ficar pronto, rode "
        "`python3 -m divine_studio higgsfield pronto <id> <arquivo ou link>` para o resultado entrar no projeto.")
