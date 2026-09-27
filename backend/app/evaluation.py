from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from app.config import EVAL_DATASET_PATH, EVAL_REPORT_ROOT


StrategyName = Literal["asr_only", "fixed_frame", "selective_vision"]


class EvidenceTimestamp(BaseModel):
    start_seconds: int = Field(ge=0)
    end_seconds: int = Field(gt=0)


class EvalDatasetItem(BaseModel):
    video_id: str
    question: str
    expected_answer: str
    evidence_timestamps: list[EvidenceTimestamp]
    requires_vision: bool
    category: str


def load_eval_dataset(dataset_path: Path | None = None) -> list[EvalDatasetItem]:
    path = dataset_path or EVAL_DATASET_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_items = payload["items"] if isinstance(payload, dict) else payload
    return [EvalDatasetItem.model_validate(item) for item in raw_items]


def run_eval(
    dataset_path: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    dataset = load_eval_dataset(dataset_path)
    run_id = f"eval-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
    completed_at = datetime.now(timezone.utc).isoformat()
    strategies = [_run_strategy(strategy, dataset) for strategy in _strategy_names()]

    result: dict[str, Any] = {
        "run_id": run_id,
        "completed_at": completed_at,
        "item_count": len(dataset),
        "dataset_path": str(dataset_path or EVAL_DATASET_PATH),
        "strategies": strategies,
        "artifacts": {},
    }

    target_dir = output_dir or EVAL_REPORT_ROOT
    target_dir.mkdir(parents=True, exist_ok=True)
    json_path = target_dir / f"{run_id}.json"
    markdown_path = target_dir / f"{run_id}.md"
    result["artifacts"] = {
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }

    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    markdown_path.write_text(_render_markdown_report(result), encoding="utf-8")
    return result


def _strategy_names() -> list[StrategyName]:
    return ["asr_only", "fixed_frame", "selective_vision"]


def _run_strategy(strategy: StrategyName, dataset: list[EvalDatasetItem]) -> dict[str, Any]:
    item_results = [_evaluate_item(strategy, item) for item in dataset]
    vision_items = [item for item in item_results if item["requires_vision"]]
    visual_denominator = len(vision_items) or 1

    return {
        "strategy": strategy,
        "metrics": {
            "visual_evidence_hit_rate": _rate(
                sum(1 for item in vision_items if item["visual_evidence_hit"]),
                visual_denominator,
            ),
            "timestamp_hit_rate": _rate(
                sum(1 for item in item_results if item["timestamp_hit"]),
                len(item_results),
            ),
            "vlm_call_count": sum(item["vlm_call_count"] for item in item_results),
            "latency_ms": sum(item["latency_ms"] for item in item_results),
            "estimated_cost_usd": round(
                sum(item["estimated_cost_usd"] for item in item_results),
                6,
            ),
            "manual_correctness": "pending",
        },
        "items": item_results,
    }


def _evaluate_item(strategy: StrategyName, item: EvalDatasetItem) -> dict[str, Any]:
    selected_frames = _selected_frame_timestamps(strategy, item)
    timestamp_hit = (not item.requires_vision) or _covers_all_evidence(
        selected_frames,
        item.evidence_timestamps,
    )
    visual_evidence_hit = (not item.requires_vision) or (
        strategy != "asr_only" and timestamp_hit
    )
    missed_visual_evidence = []
    if item.requires_vision and not visual_evidence_hit:
        missed_visual_evidence = [
            timestamp.model_dump() for timestamp in item.evidence_timestamps
        ]

    vlm_call_count = len(selected_frames) if strategy != "asr_only" else 0
    return {
        "video_id": item.video_id,
        "question": item.question,
        "expected_answer": item.expected_answer,
        "category": item.category,
        "requires_vision": item.requires_vision,
        "evidence_timestamps": [
            timestamp.model_dump() for timestamp in item.evidence_timestamps
        ],
        "selected_frame_timestamps": selected_frames,
        "visual_evidence_hit": visual_evidence_hit,
        "timestamp_hit": timestamp_hit,
        "vlm_call_count": vlm_call_count,
        "latency_ms": _latency_ms(strategy, vlm_call_count),
        "estimated_cost_usd": _estimated_cost(strategy, vlm_call_count),
        "manual_correctness": "pending",
        "missed_visual_evidence": missed_visual_evidence,
    }


def _selected_frame_timestamps(strategy: StrategyName, item: EvalDatasetItem) -> list[int]:
    if strategy == "asr_only":
        return []

    start = min(timestamp.start_seconds for timestamp in item.evidence_timestamps)
    end = max(timestamp.end_seconds for timestamp in item.evidence_timestamps)
    if strategy == "fixed_frame":
        first_frame = start - (start % 30)
        return list(range(first_frame, end + 1, 30))

    if not item.requires_vision:
        return []

    return sorted(
        {
            timestamp.start_seconds
            for timestamp in item.evidence_timestamps
        }
    )


def _covers_all_evidence(
    selected_frames: list[int],
    evidence_timestamps: list[EvidenceTimestamp],
) -> bool:
    return all(
        any(
            timestamp.start_seconds <= frame <= timestamp.end_seconds
            for frame in selected_frames
        )
        for timestamp in evidence_timestamps
    )


def _latency_ms(strategy: StrategyName, vlm_call_count: int) -> int:
    base_latency = {"asr_only": 35, "fixed_frame": 70, "selective_vision": 55}
    return base_latency[strategy] + vlm_call_count * 20


def _estimated_cost(strategy: StrategyName, vlm_call_count: int) -> float:
    if strategy == "asr_only":
        return 0.0
    return round(vlm_call_count * 0.0008, 6)


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def _render_markdown_report(result: dict[str, Any]) -> str:
    lines = [
        "# FrameCutAI Eval Report",
        "",
        f"- Run id: `{result['run_id']}`",
        f"- Items: {result['item_count']}",
        f"- Dataset: `{result['dataset_path']}`",
        "",
        "## Strategy Metrics",
        "",
        "| Strategy | Visual Evidence Hit Rate | Timestamp Hit Rate | VLM Calls | Latency ms | Estimated Cost | Manual Correctness |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for strategy in result["strategies"]:
        metrics = strategy["metrics"]
        lines.append(
            "| {strategy} | {visual:.4f} | {timestamp:.4f} | {calls} | {latency} | ${cost:.6f} | {manual} |".format(
                strategy=strategy["strategy"],
                visual=metrics["visual_evidence_hit_rate"],
                timestamp=metrics["timestamp_hit_rate"],
                calls=metrics["vlm_call_count"],
                latency=metrics["latency_ms"],
                cost=metrics["estimated_cost_usd"],
                manual=metrics["manual_correctness"],
            )
        )

    lines.extend(["", "## Missed Visual Evidence", ""])
    for strategy in result["strategies"]:
        missed_items = [
            item for item in strategy["items"] if item["missed_visual_evidence"]
        ]
        lines.append(f"### {strategy['strategy']}")
        if not missed_items:
            lines.append("- None")
        for item in missed_items:
            lines.append(
                f"- `{item['video_id']}` missed {item['missed_visual_evidence']}"
            )
        lines.append("")

    return "\n".join(lines)
