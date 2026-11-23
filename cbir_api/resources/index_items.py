"""Gestion de l'index depuis la galerie : ajouter / consulter / retirer une image.

    POST   /api/index          multipart : image + id (+ label)  -> 201
    GET    /api/index/<id>     -> {"id", "label"} ou 404
    DELETE /api/index/<id>     -> 200 ou 404

L'``id`` est choisi par le backend galerie (ex. "u/42.jpg" pour l'image 42 d'un utilisateur) :
c'est lui qui fait le lien entre la ligne de l'index et l'enregistrement PostgreSQL.
"""

from flask import current_app, request
from flask_restful import Resource
from werkzeug.exceptions import BadRequest, Conflict, NotFound

from cbir import descriptors as D
from resources.common import get_index, persist_index, uploaded_image


class IndexCollectionResource(Resource):
    def post(self):
        index = get_index()
        image_id = (request.form.get("id") or "").strip()
        if not image_id:
            raise BadRequest("Champ 'id' obligatoire")
        label = (request.form.get("label") or "").strip()
        vec = D.extract_feature_vector(uploaded_image("image"))     # calcul hors verrou (le plus long)
        with current_app.config["CBIR_LOCK"]:                       # une modification à la fois
            if image_id in index:
                raise Conflict(f"Image déjà indexée : {image_id}")
            index.add(image_id, vec, label)
            persist_index(index)
            n = len(index)
        return {"id": image_id, "label": label, "n_images": n}, 201


class IndexItemResource(Resource):
    def get(self, image_id):
        index = get_index()
        with current_app.config["CBIR_LOCK"]:
            if image_id not in index:
                raise NotFound(f"Image non indexée : {image_id}")
            return {"id": image_id, "label": str(index.labels[index.row_of(image_id)])}

    def delete(self, image_id):
        index = get_index()
        with current_app.config["CBIR_LOCK"]:
            if image_id not in index:
                raise NotFound(f"Image non indexée : {image_id}")
            index.remove(image_id)
            persist_index(index)
            n = len(index)
        return {"deleted": image_id, "n_images": n}
