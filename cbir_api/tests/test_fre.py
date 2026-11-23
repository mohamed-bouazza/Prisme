"""Tests du retour de pertinence FRE (étape 7) : formules, comportement, route de l'API."""

import cv2
import numpy as np
import pytest

from app import create_app
from cbir import descriptors as D
from cbir.feedback.fre import EPS, descriptor_counts, descriptor_weights, fre_search, intra_weights
from cbir.index import FeatureIndex


# --------------------------------------------------------------------------- formules
def test_poids_intra_exemple_du_guide():
    # Exemple calculé à la main : 3 images pertinentes, 3 composantes
    R = np.array([[0.50, 0.10, 0.30],
                  [0.52, 0.90, 0.35],
                  [0.48, 0.50, 0.40]])
    w = intra_weights(R)
    assert w == pytest.approx([60.9, 3.06, 24.4], rel=0.01)
    assert (w / w.sum()) == pytest.approx([0.689, 0.035, 0.277], abs=0.002)


def test_poids_intra_composante_identique_ne_divise_pas_par_zero():
    w = intra_weights(np.array([[1.0, 2.0], [1.0, 3.0]]))     # 1re composante : σ = 0
    assert w[0] == pytest.approx(1 / EPS) and np.isfinite(w).all()


def test_comptage_par_descripteur():
    # 4 images jugées (2 pertinentes) ; descripteur 0 classe bien les pertinentes, descripteur 1 non
    D_judged = np.array([[0.1, 0.9], [0.2, 0.8], [0.9, 0.1], [0.8, 0.2]])
    is_rel = np.array([True, True, False, False])
    assert descriptor_counts(D_judged, is_rel).tolist() == [2, 0]
    e = descriptor_weights(np.array([2.0, 0.0]))
    assert e.tolist() == pytest.approx([0.75, 0.25])           # (2+1)/4 et (0+1)/4 : jamais nul
    assert e.sum() == pytest.approx(1)


# ------------------------------------------------------------------ comportement
def make_index():
    """3 familles d'images réelles, 6 chacune : rouges, bleues, damiers."""
    rng = np.random.default_rng(0)

    def noisy(color):
        img = np.empty((64, 64, 3), np.uint8)
        img[:] = color
        return np.clip(img + rng.normal(0, 18, img.shape), 0, 255).astype(np.uint8)

    def checker():
        t = (np.indices((64, 64)).sum(axis=0) // 8 % 2 * 255).astype(np.uint8)
        noisy_t = np.clip(t + rng.normal(0, 18, t.shape), 0, 255).astype(np.uint8)
        return cv2.cvtColor(noisy_t, cv2.COLOR_GRAY2BGR)

    makers = {"rouge": lambda: noisy((40, 40, 210)), "bleu": lambda: noisy((210, 70, 40)), "damier": checker}
    ids, labels, vecs = [], [], []
    for lab, make in makers.items():
        for i in range(6):
            ids.append(f"{lab}/{i}")
            labels.append(lab)
            vecs.append(D.extract_feature_vector(make()))
    return FeatureIndex(ids, labels, np.stack(vecs))


@pytest.fixture(scope="module")
def index():
    return make_index()


def test_fre_exclut_requete_et_non_pertinentes(index):
    res = fre_search(index, ["rouge/1"], ["bleu/0", "damier/0"], query_id="rouge/0", k=20, level=2)
    ids = [str(index.ids[r]) for r in res.rows]
    assert "rouge/0" not in ids and "bleu/0" not in ids and "damier/0" not in ids
    assert len(ids) == 18 - 3
    assert list(res.distances) == sorted(res.distances)


def test_fre_ramene_la_bonne_famille_en_tete(index):
    res = fre_search(index, ["damier/1", "damier/2"], ["rouge/0"], query_id="damier/0", k=4, level=2)
    assert all(str(index.labels[r]) == "damier" for r in res.rows)
    assert res.n_relevant == 3 and res.n_nonrelevant == 1      # requête + 2 pertinentes


def test_poids_inter_somme_un_et_uniformes_sans_non_pertinentes(index):
    res = fre_search(index, ["rouge/1"], [], query_id="rouge/0", k=5, level=2)
    assert sum(res.desc_weights.values()) == pytest.approx(1)
    assert list(res.desc_weights.values()) == pytest.approx([0.2] * 5)
    assert res.counts == {}                                    # pas de comptage sans images non pertinentes


def test_niveau_0_poids_uniformes(index):
    res = fre_search(index, ["rouge/1"], [], query_id="rouge/0", k=5, level=0)
    assert np.allclose(res.weights, 1)


def test_requete_envoyee_non_indexee(index):
    q_raw = index.raw[index.row_of("bleu/3")]
    res = fre_search(index, ["bleu/1"], [], query_raw=q_raw, k=3, level=1)
    assert all(str(index.labels[r]) == "bleu" for r in res.rows)


def test_sans_aucune_image_erreur(index):
    with pytest.raises(ValueError):
        fre_search(index, [], [], k=3)


# ----------------------------------------------------------------------- route API
@pytest.fixture
def client(index, tmp_path):
    idx = FeatureIndex(index.ids, index.labels, index.raw.copy())
    return create_app(index=idx, index_dir=tmp_path, persist=False).test_client()


def test_route_feedback(client):
    r = client.post("/api/feedback", json={"query_id": "damier/0", "relevant": ["damier/1"],
                                           "non_relevant": ["rouge/0"], "k": 3})
    assert r.status_code == 200
    body = r.get_json()
    assert [x["rank"] for x in body["results"]] == [1, 2, 3]
    assert all(x["label"] == "damier" for x in body["results"])
    assert set(body["desc_weights"]) == {"color_hist", "color_moments", "dominant_colors", "glcm", "lbp"}
    assert body["level"] == 2 and body["n_relevant"] == 2


@pytest.mark.parametrize("payload, code", [
    ({"relevant": ["damier/1"]}, 400),                                  # pas de requête
    ({"query_id": "inconnue"}, 404),
    ({"query_id": "damier/0", "relevant": ["inconnue"]}, 404),
    ({"query_id": "damier/0", "relevant": "pas une liste"}, 400),
    ({"query_id": "damier/0", "level": 5}, 400),
])
def test_route_feedback_erreurs(client, payload, code):
    assert client.post("/api/feedback", json=payload).status_code == code
