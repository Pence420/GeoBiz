from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.api.tiles import router as tiles_router
from app.core.config import get_settings

app = FastAPI(title="GeoBiz API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(router)
app.include_router(tiles_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
