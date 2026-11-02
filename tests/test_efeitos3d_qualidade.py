"""Efeitos 3D e espaciais, câmera elegante e qualidade (estabilizar, upscale)."""
import shutil
import subprocess

import numpy as np
import pytest

from divine_studio import efeitos, efeitos3d, qualidade
from divine_studio.fonts import combinacao


def _cena(W=216, H=384):
    return efeitos._cena_referencia(W, H)


def test_coeficientes_levam_os_cantos_certos():
    saida = [(0, 0), (100, 0), (100, 200), (0, 200)]
    entrada = [(10, 5), (90, 8), (95, 190), (5, 195)]
    a, b, c, d, e, f, g, h = efeitos3d.coeficientes(saida, entrada)
    for (x, y), (u, v) in zip(saida, entrada):
        k = g * x + h * y + 1
        assert abs((a * x + b * y + c) / k - u) < 1e-6 and abs((d * x + e * y + f) / k - v) < 1e-6


@pytest.mark.parametrize("tipo", list(efeitos3d.EFEITOS))
def test_cada_efeito_3d_muda_o_quadro_so_dentro_do_tempo(tipo):
    q = _cena()
    f = efeitos.QUADRO[tipo]({"tipo": tipo, "inicio": 1.0, **efeitos3d.EXEMPLOS[tipo]}, combinacao("O1"), 216, 384, 10)
    assert np.array_equal(f(q, 0.5), q)                                    # antes do início: intacto
    meio = 1.0 + min(efeitos3d.MOMENTO_AMOSTRA[tipo], efeitos3d.DURACAO[tipo] * 0.5)
    for t in np.arange(1.0, meio, 0.1):
        f(q, float(t))
    r = f(q, meio)
    assert r.shape == q.shape and r.dtype == np.uint8
    assert not np.array_equal(r, q), tipo                                  # no meio: mudou
    assert np.array_equal(f(q, 1.0 + efeitos3d.DURACAO[tipo] + 0.5), q)   # depois: intacto


def test_camera_elegante_nunca_mostra_borda_preta():
    q = np.full((384, 216, 3), 200, np.uint8)
    for direcao in ("direita", "esquerda", "frente", "cima"):
        f = efeitos3d.camera_elegante({"inicio": 0.0, "duracao": 5.0, "direcao": direcao, "intensidade": 2.0},
                                      None, 216, 384, 10)
        for t in np.linspace(0, 5, 11):
            assert f(q, float(t)).min() > 150, (direcao, t)


def test_camera_continua_muda_de_direcao_a_cada_corte():
    q = _cena()
    f = efeitos3d.camera_continua(12.0, [4.0, 8.0])
    a, b = f(q, 3.0), f(q, 7.0)
    assert not np.array_equal(a, q) and not np.array_equal(a, b)


def test_efeitos_3d_no_catalogo_da_linha_do_tempo():
    cat = {c["tipo"]: c for c in efeitos.catalogo()}
    for tipo in efeitos3d.EFEITOS:
        assert tipo in cat and cat[tipo]["nome"] and cat[tipo]["duracao"] == efeitos3d.DURACAO[tipo]
        assert efeitos.amostra(tipo).size == (270, 480)


def test_opcoes_de_qualidade():
    assert qualidade.opcoes({"qualidade": "maxima"}, {}) == qualidade.MAXIMA
    assert qualidade.opcoes({}, {"qualidade": {"estabilizar": True, "denoise": False}}) == {"estabilizar": True}
    assert qualidade.opcoes({}, {}) == {}


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="sem ffmpeg")
def test_preparar_estabiliza_sobe_resolucao_e_usa_cache(tmp_path):
    bruto = tmp_path / "treme.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=240x426:r=30:d=2",
                    "-vf", "crop=220:400:10+8*sin(t*9):10+6*cos(t*7)", "-c:v", "libx264", str(bruto)], check=True)
    ops = {"estabilizar": True, "upscale": "lanczos", "denoise": "leve"}
    r = qualidade.preparar(bruto, 0.2, 1.8, ops, (540, 960), tmp_path / "q")
    from divine_studio.ingest import probe
    p = probe(r)
    assert min(p["largura"], p["altura"]) >= 530 and abs(p["duracao"] - 1.6) < 0.15
    mt = r.stat().st_mtime
    assert qualidade.preparar(bruto, 0.2, 1.8, ops, (540, 960), tmp_path / "q") == r and r.stat().st_mtime == mt


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="sem ffmpeg")
def test_upscale_com_ia_quando_o_realesrgan_existe(tmp_path, monkeypatch):
    falso = tmp_path / "realesrgan-ncnn-vulkan"
    falso.write_text("#!/bin/sh\n# -i entrada -o saida ...: simula o upscale copiando os quadros\ncp \"$2\"/*.png \"$4\"/\n")
    falso.chmod(0o755)
    monkeypatch.setattr(qualidade, "_cfg", lambda: {"realesrgan": str(falso)})
    bruto = tmp_path / "b.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=160x284:r=10:d=1",
                    "-c:v", "libx264", str(bruto)], check=True)
    r = qualidade.preparar(bruto, 0, 1, {"upscale": "auto"}, (540, 960), tmp_path / "q")
    assert r.exists() and r.stat().st_size > 1000


# ---------------------------------------------------------------- efeitos e sons virais
from divine_studio import efeitos_viral, sfx_viral  # noqa: E402


@pytest.mark.parametrize("tipo", list(efeitos_viral.EFEITOS))
def test_cada_efeito_viral_muda_o_quadro_so_dentro_do_tempo(tipo):
    q = _cena()
    f = efeitos.QUADRO[tipo]({"tipo": tipo, "inicio": 1.0, **efeitos_viral.EXEMPLOS[tipo]}, combinacao("O1"), 216, 384, 10)
    assert np.array_equal(f(q, 0.5), q)
    r = f(q, 1.0 + efeitos_viral.MOMENTO_AMOSTRA[tipo])
    assert r.shape == q.shape and r.dtype == np.uint8 and not np.array_equal(r, q), tipo
    assert np.array_equal(f(q, 1.0 + efeitos_viral.DURACAO[tipo] + 0.5), q)


def test_giro_nunca_mostra_canto_preto():
    q = np.full((384, 216, 3), 200, np.uint8)
    f = efeitos_viral.giro({"inicio": 0.0, "duracao": 0.5}, None, 216, 384, 30)
    for t in np.linspace(0.01, 0.49, 13):
        assert f(q, float(t)).min() > 120, t


def test_kit_de_sons_virais(tmp_path):
    novos = sfx_viral.garantir(tmp_path)
    assert len(novos) == 2 * len(sfx_viral.SONS)
    assert sfx_viral.garantir(tmp_path) == []                                   # já existem: não refaz
    import wave
    with wave.open(str(tmp_path / "boom_grave_a.wav")) as w:
        assert w.getframerate() == 48000 and w.getnchannels() == 2 and w.getnframes() > 48000 * 0.5


def test_velocity_vira_rapido_lento_rapido(tmp_path):
    from divine_studio.ingest import _expandir_velocity
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=64x112:r=10:d=2",
                    "-c:v", "libx264", str(tmp_path / "a.mp4")], check=True)
    out = _expandir_velocity({"_pasta": tmp_path}, [{"arquivo": "a.mp4", "fim": 2.0, "velocity": True}])
    assert [c["velocidade"] for c in out] == [1.8, 0.4, 1.8]
    assert out[0]["inicio"] == 0 and out[-1]["fim"] == 2.0 and all("velocity" not in c for c in out)
