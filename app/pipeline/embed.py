from functools import lru_cache
from pathlib import Path
from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer


@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    # Small, CPU-friendly model
    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


def encode_texts(texts: List[str]) -> np.ndarray:
    model = get_model()
    embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    return embeddings.astype("float32")

