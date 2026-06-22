# Batião — Installation (on-prem / souverain)

Batião est conçu pour tourner **entièrement chez le client** : aucune donnée
n'est envoyée à l'extérieur. Le déploiement se fait via Docker Compose en une
commande.

## Prérequis

- Serveur Linux (Ubuntu 22.04+ recommandé) — 4 vCPU / 8 Go RAM minimum
- **Docker** 24+ et **Docker Compose** v2
- Une clé **Mistral API** (La Plateforme) **OU** un serveur LLM local (vLLM/Ollama)
- 50 Go d'espace disque (DCE + base + vectorielle)

## 1. Récupérer le code

```bash
git clone <votre-depot> batiao
cd batiao
```

## 2. Configurer l'environnement

```bash
cp .env.example .env
nano .env
```

Points critiques à renseigner :

| Variable | Valeur attendue |
|---|---|
| `SECRET_KEY` | Une chaîne aléatoire de 32+ caractères (`openssl rand -hex 32`) |
| `POSTGRES_PASSWORD` | Mot de passe fort de la base |
| `MINIO_ROOT_PASSWORD` | Mot de passe fort du stockage |
| `LLM_BACKEND` | `mistral_api` (cloud FR) **ou** `local` (100% on-prem) |
| `MISTRAL_API_KEY` | Votre clé (si `mistral_api`) |

## 3. Démarrer la stack

```bash
docker compose up -d --build
```

Services exposés :

| Service | URL locale | Rôle |
|---|---|---|
| API backend | http://localhost:8000 (docs : `/docs`) | Cœur applicatif |
| UI Streamlit | http://localhost:8501 | Interface utilisateur |
| MinIO console | http://localhost:9001 | Stockage fichiers |
| Postgres | localhost:5432 | Base + vecteurs |

Vérifier que tout tourne :

```bash
docker compose ps
curl http://localhost:8000/health
# {"status":"ok","app":"batiao",...}
```

## 4. Premier usage

1. Ouvrir http://localhost:8501
2. Créer un projet (intitulé du marché)
3. Téléverser le DCE (PDF/DOCX/ZIP)
4. Discuter avec le marché

## 5. Mode 100% local (aucune donnée sortante)

Dans `.env` :

```
LLM_BACKEND=local
LOCAL_LLM_BASE_URL=http://localhost:11434/v1
LOCAL_LLM_MODEL=mistral-nemo
MISTRAL_EMBED_MODEL=nomic-embed-text   # modèle d'embedding local
```

Lancer Ollama sur le serveur :

```bash
ollama pull mistral-nemo
ollama pull nomic-embed-text
```

Toute l'IA (chat, embeddings, classification) reste sur le serveur.

## 6. Sauvegardes

```bash
# Base de données
docker exec batiao-db pg_dump -U batiao batiao > backup_$(date +%F).sql

# Fichiers (MinIO)
docker run --rm --network batiao_default -v $(pwd):/backup \
  amazon/aws-cli s3 cp --recursive s3://batiao-docs /backup/minio \
  --endpoint-url http://minio:9000
```

## 7. Mise à jour

```bash
git pull
docker compose up -d --build
# Les migrations Alembic s'appliquent automatiquement au démarrage du backend
```

## Dépannage

- **« API backend injoignable »** dans Streamlit → `docker compose logs backend`
- **Erreur Mistral API** → vérifier `MISTRAL_API_KEY` et quotas
- **Embeddings vides** → en mode local, vérifier qu'Ollama tourne et a téléchargé le modèle d'embedding
