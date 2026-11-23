"""Fixtures partagées par les tests du backend galerie.

- Base SQLite **en mémoire** (recréée pour chaque test) : pas besoin de PostgreSQL.
- Dossiers de stockage et de base d'images **temporaires**.
- **Faux client CBIR** (gallery_testutils.FakeCbir) : réponses prévisibles, sans lancer l'API.
"""

import pytest
from gallery_testutils import FakeCbir, register

from gallery import create_app
from gallery.config import TestConfig
from gallery.extensions import db


@pytest.fixture
def cbir():
    return FakeCbir()


@pytest.fixture
def app(tmp_path, cbir):
    class Cfg(TestConfig):
        STORAGE_DIR = tmp_path / "storage"
        DATASET_DIR = tmp_path / "dataset"

    application = create_app(Cfg, cbir_client=cbir)
    with application.app_context():
        db.create_all()  # tables créées directement (pas de migration en test)
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def alice(client):
    return register(client)


@pytest.fixture
def bob(client):
    return register(client, email="bob@example.com", username="Bob")
