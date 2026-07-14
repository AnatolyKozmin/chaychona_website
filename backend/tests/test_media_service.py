"""Юнит-тесты хранения/разрешения путей медиа (без БД и ffmpeg)."""
import app.services.media as media


def test_save_upload_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "UPLOAD_DIR", tmp_path / "uploads")
    rel = media.save_upload_bytes(b"hello", ".JPG")
    assert rel.startswith("uploads/")
    assert rel.endswith(".jpg")  # расширение приводится к нижнему регистру
    saved = (tmp_path / "uploads") / rel.split("/", 1)[1]
    assert saved.read_bytes() == b"hello"


def test_resolve_media_within_root(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    target = uploads / "x.jpg"
    target.write_bytes(b"1")
    assert media.resolve_media_abspath("uploads/x.jpg") == target.resolve()
    # обратные слэши и ведущий слэш нормализуются
    assert media.resolve_media_abspath("\\uploads\\x.jpg") == target.resolve()


def test_resolve_media_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    assert media.resolve_media_abspath("uploads/nope.jpg") is None
    assert media.resolve_media_abspath(None) is None
    assert media.resolve_media_abspath("") is None


def test_resolve_media_rejects_path_traversal(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    monkeypatch.setattr(media, "MEDIA_ROOT", root)
    secret = tmp_path / "secret.txt"
    secret.write_bytes(b"top-secret")
    assert media.resolve_media_abspath("../secret.txt") is None
