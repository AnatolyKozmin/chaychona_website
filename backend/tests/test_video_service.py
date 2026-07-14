"""Юнит-тесты склейки видео: строится корректная команда ffmpeg и
корректно обрабатываются все ветки ошибок (subprocess замокан, ffmpeg не нужен)."""
import types

import pytest

import app.services.video as video
from app.services.video import VideoCompositionError, compose_still_video


def test_compose_builds_command_and_succeeds(tmp_path, monkeypatch):
    out = tmp_path / "out.mp4"
    captured = {}

    def fake_run(cmd, capture_output, text, timeout):
        captured["cmd"] = cmd
        out.write_bytes(b"video-bytes")  # эмулируем результат ffmpeg
        return types.SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(video.subprocess, "run", fake_run)
    compose_still_video(tmp_path / "img.jpg", tmp_path / "a.mp3", out)

    cmd = captured["cmd"]
    assert cmd[0] == video.get_settings().ffmpeg_binary
    assert "-loop" in cmd and "-shortest" in cmd
    assert str(tmp_path / "img.jpg") in cmd
    assert str(tmp_path / "a.mp3") in cmd
    assert cmd[-1] == str(out)
    assert out.read_bytes() == b"video-bytes"


def test_compose_nonzero_exit_raises(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        return types.SimpleNamespace(returncode=1, stderr="boom failure detail")

    monkeypatch.setattr(video.subprocess, "run", fake_run)
    with pytest.raises(VideoCompositionError) as excinfo:
        compose_still_video(tmp_path / "i.jpg", tmp_path / "a.mp3", tmp_path / "o.mp4")
    assert "boom failure detail" in str(excinfo.value)


def test_compose_missing_output_raises(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        return types.SimpleNamespace(returncode=0, stderr="")  # файл не создан

    monkeypatch.setattr(video.subprocess, "run", fake_run)
    with pytest.raises(VideoCompositionError):
        compose_still_video(tmp_path / "i.jpg", tmp_path / "a.mp3", tmp_path / "o.mp4")


def test_compose_binary_not_found_raises(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr(video.subprocess, "run", fake_run)
    with pytest.raises(VideoCompositionError) as excinfo:
        compose_still_video(tmp_path / "i.jpg", tmp_path / "a.mp3", tmp_path / "o.mp4")
    assert "ffmpeg" in str(excinfo.value)


def test_compose_timeout_raises(tmp_path, monkeypatch):
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        raise sp.TimeoutExpired(cmd, 1)

    monkeypatch.setattr(video.subprocess, "run", fake_run)
    with pytest.raises(VideoCompositionError):
        compose_still_video(tmp_path / "i.jpg", tmp_path / "a.mp3", tmp_path / "o.mp4")
