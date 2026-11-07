from divine_studio import roteirista


def _pal(frase_inicio):
    out = []
    for texto, ini in frase_inicio:
        t = ini
        for w in texto.split():
            out.append({"texto": w, "inicio": t, "fim": t + 0.3})
            t += 0.35
    return out


FALA = _pal([("Você sabia que a gordura nos braços não sai só com treino?", 0.0),
             ("O Endolaser age por dentro da pele com fibra fina.", 5.0),
             ("São 2 sessões em média, com avaliação antes.", 10.0),
             ("Agende sua avaliação pelo link.", 15.0)])


def test_frases_e_ganchos():
    fr = roteirista.frases(FALA)
    assert len(fr) == 4 and fr[1]["inicio"] == 5.0
    g = roteirista.ganchos_da_fala(FALA, 3)
    assert g and "sabia" in g[0][0]["titulo"].lower()


def test_aplicar_regras():
    proj = {"titulo": "Endolaser", "versoes": [{"nome": "V1"}, {"nome": "V2"}, {"nome": "V3"}]}
    plano = roteirista.planejar_regras(proj, FALA)
    novo = roteirista.aplicar(proj, plano)
    assert novo["versoes"][0]["hook"]
    assert novo["roteiro_automatico"]["fonte"] == "regras"
    assert all(e.get("na_fala") for e in novo.get("efeitos") or [])
