from enum import Enum
from pydantic import BaseModel

class View(str, Enum):
    side = "side"
    front = "front"
    rear = "rear"

class VideoMetadata(BaseModel):
    schema_version: int = 1
    label: str = ""
    seatpost_extension_change_mm: float | None = None
    video_id: str
    view: View
    width: int
    height: int
    duration_seconds: float
    frame_rate: float
    average_frame_rate: str
    nominal_frame_rate: str
    time_base: str
    start_time_seconds: float | None
    start_pts: int | None
    duration_ts: int | None
    frame_count: int | None
    codec: str
    pixel_format: str
    rotation_degrees: float
    size_bytes: int
    uploaded_at: str
    source_creation_time: str | None
    preview_url: str | None = None
    content_url: str
