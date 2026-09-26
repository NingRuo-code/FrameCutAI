from datetime import datetime
from typing import Any

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


class AnalyzeResponse(BaseModel):
    video_id: str
    status: str
    message: str


class TaskEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: str
    stage: str
    level: str
    message: str
    created_at: datetime


class ProviderCallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: str
    provider: str
    operation: str
    latency_ms: int
    input_units: int
    output_units: int
    estimated_cost_usd: float
    created_at: datetime


class VideoContextResponse(BaseModel):
    video_id: str
    context: dict[str, Any]
    provider_calls: list[ProviderCallResponse]
    updated_at: datetime
