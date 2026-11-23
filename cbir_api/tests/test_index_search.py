"""Tests de l'index, de la recherche simple et des métriques (étape 3).

Les données sont fabriquées : aucun besoin de la base GHIM-10K.
"""

import cv2
import numpy as np
import pytest

from cbir import descriptors as D
from cbir.dataset import scan_dataset
from cbir.index import FeatureIndex
from cbir.metrics import average_precision, precision_at_k, recall_at_k
from cbir.search import combined_distance, per_descriptor_distances, search, search_by_id, weighted_distance


def random_index(n=30, seed=0, n_labels=3):
    rng = np.random.default_rng(seed)
    scales = rng.uniform(0.01, 50, D.FEATURE_DIM)          # composantes d'échelles très différentes
    raw = rng.normal(size=(n, D.FEATURE_DIM)) * scales
    ids = [f"c{i % n_labels}/img_{i:03d}.jpg" for i in range(n)]
    labels = [f"c{i % n_labels}" for i in range(n)]
    return FeatureIndex(ids, labels, raw)


# ---------------------------------------------------------------------- dataset
def test_scan_dataset_categories_et_ordre(tmp_path):
    for cat in ("flower", "aircraft"):
        (tmp_path / cat).mkdir()
        for i in (2, 1):
            cv2.imwrite(str(tmp_path / cat / f"{i}.jpg"), np.zeros((8, 8, 3), np.uint8))
    (tmp_path / "aircraft" / "notes.txt").write_text("pas une image")
    items = scan_dataset(tmp_path)
    assert items == [("aircraft/1.jpg", "aircraft"), ("aircraft/2.jpg", "aircraft"),
                     ("flower/1.jpg", "flower"), ("flower/2.jpg", "flower")]


def test_scan_dataset_dossier_absent(tmp_path):
    with pytest.raises(FileNotFoundError):
        scan_dataset(tmp_path / "absent")


# ------------------------------------------------------------------------ index
def test_zscore_moyenne_0_ecart_type_1():
    idx = random_index()
    assert np.allclose(idx.features.mean(axis=0), 0, atol=1e-9)
    assert np.allclose(idx.features.std(axis=0), 1)


def test_exemple_zscore_du_cours():
    # contraste 5, 50, 95 -> moyenne 50, écart-type 36,74 -> -1,22 ; 0 ; +1,22
    raw = np.zeros((3, D.FEATURE_DIM))
    raw[:, 0] = [5, 50, 95]
    idx = FeatureIndex(["a", "b", "c"], ["x"] * 3, raw)
    assert idx.features[:, 0] == pytest.approx([-1.2247, 0, 1.2247], abs=1e-4)


def test_composante_constante_ne_divise_pas_par_zero():
    raw = np.ones((4, D.FEATURE_DIM))
    raw[:, 0] = [1, 2, 3, 4]
    idx = FeatureIndex(list("abcd"), list("xxyy"), raw)
    assert np.isfinite(idx.features).all()


def test_sauvegarde_puis_chargement_identiques(tmp_path):
    idx = random_index()
    idx.save(tmp_path)
    back = FeatureIndex.load(tmp_path)
    assert back.ids.tolist() == idx.ids.tolist()
    assert back.labels.tolist() == idx.labels.tolist()
    assert np.allclose(back.features, idx.features)


def test_ajout_utilise_les_statistiques_de_la_base():
    idx = random_index()
    mean_before = idx.mean.copy()
    v = np.full(D.FEATURE_DIM, 3.0)
    idx.add("upload/new.jpg", v, "c0")
    assert len(idx) == 31 and "upload/new.jpg" in idx
    assert np.array_equal(idx.mean, mean_before)                    # statistiques figées
    assert np.allclose(idx.features[-1], (v - idx.mean) / idx.std)
    with pytest.raises(ValueError):
        idx.add("upload/new.jpg", v)                                # pas de doublon


def test_suppression_garde_les_tableaux_alignes():
    idx = random_index()
    target, after = idx.ids[5], idx.ids[6]
    feat_after = idx.features[6].copy()
    idx.remove(target)
    assert target not in idx and len(idx) == 29
    r = idx.row_of(after)                                           # l'image suivante a glissé d'une ligne
    assert r == 5 and np.allclose(idx.features[r], feat_after)
    assert idx.labels[r] == "c0"                                    # img_006 -> catégorie c0 (6 % 3)


