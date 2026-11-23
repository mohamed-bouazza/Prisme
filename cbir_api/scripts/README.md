# Scripts hors ligne

À lancer depuis la racine du projet, avec le venv activé.

| Script | Rôle | Sortie (non versionnée, régénérable) |
|---|---|---|
| `build_index.py` | Calcule les 174 descripteurs de chaque image de `data/GHIM-10K/` (en parallèle) et écrit l'index. La catégorie de chaque image est le nom de son dossier. | `cbir_api/index/` |
| `evaluate.py` | Précision@K, mAP et courbe précision/rappel de la recherche simple ; compare les combinaisons de descripteurs et (option `--compare-hsv`) les quantifications de teinte. | `reports/etape3/` |

```powershell
python cbir_api/scripts/build_index.py
python cbir_api/scripts/evaluate.py --compare-hsv
```

Le script `make_labels.py` prévu au départ n'est plus nécessaire : les catégories sont lues
directement depuis les noms de dossiers (`cbir/dataset.py`) et enregistrées dans l'index (`labels.npy`).
