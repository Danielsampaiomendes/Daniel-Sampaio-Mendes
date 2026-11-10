"""Painel local do Divine Studio (interface web, só na sua máquina).

  python3 -m divine_studio painel            -> abre http://127.0.0.1:8765

Arrastar os brutos, escolher o template, revisar o corte, gerar as prévias, comparar as versões lado a lado e
aprovar. Usa só a biblioteca padrão do Python (nada para instalar) e chama os mesmos comandos da linha de comando.
"""
from __future__ import annotations

import datetime as _dt
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

from .config import ROOT, hoje, load, slug

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


def nome_do_mac() -> str:
    """Nome do Mac na rede (Bonjour): http://<nome>.local:8765 vale mesmo quando o IP do Wi-Fi muda."""
    if sys.platform != "darwin":
        return ""
    try:
        r = subprocess.run(["scutil", "--get", "LocalHostName"], capture_output=True, text=True, timeout=5)
        return r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def ip_tailscale() -> str:
    """IP do Tailscale (acesso fora de casa, se o Renato instalar o app gratuito no Mac e no iPhone)."""
    import shutil as _sh
    exe = _sh.which("tailscale") or ("/Applications/Tailscale.app/Contents/MacOS/Tailscale"
                                     if Path("/Applications/Tailscale.app").exists() else None)
    if not exe:
        return ""
    try:
        r = subprocess.run([exe, "ip", "-4"], capture_output=True, text=True, timeout=5)
        return r.stdout.split()[0] if r.returncode == 0 and r.stdout.strip() else ""
    except (OSError, subprocess.SubprocessError, IndexError):
        return ""


def enderecos(porta: int) -> list:
    """Endereços para abrir no iPhone, do melhor para o pior."""
    out = []
    nome = nome_do_mac()
    if nome:
        out.append({"url": f"http://{nome}.local:{porta}", "onde": "no Wi-Fi de casa ou da clínica (não muda nunca)"})
    out.append({"url": f"http://{ip_da_rede()}:{porta}", "onde": "no mesmo Wi-Fi (muda se o roteador trocar o IP)"})
    ts = ip_tailscale()
    if ts:
        out.append({"url": f"http://{ts}:{porta}", "onde": "fora de casa, pelo Tailscale (4G ou outro Wi-Fi)"})
    return out


def qr_svg(texto: str) -> bytes:
    """QR code para o iPhone ler com a câmera (biblioteca segno; sem ela, o painel mostra só o endereço)."""
    import io
    import segno
    buf = io.BytesIO()
    segno.make(texto, error="m").save(buf, kind="svg", scale=6, border=2, dark="#12110F", light="#F5F4F1")
    return buf.getvalue()


def manter_acordado() -> None:
    """Mac acordado enquanto o painel está aberto: o iPhone alcança o Mac e as automações continuam rodando.
    A tela pode apagar; só o descanso automático do Mac fica suspenso (caffeinate termina junto com o painel)."""
    if sys.platform != "darwin":
        return
    try:
        subprocess.Popen(["caffeinate", "-i", "-s", "-w", str(os.getpid())], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except OSError:
        pass


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
    # sem resolver atalhos: peças importadas são atalhos para a pasta antiga (Divine Medical Spa Marketing)
    f = Path(os.path.normpath(pasta / unquote(rel)))
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
                    "pacote": "-pacote/" in nome or "-formatos/" in nome or "-cortes/" in nome,
                    "tags": [str(t) for t in d.get("tags") or []],
                    "tipo": d.get("tipo") if d.get("tipo") in ("carrossel", "post", "antes_depois") else "video",
                    "categoria": categoria(d), "epico": d.get("ritmo") == "epico" or bool(d.get("epico")),
                    "importado": bool(d.get("importado")), "conta": _conta(d)})
    # mais recente primeiro; as peças de um pacote e os outros formatos logo abaixo do projeto de origem
    raiz = lambda nome: re.split(r"-(?:pacote|formatos|cortes)/", nome)[0]   # noqa: E731
    out.sort(key=lambda x: (raiz(x["nome"]), 0 if not x["pacote"] else 1, x["nome"]))
    grupos = {}
    for x in out:
        grupos.setdefault(raiz(x["nome"]), []).append(x)
    return [x for k in sorted(grupos, reverse=True) for x in grupos[k]]


def _conta(d: dict):
    from .instagram import conta_do_projeto
    return conta_do_projeto(d)


def _perfis() -> dict:
    from .instagram import perfis
    return {u: c.get("nome", u) for u, c in perfis().items()}


def categoria(d: dict) -> str:
    """Tipo de edição para o menu e o filtro: video | stories | carrossel | post | tv | antes_depois."""
    if d.get("tipo") in ("carrossel", "post", "antes_depois"):
        return d["tipo"]
    if d.get("template") == "tv" or d.get("formato") == "tv":
        return "tv"
    return "stories" if d.get("formato") == "stories" else "video"


# Menu "Nova edição": cada tipo cria o projeto já no jeito certo
TIPOS_EDICAO = {
    "video": {"dados": {"formato": "reels"}},
    "epico": {"dados": {"formato": "reels", "ritmo": "epico", "tags": ["vídeo épico"]}},
    "stories": {"dados": {"formato": "stories", "tags": ["stories"]}},
    "longo": {"dados": {"formato": "reels", "tags": ["vídeo longo"]}},
    "tv": {"dados": {"template": "tv", "formato": "tv", "tags": ["tv"]}},
    "react": {"dados": {"template": "react", "formato": "reels", "layout": "auto", "legendas": "true",
                        "tags": ["tela dividida"]}},
}


def nova_edicao(tipo: str, titulo: str) -> str:
    titulo = (titulo or "").strip()
    if not titulo:
        raise ValueError("escreva o tema")
    if tipo == "carrossel":
        from .carrossel import novo as novo_carrossel
        return str(novo_carrossel(titulo).relative_to(PROJETOS))
    if tipo == "post":
        from .post import novo as novo_post
        return str(novo_post(titulo).relative_to(PROJETOS))
    if tipo == "antes_depois":
        from .antes_depois import novo as novo_ad
        return str(novo_ad(titulo).relative_to(PROJETOS))
    if tipo == "anuncio":
        return _novo_anuncio(titulo)
    if tipo not in TIPOS_EDICAO:
        raise ValueError("tipo de edição desconhecido")
    nome = novo(titulo)
    pasta = _pasta(nome)
    texto = (pasta / "projeto.yaml").read_text(encoding="utf-8")
    for campo, valor in TIPOS_EDICAO[tipo]["dados"].items():     # edição no texto: o modelo comentado continua igual
        texto = trocar_campo(texto, campo, json.dumps(valor, ensure_ascii=False) if isinstance(valor, list) else valor)
    salvar_yaml(nome, texto)
    return nome


def diagnostico() -> list:
    """Saúde do app: o que está instalado e o que falta (para a tela Nova edição)."""
    import importlib.util
    import shutil as _sh
    from . import assistente, instagram, qualidade
    from .biblioteca import listar as listar_bib
    from .transcricao import motor_disponivel
    ok_ia, motivo_ia = assistente.disponivel()
    q = qualidade.diagnostico()
    faltam_img = sum(c["faltam_obrigatorios"] for c in listar_bib())
    return [
        {"item": "FFmpeg", "ok": bool(_sh.which("ffmpeg")), "dica": "brew install ffmpeg"},
        {"item": "Logo oficial", "ok": bool(__import__("divine_studio.biblioteca", fromlist=["logo"]).logo("divine-simbolo")),
         "dica": "Biblioteca > Logomarcas"},
        {"item": "Imagens essenciais", "ok": faltam_img == 0, "dica": f"faltam {faltam_img} na Biblioteca"},
        {"item": "IA (Claude)", "ok": ok_ia, "dica": motivo_ia or ""},
        {"item": "Transcrição da fala", "ok": bool(motor_disponivel()), "dica": "pip3 install faster-whisper"},
        {"item": "Recorte da pessoa (parallax, vertigem)", "ok": importlib.util.find_spec("mediapipe") is not None,
         "dica": "pip3 install mediapipe"},
        {"item": "Estabilização vid.stab", "ok": q["vidstab"], "dica": "ffmpeg com libvidstab (brew install ffmpeg)"},
        {"item": "Upscale com IA (Real-ESRGAN)", "ok": q["realesrgan"], "dica": "realesrgan-ncnn-vulkan no PATH"},
        {"item": "Instagram conectado", "ok": instagram.configurado(), "dica": "Programação > Conectar Instagram"},
    ]


def duplicar(nome: str) -> str:
    """Cópia do projeto para testar outra ideia (mesmos brutos, sem as saídas)."""
    import shutil as _sh
    pasta = _pasta(nome)
    base = re.sub(r"-v\d+$", "", pasta.name)
    k = 2
    while (pasta.parent / f"{base}-v{k}").exists():
        k += 1
    nova = pasta.parent / f"{base}-v{k}"
    for sub in ("bruto", "trabalho", "saida"):
        (nova / sub).mkdir(parents=True)
    for f in (pasta / "bruto").iterdir() if (pasta / "bruto").exists() else []:
        alvo = nova / "bruto" / f.name
        if f.is_symlink():
            os.symlink(os.readlink(f), alvo)
        else:
            try:
                os.link(f, alvo)              # mesmo arquivo no disco: não ocupa espaço
            except OSError:
                _sh.copy2(f, alvo)
    d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
    d.pop("publicacoes", None)
    d["titulo"] = f"{d.get('titulo', nome)} (v{k})"
    texto = yaml.safe_dump(d, allow_unicode=True, sort_keys=False, width=1000, default_flow_style=None)
    (nova / "projeto.yaml").write_text("# Divine Studio (cópia)\n" + texto, encoding="utf-8")
    for f in pasta.glob("*.md"):
        _sh.copy2(f, nova / f.name)
    return str(nova.relative_to(PROJETOS))


