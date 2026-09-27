import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.evaluation import load_eval_dataset, run_eval
from app.main import app


def test_eval_dataset_loads_required_item_fields() -> None:
    dataset = load_eval_dataset()

    assert dataset
    first_item = dataset[0]
    assert first_item.video_id
    assert first_item.question
    assert first_item.expected_answer
    assert first_item.evidence_timestamps
    assert isinstance(first_item.requires_vision, bool)
    assert first_item.category


def test_eval_runner_compares_three_strategies_and_writes_reports(tmp_path: Path) -> None:
    result = run_eval(output_dir=tmp_path)

    assert {strategy["strategy"] for strategy in result["strategies"]} == {
        "asr_only",
        "fixed_frame",
        "selective_vision",
    }

    fixed_frame = next(
        strategy for strategy in result["strategies"] if strategy["strategy"] == "fixed_frame"
    )
    assert fixed_frame["items"][0]["selected_frame_timestamps"] == [0, 30, 60]
    assert fixed_frame["metrics"]["vlm_call_count"] > 0

    selective = next(
        strategy for strategy in result["strategies"] if strategy["strategy"] == "selective_vision"
    )
    assert selective["metrics"]["visual_evidence_hit_rate"] == 1.0
    assert selective["metrics"]["timestamp_hit_rate"] == 1.0
    assert selective["metrics"]["manual_correctness"] == "pending"
    assert selective["items"][0]["missed_visual_evidence"] == []

    asr_only = next(
        strategy for strategy in result["strategies"] if strategy["strategy"] == "asr_only"
    )
    assert asr_only["items"][0]["missed_visual_evidence"]

    result_path = Path(result["artifacts"]["json_path"])
    report_path = Path(result["artifacts"]["markdown_path"])
    assert result_path.exists()
    assert report_path.exists()
    assert json.loads(result_path.read_text(encoding="utf-8"))["run_id"] == result["run_id"]
    assert "# FrameCutAI Eval Report" in report_path.read_text(encoding="utf-8")


def test_eval_run_api_returns_artifact_paths() -> None:
    with TestClient(app) as client:
        response = client.post("/evals/run")

    assert response.status_code == 200
    data = response.json()
    assert data["item_count"] >= 1
    assert {strategy["strategy"] for strategy in data["strategies"]} == {
        "asr_only",
        "fixed_frame",
        "selective_vision",
    }
    assert data["artifacts"]["json_path"].endswith(".json")
    assert data["artifacts"]["markdown_path"].endswith(".md")
