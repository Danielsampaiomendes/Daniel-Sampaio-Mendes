"""Testes da fase 5: painel local (edição do YAML, segurança de caminhos e servidor com Range)."""
import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest
import yaml

from divine_studio import painel

MODELO = (painel.Path(painel.__file__).parent / "modelo_projeto.yaml").read_text(encoding="utf-8")


def test_trocar_campo_preserva_comentario():
    t = painel.trocar_campo(MODELO, "template", "george")
    assert "template: george  # divine | daniel" in t
    assert yaml.safe_load(t)["template"] == "george"
    assert yaml.safe_load(painel.trocar_campo("titulo: x\n", "formato", "tv"))["formato"] == "tv"


def test_adicionar_clipe_troca_o_exemplo_e_depois_acrescenta():
    t = painel.adicionar_clipe(MODELO, "bruto/IMG_1.MOV")
    d = yaml.safe_load(t)
    assert [c["arquivo"] for c in d["clipes"]] == ["bruto/IMG_1.MOV"]
    t2 = painel.adicionar_clipe(t, "bruto/IMG 2.MOV")
    assert [c["arquivo"] for c in yaml.safe_load(t2)["clipes"]] == ["bruto/IMG_1.MOV", "bruto/IMG 2.MOV"]
    assert yaml.safe_load(t2)["selo"] == ""                     # o resto do arquivo continua igual
    assert yaml.safe_load(painel.adicionar_clipe("titulo: x\nclipes: []\n", "bruto/a.mp4"))["clipes"] == \
        [{"arquivo": "bruto/a.mp4"}]


@pytest.fixture
def servidor(tmp_path, monkeypatch):
    proj = tmp_path / "projetos"
    p = proj / "2026-10-28_x"
    (p / "saida").mkdir(parents=True)
    (p / "projeto.yaml").write_text("titulo: X\nversoes: [{nome: V1}]\n", encoding="utf-8")
    (p / "saida" / "a_V1_PREVIA.mp4").write_bytes(bytes(range(256)) * 4)
    (tmp_path / "segredo.txt").write_text("SEGREDO")
    monkeypatch.setattr(painel, "PROJETOS", proj)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), painel.Painel)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read(), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers


def test_api_lista_e_detalhe(servidor):
    st, corpo, _ = _get(servidor + "/api/projetos")
    lista = json.loads(corpo)
    assert st == 200 and lista[0]["nome"] == "2026-10-28_x" and lista[0]["previas"] == 1
    d = json.loads(_get(servidor + "/api/projeto?p=2026-10-28_x")[1])
    assert d["saidas"][0]["versao"] == "V1" and "divine" in d["templates"]


def test_video_com_range(servidor):
    st, corpo, h = _get(servidor + "/arquivo?p=2026-10-28_x&f=saida/a_V1_PREVIA.mp4", {"Range": "bytes=10-19"})
    assert st == 206 and corpo == bytes(range(10, 20)) and h["Content-Range"] == "bytes 10-19/1024"


@pytest.mark.parametrize("url", ["/arquivo?p=2026-10-28_x&f=../../segredo.txt", "/api/projeto?p=../",
                                 "/arquivo?p=..%2F..&f=segredo.txt"])
def test_nao_sai_da_pasta_de_projetos(servidor, url):
    st, corpo, _ = _get(servidor + url)
    assert st == 400 and b"SEGREDO" not in corpo


def test_salvar_recusa_yaml_quebrado(servidor):
    req = urllib.request.Request(servidor + "/api/salvar", method="POST",
                                 data=json.dumps({"p": "2026-10-28_x", "yaml": "titulo: [quebrado"}).encode(),
                                 headers={"Content-Type": "application/json"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 400
    assert (painel.PROJETOS / "2026-10-28_x" / "projeto.yaml").read_text().startswith("titulo: X")


@pytest.fixture
def servidor_celular(servidor, monkeypatch):
    """Mesmo servidor, mas tratando a conexão como se viesse do iPhone (fora da própria máquina)."""
    monkeypatch.setattr(painel, "LOCAIS", set())
    monkeypatch.setattr(painel.Painel, "codigo", "123456")
    return servidor


def test_celular_sem_codigo_ve_so_a_tela_de_entrada(servidor_celular):
    st, corpo, _ = _get(servidor_celular + "/")
    assert st == 200 and b"Digite o c" in corpo and b"app.js" not in corpo
    assert _get(servidor_celular + "/api/projetos")[0] == 401
    assert _get(servidor_celular + "/arquivo?p=2026-10-28_x&f=saida/a_V1_PREVIA.mp4")[0] == 401
    assert _get(servidor_celular + "/icone-180.png")[0] == 200            # ícone da Tela de Início liberado


def test_celular_com_codigo_entra(servidor_celular):
    import http.client
    from urllib.parse import urlparse
    u = urlparse(servidor_celular)
    c = http.client.HTTPConnection(u.hostname, u.port)
    c.request("POST", "/entrar", body="codigo=000000", headers={"Content-Type": "application/x-www-form-urlencoded"})
    r = c.getresponse()
    assert r.status == 401 and "Set-Cookie" not in r.headers
    r.read()
    c.request("POST", "/entrar", body="codigo=123456", headers={"Content-Type": "application/x-www-form-urlencoded"})
    r = c.getresponse()
    r.read()
    assert r.status == 303 and "divine=123456" in r.headers["Set-Cookie"]
    st, corpo, _ = _get(servidor_celular + "/api/projetos", {"Cookie": "divine=123456"})
    assert st == 200 and json.loads(corpo)[0]["nome"] == "2026-10-28_x"
    assert _get(servidor_celular + "/api/projetos", {"Cookie": "divine=654321"})[0] == 401


def test_sem_modo_celular_ninguem_de_fora_entra(servidor, monkeypatch):
    monkeypatch.setattr(painel, "LOCAIS", set())
    monkeypatch.setattr(painel.Painel, "codigo", None)
    assert _get(servidor + "/api/projetos", {"Cookie": "divine=123456"})[0] == 401


def test_codigo_fica_guardado(tmp_path, monkeypatch):
    monkeypatch.setattr(painel, "PROJETOS", tmp_path)
    a = painel.codigo_celular()
    assert len(a) == 6 and a.isdigit() and painel.codigo_celular() == a
