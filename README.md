# Galerie CBIR : recherche d'images par le contenu avec retour de pertinence

Mini-projet, **groupe 14**. Application web de gestion d'une galerie de photos avec
recherche d'images similaires (descripteurs couleur et texture) et retour de pertinence par
**Feature Relevance Estimation (FRE)**.

## Auteurs

Master MST IASD (2026-2027), FST Tanger, module *Multimedia Mining and Indexing*,
encadré par le Pr. M'hamed AIT KBIR.

- Mohamed BOUAZZA
- Mohamed Ayman EL KAJDOUHI
- Oussama CHICHAOUI

## Architecture

| Dossier | Rôle | Technologies |
|---|---|---|
| `frontend/` | Interface web | React, Vite, TypeScript, Tailwind CSS |
| `gallery_backend/` | Authentification, images, catégories, transformations | Flask, SQLAlchemy, JWT, PostgreSQL |
| `cbir_api/` | Descripteurs, recherche simple, recherche avec FRE | Flask-RESTful, OpenCV, scikit-image, NumPy |
| `infra/` | Scripts d'initialisation de la base | PostgreSQL 16 + pgvector (Docker) |
| `notebooks/` | Exploration et analyses pour le rapport | Jupyter |

## Prérequis

- Python 3.12
- Node.js 20 LTS ou plus récent
- Docker Desktop
- La base d'images [GHIM-10K](https://www.kaggle.com/datasets/mcpython/ghim-10k), décompressée dans `data/GHIM-10K/`

## Installation

```powershell
# 1. Configuration : copier le modèle puis changer les mots de passe
Copy-Item .env.example .env

# 2. Base de données (PostgreSQL + Adminer)
docker compose up -d

# 3. Environnement Python commun aux deux backends
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r cbir_api\requirements.txt -r gallery_backend\requirements.txt

# 4. Index CBIR des 10 000 images (~1 min)
python cbir_api/scripts/build_index.py

# 5. Tables PostgreSQL (migrations) + import de GHIM-10K dans la base
flask --app gallery_backend/wsgi.py db upgrade
flask --app gallery_backend/wsgi.py import-dataset
```

Frontend (Node.js 20 ou plus) :

```powershell
cd frontend
npm install
```

## Lancement

Trois terminaux, dans cet ordre :

```powershell
python cbir_api/app.py            # API CBIR        -> http://127.0.0.1:5001/api/health
python gallery_backend/wsgi.py    # backend galerie -> http://127.0.0.1:5000/api/health
cd frontend; npm run dev          # application web -> http://localhost:5173
```

Tests : `python -m pytest` (106 tests) et `cd frontend; npm run build` (vérification TypeScript + compilation).

Interface d'administration de la base : http://localhost:8080 (port `ADMINER_PORT` du `.env` ;
le changer, par exemple en 8081, si une autre application utilise déjà 8080)
(système : PostgreSQL, serveur : `db`, identifiants : ceux du fichier `.env`).

## Contenu non fourni (régénérable)

Conformément à l'énoncé, ces dossiers ne sont pas rendus :

| Dossier | Comment le recréer |
|---|---|
| `data/` | Télécharger GHIM-10K depuis Kaggle |
| `cbir_api/index/` | `python cbir_api/scripts/build_index.py` |
| `storage/` | Créé automatiquement par l'application |
| `.venv/`, `node_modules/` | `pip install ...` / `npm install` |
