from fastapi.testclient import TestClient

from app.main import app


def upload_demo_video(client: TestClient) -> str:
    response = client.post(
        "/videos",
        files={"file": ("workflow.mp4", b"mock-video", "video/mp4")},
    )
    assert response.status_code == 201
    return str(response.json()["id"])


def test_analyze_persists_task_events_and_updates_video_status() -> None:
    with TestClient(app) as client:
        video_id = upload_demo_video(client)

        analyze = client.post(f"/videos/{video_id}/analyze")

        assert analyze.status_code == 202
        assert analyze.json()["status"] == "processing"

        detail = client.get(f"/videos/{video_id}")
        assert detail.status_code == 200
        assert detail.json()["status"] == "completed"

        history = client.get(f"/videos/{video_id}/events/history")
        assert history.status_code == 200
        events = history.json()
        stages = [event["stage"] for event in events]
        assert stages[:2] == ["workflow", "workflow"]
        assert {"asr", "segmenting", "scoring", "vision", "document"}.issubset(stages)
        assert stages[-1] == "workflow"
        assert events[-1]["message"] == "Mock Workflow completed."


def test_sse_stream_replays_persisted_task_events() -> None:
    with TestClient(app) as client:
        video_id = upload_demo_video(client)
        analyze = client.post(f"/videos/{video_id}/analyze")
        assert analyze.status_code == 202

        with client.stream("GET", f"/videos/{video_id}/events") as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            body = response.read().decode()

        assert "event: workflow_event" in body
        assert "Mock Workflow completed." in body
        assert '"stage": "asr"' in body
