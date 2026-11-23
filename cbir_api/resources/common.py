"""Outils partagés par les ressources : accès à l'index, lecture de l'image envoyée, erreurs JSON."""

from __future__ import annotations

import numpy as np
from flask import current_app, jsonify, request
from flask_restful import Api
from werkzeug.exceptions import BadRequest, HTTPException, ServiceUnavailable

from cbir import descriptors as D
from cbir.index import FeatureIndex

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


class JsonApi(Api):
    """Api Flask-RESTful dont toutes les erreurs ont la même forme : {"error": "...", "status": 400}.

    Par défaut, Flask-RESTful renvoie {"message": "..."} ; on uniformise pour le frontend.
    """

    def handle_error(self, e):
        if isinstance(e, HTTPException):
            return jsonify(error=e.description, status=e.code), e.code
        raise e                                         # vraie erreur Python -> 500 + trace dans la console


def get_index() -> FeatureIndex:
    index = current_app.config.get("CBIR_INDEX")
    if index is None:
        raise ServiceUnavailable("Index absent : lancer cbir_api/scripts/build_index.py "
                                 "puis redémarrer l'API.")
    return index


def persist_index(index: FeatureIndex) -> None:
    """Réécrit l'index sur disque (appelé sous verrou après un ajout ou une suppression)."""
    if current_app.config.get("CBIR_PERSIST"):
        index.save(current_app.config["CBIR_INDEX_DIR"])


def uploaded_image(field: str = "image") -> np.ndarray:
    """Lit l'image envoyée en multipart/form-data dans le champ ``field`` et la décode (BGR)."""
    file = request.files.get(field)
    if file is None or file.filename == "":
        raise BadRequest(f"Aucun fichier dans le champ '{field}' (multipart/form-data).")
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext and ext not in ALLOWED_EXTENSIONS:
        raise BadRequest(f"Extension non supportée : {ext}")
    try:
        return D.decode_image(file.read())
    except ValueError as exc:
        raise BadRequest(f"Fichier illisible comme image : {exc}") from exc


def int_param(value, name: str, default: int, lo: int, hi: int) -> int:
    if value is None or value == "":
        return default
    try:
        v = int(value)
    except (TypeError, ValueError) as exc:
        raise BadRequest(f"'{name}' doit être un entier") from exc
    if not lo <= v <= hi:
        raise BadRequest(f"'{name}' doit être entre {lo} et {hi}")
    return v
