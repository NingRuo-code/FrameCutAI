from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import TaskEvent, Video
from app.video_context import (
    append_stage,
    attach_mock_vision,
    build_evidence,
    create_empty_context,
    mock_asr_transcript,
    persist_video_context,
    score_segments,
    segment_transcript,
)
from app.writer import generate_markdown_document, persist_generated_document


def record_task_event(
    db: Session,
    video_id: str,
    stage: str,
    level: str,
    message: str,
) -> TaskEvent:
    event = TaskEvent(
        video_id=video_id,
        stage=stage,
        level=level,
        message=message,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_task_events(db: Session, video_id: str) -> list[TaskEvent]:
    return (
        db.query(TaskEvent)
        .filter(TaskEvent.video_id == video_id)
        .order_by(TaskEvent.id.asc())
        .all()
    )


def run_mock_workflow(video_id: str, _: Iterable[tuple[str, str]] = ()) -> None:
    with SessionLocal() as db:
        video = db.get(Video, video_id)
        if video is None:
            return

        video.status = "processing"
        db.commit()
        record_task_event(
            db,
            video_id=video_id,
            stage="workflow",
            level="info",
            message="Mock Workflow started.",
        )

        context = create_empty_context(video)

        context["transcript"] = mock_asr_transcript(db, video_id)
        append_stage(context, "asr", "Mock transcript prepared.")
        persist_video_context(db, video_id, context)
        record_task_event(db, video_id, "asr", "info", "Mock transcript prepared.")

        context["segments"] = segment_transcript(context["transcript"])
        append_stage(context, "segmenting", "Transcript split into 60-second Segments.")
        persist_video_context(db, video_id, context)
        record_task_event(
            db,
            video_id,
            "segmenting",
            "info",
            "Transcript split into 60-second Segments.",
        )

        context["segments"] = score_segments(context["segments"])
        append_stage(context, "scoring", "Segments scored for technical and visual value.")
        persist_video_context(db, video_id, context)
        record_task_event(
            db,
            video_id,
            "scoring",
            "info",
            "Segments scored for technical and visual value.",
        )

        context["segments"] = attach_mock_vision(db, video_id, context["segments"])
        append_stage(context, "vision", "Selective Frame extraction and mock vision completed.")
        persist_video_context(db, video_id, context)
        record_task_event(
            db,
            video_id,
            "vision",
            "info",
            "Selective Frame extraction and mock vision completed.",
        )

        context["evidence"] = build_evidence(context["segments"])
        append_stage(context, "evidence", "Evidence summaries prepared from transcript and Frames.")
        persist_video_context(db, video_id, context)

        markdown = generate_markdown_document(context)
        persist_generated_document(db, video_id, markdown)
        record_task_event(
            db,
            video_id,
            "document",
            "info",
            "Traceable document placeholder prepared.",
        )

        video = db.get(Video, video_id)
        if video is not None:
            video.status = "completed"
            db.commit()

        context["stage"] = "completed"
        persist_video_context(db, video_id, context)

        record_task_event(
            db,
            video_id=video_id,
            stage="workflow",
            level="info",
            message="Mock Workflow completed.",
        )
