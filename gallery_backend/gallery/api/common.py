"""Outils partagés par les routes : utilisateur courant, droits d'accès, lecture du JSON."""

from __future__ import annotations

from flask import request
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import or_
from werkzeug.exceptions import BadRequest, Forbidden, NotFound

from gallery.extensions import db
from gallery.models import Category, Image


def current_user_id() -> int:
    """Identifiant de l'utilisateur connecté (le JWT stocke l'id sous forme de texte)."""
    return int(get_jwt_identity())


def json_body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise BadRequest("Corps JSON attendu (Content-Type: application/json)")
    return data


def visible(model, user_id: int):
    """Condition SQL : ligne publique (owner_id NULL) OU appartenant à l'utilisateur."""
    return or_(model.owner_id.is_(None), model.owner_id == user_id)


def get_visible_image(image_id: int, user_id: int) -> Image:
    """Image visible par l'utilisateur, sinon 404.

    404 et non 403 pour l'image d'un autre : on ne révèle même pas qu'elle existe.
    """
    image = db.session.get(Image, image_id)
    if image is None or not (image.is_public or image.owner_id == user_id):
        raise NotFound(f"Image {image_id} introuvable")
    return image


def get_own_image(image_id: int, user_id: int) -> Image:
    """Image modifiable par l'utilisateur (la sienne). Les images de la base sont en lecture seule."""
    image = get_visible_image(image_id, user_id)
    if image.is_public:
        raise Forbidden("Les images de la base GHIM-10K sont en lecture seule")
    return image


def get_visible_category(category_id: int, user_id: int) -> Category:
    cat = db.session.get(Category, category_id)
    if cat is None or not (cat.is_public or cat.owner_id == user_id):
        raise NotFound(f"Catégorie {category_id} introuvable")
    return cat


def get_own_category(category_id: int, user_id: int) -> Category:
    cat = get_visible_category(category_id, user_id)
    if cat.is_public:
        raise Forbidden("Les catégories de la base GHIM-10K sont en lecture seule")
    return cat


def int_arg(name: str, default: int, lo: int, hi: int) -> int:
    raw = request.args.get(name)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise BadRequest(f"'{name}' doit être un entier") from exc
    return max(lo, min(hi, value))


def id_list(data: dict, key: str = "ids", max_len: int = 500) -> list[int]:
    ids = data.get(key)
    if not isinstance(ids, list) or not ids or len(ids) > max_len:
        raise BadRequest(f"'{key}' : liste de 1 à {max_len} identifiants attendue")
    try:
        return list(dict.fromkeys(int(i) for i in ids))   # entiers, sans doublons, ordre conservé
    except (TypeError, ValueError) as exc:
        raise BadRequest(f"'{key}' doit contenir des entiers") from exc
