import subprocess

import pytest
from fastapi import HTTPException
from app.ingestion.service import run_media

@pytest.mark.parametrize('command,stage,explanation', [
    (['ffprobe', '-i', '/private/upload.part'], 'metadata inspection', 'container'),
    (['ffmpeg', '-i', '/private/upload.part', '-f', 'null', '-'], 'frame decoding', 'decoder compatibility'),
    (['ffmpeg', '-i', '/private/upload.part', '-c:v', 'libx264', '/private/preview.mp4'], 'preview conversion', 'original decoded successfully'),
])
def test_failed_tool_has_stage_and_redacted_diagnostic(monkeypatch, caplog, command, stage, explanation):
    def fail(*args, **kwargs):
        return subprocess.CompletedProcess(command, 1, '', 'Unsupported color conversion in /private/upload.part\n')
    monkeypatch.setattr(subprocess, 'run', fail)
    with pytest.raises(HTTPException) as caught:
        run_media(command, 30)
    assert caught.value.status_code == 422
    assert stage in caught.value.detail
    assert explanation in caught.value.detail
    assert 'Unsupported color conversion' in caught.value.detail
    assert '/private/upload.part' not in caught.value.detail
    assert '[local video]' in caught.value.detail
    assert stage in caplog.text


def test_preview_timeout_is_identified(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('ffmpeg', 180)
    monkeypatch.setattr(subprocess, 'run', timeout)
    with pytest.raises(HTTPException) as caught:
        run_media(['ffmpeg', '-c:v', 'libx264'], 180)
    assert 'preview conversion timed out after 180 seconds' in caught.value.detail


def test_empty_tool_diagnostic(monkeypatch):
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess(a, 1, '', ''))
    with pytest.raises(HTTPException) as caught:
        run_media(['ffprobe'], 30)
    assert 'no diagnostic output' in caught.value.detail
