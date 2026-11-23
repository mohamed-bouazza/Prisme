"""Tests des descripteurs : on vérifie chaque descripteur sur des images dont on connaît
la réponse à l'avance (image unie, image moitié rouge / moitié bleue, exemples calculés à la main).

Lancer depuis la racine du projet :  python -m pytest -v
"""

import numpy as np
import pytest
from skimage.feature import graycomatrix

from cbir import descriptors as D

# Couleurs au format BGR (ordre OpenCV)
RED = (0, 0, 255)
BLUE = (255, 0, 0)


def solid(color, h=100, w=100):
    """Image unie d'une seule couleur."""
    img = np.zeros((h, w, 3), np.uint8)
    img[:] = color
    return img


def half_red_half_blue():
    """Image dont la moitié gauche est rouge et la moitié droite bleue."""
    img = solid(RED)
    img[:, 50:] = BLUE
    return img


def textured(seed=0):
    """Image de bruit aléatoire : une texture quelconque mais reproductible."""
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, (120, 160, 3), dtype=np.uint8)


# ----------------------------------------------------------------- préparation
def test_prepare_image_standardise_le_format():
    gray = np.full((50, 80), 128, np.uint8)                 # niveaux de gris, 2D
    rgba = np.zeros((40, 30, 4), np.uint8)                  # avec canal alpha
    for img in (gray, rgba, textured()):
        out = D.prepare_image(img)
        assert out.shape == (D.IMG_SIZE, D.IMG_SIZE, 3)
        assert out.dtype == np.uint8


# ------------------------------------------------------------ histogramme HSV
def test_histogramme_normalise():
    h = D.color_histogram(D.prepare_image(textured()))
    assert h.shape == (128,)
    assert h.sum() == pytest.approx(1.0)


def test_histogramme_image_unie_une_seule_case():
    h = D.color_histogram(solid(RED))
    assert np.count_nonzero(h) == 1                         # tous les pixels dans la même case
    assert h.max() == pytest.approx(1.0)


def test_histogramme_deux_couleurs_deux_cases_a_50():
    h = D.color_histogram(half_red_half_blue())
    assert sorted(h[h > 0]) == pytest.approx([0.5, 0.5])


def test_histogramme_robuste_au_redimensionnement():
    img = D.prepare_image(textured())
    small = D.prepare_image(img[::2, ::2])                  # même image, moitié moins de pixels
    assert np.abs(D.color_histogram(img) - D.color_histogram(small)).sum() < 0.3


# ----------------------------------------------------------- moments couleur
def test_moments_exemple_du_guide():
    # Exemple calculé à la main : pixels 10, 20, 30, 100
    mean, std, skew = D.channel_moments([10, 20, 30, 100])
    assert mean == pytest.approx(40)
    assert std == pytest.approx(35.36, abs=0.01)
    assert skew == pytest.approx(35.57, abs=0.01)           # positive : queue vers les valeurs claires


def test_moments_asymetrie_negative():
    _, _, skew = D.channel_moments([100, 90, 80, 10])        # quelques valeurs très basses
    assert skew < 0


def test_moments_image_unie_ecart_type_nul():
    m = D.color_moments(solid(RED))
    assert m.shape == (9,)
    assert m[1] == m[4] == m[7] == 0                        # écart-type nul sur H, S et V


# ------------------------------------------------------ couleurs dominantes
def test_couleurs_dominantes_rouge_et_bleu():
    dom = D.dominant_colors(half_red_half_blue())
    top2 = dom["colors"][:2]
    assert [c["proportion"] for c in top2] == pytest.approx([0.5, 0.5], abs=0.02)
    # La conversion Lab -> RGB sur 8 bits arrondit légèrement (ex. #FF0201 au lieu de #FF0000) :
    # on vérifie que chaque couleur trouvée est à moins de 5 unités du rouge ou du bleu pur.
    found = sorted(tuple(c["rgb"]) for c in top2)
    expected = sorted([(255, 0, 0), (0, 0, 255)])
    for f, e in zip(found, expected, strict=True):
        assert np.abs(np.array(f) - np.array(e)).max() <= 5
    assert dom["vector"].shape == (20,)


