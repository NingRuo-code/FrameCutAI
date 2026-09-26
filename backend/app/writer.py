from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GeneratedDocument


def format_timestamp_range(start_seconds: int, end_seconds: int) -> str:
    return f"{start_seconds}s-{end_seconds}s"


def evidence_label(evidence: dict) -> str:
    return (
        f"[Evidence: {evidence['segment_id']} @ "
        f"{format_timestamp_range(evidence['start_seconds'], evidence['end_seconds'])}]"
    )


def generate_markdown_document(context: dict) -> str:
    video = context["video"]
    segments = context.get("segments", [])
    evidence_items = context.get("evidence", [])
    visual_segments = [segment for segment in segments if segment.get("frames")]
    recommended_segments = sorted(
        segments,
        key=lambda segment: segment.get("score", {}).get("watch_value", 0),
        reverse=True,
    )[:3]

    lines: list[str] = [
        "# FrameCutAI Technical Notes",
        "",
        f"Source Video: {video['original_filename']}",
        "",
        "## Summary",
        "",
    ]

    for evidence in evidence_items[:2]:
        lines.append(f"- {evidence['summary']} {evidence_label(evidence)}")

    lines.extend(
        [
            "",
            "## Core Concepts",
            "",
            "- VideoContext is the shared structure used by Writer, Critic, QA, and debug UI.",
            "- Selective vision keeps screen Evidence only where Segments need visual inspection.",
            "- Provider calls are tracked so latency, units, and estimated cost remain visible.",
            "",
            "## Key Steps",
            "",
        ]
    )

    for segment in segments:
        score = segment.get("score", {})
        timestamp = format_timestamp_range(segment["start_seconds"], segment["end_seconds"])
        lines.append(
            "- "
            f"{segment['segment_id']} ({timestamp}): "
            f"{segment.get('transcript_text') or 'No transcript text.'} "
            f"[Evidence: {segment['segment_id']} @ {timestamp}]"
        )
        lines.append(
            "  - "
            f"Score source: {score.get('source', 'unknown')}; "
            f"visual dependency: {score.get('visual_dependency', 0)}; "
            f"watch value: {score.get('watch_value', 0)}."
        )

    lines.extend(["", "## Key Screenshots", ""])

    if visual_segments:
        for segment in visual_segments:
            for frame in segment["frames"]:
                lines.append(
                    "- "
                    f"{frame['frame_id']} @ {frame['timestamp_seconds']}s: "
                    f"{frame['image_path']}"
                )
                lines.append(f"  - OCR: {frame['ocr_text']}")
                lines.append(f"  - Vision: {frame['visual_summary']}")
    else:
        lines.append("- No visual Frames were selected for this VideoContext.")

    lines.extend(["", "## Recommended Watch Segments", ""])

    for segment in recommended_segments:
        timestamp = format_timestamp_range(segment["start_seconds"], segment["end_seconds"])
        reason = segment.get("score", {}).get("reason", "High-value Segment.")
        lines.append(f"- {segment['segment_id']} @ {timestamp}: {reason}")

    lines.extend(["", "## Evidence Index", ""])

    for evidence in evidence_items:
        lines.append(f"### {evidence['evidence_id']}")
        lines.append("")
        lines.append(f"- Segment: {evidence['segment_id']}")
        lines.append(
            "- Timestamp: "
            f"{format_timestamp_range(evidence['start_seconds'], evidence['end_seconds'])}"
        )
        lines.append(f"- Transcript: {evidence['transcript_snippet']}")
        if evidence["frame_ids"]:
            lines.append(f"- Frames: {', '.join(evidence['frame_ids'])}")
            frame_summaries = [
                frame["visual_summary"]
                for segment in segments
                for frame in segment.get("frames", [])
                if frame["frame_id"] in evidence["frame_ids"]
            ]
            for summary in frame_summaries:
                lines.append(f"- Visual summary: {summary}")
        else:
            lines.append("- Frames: none")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def persist_generated_document(db: Session, video_id: str, markdown: str) -> GeneratedDocument:
    existing = db.scalar(select(GeneratedDocument).where(GeneratedDocument.video_id == video_id))
    if existing is None:
        existing = GeneratedDocument(video_id=video_id, markdown=markdown)
        db.add(existing)
    else:
        existing.markdown = markdown
    db.commit()
    db.refresh(existing)
    return existing


def get_generated_document(db: Session, video_id: str) -> GeneratedDocument | None:
    return db.scalar(select(GeneratedDocument).where(GeneratedDocument.video_id == video_id))
