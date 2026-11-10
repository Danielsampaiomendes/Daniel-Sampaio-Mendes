"""Pontos "!" da linha do tempo, previsão de público, dublagem de trecho e equilíbrio dos efeitos na fala."""
import json

import numpy as np
import yaml

from divine_studio import alertas, previsao, ritmo


def _fala(frases, conf=0.95):
    """[(texto, inicio)] -> palavras com 0,35 s cada, como o fala_base.json."""
    out = []
    for texto, t in frases:
        for w in texto.split():
            out.append({"texto": w, "inicio": round(t, 2), "fim": round(t + 0.3, 2), "conf": conf})
            t += 0.35
    return out


def _projeto(tmp_path, fala, extra=None, atencao=None):
    (tmp_path / "trabalho").mkdir()
    (tmp_path / "projeto.yaml").write_text(yaml.safe_dump({"titulo": "teste", **(extra or {})}), encoding="utf-8")
    (tmp_path / "trabalho" / "fala_base.json").write_text(json.dumps(fala), encoding="utf-8")
    if atencao:
        (tmp_path / "trabalho" / "atencao_V1.json").write_text(json.dumps(atencao), encoding="utf-8")
    return tmp_path


def test_compliance_na_fala_bloqueia_e_vem_primeiro(tmp_path):
    p = _projeto(tmp_path, _fala([("Você sabia que o laser trata manchas?", 0.0),
                                  ("O resultado é garantido em todo mundo.", 3.0),
                                  ("Agende sua avaliação.", 6.0)]))
    r = alertas.gerar(p)
    bloq = [x for x in r["pontos"] if x["nivel"] == "bloqueia"]
    assert bloq and bloq[0]["regra"] == "compliance_fala"
    assert 2.9 <= bloq[0]["t0"] <= 3.1
    assert {a["tipo"] for a in bloq[0]["acoes"]} >= {"cortar_frase", "dublar"}


def test_apresentacao_primeiro_e_fala_incerta_pedem_regravar_e_dublar(tmp_path):
    fala = _fala([("Oi gente eu sou o doutor Daniel.", 0.0)]) + \
        _fala([("Você sabia que o colágeno cai depois dos trinta?", 3.0)], conf=0.3) + \
        _fala([("Salva para lembrar.", 7.0)])
    r = alertas.gerar(_projeto(tmp_path, fala))
    regras = {x["regra"]: x for x in r["pontos"]}
    assert regras["apresentacao_primeiro"]["t0"] == 0
    dub = regras["fala_incerta"]
    assert dub["nivel"] == "dublar"
    acao = next(a for a in dub["acoes"] if a["tipo"] == "dublar")
    assert acao["inicio"] == 3.0 and acao["fim"] > acao["inicio"] and "colágeno" in acao["copy"]
    assert "sem_pedido_final" not in regras                  # "Salva" é pedido


def test_queda_de_atencao_vira_ponto_com_efeito_e_ignorar_some(tmp_path):
    at = {"passo": 0.5, "curva": [0.6] * 40, "inicio_fraco": False,
          "zonas": [{"ini": 6.0, "fim": 9.0, "causa": "imagem quase parada", "proposta": "um zoom na batida em 7.2 s",
                     "acao": {"tipo": "zoom_batida", "inicio": 7.2}}]}
    p = _projeto(tmp_path, _fala([("Você sabia que isso importa?", 0.0), ("Agende sua avaliação.", 15.0)]), atencao=at)
    r = alertas.gerar(p)
    q = next(x for x in r["pontos"] if x["regra"] == "queda_atencao")
    assert q["acoes"][0]["efeito"]["tipo"] == "zoom_batida"
    d = yaml.safe_load((p / "projeto.yaml").read_text())
    d["alertas_ignorados"] = [q["id"]]
    (p / "projeto.yaml").write_text(yaml.safe_dump(d))
    assert not [x for x in alertas.gerar(p)["pontos"] if x["regra"] == "queda_atencao"]


def test_regra_com_defeito_nao_derruba_as_outras(tmp_path, monkeypatch):
    monkeypatch.setattr(alertas, "_r_voz_baixa", lambda ctx, cfg: 1 / 0)
    p = _projeto(tmp_path, _fala([("O resultado é garantido.", 0.0), ("Agende.", 3.0)]))
    r = alertas.gerar(p)
    assert any(x["regra"] == "compliance_fala" for x in r["pontos"])
    assert any("voz_baixa" in a for a in r["avisos"])


def test_sem_fala_nem_previa_nao_quebra(tmp_path):
    r = alertas.gerar(_projeto(tmp_path, []))
    assert r["pontos"] == [] and r["tem_fala"] is False


def test_previsao_deterministica_e_sensivel_a_atencao():
    forte = {"passo": 0.5, "curva": [0.8] * 60, "inicio_fraco": False, "zonas": []}
    fraca = {"passo": 0.5, "curva": [0.8] * 20 + [0.1] * 20 + [0.8] * 20, "inicio_fraco": True, "zonas": [
        {"ini": 10.0, "fim": 20.0, "causa": "pausa na fala"}]}
    sem_cal = {"fator": 1.0, "calibrado": False}
    a = previsao.prever(forte, 32, calibracao=sem_cal)
    b = previsao.prever(fraca, 32, calibracao=sem_cal)
    assert a == previsao.prever(forte, 32, calibracao=sem_cal)
    assert 0 < a["de_100"]["fim"] <= a["de_100"]["metade"] <= a["de_100"]["passam_3s"] <= 100
    assert b["de_100"]["fim"] < a["de_100"]["fim"] and b["tempo_medio_s"] < a["tempo_medio_s"]
    assert any(9.5 <= s["t"] <= 20 and s["motivo"] == "pausa na fala" for s in b["saidas"])
    assert "De 100 pessoas" in previsao.frase(a)


def test_calibracao_usa_a_previsao_bruta():
    at = {"passo": 0.5, "curva": [0.5] * 40, "inicio_fraco": False, "zonas": []}
    base = previsao.prever(at, 22, calibracao={"escala": 1.0})
    mais = previsao.prever(at, 22, calibracao={"escala": 0.6, "calibrado": True})
    assert mais["tempo_medio_s"] > base["tempo_medio_s"]                # menos risco de sair: assistem mais
    assert mais["tempo_medio_s_bruto"] == base["tempo_medio_s_bruto"]   # a bruta não muda com a calibração
    assert previsao.prever({}, 10) == {"tem": False}
    assert "cerca de" in previsao.frase(base) and "estimativa" in previsao.frase(mais).lower()


