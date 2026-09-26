import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.config import ACCEPTED_VIDEO_EXTENSIONS, MAX_VIDEO_BYTES, STORAGE_ROOT


def validate_video_upload(file: UploadFile) -> str:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A filename is required.",
        )

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ACCEPTED_VIDEO_EXTENSIONS:
        accepted = ", ".join(sorted(ACCEPTED_VIDEO_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported video type. Accepted extensions: {accepted}.",
        )

    if file.content_type and not (
        file.content_type.startswith("video/")
        or file.content_type == "application/octet-stream"
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be a video.",
        )

    return suffix


def create_video_id() -> str:
    return str(uuid4())


def video_dir(video_id: str) -> Path:
    return STORAGE_ROOT / "videos" / video_id


def save_video_file(video_id: str, file: UploadFile, suffix: str) -> tuple[Path, int]:
    target_dir = video_dir(video_id)
    target_dir.mkdir(parents=True, exist_ok=False)
    target_path = target_dir / f"source{suffix}"

    bytes_written = 0
    with target_path.open("wb") as output:
        while chunk := file.file.read(1024 * 1024):
            bytes_written += len(chunk)
            if bytes_written > MAX_VIDEO_BYTES:
                shutil.rmtree(target_dir, ignore_errors=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Uploaded video is larger than the configured limit.",
                )
            output.write(chunk)

    return target_path, bytes_written


def delete_video_artifacts(video_id: str) -> None:
    shutil.rmtree(video_dir(video_id), ignore_errors=True)
