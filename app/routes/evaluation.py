from fastapi import APIRouter

from ..pipeline.evaluate import evaluate_document

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.get("/{document_id}")
def evaluate(document_id: str):
    return evaluate_document(document_id)