def test_calibracao_reproduz_o_tempo_medio_real(tmp_path, monkeypatch):
    """Peças que ficam em 0,6 da previsão: a próxima previsão do mesmo tipo de vídeo já sai perto de 0,6 (converge)."""
    from divine_studio import aprendizado
    at = {"passo": 0.5, "curva": [0.6] * 30 + [0.3] * 20 + [0.6] * 10, "inicio_fraco": False, "zonas": []}
    bruta = previsao.prever(at, 34, calibracao={"escala": 1.0})
    pubs = []
    for i in range(3):
        pasta = tmp_path / f"p{i}" / "trabalho"
        pasta.mkdir(parents=True)
        previsao.salvar(pasta, "V1", bruta, final=True)
        pubs.append({"projeto": f"p{i}", "versao": "V1", "status": "postado",
                     "metricas": {"tempo_medio_s": 0.6 * bruta["tempo_medio_s_bruto"]}})
    monkeypatch.setattr(aprendizado, "PROJETOS", tmp_path)
    monkeypatch.setattr(aprendizado, "todas_publicacoes", lambda: pubs)
    cal = previsao.fator_calibracao()
    assert cal["calibrado"] and cal["escala"] > 1
    nova = previsao.prever(at, 34, calibracao=cal)
    assert abs(nova["tempo_medio_s"] - 0.6 * bruta["tempo_medio_s_bruto"]) < 0.05 * bruta["tempo_medio_s_bruto"]


def test_reels_curto_em_loop_fica_fora_da_calibracao(tmp_path, monkeypatch):
    """O tempo médio do Instagram conta as repetições: um Reels de 10 s com média de 11 s não é reproduzível e não
    pode virar "calibrado" puxando o multiplicador para o limite."""
    from divine_studio import aprendizado
    at = {"passo": 0.5, "curva": [0.6] * 20, "inicio_fraco": False, "zonas": []}
    bruta = previsao.prever(at, 10, calibracao={"escala": 1.0})
    assert previsao.escala_que_reproduz(bruta["entrada"], 11.0) is None
    pubs = []
    for i in range(3):
        pasta = tmp_path / f"p{i}" / "trabalho"
        pasta.mkdir(parents=True)
        previsao.salvar(pasta, "V1", bruta, final=True)
        pubs.append({"projeto": f"p{i}", "versao": "V1", "status": "postado", "metricas": {"tempo_medio_s": 11.0}})
    monkeypatch.setattr(aprendizado, "PROJETOS", tmp_path)
    monkeypatch.setattr(aprendizado, "todas_publicacoes", lambda: pubs)
    cal = previsao.fator_calibracao()
    assert not cal["calibrado"] and len(cal["loops"]) == 3


def test_pontos_sao_da_versao_pedida(tmp_path):
    fala = _fala([("Você sabia que isso importa?", 0.0), ("Agende sua avaliação.", 15.0)])
    p = _projeto(tmp_path, fala)
    (p / "trabalho" / "atencao_V2.json").write_text(json.dumps(
        {"zonas": [{"ini": 5.0, "fim": 9.0, "causa": "imagem parada", "proposta": "zoom lento", "acao": {"tipo": "zoom_digital", "inicio": 5.0}}]}))
    v1, v2 = alertas.gerar(p, "V1"), alertas.gerar(p, "V2")
    assert not any(x["regra"] == "queda_atencao" for x in v1["pontos"])
    assert any(x["regra"] == "queda_atencao" and x["t0"] == 5.0 for x in v2["pontos"])
    assert v2["versao"] == "V2" and v2["zonas"]


def test_leitura_do_higgsfield_so_vale_para_a_previa_analisada(tmp_path, monkeypatch):
    import os
    from divine_studio import higgsfield
    p = _projeto(tmp_path, _fala([("Você sabia disso?", 0.0), ("Agende sua avaliação.", 3.0)]))
    (p / "saida").mkdir()
    prev = p / "saida" / "teste_V1_PREVIA.mp4"
    prev.write_bytes(b"x")
    item = {"id": "a1", "projeto": p.name, "alvo": "virality_predictor", "status": "pronto",
            "entrada": {"arquivo": "saida/teste_V1_PREVIA.mp4", "mtime": round(prev.stat().st_mtime, 1)},
            "analise": {"quedas": [{"t": 2.0, "motivo": "abertura lenta"}]}}
    monkeypatch.setattr(higgsfield, "listar", lambda projeto=None, status=None: [item])
    assert any(x["regra"] == "higgsfield_queda" and x["t0"] == 2.0 for x in alertas.gerar(p, "V1")["pontos"])
    assert not any(x["regra"] == "higgsfield_queda" for x in alertas.gerar(p, "V2")["pontos"])   # outra versão
    os.utime(prev, (prev.stat().st_atime, prev.stat().st_mtime + 60))                           # prévia refeita
    velha = [x for x in alertas.gerar(p, "V1")["pontos"] if x["regra"] == "higgsfield_queda"]
    assert len(velha) == 1 and velha[0]["nivel"] == "conferir" and "antiga" in velha[0]["titulo"]


def test_dublagem_de_trecho_so_cala_o_original_ali(tmp_path, monkeypatch):
    from divine_studio import cli
    from divine_studio.audio import SR
    dub = np.full((SR, 2), 0.2, np.float32)                   # 1 s de voz nova
    monkeypatch.setattr("divine_studio.audio.ler_audio", lambda *a, **k: dub)
    monkeypatch.setattr("divine_studio.ingest.resolver", lambda p, arq: tmp_path / arq)
    voz = np.full((5 * SR, 2), 0.5, np.float32)
    p = {"audio": {"dublagem": [{"arquivo": "d.wav", "inicio": 2.0, "fim": 3.0}]}}
    out = cli._com_dublagem(p, voz, 5.0)
    assert abs(out[int(0.5 * SR), 0] - 0.5) < 1e-6           # antes: original
    assert abs(out[int(2.5 * SR), 0] - 0.2) < 1e-6           # no trecho: só a dublagem
    assert abs(out[int(4.0 * SR), 0] - 0.5) < 1e-6           # depois: original de novo


