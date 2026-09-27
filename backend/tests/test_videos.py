from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import storage
from app.database import SessionLocal
from app.main import app
from app.models import Video
from app.storage import video_dir


def test_video_upload_list_detail_and_cleanup() -> None:
    with TestClient(app) as client:
        upload = client.post(
            "/videos",
            files={"file": ("demo.mp4", b"fake-video-bytes", "video/mp4")},
        )

        assert upload.status_code == 201
        created = upload.json()
        assert created["title"] == "demo"
        assert created["original_filename"] == "demo.mp4"
        assert created["content_type"] == "video/mp4"
        assert created["file_size"] == len(b"fake-video-bytes")
        assert created["status"] == "uploaded"

        with SessionLocal() as db:
            video = db.get(Video, created["id"])
            assert video is not None
            stored_path = Path(video.file_path)
            assert stored_path.exists()
            assert stored_path.parts[-3:-1] == ("videos", created["id"])

        listing = client.get("/videos")
        assert listing.status_code == 200
        assert any(video["id"] == created["id"] for video in listing.json())

        detail = client.get(f"/videos/{created['id']}")
        assert detail.status_code == 200
        assert detail.json()["id"] == created["id"]

        delete = client.delete(f"/videos/{created['id']}")
        assert delete.status_code == 204
        assert not stored_path.exists()
        assert not stored_path.parent.exists()

        missing = client.get(f"/videos/{created['id']}")
        assert missing.status_code == 404


def test_video_media_endpoint_serves_uploaded_video_bytes() -> None:
    with TestClient(app) as client:
        upload = client.post(
            "/videos",
            files={"file": ("playable.mp4", b"fake-playable-video", "video/mp4")},
        )
        assert upload.status_code == 201
        created = upload.json()

        media = client.get(f"/videos/{created['id']}/media")

        assert media.status_code == 200
        assert media.content == b"fake-playable-video"
        assert media.headers["content-type"].startswith("video/mp4")


def test_video_upload_rejects_unsupported_extension() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/videos",
            files={"file": ("notes.txt", b"not-a-video", "text/plain")},
        )

        assert response.status_code == 400
        assert "Unsupported video type" in response.json()["detail"]


def test_video_upload_rejects_path_like_filename() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/videos",
            files={"file": ("../escape.mp4", b"fake-video", "video/mp4")},
        )

        assert response.status_code == 400
        assert "path separators" in response.json()["detail"]


def test_video_upload_rejects_files_over_configured_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(storage, "MAX_VIDEO_BYTES", 4)

    with TestClient(app) as client:
        response = client.post(
            "/videos",
            files={"file": ("too-large.mp4", b"larger-than-four", "video/mp4")},
        )

        assert response.status_code == 413
        assert "larger than the configured limit" in response.json()["detail"]


def test_video_storage_rejects_unsafe_video_ids() -> None:
    with pytest.raises(HTTPException):
        video_dir("../escape")
