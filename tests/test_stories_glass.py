"""Stories no Liquid Glass Divine (portfólio de identidade visual): cartão no centro, fora das zonas mortas,
três vozes, versões escura e clara, nunca o mesmo fundo duas vezes seguidas."""
import numpy as np
import yaml
from PIL import Image

from divine_studio import stories_glass


def _story():
    return {"id": "T", "frase": "Laser CO2 é só pra mancha?", "chave": "Mito ou verdade",
            "blocos": [{"tipo": "opcoes", "itens": ["Mito", "Verdade"]}, {"tipo": "lista", "itens": ["Um", "Dois"]},
                       {"tipo": "escala", "de": 0, "ate": 10, "rotulo_de": "Já", "rotulo_ate": "Nunca"},
                       {"tipo": "linhas", "itens": ["Linha"]}, {"tipo": "texto", "texto": "Texto.", "forte": True}],
            "fecho": "A resposta tá no próximo Story.", "chamada": "Reage com o seu palpite."}


def test_escura_e_clara_com_cartao_fora_das_zonas_mortas():
    k = stories_glass.cfg()["cartao"]
    for versao in ("escura", "clara"):
        img = stories_glass.desenhar(_story(), versao)
        assert img.size == (1080, 1920)
        assert k["base_maxima"] <= 1580 and k["topo_minimo"] >= 250
    esc = np.asarray(stories_glass.desenhar(_story(), "escura").convert("L"), float)
    cla = np.asarray(stories_glass.desenhar(_story(), "clara").convert("L"), float)
    meio = (slice(700, 1100), slice(200, 880))
    assert esc[meio].mean() < 90 < cla[meio].mean()          # vidro escuro x vidro fosco claro


def test_palavra_chave_em_caixa_alta_e_dourada():
    c = stories_glass.cores("escura")
    im = stories_glass.palavra_chave("colágeno", c, 800)
    px = np.asarray(im)[..., :3][np.asarray(im)[..., 3] > 250]
    assert len(px) and px[:, 0].mean() > px[:, 2].mean()   # dourado: mais vermelho que azul


def test_gerar_alterna_fundos_e_faz_as_duas_versoes(tmp_path):
    arq = tmp_path / "stories.yaml"
    arq.write_text(yaml.safe_dump({"versoes": ["escura", "clara"], "stories": [
        {"id": "A", "frase": "Quem nunca?", "chave": "Pele"}, {"id": "B", "frase": "De 0 a 10", "chave": "Sono"}]},
        allow_unicode=True), encoding="utf-8")
    feitos = stories_glass.gerar(arq, tmp_path / "saida")
    assert [f.name for f in feitos] == ["A_escura.png", "A_clara.png", "B_escura.png", "B_clara.png"]
    a, b = (np.asarray(Image.open(tmp_path / "saida" / n).convert("L").resize((54, 96)), float)
            for n in ("A_escura.png", "B_escura.png"))
    assert np.abs(a - b).mean() > 3                           # fundos diferentes em peças seguidas
