"""Backend galerie (Flask) : authentification, images, catégories hiérarchiques, transformations,
et relais vers l'API CBIR (descripteurs, recherche).

    create_app()  ->  application Flask prête à servir (voir gallery_backend/wsgi.py)
"""

from __future__ import annotations

from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from gallery.cbir_client import CbirError, CbirUnavailable
from gallery.config import ROOT, Config
from gallery.extensions import db, jwt, migrate
from gallery.storage import InvalidImage
from gallery.transforms import TransformError


def create_app(config_class=Config, cbir_client=None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.config["STORAGE_DIR"].mkdir(parents=True, exist_ok=True)
    if cbir_client is not None:                             # tests : faux client CBIR
        app.extensions["cbir_client"] = cbir_client

    db.init_app(app)
    migrate.init_app(app, db, directory=str(ROOT / "gallery_backend" / "migrations"))
    jwt.init_app(app)
    # Le frontend passe par le proxy de Vite (même origine) ; CORS reste utile si on l'appelle directement.
    CORS(app, origins=["http://localhost:5173", "http://127.0.0.1:5173"], supports_credentials=True)

    from gallery import models  # noqa: F401  (enregistre les tables auprès de SQLAlchemy)
    from gallery.api import auth, categories, images, search
    from gallery.cli import register_cli

    for module in (auth, categories, images, search):
        app.register_blueprint(module.bp)
    register_cli(app)
    _register_errors(app)

    @app.get("/api/health")
    def health():
        from gallery.cbir_client import get_cbir
        try:
            cbir = get_cbir().health()
        except CbirUnavailable:
            cbir = None
        return {"status": "ok", "cbir": cbir}

    return app


def _error(message: str, status: int):
    return jsonify(error=message, status=status), status


def _register_errors(app: Flask) -> None:
    """Toutes les erreurs au même format JSON : {"error": "...", "status": 400}."""

    @app.errorhandler(HTTPException)
    def http_error(e):
        return _error(e.description, e.code)

    @app.errorhandler(InvalidImage)
    @app.errorhandler(TransformError)
    def bad_input(e):
        return _error(str(e), 400)

    @app.errorhandler(CbirUnavailable)
    def cbir_down(e):
        return _error("Moteur de recherche (API CBIR) indisponible : lancer cbir_api/app.py", 503)

    @app.errorhandler(CbirError)
    def cbir_error(e):
        return _error(f"API CBIR : {e}", 502)              # 502 : erreur d'un service appelé

    # Erreurs JWT (absent, expiré, invalide) : même format que le reste
    @jwt.unauthorized_loader
    def missing_token(reason):
        return _error("Authentification requise", 401)

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return _error("Jeton invalide", 401)

    @jwt.expired_token_loader
    def expired_token(header, payload):
        return _error("Session expirée : se reconnecter", 401)
