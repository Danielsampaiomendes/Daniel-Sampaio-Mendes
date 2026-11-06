"""Publicação nas redes direto do app: Instagram (Reels, do arquivo do Mac) e TikTok (rascunho ou direto).

Só publica o que passa em TODAS as travas (`pode_publicar`):
  - você ligou "postar sozinho" na peça (ou tocou em "Publicar agora")
  - não é uso interno / TV / consulta / prévia / NAO-POSTAR
  - autorização de imagem resolvida
  - revisor de compliance (CFM 2.336/2023, Anvisa RDC 96/2008) sem erro, legenda incluída
  - o perfil da peça está conectado
Depois de publicar: status 'postado', link e hora gravados; as métricas entram sozinhas (automações 24h e 7d).
"""
from __future__ import annotations

import datetime as _dt
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .config import ROOT, load

PROJETOS = ROOT / "projetos"
AUTORIZADO = ("sim", "nao_aparece", "proprio")


def _cfg_ig() -> dict:
    return load("redes").get("instagram") or {}


def _pub(projeto: str, versao: str) -> tuple:
    from . import aprendizado
    pasta = PROJETOS / projeto
    d = aprendizado.ler(pasta)
    pub = next((p for p in d.get("publicacoes") or [] if p.get("versao") == versao), None)
    if pub is None:
        raise ValueError(f"{projeto} {versao}: aprove a versão antes (ela ainda não está na programação)")
    return pasta, d, pub


def redes_da(pub: dict) -> list:
    r = pub.get("redes") or [pub.get("rede") or "instagram"]
    return [x for x in r if x in ("instagram", "tiktok")]


def pode_publicar(projeto: str, versao: str, manual: bool = False) -> list:
    """Lista do que impede publicar (vazia = pode)."""
    from . import instagram, tiktok
    from .compliance import revisar
    pasta, d, pub = _pub(projeto, versao)
    motivos = []
    if not manual and not pub.get("auto_postar"):
        motivos.append("'postar sozinho' está desligado nesta peça")
    if d.get("uso_interno") or pub.get("rede") in ("tv", "consulta") or d.get("tipo") == "antes_depois":
        motivos.append("peça de uso interno (TV/consulta): nunca vai para as redes")
    arq = pub.get("arquivo") or ""
    if not arq or not (pasta / arq).exists():
        motivos.append("arquivo final não encontrado: exporte a final")
    elif "_PREVIA" in arq or "NAO-POSTAR" in arq or "autorizacao-pendente" in arq:
        motivos.append("o arquivo é prévia, NAO-POSTAR ou está com autorização pendente")
    if str(d.get("autorizacao_imagem", "pendente")).lower() not in AUTORIZADO:
        motivos.append("autorização de imagem pendente")
    erros = [a.linha() for a in revisar({**d, "_pasta": pasta}) if a.nivel == "erro"]
    if erros:
        motivos.append("revisor de compliance: " + "; ".join(erros))
    if not d.get("legenda") and not (pasta / "saida" / "legenda.txt").exists():
        motivos.append("falta a legenda do post")
    redes = redes_da(pub)
    if not redes:
        motivos.append("nenhuma rede marcada")
    if "instagram" in redes:
        conta = pub.get("conta") or instagram.conta_do_projeto(d)
        if not instagram.configurado(conta):
            motivos.append(f"Instagram @{conta} não conectado")
        elif not str(arq).lower().endswith((".mp4", ".mov")):
            motivos.append("o Instagram automático aceita vídeo (Reels); carrossel e foto: publicação assistida")
    if "tiktok" in redes and not tiktok.configurado():
        motivos.append("TikTok não conectado")
    return motivos


def _legenda(pasta: Path, d: dict) -> str:
    arq = pasta / "saida" / "legenda.txt"
    return (arq.read_text(encoding="utf-8") if arq.exists() else d.get("legenda", "")).strip()


