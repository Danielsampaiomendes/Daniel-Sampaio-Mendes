"""Laboratório viral: formatos, Radar, caixa de entrada, travas de publicação, automações e envio às redes
(as redes são simuladas: nada sai para a internet nos testes)."""
import datetime as dt
import json
import os
import time
from pathlib import Path

import pytest
import yaml

from divine_studio import aprendizado, automacoes, entrada, lab, publicar, radar, tiktok


def _pub(projeto, versao, formato, alcance, envios=0, conta="dvmedicalspa", tempo_ms=None, dur=30):
    m = {"alcance": alcance, "compartilhamentos": envios}
    if tempo_ms:
        m["tempo_medio_ms"] = tempo_ms
    return {"projeto": projeto, "versao": versao, "status": "postado", "conta": conta, "metricas": m,
            "data_postagem": dt.date.today().isoformat(), "formato_viral": formato,
            "caracteristicas": {"duracao": dur, "formato_viral": formato}}


def test_placar_e_proximos_aprendem(monkeypatch):
    pubs = [_pub("a", "V1", "alto_contraste", 9000, 300, tempo_ms=20000),
            _pub("b", "V1", "alto_contraste", 8000, 250, tempo_ms=19000),
            _pub("c", "V1", "alto_contraste", 9500, 280, tempo_ms=21000),
            _pub("d", "V1", "tendencia", 900, 1), _pub("e", "V1", "tendencia", 700, 0),
            _pub("f", "V1", "tendencia", 800, 0), _pub("g", "V1", "tendencia", 600, 0)]
    monkeypatch.setattr(aprendizado, "todas_publicacoes", lambda: [dict(p) for p in pubs])
    monkeypatch.setattr(lab, "_evidencia_radar", lambda: {})
    tab = {x["formato"]: x for x in lab.placar()}
    assert tab["alto_contraste"]["status"] == "campeão" and tab["alto_contraste"]["testes"] == 3
    assert tab["tendencia"]["status"] == "descartar por enquanto"
    assert tab["alto_contraste"]["retencao"] == pytest.approx(0.67, abs=0.01)
    escolhidos = [x["formato"] for x in lab.proximos(3, semente=1)]
    assert len(set(escolhidos)) == 3 and "tendencia" not in escolhidos
    assert any(tab[f]["testes"] == 0 for f in escolhidos)          # sempre explora algo novo
    plano = lab.plano_semana()
    assert len(plano) == lab._cfg()["lab"]["testes_por_semana"] and all(x["gancho"] for x in plano)


def test_classificar_e_aplicar_em_versoes(monkeypatch):
    assert lab.classificar("Prato de quem vive com fome vs prato que segura a fome") == "alto_contraste"
    assert lab.classificar("Mito ou verdade: colágeno") == "mito_verdade"
    monkeypatch.setattr(aprendizado, "todas_publicacoes", lambda: [])
    p = {"versoes": [{"nome": "V1"}, {"nome": "V2", "formato_viral": "reacao"}, {"nome": "V3"}]}
    lab.aplicar_em_versoes(p)
    assert p["versoes"][1]["formato_viral"] == "reacao"
    assert all(v.get("formato_viral") in lab.formatos() for v in p["versoes"])
    assert not p["versoes"][0].get("estilo_edicao")      # 07/11: o formato não sorteia o visual (papel, neon...)


