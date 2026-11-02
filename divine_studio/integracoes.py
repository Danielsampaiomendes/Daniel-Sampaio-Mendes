"""Integrações com ferramentas de IA externas.

- Quadro do vídeo: tira um quadro (PNG em alta) no segundo escolhido, para levar ao Higgsfield (movimento de câmera,
  perspectiva, b-roll a partir de foto), ao Nano Banana ou ao Canva. O resultado volta para bruto/ pelo envio normal.
- Nano Banana (Google, modelo de imagem do Gemini): com GEMINI_API_KEY no Mac, edita a imagem direto do app
  (trocar fundo, melhorar luz, criar capa) e salva o resultado em bruto/. Modelo em config/integracoes.yaml.
- Higgsfield, ElevenLabs e outros: sem API ligada aqui; o app prepara o quadro/trecho e você importa o resultado.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from .config import load


def _cfg() -> dict:
    try:
        return load("integracoes")
    except Exception:
        return {}


def quadro(video: Path, t: float, destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, t):.3f}", "-i", str(video), "-frames:v", "1",
                        str(destino)], capture_output=True, text=True)
    if r.returncode != 0 or not destino.exists():
        raise SystemExit("Não consegui tirar o quadro: " + r.stderr[-300:])
    return destino


def nano_banana_ok() -> tuple:
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return True, ""
    return False, ("Para usar o Nano Banana: crie uma chave em aistudio.google.com (Get API key) e rode no Terminal "
                   "export GEMINI_API_KEY=sua-chave antes de abrir o Divine Studio.")


def nano_banana(imagem: Path, pedido: str, destino: Path) -> Path:
    """Edita a imagem com o modelo de imagem do Gemini (Nano Banana) e salva o PNG em destino."""
    ok, motivo = nano_banana_ok()
    if not ok:
        raise SystemExit(motivo)
    chave = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    modelo = (_cfg().get("nano_banana") or {}).get("modelo", "gemini-2.5-flash-image")
    estilo = (_cfg().get("nano_banana") or {}).get("estilo", "")
    mime = "image/png" if imagem.suffix.lower() == ".png" else "image/jpeg"
    corpo = {"contents": [{"parts": [
        {"text": f"{pedido}. {estilo}".strip()},
        {"inline_data": {"mime_type": mime, "data": base64.b64encode(imagem.read_bytes()).decode()}}]}]}
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent",
        data=json.dumps(corpo).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": chave},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"O Google recusou o pedido ({e.code}): {e.read()[:300].decode(errors='ignore')}")
    except urllib.error.URLError:
        raise SystemExit("Sem conexão com o Google.")
    for cand in resp.get("candidates") or []:
        for parte in (cand.get("content") or {}).get("parts") or []:
            dado = parte.get("inline_data") or parte.get("inlineData")
            if dado and dado.get("data"):
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_bytes(base64.b64decode(dado["data"]))
                return destino
    texto = " ".join(p.get("text", "") for c in resp.get("candidates") or [] for p in (c.get("content") or {}).get("parts") or [])
    raise SystemExit("O Nano Banana não devolveu imagem" + (f": {texto[:200]}" if texto else "."))


def nome_saida(prefixo: str, ext: str = ".png") -> str:
    return f"{prefixo}_{time.strftime('%Y%m%d-%H%M%S')}{ext}"


def catalogo() -> list:
    return _cfg().get("ferramentas") or []
