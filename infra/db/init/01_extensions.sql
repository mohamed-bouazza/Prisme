-- Exécuté automatiquement par PostgreSQL au tout premier démarrage du conteneur.
-- Active les extensions utiles au projet.

CREATE EXTENSION IF NOT EXISTS vector;     -- pgvector : colonnes de type vecteur (descripteurs)
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid() : identifiants uniques
