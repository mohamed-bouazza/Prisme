"""Descripteurs visuels du contenu d'une image (couleur et texture).

Ce module calcule les 5 descripteurs demandés par l'énoncé :

    Couleur : histogramme HSV, moments de couleur, couleurs dominantes
    Texture : propriétés de la matrice de co-occurrence (GLCM), histogramme LBP

Deux usages :
    - ``extract_feature_vector(img)`` -> un vecteur NumPy de 174 nombres, utilisé pour la recherche ;
    - ``compute_all(img)``            -> un dictionnaire lisible (JSON), utilisé pour l'affichage.

Toutes les fonctions reçoivent une image OpenCV au format **BGR** (ordre Bleu, Vert, Rouge),
de type ``uint8`` (valeurs de 0 à 255). Voir ``load_image`` et ``prepare_image``.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import cv2
import numpy as np
from skimage.feature import graycomatrix, graycoprops, local_binary_pattern
from sklearn.cluster import KMeans
from sklearn.exceptions import ConvergenceWarning

# ---------------------------------------------------------------------------
# Paramètres (centralisés ici pour pouvoir les ajuster et les citer dans le rapport)
# ---------------------------------------------------------------------------
IMG_SIZE = 256                      # toutes les images sont ramenées à 256x256 avant calcul
HSV_BINS = (8, 4, 4)                # cases de l'histogramme : 8 teintes x 4 saturations x 4 valeurs
N_DOMINANT = 5                      # nombre de couleurs dominantes (K du K-means)
KMEANS_SIZE = 64                    # K-means sur une image 64x64 (4096 pixels) : rapide et suffisant
GLCM_LEVELS = 32                    # 256 niveaux de gris ramenés à 32 pour la GLCM
GLCM_DISTANCES = (1, 2, 3)          # distances entre pixels voisins
GLCM_ANGLES = (0, np.pi / 4, np.pi / 2, 3 * np.pi / 4)   # 0°, 45°, 90°, 135°
GLCM_PROPS = ("contrast", "dissimilarity", "homogeneity", "energy", "correlation", "ASM")
LBP_P, LBP_R = 8, 1                 # LBP : 8 voisins sur un cercle de rayon 1

# Ordre et taille de chaque descripteur dans le vecteur final.
# Les "tranches" (slices) permettent ensuite de calculer une distance par descripteur (FRE à 2 niveaux).
DESCRIPTOR_DIMS = {
    "color_hist": int(np.prod(HSV_BINS)),       # 128
    "color_moments": 9,                         # 3 moments x 3 canaux
    "dominant_colors": N_DOMINANT * 4,          # 5 x (L, a, b, proportion) = 20
    "glcm": len(GLCM_PROPS) + 1,                # 6 propriétés + entropie = 7
    "lbp": LBP_P + 2,                           # 10 motifs uniformes
}


def descriptor_slices() -> dict[str, slice]:
    """Position de chaque descripteur dans le vecteur final.

    Exemple : {"color_hist": slice(0, 128), "color_moments": slice(128, 137), ...}
    """
    slices, start = {}, 0
    for name, dim in DESCRIPTOR_DIMS.items():
        slices[name] = slice(start, start + dim)
        start += dim
    return slices


FEATURE_DIM = sum(DESCRIPTOR_DIMS.values())     # 174


# ---------------------------------------------------------------------------
# Lecture et préparation
# ---------------------------------------------------------------------------
def load_image(path: str | Path) -> np.ndarray:
    """Lit une image depuis le disque au format BGR.

    On passe par ``np.fromfile`` + ``cv2.imdecode`` plutôt que ``cv2.imread`` car ``imread``
    échoue silencieusement (renvoie None) sous Windows quand le chemin contient des accents.
    """
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Image illisible : {path}")
    return img


def decode_image(raw: bytes) -> np.ndarray:
    """Décode une image reçue en octets (par exemple un fichier uploadé via l'API)."""
    img = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError("Les données reçues ne sont pas une image valide.")
    return img


def prepare_image(img: np.ndarray, size: int = IMG_SIZE) -> np.ndarray:
    """Ramène n'importe quelle image à un format standard : BGR, 3 canaux, uint8, size x size.

    - image en niveaux de gris (2D)   -> convertie en 3 canaux
    - image avec transparence (BGRA)  -> canal alpha supprimé
    - taille quelconque               -> redimensionnée (INTER_AREA = meilleure qualité en réduction)

    Sans cette étape, deux images de tailles différentes donneraient des descripteurs
    non comparables, et les images PNG transparentes feraient planter les conversions.
    """
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    if img.dtype != np.uint8:                       # ex. images 16 bits
        img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    return cv2.resize(img, (size, size), interpolation=cv2.INTER_AREA)


# ---------------------------------------------------------------------------
# 1. Couleur : histogramme HSV
# ---------------------------------------------------------------------------
def color_histogram(img_bgr: np.ndarray, bins: tuple[int, int, int] = HSV_BINS) -> np.ndarray:
    """Histogramme 3D dans l'espace HSV, aplati et normalisé (somme = 1).

    Chaque case compte la proportion de pixels dont (teinte, saturation, valeur) tombe
    dans un intervalle donné. 8x4x4 = 128 cases : plus de finesse sur la teinte,
    qui porte l'essentiel de l'information de couleur pour l'œil humain.
    """
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    # Attention : dans OpenCV, H va de 0 à 179 (et non 0 à 359) ; S et V de 0 à 255.
    hist = cv2.calcHist([hsv], [0, 1, 2], None, list(bins), [0, 180, 0, 256, 0, 256])
    hist = hist.flatten()
    return hist / hist.sum()                        # normalisation : indépendant du nombre de pixels


# ---------------------------------------------------------------------------
# 2. Couleur : moments
# ---------------------------------------------------------------------------
def channel_moments(values: np.ndarray) -> tuple[float, float, float]:
    """Moyenne, écart-type et asymétrie (racine cubique du 3e moment centré) d'un canal."""
    v = np.asarray(values, dtype=np.float64).ravel()   # float64 : évite les débordements de uint8
    mean = v.mean()
    std = v.std()
    skew = np.cbrt(((v - mean) ** 3).mean())            # cbrt garde le signe (x ** (1/3) donnerait nan)
    return float(mean), float(std), float(skew)


def color_moments(img_bgr: np.ndarray) -> np.ndarray:
    """9 valeurs : (moyenne, écart-type, asymétrie) pour chacun des canaux H, S et V."""
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    feats = []
    for c in range(3):
        feats.extend(channel_moments(hsv[:, :, c]))
    return np.array(feats)


# ---------------------------------------------------------------------------
# 3. Couleur : couleurs dominantes (K-means)
# ---------------------------------------------------------------------------
def dominant_colors(img_bgr: np.ndarray, k: int = N_DOMINANT) -> dict:
    """Trouve les k couleurs qui résument le mieux l'image, et leur proportion.

    Le K-means regroupe les pixels en k groupes de couleurs proches ; le centre de chaque
    groupe est une couleur dominante. On travaille dans l'espace Lab, conçu pour que la
    distance euclidienne corresponde à la différence de couleur perçue par l'œil.

    Renvoie un dictionnaire avec :
        vector : 20 valeurs (L, a, b, proportion) x 5, triées par proportion décroissante
        colors : liste [{"hex": "#RRGGBB", "rgb": [r, g, b], "proportion": p}, ...] pour l'affichage
    """
    small = cv2.resize(img_bgr, (KMEANS_SIZE, KMEANS_SIZE), interpolation=cv2.INTER_AREA)
    lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB)
    pixels = lab.reshape(-1, 3).astype(np.float32)

    with warnings.catch_warnings():
        # Si l'image a moins de k couleurs distinctes (ex. image unie), sklearn prévient
        # qu'il trouve moins de k groupes : ce n'est pas une erreur, on ignore l'avertissement.
        warnings.simplefilter("ignore", ConvergenceWarning)
        km = KMeans(n_clusters=k, n_init=4, random_state=0).fit(pixels)

    counts = np.bincount(km.labels_, minlength=k)
    props = counts / counts.sum()
    order = np.argsort(-props, kind="stable")       # tri décroissant : indispensable pour comparer 2 images
    centers, props = km.cluster_centers_[order], props[order]

    # Conversion des centres Lab -> RGB pour l'affichage (nuancier).
    lab_u8 = np.clip(np.round(centers), 0, 255).astype(np.uint8).reshape(1, k, 3)
    rgb = cv2.cvtColor(lab_u8, cv2.COLOR_LAB2RGB).reshape(k, 3)
    colors = [
        {"hex": "#{:02X}{:02X}{:02X}".format(*c), "rgb": [int(x) for x in c], "proportion": float(p)}
        for c, p in zip(rgb, props, strict=True)
    ]

    vector = np.hstack([centers / 255.0, props[:, None]]).ravel()
    return {"vector": vector, "colors": colors}


