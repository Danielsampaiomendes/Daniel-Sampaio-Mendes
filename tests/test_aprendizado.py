"""Testes da programação de postagens e do aprendizado (gostei, postei, métricas, versão IA)."""
import json

import pytest
import yaml

from divine_studio import aprendizado


@pytest.fixture
def projetos(tmp_path, monkeypatch):
    raiz = tmp_path / "projetos"
    monkeypatch.setattr(aprendizado, "PROJETOS", raiz)

    def criar(nome, fontes, hook_tipo_id, gostei=False, postado=False, metricas=None, efeitos=None):
        pasta = raiz / nome
        (pasta / "trabalho").mkdir(parents=True)
        (pasta / "projeto.yaml").write_text(yaml.safe_dump({
            "titulo": nome, "template": "divine", "efeitos": efeitos or [],
            "versoes": [{"nome": "V1", "hook_id": hook_tipo_id, "fontes": fontes}]}))
        campos = {}
        if gostei:
            campos["gostei"] = True
        if postado:
            campos["status"] = "postado"
        if metricas:
            campos["metricas"] = metricas
        aprendizado.marcar(pasta, "V1", "saida/v1.mp4", **campos)
        return pasta
    return criar


def test_marcar_guarda_status_e_caracteristicas(projetos):
    pasta = projetos("a", "O3", "A-H18", gostei=True)
    pub = aprendizado.marcar(pasta, "V1", status="postado", link="https://instagram.com/p/x")
    assert pub["status"] == "postado" and pub["data_postagem"] and pub["gostei"]
    assert pub["caracteristicas"]["fontes"] == "O3" and pub["caracteristicas"]["hook_id"] == "A-H18"
    assert pub["caracteristicas"]["hook_tipo"] in ("positivo", "curiosidade", "negativo")
    todas = aprendizado.todas_publicacoes()
    assert len(todas) == 1 and todas[0]["link"].endswith("/x")


def test_metricas_acima_da_media_pesam_mais(projetos):
    projetos("bom", "O1", "A-H18", postado=True, metricas={"alcance": 20000, "compartilhamentos": 300, "salvamentos": 200})
    projetos("fraco", "O4", "C-H70", postado=True, metricas={"alcance": 800, "compartilhamentos": 1})
    projetos("meh", "O2", "C-H76", postado=True, metricas={"alcance": 3000, "compartilhamentos": 10})
    prefs = aprendizado.preferencias()
    assert prefs["fontes"]["O1"][0] > prefs["fontes"]["O2"][0] > prefs["fontes"]["O4"][0]
    assert aprendizado.melhor("fontes", ["O4", "O2", "O1"], prefs) == "O1"
    assert any("O1" in r for r in aprendizado.resumo(prefs))


def test_versao_ia_usa_o_que_funcionou_e_explica(projetos):
    projetos("bom", "O5", "A-H18", gostei=True, postado=True, efeitos=[{"tipo": "circulo", "inicio": 2}],
             metricas={"alcance": 9000, "salvamentos": 300})
    v = aprendizado.versao_ia({"titulo": "Laser de CO2", "template": "divine", "efeitos": []}, [], ["O1", "O2"])
    assert v["nome"] == "IA" and v["fontes"] == "O5"
    assert v["efeitos"][0]["tipo"] == "circulo" and v["porque"]


def test_sem_versao_ia_na_tv_e_no_carrossel():
    assert aprendizado.versao_ia({"template": "tv"}, [], []) is None
    assert aprendizado.versao_ia({"tipo": "carrossel"}, [], []) is None
