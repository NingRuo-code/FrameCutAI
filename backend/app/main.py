from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.models import Video
from app.schemas import VideoResponse
from app.storage import (
    create_video_id,
    delete_video_artifacts,
    save_video_file,
    validate_video_upload,
)


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


@app.delete("/videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(video_id: str, db: Session = Depends(get_db)) -> None:
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")

    db.delete(video)
    db.commit()
    delete_video_artifacts(video_id)