def test_couleurs_dominantes_triees_et_reproductibles():
    img = D.prepare_image(textured())
    a, b = D.dominant_colors(img), D.dominant_colors(img)
    props = [c["proportion"] for c in a["colors"]]
    assert props == sorted(props, reverse=True)             # tri décroissant
    assert np.allclose(a["vector"], b["vector"])            # random_state fixé -> même résultat


# --------------------------------------------------------------------- GLCM
def test_glcm_exemple_du_guide():
    # Exemple 4x4 calculé à la main : voisin de droite, distance 1, non symétrique
    img = np.array([[0, 0, 1, 1],
                    [0, 0, 1, 1],
                    [0, 2, 2, 2],
                    [2, 2, 3, 3]], dtype=np.uint8)
    P = graycomatrix(img, distances=[1], angles=[0], levels=4, symmetric=False, normed=True)
    f = D.glcm_properties(P)
    assert f["contrast"] == pytest.approx(7 / 12)
    assert f["homogeneity"] == pytest.approx(9.7 / 12)
    assert f["ASM"] == pytest.approx(24 / 144)
    assert f["energy"] == pytest.approx(np.sqrt(24 / 144))
    assert f["dissimilarity"] == pytest.approx(5 / 12)
    assert f["entropy"] == pytest.approx(2.689, abs=0.001)


def test_glcm_image_unie():
    f = D.glcm_features(solid(BLUE))
    assert f["contrast"] == 0                               # aucun écart entre voisins
    assert f["homogeneity"] == pytest.approx(1)
    assert f["energy"] == pytest.approx(1)
    assert f["entropy"] == pytest.approx(0)                 # aucun désordre


def test_glcm_bruit_plus_contraste_que_uni():
    assert D.glcm_features(D.prepare_image(textured()))["contrast"] > 10


# ---------------------------------------------------------------------- LBP
def test_lbp_histogramme_normalise():
    h = D.lbp_histogram(D.prepare_image(textured()))
    assert h.shape == (10,)
    assert h.sum() == pytest.approx(1.0)


def test_lbp_image_unie_un_seul_motif():
    # Tous les voisins sont égaux au centre -> tous les bits à 1 -> étiquette 8 (P)
    h = D.lbp_histogram(solid(RED))
    assert h[8] == pytest.approx(1.0)


def test_lbp_insensible_a_la_luminosite():
    # Le LBP ne dépend que de comparaisons : ajouter 40 à tous les pixels ne change (presque) rien.
    # "Presque" : les 4 voisins diagonaux tombent entre deux pixels et sont interpolés en nombres
    # à virgule ; lors d'égalités exactes, l'arrondi peut basculer un bit -> écart de quelques 0,1 %.
    rng = np.random.default_rng(1)
    img = rng.integers(0, 200, (64, 64, 3), dtype=np.uint8)
    brighter = img + np.uint8(40)                           # reste < 256 : pas de débordement
    assert np.allclose(D.lbp_histogram(img), D.lbp_histogram(brighter), atol=0.005)


# ------------------------------------------------------------- assemblage
def test_vecteur_final_174_et_tranches():
    v = D.extract_feature_vector(textured())
    assert v.shape == (D.FEATURE_DIM,) == (174,)
    assert np.isfinite(v).all()
    s = D.descriptor_slices()
    assert s["color_hist"] == slice(0, 128)
    assert s["lbp"] == slice(164, 174)


def test_compute_all_serialisable_json():
    import json

    out = D.compute_all(half_red_half_blue())
    json.dumps(out)                                         # ne doit pas lever d'erreur
    assert set(out) == {"color_histogram", "color_moments", "dominant_colors", "glcm", "lbp"}
    assert len(out["dominant_colors"]) == D.N_DOMINANT
