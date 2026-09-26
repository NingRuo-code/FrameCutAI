from fastapi.testclient import TestClient

from app.main import app


def upload_document_video(client: TestClient) -> str:
    response = client.post(
        "/videos",
        files={"file": ("document-demo.mp4", b"mock-document-video", "video/mp4")},
    )
    assert response.status_code == 201
    return str(response.json()["id"])


def test_mock_workflow_generates_traceable_markdown_document() -> None:
    with TestClient(app) as client:
        video_id = upload_document_video(client)

        analyze = client.post(f"/videos/{video_id}/analyze")
        assert analyze.status_code == 202

        response = client.get(f"/videos/{video_id}/document")
        assert response.status_code == 200
        data = response.json()
        markdown = data["markdown"]

        assert data["video_id"] == video_id
        assert markdown.startswith("# FrameCutAI Technical Notes")
        assert "## Summary" in markdown
        assert "## Core Concepts" in markdown
        assert "## Key Steps" in markdown
        assert "## Key Screenshots" in markdown
        assert "## Recommended Watch Segments" in markdown
        assert "## Evidence Index" in markdown
        assert "[Evidence: segment-001 @ 0s-60s]" in markdown
        assert "Transcript:" in markdown
        assert "mock://videos/" in markdown
        assert "Visual summary for segment-001" in markdown
