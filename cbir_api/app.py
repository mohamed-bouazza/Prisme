"""API REST du moteur CBIR (Flask + Flask-RESTful).

Rôle : **calculer** (descripteurs, distances) et **chercher**. Elle ne gère ni les utilisateurs ni le
stockage des fichiers : c'est le travail du backend galerie (étape 5), qui l'appelle en HTTP.

Lancer (depuis la racine du projet, venv activé) :

    python cbir_api/app.py                 # http://127.0.0.1:5001

Routes :

    GET    /api/health                     état de l'API et de l'index
    POST   /api/descriptors                descripteurs d'une image envoyée (affichage, Tâche 1)
    POST   /api/search                     recherche simple (image envoyée OU id d'une image indexée)
    POST   /api/feedback                   retour de pertinence FRE (marquages cumulés)
    GET    /api/index/<id>                 une image est-elle indexée ? (+ catégorie)
    POST   /api/index                      indexer une nouvelle image (upload, transformation)
    DELETE /api/index/<id>                 retirer une image de l'index
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

ROOT = Path(__file__).resolve().parent.parent          # racine du projet
sys.path.insert(0, str(Path(__file__).resolve().parent))   # pour "cbir" et "resources"

from cbir.index import FeatureIndex  # noqa: E402
from resources.common import JsonApi  # noqa: E402
from resources.descriptors import DescriptorsResource  # noqa: E402
from resources.feedback import FeedbackResource  # noqa: E402
from resources.health import HealthResource  # noqa: E402
from resources.index_items import IndexCollectionResource, IndexItemResource  # noqa: E402
from resources.search import SearchResource  # noqa: E402

MAX_UPLOAD_MB = 20


def load_index(index_dir: Path) -> FeatureIndex | None:
    """Charge l'index s'il existe ; sinon None (l'API démarre quand même, /api/health le signale)."""
    if not (index_dir / "ids.npy").exists():
        print(f"[cbir] aucun index dans {index_dir} : lancer cbir_api/scripts/build_index.py")
        return None
    index = FeatureIndex.load(index_dir)
    print(f"[cbir] index chargé : {len(index)} images")
    return index


def create_app(index: FeatureIndex | None = None, index_dir: str | Path | None = None,
               persist: bool = True) -> Flask:
    """Fabrique de l'application (*application factory*).

    - ``index`` : index déjà en mémoire (utilisé par les tests) ; sinon chargé depuis ``index_dir``.
    - ``persist`` : réécrire l'index sur disque après chaque ajout/suppression.
    """
    load_dotenv(ROOT / ".env")
    if index_dir is None:
        index_dir = ROOT / os.getenv("INDEX_DIR", "./cbir_api/index")
    index_dir = Path(index_dir)

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024    # refuse les fichiers trop gros (413)
    app.config["JSON_SORT_KEYS"] = False
    app.config["CBIR_INDEX"] = index if index is not None else load_index(index_dir)
    app.config["CBIR_INDEX_DIR"] = index_dir
    app.config["CBIR_PERSIST"] = persist
    app.config["CBIR_LOCK"] = threading.Lock()     # une seule modification de l'index à la fois

    CORS(app)                                       # le frontend (autre port) peut appeler l'API
    api = JsonApi(app, prefix="/api")
    api.add_resource(HealthResource, "/health")
    api.add_resource(DescriptorsResource, "/descriptors")
    api.add_resource(SearchResource, "/search")
    api.add_resource(FeedbackResource, "/feedback")             # retour de pertinence FRE (étape 7)
    api.add_resource(IndexCollectionResource, "/index")
    api.add_resource(IndexItemResource, "/index/<path:image_id>")   # <path:> : l'id contient des "/"

    @app.errorhandler(HTTPException)
    def json_error(err: HTTPException):
        """Erreurs hors ressources (route inconnue, fichier trop gros) aussi en JSON, pas en page HTML."""
        return jsonify(error=err.description, status=err.code), err.code

    return app


if __name__ == "__main__":
    load_dotenv(ROOT / ".env")
    port = int(os.getenv("CBIR_PORT", "5001"))
    create_app().run(host="127.0.0.1", port=port, debug=False, threaded=True)
