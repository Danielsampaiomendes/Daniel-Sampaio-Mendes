"""Testes do revisor de compliance, do rodízio e do texto rico.  Rodar: python3 -m pytest tests -q"""
import re

import pytest

from divine_studio import compliance, rodizio, text
from divine_studio.config import load


def _proj(**kw):
    p = {"titulo": "t", "conteudo_medico": True, "autorizacao_imagem": "sim",
         "legenda": "Texto.\nResultados variam de pessoa para pessoa.\nResp. técnico: Dr. Daniel · CRM/SP 186.470"}
    p.update(kw)
    return p


def _regras(achados, nivel="erro"):
    return {a.regra for a in achados if a.nivel == nivel}


@pytest.mark.parametrize("frase,regra", [
    ("Reduz 30% da gordura", "percentual"),
    ("Resultado garantido", "promessa"),
    ("Com tirzepatida você emagrece", "medicamento"),
    ("Ozempic não é milagre", "medicamento"),
    ("Implante hormonal na Divine", "implante_hormonal"),
    ("Dr. Daniel, nutrólogo", "nutrologo"),
    ("Comenta ESTRIA que eu te mando", "comenta_palavra"),
    ("Comenta CO2 que a gente explica", "comenta_palavra"),
])
def test_erros_bloqueiam(frase, regra):
    assert regra in _regras(compliance.revisar(_proj(), [frase]))


@pytest.mark.parametrize("frase", [
    "Comenta quantos você marcou",
    "Manda pra amiga que vive adiando o CO2.",
    "Microcolunas de energia que *estimulam* a renovação.",
    "Reposição hormonal com pellets",
    "Pós-graduado em Nutrologia pelo Einstein",
])
def test_frases_liberadas(frase):
    assert not _regras(compliance.revisar(_proj(), [frase]))


def test_percentual_de_tempo_liberado_por_flag():
    assert "percentual" not in _regras(compliance.revisar(_proj(permitir_percentual=True), ["1 hora é só 4% do seu dia"]))


def test_endereco_oficial_nao_conta_como_travessao():
    end = load("marca")["clinica"]["endereco"]
    p = _proj(legenda=f"Oi.\n📍 {end}\nResultados variam de pessoa para pessoa.\nCRM/SP 186.470")
    assert "travessao" not in _regras(compliance.revisar(p, []), "aviso")


def test_travessao_na_tela_gera_aviso():
    assert "travessao" in _regras(compliance.revisar(_proj(), ["Pele — renovação"]), "aviso")


def test_legenda_sem_aviso_e_sem_rt():
    ach = compliance.revisar(_proj(legenda="Só um texto."), [])
    assert {"aviso_resultados", "rt"} <= _regras(ach)


def test_autorizacao_pendente_vira_aviso():
    assert "autorizacao_imagem" in _regras(compliance.revisar(_proj(autorizacao_imagem="pendente"), []), "aviso")


def test_rodizio_tres_combinacoes_diferentes_e_fora_das_recentes():
    esc = rodizio.escolher_fontes(3)
    assert len(set(esc)) == 3
    recentes = set(load("historico")["fontes"][-6:])
    assert not set(esc) & recentes


def test_rodizio_respeita_fonte_fixa():
    assert rodizio.escolher_fontes(3, ["B", None, None])[0] == "B"


def test_sfx_versoes_nao_repetem():
    g = rodizio.escolher_sfx("abertura", 3)
    nomes = [n for grupo in g for n in grupo]
    assert len(nomes) == len(set(nomes))


def test_parse_destaque_e_quebra():
    linhas = text.parse("Essa luz vermelha / é só a *mira.*")
    assert len(linhas) == 2
    assert ("mira.", True) in linhas[1]
    assert text.limpar("A / *b*") == "A b"


def test_fontes_do_banco_existem():
    from divine_studio.fonts import pasta_fontes
    for c in load("fontes")["combinacoes"].values():
        for papel in ("titulo", "apoio", "destaque"):
            assert (pasta_fontes() / c[papel]["arquivo"]).exists(), c[papel]["arquivo"]
