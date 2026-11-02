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


def test_anuncio_roteiro_copy_e_compliance():
    from divine_studio import anuncios
    p = {"titulo": "Endolaser nos braços", "anuncio": {"objetivo": "mensagens"}}
    r = anuncios.roteiro(p)
    assert len(r["versoes"]) == 3 and all(len(v["hook"]) in (1, 2) for v in r["versoes"])
    assert r["fechamento"]["cta"].startswith("Enviar mensagem")
    vs = anuncios.copy(p)
    assert [v["variacao"] for v in vs] == ["A", "B", "C"] and all(len(v["titulo"]) <= 40 for v in vs)
    assert all("CRM/SP 186.470" in v["texto_principal"] and "variam" in v["texto_principal"] for v in vs)
    assert anuncios.revisar_copy(p, vs) == []
    q = {"anuncio": {"servico": "CO2"}}
    anuncios.preparar(q)
    assert q["posicao_texto"] == "topo" and q["fechamento"]["cta"] == "Saiba mais ›"


def test_atencao_acha_trecho_parado_e_propoe_efeito(tmp_path):
    import numpy as np
    from divine_studio import atencao

    class C:
        def __init__(self, t0, nome="msg"):
            self.t0, self.nome = t0, nome

    class Plano:
        inicio_fechamento = 14.0
        camadas = [C(0.1, "hook_titulo"), C(2.0), C(4.0)]          # nada novo de 4 a 14 s
        efeitos_auto = []
    v = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=64x112:r=10:d=14",
                    "-c:v", "libx264", str(v)], check=True)
    voz = np.zeros((48000 * 14, 2), np.float32)
    voz[: 48000 * 6] = 0.3
    r = atencao.analisar(Plano(), {}, voz, v)
    assert r["zonas"] and r["zonas"][0]["ini"] >= 5 and r["zonas"][0]["acao"]["tipo"] in ("zoom_batida", "luz_dourada")
    assert not r["inicio_fraco"]


def test_efeitos_caem_na_batida_e_inserts_da_fala(monkeypatch, tmp_path):
    from divine_studio import efeitos, biblioteca
    bt = ritmo.batida({})
    assert abs(bt - 60 / 84) < 1e-6
    for e in ritmo.planejar({"ritmo": "viral"}, {"nome": "V1"}, 24.0)[1:-1]:
        assert abs(e["inicio"] / bt - round(e["inicio"] / bt)) < 0.02
    foto = tmp_path / "assets" / "tecnologias" / "endolaser.jpg"
    foto.parent.mkdir(parents=True)
    from PIL import Image
    Image.new("RGB", (40, 30)).save(foto)
    monkeypatch.setattr(biblioteca, "ROOT", tmp_path)
    monkeypatch.setattr("divine_studio.config.ROOT", tmp_path)
    fala = [{"texto": "o", "inicio": 1.0}, {"texto": "Endolaser,", "inicio": 3.2}, {"texto": "funciona", "inicio": 3.8}]
    ins = efeitos.inserts_da_fala({"_fala": fala, "ritmo": "viral"}, [], 20.0)
    assert len(ins) == 1 and ins[0]["inicio"] == 3.2 and ins[0]["tipo"] == "insert_foto"
