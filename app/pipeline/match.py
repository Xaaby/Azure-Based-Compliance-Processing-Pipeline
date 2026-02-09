from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from ..db import get_session
from .embed import encode_texts


def _ensure_controls_loaded(session: Session):
    count = session.execute(sql_text("SELECT COUNT(*) FROM controls")).scalar_one()
    if count and count > 0:
        return

    base = Path(__file__).resolve().parent.parent.parent
    controls_path = base / "data" / "controls.csv"
    if not controls_path.exists():
        # minimal inline controls if file missing
        rows = [
            ("AC-1", "User authentication", "Access Control", "Users must authenticate with unique IDs."),
            ("LM-1", "Log monitoring", "Logging & Monitoring", "Log security events and review regularly."),
            ("DR-1", "Data retention", "Data Retention", "Retain data for at least seven years."),
        ]
        df = pd.DataFrame(rows, columns=["id", "title", "category", "text"])
    else:
        df = pd.read_csv(controls_path)

    for _, r in df.iterrows():
        session.execute(
            sql_text(
                "INSERT INTO controls (id, title, category, text) "
                "VALUES (:id, :title, :category, :text) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {
                "id": r["id"],
                "title": r["title"],
                "category": r["category"],
                "text": r["text"],
            },
        )


def _get_control_embeddings(session: Session) -> Tuple[List[Dict], np.ndarray]:
    _ensure_controls_loaded(session)
    rows = session.execute(
        sql_text("SELECT id, title, category, text, embedding FROM controls ORDER BY id")
    ).mappings().all()
    texts = []
    need_compute_idx = []
    embeddings: List[np.ndarray] = []

    for idx, r in enumerate(rows):
        if r["embedding"] is not None:
            emb = np.array(r["embedding"], dtype="float32")
            embeddings.append(emb)
        else:
            texts.append(r["text"])
            need_compute_idx.append(idx)
            embeddings.append(None)  # placeholder

    if texts:
        new_embs = encode_texts(texts)
        j = 0
        for i in need_compute_idx:
            embeddings[i] = new_embs[j]
            j += 1
        # persist
        for idx, r in enumerate(rows):
            if rows[idx]["embedding"] is None:
                session.execute(
                    sql_text("UPDATE controls SET embedding = :emb WHERE id = :id"),
                    {"emb": embeddings[idx].tolist(), "id": r["id"]},
                )

    mat = np.vstack(embeddings)
    # normalize for cosine similarity
    norms = np.linalg.norm(mat, axis=1, keepdims=True) + 1e-8
    mat = mat / norms
    return rows, mat


def compute_matches_for_document(document_id: str):
    from .classify import get_classifier
    from .chunk import ChunkLike

    with get_session() as session:
        # get chunks
        chunk_rows = (
            session.execute(
                sql_text(
                    "SELECT id, text FROM chunks WHERE document_id = :doc ORDER BY chunk_index"
                ),
                {"doc": document_id},
            )
            .mappings()
            .all()
        )
        if not chunk_rows:
            return {"document_id": document_id, "num_chunks": 0, "num_matches": 0}

        classifier = get_classifier()

        # classify chunks
        for r in chunk_rows:
            label, conf = classifier.predict(r["text"])
            session.execute(
                sql_text(
                    "UPDATE chunks SET predicted_label = :label, confidence = :conf WHERE id = :id"
                ),
                {"label": label, "conf": conf, "id": r["id"]},
            )

        # embeddings for chunks
        chunk_texts = [r["text"] for r in chunk_rows]
        chunk_embs = encode_texts(chunk_texts)
        # normalize
        norms = np.linalg.norm(chunk_embs, axis=1, keepdims=True) + 1e-8
        chunk_embs = chunk_embs / norms

        for idx, r in enumerate(chunk_rows):
            session.execute(
                sql_text("UPDATE chunks SET embedding = :emb WHERE id = :id"),
                {"emb": chunk_embs[idx].tolist(), "id": r["id"]},
            )

        # controls + embeddings
        control_rows, control_mat = _get_control_embeddings(session)

        # similarity matrix
        sim = np.matmul(chunk_embs, control_mat.T)

        # clear existing matches
        session.execute(
            sql_text(
                "DELETE FROM matches WHERE chunk_id IN "
                "(SELECT id FROM chunks WHERE document_id = :doc)"
            ),
            {"doc": document_id},
        )

        # top-3
        num_matches = 0
        for i, r in enumerate(chunk_rows):
            scores = sim[i]
            top_idx = np.argsort(-scores)[:3]
            for rank, ci in enumerate(top_idx, start=1):
                ctrl = control_rows[int(ci)]
                score = float(scores[int(ci)])
                session.execute(
                    sql_text(
                        "INSERT INTO matches (chunk_id, control_id, rank, score) "
                        "VALUES (:chunk_id, :control_id, :rank, :score)"
                    ),
                    {
                        "chunk_id": r["id"],
                        "control_id": ctrl["id"],
                        "rank": rank,
                        "score": score,
                    },
                )
                num_matches += 1

        return {
            "document_id": document_id,
            "num_chunks": len(chunk_rows),
            "num_matches": num_matches,
        }

