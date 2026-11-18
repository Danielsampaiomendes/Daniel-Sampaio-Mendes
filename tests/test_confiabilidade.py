"""Rodada de confiabilidade (15/11/2026): painel que sempre responde, tarefa que fecha sozinha, código do iPhone com
limite de tentativas, POST só do próprio painel e textos da fala sem apresentação nem dourado em preposição."""
import json
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from divine_studio import auto, painel, roteirista


@pytest.fixture
def servidor(tmp_path, monkeypatch):
    proj = tmp_path / "projetos"
    p = proj / "2026-11-15_x"
    (p / "trabalho").mkdir(parents=True)
    (p / "projeto.yaml").write_text("titulo: X\nversoes: [{nome: V1}]\n", encoding="utf-8")
    q = proj / "2026-11-15_quebrado"
    q.mkdir()
    (q / "projeto.yaml").write_text('titulo: "x\nclipes: [\n', encoding="utf-8")
    monkeypatch.setattr(painel, "PROJETOS", proj)
    monkeypatch.setattr(painel, "TENTATIVAS", {})
    srv = ThreadingHTTPServer(("127.0.0.1", 0), painel.Painel)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def _pedir(url, dados=None, headers=None, corpo=None):
    if dados is not None:
        corpo = json.dumps(dados).encode()
    req = urllib.request.Request(url, data=corpo, headers=headers or {}, method="POST" if corpo is not None else "GET")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


# ---------------------------------------------------------------- o painel sempre responde

def test_projeto_yaml_quebrado_responde_com_frase_clara(servidor):
    for rota in ("/api/dados", "/api/alertas", "/api/sugestoes"):
        st, corpo = _pedir(f"{servidor}{rota}?p=2026-11-15_quebrado")
        assert st == 400, rota
        assert "erro de escrita" in json.loads(corpo)["erro"]


def test_erro_inesperado_vira_resposta_e_fica_no_registro(servidor, monkeypatch):
    def quebra():
        raise RuntimeError("disco cheio")
    monkeypatch.setattr(painel, "listar", quebra)
    st, corpo = _pedir(servidor + "/api/projetos")
    erro = json.loads(corpo)["erro"]
    assert st == 500 and "disco cheio" in erro and "Nada foi apagado" in erro
    registro = (painel.PROJETOS / painel.LOG_ERROS).read_text(encoding="utf-8")
    assert "RuntimeError: disco cheio" in registro and "/api/projetos" in registro
    # o servidor continua de pé e o POST tem a mesma rede de proteção
    monkeypatch.setattr(painel, "fixar_linha", lambda *a: quebra())
    st, corpo = _pedir(servidor + "/api/fixar_linha", {"p": "2026-11-15_x"})
    assert st == 500 and "disco cheio" in json.loads(corpo)["erro"]


def test_registro_de_erros_nao_cresce_sem_fim(tmp_path, monkeypatch):
    monkeypatch.setattr(painel, "PROJETOS", tmp_path)
    (tmp_path / painel.LOG_ERROS).write_text("x" * 900_000, encoding="utf-8")
    painel.registrar_erro("/api/teste", ValueError("ops"))
    texto = (tmp_path / painel.LOG_ERROS).read_text(encoding="utf-8")
    assert len(texto) < 300_000 and texto.rstrip().endswith("ValueError: ops")


# ---------------------------------------------------------------- tarefa fecha sem ninguém olhando

def test_final_termina_com_a_tela_fechada_e_a_aprovacao_fica_registrada(servidor, monkeypatch):
    nome = "2026-11-15_x"
    pasta = painel.PROJETOS / nome
    log = pasta / "trabalho" / "painel_final_t.log"
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    monkeypatch.setattr(painel, "JOBS", {"t": {"id": "t", "projeto": nome, "acao": "final", "estado": "rodando",
                                               "log": str(log), "inicio": time.time(), "proc": proc,
                                               "fh": open(log, "w", encoding="utf-8"), "versoes": ["V1"]}})
    # ninguém consultou /api/job: só de abrir a lista de projetos a final já aparece aprovada
    aprovados = {x["nome"]: x["aprovado"] for x in json.loads(_pedir(servidor + "/api/projetos")[1])}
    assert aprovados[nome] is True
    assert painel.JOBS["t"]["estado"] == "ok"
    assert json.loads((pasta / "trabalho" / "aprovacao.json").read_text(encoding="utf-8"))["versoes"] == ["V1"]
    assert painel._job_do_projeto(nome) is None            # e o projeto está livre para a próxima tarefa
    assert painel.estado("t")["estado"] == "ok"            # consultar depois continua funcionando