def test_equilibrio_fala_sem_motivo_nao_ganha_efeito_no_meio():
    neutra = _fala([(f"Essa é a frase número {k} do vídeo.".replace(str(k), "x"), k * 3.0) for k in range(8)])
    com = _fala([("Você sabia disso?", k * 3.0) for k in range(8)])
    meio = lambda ef: [e for e in ef if 2.0 < e["inicio"] < 20.0]
    sem_motivo = ritmo.planejar({"ritmo": "viral", "_fala": neutra}, {"nome": "V1"}, 26.0)
    com_motivo = ritmo.planejar({"ritmo": "viral", "_fala": com}, {"nome": "V1"}, 26.0)
    assert not meio(sem_motivo)
    assert len(meio(com_motivo)) >= 1
    for e in com_motivo:                                      # teto: no máximo 2 efeitos em 10 s no meio
        assert sum(1 for x in meio(com_motivo) if abs(x["inicio"] - e["inicio"]) < 5.0) <= 2


def test_o_tipo_do_efeito_vem_do_que_a_frase_diz():
    fala = _fala([("Bom dia a todos aqui.", 0.0), ("Você sabia que o colágeno cai?", 3.0),
                  ("Você pode vir de manhã ou de tarde.", 7.0), ("Nunca faça isso em casa.", 11.0),
                  ("Agende sua avaliação.", 18.0)])
    meio = lambda ef: {round(e["inicio"]): e for e in ef if 2.0 < e["inicio"] < 18.0 and e.get("motivo")}
    v1 = meio(ritmo.planejar({"ritmo": "viral", "_fala": fala}, {"nome": "V1"}, 24.0))
    assert v1[3]["motivo"] == "pergunta" and v1[3]["tipo"] in ("zoom_digital", "foco_lente")
    assert v1[11]["motivo"] == "alerta" and v1[11]["tipo"] == "zoom_batida"
    assert 7 not in v1                                     # "você" sozinho não é motivo: frase sem efeito
    assert v1 == meio(ritmo.planejar({"ritmo": "viral", "_fala": fala}, {"nome": "V1"}, 24.0))   # sem sorteio
    v2 = meio(ritmo.planejar({"ritmo": "viral", "_fala": fala}, {"nome": "V2"}, 24.0))
    assert v2[3]["motivo"] == "pergunta" and v2[3]["tipo"] != v1[3]["tipo"]   # outra versão, outro efeito do motivo


def test_as_3_versoes_nao_coincidem_no_mesmo_motivo_e_a_ia_nao_copia_a_v1():
    fala = _fala([("Bom dia a todos aqui.", 0.0), ("Nunca faça isso em casa.", 3.0),
                  ("Cuidado com o sol depois.", 12.0), ("Agende sua avaliação.", 20.0)])
    proj = {"ritmo": "viral", "_fala": fala, "versoes": [{"nome": n} for n in ("V1", "V2", "V3", "IA")]}
    tipos = {}
    for n in ("V1", "V2", "V3", "IA"):
        ef = {round(e["inicio"]): e["tipo"] for e in ritmo.planejar(proj, {"nome": n}, 26.0) if e.get("motivo")}
        tipos[n] = (ef[3], ef[12])
    assert len({tipos[n][0] for n in ("V1", "V2", "V3")}) == 3          # alerta: 3 efeitos, um por versão
    assert len({tipos[n][1] for n in ("V1", "V2", "V3")}) == 3
    assert tipos["IA"] != tipos["V1"]                                   # a IA não copia a V1


def test_compliance_nao_se_ignora(tmp_path, monkeypatch):
    import pytest
    from divine_studio import painel
    p = _projeto(tmp_path, _fala([("O resultado é garantido.", 0.0), ("Agende.", 3.0)]))
    monkeypatch.setattr(painel, "_pasta", lambda nome: p)
    pid = next(x["id"] for x in alertas.gerar(p)["pontos"] if x["nivel"] == "bloqueia")
    with pytest.raises(ValueError):
        painel.acao_alerta("x", "V1", pid, "ignorar")


# ---------------------------------------------------------------- revisão: compliance na fala trava de verdade


def test_promessa_falada_e_pega_pelo_revisor():
    from divine_studio.compliance import achados_na_fala, revisar
    erro = lambda t: [a.regra for a in revisar({"legenda": "", "conteudo_medico": False}, [t]) if a.nivel == "erro"]
    niveis = lambda t: [x["nivel"] for x in achados_na_fala(_fala([(t, 0.0)]))]
    assert erro("você vai perder 5 kg em um mês")                  # promessa direta: erro, não se confirma
    assert erro("oitenta por cento das pacientes melhoram")
    assert niveis("em duas semanas a mancha some") == ["erro"]       # prazo + resultado + alvo: vermelho
    assert niveis("em 2 semanas a mancha some") == ["erro"]          # o mesmo nível com o número em algarismo
    assert niveis("o inchaço some em uma semana") == ["confirmar"]   # pode ser informação: trava até conferir
    assert not niveis("a gente faz cinco sessões por mês")
    assert not niveis("perder peso sem acompanhamento é perigoso")


def test_frases_corretas_da_clinica_nunca_viram_erro_sem_saida():
    """As frases corretas que uma regex confunde com promessa não travam sem saída: ou passam, ou pedem ✓ Conferi."""
    from divine_studio.compliance import achados_na_fala
    corretas = ["O inchaço some em uma semana.", "O roxinho desaparece em três dias.",
                "O resultado do exame de sangue sai em dois dias.",
                "Depois de três sessões você volta para revisão e sai com o plano.",
                "Na consulta a gente tira duas medidas, cintura e quadril.",
                "Quem perde dez quilos sozinho costuma recuperar."]
    for t in corretas:
        assert all(x["nivel"] == "confirmar" for x in achados_na_fala(_fala([(t, 0.0)]))), t
    for t in corretas[2:5]:                                         # exame, revisão, medidas: nem perguntam
        assert not achados_na_fala(_fala([(t, 0.0)])), t


