"""Tests des images : upload, liste, fichiers, téléchargement, suppression, transformations,
descripteurs, recherche, import de GHIM-10K."""

import io
import zipfile

import pytest
from gallery_testutils import png, upload
from PIL import Image as PILImage

from gallery.cli import import_dataset
from gallery.extensions import db
from gallery.models import Category, Image
from gallery.transforms import TransformError, apply_operations


def ids_of(resp):
    return [i["id"] for i in resp.get_json()["images"]]


# --------------------------------------------------------------------------- upload
def test_upload_multiple_et_indexation(client, alice, cbir, app):
    r = upload(client, alice, (png(), "rouge.png"), (png((0, 0, 255), fmt="JPEG"), "bleu.jpg"))
    assert r.status_code == 201
    body = r.get_json()
    assert [i["filename"] for i in body["images"]] == ["rouge.png", "bleu.jpg"]
    assert all(i["indexed"] and i["mine"] for i in body["images"])
    assert len(cbir.indexed) == 2                          # les deux sont dans l'index CBIR
    img = db.session.get(Image, body["images"][1]["id"])
    assert img.format == "JPEG" and img.width == 64 and img.height == 48
    assert (app.config["STORAGE_DIR"] / img.path).exists()


def test_upload_succes_partiel(client, alice):
    r = upload(client, alice, (png(), "ok.png"), (b"pas une image", "faux.jpg"))
    body = r.get_json()
    assert r.status_code == 201 and len(body["images"]) == 1
    assert body["errors"][0]["filename"] == "faux.jpg"


def test_upload_nom_de_fichier_dangereux(client, alice, app):
    r = upload(client, alice, (png(), "../../windows/evil.png"))
    img = r.get_json()["images"][0]
    assert img["filename"] == "evil.png"                    # jamais un chemin
    path = db.session.get(Image, img["id"]).path
    assert path.startswith("users/") and ".." not in path


def test_upload_cbir_arretee(client, alice, cbir):
    cbir.available = False
    r = upload(client, alice, (png(), "a.png"))
    body = r.get_json()
    assert r.status_code == 201 and body["images"][0]["indexed"] is False
    assert "indisponible" in body["warnings"][0]
    cbir.available = True                                   # on rallume : /reindex rattrape
    r = client.post(f"/api/images/{body['images'][0]['id']}/reindex", headers=alice)
    assert r.get_json()["indexed"] is True


def test_ranger_son_image_dans_une_categorie_publique(client, alice, bob):
    pub = Category(name="yacht", owner_id=None)
    db.session.add(pub)
    db.session.commit()
    iid = ids_of(upload(client, alice, (png(), "bateau.png"), category_id=pub.id))[0]
    assert client.get(f"/api/images/{iid}", headers=alice).get_json()["image"]["category_id"] == pub.id
    # la catégorie d'un autre utilisateur reste interdite
    theirs = client.post("/api/categories", json={"name": "Privé"}, headers=bob).get_json()["category"]["id"]
    r = client.patch(f"/api/images/{iid}", json={"category_id": theirs}, headers=alice)
    assert r.status_code == 404


# ---------------------------------------------------------------------------- liste
def test_liste_filtres_et_droits(client, alice, bob):
    cat = client.post("/api/categories", json={"name": "Fleurs"}, headers=alice).get_json()["category"]["id"]
    sub = client.post("/api/categories", json={"name": "Roses", "parent_id": cat},
                      headers=alice).get_json()["category"]["id"]
    upload(client, alice, (png(), "rose.png"), category_id=sub)
    upload(client, alice, (png(), "tulipe.png"), category_id=cat)
    upload(client, alice, (png(), "chat.png"))
    upload(client, bob, (png(), "secret.png"))

    def names(**params):
        r = client.get("/api/images", query_string=params, headers=alice)
        return sorted(i["filename"] for i in r.get_json()["items"])

    assert names() == ["chat.png", "rose.png", "tulipe.png"]          # pas l'image de Bob
    assert names(category_id=cat) == ["rose.png", "tulipe.png"]       # avec la sous-catégorie
    assert names(category_id=cat, recursive=0) == ["tulipe.png"]
    assert names(uncategorized=1) == ["chat.png"]
    assert names(q="TUL") == ["tulipe.png"]
    page = client.get("/api/images", query_string={"per_page": 2}, headers=alice).get_json()
    assert page["total"] == 3 and page["pages"] == 2 and len(page["items"]) == 2


