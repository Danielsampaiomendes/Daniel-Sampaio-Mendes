"""Truques dos vídeos de referência (16 efeitos e finais) e o método 3C dos carrosséis."""
import numpy as np
import pytest

from divine_studio import carrossel, efeitos
from divine_studio import efeitos_truques as et


@pytest.mark.parametrize("tipo", sorted(set(et.EFEITOS) - set(__import__("divine_studio.efeitos_mais", fromlist=["EFEITOS"]).EFEITOS)))
def test_cada_truque_desenha_sem_erro(tipo):
    W, H = 216, 384
    q = efeitos._cena_referencia(W, H)
    f = efeitos.QUADRO[tipo]({"tipo": tipo, "inicio": 0.0, **et.EXEMPLOS.get(tipo, {})}, None, W, H, 10)
    f = f[0] if isinstance(f, tuple) else f
    dur = et.DURACAO[tipo]
    for t in np.arange(0, dur, 0.2):
        r = f(q, float(t))
        assert r.shape == q.shape and r.dtype == np.uint8
    assert np.abs(f(q, dur * 0.6).astype(int) - q.astype(int)).mean() > 0.5      # algo aparece
    assert f(q, dur + 1).tolist() == q.tolist()                                   # fora do tempo, nada muda


def test_apelidos_dos_nomes_do_video():
    assert efeitos.resolver_tipo({"tipo": "vertigem"}) == "dolly_zoom"
    assert efeitos.resolver_tipo({"tipo": "profundidade"}) == "texto_atras"
    assert all(t in efeitos.NOMES for t in et.EFEITOS)


def test_carrossel_tres_c():
    cards = carrossel.rascunho("Laser CO2", "lista")
    assert cards[3]["layout"] == "toque_duplo"
    assert "bio" in cards[-1]["convite"]
    assert len(cards) <= carrossel._cfg()["max_cards"]
    assert carrossel.checar_3c({"cards": cards}) == []
    longa = [{"layout": "capa", "titulo": "uma capa enorme com muito mais do que doze palavras para ler de uma vez só"}]
    avisos = carrossel.checar_3c({"cards": longa})
    assert any("palavras" in a for a in avisos) and any("2x" in a for a in avisos)
    img = carrossel.desenhar({"cards": cards, "estilo": "divine"}, 3)
    assert img.size[0] > 0


from divine_studio import efeitos_mais as em  # noqa: E402


@pytest.mark.parametrize("tipo", sorted(em.EFEITOS))
def test_mais_efeitos_desenham_sem_erro(tipo):
    W, H = 216, 384
    q = efeitos._cena_referencia(W, H)
    f = efeitos.QUADRO[tipo]({"tipo": tipo, "inicio": 0.0, **em.EXEMPLOS.get(tipo, {})}, None, W, H, 10)
    f = f[0] if isinstance(f, tuple) else f
    dur = em.DURACAO[tipo]
    for t in np.arange(0, dur, 0.25):
        r = f(q, float(t))
        assert r.shape == q.shape and r.dtype == np.uint8
    assert f(q, dur + 1).tolist() == q.tolist()


def test_catalogo_tem_categoria_para_todos():
    cat = efeitos.catalogo()
    assert all(c["categoria"] != "Outros" for c in cat)
    assert {"ascii", "palavras_caindo", "conquista", "holofote"} <= {c["tipo"] for c in cat}
    assert efeitos.resolver_tipo({"tipo": "cores_pasteis"}) == "pasteis"
