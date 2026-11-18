"""Acervo: imagens da pasta toda catalogadas; logos em alta e fundos de IA entram na Biblioteca sozinhos."""
import pytest
from PIL import Image

from divine_studio import acervo, biblioteca, pedidos


@pytest.fixture
def pasta(tmp_path, monkeypatch):
    monkeypatch.setattr(acervo, "ROOT", tmp_path)
    monkeypatch.setattr(acervo, "INDICE", tmp_path / "assets" / ".acervo.json")
    monkeypatch.setattr(biblioteca, "ROOT", tmp_path)

    def img(rel, tam, cor=(20, 20, 20)):
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", tam, cor).save(f)
        return f
    img("assets/marca/logo-horizontal.png", (400, 120))                      # a que estava: baixa
    img("Logos Divine HD/Divine logo horizontal.png", (3000, 900))           # a boa
    img("Outra marca/logo horizontal parceiro.png", (4000, 1200))            # de outra marca: não entra
    img("Canva IA/fundo liquid glass perolas.png", (1080, 1920))             # fundo de IA vertical
    img("Canva IA/fundo liquid glass tv.png", (1920, 1080))                  # horizontal: não é de Stories
    img("Videos/Laser CO2/aparelho laser co2.jpg", (1600, 1200), (200, 200, 200))
    img("Videos/Laser CO2/miniatura.jpg", (120, 90))                         # pequena demais
    img("projetos/x/trabalho/quadro.jpg", (1080, 1920))                      # pasta de trabalho: ignorada
    return tmp_path


def test_varre_cataloga_e_ignora_o_que_nao_e_acervo(pasta):
    r = acervo.varrer()
    idx = acervo.ler()["imagens"]
    assert r["total"] == 5 and "Videos/Laser CO2/miniatura.jpg" not in idx
    assert not any("trabalho" in k for k in idx)
    assert idx["Canva IA/fundo liquid glass perolas.png"]["ia"] and idx["Canva IA/fundo liquid glass perolas.png"]["cat"] == "fundos"
    assert idx["Videos/Laser CO2/aparelho laser co2.jpg"]["cat"] == "tecnologias"
    assert idx["Videos/Laser CO2/aparelho laser co2.jpg"]["claro"] is True
    assert acervo.varrer()["novas"] == 0                                     # segunda vez: só o que mudou


def test_abastece_a_biblioteca_com_a_logo_em_alta_e_o_fundo_de_ia(pasta):
    acervo.varrer()
    feitos = acervo.abastecer()
    logo = biblioteca.logo("logo-horizontal")
    assert Image.open(logo).size == (3000, 900)                              # trocou pela boa
    assert list((pasta / "_arquivo" / "assets" / "marca").glob("*logo-horizontal.png"))   # a antiga foi guardada
    assert (pasta / "assets" / "fundos" / "fundo_liquid_glass_perolas.png").exists()
    assert not (pasta / "assets" / "fundos" / "fundo_liquid_glass_tv.png").exists()
    assert len(feitos) == 2
    acervo.varrer()
    assert acervo.abastecer() == []                                          # não repete
    assert "fundo_liquid_glass_perolas" in acervo.fundos()["escura"]
    assert acervo.saude()["logos_baixas"] == []


def test_busca_e_pedido_de_foto_pelo_campo(pasta):
    acervo.varrer()
    assert acervo.buscar("laser co2")[0]["arquivo"] == "Videos/Laser CO2/aparelho laser co2.jpg"
    assert all(x["ia"] for x in acervo.buscar("fundo", so_ia=True))
    r = pedidos.aplicar({}, "Aos 8 segundos coloca a foto do laser co2", 20)
    assert r["projeto"]["efeitos"] == [{"tipo": "insert_foto", "inicio": 8.0, "foto": "Videos/Laser CO2/aparelho laser co2.jpg"}]
    r = pedidos.aplicar({}, "Aos 8 segundos coloca a foto do unicornio", 20)
    assert r["nao_entendi"] and not r["projeto"].get("efeitos")              # sem imagem: não põe efeito quebrado
