"""POST /api/descriptors : calcule et renvoie les 5 descripteurs d'une image (affichage, Tâche 1).

Requête : multipart/form-data avec le fichier dans le champ ``image``.
Réponse : le dictionnaire de ``compute_all`` (histogramme, moments, couleurs dominantes, GLCM, LBP).
"""

import time

from flask_restful import Resource

from cbir import descriptors as D
from resources.common import uploaded_image


class DescriptorsResource(Resource):
    def post(self):
        img = uploaded_image("image")
        t0 = time.perf_counter()
        result = D.compute_all(img)
        return {
            "width": int(img.shape[1]),
            "height": int(img.shape[0]),
            "descriptors": result,
            "took_ms": round(1000 * (time.perf_counter() - t0), 1),
        }
