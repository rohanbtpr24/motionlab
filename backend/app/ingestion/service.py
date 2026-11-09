import json
import logging
import re
import math
import subprocess
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from .models import VideoMetadata, View
from ..config import Settings


logger = logging.getLogger(__name__)


def media_stage(args: list[str]) -> str:
    if args[0] == "ffprobe":
        return "metadata inspection"
    return "preview conversion" if "libx264" in args else "frame decoding"


def media_diagnostic(stderr: str, args: list[str]) -> str:
    # Include actionable tool output without exposing local storage paths.
    diagnostic = stderr
    for arg in sorted(args, key=len, reverse=True):
        if Path(arg).is_absolute():
            diagnostic = diagnostic.replace(arg, "[local video]")
    diagnostic = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", diagnostic)
    lines = [line.strip() for line in diagnostic.splitlines() if line.strip()]
    return " ".join(lines[-6:])[-1200:] or "The media tool returned no diagnostic output."


def run_media(args: list[str], timeout: float) -> str:
    stage = media_stage(args)
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise HTTPException(503, "FFmpeg and ffprobe must be installed on the server.")
    except subprocess.TimeoutExpired:
        logger.warning("Video %s timed out after %s seconds", stage, timeout)
        raise HTTPException(422, f"Video {stage} timed out after {timeout:g} seconds. Try a shorter recording.")
    if result.returncode:
        diagnostic = media_diagnostic(result.stderr, args)
        logger.warning("Video %s failed (exit %s): %s", stage, result.returncode, diagnostic)
        if stage == "preview conversion":
            explanation = "The original decoded successfully, but creating its browser preview failed."
        elif stage == "metadata inspection":
            explanation = "FFprobe could not read the video container. Check that the file is fully downloaded and plays locally."
        else:
            explanation = "FFmpeg could not decode the complete video. This may be a decoder compatibility issue or damaged data."
        raise HTTPException(422, f"Video {stage} failed. {explanation} Details: {diagnostic}")
    return result.stdout


class VideoStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.root = settings.data_dir
        self.root.mkdir(parents=True, exist_ok=True)

    def ingest(self, upload: UploadFile, view: View) -> VideoMetadata:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in {".mp4", ".mov"}:
            raise HTTPException(415, "Choose an MP4 or MOV video.")
        video_id = uuid4().hex
        temporary = self.root / f"{video_id}.part"
        target = self.root / f"{video_id}{suffix}"
        metadata_path = self.root / f"{video_id}.json"
        preview = self.root / f"{video_id}.preview.mp4"
        size = 0
        try:
            with temporary.open("xb") as output:
                while chunk := upload.file.read(1024 * 1024):
                    size += len(chunk)
                    if size > self.settings.max_bytes:
                        raise HTTPException(413, "Video exceeds the configured file-size limit.")
                    output.write(chunk)
            if not size:
                raise HTTPException(422, "The video file is empty.")
            probe = json.loads(run_media([
                "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(temporary)
            ], self.settings.probe_timeout))
            streams = [s for s in probe.get("streams", []) if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")]
            if len(streams) != 1:
                raise HTTPException(422, "Upload a file containing exactly one video stream.")
            stream = streams[0]
            if not {"mov", "mp4"}.intersection(probe.get("format", {}).get("format_name", "").split(",")):
                raise HTTPException(415, "The file content must be an MP4 or MOV container.")
            codec, pixel_format = stream.get("codec_name"), stream.get("pix_fmt")
            if codec not in {"h264", "hevc"}:
                raise HTTPException(415, f"Detected {codec or 'unknown'} / {pixel_format or 'unknown'}. Supported video codecs are H.264 and HEVC in MP4 or MOV.")
            needs_preview = codec != "h264" or pixel_format not in {"yuv420p", "yuvj420p"}
            duration = float(stream.get("duration", probe["format"].get("duration", 0)))
            fps = float(Fraction(stream.get("avg_frame_rate", "0/1")))
            width, height = int(stream["width"]), int(stream["height"])
            if not all(math.isfinite(x) and x > 0 for x in (duration, fps, width, height)):
                raise HTTPException(422, "Video timing or dimensions are invalid.")
            if duration > self.settings.max_duration:
                raise HTTPException(422, "Video exceeds the configured duration limit.")
            if max(width, height) > 4096:
                raise HTTPException(422, "Video resolution must not exceed 4096 pixels per dimension.")
            run_media(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(temporary), "-map", "0:v:0", "-an", "-fps_mode", "passthrough", "-enc_time_base:v", "demux", "-f", "null", "-"], self.settings.decode_timeout)
            if needs_preview:
                # The original remains the authoritative source for future analysis.
                # This silent derivative is only for browser playback.
                run_media([
                    "ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(temporary),
                    "-map", "0:v:0", "-an", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-fps_mode", "passthrough",
                    "-enc_time_base:v", "demux",
                    "-movflags", "+faststart", str(preview)
                ], self.settings.decode_timeout)
            rotation = next((float(s["rotation"]) for s in stream.get("side_data_list", []) if "rotation" in s), float(stream.get("tags", {}).get("rotate", 0)))
            metadata = VideoMetadata(
                video_id=video_id, view=view, width=width, height=height,
                duration_seconds=duration, frame_rate=fps,
                average_frame_rate=stream["avg_frame_rate"], nominal_frame_rate=stream.get("r_frame_rate", "0/1"),
                time_base=stream["time_base"], start_time_seconds=float(stream["start_time"]) if "start_time" in stream else None,
                start_pts=stream.get("start_pts"), duration_ts=stream.get("duration_ts"), frame_count=stream.get("nb_frames"),
                codec=stream["codec_name"], pixel_format=stream["pix_fmt"], rotation_degrees=rotation,
                size_bytes=size, uploaded_at=datetime.now(timezone.utc).isoformat(),
                source_creation_time=stream.get("tags", {}).get("creation_time", probe["format"].get("tags", {}).get("creation_time")),
                preview_url=f"/api/videos/{video_id}/preview" if needs_preview else None,
                content_url=f"/api/videos/{video_id}/content")
            temporary.replace(target)
            metadata_path.write_text(metadata.model_dump_json(indent=2))
            return metadata
        except (KeyError, ValueError, ZeroDivisionError, TypeError):
            raise HTTPException(422, "Video metadata is invalid or incomplete.")
        finally:
            temporary.unlink(missing_ok=True)
            # Publish only complete video + metadata pairs.
            if not metadata_path.exists():
                target.unlink(missing_ok=True)
                preview.unlink(missing_ok=True)

    def get(self, video_id: str) -> tuple[VideoMetadata, Path]:
        if len(video_id) != 32 or any(c not in "0123456789abcdef" for c in video_id):
            raise HTTPException(404, "Video not found.")
        path = self.root / f"{video_id}.json"
        if not path.exists():
            raise HTTPException(404, "Video not found.")
        metadata = VideoMetadata.model_validate_json(path.read_text())
        for suffix in (".mp4", ".mov"):
            content = self.root / f"{video_id}{suffix}"
            if content.exists():
                return metadata, content
        raise HTTPException(404, "Video not found.")
