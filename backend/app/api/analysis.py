from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse
from ..pose.service import AnalysisRequest

router = APIRouter()

@router.get("/api/videos")
def list_videos(request: Request):
    from ..ingestion.models import VideoMetadata
    videos = []
    for path in request.app.state.store.root.glob("*.json"):
        videos.append(VideoMetadata.model_validate_json(path.read_text()))
    return sorted(videos, key=lambda v: v.uploaded_at, reverse=True)

@router.post("/api/videos/{video_id}/analyses", status_code=202)
def start(video_id: str, body: AnalysisRequest, request: Request):
    return request.app.state.analysis.start(video_id, body)

@router.get("/api/videos/{video_id}/analyses/latest")
def latest(video_id: str, request: Request):
    return request.app.state.analysis.latest(video_id)

@router.get("/api/analyses/{analysis_id}")
def status(analysis_id: str, request: Request):
    return request.app.state.analysis.get(analysis_id)

@router.get("/api/analyses/{analysis_id}/result")
def result(analysis_id: str, request: Request):
    service = request.app.state.analysis
    job = service.get(analysis_id)
    if job["status"] != "completed":
        raise HTTPException(409, "Analysis is not complete.")
    return FileResponse(service.root / analysis_id / "result.json", media_type="application/json")
