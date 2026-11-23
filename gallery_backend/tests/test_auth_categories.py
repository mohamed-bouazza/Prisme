"""Tests de l'authentification et des catégories hiérarchiques."""

from gallery_testutils import register

from gallery.extensions import db
from gallery.models import Category, User


# ------------------------------------------------------------------- authentification
def test_inscription_puis_connexion(client):
    r = client.post("/api/auth/register", json={"email": "A@Example.com", "password": "motdepasse1",
                                                "username": "Alice"})
    assert r.status_code == 201
    body = r.get_json()
    assert body["user"]["email"] == "a@example.com"          # normalisé en minuscules
    assert "access_token" in body and "password_hash" not in body["user"]
    assert "access_token_cookie" in r.headers.get("Set-Cookie", "")

    r = client.post("/api/auth/login", json={"email": "a@example.com", "password": "motdepasse1"})
    assert r.status_code == 200
    token = r.get_json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.get_json()["user"]["username"] == "Alice"


def test_mot_de_passe_hache_jamais_en_clair(client, app):
    register(client)
    user = db.session.query(User).one()
    assert user.password_hash.startswith("$2b$") and "motdepasse1" not in user.password_hash


def test_connexion_echoue_meme_message(client):
    register(client)
    wrong_pw = client.post("/api/auth/login", json={"email": "alice@example.com", "password": "mauvais!!"})
    no_user = client.post("/api/auth/login", json={"email": "inconnu@example.com", "password": "mauvais!!"})
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.get_json()["error"] == no_user.get_json()["error"]   # ne révèle pas si l'email existe


def test_inscription_validations(client):
    register(client)
    cases = [
        ({"email": "pas-un-email", "password": "motdepasse1", "username": "X1"}, 400),
        ({"email": "c@example.com", "password": "court", "username": "X1"}, 400),
        ({"email": "c@example.com", "password": "motdepasse1", "username": "X"}, 400),
        ({"email": "ALICE@example.com", "password": "motdepasse1", "username": "Al"}, 409),   # doublon
    ]
    for payload, code in cases:
        assert client.post("/api/auth/register", json=payload).status_code == code, payload


def test_routes_protegees_sans_jeton(client):
    for method, url in [("get", "/api/images"), ("get", "/api/categories"), ("post", "/api/search")]:
        r = getattr(client, method)(url)
        assert r.status_code == 401 and r.get_json()["error"] == "Authentification requise"


def test_jeton_invalide(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer abc.def.ghi"})
    assert r.status_code == 401 and r.get_json()["error"] == "Jeton invalide"


# -------------------------------------------------------------------------- catégories
def make(client, headers, name, parent_id=None):
    r = client.post("/api/categories", json={"name": name, "parent_id": parent_id}, headers=headers)
    assert r.status_code == 201, r.get_json()
    return r.get_json()["category"]["id"]


def test_arbre_et_fil_d_ariane(client, alice):
    voyages = make(client, alice, "Voyages")
    europe = make(client, alice, "Europe", voyages)
    paris = make(client, alice, "Paris", europe)
    cat = client.get(f"/api/categories/{paris}", headers=alice).get_json()["category"]
    assert [p["name"] for p in cat["path"]] == ["Voyages", "Europe", "Paris"]
    cats = {c["name"]: c for c in client.get("/api/categories", headers=alice).get_json()["categories"]}
    assert cats["Europe"]["parent_id"] == voyages and cats["Voyages"]["parent_id"] is None


def test_nom_en_double_au_meme_niveau(client, alice):
    v = make(client, alice, "Voyages")
    make(client, alice, "Europe", v)
    r = client.post("/api/categories", json={"name": "europe", "parent_id": v}, headers=alice)
    assert r.status_code == 409
    make(client, alice, "Europe")                           # autre niveau : autorisé


def test_deplacement_interdit_dans_sa_descendance(client, alice):
    a = make(client, alice, "A")
    b = make(client, alice, "B", a)
    c = make(client, alice, "C", b)
    r = client.patch(f"/api/categories/{a}", json={"parent_id": c}, headers=alice)
    assert r.status_code == 400 and "descendance" in r.get_json()["error"]
    r = client.patch(f"/api/categories/{a}", json={"parent_id": a}, headers=alice)
    assert r.status_code == 400
    r = client.patch(f"/api/categories/{c}", json={"parent_id": None, "name": "C2"}, headers=alice)
    assert r.status_code == 200 and r.get_json()["category"]["parent_id"] is None


def test_suppression_du_sous_arbre(client, alice):
    a = make(client, alice, "A")
    b = make(client, alice, "B", a)
    make(client, alice, "C", b)
    keep = make(client, alice, "Autre")
    r = client.delete(f"/api/categories/{a}", headers=alice)
    assert r.status_code == 200 and len(r.get_json()["deleted"]) == 3
    names = [c["name"] for c in client.get("/api/categories", headers=alice).get_json()["categories"]]
    assert names == ["Autre"] and keep


def test_categories_privees_et_publiques(client, alice, bob, app):
    pub = Category(name="GHIM-10K", owner_id=None)
    db.session.add(pub)
    db.session.commit()
    a = make(client, alice, "Privé d'Alice")
    names_bob = [c["name"] for c in client.get("/api/categories", headers=bob).get_json()["categories"]]
    assert names_bob == ["GHIM-10K"]                        # Bob voit la publique, pas celle d'Alice
    assert client.get(f"/api/categories/{a}", headers=bob).status_code == 404
    assert client.delete(f"/api/categories/{pub.id}", headers=alice).status_code == 403   # lecture seule
