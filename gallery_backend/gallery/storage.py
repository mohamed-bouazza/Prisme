"""Fichiers sur disque : enregistrer une image, retrouver son chemin, créer sa miniature.

Organisation :

    storage/
        users/<user_id>/<uuid>.<ext>      images envoyées ou créées par transformation
        thumbs/<image_id>.jpg             miniatures (créées à la première demande, puis réutilisées)

Les images de GHIM-10K ne sont **pas copiées** : on les lit directement dans data/GHIM-10K/.
"""

from __future__ import annotations

import io
import uuid
from pathlib import Path

from flask import current_app
from PIL import Image as PILImage
from PIL import ImageOps, UnidentifiedImageError

from gallery.models import Image

ALLOWED_FORMATS = {                                 # format détecté par Pillow -> extension enregistrée
    "JPEG": ".jpg", "PNG": ".png", "BMP": ".bmp", "WEBP": ".webp", "TIFF": ".tif", "GIF": ".gif",
}
MAX_PIXELS = 50_000_000                             # protège contre les « bombes de décompression »


class InvalidImage(ValueError):
    pass


def open_image_bytes(data: bytes) -> PILImage.Image:
    """Ouvre et **vérifie** des octets d'image. Le format est lu dans le contenu, pas dans l'extension."""
    try:
        img = PILImage.open(io.BytesIO(data))
        img.verify()                                # détecte un fichier tronqué ou corrompu
        img = PILImage.open(io.BytesIO(data))       # verify() rend l'objet inutilisable : on rouvre
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise InvalidImage("fichier illisible comme image") from exc
    if img.format not in ALLOWED_FORMATS:
        raise InvalidImage(f"format non supporté : {img.format}")
    if img.width * img.height > MAX_PIXELS:
        raise InvalidImage("image trop grande")
    return img


def absolute_path(image: Image) -> Path:
    cfg = current_app.config
    base = cfg["DATASET_DIR"] if image.location == "dataset" else cfg["STORAGE_DIR"]
    path = (base / image.path).resolve()
    if not path.is_relative_to(base):               # défense : jamais de lecture hors du dossier prévu
        raise InvalidImage("chemin invalide")
    return path


def save_user_file(user_id: int, data: bytes, fmt: str) -> str:
    """Écrit les octets sous un nom aléatoire (uuid) et renvoie le chemin relatif à STORAGE_DIR.

    Nom aléatoire : deux utilisateurs peuvent envoyer « photo.jpg » sans s'écraser, et le nom d'origine
    (choisi par l'utilisateur, donc non fiable) n'est jamais utilisé comme chemin.
    """
    rel = f"users/{user_id}/{uuid.uuid4().hex}{ALLOWED_FORMATS[fmt]}"
    dest = current_app.config["STORAGE_DIR"] / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return rel


def encode(img: PILImage.Image, fmt: str) -> bytes:
    buf = io.BytesIO()
    if fmt == "JPEG":
        img.convert("RGB").save(buf, "JPEG", quality=92)
    else:
        img.save(buf, fmt)
    return buf.getvalue()


def thumbnail_path(image: Image) -> Path:
    """Chemin de la miniature, créée si elle n'existe pas encore."""
    thumb = current_app.config["STORAGE_DIR"] / "thumbs" / f"{image.id}.jpg"
    if not thumb.exists():
        thumb.parent.mkdir(parents=True, exist_ok=True)
        size = current_app.config["THUMB_SIZE"]
        with PILImage.open(absolute_path(image)) as img:
            img = ImageOps.exif_transpose(img)      # respecte l'orientation des photos de téléphone
            img.thumbnail((size, size))             # réduit en gardant les proportions
            img.convert("RGB").save(thumb, "JPEG", quality=85)
    return thumb


def delete_files(image: Image) -> None:
    """Supprime le fichier (sauf image de la base) et sa miniature."""
    if image.location == "storage":
        absolute_path(image).unlink(missing_ok=True)
    (current_app.config["STORAGE_DIR"] / "thumbs" / f"{image.id}.jpg").unlink(missing_ok=True)