def test_radar_colar_numeros_outlier_e_roteiro(tmp_path, monkeypatch):
    monkeypatch.setattr(radar, "ARQUIVO", tmp_path / "radar.json")
    texto = """```json
[{"link": "https://www.instagram.com/reel/A1/", "conta": "@nutri", "views": "1,2 mi", "curtidas": "35,4 mil",
  "gancho": "Prato de quem vive com fome vs prato que segura a fome", "formato": "alto contraste"},
 {"link": "https://www.instagram.com/reel/A2/", "conta": "@nutri", "views": "80 mil"},
 {"link": "https://www.instagram.com/reel/A3/", "conta": "@nutri", "views": "60 mil"}]
```"""
    assert radar.importar_texto(texto)["novos"] == 3
    assert radar.importar_texto(texto)["novos"] == 0                   # não duplica
    it = next(i for i in radar.ler() if i["link"].endswith("A1/"))
    assert it["views"] == 1_200_000 and it["curtidas"] == 35_400 and it["outlier"] == 15.0
    assert it["formato_viral"] == "alto_contraste" and it["rede"] == "instagram"
    assert [i["id"] for i in radar.em_alta()] == [it["id"]]            # só o que viralizou
    assert radar.formatos_em_alta() == {"alto_contraste": 1}
    r = radar.roteiro(it["id"], "Endolaser", usar_ia=False)
    assert r["ganchos"] and r["sequencia"] and r["erros_compliance"] == []
    radar.importar_texto("https://www.tiktok.com/@dra.x/video/99 2,5M views 300k curtidas Mito ou verdade?")
    tt = next(i for i in radar.ler() if i["rede"] == "tiktok")
    assert tt["conta"] == "dra.x" and tt["views"] == 2_500_000 and tt["formato_viral"] == "mito_verdade"
    radar.marcar(it["id"], descartado=True)
    assert [i["rede"] for i in radar.em_alta()] == ["tiktok"]        # colado sem comparação: fica no Radar
    assert "#harmonizacaofacial" in radar.missao("instagram") and "TikTok" in radar.missao("tiktok")


def test_entrada_so_pega_video_estavel_e_novo(tmp_path, monkeypatch):
    pasta = tmp_path / "Entrada"
    pasta.mkdir()
    (pasta / "nota.txt").write_text("x")
    velho, novo_ = pasta / "IMG_1.MOV", pasta / "IMG_2.mov"
    velho.write_bytes(b"1" * 10)
    novo_.write_bytes(b"2" * 10)
    antigo = time.time() - 600
    os.utime(velho, (antigo, antigo))
    monkeypatch.setattr(entrada, "pastas", lambda: [pasta])
    monkeypatch.setattr(entrada, "INDICE", tmp_path / "indice.json")
    assert [f.name for f in entrada.pendentes()] == ["IMG_1.MOV"]      # o outro ainda pode estar baixando
    entrada._gravar_indice({entrada._chave(velho): {"projeto": "x"}})
    assert entrada.pendentes() == []
    assert entrada._titulo(Path("IMG_0001.MOV")).startswith("Entrada")
    assert entrada._titulo(Path("Endolaser_bastidor.mov")) == "Endolaser bastidor"


