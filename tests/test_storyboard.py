"""Storyboard: o quadro é a edição real (igual ao render), os códigos e os pedidos de mudança."""
import json
import subprocess
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

from divine_studio import storyboard as sb
from divine_studio.compositor import Camada
from divine_studio.render import quadros_em, renderizar
from divine_studio.templates.divine import Plano

W, H = 180, 320


def _base(tmp: Path) -> Path:
    arq = tmp / "base.mov"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=s={W}x{H}:r=30:d=4",
                    "-c:v", "libx264", "-g", "1", "-crf", "1", "-pix_fmt", "yuv444p", str(arq)], check=True)
    return arq


def _plano() -> Plano:
    img = Image.new("RGBA", (120, 40), (204, 189, 145, 255))
    guardado = {}

    def congela(q, t):                          # efeito que guarda estado, como o congelar
        if 1.0 <= t <= 2.0:
            guardado.setdefault("q", q.copy())
            return guardado["q"]
        guardado.clear()
        return q
    return Plano(camadas=[Camada(img, 30, 60, 0.5, 3.0, nome="msg0_titulo", texto="Pele com / *viço.*")],
                 inicio_fechamento=3.2, duracao_total=4.0, hook_fim=0.5, efeitos_quadro=[congela])


def test_quadro_do_storyboard_igual_ao_render(tmp_path):
    base = _base(tmp_path)
    wav = tmp_path / "mix.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "4",
                    str(wav)], check=True)
    master = tmp_path / "master.mov"
    renderizar(base, _plano(), W, H, 30, wav, master, 4.0)
    tempos = [0.2, 1.5, 2.5, 3.5]
    sbq = quadros_em(base, _plano(), tempos, W, H, 4.0, amostra=10)
    for t in tempos:
        r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(master), "-vf", f"select=eq(n\\,{int(round(t * 30))})",
                            "-vframes", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True)
        real = np.frombuffer(r.stdout, np.uint8).reshape(H, W, 3).astype(int)
        dif = np.abs(real - sbq[t].astype(int)).mean()
        assert dif < 6, (t, dif)                 # só a compressão do master separa os dois


def test_codigos_e_cenas():
    p = {"_base_meta": {"clipes": [{"inicio_base": 0}, {"inicio_base": 2.4}]}, "efeitos": [], "versoes": [{"nome": "V1"}]}
    plano = _plano()
    plano.camadas.append(Camada(Image.new("RGBA", (10, 10)), 0, 0, 0.0, 0.5, nome="hook0_titulo", texto="Gancho"))
    moms = sb.momentos(plano, p)
    cs = sb.cenas(moms, plano, p)
    cods = [m["codigo"] for c in cs for m in c["momentos"]]
    assert cods[0] in ("1", "1A") and len(set(cods)) == len(cods)
    assert any(m["tipo"] == "corte" for c in cs for m in c["momentos"])
    assert cs[-1]["momentos"][-1]["tipo"] == "fechamento"


def _projeto(tmp: Path) -> Path:
    pasta = tmp / "proj"
    (pasta / "trabalho").mkdir(parents=True)
    (pasta / "projeto.yaml").write_text(yaml.safe_dump({
        "titulo": "T", "mensagens": [{"titulo": "Pele com / *viço.*"}],
        "efeitos": [{"tipo": "zoom_digital", "inicio": 4.0}],
        "versoes": [{"nome": "V1", "hook_id": "X", "hook": None}]}, allow_unicode=True), encoding="utf-8")
    dados = {"versao": "V1", "hook": [{"titulo": "Essa luz", "duracao": 2.0}, {"titulo": "é a *mira.*", "duracao": 2.0}],
             "cenas": [{"numero": 1, "momentos": [
                 {"codigo": "1A", "t": 0.0, "fim": 2.0, "tipo": "hook", "origem": {"campo": "hook", "versao": 0, "k": 0}},
                 {"codigo": "1B", "t": 2.0, "fim": 4.0, "tipo": "hook", "origem": {"campo": "hook", "versao": 0, "k": 1}}]},
                 {"numero": 2, "momentos": [
                     {"codigo": "2A", "t": 4.2, "fim": 6.0, "tipo": "mensagem", "origem": {"campo": "mensagens", "k": 0}},
                     {"codigo": "2B", "t": 4.0, "fim": 6.0, "tipo": "efeito", "origem": {"campo": "efeitos", "k": 0}}]}]}
    (pasta / "trabalho" / "storyboard_V1.json").write_text(json.dumps(dados), encoding="utf-8")
    return pasta


def test_pedidos_mudam_o_projeto(tmp_path):
    pasta = _projeto(tmp_path)
    r = sb.responder(pasta, '1B: troca o título por "é *ciência.*"; 2A: entra mais cedo; '
                            '2B: troca o efeito por flash; 9: tira; 2A: blá', "V1")
    assert len(r["aplicados"]) == 3, r
    assert {x["codigo"] for x in r["nao_entendi"]} == {"9", "2A"}
    d = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8"))
    assert d["versoes"][0]["hook"][1]["titulo"] == "é *ciência.*" and "hook_id" not in d["versoes"][0]
    assert d["mensagens"][0]["inicio"] == 3.7
    assert d["efeitos"][0]["tipo"] == "flash"
    assert list((pasta / "trabalho").glob("projeto.yaml.antes-do-storyboard-*"))      # nada se perde


def test_efeito_sem_texto_nao_muda_nada(tmp_path):
    pasta = _projeto(tmp_path)
    antes = (pasta / "projeto.yaml").read_text(encoding="utf-8")
    r = sb.responder(pasta, '2B: troca o título por "x"', "V1")
    assert not r["aplicados"] and r["avisos"]
    assert (pasta / "projeto.yaml").read_text(encoding="utf-8") == antes


def test_aprovado(tmp_path):
    pasta = _projeto(tmp_path)
    assert sb.responder(pasta, "Tudo aprovado. Finaliza.", "V1")["aprovado"]
    assert (pasta / "trabalho" / "storyboard_aprovado.json").exists()
    assert not sb.eh_aprovacao("ainda não está aprovado?")