def arquivar(nome: str) -> str:
    """Tira o projeto da lista sem apagar: vai para _arquivo/projetos/."""
    import shutil as _sh
    pasta = _pasta(nome)
    destino = ROOT / "_arquivo" / "projetos" / pasta.name
    k = 2
    while destino.exists():
        destino = destino.with_name(f"{pasta.name}-{k}")
        k += 1
    destino.parent.mkdir(parents=True, exist_ok=True)
    _sh.move(str(pasta), destino)
    return str(destino.relative_to(ROOT))


def excluir(nome: str) -> str:
    """Excluir de verdade (projeto sem sentido): vai para a Lixeira do Mac (recupera até esvaziar).
    Sem Lixeira (outro sistema), cai em _arquivo/projetos."""
    import shutil as _sh
    pasta = _pasta(nome)
    lixeira = Path.home() / ".Trash"
    if not lixeira.is_dir():
        return arquivar(nome)
    destino = lixeira / f"Divine Studio - {pasta.name}"
    k = 2
    while destino.exists():
        destino = lixeira / f"Divine Studio - {pasta.name} {k}"
        k += 1
    _sh.move(str(pasta), destino)
    return "Lixeira do Mac"


def videos() -> list:
    """Biblioteca de vídeos: todo vídeo gerado ou importado, de todos os projetos, com o estado de cada um."""
    out = []
    for y in sorted(PROJETOS.glob("**/projeto.yaml")):
        pasta = y.parent
        if "trabalho" in pasta.parts or not (pasta / "saida").exists():
            continue
        try:
            d = yaml.safe_load(y.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if d.get("uso_interno") or d.get("tipo") == "antes_depois":
            continue
        nome = str(pasta.relative_to(PROJETOS))
        mapa = json.loads(_ler_md(pasta / "trabalho" / "importados.json") or "{}")
        pubs = {p.get("arquivo"): p for p in d.get("publicacoes") or [] if p.get("arquivo")}
        pubs_v = {p.get("versao"): p for p in d.get("publicacoes") or []}
        for f in sorted((pasta / "saida").glob("*")):
            if f.suffix.lower() not in (".mp4", ".mov", ".m4v") or f.name.startswith(".") or not f.exists():
                continue
            m = re.search(r"_(V\d+|TV|IA)_", f.name + "_")
            versao = mapa.get(f.name) or (m.group(1) if m else f.stem[:24])
            rel = f"saida/{f.name}"
            pub = pubs.get(rel) or pubs_v.get(versao) or {}
            previa = "_PREVIA" in f.name
            out.append({"projeto": nome, "titulo": d.get("titulo", nome), "versao": versao, "arquivo": rel,
                        "na_tv": pub.get("na_tv"),
                        "previa": previa, "status": pub.get("status") or ("" if previa else "final"),
                        "validado": bool(pub.get("validado")), "gostei": bool(pub.get("gostei")),
                        "categoria": categoria(d), "tags": [str(t) for t in d.get("tags") or []],
                        "importado": bool(d.get("importado")), "quando": f.stat().st_mtime, "conta": _conta(d),
                        "mb": round(f.stat().st_size / 1e6, 1),
                        "views": (pub.get("metricas") or {}).get("views") or (pub.get("metricas") or {}).get("alcance")})
    return sorted(out, key=lambda x: -x["quando"])


def canal_tv() -> list:
    """Programação da TV da clínica: vídeos 16:9 finais (e os que você marcar 📺 Na TV), sem uso interno de consulta."""
    out = []
    for i in videos():
        if i.get("na_tv") is False:
            continue
        if i.get("na_tv") or (i["categoria"] == "tv" and not i["previa"]):
            out.append({"projeto": i["projeto"], "titulo": i["titulo"], "arquivo": i["arquivo"], "versao": i["versao"]})
    return sorted(out, key=lambda x: x["titulo"])


def galeria() -> list:
    """Peças validadas (★), aprovadas na final ou postadas, com arquivo existente. Uso interno não entra."""
    from . import aprendizado
    out = []
    for pub in aprendizado.todas_publicacoes():
        if pub.get("rede") == "consulta" or not pub.get("arquivo"):
            continue
        if not (pub.get("validado") or pub.get("status") in ("aprovado", "agendado", "postado")):
            continue
        pasta = PROJETOS / pub["projeto"]
        if not (pasta / pub["arquivo"]).is_file():
            continue
        try:
            d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            d = {}
        out.append({**{k: pub.get(k) for k in ("projeto", "titulo", "versao", "arquivo", "status", "gostei", "validado",
                                                  "tipo", "tags", "data_postagem", "data_agendada", "link")},
                    "categoria": categoria(d), "quando": (pasta / pub["arquivo"]).stat().st_mtime,
                    "video": pub["arquivo"].lower().endswith((".mp4", ".mov")),
                    "views": (pub.get("metricas") or {}).get("views") or (pub.get("metricas") or {}).get("alcance")})
    return sorted(out, key=lambda x: -x["quando"])


def capa_peca(pasta: Path, rel: str, largura: int = 420) -> bytes:
    """Capa da peça (quadro do vídeo em 1 s, 1º card do carrossel ou a própria imagem), com cache."""
    import hashlib
    import io
    f = _arquivo_do_projeto(pasta, rel)
    cache = pasta / "trabalho" / "miniaturas" / (hashlib.sha1(f"{rel}{f.stat().st_mtime}".encode()).hexdigest()[:16] + ".jpg")
    if cache.exists():
        return cache.read_bytes()
    cache.parent.mkdir(parents=True, exist_ok=True)
    from PIL import Image
    if f.suffix.lower() in (".mp4", ".mov", ".m4v"):
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", "1", "-i", str(f), "-frames:v", "1", "-vf",
                            f"scale={largura}:-2", "-f", "image2", "-c:v", "mjpeg", "-q:v", "4", "-"],
                           capture_output=True)
        if not r.stdout:
            r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(f), "-frames:v", "1", "-vf", f"scale={largura}:-2",
                                "-f", "image2", "-c:v", "mjpeg", "-q:v", "4", "-"], capture_output=True)
        dados = r.stdout
    elif f.suffix.lower() == ".zip":
        import zipfile
        with zipfile.ZipFile(f) as z:
            nomes = sorted(n for n in z.namelist() if n.lower().endswith(".png"))
            if not nomes:
                raise ValueError("zip sem imagens")
            im = Image.open(io.BytesIO(z.read(nomes[0])))
            im.thumbnail((largura, largura * 2))
            b = io.BytesIO()
            im.convert("RGB").save(b, "JPEG", quality=85)
            dados = b.getvalue()
    else:
        im = Image.open(f)
        im.thumbnail((largura, largura * 2))
        b = io.BytesIO()
        im.convert("RGB").save(b, "JPEG", quality=85)
        dados = b.getvalue()
    if not dados:
        raise ValueError("sem miniatura")
    cache.write_bytes(dados)
    return dados


def _anuncio_info(pasta: Path, d: dict) -> dict:
    from . import anuncios
    a = anuncios.dados_anuncio(d)
    vs = anuncios.copy(d)
    return {**a, "copy": vs, "erros": anuncios.revisar_copy(d, vs),
            "objetivos": {k: v["nome"] for k, v in (load("anuncios").get("objetivos") or {}).items()}}


def _novo_anuncio(titulo: str) -> str:
    """Anúncio: projeto já com o roteiro de conversão (gancho, problema, solução, prova, chamada) e a copy A/B."""
    from . import anuncios
    from .config import load as _load
    nome = novo(titulo)
    cfg = _load("anuncios")
    base = {"titulo": titulo, "anuncio": {"objetivo": "agendamento", "servico": titulo}}
    r = anuncios.roteiro(base)
    salvar_dados(nome, {"anuncio": base["anuncio"], "versoes": r["versoes"], "mensagens": r["mensagens"],
                        "cta_antecipado": r["cta_antecipado"], "fechamento": r["fechamento"],
                        "ritmo": (cfg.get("edicao") or {}).get("ritmo", "viral"), "posicao_texto": "topo",
                        "formatos": (cfg.get("edicao") or {}).get("formatos", ["stories", "feed45"]),
                        "objetivo": "seguir", "tags": ["anúncio"]})
    return nome