# --------------------------------------------------------------------- distances
def test_exemple_chiffre_plage_foret():
    # Exemple du cours sur l'indexation (distance euclidienne simple)
    X = np.array([[0.60, 0.30, 0.10], [0.10, 0.80, 0.10], [0.75, 0.15, 0.10]])
    q = np.array([0.65, 0.25, 0.10])
    d = weighted_distance(X, q) * np.sqrt(3)                        # notre distance divise par sum w = 3
    assert d == pytest.approx([0.0707, 0.7778, 0.1414], abs=1e-4)
    assert np.argsort(d).tolist() == [0, 2, 1]


def test_poids_nul_ignore_une_composante():
    X = np.array([[0.0, 100.0], [1.0, 0.0]])
    q = np.array([0.0, 0.0])
    d = weighted_distance(X, q, w=np.array([1.0, 0.0]))            # seule la 1re composante compte
    assert d.tolist() == [0.0, 1.0]


def test_mode_equilibre_donne_le_meme_poids_a_chaque_descripteur():
    # Un écart de 1 sur TOUT l'histogramme (128 comp.) ou sur TOUTE la GLCM (7 comp.)
    # doit coûter autant en mode équilibré ; en mode global, l'histogramme coûte bien plus.
    s = D.descriptor_slices()
    q = np.zeros(D.FEATURE_DIM)
    a, b = q.copy(), q.copy()
    a[s["color_hist"]] = 1
    b[s["glcm"]] = 1
    X = np.stack([a, b])
    bal = combined_distance(X, q, mode="balanced")
    glob = combined_distance(X, q, mode="global")
    assert bal[0] == pytest.approx(bal[1])
    assert glob[0] > 4 * glob[1]


def test_distances_par_descripteur_forme():
    idx = random_index()
    assert per_descriptor_distances(idx.features, idx.features[0]).shape == (30, 5)


# ---------------------------------------------------------------------- recherche
def test_recherche_image_de_la_base_se_trouve_en_premier():
    idx = random_index()
    res = search(idx, idx.raw[7], k=5)
    assert res[0]["id"] == idx.ids[7] and res[0]["distance"] == pytest.approx(0)
    assert [r["distance"] for r in res] == sorted(r["distance"] for r in res)


def test_recherche_par_id_exclut_la_requete():
    idx = random_index()
    res = search_by_id(idx, idx.ids[7], k=29)
    assert idx.ids[7] not in [r["id"] for r in res] and len(res) == 29


def test_recherche_retrouve_sa_categorie_sur_vraies_images():
    # 3 « catégories » d'images réelles : rouge bruité, bleu bruité, damier noir/blanc
    rng = np.random.default_rng(0)

    def noisy(color):
        img = np.empty((64, 64, 3), np.uint8)
        img[:] = color
        return np.clip(img + rng.normal(0, 12, img.shape), 0, 255).astype(np.uint8)

    def checker():
        tile = (np.indices((64, 64)).sum(axis=0) // 8 % 2 * 255).astype(np.uint8)
        return cv2.cvtColor(np.clip(tile + rng.normal(0, 12, tile.shape), 0, 255).astype(np.uint8),
                            cv2.COLOR_GRAY2BGR)

    makers = {"rouge": lambda: noisy((30, 30, 220)), "bleu": lambda: noisy((220, 60, 30)), "damier": checker}
    ids, labels, vecs = [], [], []
    for lab, make in makers.items():
        for i in range(6):
            ids.append(f"{lab}/{i}.png")
            labels.append(lab)
            vecs.append(D.extract_feature_vector(make()))
    idx = FeatureIndex(ids, labels, np.stack(vecs))
    for lab in makers:
        res = search_by_id(idx, f"{lab}/0.png", k=5)
        assert all(r["label"] == lab for r in res), (lab, res)     # precision@5 = 100 %


# ---------------------------------------------------------------------- métriques
def test_metriques_exemple_a_la_main():
    rel = np.array([1, 0, 1, 1, 0])            # pertinents aux rangs 1, 3 et 4 ; 4 pertinents au total
    assert precision_at_k(rel, 5) == pytest.approx(3 / 5)
    assert recall_at_k(rel, 5, n_relevant=4) == pytest.approx(3 / 4)
    # AP = (1/1 + 2/3 + 3/4) / 4 = 0,6042
    assert average_precision(rel, n_relevant=4) == pytest.approx((1 + 2 / 3 + 3 / 4) / 4)


def test_ap_classement_parfait():
    assert average_precision(np.array([1, 1, 1, 0, 0])) == pytest.approx(1.0)
