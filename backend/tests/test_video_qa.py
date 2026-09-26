from fastapi.testclient import TestClient

from app.main import app


def upload_qa_video(client: TestClient) -> str:
    response = client.post(
        "/videos",
        files={"file": ("qa-demo.mp4", b"mock-qa-video", "video/mp4")},
    )
    assert response.status_code == 201
    return str(response.json()["id"])


def test_current_video_qa_answers_with_evidence_and_persists_log() -> None:
    with TestClient(app) as client:
        video_id = upload_qa_video(client)
        analyze = client.post(f"/videos/{video_id}/analyze")
        assert analyze.status_code == 202

        response = client.post(
            f"/videos/{video_id}/qa",
            json={"question": "How does the video use FastAPI and API task state?"},
        )

        assert response.status_code == 200
        answer = response.json()
        assert answer["source_type"] == "current_video"
        assert answer["refusal_reason"] is None
        assert answer["confidence"] > 0
        assert answer["evidence_segments"]
        assert answer["evidence_segments"][0]["segment_id"] == "segment-001"
        assert answer["evidence_segments"][0]["start_seconds"] == 0
        assert "FastAPI" in answer["answer"]

        history = client.get(f"/videos/{video_id}/qa/history")
        assert history.status_code == 200
        logs = history.json()
        assert len(logs) == 1
        assert logs[0]["question"] == "How does the video use FastAPI and API task state?"
        assert logs[0]["answer"] == answer["answer"]


def test_current_video_qa_refuses_without_current_video_evidence() -> None:
    with TestClient(app) as client:
        video_id = upload_qa_video(client)
        analyze = client.post(f"/videos/{video_id}/analyze")
        assert analyze.status_code == 202

        response = client.post(
            f"/videos/{video_id}/qa",
            json={"question": "What does this video say about Kubernetes autoscaling?"},
        )

        assert response.status_code == 200
        answer = response.json()
        assert answer["source_type"] == "current_video"
        assert answer["answer"] == ""
        assert answer["confidence"] == 0
        assert answer["evidence_segments"] == []
        assert answer["refusal_reason"] == "Not enough current-video Evidence."

        history = client.get(f"/videos/{video_id}/qa/history")
        assert history.status_code == 200
        assert history.json()[0]["refusal_reason"] == "Not enough current-video Evidence."
