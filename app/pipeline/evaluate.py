from pathlib import Path
from typing import Dict

import pandas as pd
from sqlalchemy import text as sql_text

from ..db import get_session


def evaluate_document(document_id: str) -> Dict:
    base = Path(__file__).resolve().parent.parent.parent
    gold_path = base / "data" / "gold_eval.csv"
    if not gold_path.exists():
        return {
            "document_id": document_id,
            "classification_accuracy": None,
            "top1_accuracy": None,
            "top3_hit_rate": None,
            "support": 0,
            "report": "No gold_eval.csv found; evaluation not available.",
        }

    gold = pd.read_csv(gold_path)
    # filter by document if doc_name column present
    if "document_id" in gold.columns:
        gold_doc = gold[gold["document_id"] == document_id].copy()
    else:
        gold_doc = gold.copy()

    if gold_doc.empty:
        return {
            "document_id": document_id,
            "classification_accuracy": None,
            "top1_accuracy": None,
            "top3_hit_rate": None,
            "support": 0,
            "report": "No gold rows for this document.",
        }

    with get_session() as session:
        # map (document_id, chunk_index) -> (label, [control_ids ordered])
        rows = (
            session.execute(
                sql_text(
                    """
                    SELECT d.id as document_id,
                           c.chunk_index,
                           c.predicted_label,
                           m.control_id,
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

    pred_map: Dict[int, Dict] = {}
    for r in rows:
        idx = r["chunk_index"]
        if idx not in pred_map:
            pred_map[idx] = {
                "predicted_label": r["predicted_label"],
                "controls": [],
            }
        if r["control_id"] is not None:
            pred_map[idx]["controls"].append(r["control_id"])

    correct_cls = 0
    correct_top1 = 0
    hit_top3 = 0
    n = 0

    for _, row in gold_doc.iterrows():
        idx = int(row["chunk_index"])
        expected_label = row.get("expected_label")
        expected_control = row.get("expected_control_id")
        if idx not in pred_map:
            continue
        pred = pred_map[idx]
        n += 1
        if pd.notna(expected_label) and pred["predicted_label"] == expected_label:
            correct_cls += 1
        if pd.notna(expected_control):
            controls = pred["controls"]
            if controls:
                if controls[0] == expected_control:
                    correct_top1 += 1
                if expected_control in controls[:3]:
                    hit_top3 += 1

    if n == 0:
        return {
            "document_id": document_id,
            "classification_accuracy": None,
            "top1_accuracy": None,
            "top3_hit_rate": None,
            "support": 0,
            "report": "No overlapping gold and prediction rows for this document.",
        }

    classification_accuracy = correct_cls / n if n else None
    top1_accuracy = correct_top1 / n if n else None
    top3_hit_rate = hit_top3 / n if n else None

    def fmt(value):
        return f"{value:.2f}" if value is not None else "NA"

    report = (
        f"Evaluated {n} gold-labelled chunks for document {document_id}. "
        f"Classification accuracy={fmt(classification_accuracy)}, "
        f"top-1 control accuracy={fmt(top1_accuracy)}, "
        f"top-3 hit rate={fmt(top3_hit_rate)}."
    )

    return {
        "document_id": document_id,
        "classification_accuracy": classification_accuracy,
        "top1_accuracy": top1_accuracy,
        "top3_hit_rate": top3_hit_rate,
        "support": n,
        "report": report,
    }