def test_promessas_que_escapavam_agora_sao_pegas():
    from divine_studio.compliance import achados_na_fala
    for t in ["Em duas semanas de tratamento com o laser de CO2 a mancha some.",
              "Em três sessões a gordura localizada vai embora.", "Com duas sessões a mancha some.",
              "Você vai perder cinco quilinhos.", "Em um mês você desincha."]:
        assert achados_na_fala(_fala([(t, 0.0)])), t
    cortada = _fala([("Em duas semanas,", 0.0)]) + _fala([("a gordura desaparece.", 1.8)])   # pausa de 0,8 s no meio
    achou = achados_na_fala(cortada)
    assert achou and achou[0]["frase"]["partes"] == ["Em duas semanas,", "a gordura desaparece."]


def test_confira_trava_o_aprovar_ate_conferir_e_nao_se_ignora(tmp_path, monkeypatch):
    import pytest
    from divine_studio import painel
    p = _projeto(tmp_path, _fala([("Você sabia disso?", 0.0), ("O roxinho desaparece em três dias.", 2.0),
                                  ("Agende sua avaliação.", 5.0)]))
    monkeypatch.setattr(painel, "_pasta", lambda nome: p)
    ponto = next(x for x in alertas.gerar(p)["pontos"] if x["nivel"] == "confirmar")
    assert {a["tipo"] for a in ponto["acoes"]} == {"cortar_frase", "dublar", "conferir_fala"}
    with pytest.raises(ValueError, match="Confira antes de aprovar"):
        painel.barrar_aprovacao_por_fala(p)
    with pytest.raises(ValueError):
        painel.acao_alerta("x", "V1", ponto["id"], "ignorar")
    painel.acao_alerta("x", "V1", ponto["id"], "conferir_fala")       # você leu: é informação
    d = yaml.safe_load((p / "projeto.yaml").read_text())
    assert d["compliance_conferido"][0]["frase"].startswith("O roxinho") and d["compliance_conferido"][0]["em"]
    painel.barrar_aprovacao_por_fala(p)                               # agora passa
    assert not [x for x in alertas.gerar(p)["pontos"] if x["nivel"] == "confirmar"]


def test_toda_publicacao_pelo_app_pede_a_fala_lida(tmp_path):
    """Postar sozinho E 🚀 Publicar agora pedem a fala desta final lida uma vez (o carimbo libera os dois)."""
    from divine_studio import publicar
    p = _projeto(tmp_path, _fala([("Você sabia disso?", 0.0), ("Agende sua avaliação.", 2.0)]),
                 extra={"legendas": True})
    _final(p, "V1")
    pub = {"versao": "V1", "arquivo": "saida/V1.mp4"}
    for manual in (True, False):
        falta = publicar._compliance_fala(p, {"legendas": True}, pub, manual=manual)
        assert falta and "leia a fala" in falta[0]
    carimbo = publicar.fala_final(p, "V1")["hash"]
    for manual in (True, False):
        assert publicar._compliance_fala(p, {"legendas": True}, {**pub, "fala_lida": carimbo}, manual=manual) == []


def _final(p, versao, palavras=None):
    """Como a exportação grava: a fala conferida da final, por versão e presa ao arquivo dela."""
    fala = palavras if palavras is not None else json.loads((p / "trabalho" / "fala_base.json").read_text())
    (p / "trabalho" / f"fala_final_{versao}.json").write_text(
        json.dumps({"arquivo": f"saida/{versao}.mp4", "palavras": fala}), encoding="utf-8")


def test_fala_conferida_e_por_versao_e_pelo_arquivo(tmp_path):
    """A final da V2 sai limpa depois: o postar sozinho da V1 continua conferindo a fala da V1 (que tem a promessa)."""
    from divine_studio import publicar
    p = _projeto(tmp_path, _fala([("Você sabia disso?", 0.0), ("Esse laser elimina 80% da gordura.", 2.0)]),
                 extra={"legendas": True})
    _final(p, "V1")
    _final(p, "V2", _fala([("Você sabia disso?", 0.0), ("Agende sua avaliação.", 2.0)]))
    v1 = {"versao": "V1", "arquivo": "saida/V1.mp4"}
    assert "compliance na fala" in publicar._compliance_fala(p, {"legendas": True}, v1)[0]
    v2 = {"versao": "V2", "arquivo": "saida/V2.mp4", "fala_lida": publicar.fala_final(p, "V2")["hash"]}
    assert publicar._compliance_fala(p, {"legendas": True}, v2) == []
    # o carimbo lido da V2 não serve para a V1, e uma final de outro arquivo não vale para esta peça
    assert publicar.fala_final(p, "V1")["hash"] != publicar.fala_final(p, "V2")["hash"]
    outro = publicar._compliance_fala(p, {"legendas": True}, {"versao": "V2", "arquivo": "saida/V2_antiga.mp4"})
    assert outro and "exporte a final desta versão" in outro[0]


def test_fala_com_promessa_barra_aprovar_e_postar_sozinho(tmp_path, monkeypatch):
    import pytest
    from divine_studio import painel, publicar
    p = _projeto(tmp_path, _fala([("Você sabia disso?", 0.0), ("Esse laser elimina 80% da gordura.", 2.0)]),
                 extra={"legendas": True})
    with pytest.raises(ValueError, match="Ainda não dá para aprovar"):
        painel.barrar_aprovacao_por_fala(p)
    pub = {"versao": "V1", "arquivo": "saida/V1.mp4"}
    assert publicar._compliance_fala(p, {"legendas": True}, pub) == [
        "a fala desta final não passou pelo revisor de compliance: exporte a final de novo"]
    _final(p, "V1")
    assert "compliance na fala" in publicar._compliance_fala(p, {"legendas": True}, pub)[0]
    d = yaml.safe_load((p / "projeto.yaml").read_text())          # marcada para sair: o aprovar deixa seguir
    d["remover_trechos"] = ["Esse laser elimina 80% da gordura."]
    (p / "projeto.yaml").write_text(yaml.safe_dump(d))
    painel.barrar_aprovacao_por_fala(p)


def test_tirar_a_frase_acha_mesmo_com_muleta_no_meio():
    from divine_studio.corte import marcar_remocoes
    bruto = [{"texto": w} for w in "O laser hum elimina 80% da gordura. Agende sua avaliação.".split()]
    fora = marcar_remocoes(bruto, ["O laser elimina 80% da gordura."])     # texto da legenda (sem o "hum")
    assert sorted(i for i, m in fora.items() if m == "removido no projeto") == list(range(7))
    assert 7 not in fora