# ---------------------------------------------------------------------------
# 4. Texture : matrice de co-occurrence des niveaux de gris (GLCM)
# ---------------------------------------------------------------------------
def glcm_properties(P: np.ndarray) -> dict[str, float]:
    """Calcule les propriétés de Haralick à partir d'une GLCM normalisée.

    P a la forme (niveaux, niveaux, nb_distances, nb_angles), comme renvoyé par
    ``skimage.feature.graycomatrix``. Chaque propriété est moyennée sur toutes les
    distances et tous les angles (insensibilité à l'orientation de la texture).
    """
    feats = {name: float(np.nan_to_num(graycoprops(P, name)).mean()) for name in GLCM_PROPS}
    # L'entropie n'existe pas dans graycoprops : on la calcule pour chaque (distance, angle).
    entropies = []
    for d in range(P.shape[2]):
        for a in range(P.shape[3]):
            p = P[:, :, d, a]
            p = p[p > 0]                            # log2(0) est infini : on ignore les cases vides
            entropies.append(-np.sum(p * np.log2(p)))
    feats["entropy"] = float(np.mean(entropies))
    return feats


def glcm_features(img_bgr: np.ndarray, levels: int = GLCM_LEVELS) -> dict[str, float]:
    """7 propriétés de texture.

    Contraste, dissimilarité, homogénéité, énergie, corrélation, ASM et entropie.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    # Quantification 256 -> 32 niveaux : une GLCM 256x256 serait presque vide et très sensible au bruit.
    q = (gray.astype(np.uint16) * levels // 256).astype(np.uint8)
    P = graycomatrix(q, distances=list(GLCM_DISTANCES), angles=list(GLCM_ANGLES),
                     levels=levels, symmetric=True, normed=True)
    return glcm_properties(P)


# ---------------------------------------------------------------------------
# 5. Texture : motifs binaires locaux (LBP)
# ---------------------------------------------------------------------------
def lbp_image(img_bgr: np.ndarray, P: int = LBP_P, R: int = LBP_R) -> np.ndarray:
    """Image des étiquettes LBP uniformes (valeurs de 0 à P+1), utile pour l'affichage."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    return local_binary_pattern(gray, P, R, method="uniform")


