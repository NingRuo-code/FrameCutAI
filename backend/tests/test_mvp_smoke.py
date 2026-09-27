from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_core_workflow_api_smoke_flow() -> None:
    with TestClient(app) as client:
        upload = client.post(
            "/videos",
            files={"file": ("smoke.mp4", b"mock-smoke-video", "video/mp4")},
        )
        assert upload.status_code == 201
        video_id = upload.json()["id"]

        analyze = client.post(f"/videos/{video_id}/analyze")
        assert analyze.status_code == 202
        assert analyze.json()["status"] == "processing"

        status_response = client.get(f"/videos/{video_id}")
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "completed"

        events = client.get(f"/videos/{video_id}/events/history")
        assert events.status_code == 200
        stages = {event["stage"] for event in events.json()}
        assert {
            "workflow",
            "asr",
            "segmenting",
            "scoring",
            "vision",
            "document",
        }.issubset(stages)

        context = client.get(f"/videos/{video_id}/context")
        assert context.status_code == 200
        context_data = context.json()
        assert context_data["context"]["stage"] == "completed"
        assert context_data["provider_calls"]

        document = client.get(f"/videos/{video_id}/document")
        assert document.status_code == 200
        assert "[Evidence:" in document.json()["markdown"]

        qa_refusal = client.post(
            f"/videos/{video_id}/qa",
            json={"question": "What does this video say about Kubernetes autoscaling?"},
        )
        assert qa_refusal.status_code == 200
        assert qa_refusal.json()["refusal_reason"] == "Not enough current-video Evidence."

        eval_run = client.post("/evals/run")
        assert eval_run.status_code == 200
        eval_data = eval_run.json()
        assert Path(eval_data["artifacts"]["json_path"]).exists()
        assert Path(eval_data["artifacts"]["markdown_path"]).exists()

        cleanup = client.delete(f"/videos/{video_id}")
        assert cleanup.status_code == 204
        assert client.get(f"/videos/{video_id}").status_code == 404