def _ler_md(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def detalhe(nome: str) -> dict:
    pasta = _pasta(nome)
    try:
        reparar_projeto(pasta)
    except (OSError, yaml.YAMLError):
        pass
    texto = (pasta / "projeto.yaml").read_text(encoding="utf-8")
    try:
        d = yaml.safe_load(texto) or {}
        erro_yaml = ""
    except yaml.YAMLError as e:
        d, erro_yaml = {}, str(e)
    brutos = sorted(f.name for f in (pasta / "bruto").glob("*") if f.suffix.lower() in VIDEO and not f.name.startswith(".")) \
        if (pasta / "bruto").exists() else []
    saidas = []
    mapa = json.loads(_ler_md(pasta / "trabalho" / "importados.json") or "{}")     # peças importadas: rótulo próprio
    for f in sorted(x for x in (pasta / "saida").glob("*") if x.suffix.lower() in (".mp4", ".mov", ".m4v")
                    and not x.name.startswith(".")) if (pasta / "saida").exists() else []:
        m = re.search(r"_(V\d+|TV|IA)_", f.name + "_")
        saidas.append({"arquivo": f"saida/{f.name}", "nome": f.name, "versao": mapa.get(f.name) or (m.group(1) if m else ""),
                       "previa": "_PREVIA" in f.name, "mb": round(f.stat().st_size / 1e6, 1),
                       "quando": f.stat().st_mtime})
    from .templates import TEMPLATES
    usados = {c.get("arquivo", "").split("/")[-1] for c in d.get("clipes") or []}
    return {"nome": nome, "yaml": texto, "erro_yaml": erro_yaml, "titulo": d.get("titulo", nome),
            "template": d.get("template", "divine"), "formato": d.get("formato", "reels"),
            "autorizacao_imagem": d.get("autorizacao_imagem", "pendente"),
            "versoes": [v.get("nome") for v in d.get("versoes") or []],
            "brutos": [{"nome": b, "no_projeto": b in usados, "fora": b in (d.get("brutos_fora") or []),
                        "duracao": _duracao_arquivo(pasta / "bruto" / b)} for b in brutos], "saidas": saidas,
            "ritmo": d.get("ritmo"), "epico": d.get("ritmo") == "epico" or bool(d.get("epico")),
            "entende_fala": _entende_fala(), "roteiro_automatico": d.get("roteiro_automatico"),
            "storyboard": bool(list((pasta / "trabalho").glob("storyboard_*.json"))) if (pasta / "trabalho").exists() else False,
            "storyboard_aprovado": (pasta / "trabalho" / "storyboard_aprovado.json").exists(),
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
            "corte": d.get("corte"),
            "anuncio": _anuncio_info(pasta, d) if d.get("anuncio") else None,
            "react": {"layout": d.get("layout", "auto"), "credito": d.get("credito", ""),
                      "referencias": [c.get("arquivo") for c in d.get("clipes_referencia") or []]}
            if d.get("template") == "react" else None,
            "subtitulo": d.get("subtitulo", ""), "pares": d.get("pares") or [], "cta": d.get("cta", ""),
            "conta": _conta(d), "conta_definida": d.get("conta"),
            "perfis": _perfis(),
            "video": d.get("video", True), "camera_elegante": d.get("camera_elegante"), "qualidade": d.get("qualidade"),
            "ritmo": d.get("ritmo"), "epico": d.get("epico"),
            "estilo_edicao": d.get("estilo_edicao") or "divine", "estilos_edicao": _estilos_edicao(),
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

def _estilos_edicao() -> list:
    from . import estilos
    return estilos.lista()


CAMPOS_EDITAVEIS = {"brutos_fora", "correcoes", "estilo_edicao", "efeitos_evitar", "formato_viral", "titulo", "template", "formato", "autorizacao_imagem", "selo", "cta_antecipado", "mensagens",
                    "fechamento", "versoes", "efeitos", "legendas", "corte_limpo", "posicao_texto", "legenda", "tv",
                    "tags", "formatos", "objetivo", "cards", "estilo", "fontes", "formula", "sons",
                    "sfx_automaticos", "audio", "pares", "subtitulo", "cta", "video", "camera_elegante",
                    "qualidade", "ritmo", "epico", "validado", "copy_dublagem", "clipes", "cor",
                    "ritmo_fixo", "dissolve", "musica_licenciada", "conta",
                    "clipes_referencia", "layout", "credito", "divisoria", "anuncio", "posicao_texto",
                    "remover_trechos", "alertas_ignorados"}


def dados_projeto(nome: str) -> dict:
    """Projeto como dicionário + o que o editor precisa: prévia de referência e duração da base."""
    pasta = _pasta(nome)
    d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
    previas = sorted((x for x in (pasta / "saida").glob("*.mp4") if not x.name.startswith(".")), key=lambda f: f.stat().st_mtime, reverse=True) \
        if (pasta / "saida").exists() else []
    base = pasta / "trabalho" / "base.json"
    dur = json.loads(base.read_text(encoding="utf-8")).get("duracao") if base.exists() else None
    from .config import load
    # clipes com a duração do arquivo (para a trilha de clipes: aparar, dividir, velocidade)
    from .ingest import probe, resolver
    clipes = []
    for c in d.get("clipes") or []:
        info = {"arquivo": c.get("arquivo"), "existe": False, "duracao_arquivo": None}
        try:
            arq = resolver({**d, "_pasta": pasta}, c["arquivo"])
            info.update(existe=True, duracao_arquivo=_duracao_arquivo(arq))
        except (SystemExit, Exception):
            pass
        clipes.append(info)
    linhas = {}
    for f in (pasta / "trabalho").glob("linha_*.json") if (pasta / "trabalho").exists() else []:
        try:
            linhas[f.stem[6:]] = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            pass
    ed = load("edicao")
    return {"projeto": d, "referencia": f"saida/{previas[0].name}" if previas else None, "duracao_base": dur,
            "legendas_blocos": _blocos_legenda(pasta, d), "legendas_ligadas": _leg_ativas(d),
            "legenda_estilo": _leg_estilo(d),
            "clipes_info": clipes, "linhas": linhas, "atencao": _atencao_v1(pasta),
            "previas_versao": _previas_por_versao(previas),
            "filtros": {k: v["nome"] for k, v in (ed.get("filtros") or {}).items()},
            "transicoes": {k: v["nome"] for k, v in (ed.get("transicoes") or {}).items()},
            "velocidades": ed.get("velocidades") or [0.5, 1, 2],
            "corte_limpo": bool(d.get("corte_limpo")),
            "fechamento_s": float(load("preferencias")["fechamento"]["duracao_s"]),
            "intervalo_efeitos": float(load("efeitos").get("intervalo_minimo_s", 1.5))}


def versao_app() -> dict:
    """Qual versão está rodando e de qual pasta (para não confundir cópias antigas do app)."""
    def git(*a):
        r = subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else ""
    data = git("log", "-1", "--format=%cd", "--date=format:%d/%m %H:%M")
    return {"commit": git("rev-parse", "--short", "HEAD"), "data": data, "pasta": str(ROOT),
            "ramo": git("rev-parse", "--abbrev-ref", "HEAD"), "git": bool(data)}


def _entende_fala() -> dict:
    from . import assistente, instalar_fala
    return {**instalar_fala.estado(), "ia": assistente.disponivel()[0]}


def reiniciar_no_python_do_app(porta: int, celular: bool) -> None:
    """Reabre o painel no Python próprio do app (.venv), onde a transcrição foi instalada."""
    from . import atualizar as _at
    py = _at.python_do_app(ROOT)
    args = [py, "-m", "divine_studio", "painel", "--porta", str(porta), "--sem-navegador"] + (["--celular"] if celular else [])
    threading.Timer(0.8, lambda: (os.chdir(ROOT), os.execv(args[0], args))).start()


def acao_bruto(nome: str, arquivo: str, acao: str) -> dict:
    """Vídeo bruto: 'usar' na edição, 'tirar' da edição (fica na pasta) ou 'descartar' (vai para _arquivo/ do projeto)."""
    import shutil as _sh
    pasta = _pasta(nome)
    arq = Path(arquivo).name
    f = pasta / "bruto" / arq
    if not f.exists():
        raise ValueError("vídeo bruto não encontrado")
    d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
    fora = [x for x in d.get("brutos_fora") or [] if x != arq]
    clipes = [c for c in d.get("clipes") or [] if isinstance(c, dict)]
    sem_ele = [c for c in clipes if str(c.get("arquivo", "")).split("/")[-1] != arq]
    if acao == "usar":
        novos = {"brutos_fora": fora}
        reais = [c for c in clipes if c.get("arquivo") != "bruto/IMG_0001.MOV"]
        if reais and len(sem_ele) == len(clipes):                  # edição já montada: entra no fim
            novos["clipes"] = reais + [{"arquivo": f"bruto/{arq}", "foco": [0.5, 0.4]}]
        salvar_dados(nome, novos)
        return {"ok": True, "msg": "Vídeo na edição."}
    if acao == "tirar":
        salvar_dados(nome, {"brutos_fora": fora + [arq], "clipes": sem_ele})
        return {"ok": True, "msg": "Fora da edição (o arquivo continua em bruto/)."}
    if acao == "descartar":
        destino = pasta / "_arquivo" / "bruto"
        destino.mkdir(parents=True, exist_ok=True)
        alvo = destino / arq
        k = 2
        while alvo.exists():
            alvo = destino / f"{f.stem}-{k}{f.suffix}"
            k += 1
        _sh.move(str(f), str(alvo))
        salvar_dados(nome, {"brutos_fora": fora, "clipes": sem_ele})
        return {"ok": True, "msg": f"Guardado em {alvo.relative_to(pasta)} (nada foi apagado)."}
    raise ValueError("ação desconhecida")


def _leg_ativas(d: dict) -> bool:
    from .legendas import ativas
    return ativas(d)


def _leg_estilo(d: dict) -> dict:
    """Estilo efetivo da legenda (padrão do app + padrão salvo + o do projeto), só o que o painel ajusta."""
    from .legendas import EDITAVEIS, _cfg
    from .fonts import marca
    c = _cfg(d)
    out = {k: c.get(k) for k in EDITAVEIS if c.get(k) is not None}
    out.setdefault("fonte", marca("legenda"))
    return out


def fontes_legenda() -> list:
    from .fonts import pasta_fontes
    pasta = pasta_fontes()
    nomes = sorted(p.name for p in pasta.glob("*.ttf")) if pasta.exists() else []
    return [{"arquivo": n, "nome": re.sub(r"(?<=[a-z])(?=[A-Z])", " ", n.rsplit(".", 1)[0].split("[")[0])
             .replace("-", " ").replace("_", " ")} for n in nomes]


def previa_legenda(nome: str, t: float, estilo: dict, texto: str = "") -> bytes:
    """Um quadro real do vídeo no instante t com a legenda no estilo pedido (prévia instantânea, sem render)."""
    import io
    from PIL import Image
    from .config import cor
    from .legendas import EDITAVEIS, aplicar_correcoes, camadas
    pasta = _pasta(nome)
    d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
    W, H = 1080, 1920
    fundo = None
    base = pasta / "trabalho" / "base.mov"
    if base.exists():
        try:
            r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, t):.2f}", "-i", str(base), "-frames:v", "1",
                                "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}",
                                "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, timeout=20)
            if r.stdout:
                fundo = Image.open(io.BytesIO(r.stdout)).convert("RGBA")
        except (OSError, subprocess.SubprocessError):
            fundo = None
    if fundo is None:
        fundo = Image.new("RGBA", (W, H), cor("fundo") + (255,))
    leg = {**(d.get("legendas") if isinstance(d.get("legendas"), dict) else {}),
           **{k: v for k, v in (estilo or {}).items() if k in EDITAVEIS}}
    proj = {**d, "legendas": leg}
    pal = []
    arq = pasta / "trabalho" / "fala_base.json"
    if arq.exists() and not texto:
        try:
            pal = aplicar_correcoes(json.loads(arq.read_text(encoding="utf-8")), d.get("correcoes"))
        except ValueError:
            pal = []
    if not pal:
        ws = (texto or "Sua legenda aparece aqui").split()
        pal = [{"texto": w, "inicio": t + i * 0.3, "fim": t + i * 0.3 + 0.25} for i, w in enumerate(ws)]
    cs, _ = camadas(proj, pal, W, H, 10 ** 6)
    if cs:
        import numpy as np
        c = next((c for c in cs if c.t0 <= t < c.t1), None) or min(cs, key=lambda c: abs(c.t0 - t))
        alfa = np.clip(c.alpha, 1e-6, 1)
        rgba = np.concatenate([np.clip(c.rgb_p / alfa, 0, 255), c.alpha * 255], axis=2).astype("uint8")
        fundo.alpha_composite(Image.fromarray(rgba, "RGBA"), (max(0, c.x), max(0, c.y)))
    out = io.BytesIO()
    fundo.convert("RGB").resize((540, 960)).save(out, "JPEG", quality=82)
    return out.getvalue()


