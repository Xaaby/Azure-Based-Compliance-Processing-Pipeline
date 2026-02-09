from functools import lru_cache
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression


class ClauseClassifier:
    def __init__(self, df: pd.DataFrame):
        self.labels = sorted(df["label"].unique().tolist())
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=5000,
        )
        X = self.vectorizer.fit_transform(df["text"])
        self.model = LogisticRegression(max_iter=1000, multi_class="auto", random_state=42)
        self.model.fit(X, df["label"])

    def predict(self, text: str) -> Tuple[str, float]:
        X = self.vectorizer.transform([text])
        probs = self.model.predict_proba(X)[0]
        idx = int(np.argmax(probs))
        return self.model.classes_[idx], float(probs[idx])


@lru_cache(maxsize=1)
def get_classifier() -> ClauseClassifier:
    base = Path(__file__).resolve().parent.parent.parent
    data_path = base / "data" / "training_samples.csv"
    if not data_path.exists():
        # Fallback tiny inline dataset if file missing
        rows = [
            ("Users must authenticate with unique credentials.", "Access Control"),
            ("System events are logged and monitored.", "Logging & Monitoring"),
            ("Backups are stored for seven years.", "Data Retention"),
            ("Incidents must be reported within 24 hours.", "Incident Response"),
            ("Data at rest is encrypted using AES-256.", "Encryption"),
            ("Third-party vendors are assessed annually.", "Vendor Risk"),
            ("This policy applies to all employees.", "General"),
        ]
        df = pd.DataFrame(rows, columns=["text", "label"])
    else:
        df = pd.read_csv(data_path)
    return ClauseClassifier(df)

