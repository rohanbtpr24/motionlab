import json
from fastapi import FastAPI
from .api.routes import router
from .api.comparison import router as comparison_router
from .api.analysis import router as analysis_router
from .pose.service import AnalysisService
from .config import Settings
from .ingestion.service import VideoStore

class UploadLimit:
    """Bound the complete request while streaming, before multipart spooling."""
    def __init__(self, app, limit: int):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") != "POST":
            return await self.app(scope, receive, send)
        received = 0
        exceeded = False
        async def bounded_receive():
            nonlocal received, exceeded
            message = await receive()
            received += len(message.get("body", b""))
            if received > self.limit:
                exceeded = True
                from starlette.exceptions import HTTPException
                raise HTTPException(413, "Request exceeds the upload limit.")
            return message
        async def bounded_send(message):
            if not exceeded:
                await send(message)
        try:
            await self.app(scope, bounded_receive, bounded_send)
        finally:
            if exceeded:
                body = json.dumps({"detail": "Request exceeds the upload limit."}).encode()
                await send({"type": "http.response.start", "status": 413, "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body", "body": body})

def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="MotionLab", version="0.1.0")
    app.state.store = VideoStore(settings)
    app.state.analysis = AnalysisService(app.state.store, settings.model_path)
    app.add_middleware(UploadLimit, limit=settings.max_bytes + 64 * 1024)
    app.include_router(comparison_router)
    app.include_router(analysis_router)
    app.include_router(router)
    return app

app = create_app()
