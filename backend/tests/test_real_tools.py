"""Integración con herramientas reales del sistema (se omiten si no están instaladas)."""
import shutil
import subprocess

import pytest

from app.config import get_settings
from app.services import antivirus
from conftest import contribute, register

defender = antivirus.DefenderScanner()


@pytest.mark.skipif(not defender.available(), reason="Microsoft Defender no disponible")
def test_microsoft_defender_real(flow):
    antivirus.set_scanner_override(defender)
    col = register("col@prueba.test", "COLABORADOR")
    c = contribute(col, flow["case"]["code"], "FOTO").json()
    assert c["file"]["scan_engine"] == defender.name
    assert c["file"]["status"] == "DISPONIBLE", c["file"]["status_detail"]


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="FFmpeg no disponible")
def test_video_genera_copia_segura_con_ffmpeg(flow, tmp_path):
    src = tmp_path / "v.mp4"
    subprocess.run([get_settings().resolved_ffmpeg(), "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=10",
                    "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-metadata", "title=SECRETO", str(src)], check=True, timeout=60)
    col = register("col@prueba.test", "COLABORADOR")
    c = contribute(col, flow["case"]["code"], "VIDEO", content=src.read_bytes(), name="v.mp4").json()
    f = c["file"]
    assert f["status"] == "DISPONIBLE", f["status_detail"]
    assert f["has_playback"] and 1.5 < f["media_info"]["duration_s"] < 2.5
    r = flow["rev"].get(f"/api/files/{f['id']}/content?variant=playback")
    assert r.status_code == 200 and r.headers["content-type"] == "video/mp4"
    assert b"SECRETO" not in r.content  # metadatos eliminados en la copia de reproducción


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="FFmpeg no disponible")
def test_video_falso_rechazado(flow):
    col = register("col@prueba.test", "COLABORADOR")
    fake = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 500
    c = contribute(col, flow["case"]["code"], "VIDEO", content=fake, name="x.mp4").json()
    assert c["file"]["status"] == "RECHAZADO_FORMATO"
