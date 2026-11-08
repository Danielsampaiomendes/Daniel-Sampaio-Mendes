"""Testes do carrossel e dos formatos (Stories, Feed, TV a partir da mesma edição)."""
import zipfile

import pytest
import yaml

from divine_studio import carrossel, compliance, formatos
from divine_studio.config import load


@pytest.mark.parametrize("formula", ["lista", "mito_verdade", "metodo", "pergunta", "expectativa", "livre"])
def test_rascunho_segue_as_regras_do_carrossel(formula):
    cards = carrossel.rascunho("Laser de CO2 no corpo", formula)
    cfg = load("carrossel")
    assert cfg["min_cards"] - 1 <= len(cards) <= cfg["max_cards"]
    assert cards[0]["layout"] == "capa" and cards[-1]["layout"] == "cta"
    assert sum(1 for c in cards if c.get("pedido")) == 1                    # um pedido só
    erros = [a for a in compliance.revisar({"legenda": ""}, carrossel.textos({"cards": cards})) if a.nivel == "erro"]
    assert not erros, [a.linha() for a in erros]
    for c in cards:                                                         # sem numeração nos cards
        assert not any(t.strip()[:3].rstrip(".").isdigit() and len(t.strip()) < 4 for t in carrossel.textos({"cards": [c]}))


@pytest.mark.parametrize("estilo", ["divine", "claro", "daniel", "george", "pessoal"])
def test_todos_os_layouts_desenham(estilo):
    cards = [{"layout": l, "titulo": "Título *dourado*", "apoio": "apoio", "texto": "Um ponto por card.",
              "itens": ["a", "b"], "mito": "Mito.", "verdade": "Verdade.", "pedido": "Salva."}
             for l in carrossel.LAYOUTS]
    p = {"estilo": estilo, "cards": cards, "fontes": "O1"}
    for i in range(len(cards)):
        assert carrossel.desenhar(p, i).size == (1080, 1350)


def test_exportar_gera_pngs_zip_e_legenda(tmp_path, monkeypatch):
    monkeypatch.setattr(carrossel, "ROOT", tmp_path)          # a entrega do teste não vai para entregas/ de verdade
    p = {"tipo": "carrossel", "titulo": "Queda de cabelo", "estilo": "divine", "formula": "mito_verdade",
         "cards": carrossel.rascunho("Queda de cabelo", "mito_verdade"), "conteudo_medico": True,
         "autorizacao_imagem": "nao_aparece"}
    r = carrossel.exportar(tmp_path, p)
    assert len(r["cards"]) == len(p["cards"])
    with zipfile.ZipFile(r["zip"]) as z:
        assert len(z.namelist()) == len(p["cards"])
    leg = (tmp_path / "saida" / "legenda.txt").read_text()
    assert "Resultados variam" in leg and "CRM/SP 186.470" in leg and len(leg.splitlines()[0]) <= 125


def test_carrossel_bloqueia_promessa(tmp_path):
    p = {"titulo": "x", "cards": [{"layout": "capa", "titulo": "Resultado garantido"}], "legenda": "x"}
    with pytest.raises(SystemExit):
        carrossel.exportar(tmp_path, p)


def test_sigla_mantida():
    assert carrossel._sigla("LASER DE CO2") == "laser de CO2"


def test_formatos_derivam_a_mesma_edicao(tmp_path):
    origem = tmp_path / "projetos" / "2026-11-01_co2"
    (origem / "bruto").mkdir(parents=True)
    (origem / "trabalho").mkdir()
    (origem / "trabalho" / "hooks_sorteados.json").write_text('{"V2": "A-H18"}')
    p = {"_pasta": origem, "titulo": "CO2", "formato": "reels", "template": "daniel", "selo": "LASER DE CO2",
         "clipes": [{"arquivo": "bruto/a.mov"}], "mensagens": [{"titulo": "Oi", "na_fala": "oi"}],
         "efeitos": [{"tipo": "circulo", "inicio": 2}], "versoes": [{"nome": "V1", "fontes": "O1"}, {"nome": "V2"}]}
    criadas = formatos.gerar(p, ["stories", "tv", "reels"])
    assert [c[0].name for c in criadas] == ["stories", "tv"]                     # o próprio formato não se repete
    st = yaml.safe_load((origem.parent / "2026-11-01_co2-formatos" / "stories" / "projeto.yaml").read_text())
    assert st["formato"] == "stories" and st["template"] == "daniel" and st["versoes"][0]["fontes"] == "O1"
    assert st["clipes"][0]["arquivo"] == "../../2026-11-01_co2/bruto/a.mov" and st["efeitos"]
    assert (origem.parent / "2026-11-01_co2-formatos" / "stories" / "trabalho" / "hooks_sorteados.json").exists()
    tv = yaml.safe_load((origem.parent / "2026-11-01_co2-formatos" / "tv" / "projeto.yaml").read_text())
    assert tv["template"] == "tv" and tv["versoes"] == [{"nome": "TV"}] and tv["audio"]["original"] is False
    assert tv["tv"]["tratamento"] == "Laser de CO2"
    assert "na_fala" not in tv["mensagens"][0] and "efeitos" not in tv
