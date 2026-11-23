"""Évaluation de la recherche simple sur l'index (précision@K, mAP, courbe précision/rappel).

Chaque image requête est cherchée dans toute la base (sans elle-même) ; un résultat est pertinent
s'il a la même catégorie que la requête.

Usage (depuis la racine du projet) :

    python cbir_api/scripts/evaluate.py                    # 50 requêtes par catégorie (1 000 au total)
    python cbir_api/scripts/evaluate.py --per-class 0      # toutes les images comme requêtes
    python cbir_api/scripts/evaluate.py --compare-hsv      # + comparaison des quantifications de teinte

Sorties dans reports/etape3/ (régénérable, non versionné) : results.csv, results.md, pr_curve.png
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cbir_api"))

from cbir import descriptors as D  # noqa: E402
from cbir.index import FeatureIndex  # noqa: E402
from cbir.metrics import average_precision  # noqa: E402
from cbir.search import DESCRIPTORS, per_descriptor_distances, weighted_distance  # noqa: E402

KS = (10, 20, 50, 100)
RECALL_POINTS = np.linspace(0.1, 1.0, 10)


def pick_queries(labels: np.ndarray, per_class: int, seed: int = 0) -> np.ndarray:
    """Numéros de ligne des requêtes : ``per_class`` par catégorie (0 = toutes les images)."""
    # Les images sans catégorie (ajoutées par les utilisateurs via la galerie) n'ont pas de vérité
    # terrain : elles ne peuvent pas servir de requêtes d'évaluation.
    if per_class <= 0:
        return np.flatnonzero(labels != "")
    rng = np.random.default_rng(seed)
    rows = []
    for lab in np.unique(labels[labels != ""]):
        members = np.flatnonzero(labels == lab)
        rows.extend(rng.choice(members, size=min(per_class, len(members)), replace=False))
    return np.sort(np.array(rows))


def evaluate_distances(dist_fn, labels: np.ndarray, queries: np.ndarray) -> dict:
    """Moyenne des métriques sur les requêtes. ``dist_fn(row)`` renvoie les N distances de la requête."""
    p_at = {k: [] for k in KS}
    aps, pr = [], []
    for qr in queries:
        dist = dist_fn(qr).copy()
        dist[qr] = np.inf                                   # la requête ne se compte pas elle-même
        order = np.argsort(dist, kind="stable")[:-1]        # on retire la requête (dernière, distance inf)
        rel = (labels[order] == labels[qr]).astype(np.int8)
        n_rel = int(rel.sum())
        for k in KS:
            p_at[k].append(rel[:k].mean())
        aps.append(average_precision(rel, n_rel))
        # précision interpolée aux niveaux de rappel 10 %, 20 %, ..., 100 %
        cum = np.cumsum(rel)
        recall, precision = cum / max(n_rel, 1), cum / np.arange(1, len(rel) + 1)
        interp = np.maximum.accumulate(precision[::-1])[::-1]   # meilleure précision à rappel >= r
        pr.append([interp[np.searchsorted(recall, r)] if r <= recall[-1] else 0.0 for r in RECALL_POINTS])
    out = {f"P@{k}": float(np.mean(v)) for k, v in p_at.items()}
    out["mAP"] = float(np.mean(aps))
    out["pr_curve"] = np.mean(pr, axis=0).tolist()
    return out


def configurations(index: FeatureIndex):
    """Les méthodes comparées : combinaison équilibrée, globale, et chaque descripteur seul."""
    X = index.features
    cache = {}

    def per_desc(qr):                                       # (N, 5), calculé une seule fois par requête
        if cache.get("row") != qr:
            cache["row"], cache["D"] = qr, per_descriptor_distances(X, X[qr])
        return cache["D"]

    configs = {
        "équilibré (5 descripteurs)": lambda qr: per_desc(qr).mean(axis=1),
        "global (174 composantes)": lambda qr: weighted_distance(X, X[qr]),
        "couleur seule (hist+moments+dominantes)": lambda qr: per_desc(qr)[:, :3].mean(axis=1),
        "texture seule (GLCM+LBP)": lambda qr: per_desc(qr)[:, 3:].mean(axis=1),
    }
    for j, name in enumerate(DESCRIPTORS):
        configs[f"seul : {name}"] = lambda qr, j=j: per_desc(qr)[:, j]
    return configs


def hsv_histograms(index: FeatureIndex, dataset: Path, bins) -> np.ndarray:
    """Histogrammes HSV avec une autre quantification (relit les images : ~1 min pour 10 000)."""
    H = []
    for rel in tqdm(index.ids, desc=f"HSV {bins}", unit="img"):
        H.append(D.color_histogram(D.prepare_image(D.load_image(dataset / rel)), bins))
    return np.stack(H)


def zscore(M: np.ndarray) -> np.ndarray:
    return (M - M.mean(axis=0)) / np.maximum(M.std(axis=0), 1e-8)


def to_markdown(rows: dict) -> str:
    cols = [f"P@{k}" for k in KS] + ["mAP"]
    lines = ["| Méthode | " + " | ".join(cols) + " |", "|---|" + "---:|" * len(cols)]
    for name, r in rows.items():
        lines.append(f"| {name} | " + " | ".join(f"{100 * r[c]:.1f} %" for c in cols) + " |")
    return "\n".join(lines)


def main(argv=None) -> int:
    load_dotenv(ROOT / ".env")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--index", default=os.getenv("INDEX_DIR", "./cbir_api/index"))
    p.add_argument("--per-class", type=int, default=50)
    p.add_argument("--compare-hsv", action="store_true")
    p.add_argument("--out", default="./reports/etape3")
    args = p.parse_args(argv)

    index = FeatureIndex.load(ROOT / args.index)
    queries = pick_queries(index.labels, args.per_class)
    out = (ROOT / args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    print(f"Index : {len(index)} images, {len(np.unique(index.labels))} catégories ; {len(queries)} requêtes")

    results = {}
    t0 = time.perf_counter()
    for name, fn in configurations(index).items():
        results[name] = evaluate_distances(fn, index.labels, queries)
        r = results[name]
        print(f"  {name:42s} P@20 = {100 * r['P@20']:5.1f} %   mAP = {100 * r['mAP']:5.1f} %")
    print(f"({time.perf_counter() - t0:.0f} s)")

    if args.compare_hsv:
        meta = json.loads((ROOT / args.index / "meta.json").read_text(encoding="utf-8"))
        dataset = (ROOT / meta["dataset"]).resolve()
        for bins in [(8, 4, 4), (16, 4, 4), (18, 3, 3), (12, 3, 3)]:
            Z = zscore(hsv_histograms(index, dataset, bins))
            name = f"histogramme HSV seul {bins[0]}x{bins[1]}x{bins[2]} ({int(np.prod(bins))} cases)"
            def dist_fn(qr, Z=Z):
                return weighted_distance(Z, Z[qr])
            results[name] = evaluate_distances(dist_fn, index.labels, queries)
            print(f"  {name:42s} P@20 = {100 * results[name]['P@20']:5.1f} %")

    table = to_markdown(results)
    (out / "results.md").write_text(f"{len(queries)} requêtes, base de {len(index)} images\n\n{table}\n",
                                    encoding="utf-8")
    with open(out / "results.csv", "w", encoding="utf-8") as f:
        f.write("methode," + ",".join([f"P@{k}" for k in KS] + ["mAP"]) + "\n")
        for name, r in results.items():
            f.write(f'"{name}",' + ",".join(f"{r[c]:.4f}" for c in [f"P@{k}" for k in KS] + ["mAP"]) + "\n")

    import matplotlib
    matplotlib.use("Agg")                                   # pas de fenêtre : on écrit juste un PNG
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 5))
    for name in ["équilibré (5 descripteurs)", "global (174 composantes)",
                 "couleur seule (hist+moments+dominantes)", "texture seule (GLCM+LBP)"]:
        ax.plot(RECALL_POINTS, results[name]["pr_curve"], marker="o", label=name)
    ax.set(xlabel="rappel", ylabel="précision", ylim=(0, 1),
           title="Recherche simple : courbe précision / rappel")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "pr_curve.png", dpi=120)
    print("\n" + table + f"\n\nRésultats écrits dans {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
