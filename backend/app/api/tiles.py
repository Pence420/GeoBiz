from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.datasets.service import active_release
from app.db.session import get_session

router = APIRouter(prefix="/tiles")


@router.get("/releases/{filename}", response_class=FileResponse)
def active_tile_artifact(
    filename: str,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    release = active_release(session)
    if not release.tile_filename or filename != release.tile_filename:
        raise HTTPException(status_code=404, detail="tile artifact is not active")
    path = settings.tile_root / release.tile_filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="active tile artifact is missing")
    return FileResponse(
        path,
        media_type="application/vnd.pmtiles",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
