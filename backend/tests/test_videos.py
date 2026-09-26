from pathlib import Path

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Video


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


def test_video_upload_rejects_unsupported_extension() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/videos",
            files={"file": ("notes.txt", b"not-a-video", "text/plain")},
        )

        assert response.status_code == 400
        assert "Unsupported video type" in response.json()["detail"]