def lbp_histogram(img_bgr: np.ndarray, P: int = LBP_P, R: int = LBP_R) -> np.ndarray:
    """Histogramme normalisé des P+2 motifs LBP uniformes (10 cases pour P = 8).

    Cases 0 à P : motifs uniformes classés par nombre de bits à 1 (zone sombre, bord, coin, zone claire...).
    Case P+1    : tous les motifs non uniformes (bruit, textures complexes).
    """
    lbp = lbp_image(img_bgr, P, R)
    # On ignore une bordure de R pixels : scikit-image considère les pixels hors de l'image comme
    # valant 0, ce qui crée de faux motifs sur les bords (ex. 4 % de motifs erronés sur une image unie).
    lbp = lbp[R:-R, R:-R]
    n_bins = P + 2
    hist, _ = np.histogram(lbp, bins=n_bins, range=(0, n_bins))
    return hist / hist.sum()


# ---------------------------------------------------------------------------
# Assemblage
# ---------------------------------------------------------------------------
def extract_feature_vector(img: np.ndarray) -> np.ndarray:
    """Vecteur final de 174 valeurs (non normalisé) utilisé pour la recherche.

    La normalisation z-score se fait plus tard, sur toute la base (module index),
    car elle a besoin de la moyenne et de l'écart-type de chaque composante sur les 10 000 images.
    """
    img = prepare_image(img)
    glcm = glcm_features(img)
    vec = np.concatenate([
        color_histogram(img),
        color_moments(img),
        dominant_colors(img)["vector"],
        np.array([glcm[name] for name in (*GLCM_PROPS, "entropy")]),
        lbp_histogram(img),
    ]).astype(np.float64)
    assert vec.shape == (FEATURE_DIM,), vec.shape   # garde-fou si on change un paramètre
    return vec


def compute_all(img: np.ndarray) -> dict:
    """Tous les descripteurs sous une forme lisible et sérialisable en JSON (pour l'affichage web)."""
    img = prepare_image(img)
    moments = color_moments(img).round(4).tolist()
    dom = dominant_colors(img)
    return {
        "color_histogram": {
            "bins": list(HSV_BINS),
            "values": color_histogram(img).round(6).tolist(),
        },
        "color_moments": {
            channel: {"mean": moments[3 * i], "std": moments[3 * i + 1], "skewness": moments[3 * i + 2]}
            for i, channel in enumerate(("H", "S", "V"))
        },
        "dominant_colors": dom["colors"],
        "glcm": {k: round(v, 6) for k, v in glcm_features(img).items()},
        "lbp": {
            "P": LBP_P,
            "R": LBP_R,
            "values": lbp_histogram(img).round(6).tolist(),
        },
    }
