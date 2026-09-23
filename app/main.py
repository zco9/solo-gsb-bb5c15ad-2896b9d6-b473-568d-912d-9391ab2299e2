"""FastAPI 后端：提供静态页面与 /api/solve 排样接口。"""
from __future__ import annotations

import os
from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .solver import MAX_LEFTOVERS, MAX_TOTAL_PIECES, solve

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(title="木作裁条排样", version="1.0.0")


class PieceRow(BaseModel):
    length: float = Field(..., description="裁件长度")
    qty: int = Field(..., description="裁件数量")


class SolveRequest(BaseModel):
    new_length: float = Field(..., description="新料定长")
    leftovers: list[float] = Field(default_factory=list, description="已有余料各根长度")
    kerf: float = Field(0.0, description="锯缝宽度")
    pieces: list[PieceRow] = Field(..., description="裁件清单（长度+数量）")

    @field_validator("new_length")
    @classmethod
    def _check_new_length(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("新料定长必须大于 0")
        return v

    @field_validator("kerf")
    @classmethod
    def _check_kerf(cls, v: float) -> float:
        if v < 0:
            raise ValueError("锯缝宽度不能为负")
        return v

    @field_validator("leftovers")
    @classmethod
    def _check_left(cls, v: list[float]) -> list[float]:
        if len(v) > MAX_LEFTOVERS:
            raise ValueError(f"余料最多输入 {MAX_LEFTOVERS} 根")
        bad = [x for x in v if x <= 0]
        if bad:
            raise ValueError("余料长度必须全部大于 0")
        return v

    @field_validator("pieces")
    @classmethod
    def _check_pieces(cls, v: list[PieceRow]) -> list[PieceRow]:
        if not v:
            raise ValueError("请至少添加一种裁件")
        for row in v:
            if row.length <= 0:
                raise ValueError("裁件长度必须大于 0")
            if row.qty <= 0:
                raise ValueError("裁件数量必须为正整数")
        total = sum(row.qty for row in v)
        if total > MAX_TOTAL_PIECES:
            raise ValueError(f"裁件总数不能超过 {MAX_TOTAL_PIECES} 件（当前 {total} 件）")
        return v


@app.exception_handler(ValueError)
async def value_error_handler(_request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/api/solve")
async def api_solve(req: SolveRequest) -> dict:
    try:
        result = solve(
            new_length=req.new_length,
            leftover_lengths=req.leftovers,
            kerf=req.kerf,
            piece_rows=[(p.length, p.qty) for p in req.pieces],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "feasible": result.feasible,
        "message": result.message,
        "summary": {
            "new_bar_count": result.new_bar_count,
            "used_leftover_count": result.used_leftover_count,
            "bar_count": result.bar_count,
            "total_piece_length": result.total_piece_length,
            "total_kerf": result.total_kerf,
            "total_tail": result.total_tail,
            "unused_leftover_indices": result.unused_leftover_indices,
        },
        "overlong": result.overlong,
        "bars": [asdict(b) for b in result.bars],
        "inputs": {
            "new_length": req.new_length,
            "leftovers": req.leftovers,
            "kerf": req.kerf,
            "pieces": [{"length": p.length, "qty": p.qty} for p in req.pieces],
        },
    }


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
