"""Testes das falhas achadas na revisão de 01/11/2026."""
import json
import subprocess
import threading
import urllib.request

import pytest

from divine_studio import corte, exportar, ingest, painel


def _video(caminho, dur=4, audio=True):
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=gray:s=160x284:r=30:d={dur}"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=f=300:d={dur}", "-shortest"]
    subprocess.run(cmd + ["-c:v", "libx264", "-preset", "ultrafast", str(caminho)], check=True)


def test_fim_alem_do_arquivo_e_limitado(tmp_path):
    _video(tmp_path / "a.mp4", 4)
    _video(tmp_path / "b.mp4", 3)
    proj = {"_pasta": tmp_path, "dissolve": 0.4, "zoom_respiro": 0,
            "clipes": [{"arquivo": "a.mp4", "fim": 8}, {"arquivo": "b.mp4"}]}
    meta = ingest.construir_base(proj, 160, 284, tmp_path / "base.mov")
    assert meta["duracao"] == pytest.approx(4 + 3 - 0.4, abs=0.15)
    real = ingest.probe(tmp_path / "base.mov")["duracao"]
    assert real == pytest.approx(meta["duracao"], abs=0.15)


def test_inicio_depois_do_fim_da_erro_claro(tmp_path):
    _video(tmp_path / "a.mp4", 2)
    with pytest.raises(SystemExit, match="início"):
        ingest.construir_base({"_pasta": tmp_path, "clipes": [{"arquivo": "a.mp4", "inicio": 5}]}, 160, 284,
                              tmp_path / "base.mov")


def test_corte_limpo_pula_clipe_sem_audio(tmp_path):
    _video(tmp_path / "mudo.mp4", 2, audio=False)
    chamou = []
    novos, _ = corte.expandir_clipes({"_pasta": tmp_path, "corte_limpo": True, "clipes": [{"arquivo": "mudo.mp4"}]},
                                     lambda a: chamou.append(a) or [])
    assert novos == [{"arquivo": "mudo.mp4"}] and not chamou


def test_cache_da_base_muda_quando_o_bruto_muda(tmp_path):
    from divine_studio.cli import _digital_base
    _video(tmp_path / "IMG_1.MOV", 2)
    p = {"_pasta": tmp_path, "clipes": [{"arquivo": "IMG_1.MOV"}]}
    a = _digital_base(p, [160, 284])
    _video(tmp_path / "IMG_1.MOV", 3)            # reenviado com o mesmo nome
    assert _digital_base(p, [160, 284]) != a


def test_exportacao_nao_deixa_arquivo_com_nome_final_se_falhar(tmp_path):
    with pytest.raises(SystemExit):
        exportar.exportar(tmp_path / "nao_existe.mov", tmp_path / "saida" / "final.mp4")
    assert not (tmp_path / "saida" / "final.mp4").exists()


def test_upload_interrompido_nao_vira_bruto(tmp_path, monkeypatch):
    proj = tmp_path / "projetos"
    p = proj / "2026-11-01_x"
    (p / "bruto").mkdir(parents=True)
    (p / "projeto.yaml").write_text("titulo: X\n")
    monkeypatch.setattr(painel, "PROJETOS", proj)
    srv = painel.ThreadingHTTPServer(("127.0.0.1", 0), painel.Painel)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    import socket
    s = socket.create_connection(("127.0.0.1", srv.server_address[1]))
    s.sendall(b"POST /api/upload?p=2026-11-01_x&nome=IMG.MOV HTTP/1.1\r\nHost: x\r\nContent-Length: 100000\r\n\r\n"
              + b"x" * 5000)
    s.shutdown(socket.SHUT_WR)
    s.recv(4096)
    s.close()
    srv.shutdown()
    assert not (p / "bruto" / "IMG.MOV").exists()
    assert not list((p / "bruto").glob(".*parcial"))


def test_rodizio_da_previa_vale_na_final(tmp_path, monkeypatch):
    """A escolha de fontes/SFX gravada na prévia é reaproveitada mesmo que o histórico mude."""
    from divine_studio import rodizio
    guardado = {"V1": {"fontes": "C"}, "V2": {"fontes": "L"}}
    fixas = [guardado.get(n, {}).get("fontes") for n in ("V1", "V2", "V3")]
    esc = rodizio.escolher_fontes(3, fixas)
    assert esc[:2] == ["C", "L"] and esc[2] not in ("C", "L")


def test_hooks_ficam_no_tema():
    from divine_studio import hooks
    for semente in range(5):
        for h in hooks.sortear(3, tema="Laser de CO2 no corpo", semente=semente):
            txt = (" ".join(h["batidas"]) + h["descricao"]).lower()
            assert not any(x in txt for x in ("cabelo", "sutiã", "bumbum", "bariátrica", "sleeve")), h["id"]