def test_take_de_dublagem_e_aparado_e_encaixado_no_trecho(tmp_path):
    from divine_studio.audio import SR, ajustar_take, ler_audio, salvar_wav
    t = np.arange(int(2.3 * SR)) / SR
    voz = np.stack([0.3 * np.sin(2 * np.pi * 220 * t)] * 2, axis=1).astype(np.float32)
    silencio = np.zeros((SR, 2), np.float32)
    salvar_wav(np.vstack([silencio, voz, silencio]), tmp_path / "take.wav")    # 1 s mudo + 2,3 s + 1 s mudo
    r = ajustar_take(tmp_path / "take.wav", tmp_path / "ok.wav", 2.0)
    assert r["tempo"] == 1.15 and abs(r["sobra_s"]) < 0.15
    assert abs(len(ler_audio(tmp_path / "ok.wav")) / SR - 2.0) < 0.2
    longo = ajustar_take(tmp_path / "take.wav", tmp_path / "longo.wav", 1.0)
    assert longo["sobra_s"] > 0.8                                   # não cabe nem acelerando: o painel avisa


def test_pedido_final_segue_por_cima_do_cartao_final(tmp_path, monkeypatch):
    from divine_studio import cli
    from divine_studio.audio import SR
    monkeypatch.setattr("divine_studio.audio.ler_audio", lambda *a, **k: np.full((3 * SR, 2), 0.2, np.float32))
    monkeypatch.setattr("divine_studio.ingest.resolver", lambda p, arq: tmp_path / arq)
    voz = np.full((5 * SR, 2), 0.5, np.float32)
    out = cli._com_dublagem({"audio": {"dublagem": [{"arquivo": "d.wav", "inicio": 4.85}]}}, voz, 5.0)
    assert len(out) >= int(7.8 * SR)                               # os 3 s inteiros, não 0,15 s
    assert abs(out[int(2.0 * SR), 0] - 0.5) < 1e-6                 # sem "fim": a voz original não fica muda


def test_retencao_real_muda_o_que_o_app_prefere():
    from divine_studio import aprendizado
    base = {"status": "postado", "metricas": {"alcance": 1000, "salvamentos": 10}}
    segura = {**base, "caracteristicas": {"duracao": 30, "hook_id": "H1"},
              "metricas": {**base["metricas"], "tempo_medio_s": 20}}
    perde = {**base, "caracteristicas": {"duracao": 30, "hook_id": "H2"},
             "metricas": {**base["metricas"], "tempo_medio_s": 4, "queda_s": 2}}
    med = 12 / 30
    assert aprendizado.pontuar(segura, 1000, med) > aprendizado.pontuar(perde, 1000, med) + 2


def test_modelo_preciso_so_quando_ja_baixado(monkeypatch):
    from divine_studio import transcricao
    monkeypatch.setattr(transcricao, "_estado", lambda: {})
    monkeypatch.setattr(transcricao, "preciso_baixado", lambda nome=None: False)
    assert transcricao.modelo_escolhido() == "small"               # nunca baixa 1,6 GB no meio de uma edição
    monkeypatch.setattr(transcricao, "preciso_baixado", lambda nome=None: True)
    assert transcricao.modelo_escolhido() == "large-v3-turbo"
    monkeypatch.setattr(transcricao, "_estado", lambda: {"lento": "large-v3-turbo"})
    assert transcricao.modelo_escolhido() == "small"               # lento neste Mac: volta para o rápido


# ---------------------------------------------------------------- revisão 3: o que a crítica achou


def test_prazo_falado_no_singular_e_por_extenso_e_vermelho():
    from divine_studio.compliance import achados_na_fala
    nivel = lambda t: [x["nivel"] for x in achados_na_fala(_fala([(t, 0.0)]))]
    for t in ["Na primeira sessão a gordura some.", "Em uma sessão a mancha desaparece.",
              "Já na primeira sessão você vai ver resultado.", "Em uma aplicação a papada some.",
              "Em quinze dias você já vê a diferença.", "Com três sessões a celulite melhora muito.",
              "A mancha some na hora.", "Em duas semanas a gordura desaparece.", "O resultado aparece em duas semanas."]:
        assert nivel(t) == ["erro"], t                               # sem "Conferi": não há frase correta assim
    assert nivel("Em 2 semanas você perde a barriga.") == nivel("Em duas semanas você perde a barriga.") == ["erro"]
    for t in ["O resultado do exame de sangue sai em dois dias.", "Em três dias o roxinho desaparece.",
              "Na primeira consulta a gente vê a mancha de perto.", "O Endolaser é feito em uma sessão e você volta ao trabalho no mesmo dia."]:
        assert nivel(t) == [], t


def test_prazo_com_numero_composto_quantidade_vaga_e_verbo_de_reducao_e_vermelho():
    """Jeitos comuns de prometer que escapavam: 21 e 45 dias por extenso, "apenas", "poucas", "algumas",
    "diminui", "reduz" e "some de vez"."""
    from divine_studio.compliance import achados_na_fala, numeros_falados
    nivel = lambda t: [x["nivel"] for x in achados_na_fala(_fala([(t, 0.0)]))]
    assert numeros_falados("em vinte e um dias", {"vinte": 20, "um": 1}) == "em 21 dias"
    for t in ["Em vinte e um dias a gordura some.", "Em quarenta e cinco dias a gordura some.",
              "Em vinte e cinco dias você vê a diferença.", "Em apenas duas sessões a gordura some.",
              "Em poucas semanas a gordura some.", "Depois de algumas sessões a celulite some.",
              "Em duas semanas a gordura diminui.", "Em trinta dias a celulite reduz.",
              "A gordura localizada some de vez.", "Na primeira sessão você já tem resultado."]:
        assert nivel(t) == ["erro"], t


def test_resultado_nao_conta_como_verbo_e_alvo_ao_mesmo_tempo():
    """Frase de expectativa ou avaliação com "resultado" pede ✓ Conferi (um toque), não trava sem saída."""
    from divine_studio.compliance import achados_na_fala
    nivel = lambda t: [x["nivel"] for x in achados_na_fala(_fala([(t, 0.0)]))]
    for t in ["Na primeira sessão a gente conversa sobre o que esperar do resultado.",
              "Já na primeira sessão a gente avalia e conversa sobre o resultado que você quer.",
              "Depois de três sessões a gente faz uma nova avaliação do resultado.",
              "Em três meses a gente refaz a avaliação para ver o resultado."]:
        assert nivel(t) == ["confirmar"], t


