"""Commandes en ligne de commande (``flask ... <commande>``).

    flask --app gallery_backend/wsgi.py import-dataset

importe GHIM-10K dans la base de données : une catégorie publique « GHIM-10K » avec ses 20
sous-catégories, et une ligne ``images`` par fichier. Les fichiers ne sont **pas** copiés.
La commande est **idempotente** : la relancer n'ajoute pas de doublons.
"""

from __future__ import annotations

import click
from flask import Flask, current_app
from PIL import Image as PILImage
from sqlalchemy import select

from gallery.extensions import db
from gallery.models import Category, Image

ROOT_NAME = "GHIM-10K"


def _public_category(name: str, parent_id: int | None) -> Category:
    same_parent = Category.parent_id.is_(None) if parent_id is None else Category.parent_id == parent_id
    q = select(Category).where(Category.name == name, Category.owner_id.is_(None), same_parent)
    cat = db.session.scalar(q)
    if cat is None:
        cat = Category(name=name, parent_id=parent_id, owner_id=None)
        db.session.add(cat)
        db.session.flush()                                  # obtient l'id sans valider la transaction
    return cat


def import_dataset(dataset_dir, batch: int = 500) -> tuple[int, int]:
    """Renvoie (images ajoutées, images déjà présentes)."""
    files = sorted(p for p in dataset_dir.rglob("*.jpg") if p.is_file())
    existing = set(db.session.scalars(select(Image.cbir_id).where(Image.location == "dataset")))
    root = _public_category(ROOT_NAME, None)
    cats: dict[str, int] = {}
    added = 0
    with click.progressbar(files, label="Import GHIM-10K") as bar:
        for i, path in enumerate(bar, start=1):
            rel = path.relative_to(dataset_dir).as_posix()  # même identifiant que dans l'index CBIR
            if rel in existing:
                continue
            label = path.parent.name
            if label not in cats:
                cats[label] = _public_category(label, root.id).id
            with PILImage.open(path) as im:                 # ne lit que l'en-tête : rapide
                w, h, fmt = im.width, im.height, im.format
            db.session.add(Image(
                owner_id=None, category_id=cats[label], filename=path.name, location="dataset", path=rel,
                cbir_id=rel, width=w, height=h, size_bytes=path.stat().st_size, format=fmt,
                source="dataset", indexed=True,             # build_index.py a indexé toute la base
            ))
            added += 1
            if i % batch == 0:
                db.session.commit()                         # validation par paquets
    db.session.commit()
    return added, len(existing)


def register_cli(app: Flask) -> None:
    @app.cli.command("import-dataset")
    def import_dataset_cmd():
        """Importe GHIM-10K (catégories + images) dans la base de données."""
        dataset_dir = current_app.config["DATASET_DIR"]
        if not dataset_dir.is_dir():
            raise click.ClickException(f"Dossier introuvable : {dataset_dir}")
        added, already = import_dataset(dataset_dir)
        click.echo(f"{added} images ajoutées, {already} déjà présentes.")
