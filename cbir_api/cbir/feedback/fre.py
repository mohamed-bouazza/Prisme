"""Retour de pertinence par Feature Relevance Estimation (FRE), méthode du groupe 14.

À chaque itération, l'utilisateur marque des images pertinentes (R) et non pertinentes (N).
Les marquages s'accumulent d'une itération à l'autre (on CUMULE R et N) et :

1. **Nouvelle requête** = moyenne des vecteurs de R (la requête d'origine fait partie de R) :
       Q = (1/|R|) * somme des Y de R

2. **Poids intra-descripteur** (équation 4 de l'article) : pour chaque composante i,
       w_i = 1 / (ε + σ_i),  σ_i = écart-type de la composante i sur les images de R, ε = 0,0001
   Petite dispersion chez les pertinentes -> la composante compte beaucoup.

3. **Poids inter-descripteurs** (niveau 2, comme MARS ; optionnel) : pour chaque descripteur m,
   on classe les images DÉJÀ JUGÉES (R ∪ N) avec la seule distance d_m et on compte les pertinentes
   parmi les |R| premières -> c_m. Puis e_m = (c_m + 1) / Σ_l (c_l + 1).
   (Le « +1 », lissage de Laplace, évite qu'un descripteur tombe à un poids nul sur 2 ou 3 exemples.)

4. **Distance finale** : D = Σ_m e_m · d_m / d̄_m, où d_m est la distance euclidienne pondérée
   (poids w) restreinte au descripteur m, et d̄_m sa moyenne sur la base (même échelle pour tous).

5. Les images de N ne sont plus jamais renvoyées ; la requête d'origine non plus.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from cbir.index import FeatureIndex
from cbir.search import DESCRIPTORS, per_descriptor_distances

EPS = 1e-4                       # ε de l'article


def intra_weights(R: np.ndarray) -> np.ndarray:
    """w_i = 1 / (ε + σ_i) sur les vecteurs (normalisés) des images pertinentes R (n, d)."""
    return 1.0 / (EPS + R.std(axis=0))


def descriptor_counts(D_judged: np.ndarray, is_rel: np.ndarray) -> np.ndarray:
    """c_m : pour chaque descripteur (colonne de D_judged), nombre de pertinentes parmi les |R|
    images jugées les plus proches. D_judged : (n_jugées, 5) ; is_rel : (n_jugées,) booléens."""
    k = int(is_rel.sum())
    counts = np.zeros(D_judged.shape[1])
    for m in range(D_judged.shape[1]):
        top = np.argsort(D_judged[:, m], kind="stable")[:k]
        counts[m] = is_rel[top].sum()
    return counts


def descriptor_weights(counts: np.ndarray) -> np.ndarray:
    """e_m = (c_m + 1) / Σ (c_l + 1) : normalisés (somme 1), jamais nuls."""
    smoothed = counts + 1.0
    return smoothed / smoothed.sum()


@dataclass
class FREResult:
    rows: np.ndarray                         # lignes de l'index, de la plus proche à la plus éloignée
    distances: np.ndarray
    desc_weights: dict[str, float]           # e_m (somme 1)
    counts: dict[str, int]                   # c_m (niveau 2), sinon vide
    query: np.ndarray                        # nouvelle requête (normalisée)
    weights: np.ndarray                      # w_i (174)
    n_relevant: int = 0
    n_nonrelevant: int = 0
    top_components: list[dict] = field(default_factory=list)


def fre_search(
    index: FeatureIndex,
    relevant: list[str],
    nonrelevant: list[str] = (),
    query_id: str | None = None,
    query_raw: np.ndarray | None = None,
    k: int = 20,
    level: int = 2,
) -> FREResult:
    """Une itération de FRE.

    relevant / nonrelevant : ids de l'index marqués par l'utilisateur (cumulés depuis le début).
    query_id : la requête si elle est indexée (elle compte comme pertinente) ;
    query_raw : sinon, son vecteur brut (image envoyée, non indexée).
    level : 0 = déplacement de la requête seul (QPM), 1 = + poids intra, 2 = + poids inter-descripteurs.
    """
    X = index.features
    rel_rows = [index.row_of(i) for i in dict.fromkeys(relevant) if i in index]
    non_rows = [index.row_of(i) for i in dict.fromkeys(nonrelevant) if i in index and i not in relevant]

    vectors = [X[r] for r in rel_rows]
    if query_id is not None and query_id in index:
        q_row = index.row_of(query_id)
        if q_row not in rel_rows:
            vectors.append(X[q_row])
    else:
        q_row = None
        if query_raw is not None:
            vectors.append(index.normalize(query_raw))
    if not vectors:
        raise ValueError("au moins une image pertinente (ou une requête) est nécessaire")
    R = np.stack(vectors)

    q = R.mean(axis=0)                                           # 1. déplacement de la requête
    w = intra_weights(R) if level >= 1 else np.ones(X.shape[1])  # 2. poids intra-descripteur

    D = per_descriptor_distances(X, q, w)                        # (N, 5) : d_m pour chaque image
    D = D / np.maximum(D.mean(axis=0), 1e-12)                    # 4. d_m / d̄_m : même échelle

    counts = {}
    if level >= 2 and non_rows:                                  # 3. poids inter (besoin de N pour comparer)
        judged = np.array(rel_rows + non_rows)
        is_rel = np.array([True] * len(rel_rows) + [False] * len(non_rows))
        c = descriptor_counts(D[judged], is_rel)
        e = descriptor_weights(c)
        counts = {m: int(v) for m, v in zip(DESCRIPTORS, c, strict=True)}
    else:
        e = np.full(len(DESCRIPTORS), 1 / len(DESCRIPTORS))

    dist = D @ e                                                 # e est déjà normalisé (somme 1)
    excluded = list(non_rows) + ([q_row] if q_row is not None else [])
    if excluded:
        dist = dist.copy()
        dist[excluded] = np.inf
    order = np.argsort(dist, kind="stable")
    order = order[np.isfinite(dist[order])][:k]

    # Pour l'affichage : les composantes les plus influentes (poids relatif le plus fort)
    slices = index.slices
    top = []
    share = w / w.sum()
    for i in np.argsort(-share)[:5]:
        name = next(n for n, s in slices.items() if s.start <= i < s.stop)
        top.append({"descriptor": name, "component": int(i - slices[name].start), "share": float(share[i])})

    return FREResult(
        rows=order, distances=dist[order], desc_weights=dict(zip(DESCRIPTORS, map(float, e), strict=True)),
        counts=counts, query=q, weights=w, n_relevant=len(R), n_nonrelevant=len(non_rows), top_components=top,
    )
