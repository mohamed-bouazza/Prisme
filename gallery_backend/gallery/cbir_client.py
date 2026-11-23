"""Client HTTP de l'API CBIR (étape 4). Toute communication avec le moteur passe par ici.

Si l'API CBIR est arrêtée, on lève ``CbirUnavailable`` : les routes renvoient alors 503 au lieu de
planter, et les opérations qui n'en dépendent pas (upload, catégories...) continuent de fonctionner.
"""

from __future__ import annotations

from pathlib import Path

import requests
from flask import current_app


class CbirUnavailable(Exception):
    """L'API CBIR ne répond pas (arrêtée, délai dépassé)."""


class CbirError(Exception):
    """L'API CBIR a répondu par une erreur (4xx/5xx)."""

    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.status = status


class CbirClient:
    def __init__(self, base_url: str, timeout: float = 30):
        self.base_url = base_url.rstrip("/") + "/api"
        self.timeout = timeout

    def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            r = requests.request(method, self.base_url + path, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            reason = exc.__class__.__name__
            raise CbirUnavailable(f"API CBIR injoignable ({self.base_url}) : {reason}") from exc
        try:
            body = r.json()
        except ValueError:
            body = {"error": r.text[:200]}
        if r.status_code >= 400:
            raise CbirError(body.get("error", "erreur inconnue"), r.status_code)
        return body

    @staticmethod
    def _file(path: Path, name: str | None = None):
        return {"image": (name or path.name, path.read_bytes())}

    # ---------------------------------------------------------------- routes
    def health(self) -> dict:
        return self._request("GET", "/health")

    def descriptors(self, path: Path) -> dict:
        return self._request("POST", "/descriptors", files=self._file(path))

    def index_add(self, cbir_id: str, path: Path, label: str = "") -> dict:
        return self._request("POST", "/index", files=self._file(path), data={"id": cbir_id, "label": label})

    def index_remove(self, cbir_id: str) -> None:
        try:
            self._request("DELETE", "/index/" + requests.utils.quote(cbir_id, safe="/"))
        except CbirError as exc:
            if exc.status != 404:                       # déjà absente de l'index : rien à faire
                raise

    def search_by_id(self, cbir_id: str, k: int, **options) -> dict:
        return self._request("POST", "/search", json={"id": cbir_id, "k": k, **options})

    def search_by_file(self, data: bytes, filename: str, k: int, desc_weights: str | None = None) -> dict:
        form = {"k": str(k)}
        if desc_weights:
            form["desc_weights"] = desc_weights                 # déjà au format JSON (texte)
        return self._request("POST", "/search", files={"image": (filename, data)}, data=form)

    def feedback_by_id(self, cbir_id: str, relevant: list[str], non_relevant: list[str],
                       k: int, level: int) -> dict:
        body = {"query_id": cbir_id, "relevant": relevant, "non_relevant": non_relevant,
                "k": k, "level": level}
        return self._request("POST", "/feedback", json=body)

    def feedback_by_file(self, data: bytes, filename: str, relevant: list[str], non_relevant: list[str],
                         k: int, level: int) -> dict:
        import json
        form = {"relevant": json.dumps(relevant), "non_relevant": json.dumps(non_relevant),
                "k": str(k), "level": str(level)}
        return self._request("POST", "/feedback", files={"image": (filename, data)}, data=form)


def get_cbir() -> CbirClient:
    """Client de l'application courante (remplaçable par un faux client dans les tests)."""
    client = current_app.extensions.get("cbir_client")
    if client is None:
        client = CbirClient(current_app.config["CBIR_API_URL"], current_app.config["CBIR_TIMEOUT"])
        current_app.extensions["cbir_client"] = client
    return client
