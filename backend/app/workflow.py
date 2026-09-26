from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import TaskEvent, Video


MOCK_WORKFLOW_STAGES: tuple[tuple[str, str], ...] = (
    ("asr", "Mock transcript prepared."),
    ("segmenting", "Transcript split into 60-second Segments."),
    ("scoring", "Segments scored for technical and visual value."),
    ("vision", "Selective Frame extraction and mock vision completed."),
    ("document", "Traceable document placeholder prepared."),
)


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


def run_mock_workflow(video_id: str, stages: Iterable[tuple[str, str]] = MOCK_WORKFLOW_STAGES) -> None:
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

        for stage, message in stages:
            record_task_event(
                db,
                video_id=video_id,
                stage=stage,
                level="info",
                message=message,
            )

        video = db.get(Video, video_id)
        if video is not None:
            video.status = "completed"
            db.commit()

        record_task_event(
            db,
            video_id=video_id,
            stage="workflow",
            level="info",
            message="Mock Workflow completed.",
        )
