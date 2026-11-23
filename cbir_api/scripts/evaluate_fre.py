"""Évaluation du retour de pertinence FRE avec un UTILISATEUR SIMULÉ.

Protocole (le même pour toutes les méthodes, sur les mêmes requêtes) :
  itération 0 : recherche simple (mode équilibré), on affiche les K = 20 premières images ;
  l'utilisateur simulé marque chaque image affichée : même catégorie que la requête -> pertinente,
  sinon -> non pertinente (il « voit » la vérité terrain, comme un humain qui reconnaît un cheval) ;
  itérations 1, 2, 3 : FRE avec les marquages CUMULÉS, nouvel affichage de 20 images, nouveaux marquages.
On mesure P@20 de l'affichage à chaque itération (les pertinentes déjà vues peuvent réapparaître).

Méthodes comparées :
  QPM          : déplacement de la requête seul (moyenne des pertinentes, poids uniformes)
  FRE niveau 1 : + poids intra 1/(ε+σ)
  FRE niveau 2 : + poids inter-descripteurs (comptage), = version complète

Usage :  python cbir_api/scripts/evaluate_fre.py [--per-class 50] [--iterations 3]
Sorties : reports/etape7/ (fre_results.md, fre_results.csv, fre_curve.png)
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cbir_api"))
sys.path.insert(0, str(ROOT / "cbir_api" / "scripts"))

from evaluate import pick_queries  # noqa: E402

from cbir.feedback.fre import fre_search  # noqa: E402
from cbir.index import FeatureIndex  # noqa: E402
from cbir.search import rank  # noqa: E402

K = 20
METHODS = {
    "QPM (requête déplacée seule)": 0,
    "FRE niveau 1 (poids intra)": 1,
    "FRE niveau 2 (intra + inter)": 2,
}


def run_session(index: FeatureIndex, q_row: int, level: int, iterations: int) -> list[float]:
    """Une session simulée ; renvoie P@20 à chaque itération (0 = recherche simple)."""
    labels, ids = index.labels, index.ids
    target = labels[q_row]
    q_id = str(ids[q_row])
    rows, _ = rank(index, index.features[q_row], k=K, exclude=(q_id,))
    precisions = []
    relevant: list[str] = []
    nonrelevant: list[str] = []
    for it in range(iterations + 1):
        shown_rel = labels[rows] == target
        precisions.append(float(shown_rel.mean()))
        if it == iterations:
            break
        for r, ok in zip(rows, shown_rel, strict=True):           # marquages de l'utilisateur simulé
            (relevant if ok else nonrelevant).append(str(ids[r]))
        res = fre_search(index, relevant, nonrelevant, query_id=q_id, k=K, level=level)
        rows = res.rows
    return precisions


def main(argv=None) -> int:
    load_dotenv(ROOT / ".env")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--index", default=os.getenv("INDEX_DIR", "./cbir_api/index"))
    p.add_argument("--per-class", type=int, default=50)
    p.add_argument("--iterations", type=int, default=3)
    p.add_argument("--out", default="./reports/etape7")
    args = p.parse_args(argv)

    index = FeatureIndex.load(ROOT / args.index)
    queries = pick_queries(index.labels, args.per_class)        # mêmes requêtes que l'étape 3 (graine 0)
    out = (ROOT / args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    print(f"{len(queries)} requêtes, K = {K}, {args.iterations} itérations de retour de pertinence")

    results = {}
    per_class = {}
    t0 = time.perf_counter()
    for name, level in METHODS.items():
        curves = np.array([run_session(index, q, level, args.iterations) for q in tqdm(queries, desc=name)])
        results[name] = curves.mean(axis=0)
        labs = index.labels[queries]
        per_class[name] = {lab: curves[labs == lab].mean(axis=0) for lab in np.unique(labs)}
        print(f"  {name:32s} " + "  ".join(f"it{i}={100 * v:5.1f} %" for i, v in enumerate(results[name])))
    print(f"({time.perf_counter() - t0:.0f} s)")

    its = range(args.iterations + 1)
    header = "| Méthode | " + " | ".join(f"Itération {i}" for i in its) + " | Gain |"
    lines = [header, "|---|" + "---:|" * (args.iterations + 2)]
    for name, v in results.items():
        cells = " | ".join(f"{100 * x:.1f} %" for x in v)
        lines.append(f"| {name} | {cells} | +{100 * (v[-1] - v[0]):.1f} pts |")
    best = list(METHODS)[-1]
    cls_lines = ["| Catégorie | Itération 0 | Itération " + str(args.iterations) + " |", "|---|---:|---:|"]
    for lab, v in sorted(per_class[best].items(), key=lambda kv: kv[1][-1]):
        cls_lines.append(f"| {lab} | {100 * v[0]:.1f} % | {100 * v[-1]:.1f} % |")
    text = (f"{len(queries)} requêtes ({args.per_class} par catégorie), "
            f"P@{K} de l'affichage à chaque itération\n\n"
            + "\n".join(lines) + f"\n\nDétail par catégorie ({best}) :\n\n" + "\n".join(cls_lines) + "\n")
    (out / "fre_results.md").write_text(text, encoding="utf-8")
    with open(out / "fre_results.csv", "w", encoding="utf-8") as f:
        f.write("methode," + ",".join(f"it{i}" for i in its) + "\n")
        for name, v in results.items():
            f.write(f'"{name}",' + ",".join(f"{x:.4f}" for x in v) + "\n")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for name, v in results.items():
        ax.plot(list(its), 100 * v, marker="o", label=name)
    ax.set(xlabel="itération de retour de pertinence", ylabel=f"P@{K} (%)", ylim=(0, 100),
           title="Retour de pertinence : précision par itération")
    ax.set_xticks(list(its))
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "fre_curve.png", dpi=120)
    print("\n" + text + f"\nRésultats écrits dans {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
