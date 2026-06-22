# Architecture Batião

## Vue d'ensemble

```
┌─────────────────────── COUCHE INTERFACE ───────────────────────┐
│  Streamlit (M0-M3) → Next.js (M4+)                              │
└────────────────────────────┬────────────────────────────────────┘
                             │ REST / JSON
                             ▼
┌─────────────────────── COUCHE API (FastAPI) ───────────────────┐
│  /projets   /documents   /chat   /enveloppes (à venir)          │
└────────────────────────────┬────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌──────────────┐  ┌──────────────────┐  ┌─────────────────────┐
│ Ingestion    │  │ RAG (recherche)  │  │ Agents IA           │
│ PDF/DOCX/ZIP │  │ pgvector + HNSW  │  │ (à venir M2-M6)     │
│ + classifieur│  │                  │  │ juriste/économiste  │
└──────┬───────┘  └────────┬─────────┘  └──────────┬──────────┘
       │                   │                       │
       ▼                   ▼                       ▼
┌──────────────────────────────────────────────────────────────┐
│  Client LLM unifié (Mistral API ou local vLLM/Ollama)        │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│  PostgreSQL 16 + pgvector  │  MinIO (fichiers)  │  Redis     │
└──────────────────────────────────────────────────────────────┘
```

## Principes fondamentaux

### 1. Isolation par projet
Chaque projet (appel d'offres) est un « cerveau » autonome. La recherche
vectorielle ne sort JAMAIS du périmètre `projet_id`. Cela évite qu'un CCTP
d'un projet A influence les réponses du projet B.

### 2. Isolation de l'enveloppe financière
Les documents BPU/DPGF sont taggés `enveloppe='FINANCIERE'` dans les chunks.
Cela respecte la règle française d'indépendance des critères de prix.

### 3. Sources toujours citées
Chaque réponse IA s'accompagne de ses sources (document, page, section, score
de similarité). L'utilisateur peut toujours vérifier. Indispensable pour de
l'on-prem BTP où la traçabilité est juridique.

### 4. Souveraineté
Toute la stack tourne chez le client. En mode `LLM_BACKEND=local`, même le LLM
et les embeddings ne sortent pas. Argument commercial majeur face à des
promoteurs ou collectivités sensibles au RGPD.

## Schéma de données (synthèse)

Voir `backend/app/db/__init__.py` pour le détail. Tables principales :

- `tenants` → isolation multi-clients
- `projets` → 1 appel d'offres
- `documents` → pièces brutes (CCTP, CCAP, RC...)
- `document_chunks` → morceaux vectorisés (RAG)
- `analyses_go_nogo`, `clauses_sensibles`, `ouvrages_cctp` → extractions IA
- `enveloppe_administrative`, `enveloppe_technique`, `enveloppe_financiere`
- `audit_log` → traçabilité

## Roadmap des modules

| Milestone | Périmètre | Statut |
|---|---|---|
| **M0/M1** | Ingestion + RAG + chat | ✅ Livré |
| M2 | Agent Tri/Go-No-Go | ⏳ À venir |
| M3 | Agents Juriste + Économiste (clauses, ouvrages) | ⏳ À venir |
| M4 | Enveloppe administrative (DC1/DC2/DC4/AE) | ⏳ À venir |
| M5 | Enveloppe technique (mémoire) | ⏳ À venir |
| M6 | Enveloppe financière (DPGF/BPU) | ⏳ À venir |
| M7 | UI Next.js + packaging final | ⏳ À venir |
