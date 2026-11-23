"""Authentification : inscription, connexion, déconnexion, utilisateur courant.

Mot de passe : haché avec **bcrypt** (lent exprès, avec un sel aléatoire) ; seul le hachage est stocké.
Session : un **JWT** (jeton signé) renvoyé dans le corps de la réponse ET posé dans un cookie httpOnly.
"""

from __future__ import annotations

import re

import bcrypt
from flask import Blueprint, jsonify
from flask_jwt_extended import create_access_token, jwt_required, set_access_cookies, unset_jwt_cookies
from sqlalchemy import func, select
from werkzeug.exceptions import BadRequest, Conflict, Unauthorized

from gallery.api.common import current_user_id, json_body
from gallery.extensions import db
from gallery.models import User

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 8
# Hachage factice : si l'email n'existe pas, on vérifie quand même un mot de passe, pour que la réponse
# prenne le même temps. Sinon, la durée trahirait quels emails sont inscrits.
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password", bcrypt.gensalt())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("ascii"))


def _session_response(user: User, status: int = 200):
    token = create_access_token(identity=str(user.id))     # "sub" du JWT : l'id en texte
    resp = jsonify(user=user.to_dict(), access_token=token)
    set_access_cookies(resp, token)                         # cookie httpOnly + cookie CSRF lisible
    return resp, status


@bp.post("/register")
def register():
    data = json_body()
    email = str(data.get("email", "")).strip().lower()
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    if not EMAIL_RE.match(email):
        raise BadRequest("Adresse email invalide")
    if not 2 <= len(username) <= 80:
        raise BadRequest("Nom d'utilisateur : 2 à 80 caractères")
    if len(password) < MIN_PASSWORD:
        raise BadRequest(f"Mot de passe : au moins {MIN_PASSWORD} caractères")
    if len(password.encode("utf-8")) > 72:
        raise BadRequest("Mot de passe : 72 octets au maximum (limite de bcrypt)")
    if db.session.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise Conflict("Un compte existe déjà avec cet email")
    user = User(email=email, username=username, password_hash=hash_password(password))
    db.session.add(user)
    db.session.commit()
    return _session_response(user, 201)


@bp.post("/login")
def login():
    data = json_body()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    user = db.session.scalar(select(User).where(func.lower(User.email) == email))
    ok = check_password(password, user.password_hash if user else _DUMMY_HASH.decode("ascii"))
    if not (user and ok):
        raise Unauthorized("Email ou mot de passe incorrect")   # même message dans les deux cas
    return _session_response(user)


@bp.post("/logout")
def logout():
    resp = jsonify(ok=True)
    unset_jwt_cookies(resp)
    return resp


@bp.get("/me")
@jwt_required()
def me():
    user = db.session.get(User, current_user_id())
    if user is None:                                        # compte supprimé depuis l'émission du jeton
        raise Unauthorized("Utilisateur inconnu")
    return {"user": user.to_dict()}
