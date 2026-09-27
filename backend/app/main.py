from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.responses import FileResponse, StreamingResponse

from app.database import SessionLocal, get_db, init_db
from app.critic import critique_document, make_warning
from app.evaluation import run_eval
from app.models import GeneratedDocument, ProviderCall, QALog, TaskEvent, Video, VideoContext
from app.qa import answer_from_context, list_qa_logs, persist_qa_log
from app.schemas import (
    AnalyzeResponse,
    DocumentResponse,
    EvalRunResponse,
    QARequest,
    QAResponse,
    ProviderCallResponse,
    TaskEventResponse,
    VideoContextResponse,
    VideoResponse,
)
from app.storage import (
    create_video_id,
    delete_video_artifacts,
    save_video_file,
    validate_video_upload,
)
from app.workflow import list_task_events, record_task_event, run_mock_workflow
from app.video_context import get_video_context, list_provider_calls
from app.writer import get_generated_document


class HealthResponse(BaseModel):
    status: str
    service: str
    mode: str
    message: str


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(
    title="FrameCutAI API",
    description="Local API shell for the FrameCutAI selective-vision Video Agent.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="FrameCutAI",
        mode="local-shell",
        message="Backend shell is ready for the workspace.",
    )


@app.post("/videos", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
def upload_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> Video:
    suffix = validate_video_upload(file)
    video_id = create_video_id()
    stored_path, file_size = save_video_file(video_id, file, suffix)
    title = Path(file.filename or stored_path.name).stem

    video = Video(
        id=video_id,
        title=title,
        original_filename=file.filename or stored_path.name,
        content_type=file.content_type or "application/octet-stream",
        file_path=str(stored_path),
        file_size=file_size,
        status="uploaded",
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


@app.get("/videos", response_model=list[VideoResponse])
def list_videos(db: Session = Depends(get_db)) -> list[Video]:
    return list(db.scalars(select(Video).order_by(Video.created_at.desc())))


@app.get("/videos/{video_id}", response_model=VideoResponse)
def get_video(video_id: str, db: Session = Depends(get_db)) -> Video:
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")
    return video


@app.get("/videos/{video_id}/media")
def get_video_media(video_id: str, db: Session = Depends(get_db)) -> FileResponse:
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")

    source_path = Path(video.file_path)
    if not source_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video media not found.",
        )

    return FileResponse(
        source_path,
        media_type=video.content_type,
        filename=video.original_filename,
    )


@app.post(
    "/videos/{video_id}/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def analyze_video(
    video_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> AnalyzeResponse:
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")

    video.status = "processing"
    db.commit()
    record_task_event(
        db,
        video_id=video_id,
        stage="workflow",
        level="info",
        message="Mock Workflow queued.",
    )
    background_tasks.add_task(run_mock_workflow, video_id)
    return AnalyzeResponse(
        video_id=video_id,
        status="processing",
        message="Mock Workflow queued.",
    )


@app.get("/videos/{video_id}/events/history", response_model=list[TaskEventResponse])
def get_video_event_history(video_id: str, db: Session = Depends(get_db)) -> list[TaskEventResponse]:
    if db.get(Video, video_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")
    return [TaskEventResponse.model_validate(event) for event in list_task_events(db, video_id)]


@app.get("/videos/{video_id}/context", response_model=VideoContextResponse)
def get_video_context_response(video_id: str, db: Session = Depends(get_db)) -> VideoContextResponse:
    if db.get(Video, video_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")

    context = get_video_context(db, video_id)
    if context is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VideoContext not found.",
        )

    provider_calls = [
        ProviderCallResponse.model_validate(call)
        for call in list_provider_calls(db, video_id)
    ]
    return VideoContextResponse(
        video_id=video_id,
        context=context.context_json,
        provider_calls=provider_calls,
        updated_at=context.updated_at,
    )


@app.get("/videos/{video_id}/document", response_model=DocumentResponse)
def get_video_document(video_id: str, db: Session = Depends(get_db)) -> DocumentResponse:
    if db.get(Video, video_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")

    document = get_generated_document(db, video_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    context = get_video_context(db, video_id)
    if context is None:
        quality_summary = {
            "status": "warning",
            "warning_count": 1,
            "warnings": [
                make_warning(
                    "missing-video-context",
                    "Document cannot be checked because VideoContext is missing.",
                )
            ],
        }
    else:
        quality_summary = critique_document(context.context_json, document.markdown)

    return DocumentResponse(
        video_id=video_id,
        markdown=document.markdown,
        quality_summary=quality_summary,
        updated_at=document.updated_at,
    )


@app.post("/videos/{video_id}/qa", response_model=QAResponse)
def ask_video_question(
    video_id: str,
    request: QARequest,
    db: Session = Depends(get_db),
) -> QAResponse:
    if db.get(Video, video_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")

    context = get_video_context(db, video_id)
    if context is None:
        qa_result = {
            "answer": "",
            "source_type": "current_video",
            "evidence_segments": [],
            "confidence": 0.0,
            "refusal_reason": "VideoContext is not available for this Video.",
        }
    else:
        qa_result = answer_from_context(context.context_json, request.question)

    log = persist_qa_log(db, video_id, request.question, qa_result)
    return QAResponse.model_validate(log)


@app.post("/evals/run", response_model=EvalRunResponse)
def run_mvp_eval() -> EvalRunResponse:
    return EvalRunResponse.model_validate(run_eval())


@app.get("/videos/{video_id}/qa/history", response_model=list[QAResponse])
def get_video_qa_history(video_id: str, db: Session = Depends(get_db)) -> list[QAResponse]:
    if db.get(Video, video_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")
    return [QAResponse.model_validate(log) for log in list_qa_logs(db, video_id)]


def format_sse_event(event: TaskEventResponse) -> str:
    payload = event.model_dump(mode="json")
    return f"id: {event.id}\nevent: workflow_event\ndata: {json.dumps(payload)}\n\n"


@app.get("/videos/{video_id}/events")
async def stream_video_events(video_id: str) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        last_event_id = 0

        while True:
            with SessionLocal() as db:
                video = db.get(Video, video_id)
                if video is None:
                    not_found = TaskEventResponse(
                        id=0,
                        video_id=video_id,
                        stage="workflow",
                        level="error",
                        message="Video not found.",
                        created_at=datetime.now(timezone.utc),
                    )
                    yield format_sse_event(not_found)
                    return

                events = [
                    event
                    for event in list_task_events(db, video_id)
                    if event.id > last_event_id
                ]
                for event in events:
                    last_event_id = event.id
                    yield format_sse_event(TaskEventResponse.model_validate(event))

                if video.status in {"completed", "failed"} and not events:
                    return

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@app.delete("/videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(video_id: str, db: Session = Depends(get_db)) -> None:
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")

    for qa_log in db.scalars(select(QALog).where(QALog.video_id == video_id)):
        db.delete(qa_log)
    for document in db.scalars(select(GeneratedDocument).where(GeneratedDocument.video_id == video_id)):
        db.delete(document)
    for provider_call in db.scalars(select(ProviderCall).where(ProviderCall.video_id == video_id)):
        db.delete(provider_call)
    for context in db.scalars(select(VideoContext).where(VideoContext.video_id == video_id)):
        db.delete(context)
    for event in db.scalars(select(TaskEvent).where(TaskEvent.video_id == video_id)):
        db.delete(event)
    db.delete(video)
    db.commit()
    delete_video_artifacts(video_id)
