"""Lecture de la base d'images : liste des fichiers et de leur catégorie.

Organisation attendue (version Kaggle de GHIM-10K) :

    data/GHIM-10K/
        aircraft/10_5001.jpg
        aircraft/10_5002.jpg
        ...
        flower/...

Chaque sous-dossier est une catégorie (20 catégories x 500 images). La catégorie ne sert
**pas** à la recherche (la recherche n'utilise que le contenu visuel) : elle sert uniquement
à l'**évaluation** (une image renvoyée est « pertinente » si elle a la même catégorie que la requête).
"""

from __future__ import annotations

from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def scan_dataset(root: str | Path) -> list[tuple[str, str]]:
    """Liste triée de (chemin relatif, catégorie) pour toutes les images sous ``root``.

    - Le chemin est relatif à ``root`` et écrit avec des « / » (identique sous Windows et Linux) :
      c'est l'**identifiant** stable de l'image dans l'index.
    - La catégorie est le nom du dossier parent. Une image posée directement dans ``root``
      reçoit la catégorie ``""`` (inconnue).
    - Le tri rend le résultat reproductible : la ligne i de l'index est toujours la même image.
    """
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"Dossier introuvable : {root}")
    items = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            rel = path.relative_to(root).as_posix()
            label = path.parent.name if path.parent != root else ""
            items.append((rel, label))
    items.sort()
    return items