def test_tarefa_que_falhou_nao_aprova(servidor, monkeypatch):
    nome = "2026-11-15_x"
    pasta = painel.PROJETOS / nome
    log = pasta / "trabalho" / "painel_final_f.log"
    proc = subprocess.Popen([sys.executable, "-c", "raise SystemExit(1)"])
    proc.wait()
    monkeypatch.setattr(painel, "JOBS", {"f": {"id": "f", "projeto": nome, "acao": "final", "estado": "rodando",
                                               "log": str(log), "inicio": time.time(), "proc": proc,
                                               "fh": open(log, "w", encoding="utf-8"), "versoes": []}})
    assert painel._job_do_projeto(nome) is None and painel.JOBS["f"]["estado"] == "erro"
    assert not (pasta / "trabalho" / "aprovacao.json").exists()


# ---------------------------------------------------------------- código do iPhone e origem do POST

def _entrar(servidor, codigo):
    return _pedir(servidor + "/entrar", corpo=f"codigo={codigo}".encode(),
                  headers={"Content-Type": "application/x-www-form-urlencoded"})


def test_codigo_errado_muitas_vezes_fecha_a_entrada(servidor, monkeypatch):
    monkeypatch.setattr(painel, "LOCAIS", set())
    monkeypatch.setattr(painel.Painel, "codigo", "123456")
    monkeypatch.setattr(painel.time, "sleep", lambda s: None)
    for _ in range(painel.MAX_ERROS_CODIGO):
        assert _entrar(servidor, "000000")[0] == 401
    st, corpo = _entrar(servidor, "123456")                 # nem o código certo entra durante a espera
    assert st == 429 and "Muitas tentativas" in corpo.decode()
    # quem já tinha entrado continua usando
    assert _pedir(servidor + "/api/projetos", headers={"Cookie": "divine=123456"})[0] == 200
    # passada a janela, a entrada abre de novo
    velhos = time.time() - painel.JANELA_CODIGO_S - 5
    painel.TENTATIVAS.update({k: [velhos] * len(v) for k, v in painel.TENTATIVAS.items()})
    req = urllib.request.Request(servidor + "/entrar", data=b"codigo=123456", method="POST")
    opener = urllib.request.build_opener(_SemRedirecionar)
    with pytest.raises(urllib.error.HTTPError) as e:
        opener.open(req)
    assert e.value.code == 303 and "divine=123456" in e.value.headers["Set-Cookie"]


