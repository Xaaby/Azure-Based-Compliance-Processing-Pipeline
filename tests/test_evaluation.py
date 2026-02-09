from app.pipeline.evaluate import evaluate_document


class DummySession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, *args, **kwargs):
        class Result:
            def mappings(self_inner):
                # minimal shape: one chunk with label and three controls
                return [
                    {
                        "document_id": "SAMPLE_DOC_1",
                        "chunk_index": 0,
                        "predicted_label": "Access Control",
                        "control_id": "AC-2",
                        "rank": 1,
                    }
                ]

        return Result()


def test_evaluation_keys(monkeypatch):
    # Monkeypatch get_session to avoid real DB; evaluation should still return keys.
    from app import db as db_module

    def fake_get_session():
        return DummySession()

    monkeypatch.setattr(db_module, "get_session", fake_get_session)

    metrics = evaluate_document("SAMPLE_DOC_1")
    assert "classification_accuracy" in metrics
    assert "top1_accuracy" in metrics
    assert "top3_hit_rate" in metrics
    assert "support" in metrics
    assert "report" in metrics

