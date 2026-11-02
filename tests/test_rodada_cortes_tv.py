"""Cortes de vídeo longo, conversa sobre a edição, tela dividida, Divine TV, crescimento e integrações."""
import datetime as dt
import json
import shutil
import subprocess

import pytest
import yaml

from divine_studio import aprendizado, carrossel, cortes_longos, crescimento, feedback, painel, ritmo
from divine_studio.templates import react


def _t(arq, a, b, txt):
    return ({"arquivo": arq}, a, b, txt)


def test_cortes_comecam_pela_frase_forte_e_espalham_pelo_video():
    frases = []
    t = 0.0
    for k in range(40):
        txt = "Você sabe qual é o erro mais comum?" if k in (10, 25) else "Aqui eu explico mais um detalhe do tratamento."
        frases.append(_t("a.mp4", t, t + 4.0, txt))
        t += 4.2
    pecas = cortes_longos.planejar(frases)
    tipos = [p[0] for p in pecas]
    assert tipos.count("curto") == 3 and tipos.count("medio") == 2 and tipos.count("longo") == 1
    assert "melhores" in tipos and "stories" in tipos
    curtos = [p for p in pecas if p[0] == "curto"]
    assert any("erro mais comum" in p[2][0][3] for p in curtos)                 # um curto abre com o gancho
    inicios = sorted(p[2][0][1] for p in curtos)
    assert len(set(round(i) for i in inicios)) == 3                            # sem repetir o mesmo trecho
    for p in pecas:
        d = sum(x[2] - x[1] for x in p[2])
        if p[0] == "curto":
            assert 12 <= d <= 25


def test_pontuacao_de_frase():
    assert cortes_longos.pontuar("Você sabe por que 90% erra?", 3) > cortes_longos.pontuar("é isso aí", 3)
    assert cortes_longos.pontuar("tá", 0.5) < 1


@pytest.fixture
def projetos(tmp_path, monkeypatch):
    p = tmp_path / "projetos"
    p.mkdir()
    for m in (painel, aprendizado):
        monkeypatch.setattr(m, "PROJETOS", p)
    monkeypatch.setattr(crescimento, "ARQ", p / ".crescimento.json")
    monkeypatch.setattr(feedback, "_registrar_regra", lambda *a: None)
    feedback._CACHE["v"] = None
    return p


def _projeto(projetos, nome, extra=None):
    pasta = projetos / nome
    for s in ("bruto", "saida", "trabalho"):
        (pasta / s).mkdir(parents=True)
    carrossel.salvar(pasta, {"titulo": "Teste", "formato": "reels", **(extra or {})})
    return pasta


def test_conversa_app_x_voce_vira_ajuste_no_proximo(projetos):
    pasta = _projeto(projetos, "p1")
    (pasta / "trabalho" / "nota_V1.json").write_text(json.dumps(
        {"notas": {"hook": 9, "retenção": 6, "leitura": 8}, "dicas": ["mudança visual a cada 3.2s"], "media": 7.7,
         "duracao": 52, "efeitos": 0}))
    app = feedback.opiniao_app(pasta, "V1")
    assert app["tem"] and app["viraliza"] and any("20 a 30 s" in s for s in app["sugestoes"])
    r = feedback.registrar(pasta, "V1", ["mais_efeitos"], "achei meio lento e o som baixo", 3)
    assert {"mais_efeitos", "mais_rapido", "mais_sons"} <= set(r["reacoes"])
    assert r["ajustes"]["intervalo_efeitos"] < 1 and r["ajustes"]["ganho_sons_db"] > 0
    pub = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8"))["publicacoes"][0]
    assert pub["feedback"]["nota_usuario"] == 3 and pub["feedback"]["nota_app"] == 7.7
    a_menos = ritmo.planejar({"ritmo": "viral"}, {"nome": "V1"}, 30.0)
    feedback._CACHE["v"] = {"intervalo_efeitos": 1.0}
    a_normal = ritmo.planejar({"ritmo": "viral"}, {"nome": "V1"}, 30.0)
    assert len(a_menos) >= len(a_normal)                                       # mais efeitos depois da opinião
    r2 = feedback.registrar(pasta, "V2", ["nao_viraliza"])
    assert r2["concordam"] is None                                             # V2 sem nota do app


def test_tela_dividida_escolhe_o_layout_pelo_formato():
    assert react.layout({"_ar_ref": 9 / 16}) == "cabecinha"
    assert react.layout({"_ar_ref": 16 / 9}) == "dividida" and react._div_frac({"_ar_ref": 16 / 9}) == 0.5
    assert react._div_frac({"_ar_ref": 1.0}) == 0.6                            # 60% vídeo, 40% você
    assert react.layout({"_ar_ref": 9 / 16, "layout": "dividida"}) == "dividida"
    assert react.tamanho_base({"_ar_ref": 9 / 16}, 1080, 1920)[0] == react._lado_cabecinha(1080)


def test_divine_tv_pega_videos_de_tv_e_os_marcados(projetos):
    tv = _projeto(projetos, "tv1", {"template": "tv", "formato": "tv"})
    (tv / "saida" / "a_TV_.mp4").write_bytes(b"x")
    (tv / "saida" / "a_TV_PREVIA.mp4").write_bytes(b"x")
    r = _projeto(projetos, "r1")
    (r / "saida" / "b_V1_.mp4").write_bytes(b"x")
    aprendizado.marcar(r, "V1", arquivo="saida/b_V1_.mp4", na_tv=True)
    assert sorted(i["arquivo"] for i in painel.canal_tv()) == ["saida/a_TV_.mp4", "saida/b_V1_.mp4"]


def test_crescimento_projecao_metas_e_plano(projetos):
    hoje = dt.date.today()
    for k, n in enumerate([1000, 1010, 1025, 1040]):
        crescimento.registrar_seguidores("dvmedicalspa", n, (hoje - dt.timedelta(days=9 - 3 * k)).isoformat())
    pr = crescimento.projecao("dvmedicalspa")
    assert pr["tem"] and pr["atual"] == 1040 and pr["por_dia"] > 3 and pr["em_30"] > 1100
    pasta = _projeto(projetos, "p2")
    aprendizado.marcar(pasta, "V1", status="postado", data_postagem=hoje.isoformat())
    req = {x["item"].split(":")[0]: x["ok"] for x in crescimento.requisitos("dvmedicalspa")}
    assert req["Reels na semana"] is False and "Dias com Stories" in req
    crescimento.marcar_stories("dvmedicalspa")
    plano = [x["acao"] for x in crescimento.plano_do_dia("dvmedicalspa")]
    assert not any("Stories hoje" in a for a in plano)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="sem ffmpeg")
def test_quadro_para_ferramenta_externa(tmp_path, monkeypatch):
    from divine_studio import integracoes
    v = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=160x284:r=10:d=2", "-c:v", "libx264",
                    str(v)], check=True)
    q = integracoes.quadro(v, 1.0, tmp_path / "q.png")
    assert q.exists() and q.stat().st_size > 1000
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert integracoes.nano_banana_ok()[0] is False
    with pytest.raises(SystemExit):
        integracoes.nano_banana(q, "trocar fundo", tmp_path / "r.png")
    assert any(f["nome"].startswith("Higgsfield") for f in integracoes.catalogo())