def test_image_d_un_autre_invisible(client, alice, bob):
    iid = ids_of(upload(client, bob, (png(), "secret.png")))[0]
    for url in (f"/api/images/{iid}", f"/api/images/{iid}/file", f"/api/images/{iid}/thumb"):
        assert client.get(url, headers=alice).status_code == 404
    assert client.delete(f"/api/images/{iid}", headers=alice).status_code == 404


# ----------------------------------------------------------------- fichiers, ZIP
def test_fichier_miniature_et_zip(client, alice):
    ids = ids_of(upload(client, alice, (png(size=(800, 600)), "grande.png"), (png(), "petite.png")))
    r = client.get(f"/api/images/{ids[0]}/file?download=1", headers=alice)
    assert r.status_code == 200 and "attachment" in r.headers["Content-Disposition"]
    thumb = PILImage.open(io.BytesIO(client.get(f"/api/images/{ids[0]}/thumb", headers=alice).data))
    assert max(thumb.size) == 320 and thumb.size == (320, 240)     # proportions gardées
    r = client.post("/api/images/download", json={"ids": ids}, headers=alice)
    names = zipfile.ZipFile(io.BytesIO(r.data)).namelist()
    assert names == [f"{ids[0]}_grande.png", f"{ids[1]}_petite.png"]


# ---------------------------------------------------------------------- suppression
def test_suppression_simple_et_multiple(client, alice, cbir, app):
    ids = ids_of(upload(client, alice, (png(), "a.png"), (png(), "b.png"), (png(), "c.png")))
    path = app.config["STORAGE_DIR"] / db.session.get(Image, ids[0]).path
    assert client.delete(f"/api/images/{ids[0]}", headers=alice).status_code == 200
    assert not path.exists() and len(cbir.indexed) == 2            # fichier + index nettoyés
    r = client.post("/api/images/bulk-delete", json={"ids": ids[1:]}, headers=alice)
    assert r.get_json()["deleted"] == ids[1:] and cbir.indexed == []


def test_suppression_multiple_tout_ou_rien(client, alice, bob):
    mine = ids_of(upload(client, alice, (png(), "a.png")))
    theirs = ids_of(upload(client, bob, (png(), "b.png")))
    r = client.post("/api/images/bulk-delete", json={"ids": mine + theirs}, headers=alice)
    assert r.status_code == 404
    assert client.get(f"/api/images/{mine[0]}", headers=alice).status_code == 200   # rien n'a été supprimé


# -------------------------------------------------------------------- transformations
def test_operations_pures():
    img = PILImage.new("RGB", (100, 50), "red")
    out = apply_operations(img, [{"op": "crop", "x": 10, "y": 5, "width": 40, "height": 20},
                                 {"op": "resize", "width": 80},
                                 {"op": "rotate", "angle": 90}])
    assert out.size == (40, 80)                     # crop 40x20 -> resize 80x40 -> rotation 90° -> 40x80
    assert img.size == (100, 50)                    # originale intacte
    gray = apply_operations(img, [{"op": "grayscale"}])
    r, g, b = gray.getpixel((0, 0))
    assert r == g == b


@pytest.mark.parametrize("ops", [
    [],
    [{"op": "inconnue"}],
    [{"op": "crop", "x": 90, "y": 0, "width": 50, "height": 10}],   # sort de l'image
    [{"op": "resize"}],
    [{"op": "brightness", "factor": "abc"}],
    [{"op": "flip", "direction": "diagonale"}],
])
def test_operations_invalides(ops):
    with pytest.raises(TransformError):
        apply_operations(PILImage.new("RGB", (100, 50)), ops)


def test_transformation_cree_une_nouvelle_image(client, alice, cbir):
    src = ids_of(upload(client, alice, (png(size=(200, 100)), "paysage.png")))[0]
    ops = [{"op": "crop", "x": 0, "y": 0, "width": 100, "height": 100}, {"op": "flip"}]
    r = client.post(f"/api/images/{src}/transform", json={"operations": ops}, headers=alice)
    assert r.status_code == 201
    new = r.get_json()["image"]
    assert new["id"] != src and new["parent_id"] == src and new["source"] == "transform"
    assert (new["width"], new["height"]) == (100, 100) and new["transform"] == ops
    assert new["filename"] == "paysage_transform.png" and new["indexed"]
    assert len(cbir.indexed) == 2
    bad = client.post(f"/api/images/{src}/transform", json={"operations": [{"op": "zoom"}]}, headers=alice)
    assert bad.status_code == 400


