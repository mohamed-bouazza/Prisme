"""Tests de l'API REST (étape 4), avec le client de test de Flask : aucun serveur à lancer.

``app.test_client()`` simule des requêtes HTTP directement dans le processus Python.
"""

import io
import json

import cv2
import numpy as np
import pytest

from app import create_app
from cbir import descriptors as D
from cbir.index import FeatureIndex


def make_image(kind: str, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = np.empty((90, 120, 3), np.uint8)
    if kind == "rouge":
        img[:] = (30, 30, 220)
    elif kind == "bleu":
        img[:] = (220, 60, 30)
    else:                                                   # damier
        img[:] = (np.indices((90, 120)).sum(axis=0) // 10 % 2 * 255)[..., None]
    return np.clip(img + rng.normal(0, 12, img.shape), 0, 255).astype(np.uint8)


def png_bytes(img: np.ndarray) -> io.BytesIO:
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return io.BytesIO(buf.tobytes())


@pytest.fixture(scope="module")
def base():
    """12 images (3 catégories x 4) : calculées une fois pour tout le module (c'est le plus long)."""
    ids, labels, vecs = [], [], []
    for kind in ("rouge", "bleu", "damier"):
        for i in range(4):
            ids.append(f"{kind}/{i}.png")
            labels.append(kind)
            vecs.append(D.extract_feature_vector(make_image(kind, seed=i)))
    return ids, labels, np.stack(vecs)


@pytest.fixture
def client(base, tmp_path):
    """Une application neuve par test (copie de l'index) : un test ne peut pas en perturber un autre."""
    ids, labels, raw = base
    app = create_app(index=FeatureIndex(ids, labels, raw.copy()), index_dir=tmp_path, persist=True)
    app.config["TESTING"] = True
    return app.test_client()


# ---------------------------------------------------------------------------- health
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.get_json()
    assert body["index_loaded"] is True and body["n_images"] == 12 and body["n_categories"] == 3
    assert body["feature_dim"] == 174


def test_health_sans_index(tmp_path):
    app = create_app(index_dir=tmp_path / "vide")
    c = app.test_client()
    assert c.get("/api/health").get_json()["index_loaded"] is False
    r = c.post("/api/search", json={"id": "x"})
    assert r.status_code == 503 and "build_index" in r.get_json()["error"]


# ------------------------------------------------------------------------ descripteurs
def test_descripteurs_d_une_image_envoyee(client):
    r = client.post("/api/descriptors", data={"image": (png_bytes(make_image("rouge", 9)), "r.png")},
                    content_type="multipart/form-data")
    assert r.status_code == 200
    body = r.get_json()
    assert body["width"] == 120 and body["height"] == 90
    assert set(body["descriptors"]) == {"color_histogram", "color_moments", "dominant_colors", "glcm", "lbp"}


def test_descripteurs_sans_fichier(client):
    r = client.post("/api/descriptors", data={}, content_type="multipart/form-data")
    assert r.status_code == 400 and "image" in r.get_json()["error"]


def test_descripteurs_fichier_qui_n_est_pas_une_image(client):
    r = client.post("/api/descriptors", data={"image": (io.BytesIO(b"pas une image"), "x.jpg")},
                    content_type="multipart/form-data")
    assert r.status_code == 400


# ---------------------------------------------------------------------------- recherche
def test_recherche_par_id(client):
    r = client.post("/api/search", json={"id": "damier/0.png", "k": 3})
    assert r.status_code == 200
    body = r.get_json()
    assert body["query"] == {"type": "indexed", "id": "damier/0.png", "label": "damier"}
    res = body["results"]
    assert [x["rank"] for x in res] == [1, 2, 3]
    assert all(x["label"] == "damier" for x in res)                 # les 3 autres damiers
    assert "damier/0.png" not in [x["id"] for x in res]             # la requête est exclue


def test_recherche_par_image_envoyee(client):
    data = {"image": (png_bytes(make_image("bleu", 99)), "q.png"), "k": "4"}
    r = client.post("/api/search", data=data, content_type="multipart/form-data")
    assert r.status_code == 200
    body = r.get_json()
    assert body["query"]["type"] == "upload"
    assert [x["label"] for x in body["results"]] == ["bleu"] * 4


def test_recherche_exclusion_et_poids(client):
    body = client.post("/api/search", json={
        "id": "rouge/0.png", "k": 11, "exclude": ["rouge/1.png"], "desc_weights": {"glcm": 1, "lbp": 1},
    }).get_json()
    ids = [x["id"] for x in body["results"]]
    assert "rouge/1.png" not in ids and len(ids) == 10              # 12 - requête - exclue


@pytest.mark.parametrize("payload, fragment", [
    ({"id": "inconnue.png"}, "non indexée"),
    ({"id": "rouge/0.png", "k": 0}, "'k'"),
    ({"id": "rouge/0.png", "k": "abc"}, "'k'"),
    ({"id": "rouge/0.png", "mode": "magique"}, "'mode'"),
    ({"id": "rouge/0.png", "desc_weights": {"forme": 1}}, "inconnus"),
    ({"id": "rouge/0.png", "desc_weights": {"glcm": 0}}, "> 0"),
    ({}, "Donner soit"),
])
def test_recherche_erreurs(client, payload, fragment):
    r = client.post("/api/search", json=payload)
    assert r.status_code in (400, 404)
    assert fragment in r.get_json()["error"]


# --------------------------------------------------------------- cycle de vie de l'index
def test_ajout_puis_recherche_puis_suppression(client, tmp_path):
    img = make_image("rouge", 50)
    data = {"image": (png_bytes(img), "n.png"), "id": "u/1.png", "label": "rouge"}
    r = client.post("/api/index", data=data, content_type="multipart/form-data")
    assert r.status_code == 201 and r.get_json()["n_images"] == 13
    assert (tmp_path / "ids.npy").exists()                          # index réécrit sur disque
    assert "u/1.png" in FeatureIndex.load(tmp_path)

    assert client.get("/api/index/u/1.png").get_json() == {"id": "u/1.png", "label": "rouge"}

    # la nouvelle image est trouvée par une recherche sur une autre image rouge
    res = client.post("/api/search", json={"id": "rouge/0.png", "k": 4}).get_json()["results"]
    assert "u/1.png" in [x["id"] for x in res]

    r = client.delete("/api/index/u/1.png")
    assert r.status_code == 200 and r.get_json()["n_images"] == 12
    assert client.get("/api/index/u/1.png").status_code == 404
    assert client.delete("/api/index/u/1.png").status_code == 404


def test_ajout_doublon_refuse(client):
    data = {"image": (png_bytes(make_image("bleu", 1)), "b.png"), "id": "bleu/0.png"}
    r = client.post("/api/index", data=data, content_type="multipart/form-data")
    assert r.status_code == 409


def test_ajout_sans_id(client):
    data = {"image": (png_bytes(make_image("bleu", 1)), "b.png")}
    assert client.post("/api/index", data=data, content_type="multipart/form-data").status_code == 400


def test_route_inconnue_en_json(client):
    r = client.get("/api/nexiste-pas")
    assert r.status_code == 404
    assert json.loads(r.data)["status"] == 404
