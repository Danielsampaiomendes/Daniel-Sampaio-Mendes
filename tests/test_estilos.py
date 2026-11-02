"""Estilos de edição: aplicam legenda, ritmo e peças sem passar por cima do que o projeto define."""
from PIL import Image

from divine_studio import estilos, legendas
from divine_studio.efeitos import QUADRO, TIPOS, resolver_tipo


def test_todo_estilo_usa_efeitos_que_existem():
    cfg = estilos._cfg()["estilos"]
    assert len(cfg) >= 10
    for nome, e in cfg.items():
        for tipo in (e.get("meio") or []) + [x["tipo"] for x in e.get("elementos") or []]:
            t = resolver_tipo({"tipo": tipo})
            assert t in QUADRO or t in TIPOS, (nome, tipo)


def test_aplicar_respeita_o_projeto():
    p = {"titulo": "Laser CO2", "selo": "LASER DE CO2", "estilo_edicao": "papel", "legendas": {"tamanho": 40},
         "efeitos": [{"tipo": "manchetes", "inicio": 1.6}], "efeitos_evitar": [{"tipo": "ticket", "inicio": 15.8}]}
    pv, v = estilos.aplicar(p, {"nome": "V1"}, 20.0)
    assert pv["_estilo"] == "papel" and pv["legendas"]["tamanho"] == 40 and pv["legendas"]["caixa"] == "fundo"
    tipos = [e["tipo"] for e in pv["efeitos"]]
    assert tipos.count("manchetes") == 1                       # o seu, perto do mesmo tempo, vence
    assert "ticket" not in tipos                              # tirado no storyboard, não volta
    rec = next(e for e in pv["efeitos"] if e["tipo"] == "recorte_papel")
    assert rec["texto"] == "LASER DE CO2" and rec["_estilo"] == "papel"
    assert "efeitos" in p and len(p["efeitos"]) == 1           # o original fica intacto


def test_estilo_por_versao_e_padrao():
    p = {"titulo": "x", "estilo_edicao": "glow"}
    assert estilos.nome_do(p, {"estilo_edicao": "papel"}) == "papel"
    assert estilos.aplicar({"titulo": "x"}, {}, 10)[0].get("_estilo") is None


def test_legenda_caixa_e_glow():
    img = Image.new("RGBA", (100, 40), (255, 255, 255, 255))
    assert legendas._acabamento(img, {}, 1.0) is img
    caixa = legendas._acabamento(img, {"caixa": "fundo"}, 1.0)
    glow = legendas._acabamento(img, {"glow": "dourado"}, 1.0)
    assert caixa.width > img.width and glow.width > caixa.width
