from datetime import datetime

from pydantic import BaseModel, Field


class RecordCreate(BaseModel):
    name: str
    clue: int = Field(ge=1, le=7)
    type: str = Field(pattern=r"^[+-]$")
    was_new: bool = False
    time: datetime | None = None


class RecordUpdate(BaseModel):
    time: datetime | None = None
    was_new: bool | None = None


class RecordOut(BaseModel):
    id: int
    name: str
    clue: int
    type: str
    was_new: bool
    time: datetime
    deleted: bool
    created_at: datetime


class PaginatedRecords(BaseModel):
    items: list[RecordOut]
    total: int
