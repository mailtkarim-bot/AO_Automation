# Batião — Copilote IA de réponse aux appels d'offres BTP

> L'IA lit vos marchés, fait le travail, vos équipes valident.

**Batião** est un copilote IA destiné aux entreprises de construction et promoteurs
immobiliers français. Il automatise l'analyse et la réponse aux appels d'offres,
en respectant la procédure française (MAPA / procédure formalisée, 3 enveloppes,
CCAG-Travaux 2021, dématérialisation).

Conçu pour un déploiement **100 % souverain (on-prem)** : aucune donnée ne sort
de l'infrastructure du client. Moteur IA : **Mistral** (souverain français).

## Modules du produit

1. **Analyse & réponse aux appels d'offres** (M1 → M7, en cours)
   - Tri / Go-No-Go automatique d'un DCE
   - Enveloppe administrative (DC1, DC2, DC4, acte d'engagement)
   - Enveloppe technique (mémoire technique)
   - Enveloppe financière (DPGF / BPU) — isolée
2. *(à venir)* Métré depuis CCTP / plans
3. *(à venir)* Suivi de chantier
4. *(à venir)* Gestion administrative & financière d'exécution

## Stack

| Couche | Technologie |
|---|---|
| Backend | Python 3.11 · FastAPI · SQLAlchemy 2 · Alembic |
| IA / RAG | LangChain · pgvector · Mistral (API La Plateforme ou local vLLM) |
| Données | PostgreSQL 16 + pgvector · Redis (files) |
| Stockage fichiers | MinIO (S3-compatible) |
| UI (M0–M3) | Streamlit |
| UI (M4+) | Next.js |
| Déploiement | Docker Compose (on-prem en 1 commande) |

## Démarrage rapide (dev)

```bash
cp .env.example .env          # renseigner MISTRAL_API_KEY
docker compose up -d          # Postgres + pgvector + MinIO + Redis
cd backend && uv pip install -r requirements.txt
uv run alembic upgrade head   # créer le schéma
uv run uvicorn app.main:app --reload   # API sur :8000
streamlit run frontend_streamlit/app.py # UI sur :8501
```

Voir `docs/INSTALL.md` pour le déploiement on-prem chez un client.

## Structure du dépôt

```
batiao/
├── backend/          # API FastAPI + agents IA + RAG
├── frontend_streamlit/  # UI de validation (M0–M3)
├── infra/            # Dockerfiles, scripts d'install on-prem
├── docs/             # Documentation FR (install, archi, métier)
└── docker-compose.yml
```

## Statut

🚧 En cours de développement — Milestone M0/M1 (fondation + ingestion).
