"""Baseline classifier: one-hot symptoms -> LogisticRegression (T14).

scikit-learn 1.9 LogisticRegression (lbfgs, multinomial by default):
https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression

from triage.data import RISK_FACTORS, Row


@dataclass
class TriageModel:
    version: str
    features: list[str]  # symptom ids the model reads (risk factors excluded)
    vocab: list[str]  # every known symptom id (features + risk factors)
    estimator: LogisticRegression

    @classmethod
    def fit(cls, rows: list[Row], vocab: list[str], version: str) -> TriageModel:
        features = [s for s in vocab if s not in RISK_FACTORS]
        estimator = LogisticRegression(C=1.0, max_iter=2000, random_state=0)
        estimator.fit(_encode([r[0] for r in rows], features), [r[1] for r in rows])
        return cls(version=version, features=features, vocab=list(vocab), estimator=estimator)

    def predict(
        self, symptom_ids: list[str], top_k: int
    ) -> tuple[list[tuple[str, float]], list[str]]:
        """Top-k (disease_id, probability), highest first, and the unknown symptom ids."""
        known = set(self.vocab)
        unknown = [s for s in dict.fromkeys(symptom_ids) if s not in known]
        proba = self.estimator.predict_proba(_encode([frozenset(symptom_ids)], self.features))[0]
        order = np.argsort(-proba, kind="stable")[:top_k]
        return [
            (str(self.estimator.classes_[i]), float(round(proba[i], 6))) for i in order
        ], unknown

    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.version}.joblib"
        joblib.dump(self, path)
        return path

    @classmethod
    def load(cls, path: Path) -> TriageModel:
        model = joblib.load(path)
        if not isinstance(model, cls):
            raise TypeError(f"{path} is not a TriageModel")
        return model


def _encode(symptom_sets: list[frozenset[str]], features: list[str]) -> np.ndarray:
    index = {s: i for i, s in enumerate(features)}
    x = np.zeros((len(symptom_sets), len(features)), dtype=np.float64)
    for row, symptoms in enumerate(symptom_sets):
        for s in symptoms:
            if s in index:  # unknown ids and risk factors are ignored
                x[row, index[s]] = 1.0
    return x


def top_k_accuracy(model: TriageModel, rows: list[Row], k: int) -> float:
    hits = sum(d in {p for p, _ in model.predict(sorted(s), k)[0]} for s, d in rows)
    return hits / len(rows)
