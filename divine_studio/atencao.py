"""Atenção prevista ao longo do vídeo: onde a pessoa tende a sair, por quê, e como resolver.

Para cada meio segundo, o app olha três coisas: algo novo na tela (texto, corte, efeito), movimento na imagem e fala.
Trecho longo sem nada novo, imagem parada e silêncio = risco de queda. Cada risco vem com uma proposta que dá para
aplicar com um toque (efeito no ponto certo). Depois de postar, o tempo médio assistido do Instagram confirma ou não.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

PASSO = 0.5


def _movimento(video: Path, dur: float) -> np.ndarray:
    """Diferença média entre quadros (2 por segundo, em miniatura): 0 = parado, 1 = muito movimento."""
    w, h = 48, 86
    try:
        r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps={1 / PASSO},scale={w}:{h},format=gray",
                            "-f", "rawvideo", "-"], capture_output=True, timeout=120)
        q = np.frombuffer(r.stdout, np.uint8)
        n = len(q) // (w * h)
        if n < 2:
            return np.zeros(int(dur / PASSO) + 1)
        q = q[: n * w * h].reshape(n, h, w).astype(np.float32)
        d = np.concatenate([[0.0], np.abs(np.diff(q, axis=0)).mean(axis=(1, 2))])
        return np.clip(d / 12.0, 0, 1)
    except (subprocess.SubprocessError, OSError):
        return np.zeros(int(dur / PASSO) + 1)


def analisar(plano, projeto: dict, voz: np.ndarray | None, base_video: Path, sr: int = 48000) -> dict:
    fim = float(plano.inicio_fechamento)
    n = max(1, int(fim / PASSO))
    eventos = sorted({round(c.t0, 2) for c in plano.camadas if c.t0 < fim
                      and not c.nome.startswith(("grad", "moldura", "legenda", "barra"))}
                     | {round(float(c.get("inicio_base", 0)), 2) for c in (projeto.get("_base_meta") or {}).get("clipes", [])}
                     | {round(float(e.get("inicio", 0)), 2) for e in (projeto.get("efeitos") or []) + (getattr(plano, "efeitos_auto", None) or [])})
    mov = _movimento(base_video, fim)
    fala = np.zeros(n)
    if voz is not None and len(voz):
        mono = np.abs(voz).mean(axis=1) if voz.ndim == 2 else np.abs(voz)
        for k in range(n):
            a, b = int(k * PASSO * sr), int((k + 1) * PASSO * sr)
            fala[k] = float(mono[a:b].mean()) if b <= len(mono) else 0.0
        fala = np.clip(fala / (np.percentile(fala, 90) + 1e-6), 0, 1)
    curva, motivo = [], []
    for k in range(n):
        t = k * PASSO
        desde = min([t - e for e in eventos if e <= t + 0.01] or [t + 3])
        novidade = float(np.exp(-max(0.0, desde) / 1.6))
        m = float(mov[k]) if k < len(mov) else 0.0
        f = float(fala[k])
        curva.append(round(0.5 * novidade + 0.25 * m + 0.25 * f, 3))
        motivo.append((desde, m, f))
    zonas, k = [], 1
    while k < n:
        if curva[k] < 0.32:
            j = k
            while j < n and curva[j] < 0.32:
                j += 1
            ini, fim_z = k * PASSO, j * PASSO
            if fim_z - ini >= 2.0:
                trecho = motivo[k:j]
                sem_novidade = max(x[0] for x in trecho)
                parado = np.mean([x[1] for x in trecho]) < 0.15
                silencio = np.mean([x[2] for x in trecho]) < 0.15 and voz is not None
                causas = []
                if sem_novidade >= 2.5:
                    causas.append(f"{sem_novidade:.0f} s sem nada novo na tela")
                if parado:
                    causas.append("imagem quase parada")
                if silencio:
                    causas.append("pausa na fala")
                meio = round(ini + min(1.2, (fim_z - ini) / 2), 1)
                if silencio:
                    proposta = "cortar a pausa (ligue o corte limpo) ou cobrir com uma frase na tela"
                    acao = {"tipo": "zoom_batida", "inicio": meio}
                elif parado:
                    proposta = f"um zoom na batida em {meio:.1f} s (ou um corte para outro take)"
                    acao = {"tipo": "zoom_batida", "inicio": meio}
                else:
                    proposta = f"uma luz dourada ou um texto curto em {meio:.1f} s"
                    acao = {"tipo": "luz_dourada", "inicio": meio}
                zonas.append({"ini": ini, "fim": fim_z, "causa": ", ".join(causas) or "pouca coisa acontecendo",
                              "proposta": proposta, "acao": acao})
            k = j
        k += 1
    inicio_fraco = not any(e <= 1.0 for e in eventos)
    return {"passo": PASSO, "curva": curva, "zonas": zonas, "inicio_fraco": inicio_fraco,
            "media": round(float(np.mean(curva)), 2)}


def salvar(trabalho: Path, versao: str, dados: dict) -> None:
    (trabalho / f"atencao_{versao}.json").write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")


def ler(pasta: Path, versao: str) -> dict:
    try:
        return json.loads((pasta / "trabalho" / f"atencao_{versao}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
