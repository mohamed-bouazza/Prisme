"""Recherche simple : classer toutes les images de l'index par distance à une requête.

Distance euclidienne pondérée (la même formule servira à FRE, étape 7) :

    d(x, q) = sqrt( sum_i w_i (x_i - q_i)^2  /  sum_i w_i )

Avec tous les poids w_i = 1, c'est la moyenne quadratique des écarts (RMS). Diviser par sum w_i
rend la distance indépendante du nombre de composantes et de l'échelle des poids.

Deux façons de combiner les 5 descripteurs :

- ``mode="global"``   : une seule distance sur les 174 composantes. Problème : l'histogramme HSV a
  128 composantes sur 174 (74 %), il pèse donc 74 % de la distance, la texture GLCM seulement 4 %.
- ``mode="balanced"`` (défaut) : une distance d_m par descripteur, puis une moyenne pondérée

      D(x, q) = sum_m e_m d_m(x, q)  /  sum_m e_m

  où e_m est le poids du descripteur m (1 par défaut : chaque descripteur compte autant).
  C'est le niveau « inter-descripteurs » de FRE à deux niveaux.
"""

from __future__ import annotations

import numpy as np

from cbir.descriptors import DESCRIPTOR_DIMS, descriptor_slices
from cbir.index import FeatureIndex

DESCRIPTORS = tuple(DESCRIPTOR_DIMS)    # ("color_hist", "color_moments", "dominant_colors", "glcm", "lbp")


def weighted_distance(X: np.ndarray, q: np.ndarray, w: np.ndarray | None = None) -> np.ndarray:
    """Distance de chaque ligne de X (N, d) au vecteur q (d,), avec les poids w (d,)."""
    sq = (X - q) ** 2                                   # broadcasting : q est soustrait de chaque ligne
    if w is None:
        return np.sqrt(sq.mean(axis=1))
    w = np.asarray(w, dtype=np.float64)
    return np.sqrt((sq * w).sum(axis=1) / w.sum())


def per_descriptor_distances(X: np.ndarray, q: np.ndarray, w: np.ndarray | None = None) -> np.ndarray:
    """Matrice (N, 5) : colonne m = distance calculée seulement sur les composantes du descripteur m."""
    cols = []
    for s in descriptor_slices().values():
        cols.append(weighted_distance(X[:, s], q[s], None if w is None else w[s]))
    return np.stack(cols, axis=1)


def combined_distance(X, q, weights=None, desc_weights=None, mode="balanced") -> np.ndarray:
    """Distance finale (N,) entre chaque image de X et la requête q (vecteurs déjà normalisés)."""
    if mode == "global":
        return weighted_distance(X, q, weights)
    if mode != "balanced":
        raise ValueError(f"mode inconnu : {mode}")
    D = per_descriptor_distances(X, q, weights)
    e = np.array([1.0 if desc_weights is None else desc_weights.get(m, 0.0) for m in DESCRIPTORS])
    if e.sum() <= 0:
        raise ValueError("au moins un descripteur doit avoir un poids > 0")
    return D @ e / e.sum()                              # moyenne pondérée des 5 colonnes


def rank(index: FeatureIndex, q_norm: np.ndarray, k: int | None = None, exclude=(), **kwargs):
    """Classe les images de la plus proche à la plus éloignée.

    Retourne (rows, dists) : numéros de ligne et distances, triés. ``exclude`` = ids à ignorer
    (ex. la requête elle-même, ou les images jugées non pertinentes pendant le feedback).
    """
    dist = combined_distance(index.features, q_norm, **kwargs)
    if exclude:
        rows_out = [index.row_of(i) for i in exclude if i in index]
        dist = dist.copy()
        dist[rows_out] = np.inf                         # distance infinie -> classées en dernier
    order = np.argsort(dist, kind="stable")             # "stable" : à distance égale, l'ordre est fixe
    if exclude:
        order = order[np.isfinite(dist[order])]
    if k is not None:
        order = order[:k]
    return order, dist[order]


def search(index: FeatureIndex, q_raw: np.ndarray, k: int = 20, exclude=(), **kwargs) -> list[dict]:
    """Recherche simple à partir d'un vecteur **brut** (sortie de extract_feature_vector).

    Retourne une liste [{"id", "label", "distance"}, ...] prête à être envoyée en JSON.
    """
    rows, dists = rank(index, index.normalize(q_raw), k=k, exclude=exclude, **kwargs)
    return [{"id": str(index.ids[r]), "label": str(index.labels[r]), "distance": float(d)}
            for r, d in zip(rows, dists, strict=True)]


def search_by_id(index: FeatureIndex, image_id: str, k: int = 20, include_self=False, **kwargs) -> list[dict]:
    """Recherche avec une image déjà indexée comme requête (pas besoin de recalculer ses descripteurs)."""
    q_raw = index.raw[index.row_of(image_id)]
    return search(index, q_raw, k=k, exclude=() if include_self else (image_id,), **kwargs)
