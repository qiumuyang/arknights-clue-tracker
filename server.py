from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from advice import get_advice
from database import Database
from models import PaginatedRecords, RecordCreate, RecordOut, RecordUpdate

BASE_DIR = Path(__file__).parent

app = FastAPI(title="Ark Clues Manager")
db = Database(str(BASE_DIR / "clues.db"))

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/")
def index():
    return FileResponse(BASE_DIR / "static/index.html")


@app.post("/api/records", response_model=RecordOut)
def add_record(body: RecordCreate):
    if body.was_new is None:
        body.was_new = False
    time = body.time or datetime.now()
    id_ = db.add_record(
        name=body.name,
        clue=body.clue,
        type_=body.type,
        was_new=body.was_new,
        time=time,
    )
    rows = db.list_records(include_deleted=True)
    for r in rows:
        if r["id"] == id_:
            return RecordOut(**r)
    raise HTTPException(500, "record not found after insert")


@app.get("/api/records", response_model=PaginatedRecords)
def list_records(
    name: str | None = None,
    since: str | None = None,
    type: str | None = Query(None, pattern=r"^[+-]$"),
    clue: int | None = Query(None, ge=1, le=7),
    clues: list[int] | None = Query(None),
    include_deleted: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    sort_col: str = "time",
    sort_dir: str = "desc",
):
    since_dt = datetime.fromisoformat(since) if since else None
    offset = (page - 1) * page_size
    total = db.count_records_filtered(
        name=name,
        since=since_dt,
        type_=type,
        clue=clue,
        clues=clues,
        include_deleted=include_deleted,
    )
    rows = db.list_records(
        name=name,
        since=since_dt,
        type_=type,
        clue=clue,
        clues=clues,
        include_deleted=include_deleted,
        limit=page_size,
        offset=offset,
        sort_col=sort_col,
        sort_dir=sort_dir,
    )
    return PaginatedRecords(items=[RecordOut(**r) for r in rows], total=total)


@app.patch("/api/records/{id_}", response_model=RecordOut)
def update_record(id_: int, body: RecordUpdate):
    ok = db.update_record(
        id_,
        time=body.time,
        was_new=body.was_new if body.was_new is not None else None,
    )
    if not ok:
        raise HTTPException(404, "record not found")
    rows = db.list_records(include_deleted=True)
    for r in rows:
        if r["id"] == id_:
            return RecordOut(**r)
    raise HTTPException(404, "record not found")


@app.delete("/api/records/{id_}")
def delete_record(id_: int):
    ok = db.delete_record(id_)
    if not ok:
        raise HTTPException(404, "record not found")
    return {"ok": True}


@app.get("/api/summary")
def get_summary(
    since: str | None = None,
    name: str | None = None,
):
    since_dt = datetime.fromisoformat(since) if since else None
    return db.get_summary(since=since_dt, name=name)


@app.get("/api/players")
def get_players(q: str = ""):
    return db.get_players(q)


@app.get("/api/advice")
def advice(since: str = "", clue: int | None = Query(None, ge=1, le=7), weight: float = Query(1.0, ge=0, le=1)):
    since_dt = datetime.fromisoformat(since) if since else None
    return get_advice(db, since=since_dt, clue=clue, weight=weight)


class ImportRequest(BaseModel):
    content: str


@app.post("/api/import")
def import_data(body: ImportRequest):
    import os
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(body.content)
        tmp = f.name
    result = db.import_from_file(tmp)
    os.unlink(tmp)
    return result


@app.get("/api/stats")
def stats():
    return {"total": db.count_records()}

