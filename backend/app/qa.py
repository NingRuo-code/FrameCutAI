import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import QALog


STOP_WORDS = {
    "about",
    "does",
    "this",
    "that",
    "the",
    "use",
    "uses",
    "video",
    "what",
    "when",
    "where",
    "which",
    "with",
}


def question_terms(question: str) -> set[str]:
    terms = {
        term.lower()
        for term in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", question)
    }
    return terms - STOP_WORDS


def evidence_search_text(evidence: dict[str, Any], segments: dict[str, dict[str, Any]]) -> str:
    segment = segments.get(evidence["segment_id"], {})
    frame_text = " ".join(
        " ".join(
            [
                str(frame.get("ocr_text", "")),
                str(frame.get("visual_summary", "")),
            ]
        )
        for frame in segment.get("frames", [])
    )
    return " ".join(
        [
            str(evidence.get("summary", "")),
            str(evidence.get("transcript_snippet", "")),
            str(segment.get("transcript_text", "")),
            frame_text,
        ]
    ).lower()


def evidence_response(evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "segment_id": evidence["segment_id"],
        "start_seconds": evidence["start_seconds"],
        "end_seconds": evidence["end_seconds"],
        "summary": evidence["summary"],
        "transcript_snippet": evidence["transcript_snippet"],
        "frame_ids": evidence["frame_ids"],
    }


def answer_from_context(context: dict[str, Any], question: str) -> dict[str, Any]:
    terms = question_terms(question)
    segments = {segment["segment_id"]: segment for segment in context.get("segments", [])}
    evidence_items = context.get("evidence", [])

    matches: list[tuple[int, dict[str, Any]]] = []
    for evidence in evidence_items:
        search_text = evidence_search_text(evidence, segments)
        hit_count = sum(1 for term in terms if term in search_text)
        if hit_count > 0:
            matches.append((hit_count, evidence))

    matches.sort(key=lambda item: item[0], reverse=True)
    selected = [evidence for _, evidence in matches[:2]]

    if not selected:
        return {
            "answer": "",
            "source_type": "current_video",
            "evidence_segments": [],
            "confidence": 0.0,
            "refusal_reason": "Not enough current-video Evidence.",
        }

    evidence_segments = [evidence_response(evidence) for evidence in selected]
    answer_parts = [
        (
            f"{evidence['summary']} "
            f"(Segment {evidence['segment_id']} @ "
            f"{evidence['start_seconds']}s-{evidence['end_seconds']}s)"
        )
        for evidence in evidence_segments
    ]
    confidence = min(0.55 + 0.15 * len(selected), 0.9)

    return {
        "answer": " ".join(answer_parts),
        "source_type": "current_video",
        "evidence_segments": evidence_segments,
        "confidence": round(confidence, 2),
        "refusal_reason": None,
    }


def persist_qa_log(
    db: Session,
    video_id: str,
    question: str,
    qa_result: dict[str, Any],
) -> QALog:
    log = QALog(
        video_id=video_id,
        question=question,
        answer=qa_result["answer"],
        source_type=qa_result["source_type"],
        evidence_segments=qa_result["evidence_segments"],
        confidence=qa_result["confidence"],
        refusal_reason=qa_result["refusal_reason"],
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def list_qa_logs(db: Session, video_id: str) -> list[QALog]:
    return list(
        db.scalars(
            select(QALog)
            .where(QALog.video_id == video_id)
            .order_by(QALog.created_at.desc(), QALog.id.desc())
        )
    )
