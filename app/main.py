from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.optimizer import MAX_PIECES, MAX_REMNANTS, optimize

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="木作裁条排样助手", docs_url=None, redoc_url=None)


class PieceIn(BaseModel):
    length: float = Field(gt=0, le=1_000_000)
    qty: int = Field(ge=1, le=MAX_PIECES)


class OptimizeRequest(BaseModel):
    stock_length: float = Field(gt=0, le=1_000_000)
    kerf: float = Field(ge=0, le=10_000)
    remnants: list[float] = Field(default_factory=list)
    pieces: list[PieceIn] = Field(min_length=1)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/optimize")
def api_optimize(req: OptimizeRequest):
    remnants = []
    for r in req.remnants:
        if not (r > 0):
            raise HTTPException(status_code=400, detail="余料长度必须为正数。")
        remnants.append(float(r))
    if len(remnants) > MAX_REMNANTS:
        raise HTTPException(status_code=400, detail=f"余料根数最多 {MAX_REMNANTS} 根。")

    pieces = []
    for item in req.pieces:
        pieces.extend([float(item.length)] * item.qty)
    if len(pieces) > MAX_PIECES:
        raise HTTPException(
            status_code=400,
            detail=f"裁件总数不能超过 {MAX_PIECES} 件（当前 {len(pieces)} 件）。",
        )

    return optimize(req.stock_length, req.kerf, remnants, pieces)


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