@pytest.fixture
def projeto_pub(tmp_path, monkeypatch):
    raiz = tmp_path / "projetos"
    pasta = raiz / "p1"
    (pasta / "saida").mkdir(parents=True)
    (pasta / "saida" / "final_V1.mp4").write_bytes(b"0" * 2048)
    d = {"titulo": "Teste", "autorizacao_imagem": "sim", "conteudo_medico": False,
         "legenda": "Legenda.\n\nResultados variam de pessoa para pessoa.",
         "publicacoes": [{"versao": "V1", "status": "agendado", "arquivo": "saida/final_V1.mp4",
                          "data_agendada": "2026-01-01", "redes": ["instagram"]}]}
    (pasta / "projeto.yaml").write_text(yaml.safe_dump(d, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(publicar, "PROJETOS", raiz)
    monkeypatch.setattr(aprendizado, "PROJETOS", raiz)
    from divine_studio import instagram
    monkeypatch.setattr(instagram, "configurado", lambda u=None: True)
    monkeypatch.setattr(instagram, "_credenciais", lambda u=None: {"token": "EAAteste", "user_id": "17"})
    return pasta


def test_travas_de_publicacao(projeto_pub):
    motivos = publicar.pode_publicar("p1", "V1")
    assert any("postar sozinho" in m for m in motivos)                  # sem o seu ok, nada sai sozinho
    assert publicar.pode_publicar("p1", "V1", manual=True) == []
    d = yaml.safe_load((projeto_pub / "projeto.yaml").read_text(encoding="utf-8"))
    d["autorizacao_imagem"] = "pendente"
    d["publicacoes"][0]["arquivo"] = "saida/final_V1_PREVIA.mp4"
    d["uso_interno"] = True
    (projeto_pub / "projeto.yaml").write_text(yaml.safe_dump(d, allow_unicode=True), encoding="utf-8")
    motivos = " | ".join(publicar.pode_publicar("p1", "V1", manual=True))
    assert "autorização" in motivos and "uso interno" in motivos and "arquivo final" in motivos


def test_reels_instagram_fluxo_resumable(projeto_pub, monkeypatch):
    chamadas = []

    def falso(url, metodo="GET", campos=None, corpo=None, cab=None):
        chamadas.append((metodo, url, dict(campos or {}), cab))
        if url.endswith("/17/media"):
            return {"id": "C1", "uri": "https://rupload.facebook.com/ig-api-upload/v21.0/C1"}
        if "rupload" in url:
            return {"success": True}
        if url.endswith("/C1"):
            return {"status_code": "FINISHED"}
        if url.endswith("/media_publish"):
            return {"id": "M9"}
        if url.endswith("/M9"):
            return {"permalink": "https://www.instagram.com/reel/XYZ/"}
        raise AssertionError(url)
    monkeypatch.setattr(publicar, "_req", falso)
    r = publicar.publicar("p1", "V1", manual=True)
    assert r == {"instagram": "https://www.instagram.com/reel/XYZ/"}
    assert chamadas[0][2]["media_type"] == "REELS" and chamadas[0][2]["upload_type"] == "resumable"
    up = next(c for c in chamadas if "rupload" in c[1])
    assert up[3]["Authorization"] == "OAuth EAAteste" and up[3]["file_size"] == "2048"
    pub = aprendizado.ler(projeto_pub)["publicacoes"][0]
    assert pub["status"] == "postado" and pub["link"].endswith("XYZ/") and pub["postado_por"] == "manual"


def test_automacao_posta_no_horario(projeto_pub, tmp_path, monkeypatch):
    monkeypatch.setattr(automacoes, "ESTADO", tmp_path / "auto.json")
    monkeypatch.setattr(entrada, "pendentes", lambda: [])
    feitos = []
    monkeypatch.setattr(publicar, "publicar", lambda p, v, manual=False: feitos.append((p, v)) or {"instagram": "ok"})
    agora = dt.datetime(2026, 1, 1, 20, 0)
    automacoes.ciclo(agora)
    assert feitos == []                                                # 'postar sozinho' desligado
    aprendizado.marcar(projeto_pub, "V1", auto_postar=True, hora_agendada="21:30")
    automacoes.ciclo(agora)
    assert feitos == []                                                # ainda não é 21:30
    automacoes.ciclo(agora.replace(hour=21, minute=31))
    automacoes.ciclo(agora.replace(hour=21, minute=40))
    assert feitos == [("p1", "V1")]                                    # uma vez só
    h = automacoes.historico()
    assert h[0]["acao"] == "publicar" and h[0]["ok"]
    automacoes.ligar(2, False)
    assert not automacoes.regras()[2]["ligado"]


def test_tiktok_pkce_e_envio_rascunho(tmp_path, monkeypatch):
    monkeypatch.setattr(tiktok, "ARQUIVO", tmp_path / "tiktok.json")
    tiktok.salvar_app("chave123", "segredo")
    link = tiktok.link_autorizacao()
    assert "client_key=chave123" in link and "code_challenge_method=S256" in link and "video.upload" in link
    with pytest.raises(SystemExit):
        tiktok.retorno("codigo", "estado-errado")
    arq = tmp_path / "v.mp4"
    arq.write_bytes(b"0" * 1000)
    pedidos, subidas = [], []
    monkeypatch.setattr(tiktok, "_api", lambda m, c, corpo=None, campos=None: pedidos.append((c, corpo)) or
                        {"data": {"publish_id": "P1", "upload_url": "https://up"}})
    monkeypatch.setattr(tiktok, "_subir", lambda a, u, p, n: subidas.append((u, p, n)))
    r = tiktok.enviar(arq, "legenda")
    assert r == {"publish_id": "P1", "modo": "rascunho"}
    assert pedidos[0][0] == "post/publish/inbox/video/init/" and pedidos[0][1]["source_info"]["video_size"] == 1000
    assert subidas == [("https://up", 1000, 1)]
