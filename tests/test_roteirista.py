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


def test_estilo_legenda_padrao_e_projeto(tmp_path, monkeypatch):
    from divine_studio import legendas
    monkeypatch.setattr(legendas, "PADRAO", tmp_path / "padrao.json")
    legendas.salvar_padrao({"posicao": 0.3, "cor": "#F7D046", "lixo": 1})
    c = legendas._cfg({"legendas": {"tamanho": 80, "ativo": True}})
    assert c["posicao"] == 0.3 and c["cor"] == "#F7D046" and c["tamanho"] == 80 and "lixo" not in c
    cs, _ = legendas.camadas({"legendas": {"fonte": "Anton-Regular.ttf", "caixa": True}},
                             [{"texto": "Oi", "inicio": 0, "fim": 0.4}], 1080, 1920, 10)
    assert cs and abs((cs[0].y + cs[0].h / 2) - 1920 * 0.3) < 4


def test_tem_fala_pela_transcricao(tmp_path):
    import subprocess
    from divine_studio import auto
    v = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=s=64x64:d=10", "-f", "lavfi",
                    "-i", "anoisesrc=d=10:a=0.3", "-shortest", str(v)], check=True)
    palavras = [{"texto": "oi", "inicio": i * 0.5, "fim": i * 0.5 + 0.3} for i in range(15)]
    assert auto.tem_fala(v, lambda f: palavras)
    assert not auto.tem_fala(v, lambda f: [])


def test_sugestoes_da_fala():
    from divine_studio import sugestoes
    fala = _pal([("Oi gente, eu sou o Doutor Daniel e hoje eu vou falar de Endolaser.", 0.0),
                 ("O Endolaser age por dentro da pele com fibra fina.", 6.0),
                 ("Ele aquece a gordura e estimula o colágeno.", 10.0)])
    s = sugestoes.da_fala(fala)
    titulos = " ".join(x["titulo"] for x in s)
    assert "apresentação" in titulos            # abre com "oi, eu sou": sugere começar pelo assunto
    assert "pedido" in titulos                  # termina sem CTA falado
    assert not sugestoes.da_fala(FALA) or all("apresentação" not in x["titulo"] for x in sugestoes.da_fala(FALA))
    assert sugestoes.da_fala([])[0]["titulo"] == "Ligue a transcrição"