def _blocos_legenda(pasta: Path, d: dict) -> list:
    """Blocos da legenda da fala (como saem no vídeo) para a faixa Legendas do editor."""
    arq = pasta / "trabalho" / "fala_base.json"
    if not arq.exists():
        return []
    try:
        from .legendas import aplicar_correcoes, blocos, _cfg as cfg_leg
        pal = aplicar_correcoes(json.loads(arq.read_text(encoding="utf-8")), d.get("correcoes"))
        c = cfg_leg(d)
        gs = blocos(pal, int(c.get("max_palavras", 4)), int(c.get("max_caracteres", 24)), float(c.get("pausa_quebra_s", 0.35)))
        return [{"inicio": round(g[0]["inicio"], 2), "fim": round(g[-1]["fim"], 2),
                 "texto": " ".join(w["texto"] for w in g)} for g in gs if g]
    except Exception:
        return []


def tira_miniaturas(nome: str, rel: str, n: int = 24, altura: int = 96) -> Path:
    """Tira de miniaturas do vídeo (uma imagem com n quadros lado a lado) para a faixa de vídeo do editor."""
    import hashlib
    pasta = _pasta(nome)
    video = _arquivo_do_projeto(pasta, rel)
    chave = hashlib.sha1(f"{rel}|{video.stat().st_mtime}|{n}|{altura}".encode()).hexdigest()[:12]
    saida = pasta / "trabalho" / f"tira_{chave}.jpg"
    if not saida.exists():
        saida.parent.mkdir(exist_ok=True)
        dur = max(0.5, _duracao_arquivo(video) or 1.0)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf",
                        f"fps={n / dur},scale=-2:{altura},tile={n}x1", "-frames:v", "1", "-q:v", "5", str(saida)],
                       check=False, timeout=120)
    if not saida.exists():
        raise ValueError("não consegui fazer as miniaturas do vídeo")
    return saida


def _previas_por_versao(previas: list) -> dict:
    """{versão: prévia mais recente} (a lista já vem da mais nova para a mais velha): a aba Ajustar mostra a versão
    que você escolheu, com os "!" dela, e não sempre a V1."""
    out = {}
    for f in previas:
        m = re.search(r"_(V\d+|TV|IA)_", f.name + "_")
        if m and "_PREVIA" in f.name and m.group(1) not in out:
            out[m.group(1)] = f"saida/{f.name}"
    return out


def estudio_config() -> dict:
    """config/estudio.yaml, só com os efeitos e sons que existem de verdade (um nome errado no YAML não quebra a tela)."""
    from .efeitos import catalogo
    try:
        cfg = dict(load("estudio"))
    except FileNotFoundError:
        cfg = {}
    tipos = {c["tipo"]: c for c in catalogo()}
    kit = ROOT / "Biblioteca_SFX" / "1_kit_original_divine"
    cfg["efeitos_rapidos"] = [{**e, "rotulo": e.get("rotulo") or tipos[e["tipo"]]["nome"]}
                              for e in cfg.get("efeitos_rapidos") or [] if isinstance(e, dict) and e.get("tipo") in tipos]
    cfg["sons_rapidos"] = [n for n in cfg.get("sons_rapidos") or [] if (kit / f"{n}.wav").exists()]
    cfg["agentes"] = [a for a in cfg.get("agentes") or [] if isinstance(a, dict) and a.get("chave") and a.get("nome")]
    cfg.setdefault("abrir_sozinho", True)
    cfg.setdefault("largura_minima", 1100)
    cfg["previa_automatica"] = {"ligada_por_padrao": False, "espera_s": 4, **(cfg.get("previa_automatica") or {})}
    return cfg


def _atencao_v1(pasta: Path) -> dict:
    from . import atencao
    for v in ("V1", "TV", "IA"):
        a = atencao.ler(pasta, v)
        if a:
            return {"versao": v, "zonas": a.get("zonas") or []}
    return {}


_DURACOES: dict = {}


def _duracao_arquivo(arq: Path) -> float:
    from .ingest import probe
    chave = (str(arq), arq.stat().st_mtime)
    if chave not in _DURACOES:
        _DURACOES[chave] = probe(arq)["duracao"]
    return _DURACOES[chave]


def fixar_linha(nome: str, versao: str | None = None) -> dict:
    """Traz os efeitos do ritmo e os sons automáticos da última prévia para a linha do tempo (editáveis).
    Depois disso o ritmo não acrescenta mais nada sozinho (ritmo_fixo) e os sons automáticos ficam desligados."""
    pasta = _pasta(nome)
    trab = pasta / "trabalho"
    arqs = sorted(trab.glob("linha_*.json"), key=lambda f: (f.stem != "linha_V1", f.stem == "linha_IA", f.stem)) \
        if trab.exists() else []
    if versao:
        arqs = [a for a in arqs if a.stem == f"linha_{versao}"]
    if not arqs:
        raise ValueError("gere as prévias uma vez para o app saber quais efeitos e sons automáticos entraram")
    linha = json.loads(arqs[0].read_text(encoding="utf-8"))
    d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
    efeitos = list(d.get("efeitos") or [])
    for e in linha.get("efeitos") or []:
        efeitos.append({k: v for k, v in e.items() if not k.startswith("_")})
    sons = list(d.get("sons") or [])
    ja = {(s.get("nome"), round(float(s.get("inicio", 0)), 2)) for s in sons}
    for s_ in linha.get("sons") or []:
        if (s_["nome"], round(float(s_["inicio"]), 2)) not in ja:
            sons.append({"nome": s_["nome"], "inicio": s_["inicio"], "ganho_db": s_.get("ganho_db", -24)})
    salvar_dados(nome, {"efeitos": sorted(efeitos, key=lambda e: float(e.get("inicio", 0))),
                        "sons": sorted(sons, key=lambda x: float(x.get("inicio", 0))),
                        "sfx_automaticos": False, "ritmo_fixo": True})
    return {"efeitos": len(linha.get("efeitos") or []), "sons": len(linha.get("sons") or []), "versao": linha.get("versao")}