# ---------------------------------------------------------------------- descripteurs
def test_descripteurs_mis_en_cache(client, alice):
    iid = ids_of(upload(client, alice, (png(), "a.png")))[0]
    first = client.get(f"/api/images/{iid}/descriptors", headers=alice).get_json()
    second = client.get(f"/api/images/{iid}/descriptors", headers=alice).get_json()
    assert first["cached"] is False and second["cached"] is True
    assert second["descriptors"]["glcm"]["contrast"] == 1.0


def test_descripteurs_cbir_arretee(client, alice, cbir):
    iid = ids_of(upload(client, alice, (png(), "a.png")))[0]
    cbir.available = False
    r = client.get(f"/api/images/{iid}/descriptors", headers=alice)
    assert r.status_code == 503 and "CBIR" in r.get_json()["error"]


# --------------------------------------------------------------------------- recherche
def test_recherche_filtre_les_images_des_autres(client, alice, bob):
    a = ids_of(upload(client, alice, (png(), "a1.png"), (png(), "a2.png")))
    ids_of(upload(client, bob, (png(), "b1.png")))
    upload(client, alice, (png(), "a3.png"))
    r = client.post("/api/search", json={"image_id": a[0], "k": 10}, headers=alice)
    res = r.get_json()["results"]
    assert [x["image"]["filename"] for x in res] == ["a2.png", "a3.png"]   # b1 (Bob) filtrée
    assert [x["rank"] for x in res] == [1, 2]


def test_recherche_par_fichier_envoye(client, alice):
    upload(client, alice, (png(), "a1.png"))
    data = {"image": (io.BytesIO(png()), "q.png"), "k": "5"}
    r = client.post("/api/search", data=data, headers=alice, content_type="multipart/form-data")
    assert r.status_code == 200 and r.get_json()["query"]["type"] == "upload"
    assert len(r.get_json()["results"]) == 1


def test_recherche_k_invalide(client, alice):
    iid = ids_of(upload(client, alice, (png(), "a.png")))[0]
    assert client.post("/api/search", json={"image_id": iid, "k": 0}, headers=alice).status_code == 400


def test_retour_de_pertinence_relaye_et_filtre(client, alice, bob, cbir):
    a = ids_of(upload(client, alice, *[(png(), f"a{i}.png") for i in range(4)]))
    b = ids_of(upload(client, bob, (png(), "b.png")))
    body = {"image_id": a[0], "relevant_ids": [a[2]], "non_relevant_ids": [a[1]], "k": 10}
    r = client.post("/api/search/feedback", json=body, headers=alice)
    assert r.status_code == 200
    names = [x["image"]["filename"] for x in r.get_json()["results"]]
    assert names == ["a2.png", "a3.png"]                       # pertinente en tête ; a0, a1 et b exclues
    # le backend a bien traduit les ids de la galerie en ids CBIR
    assert cbir.last_feedback["relevant"] == [db.session.get(Image, a[2]).cbir_id]
    # on ne peut pas utiliser l'image d'un autre comme exemple
    body["relevant_ids"] = b
    assert client.post("/api/search/feedback", json=body, headers=alice).status_code == 404


def test_retour_de_pertinence_fichier_sans_pertinente(client, alice):
    data = {"image": (io.BytesIO(png()), "q.png"), "relevant_ids": "[]"}
    r = client.post("/api/search/feedback", data=data, headers=alice, content_type="multipart/form-data")
    assert r.status_code == 400 and "pertinente" in r.get_json()["error"]


# --------------------------------------------------------------------- import GHIM-10K
def test_import_dataset_idempotent(app, client, alice):
    root = app.config["DATASET_DIR"]
    for cat in ("flowers", "sea shores"):
        (root / cat).mkdir(parents=True)
        for i in range(3):
            PILImage.new("RGB", (40, 30)).save(root / cat / f"{i}.jpg")
    assert import_dataset(root) == (6, 0)
    assert import_dataset(root) == (0, 6)                  # relancer n'ajoute rien
    cats = {c.name: c for c in db.session.query(Category)}
    assert cats["sea shores"].parent_id == cats["GHIM-10K"].id and cats["GHIM-10K"].owner_id is None
    img = db.session.query(Image).filter_by(cbir_id="sea shores/0.jpg").one()
    assert img.is_public and img.indexed
    # visible par tout le monde, en lecture seule
    assert client.get(f"/api/images/{img.id}/thumb", headers=alice).status_code == 200
    assert client.delete(f"/api/images/{img.id}", headers=alice).status_code == 403
    # mais on peut créer sa propre version transformée
    ops = {"operations": [{"op": "grayscale"}]}
    r = client.post(f"/api/images/{img.id}/transform", json=ops, headers=alice)
    assert r.status_code == 201 and r.get_json()["image"]["mine"]
