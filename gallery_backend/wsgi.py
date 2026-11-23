"""Point d'entrée du backend galerie.

    python gallery_backend/wsgi.py                               # serveur de développement, port 5000
    flask --app gallery_backend/wsgi.py db upgrade               # applique les migrations
    flask --app gallery_backend/wsgi.py import-dataset           # importe GHIM-10K en base
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))      # pour importer le paquet "gallery"

from gallery import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("GALLERY_PORT", "5000")), debug=False, threaded=True)
