"""Painel local do Divine Studio (interface web, só na sua máquina).

  python3 -m divine_studio painel            -> abre http://127.0.0.1:8765

Arrastar os brutos, escolher o template, revisar o corte, gerar as prévias, comparar as versões lado a lado e
aprovar. Usa só a biblioteca padrão do Python (nada para instalar) e chama os mesmos comandos da linha de comando.
"""
from __future__ import annotations

import json
import mimetypes
import re
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import yaml

from .config import ROOT, hoje, slug

PROJETOS = ROOT / "projetos"
WEB = Path(__file__).parent / "web"
VIDEO = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}
JOBS: dict = {}
TRAVA = threading.Lock()


# ---------------------------------------------------------------- projetos

def _pasta(nome: str) -> Path:
    """Pasta de projeto pelo nome (inclusive peças de pacote 'x-pacote/03_reels-curto'), sem sair de projetos/."""
    p = (PROJETOS / unquote(nome)).resolve()
    if PROJETOS.resolve() not in p.parents or not (p / "projeto.yaml").exists():
        raise ValueError("projeto não encontrado")
    return p


def _arquivo_do_projeto(pasta: Path, rel: str) -> Path:
    f = (pasta / unquote(rel)).resolve()
    if pasta not in f.parents or not f.is_file():
        raise ValueError("arquivo não encontrado")
    return f


