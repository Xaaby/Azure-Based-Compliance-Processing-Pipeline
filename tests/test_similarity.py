import numpy as np

from app.pipeline.embed import encode_texts


def test_similarity_returns_three_matches_like_behavior():
    texts = [
        "access control and authentication",
        "logging and monitoring of events",
        "data retention and backup policy",
        "incident response and reporting procedures",
    ]

    embs = encode_texts(texts)
    # normalize
    norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-8
    embs = embs / norms

    # Treat first vector as a "chunk" and others as "controls"
    query = embs[0:1]
    controls = embs[1:]
    sims = np.matmul(query, controls.T)[0]

    top_idx = np.argsort(-sims)[:3]

    # We should always get exactly 3 indices and they should be sorted by score descending
    assert len(top_idx) == 3
    scores = sims[top_idx]
    assert list(scores) == sorted(scores, reverse=True)

