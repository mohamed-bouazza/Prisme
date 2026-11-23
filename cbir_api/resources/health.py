"""GET /api/health : l'API répond-elle, et l'index est-il chargé ?"""

from flask import current_app
from flask_restful import Resource

from cbir.descriptors import DESCRIPTOR_DIMS, FEATURE_DIM


class HealthResource(Resource):
    def get(self):
        index = current_app.config.get("CBIR_INDEX")
        return {
            "status": "ok",
            "index_loaded": index is not None,
            "n_images": len(index) if index is not None else 0,
            "n_categories": len(set(index.labels.tolist())) if index is not None else 0,
            "feature_dim": FEATURE_DIM,
            "descriptors": DESCRIPTOR_DIMS,             # nom -> nombre de composantes
        }
