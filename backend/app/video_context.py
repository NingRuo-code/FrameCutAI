from copy import deepcopy
from math import ceil
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ProviderCall, Video, VideoContext


MOCK_TRANSCRIPT: list[dict[str, Any]] = [
    {
        "start_seconds": 0,
        "end_seconds": 22,
        "text": "We build a FastAPI upload endpoint and keep every Video task traceable.",
    },
    {
        "start_seconds": 24,
        "end_seconds": 55,
        "text": "The Vue workspace calls the local API and shows task state beside the player.",
    },
    {
        "start_seconds": 64,
        "end_seconds": 93,
        "text": "Now the screen shows SSE task events updating the Agent progress timeline.",
    },
    {
        "start_seconds": 121,
        "end_seconds": 146,
        "text": "The SQLAlchemy models on screen record VideoContext and Provider calls.",
    },
]

FIXTURE_SCORES: dict[str, dict[str, Any]] = {
    "segment-001": {
        "source": "fixture",
        "technical_density": 0.82,
        "visual_dependency": 0.78,
        "operation_density": 0.68,
        "novelty": 0.64,
        "watch_value": 0.8,
        "confidence": 0.91,
        "reason": "Opening implementation walkthrough references API and UI state.",
    },
}

VISUAL_KEYWORDS = ("screen", "vue", "api", "sqlalchemy", "model", "timeline", "player")


def create_empty_context(video: Video) -> dict[str, Any]:
    return {
        "video": {
            "id": video.id,
            "title": video.title,
            "original_filename": video.original_filename,
        },
        "stage": "created",
        "stage_history": [],
        "transcript": [],
        "segments": [],
        "evidence": [],
    }


def append_stage(context: dict[str, Any], stage: str, summary: str) -> None:
    context["stage"] = stage
    context["stage_history"].append({"stage": stage, "summary": summary})


def persist_video_context(db: Session, video_id: str, context: dict[str, Any]) -> VideoContext:
    existing = db.scalar(select(VideoContext).where(VideoContext.video_id == video_id))
    payload = deepcopy(context)
    if existing is None:
        existing = VideoContext(video_id=video_id, context_json=payload)
        db.add(existing)
    else:
        existing.context_json = payload
    db.commit()
    db.refresh(existing)
    return existing


def get_video_context(db: Session, video_id: str) -> VideoContext | None:
    return db.scalar(select(VideoContext).where(VideoContext.video_id == video_id))


def record_provider_call(
    db: Session,
    video_id: str,
    provider: str,
    operation: str,
    latency_ms: int,
    input_units: int,
    output_units: int,
    estimated_cost_usd: float,
) -> ProviderCall:
    call = ProviderCall(
        video_id=video_id,
        provider=provider,
        operation=operation,
        latency_ms=latency_ms,
        input_units=input_units,
        output_units=output_units,
        estimated_cost_usd=estimated_cost_usd,
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    return call


def list_provider_calls(db: Session, video_id: str) -> list[ProviderCall]:
    return list(
        db.scalars(
            select(ProviderCall)
            .where(ProviderCall.video_id == video_id)
            .order_by(ProviderCall.id.asc())
        )
    )


def mock_asr_transcript(db: Session, video_id: str) -> list[dict[str, Any]]:
    record_provider_call(
        db,
        video_id=video_id,
        provider="MockASRProvider",
        operation="transcribe",
        latency_ms=42,
        input_units=146,
        output_units=sum(len(entry["text"].split()) for entry in MOCK_TRANSCRIPT),
        estimated_cost_usd=0.0,
    )
    return deepcopy(MOCK_TRANSCRIPT)


def segment_transcript(transcript: list[dict[str, Any]], window_seconds: int = 60) -> list[dict[str, Any]]:
    max_end = max(entry["end_seconds"] for entry in transcript)
    segment_count = ceil(max_end / window_seconds)
    segments: list[dict[str, Any]] = []

    for index in range(segment_count):
        start = index * window_seconds
        end = start + window_seconds
        entries = [
            entry
            for entry in transcript
            if start <= entry["start_seconds"] < end
        ]
        segment_id = f"segment-{index + 1:03d}"
        segments.append(
            {
                "segment_id": segment_id,
                "start_seconds": start,
                "end_seconds": end,
                "transcript_text": " ".join(entry["text"] for entry in entries),
                "score": {},
                "selected_for_vision": False,
                "frames": [],
            }
        )

    return segments


def score_segment(segment: dict[str, Any]) -> dict[str, Any]:
    segment_id = str(segment["segment_id"])
    if segment_id in FIXTURE_SCORES:
        return deepcopy(FIXTURE_SCORES[segment_id])

    text = str(segment["transcript_text"]).lower()
    keyword_hits = sum(1 for keyword in VISUAL_KEYWORDS if keyword in text)
    visual_dependency = min(0.35 + keyword_hits * 0.18, 0.92)
    technical_density = min(0.42 + len(text.split()) / 80, 0.9)
    return {
        "source": "rule-based",
        "technical_density": round(technical_density, 2),
        "visual_dependency": round(visual_dependency, 2),
        "operation_density": 0.58 if keyword_hits else 0.32,
        "novelty": 0.56,
        "watch_value": round((technical_density + visual_dependency) / 2, 2),
        "confidence": 0.74,
        "reason": "Rule-based fallback found visual or implementation keywords.",
    }


def score_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for segment in segments:
        segment["score"] = score_segment(segment)
        segment["selected_for_vision"] = segment["score"]["visual_dependency"] >= 0.55
    return segments


def attach_mock_vision(db: Session, video_id: str, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frame_count = 0
    for segment in segments:
        if not segment["selected_for_vision"]:
            continue

        frame_offsets = (10, 30, 50)
        frames: list[dict[str, Any]] = []
        for frame_index, offset in enumerate(frame_offsets, start=1):
            timestamp = min(segment["start_seconds"] + offset, segment["end_seconds"] - 1)
            frame_id = f"{segment['segment_id']}-frame-{frame_index}"
            frames.append(
                {
                    "frame_id": frame_id,
                    "timestamp_seconds": timestamp,
                    "image_path": f"mock://videos/{video_id}/frames/{frame_id}.jpg",
                    "ocr_text": f"OCR: {segment['segment_id']} shows API, state, and trace data.",
                    "visual_summary": (
                        f"Visual summary for {segment['segment_id']}: code or UI state "
                        "supports the spoken implementation step."
                    ),
                }
            )
        segment["frames"] = frames
        frame_count += len(frames)

    if frame_count:
        record_provider_call(
            db,
            video_id=video_id,
            provider="MockVisionProvider",
            operation="ocr_and_visual_summary",
            latency_ms=65,
            input_units=frame_count,
            output_units=frame_count * 120,
            estimated_cost_usd=0.0,
        )

    return segments


def build_evidence(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for segment in segments:
        if not segment["transcript_text"]:
            continue

        frame_ids = [frame["frame_id"] for frame in segment["frames"]]
        evidence.append(
            {
                "evidence_id": f"evidence-{segment['segment_id']}",
                "segment_id": segment["segment_id"],
                "start_seconds": segment["start_seconds"],
                "end_seconds": segment["end_seconds"],
                "summary": (
                    f"{segment['segment_id']} covers {segment['transcript_text'][:96]}"
                ),
                "transcript_snippet": segment["transcript_text"][:180],
                "frame_ids": frame_ids,
            }
        )
    return evidence