def barrar_aprovacao_por_fala(pasta: Path) -> None:
    """✓ Aprovar com algo de compliance na fala da última prévia: para aqui, com o que fazer.
    Frases já marcadas para sair (remover_trechos) não contam: a final refaz o corte e confere de novo.
    Frases "confira" (prazo, quantidade) que você já conferiu (compliance_conferido) também não."""
    from .compliance import achados_na_fala, video_falado
    d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
    try:
        fala = json.loads((pasta / "trabalho" / "fala_base.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        if video_falado(d):                       # tem fala e ninguém leu: não aprova (a final também não sairia)
            raise ValueError("Ainda não dá para aprovar: este vídeo tem fala, mas ela ainda não foi transcrita, então o "
                             "revisor de compliance não leu o que é dito. Toque em 🎤 Instalar a transcrição (passo 3) e "
                             "depois em Gerar prévias.")
        return                                    # sem fala (só imagem e música): nada para ler
    ruins = [x for x in achados_na_fala(fala, d, ignorar=d.get("remover_trechos")) if not x["conferido"]]
    if not ruins:
        return
    x = next((r for r in ruins if r["nivel"] == "erro"), ruins[0])
    fr = x["frase"]
    if x["nivel"] == "erro":
        raise ValueError(f"Ainda não dá para aprovar: aos {fr['inicio']:.0f} s a fala diz \"{fr['texto'][:70]}\" "
                         f"({x['achado'].motivo}) Toque no ! vermelho da aba Ajustar: ✂ Tirar esta frase ou 🎙 Dublar sem ela.")
    raise ValueError(f"Confira antes de aprovar: aos {fr['inicio']:.0f} s a fala diz \"{fr['texto'][:70]}\", que pode soar "
                     "como promessa de prazo ou de quantidade. Toque no ! laranja da aba Ajustar: se for informação, "
                     "✓ Conferi; se for promessa, ✂ Tirar esta frase ou 🎙 Dublar sem ela.")


def acao_alerta(nome: str, versao: str, id_: str, acao: str) -> dict:
    """Ações de um toque nos pontos "!" (as de gravar, dublar e corrigir abrem telas no próprio painel)."""
    from . import alertas
    pasta = _pasta(nome)
    ponto = next((x for x in alertas.gerar(pasta, versao, nome)["pontos"] if x["id"] == id_), None)
    if not ponto:
        raise ValueError("este ponto já foi resolvido ou ignorado; gere a prévia de novo para atualizar")
    d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
    if acao == "ignorar":
        if ponto["nivel"] in alertas.TRAVAM:   # compliance prevalece: não se ignora, se resolve
            raise ValueError("Compliance (CFM/Anvisa) não dá para ignorar: tire a frase, regrave sem ela"
                             + (" ou toque em ✓ Conferi se for só informação." if ponto["nivel"] == "confirmar" else "."))
        salvar_dados(nome, {"alertas_ignorados": sorted(set(d.get("alertas_ignorados") or []) | {id_})})
        return {"ok": True, "msg": "Ignorado: este ponto não aparece mais nesta edição."}
    a = next((x for x in ponto["acoes"] if x["tipo"] == acao), None)
    if not a:
        raise ValueError("ação indisponível para este ponto")
    if acao == "conferir_fala":               # você leu e é informação, não promessa: fica anotado com a data
        feitos = list(d.get("compliance_conferido") or [])
        if not any((x.get("id") if isinstance(x, dict) else x) == a["id_frase"] for x in feitos):
            feitos.append({"id": a["id_frase"], "frase": a["frase"][:200],
                           "em": _dt.datetime.now().isoformat(timespec="minutes")})
        salvar_dados(nome, {"compliance_conferido": feitos}, do_app=True)
        return {"ok": True, "msg": "Anotado: você conferiu esta frase. Se a fala mudar, o app pergunta de novo."}
    if acao == "cortar_frase":                # o corte limpo tira a frase exata na próxima prévia (remover_trechos)
        trechos = list(d.get("remover_trechos") or [])
        for f in a.get("frases") or [a["frase"]]:
            if f not in trechos:
                trechos.append(f)
        novos = {"remover_trechos": trechos}
        if not d.get("corte_limpo"):
            # só as frases marcadas saem: ligar o corte limpo inteiro (muletas, takes, pausas) mudaria o vídeo todo
            novos["corte_limpo"] = "so_frases"
        salvar_dados(nome, novos)
        return {"ok": True, "msg": "A frase sai na próxima prévia (toque em Gerar prévias). Dublagens e efeitos que "
                                  "você já pôs acompanham a fala e continuam no lugar certo."}
    if acao == "efeito":
        efeitos = list(d.get("efeitos") or []) + [dict(a["efeito"])]
        salvar_dados(nome, {"efeitos": sorted(efeitos, key=lambda e: float(e.get("inicio", 0)))})
        return {"ok": True, "msg": f"Efeito colocado em {a['efeito'].get('inicio')} s. Gere a prévia para ver."}
    raise ValueError("esta ação abre no painel (gravador ou legenda)")


# campos que só o próprio app grava (nunca pelo editor genérico): o registro de que você conferiu uma frase
CAMPOS_DO_APP = {"compliance_conferido"}


def salvar_dados(nome: str, novos: dict, do_app: bool = False) -> None:
    """Atualiza só os campos enviados; o resto do projeto.yaml fica como estava."""
    pasta = _pasta(nome)
    d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
    for k, v in novos.items():
        if k not in CAMPOS_EDITAVEIS and not (do_app and k in CAMPOS_DO_APP):
            raise ValueError(f"campo não editável: {k}")
        if v in (None, "", []) and k in ("efeitos", "legenda", "selo", "camera_elegante", "qualidade", "epico", "copy_dublagem",
                                                  "cor", "ritmo_fixo", "musica_licenciada", "conta"):
            d.pop(k, None)      # vazio = sem efeito/selo; a legenda vazia volta a ser gerada sozinha
        else:
            d[k] = v
    if "efeitos" in novos:
        from .efeitos import QUADRO, TIPOS
        for ef in d.get("efeitos") or []:
            if ef.get("tipo") not in TIPOS and ef.get("tipo") not in QUADRO:
                raise ValueError(f"efeito desconhecido: {ef.get('tipo')}")
            ef["inicio"] = round(float(ef.get("inicio", 0)), 2)
    if "efeitos" in novos or "audio" in novos:
        # efeitos e dublagens presos às PALAVRAS da fala (ancoras.py): um corte depois não os joga no lugar errado
        from . import ancoras
        try:
            fala = json.loads((pasta / "trabalho" / "fala_base.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            fala = []
        if d.get("efeitos"):
            d["efeitos"] = ancoras.ancorar_itens(d["efeitos"], fala)
        if (d.get("audio") or {}).get("dublagem"):
            d["audio"] = {**d["audio"], "dublagem": ancoras.ancorar_itens(d["audio"]["dublagem"], fala, com_fim=True)}
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


EXEMPLO_CLIPE = "bruto/IMG_0001.MOV"


def _clipe_estruturado(texto: str, arquivo: str) -> str:
    """Plano B (YAML já regravado pelo editor): carrega, troca o exemplo do modelo e acrescenta o clipe."""
    d = yaml.safe_load(texto) or {}
    clipes = [c for c in d.get("clipes") or [] if isinstance(c, dict) and c.get("arquivo") != EXEMPLO_CLIPE]
    if not any(c.get("arquivo") == arquivo for c in clipes):
        clipes.append({"arquivo": arquivo})
    d["clipes"] = clipes
    return "# Divine Studio\n" + yaml.safe_dump(d, allow_unicode=True, sort_keys=False, width=1000, default_flow_style=None)


def _yaml_ok(texto: str, arquivo: str | None = None) -> bool:
    try:
        d = yaml.safe_load(texto) or {}
    except yaml.YAMLError:
        return False
    arqs = [c.get("arquivo") for c in d.get("clipes") or [] if isinstance(c, dict)]
    return isinstance(d, dict) and (arquivo is None or (arquivo in arqs and EXEMPLO_CLIPE not in arqs))


def adicionar_clipe(texto: str, arquivo: str) -> str:
    """Acrescenta o clipe preservando os comentários do modelo; se o arquivo já foi regravado em outro formato,
    usa o YAML estruturado (nunca deixa o projeto.yaml quebrado nem com o vídeo de exemplo)."""
    novo_texto = _adicionar_clipe_texto(texto, arquivo)
    if _yaml_ok(novo_texto, arquivo):
        return novo_texto
    return _clipe_estruturado(texto, arquivo)


def reparar_projeto(pasta: Path) -> bool:
    """Conserta projeto.yaml quebrado pelo clipe com recuo errado (versões até 01/11/2026). Guarda o original."""
    arq = pasta / "projeto.yaml"
    texto = arq.read_text(encoding="utf-8")
    if _yaml_ok(texto):
        d = yaml.safe_load(texto) or {}
        exemplo = [c for c in d.get("clipes") or [] if isinstance(c, dict) and c.get("arquivo") == EXEMPLO_CLIPE]
        reais = [c for c in d.get("clipes") or [] if isinstance(c, dict) and c.get("arquivo") != EXEMPLO_CLIPE]
        if not (exemplo and reais and not (pasta / EXEMPLO_CLIPE).exists()):
            return False
        novo = texto
    else:
        linhas = texto.split("\n")
        for i, ln in enumerate(linhas):
            if re.match(r"^  - \{arquivo: ", ln):            # clipe inserido com recuo onde a lista está na coluna 0
                linhas[i] = ln[2:]
        novo = "\n".join(linhas)
        if not _yaml_ok(novo):
            return False
    d = yaml.safe_load(novo) or {}
    d["clipes"] = [c for c in d.get("clipes") or [] if not (isinstance(c, dict) and c.get("arquivo") == EXEMPLO_CLIPE
                                                            and not (pasta / EXEMPLO_CLIPE).exists())]
    (pasta / "trabalho").mkdir(exist_ok=True)
    (pasta / "trabalho" / "projeto.yaml.antes-do-reparo").write_text(texto, encoding="utf-8")
    arq.write_text("# Divine Studio (reparado)\n" + yaml.safe_dump(d, allow_unicode=True, sort_keys=False, width=1000,
                                                                     default_flow_style=None), encoding="utf-8")
    return True


def _adicionar_clipe_texto(texto: str, arquivo: str) -> str:
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
    "post": ["post", "exportar"], "antesdepois": ["antesdepois", "exportar"], "cortes": ["cortes"],
    "storyboard": ["storyboard"], "instalar_fala": ["instalar-fala"],
    "fala_precisa": ["instalar-fala", "--preciso"],
}


def _job_do_projeto(nome: str):
    for j in JOBS.values():
        if j["projeto"] == nome and j["estado"] == "rodando":
            return j["id"]
    return None


def iniciar(nome: str, acao: str, versoes: list | None = None) -> str:
    pasta = _pasta(nome)
    try:
        reparar_projeto(pasta)
    except (OSError, yaml.YAMLError):
        pass
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
        if versoes and acao in ("previa", "final", "storyboard"):
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
    return {"id": jid, "acao": j["acao"], "estado": j["estado"], "versoes": j.get("versoes") or [], "log": "\n".join(linhas[-200:]),
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
            if u.path in ("/app.js", "/editor.js", "/carrossel.js", "/telas.js", "/ia.js", "/biblioteca.js", "/storyboard.js", "/lab.js", "/estudio.js", "/estilo.css", "/logo.jpg", "/icone-64.png", "/icone-180.png",
                          "/manifest.json"):
                return self._arquivo(WEB / u.path.lstrip("/"))
            if u.path == "/api/versao":
                return self._json(versao_app())
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
            if u.path == "/api/copy":
                from .copy_voz import ler
                return self._json(ler(_pasta(q["p"])))
            if u.path == "/api/diagnostico":
                return self._json(diagnostico())
            if u.path == "/qr.svg":
                try:
                    return self._bytes(qr_svg(q.get("u", "")[:300]), "image/svg+xml")
                except ImportError:
                    return self._erro("QR indisponível (falta a biblioteca segno)", 404)
            if u.path == "/api/celular":
                porta_ = self.server.server_address[1]
                return self._json({"ativo": bool(Painel.codigo), "endereco": f"http://{ip_da_rede()}:{porta_}",
                                   "enderecos": enderecos(porta_),
                                   "codigo": Painel.codigo if self.client_address[0] in LOCAIS else None})
            if u.path == "/api/videos":
                return self._json(videos())
            if u.path == "/api/lab":
                from . import entrada, lab, radar, tiktok
                conta = q.get("conta") or None
                return self._json({"placar": lab.placar(conta), "plano": lab.plano_semana(conta),
                                   "radar": radar.em_alta()[:60], "missao_instagram": radar.missao("instagram"),
                                   "missao_tiktok": radar.missao("tiktok"),
                                   "entrada": {"pastas": [str(x) for x in entrada.pastas()],
                                               "pendentes": [x.name for x in entrada.pendentes()],
                                               "recentes": sorted(entrada._indice().values(), key=lambda x: x.get("em", ""),
                                                                  reverse=True)[:15]},
                                   "tiktok": tiktok.estado()})
            if u.path == "/api/radar/missao":
                from . import radar
                host = self.headers.get("Host") or "127.0.0.1:8765"
                return self._json({"texto": radar.missao_completa(q.get("rede", "instagram"), q.get("tema", ""),
                                                                  f"http://{host}", q.get("higgsfield") == "1")})
            if u.path == "/api/automacoes":
                from . import automacoes
                return self._json({"regras": automacoes.regras(), "historico": automacoes.historico()})
            if u.path == "/api/tiktok/conectar":
                from . import tiktok
                return self._json({"link": tiktok.link_autorizacao()})
            if u.path == "/tiktok/retorno":
                from . import tiktok
                try:
                    if q.get("error"):
                        raise SystemExit(q.get("error_description") or q["error"])
                    tiktok.retorno(q.get("code", ""), q.get("state", ""))
                    msg = "TikTok conectado. Pode fechar esta aba e voltar ao Divine Studio."
                except SystemExit as e:
                    msg = f"Não conectou: {e}"
                return self._html(f"<meta charset='utf-8'><body style='font-family:sans-serif;background:#12110F;"
                                  f"color:#F5F4F1;padding:40px'><h2>{msg}</h2><p><a style='color:#CCBD91' "
                                  f"href='/#programacao'>Voltar ao Divine Studio</a></p></body>")
            if u.path == "/api/storyboard":
                from . import storyboard
                pasta = _pasta(q["p"])
                vs = storyboard.versoes_com_storyboard(pasta)
                v = q.get("v") or (vs[0] if vs else "V1")
                return self._json({"versoes": vs, "versao": v, "dados": storyboard.ler(pasta, v),
                                   "aprovado": (pasta / "trabalho" / "storyboard_aprovado.json").exists()})
            if u.path == "/api/opiniao":
                from . import aprendizado, feedback
                pasta = _pasta(q["p"])
                pub = next((x for x in aprendizado.ler(pasta).get("publicacoes") or [] if x.get("versao") == q["v"]), {})
                return self._json({"app": feedback.opiniao_app(pasta, q["v"]), "sua": pub.get("feedback") or {},
                                   "comentario_ia": pub.get("comentario_ia"), "reacoes": feedback.REACOES,
                                   "ajustes": feedback.explicar(feedback.ajustes())})
            if u.path == "/api/crescimento":
                from . import crescimento
                return self._json(crescimento.resumo())
            if u.path == "/api/integracoes":
                from . import integracoes
                ok, motivo = integracoes.nano_banana_ok()
                return self._json({"ferramentas": integracoes.catalogo(), "nano_banana": ok, "motivo": motivo})
            if u.path == "/api/tv":
                return self._json(canal_tv())
            if u.path in ("/tv", "/tv/"):
                return self._arquivo(WEB / "tv.html")
            if u.path == "/api/galeria":
                return self._json(galeria())
            if u.path == "/miniatura.jpg":
                return self._bytes(capa_peca(_pasta(q["p"]), q["f"]), "image/jpeg")
            if u.path == "/api/instagram":
                from . import instagram
                return self._json(instagram.conta())
            if u.path == "/api/programacao":
                from . import aprendizado
                return self._json({"pecas": aprendizado.todas_publicacoes(), "aprendi": aprendizado.resumo()})
            if u.path == "/api/hooks":
                from .hooks import sortear
                return self._json([{"id": h["id"], "tipo": h["tipo"], "batidas": h["batidas"]}
                                   for h in sortear(int(q.get("n", 3)), tema=q.get("tema"))])
            if u.path == "/arquivo":
                return self._arquivo(_arquivo_do_projeto(_pasta(q["p"]), q["f"]))
            if u.path == "/api/estudio":            # a tela Estúdio: agentes, efeitos e sons rápidos (config/estudio.yaml)
                return self._json(estudio_config())
            if u.path == "/api/fala":
                return self._json(_entende_fala())
            if u.path == "/api/sugestoes":
                from . import sugestoes
                return self._json(sugestoes.gerar(_pasta(q["p"]), q["p"]))
            if u.path == "/api/alertas":            # o "!" da linha do tempo (config/alertas.yaml)
                from . import alertas
                return self._json(alertas.gerar(_pasta(q["p"]), q.get("v") or "V1", q["p"]))
            if u.path == "/api/fala_final":         # a fala da final, para você ler antes de ligar "postar sozinho"
                from . import publicar
                pasta_ff = _pasta(q["p"])
                ff = publicar.fala_final(pasta_ff, q.get("v") or "")
                d_ff = yaml.safe_load((pasta_ff / "projeto.yaml").read_text(encoding="utf-8")) or {}
                pub_ff = next((x for x in d_ff.get("publicacoes") or [] if x.get("versao") == q.get("v")), {})
                return self._json({"tem": ff["tem"], "texto": ff["texto"], "hash": ff["hash"], "arquivo": ff["arquivo"],
                                   "lida": bool(ff["tem"] and pub_ff.get("fala_lida") == ff["hash"])})
            if u.path == "/api/previsao":           # de 100 pessoas, quantas ficam (por versão)
                from . import previsao
                pasta = _pasta(q["p"])
                vs = [v for v in (q.get("v") or "").split(",") if v] or \
                    sorted({f.stem[9:] for f in (pasta / "trabalho").glob("previsao_*.json") if "_" not in f.stem[9:]})
                return self._json({v: {**previsao.ler(pasta, v), "frase": previsao.frase(previsao.ler(pasta, v))}
                                   for v in vs})
            if u.path == "/api/fontes_legenda":
                return self._json(fontes_legenda())
            if u.path == "/legenda.jpg":
                return self._bytes(previa_legenda(q["p"], float(q.get("t", 0)), json.loads(q.get("estilo") or "{}"),
                                                  q.get("texto", "")[:80]), "image/jpeg")
            if u.path == "/api/tira":
                return self._arquivo(tira_miniaturas(q["p"], q["f"], int(q.get("n", 24))))
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
            if u.path == "/api/musica":
                pasta = _pasta(q["p"])
                nome = Path(unquote(q.get("nome", "musica.mp3"))).name
                if Path(nome).suffix.lower() not in (".mp3", ".m4a", ".wav", ".aac", ".aiff", ".flac"):
                    return self._erro("só áudio (.mp3, .m4a, .wav)")
                destino = pasta / "bruto" / f"musica_{slug(Path(nome).stem, 30)}{Path(nome).suffix.lower()}"
                destino.parent.mkdir(exist_ok=True)
                n = int(self.headers.get("Content-Length") or 0)
                destino.write_bytes(self.rfile.read(n))
                d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
                aud = dict(d.get("audio") or {})
                aud["musica"] = f"bruto/{destino.name}"
                aud["trilha"] = True
                salvar_dados(q["p"], {"audio": aud})
                return self._json({"ok": True, "arquivo": aud["musica"]})
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
                novo = {"arquivo": f"trabalho/dublagem/{wav.name}", "inicio": round(float(q.get("inicio", 0)), 2)}
                aviso_dub = ""
                if q.get("fim"):                     # dublar um trecho (ponto "!"): só ali o som original fica mudo
                    from .audio import ajustar_take
                    fim = round(max(float(q["fim"]), novo["inicio"]), 2)
                    ajustada = dest / f"voz_{carimbo}_no_trecho.wav"   # a gravação inteira continua em voz_*.wav
                    aj = ajustar_take(wav, ajustada, fim - novo["inicio"])
                    novo.update({"arquivo": f"trabalho/dublagem/{ajustada.name}", "original_gravado": f"trabalho/dublagem/{wav.name}",
                                 "tempo": aj["tempo"]})
                    if aj["sobra_s"] > 0.15:         # passou do trecho mesmo acelerando: cala o original até o fim dela
                        fim = round(novo["inicio"] + aj["duracao"], 2)
                        aviso_dub = (f"A gravação ficou {aj['sobra_s']:.1f} s mais longa que o trecho e cobre o começo "
                                     "da frase seguinte. Se não gostar, grave de novo um pouco mais curta.")
                    elif aj["sobra_s"] < -0.3:
                        aviso_dub = (f"A gravação ficou {-aj['sobra_s']:.1f} s mais curta que o trecho: sobra um "
                                     "silêncio com a boca mexendo. Grave de novo no ritmo da fala original.")
                    novo["fim"] = fim
                # a âncora (as palavras daquele trecho) é posta por salvar_dados: se um corte mudar a base depois,
                # a dublagem acompanha a fala (ancoras.py)
                dubs.append(novo)
                aud["dublagem"] = dubs
                if q.get("substituir") == "1" and not q.get("fim"):
                    aud["original"] = False          # a gravação substitui o som do vídeo inteiro
                aud.setdefault("trilha", True)
                salvar_dados(q["p"], {"audio": aud})
                return self._json({"ok": True, "arquivo": novo["arquivo"], "aviso": aviso_dub})
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
            if u.path == "/api/copy":
                pasta = _pasta(dados["p"])
                salvar_dados(dados["p"], {"copy_dublagem": (dados.get("copy") or "").strip() or None})
                from .copy_voz import ler
                return self._json(ler(pasta))
            if u.path == "/api/copy/ia":
                from .copy_voz import melhorar_com_ia
                return self._json({"copy": melhorar_com_ia(_pasta(dados["p"]), dados.get("copy", ""))})
            if u.path == "/api/importar":
                from .importar import importar
                return self._json(importar(dados.get("origem") or None, bool(dados.get("copiar")),
                                           bool(dados.get("simular"))))
            if u.path == "/api/fixar_linha":
                return self._json(fixar_linha(dados["p"], dados.get("versao")))
            if u.path == "/api/opiniao":
                from . import feedback
                return self._json(feedback.registrar(_pasta(dados["p"]), dados["versao"], dados.get("reacoes") or [],
                                                     dados.get("texto", ""), dados.get("nota")))
            if u.path == "/api/alertas/acao":       # um toque num ponto "!": ignorar, tirar a frase, pôr o efeito
                return self._json(acao_alerta(dados["p"], dados.get("versao") or "V1", dados["id"], dados["acao"]))
            if u.path == "/api/atencao/aplicar":
                from . import atencao
                pasta = _pasta(dados["p"])
                at = atencao.ler(pasta, dados["versao"])
                zona = (at.get("zonas") or [])[int(dados["i"])]
                d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
                efeitos = list(d.get("efeitos") or []) + [dict(zona["acao"])]
                salvar_dados(dados["p"], {"efeitos": sorted(efeitos, key=lambda e: float(e.get("inicio", 0)))})
                return self._json({"ok": True, "efeito": zona["acao"]})
            if u.path == "/api/opiniao/ia":
                from . import feedback
                return self._json({"texto": feedback.comentario_ia(_pasta(dados["p"]), dados["versao"])})
            if u.path == "/api/crescimento/seguidores":
                from . import crescimento
                crescimento.registrar_seguidores(dados["conta"], int(dados["n"]))
                return self._json({"ok": True})
            if u.path == "/api/crescimento/stories":
                from . import crescimento
                crescimento.marcar_stories(dados["conta"], feito=bool(dados.get("feito", True)))
                return self._json({"ok": True})
            if u.path == "/api/crescimento/puxar":
                from . import crescimento
                return self._json(crescimento.puxar_seguidores())
            if u.path == "/api/quadro":
                from . import integracoes
                pasta = _pasta(dados["p"])
                video = _arquivo_do_projeto(pasta, dados["arquivo"])
                nome = integracoes.nome_saida("quadro")
                integracoes.quadro(video, float(dados.get("t", 0)), pasta / "bruto" / nome)
                return self._json({"arquivo": f"bruto/{nome}"})
            if u.path == "/api/nanobanana":
                from . import integracoes
                pasta = _pasta(dados["p"])
                img = _arquivo_do_projeto(pasta, dados["imagem"])
                nome = integracoes.nome_saida("nanobanana")
                integracoes.nano_banana(img, dados.get("pedido", ""), pasta / "bruto" / nome)
                return self._json({"arquivo": f"bruto/{nome}"})
            if u.path == "/api/anuncio/roteiro":
                from . import anuncios
                pasta = _pasta(dados["p"])
                d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
                r = anuncios.roteiro(d)
                salvar_dados(dados["p"], {"versoes": r["versoes"], "mensagens": r["mensagens"],
                                          "cta_antecipado": r["cta_antecipado"], "fechamento": r["fechamento"]})
                return self._json({"ok": True})
            if u.path == "/api/duplicar":
                return self._json({"nome": duplicar(dados["p"])})
            if u.path == "/api/legenda_padrao":
                from .legendas import salvar_padrao
                return self._json(salvar_padrao(dados.get("estilo") or {}))
            if u.path == "/api/excluir":
                if _job_do_projeto(dados["p"]):
                    raise ValueError("espere a tarefa deste projeto terminar")
                return self._json({"destino": excluir(dados["p"])})
            if u.path == "/api/arquivar":
                if _job_do_projeto(dados["p"]):
                    raise ValueError("espere a tarefa deste projeto terminar")
                return self._json({"destino": arquivar(dados["p"])})
            if u.path == "/api/nova_edicao":
                return self._json({"nome": nova_edicao(dados.get("tipo", "video"), dados.get("titulo", ""))})
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
            if u.path == "/api/clipe" and dados.get("referencia"):
                pasta = _pasta(dados["p"])
                d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8")) or {}
                refs = [{"arquivo": f"bruto/{Path(dados['arquivo']).name}", "mudo": True}]
                if dados.get("somar"):
                    refs = list(d.get("clipes_referencia") or []) + refs
                salvar_dados(dados["p"], {"clipes_referencia": refs})
                return self._json({"ok": True})
            if u.path == "/api/bruto":                 # usar / tirar da edição / descartar (vai para _arquivo/)
                return self._json(acao_bruto(dados["p"], dados["nome"], dados["acao"]))
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
            if u.path == "/api/instagram/conectar":
                from . import instagram
                if self.client_address[0] not in LOCAIS and not Painel.codigo:
                    raise ValueError("conecte pelo próprio Mac")
                r = instagram.conectar(dados.get("token", ""))
                try:
                    r["sincronizado"] = instagram.sincronizar()
                except SystemExit as e:
                    r["aviso"] = str(e)
                return self._json(r)
            if u.path == "/api/instagram/desconectar":
                from . import instagram
                instagram.desconectar(dados.get("usuario"))
                return self._json({"ok": True})
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
            if u.path == "/api/aprovar":             # um toque: aprova a versão (o app aprende) e exporta a final
                from . import aprendizado
                if _job_do_projeto(dados["p"]):
                    raise ValueError("espere a tarefa deste projeto terminar")
                pasta_ap = _pasta(dados["p"])
                barrar_aprovacao_por_fala(pasta_ap)      # compliance na fala: avisa já, antes de aprender e exportar
                # só o PEDIDO fica anotado: "aprovado", "gostei" e "validado" (que alimentam o aprendizado e a Galeria)
                # entram quando a final sai de fato pelo revisor (cli._entregar). Final barrada não ensina nada.
                aprendizado.marcar(pasta_ap, dados["versao"], dados.get("arquivo"),
                                   aprovacao_pedida=_dt.datetime.now().isoformat(timespec="minutes"),
                                   aprovacao_barrada=None)
                return self._json({"job": iniciar(dados["p"], "final", [dados["versao"]])})
            if u.path == "/api/sugestoes/ia":
                from . import sugestoes
                return self._json({"sugestoes": sugestoes.com_ia(_pasta(dados["p"]))})
            if u.path == "/api/sugestoes/higgsfield":
                from . import higgsfield as hf, sugestoes
                ped = sugestoes.pedir_higgsfield(dados["p"], _pasta(dados["p"]), dados["arquivo"])
                return self._json({"pedido": ped, "instrucao": hf.instrucao_claude([ped["id"]])})
            if u.path == "/api/publicacao":
                from . import aprendizado
                campos = {k: v for k, v in (dados.get("campos") or {}).items()
                          if k in ("status", "gostei", "nao_gostei", "data_agendada", "data_postagem", "rede", "link",
                                   "metricas", "obs", "validado", "na_tv", "auto_postar", "redes", "hora_agendada",
                                   "link_tiktok", "formato_viral")}
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
            if u.path == "/api/fala_lida":           # você leu a fala da final: o postar sozinho pode usar ESTA fala
                from . import aprendizado, publicar
                pasta_fl = _pasta(dados["p"])
                ff = publicar.fala_final(pasta_fl, dados["versao"])
                if not ff["tem"] or dados.get("hash") != ff["hash"]:
                    raise ValueError("a fala da final mudou: abra de novo e leia a fala atual")
                return self._json(aprendizado.marcar(pasta_fl, dados["versao"], fala_lida=ff["hash"],
                                                     fala_lida_em=_dt.datetime.now().isoformat(timespec="minutes")))
            if u.path == "/api/publicar":             # "Publicar agora" (você tocou): mesmas travas, menos o 'sozinho'
                from . import publicar
                motivos = publicar.pode_publicar(dados["p"], dados["versao"], manual=True)
                if motivos:
                    raise ValueError("Não dá para publicar: " + "; ".join(motivos))
                return self._json(publicar.publicar(dados["p"], dados["versao"], manual=True))
            if u.path == "/api/radar/colar":
                from . import radar
                return self._json(radar.importar_texto(dados.get("texto", ""), dados.get("fonte", "chrome")))
            if u.path == "/api/radar/buscar":
                from . import radar
                return self._json(radar.buscar_instagram())
            if u.path == "/api/radar/roteiro":
                from . import radar
                return self._json(radar.roteiro(dados["id"], dados.get("tema") or "Divine", dados.get("ia", True)))
            if u.path == "/api/radar/projeto":
                from . import radar
                return self._json({"nome": radar.criar_projeto(dados["id"], dados.get("tema") or "Divine", dados.get("ia", True))})
            if u.path == "/api/radar/marcar":
                from . import radar
                return self._json(radar.marcar(dados["id"], **{k: v for k, v in dados.items() if k in ("descartado", "nota")}))
            if u.path == "/api/entrada/varrer":
                from . import automacoes
                rodou = automacoes.ciclo(iniciar=iniciar)
                return self._json({"rodou": [{"regra": r, "acao": a, "alvo": al, "detalhe": d} for r, a, al, d in rodou]})
            if u.path == "/api/automacoes/ligar":
                from . import automacoes
                automacoes.ligar(int(dados["indice"]), bool(dados["ligado"]))
                return self._json({"ok": True})
            if u.path == "/api/tiktok/app":
                from . import tiktok
                tiktok.salvar_app(dados["client_key"], dados["client_secret"])
                return self._json(tiktok.estado())
            if u.path == "/api/tiktok/desconectar":
                from . import tiktok
                tiktok.desconectar()
                return self._json(tiktok.estado())
            if u.path == "/api/storyboard":           # resposta: "aprovado" ou "4B: troca o título por ..."
                from . import storyboard
                nome = dados["p"]
                v = dados.get("v") or "V1"
                if dados.get("gerar"):
                    return self._json({"job": iniciar(nome, "storyboard", dados.get("versoes"))})
                r = storyboard.responder(_pasta(nome), dados.get("resposta", ""), v)
                if r["aprovado"]:
                    r["job"] = iniciar(nome, "final", dados.get("versoes"))
                elif r["aplicados"]:
                    r["job"] = iniciar(nome, "storyboard", dados.get("versoes"))
                return self._json(r)
            if u.path == "/api/reiniciar":           # depois de instalar a transcrição: painel no Python novo
                reiniciar_no_python_do_app(self.server.server_address[1], bool(self.codigo))
                return self._json({"reiniciando": True})
            if u.path == "/api/atualizar":           # baixa a versão nova e reinicia este painel
                from . import atualizar as _at
                r = _at.atualizar(ROOT)
                _at.preparar_python(ROOT)
                d = _at.dependencias(ROOT)
                _at.fontes(ROOT)
                from . import instalar_fala as _if
                if _if.estado()["precisa_reiniciar"]:       # o Python novo ficou pronto: o painel passa para ele
                    r = {**r, "ok": True, "mudou": True, "msg": (r.get("msg") or "") + " Transcrição instalada."}
                if r["ok"] and r.get("mudou"):
                    porta = self.server.server_address[1]
                    py = _at.python_do_app(ROOT)
                    args = [py, "-m", "divine_studio", "painel", "--porta", str(porta), "--sem-navegador"]
                    if self.codigo:
                        args.append("--celular")
                    threading.Timer(0.8, lambda: (os.chdir(ROOT), os.execv(args[0], args))).start()
                return self._json({**r, "dependencias": d, "reiniciando": bool(r["ok"] and r.get("mudou"))})
            if u.path == "/api/regra":
                from .cli import main
                main(["regra", dados["texto"]])
                return self._json({"ok": True})
            return self._erro("não encontrado", 404)
        except yaml.YAMLError as e:
            return self._erro(f"YAML com erro: {e}")
        except (ValueError, KeyError, SystemExit) as e:
            return self._erro(str(e))


def _iniciar_seguro(nome: str, acao: str) -> str:
    """Para as automações: espera a tarefa do projeto terminar em vez de falhar."""
    for _ in range(120):
        if not _job_do_projeto(nome):
            return iniciar(nome, acao)
        time.sleep(5)
    return "projeto ocupado"


def _ir_para_python_do_app() -> None:
    """Aberto pelo Python antigo do Mac, mas o Python do app (.venv) já existe e está completo: troca para ele."""
    from . import atualizar as _at, instalar_fala
    if instalar_fala.no_python_do_app() or os.environ.get("DIVINE_SEM_VENV") == "1":
        return
    py = _at.python_do_app(ROOT)
    if py == sys.executable or not instalar_fala._ok_import(py, "PIL, numpy, yaml"):
        return
    print(f"  Abrindo no Python do Divine Studio ({py})", flush=True)
    os.execv(py, [py, "-m", "divine_studio", *sys.argv[1:]])


def rodar(porta: int = 8765, abrir: bool = True, celular: bool = False) -> None:
    _ir_para_python_do_app()
    try:                                   # kit de sons virais (cria os que faltam, rápido)
        from .config import ROOT as _R, load as _L
        from .sfx_viral import garantir
        garantir(_R / _L("sfx")["pasta"])
    except Exception as e:
        print(f"  aviso: kit de sons virais não criado ({e})")
    PROJETOS.mkdir(exist_ok=True)
    Painel.codigo = codigo_celular() if celular else None
    try:                                   # automações (caixa de entrada, postar no horário, métricas, radar)
        from . import automacoes, entrada
        entrada.garantir_pasta_local()
        automacoes.iniciar_vigia(iniciar=lambda nome, acao: _iniciar_seguro(nome, acao))
    except Exception as e:
        print(f"  aviso: automações desligadas ({e})")
    srv = ThreadingHTTPServer(("0.0.0.0" if celular else "127.0.0.1", porta), Painel)
    manter_acordado()
    url = f"http://127.0.0.1:{porta}"
    print(f"Painel do Divine Studio em {url}  (Ctrl+C para fechar)")
    if celular:
        print("\n  iPhone: abra no Safari (ou aponte a câmera para o QR em 📱 iPhone, no painel do Mac)")
        for e in enderecos(porta):
            print(f"    {e['url']}   {e['onde']}")
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
