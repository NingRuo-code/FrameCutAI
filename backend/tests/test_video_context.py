from fastapi.testclient import TestClient

from app.main import app


def upload_context_video(client: TestClient) -> str:
    response = client.post(
        "/videos",
        files={"file": ("context-demo.mp4", b"mock-video-context", "video/mp4")},
    )
    assert response.status_code == 201
    return str(response.json()["id"])


def test_mock_workflow_persists_inspectable_video_context() -> None:
    with TestClient(app) as client:
        video_id = upload_context_video(client)

        analyze = client.post(f"/videos/{video_id}/analyze")
        assert analyze.status_code == 202

        response = client.get(f"/videos/{video_id}/context")
        assert response.status_code == 200
        data = response.json()

        context = data["context"]
        assert context["video"]["id"] == video_id
        assert context["stage"] == "completed"
        assert [snapshot["stage"] for snapshot in context["stage_history"]] == [
            "asr",
            "segmenting",
            "scoring",
            "vision",
            "evidence",
        ]

        transcript = context["transcript"]
        assert transcript[0]["start_seconds"] == 0
        assert transcript[0]["end_seconds"] > transcript[0]["start_seconds"]
        assert "FastAPI" in transcript[0]["text"]

        segments = context["segments"]
        assert [segment["segment_id"] for segment in segments] == [
            "segment-001",
            "segment-002",
            "segment-003",
        ]
        assert segments[0]["start_seconds"] == 0
        assert segments[0]["end_seconds"] == 60
        assert segments[0]["score"]["source"] == "fixture"
        assert segments[1]["score"]["source"] == "rule-based"

        visual_segments = [segment for segment in segments if segment["selected_for_vision"]]
        assert visual_segments
        assert all(len(segment["frames"]) == 3 for segment in visual_segments)
        assert visual_segments[0]["frames"][0]["ocr_text"]
        assert visual_segments[0]["frames"][0]["visual_summary"]

        evidence = context["evidence"]
        assert evidence[0]["segment_id"] == "segment-001"
        assert evidence[0]["summary"]
        assert evidence[0]["frame_ids"]

        provider_calls = data["provider_calls"]
        assert {call["provider"] for call in provider_calls} == {
            "MockASRProvider",
            "MockVisionProvider",
        }
        assert all(call["latency_ms"] >= 0 for call in provider_calls)
        assert all(call["estimated_cost_usd"] >= 0 for call in provider_calls)
