"""Stories no liquid glass Divine: cartão de vidro fora das zonas mortas, rosto livre e texto em caixa alta e baixa."""
import numpy as np
import yaml
from PIL import Image

from divine_studio import stories_glass


def test_story_glass_respeita_zonas_e_rosto(tmp_path):
    foto = tmp_path / "foto.jpg"
    Image.new("RGB", (900, 1000), (200, 190, 180)).save(foto)
    s = {"id": "T", "selo": "Mito ou verdade?", "titulo": "Laser *CO2*", "apoio": "É só pra mancha.",
         "blocos": [{"tipo": "opcoes", "itens": ["Mito", "Verdade"]}, {"tipo": "lista", "itens": ["Um", "Dois"]},
                    {"tipo": "escala", "de": 0, "ate": 10, "rotulo_de": "Já", "rotulo_ate": "Nunca"},
                    {"tipo": "linhas", "itens": ["Linha"]}, {"tipo": "grande", "texto": "Mito."},
                    {"tipo": "texto", "texto": "Texto corrido.", "forte": True}],
         "chamada": "Me chama no direct", "chamada_apoio": "Sem julgamento"}
    img = stories_glass.desenhar(s, foto)
    assert img.size == (1080, 1920)
    a = np.asarray(img.convert("L")).astype(int)
    c = stories_glass.cfg()["cartao"]
    # abaixo do cartão (zona morta de baixo) não tem texto: só fundo liso
    assert a[1600:1900, 100:980].std() < 12
    # o alto da foto (rosto) não é coberto pelo cartão
    assert abs(a[200:600, 300:780].mean() - 180) < 40
    assert c["base"] <= 1580


def test_gerar_a_partir_do_yaml(tmp_path):
    (tmp_path / "fotos").mkdir()
    Image.new("RGB", (800, 900), (120, 110, 100)).save(tmp_path / "fotos" / "f.jpg")
    arq = tmp_path / "stories.yaml"
    arq.write_text(yaml.safe_dump({"fotos": "fotos", "stories": [
        {"id": "A", "foto": "f.jpg", "titulo": "Quem *nunca*?", "apoio": "Conta quantos você já fez"},
        {"id": "B", "titulo": "Sem foto também sai"}]}, allow_unicode=True), encoding="utf-8")
    feitos = stories_glass.gerar(arq, tmp_path / "saida")
    assert [f.name for f in feitos] == ["A_liquid_glass.png", "B_liquid_glass.png"]
