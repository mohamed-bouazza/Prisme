"""Recherche par le contenu (Tâche 2, recherche simple) : relais vers l'API CBIR.

Le backend ajoute ce que l'API CBIR ne sait pas faire :
- **droits** : l'index CBIR contient les images de tous les utilisateurs ; on ne renvoie que celles que
  l'utilisateur a le droit de voir (les siennes + la base) ;
- **métadonnées** : on remplace chaque identifiant CBIR par l'image complète (nom, miniature, catégorie).

Corps JSON : {"image_id": 12, "k": 20, "mode": "balanced", "desc_weights": {...}}
ou multipart : champ ``image`` (nouvelle image, non enregistrée) + ``k``.
"""

from __future__ import annotations

import json

from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from werkzeug.exceptions import BadRequest, Conflict

from gallery.api.common import current_user_id, get_visible_image
from gallery.api.images import images_by_cbir_ids
from gallery.cbir_client import get_cbir

bp = Blueprint("search", __name__, url_prefix="/api/search")

MAX_K = 200


def _k(value) -> int:
    try:
        k = int(value if value not in (None, "") else 20)
    except (TypeError, ValueError) as exc:
        raise BadRequest("'k' doit être un entier") from exc
    if not 1 <= k <= MAX_K:
        raise BadRequest(f"'k' doit être entre 1 et {MAX_K}")
    return k


@bp.post("")
@jwt_required()
def search():
    uid = current_user_id()
    cbir = get_cbir()

    if "image" in request.files:                            # requête : nouvelle image envoyée
        f = request.files["image"]
        k = _k(request.form.get("k"))
        fetch = min(500, 3 * k + 20)                        # marge : certains résultats seront filtrés
        # desc_weights (optionnel) : texte JSON, ex. '{"glcm": 1, "lbp": 1}' = texture seule ;
        # l'API CBIR le valide et renvoie 400 s'il est mal formé.
        raw = cbir.search_by_file(f.read(), f.filename or "query.jpg", fetch,
                                  desc_weights=request.form.get("desc_weights") or None)
        query = {"type": "upload", "filename": f.filename}
    else:                                                   # requête : image de la galerie
        data = request.get_json(silent=True) or {}
        k = _k(data.get("k"))
        if "image_id" not in data:
            raise BadRequest("Donner {\"image_id\": ...} (JSON) ou un fichier 'image' (multipart)")
        image = get_visible_image(int(data["image_id"]), uid)
        if not image.indexed:
            raise Conflict("Cette image n'est pas encore indexée (POST /api/images/<id>/reindex)")
        options = {key: data[key] for key in ("mode", "desc_weights") if key in data}
        fetch = min(500, 3 * k + 20)
        raw = cbir.search_by_id(image.cbir_id, fetch, **options)
        query = {"type": "image", "image_id": image.id, "filename": image.filename}

    return {"query": query, "k": k, "results": _visible_results(raw, uid, k), "cbir_ms": raw.get("took_ms")}


def _visible_results(raw: dict, uid: int, k: int) -> list[dict]:
    """Résultats CBIR -> images complètes, en retirant celles que l'utilisateur ne peut pas voir."""
    found = images_by_cbir_ids([r["id"] for r in raw["results"]], uid)
    results = []
    for r in raw["results"]:
        img = found.get(r["id"])
        if img is None:                                     # image d'un autre utilisateur : invisible
            continue
        results.append({"rank": len(results) + 1, "distance": r["distance"], "image": img.to_dict(uid)})
        if len(results) == k:
            break
    return results


def _gallery_ids(value, name: str, uid: int) -> list[str]:
    """Ids de la galerie (entiers) -> ids CBIR, en vérifiant que chaque image est visible et indexée."""
    if value in (None, ""):
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise BadRequest(f"'{name}' doit être une liste JSON") from exc
    if not isinstance(value, list) or len(value) > 2000:
        raise BadRequest(f"'{name}' : liste de 2000 identifiants au maximum")
    out = []
    for raw_id in value:
        try:
            img = get_visible_image(int(raw_id), uid)
        except (TypeError, ValueError) as exc:
            raise BadRequest(f"'{name}' doit contenir des entiers") from exc
        if img.indexed:
            out.append(img.cbir_id)
    return out


@bp.post("/feedback")
@jwt_required()
def feedback():
    """Retour de pertinence FRE (étape 7). Le frontend renvoie à chaque itération TOUS ses marquages.

    JSON : {"image_id": 12, "relevant_ids": [..], "non_relevant_ids": [..], "k": 20, "level": 2}
    ou multipart : ``image`` (fichier requête) + ``relevant_ids`` / ``non_relevant_ids`` (listes JSON), ``k``.
    """
    uid = current_user_id()
    cbir = get_cbir()
    is_upload = "image" in request.files
    data = request.form if is_upload else (request.get_json(silent=True) or {})
    k = _k(data.get("k"))
    try:
        level = int(data.get("level", 2))
    except (TypeError, ValueError) as exc:
        raise BadRequest("'level' doit valoir 0, 1 ou 2") from exc
    relevant = _gallery_ids(data.get("relevant_ids"), "relevant_ids", uid)
    non_relevant = _gallery_ids(data.get("non_relevant_ids"), "non_relevant_ids", uid)
    fetch = min(500, 3 * k + 20)

    if is_upload:
        if not relevant:
            raise BadRequest("Marquez au moins une image pertinente avant de relancer")
        f = request.files["image"]
        raw = cbir.feedback_by_file(f.read(), f.filename or "query.jpg", relevant, non_relevant, fetch, level)
    else:
        if "image_id" not in data:
            raise BadRequest("Donner {\"image_id\": ...} (JSON) ou un fichier 'image' (multipart)")
        image = get_visible_image(int(data["image_id"]), uid)
        if not image.indexed:
            raise Conflict("Cette image n'est pas encore indexée")
        raw = cbir.feedback_by_id(image.cbir_id, relevant, non_relevant, fetch, level)

    return {
        "k": k,
        "results": _visible_results(raw, uid, k),
        "desc_weights": raw.get("desc_weights"),
        "counts": raw.get("counts"),
        "n_relevant": raw.get("n_relevant"),
        "n_nonrelevant": raw.get("n_nonrelevant"),
        "cbir_ms": raw.get("took_ms"),
    }
