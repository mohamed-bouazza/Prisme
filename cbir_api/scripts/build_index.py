"""Indexation hors ligne : calcule les descripteurs de toutes les images et écrit l'index.

Usage (depuis la racine du projet, venv activé) :

    python cbir_api/scripts/build_index.py                       # toute la base, tous les cœurs
    python cbir_api/scripts/build_index.py --limit 200           # essai rapide sur 200 images
    python cbir_api/scripts/build_index.py --dataset D --out O   # autres dossiers

Résultat dans cbir_api/index/ (non versionné, régénérable) :
    features_raw.npy, ids.npy, labels.npy, stats.npz, meta.json
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from joblib import Parallel, delayed
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[2]              # racine du projet
sys.path.insert(0, str(ROOT / "cbir_api"))              # pour importer le paquet "cbir"

from cbir import descriptors as D  # noqa: E402  (import après la modification de sys.path)
from cbir.dataset import scan_dataset  # noqa: E402
from cbir.index import FeatureIndex  # noqa: E402


def extract_one(root: Path, rel: str):
    """Vecteur d'une image, ou None si le fichier est illisible (on ne bloque pas toute l'indexation)."""
    try:
        return D.extract_feature_vector(D.load_image(root / rel))
    except Exception as exc:                            # volontairement large : une image corrompue suffit
        return f"{type(exc).__name__}: {exc}"


def main(argv=None) -> int:
    load_dotenv(ROOT / ".env")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dataset", default=os.getenv("DATASET_DIR", "./data/GHIM-10K"))
    p.add_argument("--out", default=os.getenv("INDEX_DIR", "./cbir_api/index"))
    p.add_argument("--jobs", type=int, default=-1, help="nombre de processus (-1 = tous les cœurs)")
    p.add_argument("--limit", type=int, default=None, help="n'indexer que N images tirées au hasard")
    args = p.parse_args(argv)

    dataset = (ROOT / args.dataset).resolve()
    out = (ROOT / args.out).resolve()
    items = scan_dataset(dataset)
    if not items:
        print(f"Aucune image trouvée dans {dataset}")
        return 1
    if args.limit:
        random.seed(0)
        items = sorted(random.sample(items, min(args.limit, len(items))))
    n_labels = len({lab for _, lab in items})
    print(f"{len(items)} images, {n_labels} catégories, dans {dataset}")

    t0 = time.perf_counter()
    results = Parallel(n_jobs=args.jobs, batch_size=16)(
        delayed(extract_one)(dataset, rel) for rel, _ in tqdm(items, desc="descripteurs", unit="img")
    )
    elapsed = time.perf_counter() - t0

    ok = [(rel, lab, r) for (rel, lab), r in zip(items, results, strict=True) if isinstance(r, np.ndarray)]
    failed = [(rel, r) for (rel, _), r in zip(items, results, strict=True) if not isinstance(r, np.ndarray)]
    for rel, err in failed:
        print(f"  ignorée : {rel}  ({err})")

    ids, labels, vecs = zip(*ok, strict=True)
    index = FeatureIndex(ids, labels, np.stack(vecs))
    index.save(out, meta={
        "dataset": str(dataset.relative_to(ROOT)) if dataset.is_relative_to(ROOT) else str(dataset),
        "n_failed": len(failed),
        "seconds": round(elapsed, 1),
        "params": {"IMG_SIZE": D.IMG_SIZE, "HSV_BINS": D.HSV_BINS, "N_DOMINANT": D.N_DOMINANT,
                   "GLCM_LEVELS": D.GLCM_LEVELS, "GLCM_DISTANCES": D.GLCM_DISTANCES,
                   "LBP_P": D.LBP_P, "LBP_R": D.LBP_R},
    })
    print(f"Index écrit dans {out} : {len(index)} images x {D.FEATURE_DIM} composantes, "
          f"{len(failed)} échec(s), {elapsed:.0f} s ({1000 * elapsed / len(items):.1f} ms/image)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
