"""Transformations d'images (Tâche 1 : « créer de nouvelles images par transformation »).

Une transformation est une **liste d'opérations** appliquées dans l'ordre, par exemple :

    [{"op": "crop", "x": 10, "y": 20, "width": 200, "height": 150},
     {"op": "resize", "width": 100},
     {"op": "rotate", "angle": 90}]

Cette liste est enregistrée avec la nouvelle image (colonne JSONB ``transform``) : on sait toujours
comment une image a été obtenue, et on peut la recréer.
"""

from __future__ import annotations

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


class TransformError(ValueError):
    """Opération invalide (paramètre manquant, hors limites...) : renvoyée en 400 au client."""


MAX_SIDE = 8000
MAX_OPS = 20


def _int(op: dict, key: str, lo: int, hi: int, default: int | None = None) -> int:
    value = op.get(key, default)
    if value is None:
        raise TransformError(f"{op['op']} : paramètre '{key}' manquant")
    try:
        value = int(value)
    except (TypeError, ValueError) as exc:
        raise TransformError(f"{op['op']} : '{key}' doit être un entier") from exc
    if not lo <= value <= hi:
        raise TransformError(f"{op['op']} : '{key}' doit être entre {lo} et {hi}")
    return value


def _float(op: dict, key: str, lo: float, hi: float) -> float:
    try:
        value = float(op[key])
    except KeyError as exc:
        raise TransformError(f"{op['op']} : paramètre '{key}' manquant") from exc
    except (TypeError, ValueError) as exc:
        raise TransformError(f"{op['op']} : '{key}' doit être un nombre") from exc
    if not lo <= value <= hi:
        raise TransformError(f"{op['op']} : '{key}' doit être entre {lo} et {hi}")
    return value


def crop(img: Image.Image, op: dict) -> Image.Image:
    """Découpe le rectangle (x, y, largeur, hauteur), en pixels depuis le coin haut-gauche."""
    w, h = img.size
    x = _int(op, "x", 0, w - 1)
    y = _int(op, "y", 0, h - 1)
    cw = _int(op, "width", 1, w - x)                    # le rectangle doit rester dans l'image
    ch = _int(op, "height", 1, h - y)
    return img.crop((x, y, x + cw, y + ch))             # Pillow attend (gauche, haut, droite, bas)


def resize(img: Image.Image, op: dict) -> Image.Image:
    """Redimensionne. Avec une seule dimension, l'autre est calculée pour garder les proportions."""
    w, h = img.size
    if op.get("width") is None and op.get("height") is None:
        raise TransformError("resize : donner 'width' et/ou 'height'")
    nw = _int(op, "width", 1, MAX_SIDE) if op.get("width") is not None else None
    nh = _int(op, "height", 1, MAX_SIDE) if op.get("height") is not None else None
    if nw is None:
        nw = max(1, round(w * nh / h))
    if nh is None:
        nh = max(1, round(h * nw / w))
    return img.resize((nw, nh), Image.Resampling.LANCZOS)   # LANCZOS : le filtre le plus net


def rotate(img: Image.Image, op: dict) -> Image.Image:
    """Rotation en degrés, sens inverse des aiguilles d'une montre ; l'image est agrandie pour tout garder."""
    angle = _float(op, "angle", -360, 360)
    return img.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC, fillcolor=(255, 255, 255))


def flip(img: Image.Image, op: dict) -> Image.Image:
    direction = op.get("direction", "horizontal")
    if direction == "horizontal":
        return ImageOps.mirror(img)                     # miroir gauche-droite
    if direction == "vertical":
        return ImageOps.flip(img)                       # haut-bas
    raise TransformError("flip : 'direction' doit valoir 'horizontal' ou 'vertical'")


def grayscale(img: Image.Image, op: dict) -> Image.Image:
    return ImageOps.grayscale(img).convert("RGB")       # on reste en 3 canaux pour les descripteurs


def brightness(img: Image.Image, op: dict) -> Image.Image:
    """factor : 1 = inchangé, 0,5 = deux fois plus sombre, 1,5 = plus clair."""
    return ImageEnhance.Brightness(img).enhance(_float(op, "factor", 0, 5))


def contrast(img: Image.Image, op: dict) -> Image.Image:
    return ImageEnhance.Contrast(img).enhance(_float(op, "factor", 0, 5))


def blur(img: Image.Image, op: dict) -> Image.Image:
    return img.filter(ImageFilter.GaussianBlur(_float(op, "radius", 0, 50)))


OPERATIONS = {
    "crop": crop, "resize": resize, "rotate": rotate, "flip": flip,
    "grayscale": grayscale, "brightness": brightness, "contrast": contrast, "blur": blur,
}


def apply_operations(img: Image.Image, operations: list) -> Image.Image:
    """Applique les opérations dans l'ordre et renvoie une **nouvelle** image (l'originale est intacte)."""
    if not isinstance(operations, list) or not operations:
        raise TransformError("'operations' doit être une liste non vide")
    if len(operations) > MAX_OPS:
        raise TransformError(f"au plus {MAX_OPS} opérations")
    out = img.convert("RGB")
    for op in operations:
        if not isinstance(op, dict) or op.get("op") not in OPERATIONS:
            raise TransformError(f"opération inconnue : {op!r} (valides : {sorted(OPERATIONS)})")
        out = OPERATIONS[op["op"]](out, op)
    return out
