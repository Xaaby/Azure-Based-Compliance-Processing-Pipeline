from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text as sql_text

from ..db import get_session
from ..pipeline.chunk import chunk_text
from ..pipeline.ingest import ingest_uploaded_document
from ..pipeline.match import compute_matches_for_document

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentOut(BaseModel):
    id: str
    name: str
    source: str | None = None
    created_at: str


@router.post("", response_model=DocumentOut)
async def upload_document(file: UploadFile = File(...)):
    if not (file.filename.endswith(".txt") or file.filename.endswith(".md")):
        raise HTTPException(status_code=400, detail="Only .txt and .md files are supported")

    content = await file.read()
    doc = ingest_uploaded_document(file.filename, content)
    return {
        "id": str(doc["id"]),
        "name": doc["name"],
        "source": doc.get("source"),
        "created_at": doc["created_at"].isoformat() if hasattr(doc["created_at"], "isoformat") else str(doc["created_at"]),
    }


@router.get("", response_model=List[DocumentOut])
def list_documents():
    with get_session() as session:
        rows = (
            session.execute(
                sql_text(
                    "SELECT id, name, source, created_at FROM documents ORDER BY created_at DESC"
                )
            )
            .mappings()
            .all()
        )
        return [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "source": r.get("source"),
                "created_at": r["created_at"].isoformat()
                if hasattr(r["created_at"], "isoformat")
                else str(r["created_at"]),
            }
            for r in rows
        ]


@router.post("/{document_id}/chunk")
def chunk_document(document_id: str):
    with get_session() as session:
        doc_row = (
            session.execute(
                sql_text("SELECT id, raw_text FROM documents WHERE id = :id"),
                {"id": document_id},
            )
            .mappings()
            .first()
        )
        if not doc_row:
            raise HTTPException(status_code=404, detail="Document not found")

        chunks = chunk_text(doc_row["raw_text"])

        # delete existing chunks for idempotency
        session.execute(
            sql_text("DELETE FROM chunks WHERE document_id = :id"), {"id": document_id}
        )

        for ch in chunks:
            session.execute(
                sql_text(
                    """
                    INSERT INTO chunks (document_id, chunk_index, start_char, end_char, text)
                    VALUES (:document_id, :chunk_index, :start_char, :end_char, :text)
                    """
                ),
                {
                    "document_id": document_id,
                    "chunk_index": ch.chunk_index,
                    "start_char": ch.start_char,
                    "end_char": ch.end_char,
                    "text": ch.text,
                },
            )

        return {
            "document_id": document_id,
            "num_chunks": len(chunks),
        }


@router.post("/{document_id}/process")
def process_document(document_id: str):
    # chunk (idempotent) then classify + match
    chunk_result = chunk_document(document_id)
    match_result = compute_matches_for_document(document_id)
    return {
        "document_id": document_id,
        "chunks_created": chunk_result["num_chunks"],
        "num_chunks": match_result["num_chunks"],
        "num_matches": match_result["num_matches"],
    }


@router.get("/{document_id}/results")
def document_results(document_id: str):
    with get_session() as session:
        rows = (
            session.execute(
                sql_text(
                    """
                    SELECT d.name as doc_name,
                           c.chunk_index,
                           c.text,
                           c.predicted_label,
                           c.confidence,
                           m.control_id,
                           m.score,
                           m.rank
                    FROM documents d
                    JOIN chunks c ON c.document_id = d.id
                    LEFT JOIN matches m ON m.chunk_id = c.id
                    WHERE d.id = :doc
                    ORDER BY c.chunk_index, m.rank
                    """
                ),
                {"doc": document_id},
            )
            .mappings()
            .all()
        )
    # reshape into per-chunk records
    by_chunk = {}
    for r in rows:
        idx = r["chunk_index"]
        if idx not in by_chunk:
            by_chunk[idx] = {
                "doc_name": r["doc_name"],
                "chunk_index": idx,
                "chunk_text": (r["text"][:300] + "…") if len(r["text"]) > 300 else r["text"],
                "predicted_label": r["predicted_label"],
                "confidence": r["confidence"],
                "matches": [],
            }
        if r["control_id"] is not None:
            by_chunk[idx]["matches"].append(
                {"control_id": r["control_id"], "score": r["score"], "rank": r["rank"]}
            )

    result = []
    for idx in sorted(by_chunk.keys()):
        chunk = by_chunk[idx]
        matches = sorted(chunk["matches"], key=lambda x: x["rank"])[:3]
        record = {
            "doc_name": chunk["doc_name"],
            "chunk_index": chunk["chunk_index"],
            "chunk_text": chunk["chunk_text"],
            "predicted_label": chunk["predicted_label"],
            "confidence": chunk["confidence"],
        }
        for i in range(3):
            if i < len(matches):
                record[f"matched_control_id_{i+1}"] = matches[i]["control_id"]
                record[f"score_{i+1}"] = matches[i]["score"]
            else:
                record[f"matched_control_id_{i+1}"] = None
                record[f"score_{i+1}"] = None
        result.append(record)

    return result


@router.get("/{document_id}/export.csv")
def export_document_csv(document_id: str):
    import csv
    from io import StringIO

    rows = document_results(document_id)
    output = StringIO()
    fieldnames = [
        "doc_name",
        "chunk_index",
        "chunk_text",
        "predicted_label",
        "confidence",
        "matched_control_id_1",
        "score_1",
        "matched_control_id_2",
        "score_2",
        "matched_control_id_3",
        "score_3",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for r in rows:
        writer.writerow(r)

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="document_{document_id}.csv"'},
    )


