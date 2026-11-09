import os
from dataclasses import dataclass, field
from pathlib import Path

@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("MOTIONLAB_DATA_DIR", Path(__file__).resolve().parents[2] / "data")))
    max_bytes: int = field(default_factory=lambda: int(os.getenv("MOTIONLAB_MAX_BYTES", 500 * 1024 * 1024)))
    max_duration: float = field(default_factory=lambda: float(os.getenv("MOTIONLAB_MAX_DURATION", "300")))
    model_path: Path = field(default_factory=lambda: Path(os.getenv("MOTIONLAB_POSE_MODEL", Path(__file__).resolve().parents[2] / "models" / "pose_landmarker_lite.task")))
    probe_timeout: float = 30
    decode_timeout: float = 180
