import json
import hashlib
import logging
import threading
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import cv2
from fastapi import HTTPException
from pydantic import BaseModel, Field
from ..biomechanics.angles import joint_angles
from ..ingestion.service import run_media
from .landmarker import PoseTracker

logger = logging.getLogger(__name__)

class AnalysisRequest(BaseModel):
    start_seconds: float = Field(default=0, ge=0, allow_inf_nan=False)
    duration_seconds: float = Field(default=10, ge=1, le=30, allow_inf_nan=False)

class AnalysisService:
    def __init__(self, store, model_path, tracker_factory=PoseTracker):
        self.store, self.model_path, self.tracker_factory = store, Path(model_path), tracker_factory
        self.root = store.root / "analyses"
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="motionlab-pose")
        self.active = False
        for path in self.root.glob("*/job.json"):
            job = json.loads(path.read_text())
            if job["status"] in {"queued", "running"}:
                job.update(status="failed", error="Analysis interrupted by a server restart. Run tracking again.")
                self.save(job)

    def save(self, job):
        directory = self.root / job["analysis_id"]
        directory.mkdir(parents=True, exist_ok=True)
        temporary = directory / "job.tmp"
        temporary.write_text(json.dumps(job))
        temporary.replace(directory / "job.json")

    def get(self, analysis_id):
        if len(analysis_id) != 32 or any(c not in "0123456789abcdef" for c in analysis_id):
            raise HTTPException(404, "Analysis not found.")
        path = self.root / analysis_id / "job.json"
        if not path.exists():
            raise HTTPException(404, "Analysis not found.")
        return json.loads(path.read_text())

    def latest(self, video_id):
        self.store.get(video_id)
        jobs = [json.loads(p.read_text()) for p in self.root.glob("*/job.json")]
        return next(iter(sorted((j for j in jobs if j["video_id"] == video_id), key=lambda j: j["created_at"], reverse=True)), None)

    def start(self, video_id, request):
        metadata, original = self.store.get(video_id)
        if request.start_seconds >= metadata.duration_seconds:
            raise HTTPException(422, "Clip start must be before the end of the video.")
        if not self.model_path.is_file():
            raise HTTPException(503, "Pose model is missing. Download models/pose_landmarker_lite.task using the README instructions.")
        with self.lock:
            if self.active:
                raise HTTPException(409, "Another tracking job is running. Wait for it to finish.")
            job = dict(analysis_id=uuid4().hex, video_id=video_id, view=metadata.view.value,
                       status="queued", progress=0, start_seconds=request.start_seconds,
                       duration_seconds=min(request.duration_seconds, metadata.duration_seconds-request.start_seconds),
                       created_at=datetime.now(timezone.utc).isoformat(), error=None)
            self.save(job)
            self.active = True
            self.executor.submit(self.run, job.copy(), original)
        return job

    def run(self, job, original):
        tracker = None
        try:
            job["status"] = "running"
            self.save(job)
            fps = 15
            frames = []
            with tempfile.TemporaryDirectory(dir=self.root, prefix="frames-") as folder:
                # FFmpeg applies the source display rotation. Regular samples are
                # aligned to video playback time, not inferred from average FPS.
                run_media(["ffmpeg", "-nostdin", "-v", "error", "-xerror",
                           "-ss", str(job["start_seconds"]), "-i", str(original),
                           "-t", str(job["duration_seconds"]), "-map", "0:v:0", "-an",
                           "-vf", f"fps={fps},scale=960:960:force_original_aspect_ratio=decrease",
                           "-q:v", "3", str(Path(folder) / "%06d.jpg")], 180)
                paths = sorted(Path(folder).glob("*.jpg"))
                if not paths:
                    raise ValueError("The selected clip contains no readable frames.")
                tracker = self.tracker_factory(self.model_path)
                for index, path in enumerate(paths):
                    image = cv2.imread(str(path))
                    if image is None:
                        raise ValueError("A sampled frame could not be read.")
                    height, width = image.shape[:2]
                    sample_time = job["start_seconds"] + index / fps
                    landmarks = tracker.detect(cv2.cvtColor(image, cv2.COLOR_BGR2RGB), round(sample_time * 1000))
                    angles = joint_angles(landmarks, width, height) if landmarks else {f"{side}_{name}": None for side in ("left", "right") for name in ("hip", "knee", "ankle")}
                    frames.append(dict(time_seconds=sample_time, landmarks=landmarks, angles=angles))
                    if index % 15 == 0:
                        job["progress"] = round(100 * (index + 1) / len(paths))
                        self.save(job)
                valid = sum(f["landmarks"] is not None for f in frames)
                with self.model_path.open('rb') as model:
                    model_sha256 = hashlib.file_digest(model, 'sha256').hexdigest()
                result = dict(tracking_version="pose-2d-v1", angle_convention="interior-2d-degrees",
                              model_sha256=model_sha256, confidence_threshold=0.6, schema_version=1, video_id=job["video_id"], view=job["view"],
                              method="MediaPipe Pose Landmarker Lite; image-plane estimates", synchronized=False,
                              marker_tracking=False, sample_rate=fps, width=width, height=height,
                              start_seconds=job["start_seconds"], duration_seconds=job["duration_seconds"],
                              detected_frames=valid, total_frames=len(frames), frames=frames)
                result_path = self.root / job["analysis_id"] / "result.json"
                result_path.write_text(json.dumps(result, allow_nan=False))
            job.update(status="completed", progress=100, result_url=f"/api/analyses/{job['analysis_id']}/result")
        except Exception as error:
            logger.exception("Tracking job %s failed", job["analysis_id"])
            message = error.detail if isinstance(error, HTTPException) else str(error)
            job.update(status="failed", error=f"Tracking failed: {message}")
        finally:
            if tracker:
                try:
                    tracker.close()
                except Exception:
                    logger.exception("Could not close the pose detector")
            self.save(job)
            with self.lock:
                self.active = False
