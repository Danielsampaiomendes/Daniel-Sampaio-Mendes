"""Painel local do Divine Studio (interface web, só na sua máquina).

  python3 -m divine_studio painel            -> abre http://127.0.0.1:8765

Arrastar os brutos, escolher o template, revisar o corte, gerar as prévias, comparar as versões lado a lado e
aprovar. Usa só a biblioteca padrão do Python (nada para instalar) e chama os mesmos comandos da linha de comando.
"""
from __future__ import annotations

import json
import mimetypes
import os
import secrets
import socket
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
LOCAIS = {"127.0.0.1", "::1", "::ffff:127.0.0.1"}


# ---------------------------------------------------------------- acesso pelo celular

def codigo_celular() -> str:
    """Código de 6 dígitos para o iPhone entrar (fica guardado: o ícone na Tela de Início continua valendo)."""
    arq = PROJETOS / ".codigo_celular"
    if arq.exists() and re.fullmatch(r"\d{6}", arq.read_text().strip()):
        return arq.read_text().strip()
    cod = f"{secrets.randbelow(10 ** 6):06d}"
    PROJETOS.mkdir(exist_ok=True)
    arq.write_text(cod)
    arq.chmod(0o600)
    return cod


def ip_da_rede() -> str:
    """IP do Mac na rede Wi-Fi (nada é enviado: só consulta a rota)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


PAGINA_ENTRAR = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Divine Studio</title>
<link rel="apple-touch-icon" href="/icone-180.png"><link rel="stylesheet" href="/estilo.css"></head>
<body><form method="post" action="/entrar" class="entrar">
<img src="/logo.jpg" alt="Divine Studio"><h1>Divine Studio</h1>
<p>Digite o código que aparece no Terminal do Mac.</p>
<input name="codigo" inputmode="numeric" autocomplete="one-time-code" maxlength="6" placeholder="000000" autofocus>
<button class="dourado" type="submit">Entrar</button>{erro}</form></body></html>"""


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
        saidas = [x for x in (pasta / "saida").glob("*.mp4") if not x.name.startswith(".")] if (pasta / "saida").exists() else []
        out.append({"nome": nome, "titulo": d.get("titulo", nome), "template": d.get("template", "divine"),
                    "brutos": len([f for f in (pasta / "bruto").glob("*") if f.suffix.lower() in VIDEO])
                    if (pasta / "bruto").exists() else 0,
                    "previas": len([s for s in saidas if "_PREVIA" in s.name]),
                    "finais": len([s for s in saidas if "_PREVIA" not in s.name]),
                    "aprovado": (pasta / "trabalho" / "aprovacao.json").exists(),
                    "pacote": "-pacote/" in nome or "-formatos/" in nome,
                    "tags": [str(t) for t in d.get("tags") or []],
                    "tipo": d.get("tipo") if d.get("tipo") in ("carrossel", "post", "antes_depois") else "video"})
    # mais recente primeiro; as peças de um pacote e os outros formatos logo abaixo do projeto de origem
    raiz = lambda nome: re.split(r"-(?:pacote|formatos)/", nome)[0]   # noqa: E731
    out.sort(key=lambda x: (raiz(x["nome"]), 0 if not x["pacote"] else 1, x["nome"]))
    grupos = {}
    for x in out:
        grupos.setdefault(raiz(x["nome"]), []).append(x)
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
    brutos = sorted(f.name for f in (pasta / "bruto").glob("*") if f.suffix.lower() in VIDEO and not f.name.startswith(".")) \
        if (pasta / "bruto").exists() else []
    saidas = []
    for f in sorted(x for x in (pasta / "saida").glob("*.mp4") if not x.name.startswith(".")) \
            if (pasta / "saida").exists() else []:
        m = re.search(r"_(V\d+|TV|IA)_", f.name + "_")
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
            "fotos": sorted(f.name for f in (pasta / "bruto").glob("*") if f.suffix.lower() in
                            {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"} and not f.name.startswith("."))
            if (pasta / "bruto").exists() else [],
            "cards": d.get("cards") or [], "estilo": d.get("estilo", "divine"), "fontes": d.get("fontes"),
            "formula": d.get("formula", "lista"),
            "zip": next((f"saida/{z.name}" for z in sorted((pasta / "saida").glob("*.zip"))), None)
            if (pasta / "saida").exists() else None,
            "relatorio": _ler_md(pasta / "relatorio.md"), "cortes": _ler_md(pasta / "trabalho" / "cortes.md"),
            "legenda": _ler_md(pasta / "saida" / "legenda.txt") or d.get("legenda", ""),
            "aprovacao": json.loads(_ler_md(pasta / "trabalho" / "aprovacao.json") or "{}"),
            "templates": list(TEMPLATES), "job": _job_do_projeto(nome),
            "tags": [str(t) for t in d.get("tags") or []], "formatos": d.get("formatos") or ["stories", "tv"],
            "objetivo": d.get("objetivo", ""), "tipo": d.get("tipo", "video"),
            "subtitulo": d.get("subtitulo", ""), "pares": d.get("pares") or [], "cta": d.get("cta", ""),
            "video": d.get("video", True), "camera_elegante": d.get("camera_elegante"), "qualidade": d.get("qualidade"),
            "qualidade_info": _qualidade_info() if d.get("qualidade") else "",
            "imagens": sorted(f"saida/{x.name}" for x in (pasta / "saida").glob("*") if x.suffix.lower() in (".png", ".mp4")
                              and not x.name.startswith(".")) if (pasta / "saida").exists() else [],
            "pedidos_imagem": _pedidos(d),
            "publicacoes": d.get("publicacoes") or []}


def _qualidade_info() -> str:
    from .qualidade import diagnostico
    q = diagnostico()
    return ("estabilização vid.stab" if q["vidstab"] else "estabilização simples (deshake)") + " · " + \
        ("upscale com IA (Real-ESRGAN)" if q["realesrgan"] else "upscale Lanczos (instale o Real-ESRGAN para IA)")


def _pedidos(d: dict) -> list:
    """Imagens que o app pede para este projeto (Biblioteca): logo, fotos oficiais, foto da tecnologia do tema."""
    if d.get("tipo") == "antes_depois" or d.get("template") == "pessoal" or d.get("estilo") == "pessoal":
        return []
    from .biblioteca import pedidos
    try:
        return pedidos(d.get("titulo", ""), d.get("tipo", "video"))
    except Exception:
        return []


# ---------------------------------------------------------------- editor por campos (sem YAML)

CAMPOS_EDITAVEIS = {"titulo", "template", "formato", "autorizacao_imagem", "selo", "cta_antecipado", "mensagens",
                    "fechamento", "versoes", "efeitos", "legendas", "corte_limpo", "posicao_texto", "legenda", "tv",
                    "tags", "formatos", "objetivo", "cards", "estilo", "fontes", "formula", "sons",
                    "sfx_automaticos", "audio", "pares", "subtitulo", "cta", "video", "camera_elegante",
                    "qualidade"}


def dados_projeto(nome: str) -> dict:
    """Projeto como dicionário + o que o editor precisa: prévia de referência e duração da base."""
    pasta = _pasta(nome)
    d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
    previas = sorted((x for x in (pasta / "saida").glob("*.mp4") if not x.name.startswith(".")), key=lambda f: f.stat().st_mtime, reverse=True) \
        if (pasta / "saida").exists() else []
    base = pasta / "trabalho" / "base.json"
    dur = json.loads(base.read_text(encoding="utf-8")).get("duracao") if base.exists() else None
    from .config import load
    return {"projeto": d, "referencia": f"saida/{previas[0].name}" if previas else None, "duracao_base": dur,
            "fechamento_s": float(load("preferencias")["fechamento"]["duracao_s"]),
            "intervalo_efeitos": float(load("efeitos").get("intervalo_minimo_s", 1.5))}


def salvar_dados(nome: str, novos: dict) -> None:
    """Atualiza só os campos enviados; o resto do projeto.yaml fica como estava."""
    pasta = _pasta(nome)
    d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
    for k, v in novos.items():
        if k not in CAMPOS_EDITAVEIS:
            raise ValueError(f"campo não editável: {k}")
        if v in (None, "", []) and k in ("efeitos", "legenda", "selo", "camera_elegante", "qualidade"):
            d.pop(k, None)      # vazio = sem efeito/selo; a legenda vazia volta a ser gerada sozinha
        else:
            d[k] = v
    if "efeitos" in novos:
        from .efeitos import QUADRO, TIPOS
        for ef in d.get("efeitos") or []:
            if ef.get("tipo") not in TIPOS and ef.get("tipo") not in QUADRO:
                raise ValueError(f"efeito desconhecido: {ef.get('tipo')}")
            ef["inicio"] = round(float(ef.get("inicio", 0)), 2)
    texto = yaml.safe_dump(d, allow_unicode=True, sort_keys=False, width=1000, default_flow_style=None)
    salvar_yaml(nome, "# Editado pelo painel do Divine Studio.\n" + texto)


_CACHE_IMG: dict = {}


def png(img) -> bytes:
    import io
    b = io.BytesIO()
    img.save(b, "PNG", optimize=True)
    return b.getvalue()


def amostra_fonte(codigo: str, texto: str) -> bytes:
    """Miniatura de uma combinação de fontes (título com destaque dourado + apoio), no fundo da marca."""
    chave = ("fonte", codigo, texto)
    if chave not in _CACHE_IMG:
        from PIL import Image
        from .config import cor
        from .fonts import combinacao
        from .text import Estilo, render
        combo = combinacao(codigo)
        it = render(texto, Estilo.de_config(combo["titulo"], 54, cor("off_white")),
                    Estilo.de_config(combo["destaque"], 54, cor("dourado")), largura_max=440)
        ia = render(combo.get("nome", ""), Estilo.de_config(combo["apoio"], 34, cor("dourado")), largura_max=440)
        bloco = Image.new("RGBA", (max(it.width, ia.width), it.height + ia.height - 10), (0, 0, 0, 0))
        bloco.alpha_composite(it, ((bloco.width - it.width) // 2, 0))
        bloco.alpha_composite(ia, ((bloco.width - ia.width) // 2, it.height - 10))
        esc = min(1.0, 460 / bloco.width, 214 / bloco.height)     # frase longa: reduz para caber inteira
        if esc < 1:
            bloco = bloco.resize((max(1, int(bloco.width * esc)), max(1, int(bloco.height * esc))), Image.LANCZOS)
        img = Image.new("RGB", (480, 230), cor("fundo"))
        img.paste(bloco, ((480 - bloco.width) // 2, (230 - bloco.height) // 2), bloco)
        _CACHE_IMG[chave] = png(img)
    return _CACHE_IMG[chave]


def amostra_efeito(tipo: str) -> bytes:
    chave = ("efeito", tipo)
    if chave not in _CACHE_IMG:
        from .efeitos import amostra
        _CACHE_IMG[chave] = png(amostra(tipo))
    return _CACHE_IMG[chave]


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
    "previa": ["editar", "--rapido"], "final": ["editar"], "pacote": ["pacote"], "auto": ["auto", "--previa"],
    "formatos": ["formatos"], "formatos_final": ["formatos", "--final"], "carrossel": ["carrossel", "exportar"],
    "post": ["post", "exportar"], "antesdepois": ["antesdepois", "exportar"],
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
        if acao in ("carrossel", "post", "antesdepois"):
            cmd = [sys.executable, "-u", "-m", "divine_studio", *ACOES[acao], str(pasta)]
        else:
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
    codigo = None            # com código: aceita o celular na rede; sem: só a própria máquina

    def _autorizado(self) -> bool:
        if self.client_address[0] in LOCAIS:
            return True
        if not self.codigo:
            return False
        cookie = self.headers.get("Cookie") or ""
        m = re.search(r"(?:^|;\s*)divine=(\d{6})", cookie)
        return bool(m) and secrets.compare_digest(m.group(1), self.codigo)

    def _barrar(self, caminho: str) -> bool:
        """Pede o código ao celular; arquivos do visual (ícone, estilo) passam para a tela de entrada."""
        if self._autorizado() or caminho in ("/estilo.css", "/logo.jpg", "/icone-180.png", "/icone-64.png",
                                             "/manifest.json"):
            return False
        if caminho.startswith("/api") or caminho == "/arquivo":
            self._erro("digite o código do Mac", 401)
        else:
            self._html(PAGINA_ENTRAR.format(erro=""))
        return True

    def _html(self, texto: str, codigo: int = 200):
        corpo = texto.encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

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

    def _bytes(self, corpo: bytes, tipo: str):
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "max-age=3600")
        self.end_headers()
        self.wfile.write(corpo)

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
        if self._barrar(u.path):
            return
        try:
            if u.path in ("/", "/index.html"):
                return self._arquivo(WEB / "index.html")
            if u.path in ("/app.js", "/editor.js", "/carrossel.js", "/telas.js", "/ia.js", "/biblioteca.js", "/estilo.css", "/logo.jpg", "/icone-64.png", "/icone-180.png",
                          "/manifest.json"):
                return self._arquivo(WEB / u.path.lstrip("/"))
            if u.path == "/api/projetos":
                return self._json(listar())
            if u.path == "/api/projeto":
                return self._json(detalhe(q["p"]))
            if u.path == "/api/job":
                return self._json(estado(q["id"]))
            if u.path == "/api/dados":
                return self._json(dados_projeto(q["p"]))
            if u.path == "/api/fontes":
                from .config import load
                f = load("fontes")["combinacoes"]
                return self._json([{"codigo": k, "nome": v.get("nome", k)} for k, v in f.items()])
            if u.path == "/api/efeitos":
                from .efeitos import catalogo
                return self._json(catalogo())
            if u.path == "/fonte.png":
                return self._bytes(amostra_fonte(q["c"], q.get("t", "Sua frase / em *destaque.*")[:80]), "image/png")
            if u.path == "/carrossel.jpg":
                from .carrossel import png as png_card
                pasta = _pasta(q["p"])
                d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
                if q.get("fmt"):
                    d["formato"] = q["fmt"]
                return self._bytes(png_card(d, int(q["i"]), pasta, int(q.get("w", 540))), "image/jpeg")
            if u.path == "/antesdepois.jpg":
                from .antes_depois import previa
                pasta = _pasta(q["p"])
                d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
                return self._bytes(previa(pasta, d, q.get("fmt", "tv"), int(q.get("w", 960))), "image/jpeg")
            if u.path == "/api/biblioteca":
                from .biblioteca import listar as listar_bib
                return self._json(listar_bib())
            if u.path == "/biblioteca.img":
                from .biblioteca import miniatura
                corpo = miniatura(q["cat"], unquote(q["f"]), int(q.get("w", 320)))
                return self._bytes(corpo, "image/png" if corpo[:4] == b"\x89PNG" else "image/jpeg")
            if u.path == "/api/carrossel/config":
                from .config import load
                c = load("carrossel")
                return self._json({"estilos": {k: v["nome"] for k, v in c["estilos"].items()},
                                   "formulas": {k: v["nome"] for k, v in c["formulas"].items()}})
            if u.path == "/efeito.png":
                return self._bytes(amostra_efeito(q["tipo"]), "image/png")
            if u.path == "/api/ia/estado":
                from . import assistente, instagram
                ok, motivo = assistente.disponivel()
                return self._json({"ok": ok, "motivo": motivo, "instagram": instagram.configurado()})
            if u.path == "/api/ia/conversa":
                from . import assistente
                pasta = _pasta(q["p"]) if q.get("p") else None
                return self._json(assistente.mensagens_para_tela(assistente.carregar_conversa(pasta, q.get("c"))))
            if u.path == "/api/referencias":
                from . import referencias
                return self._json(referencias.listar())
            if u.path == "/referencia":
                from . import referencias
                pasta = referencias.pasta_de(q["r"])
                f = (pasta / Path(unquote(q["f"])).name)
                if not f.is_file():
                    raise ValueError("arquivo não encontrado")
                return self._arquivo(f)
            if u.path == "/api/sons":
                from .config import load
                cfg = load("sfx")
                pasta_sfx = ROOT / cfg["pasta"]
                nomes = sorted(f.stem for f in pasta_sfx.glob("*.wav")) if pasta_sfx.exists() else []
                fam = cfg.get("familias") or {}
                return self._json([{"nome": n, "familia": re.sub(r"_(?:[a-c])(?:_duplo)?$", "", n),
                                    "uso": fam.get(re.sub(r"_(?:[a-c])(?:_duplo)?$", "", n), "")} for n in nomes])
            if u.path == "/sfx.wav":
                from .config import load
                nome = q.get("nome", "")
                if not re.fullmatch(r"[a-z0-9_]+", nome):
                    raise ValueError("som inválido")
                f = ROOT / load("sfx")["pasta"] / f"{nome}.wav"
                if not f.is_file():
                    raise ValueError("som não encontrado (gere o kit: Biblioteca_SFX/gerar_kit_sfx.py)")
                return self._arquivo(f)
            if u.path == "/api/programacao":
                from . import aprendizado
                return self._json({"pecas": aprendizado.todas_publicacoes(), "aprendi": aprendizado.resumo()})
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
        if u.path == "/entrar":
            dado = parse_qs(self._corpo().decode("utf-8", "ignore")).get("codigo", [""])[0].strip()
            if self.codigo and secrets.compare_digest(dado.encode(), self.codigo.encode()):
                self.send_response(303)
                self.send_header("Set-Cookie", f"divine={self.codigo}; Max-Age=31536000; Path=/; HttpOnly; SameSite=Strict")
                self.send_header("Location", "/")
                self.end_headers()
                return
            time.sleep(1.0)            # freia tentativa e erro
            return self._html(PAGINA_ENTRAR.format(erro='<p class="erro">Código errado.</p>'), 401)
        if self._barrar(u.path):
            return
        try:
            if u.path == "/api/dublagem":
                pasta = _pasta(q["p"])
                if _job_do_projeto(q["p"]):
                    return self._erro("espere a tarefa deste projeto terminar")
                ext = re.sub(r"[^a-z0-9]", "", q.get("ext", "webm").lower())[:5] or "webm"
                dest = pasta / "trabalho" / "dublagem"
                dest.mkdir(parents=True, exist_ok=True)
                carimbo = time.strftime("%Y%m%d-%H%M%S")
                bruto = dest / f"gravacao_{carimbo}.{ext}"
                n = int(self.headers.get("Content-Length") or 0)
                bruto.write_bytes(self.rfile.read(n))
                wav = dest / f"voz_{carimbo}.wav"
                r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(bruto), "-ac", "2", "-ar", "48000",
                                    str(wav)], capture_output=True, text=True)
                if r.returncode != 0 or not wav.exists():
                    return self._erro("não consegui ler a gravação: " + r.stderr[-300:])
                d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
                aud = dict(d.get("audio") or {})
                dubs = list(aud.get("dublagem") or [])
                dubs.append({"arquivo": f"trabalho/dublagem/{wav.name}", "inicio": round(float(q.get("inicio", 0)), 2)})
                aud["dublagem"] = dubs
                if q.get("substituir") == "1":
                    aud["original"] = False          # a gravação substitui o som do vídeo
                aud.setdefault("trilha", True)
                salvar_dados(q["p"], {"audio": aud})
                return self._json({"ok": True, "arquivo": f"trabalho/dublagem/{wav.name}"})
            if u.path == "/api/upload":
                if q.get("ref"):
                    from . import referencias
                    pasta_ref = referencias.pasta_de(q["ref"])
                    nome = Path(unquote(q["nome"])).name
                    n = int(self.headers.get("Content-Length") or 0)
                    parcial = pasta_ref / f".{nome}.parcial"
                    with open(parcial, "wb") as fh:
                        while n > 0:
                            bloco = self.rfile.read(min(1 << 20, n))
                            if not bloco:
                                break
                            fh.write(bloco)
                            n -= len(bloco)
                    if n != 0:
                        parcial.unlink(missing_ok=True)
                        return self._erro("o envio foi interrompido; mande de novo")
                    os.replace(parcial, pasta_ref / nome)
                    return self._json({"ok": True})
                pasta = _pasta(q["p"])
                nome = Path(unquote(q["nome"])).name
                from .carrossel import IMAGEM
                if Path(nome).suffix.lower() not in VIDEO | IMAGEM:
                    return self._erro("só vídeos (.mov, .mp4…) ou fotos (.jpg, .png, .heic)")
                if _job_do_projeto(q["p"]):
                    return self._erro("espere a tarefa deste projeto terminar para enviar vídeos")
                destino = pasta / "bruto" / nome
                destino.parent.mkdir(exist_ok=True)
                parcial = destino.with_name(f".{nome}.parcial")
                n = int(self.headers.get("Content-Length") or 0)
                try:
                    with open(parcial, "wb") as fh:
                        while n > 0:
                            bloco = self.rfile.read(min(1 << 20, n))
                            if not bloco:
                                break
                            fh.write(bloco)
                            n -= len(bloco)
                except (ConnectionError, OSError):
                    n = -1
                if n != 0:
                    parcial.unlink(missing_ok=True)      # envio interrompido: não fica bruto cortado
                    return self._erro("o envio foi interrompido; mande o vídeo de novo")
                os.replace(parcial, destino)
                return self._json({"ok": True, "arquivo": f"bruto/{nome}"})
            if u.path == "/api/biblioteca/upload":
                from .biblioteca import salvar as salvar_bib
                n = int(self.headers.get("Content-Length") or 0)
                f = salvar_bib(q["cat"], unquote(q["nome"]), self.rfile, n, q.get("item") or None)
                return self._json({"ok": True, "arquivo": f.name})
            dados = json.loads(self._corpo() or b"{}")
            if u.path == "/api/post/novo":
                from .post import novo as novo_post
                return self._json({"nome": str(novo_post(dados["titulo"]).relative_to(PROJETOS))})
            if u.path == "/api/antesdepois/novo":
                from .antes_depois import novo as novo_ad
                return self._json({"nome": str(novo_ad(dados["titulo"], dados.get("subtitulo", "")).relative_to(PROJETOS))})
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
            if u.path == "/api/dados":
                salvar_dados(dados["p"], dados["dados"])
                return self._json({"ok": True})
            if u.path == "/api/carrossel/novo":
                from .carrossel import novo as novo_carrossel
                pasta = novo_carrossel(dados["titulo"], dados.get("formula", "lista"), dados.get("objetivo") or None,
                                       dados.get("estilo", "divine"))
                return self._json({"nome": str(pasta.relative_to(PROJETOS))})
            if u.path == "/api/carrossel/rascunho":
                from .carrossel import rascunho, salvar as salvar_carrossel
                pasta = _pasta(dados["p"])
                d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
                d["formula"] = dados.get("formula", d.get("formula", "lista"))
                d["cards"] = rascunho(d.get("titulo", ""), d["formula"], d.get("objetivo"),
                                      semente=int(time.time()) % 1000)
                salvar_carrossel(pasta, d)
                return self._json({"ok": True})
            if u.path == "/api/ia/mensagem":
                from . import assistente
                pasta = _pasta(dados["p"]) if dados.get("p") else None
                return self._json(assistente.conversar(pasta, dados["mensagem"], dados.get("c"),
                                                       bool(dados.get("olhar_video"))))
            if u.path == "/api/ia/aplicar":
                from . import assistente
                return self._json({"mudou": assistente.aplicar_sugestao(_pasta(dados["p"]), dados["sugestao"])})
            if u.path == "/api/ia/criar_projeto":
                from . import assistente
                sug = dados["sugestao"]
                ideia = sug.get("ideia_projeto") or {}
                nome = novo(ideia.get("titulo") or "ideia da IA")
                pasta = _pasta(nome)
                if ideia.get("template"):
                    salvar_yaml(nome, trocar_campo((pasta / "projeto.yaml").read_text(encoding="utf-8"), "template",
                                                   ideia["template"]))
                assistente.aplicar_sugestao(pasta, {k: v for k, v in sug.items() if k != "ideia_projeto"})
                return self._json({"nome": nome})
            if u.path == "/api/ia/nova_conversa":
                from . import assistente
                pasta = _pasta(dados["p"]) if dados.get("p") else None
                arq = assistente._arquivo_conversa(pasta, dados.get("c"))
                if arq.exists():       # não apaga: guarda a conversa antiga em _arquivo/
                    destino = ROOT / "_arquivo" / "conversas_ia"
                    destino.mkdir(parents=True, exist_ok=True)
                    os.replace(arq, destino / f"{int(time.time())}_{arq.parent.parent.name}_{arq.name}")
                return self._json({"ok": True})
            if u.path == "/api/ia/desempenho":
                from . import aprendizado, assistente
                pecas = [{k: p.get(k) for k in ("titulo", "versao", "formato", "status", "gostei", "metricas",
                                                 "caracteristicas", "data_postagem")}
                         for p in aprendizado.todas_publicacoes() if p.get("status") == "postado"]
                msg = ("Analise o desempenho dos posts abaixo (dados do Instagram e o que eu gostei). Diga o que mais "
                       "funcionou, o que menos funcionou e 3 ajustes concretos para os próximos vídeos (hook, ritmo, "
                       "fontes, efeitos, duração, objetivo). Seja específico.\n\n"
                       + json.dumps(pecas, ensure_ascii=False)[:20000])
                return self._json(assistente.conversar(None, msg, "desempenho"))
            if u.path == "/api/instagram/sincronizar":
                from . import instagram
                return self._json(instagram.sincronizar())
            if u.path == "/api/referencias/nova":
                from . import referencias
                p = referencias.nova(dados.get("titulo", ""), dados.get("link", ""), dados.get("nota", ""))
                return self._json({"nome": p.name})
            if u.path == "/api/referencias/analisar":
                from . import referencias
                return self._json(referencias.analisar(dados["nome"]))
            if u.path == "/api/referencias/incorporar":
                from . import referencias
                return self._json(referencias.incorporar(dados["nome"]))
            if u.path == "/api/publicacao":
                from . import aprendizado
                campos = {k: v for k, v in (dados.get("campos") or {}).items()
                          if k in ("status", "gostei", "nao_gostei", "data_agendada", "data_postagem", "rede", "link",
                                   "metricas", "obs")}
                if campos.get("status") and campos["status"] not in aprendizado.STATUS:
                    raise ValueError("status inválido")
                pasta_pub = _pasta(dados["p"])
                if campos.get("status") in ("postado", "agendado") and \
                        (aprendizado.ler(pasta_pub).get("tipo") == "antes_depois" or aprendizado.ler(pasta_pub).get("uso_interno")):
                    raise ValueError("Antes e depois é uso interno (consulta): não pode ser postado nem agendado (CFM 2.336/2023).")
                pub = aprendizado.marcar(pasta_pub, dados["versao"], dados.get("arquivo"), **campos)
                return self._json(pub)
            if u.path == "/api/abrir_pasta":
                if self.client_address[0] not in LOCAIS:
                    raise ValueError("só no próprio Mac")
                alvo = (ROOT / dados["caminho"]).resolve()
                if ROOT.resolve() not in alvo.parents and alvo != ROOT.resolve():
                    raise ValueError("caminho fora do projeto")
                subprocess.run(["open", "-R", str(alvo)] if alvo.is_file() else ["open", str(alvo)], check=False)
                return self._json({"ok": True})
            if u.path == "/api/regra":
                from .cli import main
                main(["regra", dados["texto"]])
                return self._json({"ok": True})
            return self._erro("não encontrado", 404)
        except yaml.YAMLError as e:
            return self._erro(f"YAML com erro: {e}")
        except (ValueError, KeyError, SystemExit) as e:
            return self._erro(str(e))


def rodar(porta: int = 8765, abrir: bool = True, celular: bool = False) -> None:
    PROJETOS.mkdir(exist_ok=True)
    Painel.codigo = codigo_celular() if celular else None
    srv = ThreadingHTTPServer(("0.0.0.0" if celular else "127.0.0.1", porta), Painel)
    url = f"http://127.0.0.1:{porta}"
    print(f"Painel do Divine Studio em {url}  (Ctrl+C para fechar)")
    if celular:
        print(f"\n  iPhone (mesma rede Wi-Fi): abra no Safari  http://{ip_da_rede()}:{porta}")
        print(f"  Código de acesso: {Painel.codigo}")
        print("  Depois: Compartilhar > Adicionar à Tela de Início. O Mac precisa ficar ligado com esta janela aberta.\n")
    if abrir:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nPainel fechado.")
    finally:
        srv.server_close()
