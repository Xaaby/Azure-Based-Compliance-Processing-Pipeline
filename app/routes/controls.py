from typing import List

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text as sql_text

from ..db import get_session
from ..pipeline.match import _ensure_controls_loaded

router = APIRouter(prefix="/controls", tags=["controls"])


class ControlOut(BaseModel):
    id: str
    title: str
    category: str
    text: str


@router.get("", response_model=List[ControlOut])
def list_controls():
    with get_session() as session:
        _ensure_controls_loaded(session)
        rows = (
            session.execute(
                sql_text("SELECT id, title, category, text FROM controls ORDER BY id")
            )
            .mappings()
            .all()
        )
        return [
            {
                "id": r["id"],
                "title": r["title"],
                "category": r["category"],
                "text": r["text"],
            }
            for r in rows
        ]