def publicar(projeto: str, versao: str, manual: bool = False) -> dict:
    """Publica nas redes da peça. Devolve {rede: resultado}."""
    from . import aprendizado, instagram
    motivos = pode_publicar(projeto, versao, manual)
    if motivos:
        raise SystemExit("Não publiquei: " + "; ".join(motivos))
    pasta, d, pub = _pub(projeto, versao)
    arquivo = pasta / pub["arquivo"]
    legenda = _legenda(pasta, d)
    out, campos = {}, {}
    for rede in redes_da(pub):
        try:
            if rede == "instagram":
                conta = pub.get("conta") or instagram.conta_do_projeto(d)
                r = reels_instagram(arquivo, legenda, conta)
                campos.update({"link": r["link"], "media_id": r["id"], "conta": conta})
                out["instagram"] = r["link"]
            else:
                from . import tiktok
                r = tiktok.enviar(arquivo, legenda)
                campos.update({"tiktok_publish_id": r["publish_id"], "tiktok_modo": r["modo"]})
                out["tiktok"] = "rascunho enviado: abra o app TikTok e publique" if r["modo"] == "rascunho" \
                    else "publicado (privacidade conforme o app)"
        except SystemExit as e:
            out[rede] = f"erro: {e}"
    if any(not str(v).startswith("erro") for v in out.values()):
        campos.update({"status": "postado", "postado_em": _dt.datetime.now().isoformat(timespec="minutes"),
                       "postado_por": "manual" if manual else "automação"})
        aprendizado.marcar(pasta, versao, **campos)
    return out


# ---------------------------------------------------------------- Instagram Reels (arquivo local, upload resumable)
def _base(token: str) -> str:
    v = _cfg_ig().get("versao_api", "v21.0")
    return f"https://graph.instagram.com/{v}" if token.startswith("IG") else f"https://graph.facebook.com/{v}"


def _req(url: str, metodo: str = "GET", campos: dict | None = None, corpo: bytes | None = None,
         cab: dict | None = None) -> dict:
    if campos and metodo == "GET":
        url += "?" + urllib.parse.urlencode(campos)
        dados = None
    else:
        dados = corpo if corpo is not None else (urllib.parse.urlencode(campos).encode() if campos else None)
    req = urllib.request.Request(url, data=dados, method=metodo, headers=cab or {})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            msg = (json.loads(e.read()).get("error") or {}).get("message", "")
        except ValueError:
            msg = ""
        raise SystemExit(f"Instagram recusou ({e.code}): {msg or 'sem detalhe'}")
    except urllib.error.URLError:
        raise SystemExit("Sem conexão com o Instagram.")


def reels_instagram(arquivo: Path, legenda: str, conta: str | None = None) -> dict:
    """Cria o contêiner de Reels, envia o arquivo, espera processar, publica e devolve {id, link}."""
    from . import instagram
    c = instagram._credenciais(conta)
    token, uid = c["token"], c["user_id"]
    base = _base(token)
    cont = _req(f"{base}/{uid}/media", "POST", {
        "media_type": "REELS", "upload_type": "resumable", "caption": legenda[:2200],
        "share_to_feed": "true" if _cfg_ig().get("compartilhar_no_feed", True) else "false", "access_token": token})
    cid = cont.get("id")
    if not cid:
        raise SystemExit(f"Instagram não criou o contêiner: {cont}")
    uri = cont.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{_cfg_ig().get('versao_api', 'v21.0')}/{cid}"
    tam = arquivo.stat().st_size
    with open(arquivo, "rb") as f:
        _req(uri, "POST", corpo=f.read(), cab={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(tam)})
    limite = time.time() + float(_cfg_ig().get("esperar_processamento_s", 300))
    while True:
        st = _req(f"{base}/{cid}", "GET", {"fields": "status_code,status", "access_token": token})
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") in ("ERROR", "EXPIRED"):
            raise SystemExit(f"Instagram não processou o vídeo: {st.get('status')}")
        if time.time() > limite:
            raise SystemExit("O Instagram ainda está processando; tente publicar de novo em alguns minutos")
        time.sleep(5)
    pub = _req(f"{base}/{uid}/media_publish", "POST", {"creation_id": cid, "access_token": token})
    mid = pub.get("id")
    link = _req(f"{base}/{mid}", "GET", {"fields": "permalink", "access_token": token}).get("permalink", "")
    return {"id": mid, "link": link}