def listar() -> list:
    out = []
    for y in sorted(PROJETOS.glob("**/projeto.yaml")):
        pasta = y.parent
        if "trabalho" in pasta.parts:
            continue
        nome = str(pasta.relative_to(PROJETOS))
        try:
            d = yaml.safe_load(y.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            d = {}
        saidas = list((pasta / "saida").glob("*.mp4")) if (pasta / "saida").exists() else []
        out.append({"nome": nome, "titulo": d.get("titulo", nome), "template": d.get("template", "divine"),
                    "brutos": len([f for f in (pasta / "bruto").glob("*") if f.suffix.lower() in VIDEO])
                    if (pasta / "bruto").exists() else 0,
                    "previas": len([s for s in saidas if "_PREVIA" in s.name]),
                    "finais": len([s for s in saidas if "_PREVIA" not in s.name]),
                    "aprovado": (pasta / "trabalho" / "aprovacao.json").exists(),
                    "pacote": "-pacote" in nome})
    # mais recente primeiro; as peças de um pacote logo abaixo do projeto de origem
    out.sort(key=lambda x: x["nome"].split("-pacote")[0], reverse=True)
    out.sort(key=lambda x: (x["nome"].split("-pacote")[0], 0 if not x["pacote"] else 1, x["nome"]))
    grupos = {}
    for x in out:
        grupos.setdefault(x["nome"].split("-pacote")[0], []).append(x)
    return [x for k in sorted(grupos, reverse=True) for x in grupos[k]]


def _ler_md(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def detalhe(nome: str) -> dict:
    pasta = _pasta(nome)
    texto = (pasta / "projeto.yaml").read_text(encoding="utf-8")
    try:
        d = yaml.safe_load(texto) or {}
        erro_yaml = ""
    except yaml.YAMLError as e:
        d, erro_yaml = {}, str(e)
    brutos = sorted(f.name for f in (pasta / "bruto").glob("*") if f.suffix.lower() in VIDEO) \
        if (pasta / "bruto").exists() else []
    saidas = []
    for f in sorted((pasta / "saida").glob("*.mp4")) if (pasta / "saida").exists() else []:
        m = re.search(r"_(V\d+|TV)_", f.name + "_")
        saidas.append({"arquivo": f"saida/{f.name}", "nome": f.name, "versao": m.group(1) if m else "",
                       "previa": "_PREVIA" in f.name, "mb": round(f.stat().st_size / 1e6, 1),
                       "quando": f.stat().st_mtime})
    from .templates import TEMPLATES
    usados = {c.get("arquivo", "").split("/")[-1] for c in d.get("clipes") or []}
    return {"nome": nome, "yaml": texto, "erro_yaml": erro_yaml, "titulo": d.get("titulo", nome),
            "template": d.get("template", "divine"), "formato": d.get("formato", "reels"),
            "autorizacao_imagem": d.get("autorizacao_imagem", "pendente"),
            "versoes": [v.get("nome") for v in d.get("versoes") or []],
            "brutos": [{"nome": b, "no_projeto": b in usados} for b in brutos], "saidas": saidas,
            "relatorio": _ler_md(pasta / "relatorio.md"), "cortes": _ler_md(pasta / "trabalho" / "cortes.md"),
            "legenda": _ler_md(pasta / "saida" / "legenda.txt") or d.get("legenda", ""),
            "aprovacao": json.loads(_ler_md(pasta / "trabalho" / "aprovacao.json") or "{}"),
            "templates": list(TEMPLATES), "job": _job_do_projeto(nome)}


def salvar_yaml(nome: str, texto: str) -> None:
    pasta = _pasta(nome)
    yaml.safe_load(texto)                       # erro de sintaxe volta para a tela antes de gravar
    atual = pasta / "projeto.yaml"
    (pasta / "trabalho").mkdir(exist_ok=True)
    (pasta / "trabalho" / "projeto.yaml.anterior").write_text(atual.read_text(encoding="utf-8"), encoding="utf-8")
    atual.write_text(texto if texto.endswith("\n") else texto + "\n", encoding="utf-8")


def trocar_campo(texto: str, campo: str, valor: str) -> str:
    """Troca `campo: valor` na raiz do YAML preservando os comentários; acrescenta se não existir."""
    linha = f"{campo}: {valor}"
    padrao = re.compile(rf"^{campo}:[^\n#]*(#.*)?$", re.M)
    m = padrao.search(texto)
    if m:
        comentario = f"  {m.group(1)}" if m.group(1) else ""
        return texto[:m.start()] + linha + comentario + texto[m.end():]
    return linha + "\n" + texto


def adicionar_clipe(texto: str, arquivo: str) -> str:
    """Acrescenta `- {arquivo: bruto/X}` na lista de clipes (troca o exemplo do modelo, se ainda estiver lá)."""
    item = f"  - {{arquivo: {json.dumps(arquivo, ensure_ascii=False)}}}"
    if re.search(r"^clipes:\s*\[\]\s*$", texto, re.M):
        return re.sub(r"^clipes:\s*\[\]\s*$", "clipes:\n" + item, texto, count=1, flags=re.M)
    m = re.search(r"^clipes:\s*\n((?:[ \t]+.*\n|\s*\n)*)", texto, re.M)
    if not m:
        return texto.rstrip("\n") + "\n\nclipes:\n" + item + "\n"
    bloco = m.group(1)
    if "IMG_0001.MOV" in bloco:              # exemplo do modelo: substitui pelo primeiro clipe de verdade
        return texto[:m.start(1)] + item + "\n\n" + texto[m.end(1):]
    fim = m.start(1) + len(bloco.rstrip("\n")) + 1
    return texto[:fim] + item + "\n" + texto[fim:]


def novo(nome: str) -> str:
    from .cli import main
    main(["novo", nome])
    return f"{hoje()}_{slug(nome)}"


# ---------------------------------------------------------------- tarefas em segundo plano

ACOES = {
    "revisar": ["revisar"], "transcrever": ["transcrever"], "cortar": ["cortar"], "legenda": ["legenda"],
    "previa": ["editar", "--rapido"], "final": ["editar"], "pacote": ["pacote"],
}


def _job_do_projeto(nome: str):
    for j in JOBS.values():
        if j["projeto"] == nome and j["estado"] == "rodando":
            return j["id"]
    return None


def iniciar(nome: str, acao: str, versoes: list | None = None) -> str:
    pasta = _pasta(nome)
    if acao not in ACOES:
        raise ValueError("ação desconhecida")
    with TRAVA:
        if _job_do_projeto(nome):
            raise ValueError("já tem uma tarefa rodando neste projeto")
        jid = uuid.uuid4().hex[:10]
        cmd = [sys.executable, "-u", "-m", "divine_studio", *ACOES[acao][:1], str(pasta), *ACOES[acao][1:]]
        if versoes and acao in ("previa", "final"):
            cmd += ["--versoes", ",".join(versoes)]
        log = pasta / "trabalho" / f"painel_{acao}_{jid}.log"
        log.parent.mkdir(exist_ok=True)
        fh = open(log, "w", encoding="utf-8")
        proc = subprocess.Popen(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
        JOBS[jid] = {"id": jid, "projeto": nome, "acao": acao, "estado": "rodando", "log": str(log),
                     "inicio": time.time(), "proc": proc, "fh": fh, "versoes": versoes or []}
    return jid


def estado(jid: str) -> dict:
    j = JOBS.get(jid)
    if not j:
        raise ValueError("tarefa não encontrada")
    if j["estado"] == "rodando" and j["proc"].poll() is not None:
        j["fh"].close()
        j["estado"] = "ok" if j["proc"].returncode == 0 else "erro"
        if j["estado"] == "ok" and j["acao"] == "final":
            pasta = _pasta(j["projeto"])
            (pasta / "trabalho" / "aprovacao.json").write_text(json.dumps(
                {"aprovado_em": time.strftime("%d/%m/%Y %H:%M"), "versoes": j["versoes"] or "todas"},
                ensure_ascii=False), encoding="utf-8")
    texto = Path(j["log"]).read_text(encoding="utf-8", errors="replace") if Path(j["log"]).exists() else ""
    # linhas de progresso do render ("  5.0s / 12.7s") viram só a última
    linhas = [ln for ln in texto.splitlines() if not re.match(r"^\s+[\d.]+s / [\d.]+s$", ln)]
    prog = re.findall(r"^\s+([\d.]+)s / ([\d.]+)s$", texto, re.M)
    return {"id": jid, "acao": j["acao"], "estado": j["estado"], "log": "\n".join(linhas[-200:]),
            "progresso": [float(prog[-1][0]), float(prog[-1][1])] if prog else None,
            "segundos": round(time.time() - j["inicio"])}


# ---------------------------------------------------------------- HTTP

class Painel(BaseHTTPRequestHandler):
    server_version = "DivineStudio"

    def log_message(self, fmt, *args):     # silencioso no terminal
        pass

    def _json(self, dados, codigo=200):
        corpo = json.dumps(dados, ensure_ascii=False).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _erro(self, msg, codigo=400):
        self._json({"erro": msg}, codigo)

    def _corpo(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _arquivo(self, f: Path):
        """Serve arquivo com suporte a Range (o player de vídeo precisa para avançar e no Safari)."""
        tam = f.stat().st_size
        tipo = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        rng = self.headers.get("Range")
        ini, fim = 0, tam - 1
        if rng and rng.startswith("bytes="):
            a, _, b = rng[6:].partition("-")
            ini = int(a) if a else max(0, tam - int(b))
            fim = int(b) if a and b else tam - 1
            fim = min(fim, tam - 1)
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {ini}-{fim}/{tam}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(fim - ini + 1))
        self.end_headers()
        with open(f, "rb") as fh:
            fh.seek(ini)
            falta = fim - ini + 1
            while falta > 0:
                bloco = fh.read(min(1 << 20, falta))
                if not bloco:
                    break
                try:
                    self.wfile.write(bloco)
                except (BrokenPipeError, ConnectionResetError):
                    return
                falta -= len(bloco)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path in ("/", "/index.html"):
                return self._arquivo(WEB / "index.html")
            if u.path in ("/app.js", "/estilo.css"):
                return self._arquivo(WEB / u.path.lstrip("/"))
            if u.path == "/api/projetos":
                return self._json(listar())
            if u.path == "/api/projeto":
                return self._json(detalhe(q["p"]))
            if u.path == "/api/job":
                return self._json(estado(q["id"]))
            if u.path == "/api/hooks":
                from .hooks import sortear
                return self._json([{"id": h["id"], "tipo": h["tipo"], "batidas": h["batidas"]}
                                   for h in sortear(int(q.get("n", 3)), tema=q.get("tema"))])
            if u.path == "/arquivo":
                return self._arquivo(_arquivo_do_projeto(_pasta(q["p"]), q["f"]))
            return self._erro("não encontrado", 404)
        except (ValueError, KeyError) as e:
            return self._erro(str(e))

    def do_POST(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/api/upload":
                pasta = _pasta(q["p"])
                nome = Path(unquote(q["nome"])).name
                if Path(nome).suffix.lower() not in VIDEO:
                    return self._erro("só arquivos de vídeo (.mov, .mp4…)")
                destino = pasta / "bruto" / nome
                destino.parent.mkdir(exist_ok=True)
                n = int(self.headers.get("Content-Length") or 0)
                with open(destino, "wb") as fh:
                    while n > 0:
                        bloco = self.rfile.read(min(1 << 20, n))
                        if not bloco:
                            break
                        fh.write(bloco)
                        n -= len(bloco)
                return self._json({"ok": True, "arquivo": f"bruto/{nome}"})
            dados = json.loads(self._corpo() or b"{}")
            if u.path == "/api/novo":
                return self._json({"nome": novo(dados["nome"])})
            if u.path == "/api/salvar":
                salvar_yaml(dados["p"], dados["yaml"])
                return self._json({"ok": True})
            if u.path == "/api/campo":
                pasta = _pasta(dados["p"])
                texto = (pasta / "projeto.yaml").read_text(encoding="utf-8")
                salvar_yaml(dados["p"], trocar_campo(texto, dados["campo"], dados["valor"]))
                return self._json({"ok": True})
            if u.path == "/api/clipe":
                pasta = _pasta(dados["p"])
                texto = (pasta / "projeto.yaml").read_text(encoding="utf-8")
                salvar_yaml(dados["p"], adicionar_clipe(texto, f"bruto/{Path(dados['arquivo']).name}"))
                return self._json({"ok": True})
            if u.path == "/api/acao":
                return self._json({"job": iniciar(dados["p"], dados["acao"], dados.get("versoes"))})
            if u.path == "/api/regra":
                from .cli import main
                main(["regra", dados["texto"]])
                return self._json({"ok": True})
            return self._erro("não encontrado", 404)
        except yaml.YAMLError as e:
            return self._erro(f"YAML com erro: {e}")
        except (ValueError, KeyError, SystemExit) as e:
            return self._erro(str(e))


def rodar(porta: int = 8765, abrir: bool = True) -> None:
    PROJETOS.mkdir(exist_ok=True)
    srv = ThreadingHTTPServer(("127.0.0.1", porta), Painel)
    url = f"http://127.0.0.1:{porta}"
    print(f"Painel do Divine Studio em {url}  (Ctrl+C para fechar)")
    if abrir:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nPainel fechado.")
    finally:
        srv.server_close()
