"""Outils de test réutilisables (importés par conftest.py et par les fichiers de test)."""

from __future__ import annotations

import io

from PIL import Image as PILImage

from gallery.cbir_client import CbirError, CbirUnavailable


class FakeCbir:
    """Imite CbirClient sans lancer l'API. ``indexed`` = ids du « faux index », dans l'ordre d'ajout."""

    def __init__(self):
        self.indexed: list[str] = []
        self.available = True

    def _check(self):
        if not self.available:
            raise CbirUnavailable("arrêtée")

    def health(self):
        self._check()
        return {"status": "ok", "n_images": len(self.indexed)}

    def descriptors(self, path):
        self._check()
        return {"descriptors": {"glcm": {"contrast": 1.0}, "path": path.name}}

    def index_add(self, cbir_id, path, label=""):
        self._check()
        if cbir_id in self.indexed:
            raise CbirError("déjà indexée", 409)
        self.indexed.append(cbir_id)
        return {"id": cbir_id}

    def index_remove(self, cbir_id):
        self._check()
        if cbir_id in self.indexed:
            self.indexed.remove(cbir_id)

    def search_by_id(self, cbir_id, k, **options):
        self._check()
        others = [i for i in self.indexed if i != cbir_id][:k]
        return {"results": [{"id": i, "distance": 0.1 * n} for n, i in enumerate(others, 1)], "took_ms": 1}

    def feedback_by_id(self, cbir_id, relevant, non_relevant, k, level):
        self._check()
        self.last_feedback = {"query": cbir_id, "relevant": relevant, "non_relevant": non_relevant}
        # imite FRE : les pertinentes d'abord, puis le reste ; jamais la requête ni les non pertinentes
        rest = [i for i in self.indexed if i not in relevant and i not in non_relevant and i != cbir_id]
        ordered = (relevant + rest)[:k]
        return {"results": [{"id": i, "distance": 0.1 * n} for n, i in enumerate(ordered, 1)],
                "desc_weights": {"color_hist": 0.2}, "counts": {}, "n_relevant": len(relevant) + 1,
                "n_nonrelevant": len(non_relevant), "took_ms": 1}

    def feedback_by_file(self, data, filename, relevant, non_relevant, k, level):
        return self.feedback_by_id(None, relevant, non_relevant, k, level)

    def search_by_file(self, data, filename, k, desc_weights=None):
        self._check()
        return {"results": [{"id": i, "distance": 0.1 * n} for n, i in enumerate(self.indexed[:k], 1)],
                "took_ms": 1}


def png(color=(255, 0, 0), size=(64, 48), fmt="PNG") -> bytes:
    """Octets d'une image unie (PNG par défaut)."""
    buf = io.BytesIO()
    PILImage.new("RGB", size, color).save(buf, fmt)
    return buf.getvalue()


def register(client, email="alice@example.com", password="motdepasse1", username="Alice") -> dict:
    """Crée un compte et renvoie l'en-tête Authorization à utiliser."""
    r = client.post("/api/auth/register", json={"email": email, "password": password, "username": username})
    assert r.status_code == 201, r.get_json()
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


def upload(client, headers, *files, category_id=None):
    """Envoie des images : files = (octets, nom), ..."""
    data = {"files": [(io.BytesIO(b), name) for b, name in files]}
    if category_id is not None:
        data["category_id"] = str(category_id)
    return client.post("/api/images", data=data, headers=headers, content_type="multipart/form-data")
