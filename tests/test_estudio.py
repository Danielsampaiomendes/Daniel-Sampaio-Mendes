"""Estúdio (tela de edição profissional): config/estudio.yaml vale e um nome errado não quebra a tela."""
from divine_studio import painel
from divine_studio.efeitos import catalogo


def test_config_do_estudio_so_com_o_que_existe():
    c = painel.estudio_config()
    tipos = {x["tipo"] for x in catalogo()}
    assert c["efeitos_rapidos"] and all(e["tipo"] in tipos and e["rotulo"] for e in c["efeitos_rapidos"])
    assert c["sons_rapidos"]
    chaves = [a["chave"] for a in c["agentes"]]
    assert {"fala", "roteiro", "legenda", "ritmo", "compliance", "previsao", "render"} <= set(chaves)
    assert c["previa_automatica"]["espera_s"] >= 1 and c["largura_minima"] >= 900


def test_nome_errado_no_yaml_fica_de_fora(monkeypatch):
    real = painel.load

    def falso(nome):
        if nome == "estudio":
            return {"efeitos_rapidos": [{"tipo": "nao_existe"}, {"tipo": "zoom_batida"}, "lixo"],
                    "sons_rapidos": ["som_que_nao_existe", "pop_suave_a"], "agentes": [{"chave": "x"}]}
        return real(nome)
    monkeypatch.setattr(painel, "load", falso)
    c = painel.estudio_config()
    assert [e["tipo"] for e in c["efeitos_rapidos"]] == ["zoom_batida"]
    assert c["efeitos_rapidos"][0]["rotulo"]                       # sem rótulo no YAML: usa o nome do catálogo
    assert c["agentes"] == [] and c["abrir_sozinho"] is True
    assert all(n != "som_que_nao_existe" for n in c["sons_rapidos"])


def test_estudio_js_servido_e_ligado_no_html():
    html = (painel.WEB / "index.html").read_text(encoding="utf-8")
    assert '<script src="/estudio.js"></script>' in html
    assert (painel.WEB / "estudio.js").exists()