def test_frase_que_nega_a_promessa_pede_conferir_e_nao_trava_sem_saida():
    from divine_studio.compliance import achados_na_fala
    nivel = lambda t: [x["nivel"] for x in achados_na_fala(_fala([(t, 0.0)]))]
    for t in ["Nenhum tratamento tem resultado garantido.", "A depilação a laser não é definitiva.",
              "Antes e depois da sessão, beba bastante água.", "Nenhum tratamento faz a gordura sumir em uma sessão."]:
        assert nivel(t) == ["confirmar"], t                          # ✓ Conferi resolve com um toque
    for t in ["Não tem dor, resultado garantido.", "O resultado é definitivo.", "Olha o antes e depois dessa paciente."]:
        assert nivel(t) == ["erro"], t                               # negação em outra oração não salva a promessa


def test_dublagem_e_efeito_acompanham_a_fala_depois_do_corte():
    from divine_studio import ancoras
    antes = _fala([("Olá a todos.", 0.0), ("Esse laser elimina oitenta por cento.", 3.0), ("Depois vem a parte boa.", 8.0),
                   ("O roxinho some rápido.", 12.0), ("Agende sua avaliação.", 16.0)])
    dub = {"arquivo": "trabalho/dublagem/voz.wav", "inicio": 12.0, "fim": 13.4}
    ef = {"tipo": "zoom_digital", "inicio": 8.4}
    dub = ancoras.ancorar_itens([dub], antes, com_fim=True)[0]
    ef = ancoras.ancorar_itens([ef], antes)[0]
    depois = [w for w in antes if not 3.0 <= w["inicio"] < 6.0]          # a frase do meio saiu: 3 s a menos
    for w in depois:
        if w["inicio"] >= 6.0:
            w["inicio"], w["fim"] = round(w["inicio"] - 3.0, 2), round(w["fim"] - 3.0, 2)
    (d2,), perd = ancoras.reposicionar([dub], depois, com_fim=True)
    (e2,), _ = ancoras.reposicionar([ef], depois)
    assert not perd and abs(d2["inicio"] - 9.0) < 0.01 and abs(d2["fim"] - 10.4) < 0.01
    assert abs(e2["inicio"] - 5.4) < 0.01
    sem = [w for w in depois if not 9.0 <= w["inicio"] < 10.5]          # a frase dublada também saiu
    ok, perd = ancoras.reposicionar([d2], sem, com_fim=True)
    assert not ok and perd                                              # fica de fora desta edição, não cai em outra fala
    movido = ancoras.ancorar_itens([{**e2, "inicio": 0.2}], depois)[0]  # você arrastou: a âncora é refeita
    assert movido["ancora"]["palavras"][0] == "ola"


def test_tirar_frase_sem_corte_limpo_so_tira_a_frase(tmp_path, monkeypatch):
    from divine_studio import painel
    from divine_studio.corte import marcar_remocoes, segmentos_sem_frases
    p = _projeto(tmp_path, _fala([("Você sabia disso?", 0.0), ("Esse laser elimina 80% da gordura.", 2.0),
                                  ("Agende sua avaliação.", 6.0)]))
    monkeypatch.setattr(painel, "_pasta", lambda nome: p)
    ponto = next(x for x in alertas.gerar(p)["pontos"] if x["nivel"] == "bloqueia")
    painel.acao_alerta("x", "V1", ponto["id"], "cortar_frase")
    assert yaml.safe_load((p / "projeto.yaml").read_text())["corte_limpo"] == "so_frases"
    pal = _fala([("Então hum você sabia?", 0.0), ("Esse laser elimina 80% da gordura.", 3.0), ("Agende.", 7.0)])
    fora = marcar_remocoes(pal, ["Esse laser elimina 80% da gordura."], so_pedidas=True)
    assert "hum" not in {pal[i]["texto"] for i in fora}               # muleta fica: só a frase pedida sai
    segs = segmentos_sem_frases(pal, fora, 0.0, 8.0)
    assert segs[0][0] == 0.0 and segs[-1][1] == 8.0 and len(segs) == 2


def test_calibracao_usa_o_que_foi_ao_ar_e_nao_a_previa_nova(tmp_path, monkeypatch):
    from divine_studio import aprendizado
    at = {"passo": 0.5, "curva": [0.6] * 60, "inicio_fraco": False, "zonas": []}
    postada = previsao.prever(at, 32, calibracao={"escala": 1.0})
    outra = previsao.prever({**at, "curva": [0.2] * 20}, 12, calibracao={"escala": 1.0})
    pubs = []
    for i in range(3):
        pasta = tmp_path / f"p{i}"
        (pasta / "trabalho").mkdir(parents=True)
        (pasta / "projeto.yaml").write_text(yaml.safe_dump({"titulo": "t"}), encoding="utf-8")
        previsao.salvar(pasta / "trabalho", "V1", postada, final=True)
        pub = aprendizado.marcar(pasta, "V1", status="postado")         # congela a previsão da final
        assert pub["previsao_postada"] == "trabalho/previsao_postada_V1.json"
        previsao.salvar(pasta / "trabalho", "V1", outra)                # prévia nova da mesma versão, depois
        previsao.salvar(pasta / "trabalho", "V1", outra, final=True)    # e até uma final nova, ainda não postada
        pubs.append({"projeto": f"p{i}", **pub, "metricas": {"tempo_medio_s": 0.6 * postada["tempo_medio_s_bruto"]}})
    monkeypatch.setattr(aprendizado, "PROJETOS", tmp_path)
    monkeypatch.setattr(aprendizado, "todas_publicacoes", lambda: pubs)
    cal = previsao.fator_calibracao()
    nova = previsao.prever(at, 32, calibracao=cal)
    assert abs(nova["tempo_medio_s"] - 0.6 * postada["tempo_medio_s_bruto"]) < 0.05 * postada["tempo_medio_s_bruto"]


