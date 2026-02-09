from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from ..db import get_session


def _read_text_file(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    # Normalize newlines for determinism
    return text.replace("\r\n", "\n").replace("\r", "\n")


def ingest_uploaded_document(
    file_name: str,
    content: bytes,
    source: Optional[str] = None,
    session: Optional[Session] = None,
):
    """
    Store an uploaded .txt or .md document and return its DB row.
    """
    from sqlalchemy import text as sql_text

    text = content.decode("utf-8")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    own_session = session is None
    if own_session:
        cm = get_session()
        session_cm = cm.__enter__()
        session = session_cm
    try:
        stmt = sql_text(
            """
            INSERT INTO documents (name, source, raw_text, created_at)
            VALUES (:name, :source, :raw_text, :created_at)
            RETURNING id, name, source, created_at
            """
        )
        row = session.execute(
            stmt,
            {
                "name": file_name,
                "source": source or "upload",
                "raw_text": text,
                "created_at": datetime.utcnow(),
            },
        ).mappings().first()
        if own_session:
            cm.__exit__(None, None, None)
        return dict(row)
    except Exception as exc:  # pragma: no cover - defensive
        if own_session:
            cm.__exit__(type(exc), exc, exc.__traceback__)
        raise


def ingest_local_document(path: Path, source: str = "local-sample"):
    """
    Ingest a document from a local path under data/sample_docs/.
    """
    text = _read_text_file(path)
    from sqlalchemy import text as sql_text

    with get_session() as session:
        stmt = sql_text(
            """
            INSERT INTO documents (name, source, raw_text, created_at)
            VALUES (:name, :source, :raw_text, :created_at)
            RETURNING id, name, source, created_at
            """
        )
        row = session.execute(
            stmt,
            {
                "name": path.name,
                "source": source,
                "raw_text": text,
                "created_at": datetime.utcnow(),
            },
        ).mappings().first()
        return dict(row)

