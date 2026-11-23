"""Configuration lue dans le fichier .env (à la racine du projet)."""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]          # racine du projet
load_dotenv(ROOT / ".env")


def _path(env: str, default: str) -> Path:
    """Chemin du .env, relatif à la racine du projet (et non au dossier courant)."""
    return (ROOT / os.getenv(env, default)).resolve()


def _local(url: str) -> str:
    """Sous Windows, « localhost » est d'abord essayé en IPv6 (::1) et peut rester bloqué
    (même problème qu'avec Adminer à l'étape 1) : on force l'adresse IPv4 127.0.0.1."""
    return url.replace("@localhost:", "@127.0.0.1:").replace("//localhost:", "//127.0.0.1:")


class Config:
    SQLALCHEMY_DATABASE_URI = _local(os.getenv(
        "DATABASE_URL", "postgresql+psycopg://cbir:change-me@127.0.0.1:5432/cbir_gallery"))
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}    # reconnexion si PostgreSQL a redémarré

    # --- Authentification JWT ---
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)
    # Le jeton est accepté dans l'en-tête "Authorization: Bearer ..." (outils, tests) OU dans un cookie
    # httpOnly (navigateur : une balise <img> ne peut pas envoyer d'en-tête Authorization).
    JWT_TOKEN_LOCATION = ["headers", "cookies"]
    JWT_COOKIE_SECURE = False                   # True en HTTPS (production)
    JWT_COOKIE_SAMESITE = "Lax"
    JWT_COOKIE_CSRF_PROTECT = True              # requêtes modifiantes par cookie : en-tête X-CSRF-TOKEN exigé

    # --- Fichiers ---
    STORAGE_DIR = _path("STORAGE_DIR", "./storage")         # images des utilisateurs + miniatures
    DATASET_DIR = _path("DATASET_DIR", "./data/GHIM-10K")   # base GHIM-10K (lue, jamais copiée)
    MAX_CONTENT_LENGTH = 200 * 1024 * 1024                  # 200 Mo par requête (upload multiple)
    MAX_FILE_MB = 20
    THUMB_SIZE = 320

    # --- API CBIR ---
    CBIR_API_URL = _local(os.getenv("CBIR_API_URL", "http://127.0.0.1:5001"))
    CBIR_TIMEOUT = 30


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"                   # base en mémoire, recréée à chaque test
    SQLALCHEMY_ENGINE_OPTIONS = {}
    JWT_SECRET_KEY = "test-secret-key-at-least-32-bytes-long!"
    JWT_COOKIE_CSRF_PROTECT = False
