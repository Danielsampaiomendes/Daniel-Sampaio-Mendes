"""Biblioteca de imagens, post estático e antes e depois (uso interno)."""
import pytest
import yaml
from PIL import Image

from divine_studio import antes_depois, aprendizado, biblioteca, carrossel, post


@pytest.fixture
def raiz(tmp_path, monkeypatch):
    for m in (biblioteca, post, antes_depois, carrossel):
        monkeypatch.setattr(m, "ROOT", tmp_path)
    monkeypatch.setattr(aprendizado, "PROJETOS", tmp_path / "projetos")
    return tmp_path


def _foto(caminho, cor=(150, 120, 110), tam=(600, 800)):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", tam, cor).save(caminho)
    return caminho


def test_biblioteca_lista_o_que_falta_e_acha_por_tema(raiz):
    cats = {c["chave"]: c for c in biblioteca.listar()}
    assert {"marca", "pessoas", "tecnologias", "clinica", "produtos"} <= set(cats)
    assert cats["marca"]["faltam_obrigatorios"] >= 1
    assert biblioteca.foto_do_tema("Endolaser nos braços") is None
    _foto(raiz / "assets/tecnologias/endolaser.jpg")
    assert biblioteca.foto_do_tema("Endolaser nos braços").name == "endolaser.jpg"
    pedidos = biblioteca.pedidos("Laser de CO2 no rosto")
    assert any(p["arquivo"] == "laser-co2" for p in pedidos)              # pede a foto da tecnologia do tema
    assert any(p["arquivo"] == "divine-simbolo" for p in pedidos)         # e o essencial que falta
    assert not any(p["arquivo"] == "endolaser" for p in pedidos)


def test_salvar_renomeia_e_arquiva_a_anterior(raiz):
    biblioteca.salvar("tecnologias", "IMG_123.jpg", _foto(raiz / "a.jpg").read_bytes(), item="laser-co2")
    biblioteca.salvar("tecnologias", "IMG_456.png", _foto(raiz / "b.png").read_bytes(), item="laser-co2")
    assert [f.name for f in (raiz / "assets/tecnologias").iterdir()] == ["laser-co2.png"]
    assert len(list((raiz / "_arquivo/biblioteca/tecnologias").iterdir())) == 1       # nunca apaga
    with pytest.raises(ValueError):
        biblioteca.salvar("tecnologias", "x.exe", b"..")


def test_post_estatico_sai_nos_tres_tamanhos(raiz):
    (raiz / "projetos").mkdir()
    _foto(raiz / "assets/tecnologias/endolaser.jpg")
    pasta = post.novo("Endolaser nos braços")
    p = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8"))
    assert p["tipo"] == "post" and len(p["cards"]) == 1
    assert p["cards"][0]["foto"] == "assets/tecnologias/endolaser.jpg"    # foto da Biblioteca na capa
    r = post.exportar(pasta, p)
    tamanhos = sorted(Image.open(a).size for a in r["arquivos"])
    assert tamanhos == [(1080, 1350), (1080, 1920), (1920, 1080)]
    assert len(list((raiz / "entregas").glob("*/Posts/*.png"))) == 3
    pubs = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8"))["publicacoes"]
    assert {x["versao"]: x["rede"] for x in pubs} == {"feed45": "instagram", "stories": "instagram", "tv": "tv"}


def _projeto_ad(raiz):
    (raiz / "projetos").mkdir(exist_ok=True)
    pasta = antes_depois.novo("Bumbum Up", "bioestimulação glútea")
    _foto(pasta / "bruto/a.jpg"), _foto(pasta / "bruto/d.jpg", (110, 90, 140))
    _foto(pasta / "bruto/m.jpg", (200, 100, 90), (1200, 800))
    p = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8"))
    p["pares"] = [{"antes": "bruto/a.jpg", "depois": "bruto/d.jpg", "angulo": "Perfil"},
                  {"montagem": "bruto/m.jpg", "angulo": "Posterior"}]
    return pasta, p


def test_montagem_e_dividida_ao_meio(raiz):
    pasta, p = _projeto_ad(raiz)
    a, d = antes_depois.fotos_do_par(pasta, p["pares"][1])
    assert a.size == d.size == (600, 800)


def test_antes_depois_exige_autorizacao_e_sai_marcado_nao_postar(raiz):
    pasta, p = _projeto_ad(raiz)
    with pytest.raises(SystemExit, match="autorização"):
        antes_depois.exportar(pasta, p)
    p["autorizacao_imagem"] = "sim"
    p["video"] = False
    r = antes_depois.exportar(pasta, p)
    assert len(r["arquivos"]) == 3 and all("NAO-POSTAR" in a for a in r["arquivos"])
    assert sorted(Image.open(a).size for a in r["arquivos"]) == [(1080, 1350), (1080, 1920), (1920, 1080)]
    assert len(list((raiz / "entregas").glob(f"*/{antes_depois.ENTREGA}/*NAO-POSTAR*"))) == 3
    pubs = yaml.safe_load((pasta / "projeto.yaml").read_text(encoding="utf-8"))["publicacoes"]
    assert {x["rede"] for x in pubs} == {"consulta"} and {x["status"] for x in pubs} == {"aprovado"}


def test_painel_nao_deixa_postar_antes_e_depois(raiz, monkeypatch):
    from divine_studio import painel
    pasta, p = _projeto_ad(raiz)
    monkeypatch.setattr(painel, "PROJETOS", raiz / "projetos")
    import json
    corpo = json.dumps({"p": pasta.name, "versao": "tv", "campos": {"status": "postado"}}).encode()
    h = _handler(painel, "/api/publicacao", corpo)
    h.do_POST()
    assert h.codigo == 400 and "uso interno" in h.saida.decode()


def _handler(painel, caminho, corpo):
    import io
    cls = next(v for v in vars(painel).values() if isinstance(v, type) and hasattr(v, "do_POST"))
    h = cls.__new__(cls)
    h.path, h.headers = caminho, {"Content-Length": str(len(corpo))}
    h.rfile, h.client_address = io.BytesIO(corpo), ("127.0.0.1", 0)
    h.codigo, h.saida = None, b""
    h._autorizado = lambda: True
    h._barrar = lambda c: False

    def json_(dados, codigo=200):
        h.codigo, h.saida = codigo, json.dumps(dados).encode()
    import json
    h._json = json_
    h._erro = lambda msg, codigo=400: json_({"erro": msg}, codigo)
    return h


def test_post_na_tv_usa_a_coluna_central(raiz):
    p = {"cards": [{"layout": "texto", "titulo": "Um título *longo* para ver a coluna", "texto": "texto"}],
         "estilo": "divine", "fontes": "O1", "formato": "tv"}
    assert carrossel.desenhar(p, 0).size == (1920, 1080)
