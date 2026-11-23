"""Modèle de données (tables PostgreSQL) décrit avec SQLAlchemy 2.

    users ──< images >── categories ──┐
                │  ▲                  │ parent_id (arbre de catégories)
                └──┘ parent_id        └─────────────────────────────────┘
              (image d'origine d'une transformation)

- Une ligne ``owner_id = NULL`` est **publique** : ce sont les 10 000 images de GHIM-10K et leurs
  catégories, visibles par tous et non modifiables. Le reste appartient à un utilisateur.
- ``JSONB`` (JSON binaire de PostgreSQL) stocke les données de forme libre : paramètres d'une
  transformation, descripteurs calculés (mis en cache pour ne pas les recalculer).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gallery.extensions import db

# JSONB sous PostgreSQL, JSON ordinaire ailleurs (SQLite des tests)
JsonType = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(100))         # bcrypt : jamais le mot de passe en clair
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def to_dict(self) -> dict:
        return {"id": self.id, "email": self.email, "username": self.username,
                "created_at": self.created_at.isoformat()}


class Category(db.Model):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    parent: Mapped[Category | None] = relationship(remote_side="Category.id", back_populates="children")
    children: Mapped[list[Category]] = relationship(back_populates="parent")

    @property
    def is_public(self) -> bool:
        return self.owner_id is None


class Image(db.Model):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    filename: Mapped[str] = mapped_column(String(255))  # nom d'origine (affichage, téléchargement)
    location: Mapped[str] = mapped_column(String(10))               # "dataset" ou "storage"
    path: Mapped[str] = mapped_column(String(500))                  # chemin relatif dans location
    cbir_id: Mapped[str] = mapped_column(String(500), unique=True)  # identifiant dans l'index de l'API CBIR
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    size_bytes: Mapped[int] = mapped_column(Integer)
    format: Mapped[str] = mapped_column(String(10))                 # JPEG, PNG...
    source: Mapped[str] = mapped_column(String(12))                 # "dataset", "upload", "transform"
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("images.id", ondelete="SET NULL"))
    transform: Mapped[list | None] = mapped_column(JsonType)  # opérations appliquées (si source = transform)
    descriptors: Mapped[dict | None] = mapped_column(JsonType)      # cache des descripteurs (API CBIR)
    indexed: Mapped[bool] = mapped_column(Boolean, default=False)   # présente dans l'index CBIR ?
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    category: Mapped[Category | None] = relationship()

    __table_args__ = (
        Index("ix_images_owner_category", "owner_id", "category_id"),   # filtre le plus fréquent
        Index("ix_images_category", "category_id"),
    )

    @property
    def is_public(self) -> bool:
        return self.owner_id is None

    def to_dict(self, user_id: int | None = None) -> dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "width": self.width,
            "height": self.height,
            "size_bytes": self.size_bytes,
            "format": self.format,
            "source": self.source,
            "category_id": self.category_id,
            "parent_id": self.parent_id,
            "transform": self.transform,
            "indexed": self.indexed,
            "public": self.is_public,
            "mine": user_id is not None and self.owner_id == user_id,
            "created_at": self.created_at.isoformat(),
            "urls": {
                "file": f"/api/images/{self.id}/file",
                "thumb": f"/api/images/{self.id}/thumb",
                "download": f"/api/images/{self.id}/file?download=1",
            },
        }