def test_aprovar_so_conta_quando_a_final_passa_pelo_revisor(tmp_path):
    from divine_studio import aprendizado, cli
    (tmp_path / "trabalho").mkdir()
    (tmp_path / "projeto.yaml").write_text(yaml.safe_dump({"titulo": "t"}), encoding="utf-8")
    aprendizado.marcar(tmp_path, "V2", aprovacao_pedida="2026-11-08T10:00")      # o que o ✓ Aprovar grava agora
    pub = aprendizado.ler(tmp_path)["publicacoes"][0]
    assert not pub.get("validado") and not pub.get("gostei") and pub["status"] == "rascunho"
    p = {"_pasta": tmp_path, **aprendizado.ler(tmp_path)}
    cli._aprovacao_barrada(p, [({"inicio": 12.0, "texto": "Esse laser elimina 80%"},
                                type("A", (), {"regra": "percentual"})())])
    pub = aprendizado.ler(tmp_path)["publicacoes"][0]
    assert "percentual" in pub["aprovacao_barrada"] and not pub.get("aprovacao_pedida") and not pub.get("validado")


def test_final_que_sai_do_revisor_vira_aprovada_e_validada(tmp_path, monkeypatch):
    from divine_studio import aprendizado, cli
    (tmp_path / "trabalho").mkdir()
    (tmp_path / "saida").mkdir()
    (tmp_path / "projeto.yaml").write_text(yaml.safe_dump({"titulo": "t"}), encoding="utf-8")
    aprendizado.marcar(tmp_path, "V2", aprovacao_pedida="2026-11-08T10:00")
    arq = tmp_path / "saida" / "t_V2_FINAL.mp4"
    arq.write_bytes(b"x")
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(aprendizado, "caracteristicas", lambda d, v: {})
    cli._entregar({"_pasta": tmp_path, **aprendizado.ler(tmp_path)}, arq, "V2")
    pub = aprendizado.ler(tmp_path)["publicacoes"][0]
    assert pub["status"] == "aprovado" and pub["validado"] and pub["gostei"] and not pub.get("aprovacao_pedida")


def test_render_reposiciona_e_grava_os_segundos_novos(tmp_path):
    from divine_studio import ancoras, cli
    antes = _fala([("Olá a todos.", 0.0), ("Frase que sai.", 3.0), ("O roxinho some rápido.", 12.0)])
    dub = ancoras.ancorar_itens([{"arquivo": "trabalho/dublagem/v.wav", "inicio": 12.0, "fim": 13.4}], antes, True)
    efs = ancoras.ancorar_itens([{"tipo": "zoom_digital", "inicio": 3.4}], antes)     # preso à frase que vai sair
    (tmp_path / "trabalho").mkdir()
    (tmp_path / "projeto.yaml").write_text(yaml.safe_dump({"efeitos": efs, "audio": {"dublagem": dub}}), encoding="utf-8")
    nova = [w for w in antes if w["inicio"] < 3.0] + [{**w, "inicio": w["inicio"] - 9, "fim": w["fim"] - 9}
                                                       for w in antes if w["inicio"] >= 12.0]
    p = {"_pasta": tmp_path, "efeitos": efs, "audio": {"dublagem": dub}}
    cli._reposicionar_ancoras(p, nova, tmp_path / "trabalho")
    assert abs(p["audio"]["dublagem"][0]["inicio"] - 3.0) < 0.01 and p["efeitos"] == []     # efeito fica de fora
    d = yaml.safe_load((tmp_path / "projeto.yaml").read_text())
    assert abs(d["audio"]["dublagem"][0]["inicio"] - 3.0) < 0.01 and len(d["efeitos"]) == 1  # nada apagado
    perdidos = json.loads((tmp_path / "trabalho" / "ancoras_perdidas.json").read_text())
    assert perdidos[0]["tipo"] == "efeito"
    assert any(x["regra"] == "ancora_perdida" for x in alertas.gerar(tmp_path)["pontos"])      # vira um "!"


# ---------------------------------------------------------------- revisão de 08/11/2026 (segunda rodada)

def _sem_fala_transcrita(tmp_path, extra):
    (tmp_path / "trabalho").mkdir()
    (tmp_path / "projeto.yaml").write_text(yaml.safe_dump({"titulo": "teste", **extra}), encoding="utf-8")
    return tmp_path


def test_video_falado_sem_transcricao_trava_todas_as_portas(tmp_path):
    """Sem o modelo de fala, o auto desliga legenda e corte limpo: antes, o vídeo falado passava por todas as portas
    sem ninguém ter lido a fala. Agora 'falado' vem do que se ouve (tem_fala) e as quatro portas travam."""
    import argparse
    import pytest
    from divine_studio import cli, compliance, painel, publicar
    extra = {"tem_fala": True, "legendas": False, "corte_limpo": False,
             "clipes": [{"arquivo": "bruto/a.mov"}], "publicacoes": [{"versao": "V1", "aprovacao_pedida": True}]}
    p = _sem_fala_transcrita(tmp_path, extra)
    assert compliance.video_falado(extra)
    ponto = [x for x in alertas.gerar(p)["pontos"] if x["regra"] == "fala_sem_revisor"]
    assert ponto and ponto[0]["nivel"] == "bloqueia" and ponto[0]["acoes"][0]["tipo"] == "instalar_fala"
    with pytest.raises(ValueError, match="não foi transcrita"):
        painel.barrar_aprovacao_por_fala(p)
    assert "não passou pelo revisor" in publicar._compliance_fala(p, extra, {"versao": "V1"}, manual=True)[0]
    a = argparse.Namespace(rapido=False, storyboard=False, forcar=False)
    with pytest.raises(SystemExit, match="não foi transcrita"):
        cli._barrar_fala_nao_lida({**extra, "_pasta": p, "_fala": None}, a, True)
    pub = yaml.safe_load((p / "projeto.yaml").read_text())["publicacoes"][0]
    assert "não foi transcrita" in pub["aprovacao_barrada"] and not pub.get("aprovado")
    cli._barrar_fala_nao_lida({**extra, "_pasta": p, "_fala": None}, argparse.Namespace(rapido=True, storyboard=False,
                                                                                       forcar=False), True)  # prévia segue


def test_video_sem_fala_e_projeto_feito_a_mao():
    from divine_studio import compliance
    assert not compliance.video_falado({"tem_fala": False, "clipes": [{"arquivo": "a"}]})       # b-roll com trilha
    assert not compliance.video_falado({"tipo": "carrossel"})
    assert compliance.video_falado({"clipes": [{"arquivo": "a"}]})                    # à mão, som original: na dúvida, fala
    assert not compliance.video_falado({"clipes": [{"arquivo": "a", "mudo": True}]})
    assert not compliance.video_falado({"audio": {"original": False}, "clipes": [{"arquivo": "a"}]})


