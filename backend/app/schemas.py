from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VideoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    original_filename: str
    content_type: str
    file_size: int
    status: str
    created_at: datetime
    updated_at: datetime
