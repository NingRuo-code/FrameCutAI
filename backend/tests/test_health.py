from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_local_shell_status() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "service": "FrameCutAI",
            "mode": "local-shell",
            "message": "Backend shell is ready for the workspace.",
        }
