"""Catégories hiérarchiques (arbre) : lister, créer, renommer/déplacer, supprimer.

Chaque catégorie pointe vers sa catégorie parente (``parent_id``) ; une racine a ``parent_id = NULL``.
Pour obtenir **tous les descendants** d'une catégorie, on utilise une requête SQL **récursive**
(CTE récursive, ``WITH RECURSIVE``) : PostgreSQL parcourt l'arbre lui-même, en une seule requête.
"""

from __future__ import annotations

from flask import Blueprint
from flask_jwt_extended import jwt_required
from sqlalchemy import delete, func, select, update
from werkzeug.exceptions import BadRequest, Conflict

from gallery.api.common import (
    current_user_id,
    get_own_category,
    get_visible_category,
    json_body,
    visible,
)
from gallery.extensions import db
from gallery.models import Category, Image

bp = Blueprint("categories", __name__, url_prefix="/api/categories")


def descendant_ids(root_id: int) -> list[int]:
    """Ids de la catégorie ``root_id`` et de toutes ses sous-catégories, à n'importe quelle profondeur.

    SQL généré (simplifié) :
        WITH RECURSIVE tree(id) AS (
            SELECT id FROM categories WHERE id = :root          -- point de départ
            UNION ALL
            SELECT c.id FROM categories c JOIN tree ON c.parent_id = tree.id   -- enfants déjà trouvés
        )
        SELECT id FROM tree;
    """
    tree = select(Category.id).where(Category.id == root_id).cte("tree", recursive=True)
    tree = tree.union_all(select(Category.id).where(Category.parent_id == tree.c.id))
    return list(db.session.scalars(select(tree.c.id)))


def category_path(cat: Category | None) -> list[dict]:
    """Fil d'Ariane : [racine, ..., catégorie]. Ex. GHIM-10K > flowers."""
    path = []
    while cat is not None:
        path.append({"id": cat.id, "name": cat.name})
        cat = cat.parent
    return path[::-1]


def _check_name(name, parent_id, owner_id, exclude_id=None) -> str:
    name = str(name or "").strip()
    if not 1 <= len(name) <= 120:
        raise BadRequest("Nom de catégorie : 1 à 120 caractères")
    q = select(Category.id).where(
        func.lower(Category.name) == name.lower(),
        Category.parent_id.is_(None) if parent_id is None else Category.parent_id == parent_id,
        Category.owner_id == owner_id,
    )
    if exclude_id is not None:
        q = q.where(Category.id != exclude_id)
    if db.session.scalar(q):
        raise Conflict(f"Une catégorie « {name} » existe déjà à cet endroit")
    return name


@bp.get("")
@jwt_required()
def list_categories():
    """Liste **à plat** (chaque catégorie avec son parent_id) : le frontend reconstruit l'arbre.

    ``image_count`` : images directement dans la catégorie ; ``total_count`` : avec les sous-catégories.
    """
    uid = current_user_id()
    cats = db.session.scalars(select(Category).where(visible(Category, uid)).order_by(Category.name)).all()
    counts = dict(db.session.execute(
        select(Image.category_id, func.count()).where(visible(Image, uid), Image.category_id.is_not(None))
        .group_by(Image.category_id)
    ).all())
    children: dict[int | None, list[int]] = {}
    for c in cats:
        children.setdefault(c.parent_id, []).append(c.id)

    totals: dict[int, int] = {}

    def total(cid: int) -> int:                             # somme récursive (en mémoire, arbre petit)
        if cid not in totals:
            totals[cid] = counts.get(cid, 0) + sum(total(k) for k in children.get(cid, []))
        return totals[cid]

    return {"categories": [{
        "id": c.id, "name": c.name, "parent_id": c.parent_id, "public": c.is_public,
        "image_count": counts.get(c.id, 0), "total_count": total(c.id),
    } for c in cats]}


@bp.post("")
@jwt_required()
def create_category():
    uid = current_user_id()
    data = json_body()
    parent_id = data.get("parent_id")
    if parent_id is not None:
        parent_id = get_own_category(int(parent_id), uid).id   # on ne crée que sous ses propres catégories
    name = _check_name(data.get("name"), parent_id, uid)
    cat = Category(name=name, parent_id=parent_id, owner_id=uid)
    db.session.add(cat)
    db.session.commit()
    return {"category": {"id": cat.id, "name": cat.name, "parent_id": cat.parent_id, "public": False}}, 201


@bp.get("/<int:category_id>")
@jwt_required()
def get_category(category_id: int):
    cat = get_visible_category(category_id, current_user_id())
    return {"category": {"id": cat.id, "name": cat.name, "parent_id": cat.parent_id, "public": cat.is_public,
                         "path": category_path(cat)}}


@bp.patch("/<int:category_id>")
@jwt_required()
def update_category(category_id: int):
    """Renommer et/ou déplacer (changer de parent). Interdit de créer un cycle."""
    uid = current_user_id()
    cat = get_own_category(category_id, uid)
    data = json_body()
    parent_id = cat.parent_id
    if "parent_id" in data:
        parent_id = data["parent_id"]
        if parent_id is not None:
            parent_id = get_own_category(int(parent_id), uid).id
            if parent_id in descendant_ids(cat.id):         # soi-même ou un de ses descendants
                raise BadRequest("Impossible : une catégorie ne peut pas être rangée "
                                 "dans sa propre descendance")
    name = _check_name(data.get("name", cat.name), parent_id, uid, exclude_id=cat.id)
    cat.name, cat.parent_id = name, parent_id
    db.session.commit()
    return {"category": {"id": cat.id, "name": cat.name, "parent_id": cat.parent_id, "public": False}}


@bp.delete("/<int:category_id>")
@jwt_required()
def delete_category(category_id: int):
    """Supprime la catégorie et ses sous-catégories. Les images ne sont PAS supprimées :
    elles deviennent « sans catégorie »."""
    uid = current_user_id()
    cat = get_own_category(category_id, uid)
    ids = descendant_ids(cat.id)
    moved = db.session.execute(
        update(Image).where(Image.category_id.in_(ids)).values(category_id=None)
    ).rowcount
    # On détache d'abord les liens parent -> enfant du sous-arbre, puis on supprime tout d'un coup.
    # (Supprimer un parent encore référencé par un enfant violerait la clé étrangère parent_id ;
    #  et l'ordre des lignes renvoyées par une CTE n'est pas garanti par SQL.)
    db.session.execute(update(Category).where(Category.id.in_(ids)).values(parent_id=None))
    db.session.execute(delete(Category).where(Category.id.in_(ids)))
    db.session.commit()
    return {"deleted": ids, "images_uncategorized": moved}
