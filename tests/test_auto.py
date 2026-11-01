"""Testes da edição automática (montagem do projeto.yaml a partir dos brutos)."""
import subprocess

import pytest
import yaml

from divine_studio import auto, compliance


@pytest.mark.parametrize("titulo,chave", [
    ("Laser de CO2 no corpo", "co2"), ("Endolaser nos braços", "endolaser"), ("CMSlim 12 Tesla", "cmslim"),
    ("Spa pedras quentes", "spa"), ("Queda de cabelo", "cabelo"), ("Reposição hormonal com pellets", "pellets"),
    ("Um vídeo qualquer", "padrao")])
def test_tema_reconhecido(titulo, chave):
    assert auto.tema(titulo)[0] == chave


def test_roteiros_passam_no_revisor():
    from divine_studio.config import load
    cfg = load("roteiros")
    for chave, r in list(cfg["temas"].items()) + [("padrao", cfg["padrao"])]:
        textos = [r.get("selo", ""), r.get("fechamento", "")] + \
                 [x for m in r.get("mensagens", []) for x in (m.get("titulo"), m.get("apoio")) if x]
        erros = [a for a in compliance.revisar({"legenda": ""}, textos) if a.nivel == "erro"]
        assert not erros, (chave, [a.linha() for a in erros])
    assert not [a for a in compliance.revisar({"legenda": ""}, cfg["cta_antecipado"]) if a.nivel == "erro"]


def test_destaque_e_quebra_sem_conectivo():
    assert auto._destacar("Ele estimula o colágeno no seu tempo.") == "Ele estimula / o colágeno no *seu tempo*"
    assert auto._destacar("A pele responde.") == "A pele *responde*"


def _pal(texto):
    return [{"texto": w, "inicio": k * 0.3, "fim": k * 0.3 + 0.25} for k, w in enumerate(texto.split())]


def test_mensagens_da_fala_sem_muleta_take_cta_e_promessa():
    fala = ("O laser de CO2 ele O laser de CO2 trabalha por dentro da pele. hum "
            "Resultado garantido em uma sessão. Ele estimula o colágeno no seu tempo. Agende sua avaliação.")
    ms = auto.mensagens_da_fala(_pal(fala), "co2")
    titulos = " ".join(m["titulo"] for m in ms).lower()
    assert "hum" not in titulos and "garantido" not in titulos and "agende" not in titulos
    assert ms[0]["titulo"].startswith("O laser de CO2 / trabalha")
    assert ms[0]["na_fala"] == "O laser de CO2"


@pytest.fixture
def projeto(tmp_path):
    pasta = tmp_path / "2026-11-01_co2"
    (pasta / "bruto").mkdir(parents=True)
    for k in range(2):
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=160x284:r=30:d=25",
                        "-c:v", "libx264", "-preset", "ultrafast", str(pasta / "bruto" / f"IMG_000{k}.mov")],
                       check=True)
    modelo = yaml.safe_load((auto.Path(auto.__file__).parent / "modelo_projeto.yaml").read_text(encoding="utf-8"))
    modelo["titulo"] = "Laser de CO2 no corpo"
    modelo["_pasta"] = pasta
    return modelo


def test_monta_projeto_sem_fala(projeto):
    p = auto.montar(projeto)
    assert [c["arquivo"] for c in p["clipes"]] == ["bruto/IMG_0000.mov", "bruto/IMG_0001.mov"]
    assert all(c["mudo"] and c["velocidade"] == 0.85 for c in p["clipes"])
    dur = sum((c["fim"] - c["inicio"]) / c["velocidade"] for c in p["clipes"])
    assert dur == pytest.approx(30, abs=1.5)                    # miolo até ~30 s
    assert p["audio"]["original"] is False and not p["legendas"] and not p["corte_limpo"]
    assert p["selo"] == "LASER DE CO2" and len(p["mensagens"]) == 3
    assert [v["hook"] for v in p["versoes"]] == ["auto", "auto", "auto"]   # exemplos do modelo trocados
    assert "legenda" not in p                                             # a do modelo sai; a certa é gerada


def test_mantem_o_que_foi_preenchido_a_mao(projeto):
    projeto["clipes"] = [{"arquivo": "bruto/IMG_0001.mov", "inicio": 2, "fim": 9, "foco": [0.3, 0.3]}]
    projeto["versoes"] = [{"nome": "V1", "hook_id": "A-H18"}]
    projeto["autorizacao_imagem"] = "sim"
    p = auto.montar(projeto, template="george")
    manual = next(c for c in p["clipes"] if c["arquivo"] == "bruto/IMG_0001.mov")
    assert manual["foco"] == [0.3, 0.3] and p["template"] == "george" and p["autorizacao_imagem"] == "sim"
    assert p["versoes"][0] == {"nome": "V1", "hook_id": "A-H18"} and len(p["versoes"]) == 3


def test_tv_uma_versao_com_tratamento(projeto):
    p = auto.montar(projeto, template="tv")
    assert p["formato"] == "tv" and [v["nome"] for v in p["versoes"]] == ["TV"]
    assert p["tv"]["tratamento"] and len(p["mensagens"]) >= 3


def test_sem_brutos_avisa(tmp_path):
    (tmp_path / "bruto").mkdir()
    with pytest.raises(SystemExit):
        auto.montar({"_pasta": tmp_path, "titulo": "x"})
