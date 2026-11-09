from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse
from ..ingestion.models import VideoMetadata, View

router = APIRouter()

@router.get("/health")
def health():
    return {"status": "ok"}

@router.post("/api/videos", response_model=VideoMetadata, status_code=201)
def upload_video(request: Request, view: View = Form(...), file: UploadFile = File(...)):
    try:
        return request.app.state.store.ingest(file, view)
    finally:
        file.file.close()

@router.get("/api/videos/{video_id}", response_model=VideoMetadata)
def metadata(video_id: str, request: Request):
    return request.app.state.store.get(video_id)[0]

@router.get("/api/videos/{video_id}/content")
def content(video_id: str, request: Request):
    _, path = request.app.state.store.get(video_id)
    return FileResponse(path, media_type="video/mp4" if path.suffix == ".mp4" else "video/quicktime")


@router.get("/api/videos/{video_id}/preview")
def preview(video_id: str, request: Request):
    from fastapi import HTTPException
    store = request.app.state.store
    metadata, original = store.get(video_id)
    if not metadata.preview_url:
        return FileResponse(original, media_type="video/mp4" if original.suffix == ".mp4" else "video/quicktime")
    path = store.root / f"{video_id}.preview.mp4"
    if not path.exists():
        raise HTTPException(404, "Preview not found.")
    return FileResponse(path, media_type="video/mp4")
