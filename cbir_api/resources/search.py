"""POST /api/search : recherche simple (Tâche 2).

Deux façons de donner la requête :

1. **Image déjà indexée** (choisie dans la galerie) — JSON :
       {"id": "aircraft/10_5001.jpg", "k": 20}
2. **Nouvelle image** (envoyée) — multipart/form-data : champ ``image``
   + champs texte optionnels ``k``, ``mode``.

Options (JSON ou champs de formulaire) :
    k             nombre de résultats (1 à 500, défaut 20)
    mode          "balanced" (défaut, chaque descripteur compte autant) ou "global"
    desc_weights  poids par descripteur, ex. {"color_hist": 1, "glcm": 2} (absent = 0)
    exclude       liste d'ids à ne pas renvoyer

Réponse :
    {"query": {...}, "results": [{"rank": 1, "id": ..., "label": ..., "distance": ...}, ...], "took_ms": ...}
"""

import json
import time

from flask import current_app, request
from flask_restful import Resource
from werkzeug.exceptions import BadRequest, NotFound

from cbir import descriptors as D
from cbir.search import DESCRIPTORS, search
from resources.common import get_index, int_param, uploaded_image

MAX_K = 500


def parse_desc_weights(value):
    if value in (None, ""):
        return None
    if isinstance(value, str):                          # champ de formulaire : JSON dans une chaîne
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise BadRequest("'desc_weights' doit être un objet JSON") from exc
    if not isinstance(value, dict):
        raise BadRequest("'desc_weights' doit être un objet JSON")
    unknown = set(value) - set(DESCRIPTORS)
    if unknown:
        raise BadRequest(f"Descripteurs inconnus : {sorted(unknown)} (valides : {list(DESCRIPTORS)})")
    try:
        weights = {k: float(v) for k, v in value.items()}
    except (TypeError, ValueError) as exc:
        raise BadRequest("les poids doivent être des nombres") from exc
    if any(w < 0 for w in weights.values()) or sum(weights.values()) <= 0:
        raise BadRequest("poids positifs, au moins un > 0")
    return weights


class SearchResource(Resource):
    def post(self):
        index = get_index()
        is_upload = "image" in request.files
        params = request.form if is_upload else (request.get_json(silent=True) or {})

        k = int_param(params.get("k"), "k", default=20, lo=1, hi=MAX_K)
        mode = params.get("mode") or "balanced"
        if mode not in ("balanced", "global"):
            raise BadRequest("'mode' doit valoir 'balanced' ou 'global'")
        desc_weights = parse_desc_weights(params.get("desc_weights"))
        exclude = params.get("exclude") or []
        if isinstance(exclude, str):
            exclude = [e for e in exclude.split(",") if e]
        options = {"mode": mode, "desc_weights": desc_weights}

        t0 = time.perf_counter()
        q_raw = D.extract_feature_vector(uploaded_image("image")) if is_upload else None   # hors verrou
        # Le verrou empêche une suppression simultanée de décaler les lignes pendant la recherche
        # (la recherche ne dure que quelques millisecondes).
        with current_app.config["CBIR_LOCK"]:
            if is_upload:
                results = search(index, q_raw, k=k, exclude=tuple(exclude), **options)
                query = {"type": "upload", "filename": request.files["image"].filename}
            else:
                image_id = params.get("id")
                if not image_id:
                    raise BadRequest("Donner soit un fichier 'image' (multipart), soit {\"id\": ...} (JSON).")
                if image_id not in index:
                    raise NotFound(f"Image non indexée : {image_id}")
                row = index.row_of(image_id)
                # la requête elle-même est toujours exclue de ses propres résultats
                results = search(index, index.raw[row], k=k, exclude=(image_id, *exclude), **options)
                query = {"type": "indexed", "id": image_id, "label": str(index.labels[row])}

        for rank, r in enumerate(results, start=1):
            r["rank"] = rank
        return {"query": query, "k": k, "mode": mode, "results": results,
                "took_ms": round(1000 * (time.perf_counter() - t0), 1)}
