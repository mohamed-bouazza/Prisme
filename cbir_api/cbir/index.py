"""Index des descripteurs : la « mémoire » de la base, calculée une fois hors ligne.

Un index contient, **ligne par ligne dans le même ordre** :

    ids       (N,)      identifiant de l'image (chemin relatif, ex. "aircraft/10_5001.jpg")
    labels    (N,)      catégorie (sert à l'évaluation uniquement)
    raw       (N, 174)  vecteurs de descripteurs bruts (sortie de extract_feature_vector)

et les statistiques de normalisation, calculées sur la base au moment de la construction :

    mean, std (174,)    moyenne et écart-type de chaque composante

Pourquoi normaliser ? Les composantes n'ont pas la même échelle : une case d'histogramme vaut
~0,01, le contraste GLCM peut valoir 50. Sans normalisation, le contraste écraserait tout le reste
dans la distance. Le z-score  z = (x - moyenne) / écart-type  ramène chaque composante à une
moyenne de 0 et un écart-type de 1.

Les statistiques sont **figées** : une image ajoutée plus tard est normalisée avec les statistiques
de la base, pas recalculées (sinon tous les vecteurs changeraient à chaque upload).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from cbir.descriptors import FEATURE_DIM, descriptor_slices

STD_FLOOR = 1e-8    # une composante constante sur toute la base (écart-type 0) ne doit pas diviser par 0


class FeatureIndex:
    def __init__(self, ids, labels, raw, mean=None, std=None):
        self.ids = np.asarray(ids, dtype=str)
        self.labels = np.asarray(labels, dtype=str)
        self.raw = np.asarray(raw, dtype=np.float64).reshape(-1, FEATURE_DIM)
        if not (len(self.ids) == len(self.labels) == len(self.raw)):
            raise ValueError("ids, labels et raw doivent avoir le même nombre de lignes")
        if len(set(self.ids.tolist())) != len(self.ids):
            raise ValueError("identifiants en double dans l'index")
        if mean is None:                                    # construction : on calcule les statistiques
            if len(self.raw) < 2:
                raise ValueError("il faut au moins 2 images pour calculer les statistiques")
            mean, std = self.raw.mean(axis=0), self.raw.std(axis=0)
        self.mean = np.asarray(mean, dtype=np.float64)
        self.std = np.maximum(np.asarray(std, dtype=np.float64), STD_FLOOR)
        self.features = self.normalize(self.raw)            # matrice normalisée, utilisée par la recherche
        self._row = {id_: i for i, id_ in enumerate(self.ids.tolist())}   # id -> numéro de ligne

    # ------------------------------------------------------------------ accès
    def __len__(self) -> int:
        return len(self.ids)

    def __contains__(self, image_id: str) -> bool:
        return image_id in self._row

    def row_of(self, image_id: str) -> int:
        """Numéro de ligne d'une image (KeyError si absente)."""
        return self._row[image_id]

    def normalize(self, raw: np.ndarray) -> np.ndarray:
        """z-score avec les statistiques de la base (fonctionne pour 1 vecteur ou une matrice)."""
        return (np.asarray(raw, dtype=np.float64) - self.mean) / self.std

    @property
    def slices(self) -> dict[str, slice]:
        return descriptor_slices()

    # ------------------------------------------------- cycle de vie (upload / suppression)
    def add(self, image_id: str, raw_vector: np.ndarray, label: str = "") -> None:
        """Ajoute une image (upload, transformation). Les statistiques restent celles de la base."""
        if image_id in self._row:
            raise ValueError(f"image déjà indexée : {image_id}")
        raw_vector = np.asarray(raw_vector, dtype=np.float64).reshape(1, FEATURE_DIM)
        self.ids = np.append(self.ids, image_id)
        self.labels = np.append(self.labels, label)
        self.raw = np.vstack([self.raw, raw_vector])
        self.features = np.vstack([self.features, self.normalize(raw_vector)])
        self._row[image_id] = len(self.ids) - 1

    def remove(self, image_id: str) -> None:
        """Retire une image en supprimant **la même ligne** dans tous les tableaux."""
        i = self._row[image_id]
        keep = np.arange(len(self.ids)) != i
        self.ids, self.labels = self.ids[keep], self.labels[keep]
        self.raw, self.features = self.raw[keep], self.features[keep]
        self._row = {id_: j for j, id_ in enumerate(self.ids.tolist())}   # les lignes suivantes ont glissé

    # ------------------------------------------------------------- sauvegarde
    def save(self, directory: str | Path, meta: dict | None = None) -> None:
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        np.save(d / "features_raw.npy", self.raw)
        np.save(d / "ids.npy", self.ids)
        np.save(d / "labels.npy", self.labels)
        np.savez(d / "stats.npz", mean=self.mean, std=self.std)
        info = {"n_images": len(self), "feature_dim": FEATURE_DIM,
                "slices": {k: [s.start, s.stop] for k, s in self.slices.items()}, **(meta or {})}
        (d / "meta.json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, directory: str | Path) -> FeatureIndex:
        d = Path(directory)
        stats = np.load(d / "stats.npz")
        meta_path = d / "meta.json"
        if meta_path.exists():                  # garde-fou : index construit avec d'autres paramètres
            dim = json.loads(meta_path.read_text(encoding="utf-8")).get("feature_dim")
            if dim != FEATURE_DIM:
                raise ValueError(f"index de dimension {dim}, code de dimension {FEATURE_DIM} : réindexer")
        return cls(np.load(d / "ids.npy"), np.load(d / "labels.npy"), np.load(d / "features_raw.npy"),
                   mean=stats["mean"], std=stats["std"])
