from fastapi.testclient import TestClient

from app.critic import critique_document
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

        quality = data["quality_summary"]
        assert quality["status"] == "passed"
        assert quality["warning_count"] == 0
        assert quality["warnings"] == []


def test_critic_flags_weak_or_unsupported_documents() -> None:
    context = {
        "segments": [
            {
                "segment_id": "segment-001",
                "start_seconds": 0,
                "end_seconds": 60,
                "selected_for_vision": True,
                "score": {"visual_dependency": 0.9},
                "frames": [{"frame_id": "segment-001-frame-1"}],
            },
            {
                "segment_id": "segment-002",
                "start_seconds": 60,
                "end_seconds": 120,
                "selected_for_vision": True,
                "score": {"visual_dependency": 0.88},
                "frames": [{"frame_id": "segment-002-frame-1"}],
            },
        ],
        "evidence": [
            {
                "segment_id": "segment-001",
                "start_seconds": 0,
                "end_seconds": 60,
            },
            {
                "segment_id": "segment-002",
                "start_seconds": 60,
                "end_seconds": 120,
            },
        ],
    }
    weak_markdown = "\n".join(
        [
            "# FrameCutAI Technical Notes",
            "## Summary",
            "- The system guarantees perfect understanding.",
            "## Key Steps",
            "- segment-001 has a mismatched timestamp. [Evidence: segment-001 @ 0s-30s]",
        ]
    )

    quality = critique_document(context, weak_markdown)
    warning_codes = {warning["code"] for warning in quality["warnings"]}

    assert quality["status"] == "warning"
    assert "missing-evidence-label" in warning_codes
    assert "invalid-evidence-time" in warning_codes
    assert "unsupported-claim" in warning_codes
    assert "missing-high-value-visual" in warning_codes
