"""Mesures de qualité d'une recherche.

Pour une requête, on regarde la liste ordonnée des résultats et on marque chacun
pertinent (1) ou non (0). Dans GHIM-10K, « pertinent » = même catégorie que la requête.

    precision@K = (nb de pertinents parmi les K premiers) / K
    recall@K    = (nb de pertinents parmi les K premiers) / (nb total de pertinents dans la base)
    AP          = moyenne des precision@k aux rangs k où un pertinent apparaît (average precision)
    mAP         = moyenne des AP sur toutes les requêtes
"""

from __future__ import annotations

import numpy as np


def precision_at_k(relevant: np.ndarray, k: int) -> float:
    """``relevant`` : tableau 0/1 dans l'ordre du classement."""
    return float(np.asarray(relevant[:k]).sum() / k)


def recall_at_k(relevant: np.ndarray, k: int, n_relevant: int) -> float:
    return float(np.asarray(relevant[:k]).sum() / n_relevant) if n_relevant else 0.0


def average_precision(relevant: np.ndarray, n_relevant: int | None = None) -> float:
    rel = np.asarray(relevant, dtype=np.float64)
    n_relevant = int(rel.sum()) if n_relevant is None else n_relevant
    if n_relevant == 0:
        return 0.0
    precisions = np.cumsum(rel) / np.arange(1, len(rel) + 1)   # precision@k pour chaque rang k
    return float((precisions * rel).sum() / n_relevant)
