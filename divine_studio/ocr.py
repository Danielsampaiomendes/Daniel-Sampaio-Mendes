"""OCR da legenda queimada (caso George: ele grava com legenda do app no terço inferior).

Lê a faixa da legenda a cada `passo` segundos com o Tesseract, junta quadros com o mesmo texto e devolve
palavras com tempo (distribuído pelo tamanho de cada palavra dentro do trecho), no mesmo formato da transcrição.
Mac: brew install tesseract tesseract-lang.   Uso no projeto: texto_da_fala: ocr
"""
from __future__ import annotations

import difflib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .ingest import probe, rodar


def disponivel() -> bool:
    return shutil.which("tesseract") is not None


def _ler_quadro(png: Path) -> str:
    r = subprocess.run(["tesseract", str(png), "stdout", "-l", "por", "--psm", "6"], capture_output=True, text=True)
    t = re.sub(r"[^\wÀ-ÿ.,!?:;'\" -]+", " ", r.stdout.replace("\n", " "))
    return re.sub(r"\s+", " ", t).strip()


def trechos(leituras: list, similaridade: float = 0.8) -> list:
    """[(t, texto)] -> [(inicio, fim, texto)] juntando leituras parecidas e ignorando as vazias."""
    out = []
    for t, txt in leituras:
        if len(txt) < 2:
            if out and out[-1][3]:
                out[-1][3] = False      # fecha o trecho aberto
            continue
        if out and out[-1][3] and difflib.SequenceMatcher(None, out[-1][2].lower(), txt.lower()).ratio() >= similaridade:
            out[-1][1] = t
            if len(txt) > len(out[-1][2]):
                out[-1][2] = txt        # fica com a leitura mais completa
        else:
            if out and out[-1][3]:
                out[-1][3] = False
            out.append([t, t, txt, True])
    return [(a, b, txt) for a, b, txt, _ in out]


def palavras_dos_trechos(trs: list, passo: float) -> list:
    pal = []
    for a, b, txt in trs:
        ws = txt.split()
        fim = b + passo
        total = sum(len(w) + 1 for w in ws) or 1
        t = a
        for w in ws:
            d = (fim - a) * (len(w) + 1) / total
            pal.append({"texto": w, "inicio": round(t, 3), "fim": round(t + d * 0.9, 3), "conf": 0.8})
            t += d
    return pal


def ler_legenda_queimada(arquivo: Path, pasta_cache: Path, faixa: tuple = (0.70, 0.88), passo: float = 0.4) -> list:
    """faixa: (topo, base) da legenda queimada em fração da altura do bruto."""
    if not disponivel():
        raise SystemExit("OCR precisa do Tesseract (Mac: brew install tesseract tesseract-lang). "
                         "Sem ele, use a transcrição da fala (tire texto_da_fala: ocr do projeto).")
    pasta_cache.mkdir(parents=True, exist_ok=True)
    cache = pasta_cache / f"{Path(arquivo).stem}_ocr.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))["palavras"]
    p = probe(Path(arquivo))
    y0, y1 = faixa
    with tempfile.TemporaryDirectory() as tmp:
        rodar(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(arquivo), "-vf",
               f"fps={1 / passo},crop=iw:ih*{y1 - y0}:0:ih*{y0},format=gray,scale=iw*1.5:-2,"
               f"eq=contrast=1.6", f"{tmp}/q%05d.png"])
        quadros = sorted(Path(tmp).glob("q*.png"))
        print(f"  OCR de {len(quadros)} quadros da legenda queimada…", flush=True)
        leituras = [(k * passo, _ler_quadro(q)) for k, q in enumerate(quadros)]
    pal = palavras_dos_trechos(trechos(leituras), passo)
    cache.write_text(json.dumps({"arquivo": str(arquivo), "duracao": p["duracao"], "palavras": pal}, indent=1,
                                ensure_ascii=False), encoding="utf-8")
    return pal