def _nivel(*frases):
    from divine_studio.compliance import achados_na_fala
    t, pal = 0.0, []
    for f in frases:
        for w in f.split():
            pal.append({"texto": w, "inicio": round(t, 2), "fim": round(t + 0.3, 2), "conf": 0.95})
            t += 0.35
        t += 0.6
    return sorted({x["nivel"] for x in achados_na_fala(pal, {})})


def test_quem_desmente_a_promessa_tem_saida():
    for f in ("É mito que a celulite desaparece em duas semanas.", "Cuidado com quem fala que a mancha some na hora.",
              "Desconfie de quem promete que a gordura some em uma sessão.",
              "Isso não é verdade: a gordura não some em uma sessão.", "O resultado não é permanente."):
        assert _nivel(f) == ["confirmar"], f
    assert "erro" in _nivel("Dizem que é mito, mas aqui em uma sessão a gordura some.")   # o "mas" volta a afirmar


def test_duas_frases_inteiras_nao_viram_uma_promessa():
    assert _nivel("O retorno é em duas semanas.", "A celulite melhora com o tratamento certo.") == []
    assert _nivel("O protocolo dura duas semanas.", "A celulite some.") == ["confirmar"]
    assert _nivel("Em duas semanas,", "a gordura desaparece.") == ["erro"]       # cortada por uma pausa: um ponto só


def test_promessas_que_escapavam_na_segunda_revisao():
    for f in ("Em três sessões você rejuvenesce dez anos.", "Em uma sessão você fica dez anos mais jovem.",
              "O resultado é permanente.", "Duas semanas depois a gordura sumiu.", "Duas sessões e a gordura some.",
              "Em pouco tempo a gordura some.", "Você vai sair daqui com a pele perfeita.",
              "Em dois meses você está outra pessoa.", "Em uma semana você emagrece.", "Em um mês você vai emagrecer."):
        assert _nivel(f) == ["erro"], f
    assert _nivel("Com o Endolaser a flacidez acaba.") == ["confirmar"]
    for f in ("Indique para outra pessoa que precisa.", "O atendimento é perfeito para quem tem pouco tempo.",
              "A sessão acaba em quarenta minutos.", "Com o tempo a flacidez acaba aparecendo.",
              "Você volta ao trabalho no mesmo dia.", "Em três dias o roxinho desaparece."):
        assert _nivel(f) == [], f


def _calibrar(tmp_path, monkeypatch, at, dur, medias):
    from divine_studio import aprendizado
    bruta = previsao.prever(at, dur, calibracao={"escala": 1.0})
    pubs = []
    for i, m in enumerate(medias):
        pasta = tmp_path / f"p{i}" / "trabalho"
        pasta.mkdir(parents=True)
        previsao.salvar(pasta, "V1", bruta, final=True)
        pubs.append({"projeto": f"p{i}", "versao": "V1", "status": "postado", "metricas": {"tempo_medio_s": m},
                     "caracteristicas": {"duracao": dur, "hook_id": f"H{i}"}})
    monkeypatch.setattr(aprendizado, "PROJETOS", tmp_path)
    monkeypatch.setattr(aprendizado, "todas_publicacoes", lambda: pubs)
    return bruta, pubs


def test_peca_que_segura_muito_nao_e_loop_e_puxa_a_previsao_para_cima(tmp_path, monkeypatch):
    """60 s com 37 s de média: mais do que o modelo dava mesmo no mínimo, mas longe de um loop. Entra na conta."""
    at = {"passo": 0.5, "curva": [0.5] * 120, "inicio_fraco": False, "zonas": []}
    bruta, _ = _calibrar(tmp_path, monkeypatch, at, 60, [37.0, 38.0, 40.0])
    assert previsao.escala_que_reproduz(bruta["entrada"], 37.0) is not None
    cal = previsao.fator_calibracao()
    assert cal["calibrado"] and cal["escala"] < 0.2 and not cal["loops"]   # antes: as 3 iam para "loops"
    nova = previsao.prever(at, 60, calibracao=cal)
    assert abs(nova["tempo_medio_s"] - 38.0) < 0.05 * 38.0                # reproduz a mediana real
    assert "loop" not in previsao.frase(nova)
    # acima do que o modelo dá mesmo no mínimo (e abaixo de 85%): entra com o piso e a tela diz, sem chamar de loop
    assert previsao.escala_que_reproduz(bruta["entrada"], 50.0, {**previsao._cfg(), "calibracao": {
        **previsao._cfg()["calibracao"], "busca": [0.2, 5.0]}}) == 0.2


def test_loop_nao_vira_favorito_e_retencao_e_observado_sobre_esperado(tmp_path, monkeypatch):
    from divine_studio import aprendizado
    at = {"passo": 0.5, "curva": [0.6] * 20, "inicio_fraco": False, "zonas": []}
    bruta, pubs = _calibrar(tmp_path, monkeypatch, at, 10, [15.0, 5.0, 6.0])
    assert aprendizado.retencao(pubs[0]) is None and aprendizado.retencao(pubs[0], "relativa") is None   # loop
    esperado = previsao.tempo_medio_esperado(bruta["entrada"])
    assert abs(aprendizado.retencao(pubs[1], "relativa") - 5.0 / esperado) < 1e-6
    prefs = aprendizado.preferencias()
    assert prefs["hook_id"]["H0"][0] <= prefs["hook_id"]["H2"][0]        # o loop não ganha a nota de retenção


def test_alcance_comparado_na_mesma_idade():
    from divine_studio import aprendizado
    novo = {"metricas": {"alcance": 900}, "historico_metricas": [{"idade_h": 30, "alcance": 900}]}
    assert aprendizado.alcance_comparavel(novo) is None                   # 30 h: ainda subindo, não compara
    hist = [{"idade_h": 24 * d, "alcance": 100 * d} for d in range(1, 31)]
    velho = {"metricas": {"alcance": 3000}, "historico_metricas": hist}
    assert aprendizado.alcance_comparavel(velho) == 700                   # o retrato dos 7 dias, não o de hoje
    podado = aprendizado._podar_historico(hist)
    assert any(h["idade_h"] == 168 for h in podado) and len(podado) <= 9
    assert aprendizado.alcance_comparavel({"metricas": {"alcance": 500}}) == 500   # digitado: o número que há