class _SemRedirecionar(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def test_acertar_o_codigo_zera_os_erros_do_aparelho(servidor, monkeypatch):
    monkeypatch.setattr(painel, "LOCAIS", set())
    monkeypatch.setattr(painel.Painel, "codigo", "123456")
    monkeypatch.setattr(painel.time, "sleep", lambda s: None)
    for _ in range(painel.MAX_ERROS_CODIGO - 1):
        _entrar(servidor, "000000")
    opener = urllib.request.build_opener(_SemRedirecionar)
    with pytest.raises(urllib.error.HTTPError) as e:
        opener.open(urllib.request.Request(servidor + "/entrar", data=b"codigo=123456", method="POST"))
    assert e.value.code == 303
    assert not painel.TENTATIVAS.get("127.0.0.1")


def test_post_de_outro_site_e_recusado(servidor):
    antes = (painel.PROJETOS / "2026-11-15_x" / "projeto.yaml").read_text(encoding="utf-8")
    novo = {"p": "2026-11-15_x", "yaml": "titulo: Invadido\n"}
    st, corpo = _pedir(servidor + "/api/salvar", novo, {"Origin": "https://site-qualquer.example"})
    assert st == 403 and "outro site" in json.loads(corpo)["erro"]
    assert _pedir(servidor + "/api/salvar", novo, {"Origin": "null"})[0] == 403
    assert (painel.PROJETOS / "2026-11-15_x" / "projeto.yaml").read_text(encoding="utf-8") == antes
    # o próprio painel (mesma origem, como o Safari manda) e a linha de comando (sem Origin) continuam valendo
    assert _pedir(servidor + "/api/salvar", novo, {"Origin": servidor})[0] == 200
    assert _pedir(servidor + "/api/salvar", {"p": "2026-11-15_x", "yaml": "titulo: X\n"})[0] == 200


# ---------------------------------------------------------------- textos tirados da fala

def _pal(frase_inicio):
    out = []
    for texto, ini in frase_inicio:
        t = ini
        for w in texto.split():
            out.append({"texto": w, "inicio": t, "fim": t + 0.3})
            t += 0.35
    return out


FALA = _pal([("Oi gente, eu sou o Doutor Daniel.", 0.0),
             ("Hoje eu vou falar sobre o laser de CO2 fracionado.", 3.0),
             ("Ele trata a textura da pele, poros e cicatrizes de acne.", 8.0),
             ("Muita gente acha que o laser afina a pele, mas isso é mito.", 13.0),
             ("Em 30 dias você tem 80% de melhora garantida.", 19.0),
             ("A recuperação leva de 5 a 7 dias.", 24.0),
             ("Agende sua avaliação pelo link da bio.", 30.0)])


def test_apresentacao_nao_vira_mensagem_nem_hook():
    plano = roteirista.planejar_regras({"titulo": "Laser CO2"}, FALA)
    textos = [m["titulo"] for m in plano["mensagens"]] + [g[0]["titulo"] for g in plano["ganchos"]]
    assert textos and not [t for t in textos if "Hoje eu vou" in t or "eu sou" in t]
    assert any("mito" in g[0]["titulo"] for g in plano["ganchos"])


def test_efeito_nunca_reforca_frase_que_o_revisor_barra():
    plano = roteirista.planejar_regras({"titulo": "Laser CO2"}, FALA)
    assert [e["na_fala"] for e in plano["efeitos"]] == ["A recuperação leva de"]


@pytest.mark.parametrize("frase, esperado", [
    ("Ele trata a textura da pele, poros e cicatrizes de acne.", "cicatrizes de *acne*"),
    ("Você sabia que a gordura nos braços não sai só com treino?", "com *treino?*"),
    ("O Endolaser age por dentro da pele com fibra fina.", "com *fibra fina*"),      # duas palavras fortes: as duas
    ("Isso é mito", "é *mito*"),
    ("O laser age em camadas profundas no colágeno.", "no *colágeno*"),
    ("Ele estimula o colágeno no seu tempo.", "no *seu tempo*"),                     # frase da marca continua inteira
])
def test_dourado_fica_na_palavra_forte(frase, esperado):
    assert auto._destacar(frase).endswith(esperado)


def test_regras_da_fala_estao_no_config():
    from divine_studio.config import load
    fala = load("roteiros")["fala"]
    assert fala["pular_apresentacao"] and {"de", "no", "com"} <= set(fala["destaque_nao_comeca_em"]) and fala["efeito_so_em_frase_aprovada"]


def test_hdr_sem_zscale_usa_conversao_que_todo_ffmpeg_tem(monkeypatch, tmp_path):
    """FFmpeg do Mac sem o zscale parava com "No such filter: 'zscale'" em vídeo HDR do iPhone."""
    import subprocess
    from divine_studio import ingest
    monkeypatch.setattr(ingest, "_FILTROS", {"zscale": False})
    f = ingest.filtro_hdr()
    assert "zscale" not in f and "tonemap" not in f
    saida = tmp_path / "o.mp4"
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=320x568:d=0.4:r=30",
                        "-vf", "format=yuv420p10le," + f, str(saida)], capture_output=True, text=True)
    assert r.returncode == 0 and saida.stat().st_size > 0, r.stderr
    monkeypatch.setattr(ingest, "_FILTROS", {"zscale": True})
    assert "zscale" in ingest.filtro_hdr()
    monkeypatch.setattr(ingest, "_FILTROS", {})
    assert ingest.tem_filtro("scale") and not ingest.tem_filtro("filtro_que_nao_existe")


def test_filtro_de_acabamento_que_falta_e_pulado_sem_derrubar(monkeypatch, tmp_path):
    """Mesma classe do erro do zscale: FFmpeg sem eq, vignette ou arnndn segue a edição sem o acabamento."""
    import subprocess
    from divine_studio import ingest
    grafo = ("[0:v]scale=64:64,eq=contrast=1.1:saturation=1.2,vignette=angle=PI/5[v0];"
             "[0:a]highpass=f=80,arnndn=m='a,b.rnnn':mix=0.8,loudnorm=I=-16[a0]")
    monkeypatch.setattr(ingest, "_FILTROS", {})
    assert ingest.filtros_seguros(grafo) == grafo                       # tudo existe: nada muda
    monkeypatch.setattr(ingest, "_FILTROS", {"eq": False, "vignette": False, "arnndn": False, "highpass": True})
    monkeypatch.setattr(ingest, "_AVISADOS", set())
    seguro = ingest.filtros_seguros(grafo)
    assert seguro == "[0:v]scale=64:64,null,null[v0];[0:a]highpass=f=80,anull,loudnorm=I=-16[a0]"
    # essencial nunca é trocado, mesmo marcado como ausente
    monkeypatch.setattr(ingest, "_FILTROS", {"scale": False})
    assert ingest.filtros_seguros("scale=64:64") == "scale=64:64"
    # o comando inteiro roda de verdade com os filtros pulados
    monkeypatch.setattr(ingest, "_FILTROS", {"eq": False, "vignette": False})
    saida = tmp_path / "o.mp4"
    ingest.rodar(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=64x64:d=0.3:r=30",
                  "-vf", "eq=contrast=1.1,vignette=angle=PI/5,format=yuv420p", str(saida)])
    assert saida.stat().st_size > 0
    # sem conseguir ler a lista de filtros, o app tenta com tudo (não tira filtro que existe)
    monkeypatch.setattr(ingest, "_FILTROS", {})
    monkeypatch.setattr(ingest, "_LISTA", [set()])
    assert ingest.tem_filtro("eq") is True
