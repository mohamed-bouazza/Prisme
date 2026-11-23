"""POST /api/feedback : une itération de retour de pertinence FRE (Tâche 2, groupe 14).

L'API est **sans état** : le client renvoie à chaque itération TOUS les marquages cumulés.
(Pas de session à stocker côté serveur ; plusieurs utilisateurs peuvent chercher en même temps.)

Requête par image indexée — JSON :
    {"query_id": "flowers/6_3003.jpg", "relevant": ["flowers/6_3004.jpg", ...],
     "non_relevant": ["cars/3_1582.jpg", ...], "k": 20, "level": 2}
Requête par image envoyée — multipart : champ ``image`` + champs texte ``relevant``,
``non_relevant`` (listes JSON), ``k``, ``level``.

Réponse : {"results": [{rank, id, label, distance}], "desc_weights": {...}, "counts": {...},
           "n_relevant": .., "n_nonrelevant": .., "top_components": [...], "took_ms": ..}
"""

import json
import time

from flask import current_app, request
from flask_restful import Resource
from werkzeug.exceptions import BadRequest, NotFound

from cbir import descriptors as D
from cbir.feedback.fre import fre_search
from resources.common import get_index, int_param, uploaded_image

MAX_K = 500
MAX_MARKS = 2000


def _id_list(value, name: str) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise BadRequest(f"'{name}' doit être une liste JSON d'identifiants") from exc
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise BadRequest(f"'{name}' doit être une liste d'identifiants (texte)")
    if len(value) > MAX_MARKS:
        raise BadRequest(f"'{name}' : {MAX_MARKS} identifiants au maximum")
    return value


class FeedbackResource(Resource):
    def post(self):
        index = get_index()
        is_upload = "image" in request.files
        params = request.form if is_upload else (request.get_json(silent=True) or {})
        k = int_param(params.get("k"), "k", default=20, lo=1, hi=MAX_K)
        level = int_param(params.get("level"), "level", default=2, lo=0, hi=2)
        relevant = _id_list(params.get("relevant"), "relevant")
        nonrelevant = _id_list(params.get("non_relevant"), "non_relevant")

        t0 = time.perf_counter()
        query_raw = D.extract_feature_vector(uploaded_image("image")) if is_upload else None
        query_id = None if is_upload else params.get("query_id")
        if not is_upload and not query_id:
            raise BadRequest("Donner 'query_id' (JSON) ou un fichier 'image' (multipart).")

        with current_app.config["CBIR_LOCK"]:
            if query_id is not None and query_id not in index:
                raise NotFound(f"Image non indexée : {query_id}")
            unknown = [i for i in relevant + nonrelevant if i not in index]
            if unknown:
                raise NotFound(f"Images non indexées : {unknown[:5]}")
            try:
                res = fre_search(index, relevant, nonrelevant, query_id=query_id, query_raw=query_raw,
                                 k=k, level=level)
            except ValueError as exc:
                raise BadRequest(str(exc)) from exc
            results = [
                {"rank": n, "id": str(index.ids[r]), "label": str(index.labels[r]), "distance": float(d)}
                for n, (r, d) in enumerate(zip(res.rows, res.distances, strict=True), start=1)
            ]

        return {
            "results": results,
            "level": level,
            "desc_weights": res.desc_weights,
            "counts": res.counts,
            "n_relevant": res.n_relevant,
            "n_nonrelevant": res.n_nonrelevant,
            "top_components": res.top_components,
            "took_ms": round(1000 * (time.perf_counter() - t0), 1),
        }
