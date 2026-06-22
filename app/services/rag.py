"""RAG (Retrieval Augmented Generation) — cœur de l'intelligence documentaire.

Principes :
  - 1 collection logique = (projet_id, enveloppe). Jamais de fuite cross-projet.
  - Chunking sémantique (par section / paragraphe), pas par nombre de mots.
  - L'enveloppe FINANCIERE est isolée des autres pour respecter la règle d'indépendance.
  - Les sources sont toujours citées (page, section, nom du document).

Pipeline :
  Document → chunks → embeddings Mistral → pgvector (HNSW)
  Question → embed question → recherche top-K → contexte → LLM → réponse + sources
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import Document, DocumentChunk
from app.llm import get_llm
from app.services.parser import ParsedDoc

ENVELOPPE_FINANCIERE = "FINANCIERE"
ENVELOPPE_GENERALE = "GEN"


@dataclass
class ChunkResult:
    chunk_id: UUID
    texte: str
    score: float
    page: int | None
    section: str | None
    document_nom: str
    document_type: str


# ---------- Chunking ----------
# Numérotation de titre CCTP : « 1.2.3 Titre... » / « Article 5 - ... » / « I. Titre »
# On capture la LIGNE ENTIÈRE du titre (jusqu'au \n) pour ne pas perdre le libellé.
TITRE_RX = re.compile(
    r"^(\s*(?:article\s+\d+|[IVXLC]+\.\s|\d+(?:\.\d+){0,3}\.?\s+)[^\n]*)$",
    re.M,
)


def _split_sections(parsed: ParsedDoc) -> list[tuple[str, str, int | None]]:
    """Découpe par titre de section (regex) puis regroupe en chunks.
    Renvoie [(section, texte, page)]. Le titre de section est conservé
    grâce au groupe capturant dans TITRE_RX (re.split le rend en intercalaire)."""
    chunks: list[tuple[str, str, int | None]] = []
    pages = parsed.pages or []
    if not pages:
        pages = [type("P", (), {"page": 1, "texte": parsed.texte_brut})()]

    for p in pages:
        txt = p.texte or ""
        # re.split avec un GROUPE conserve le délimiteur dans le résultat
        morceaux = TITRE_RX.split(txt)
        current_section = "Général"
        buffer = ""
        for frag in morceaux:
            if not frag:
                continue
            frag_strip = frag.strip()
            if not frag_strip:
                continue
            # Si ce fragment EST un titre capturé par le groupe, c'est un nouveau §
            if TITRE_RX.match(frag):
                if buffer.strip():
                    chunks.append((current_section, buffer.strip(), p.page))
                    buffer = ""
                current_section = frag_strip[:200]
            else:
                buffer = (buffer + "\n" + frag_strip).strip()
                if len(buffer) >= settings.chunk_size:
                    chunks.append((current_section, buffer, p.page))
                    buffer = ""
        if buffer.strip():
            chunks.append((current_section, buffer.strip(), p.page))
    return chunks
    return chunks


def index_document(db: Session, document: Document, parsed: ParsedDoc) -> int:
    """Vectorise un document : chunks + embeddings + persistance.
    Renvoie le nombre de chunks créés."""
    sections = _split_sections(parsed)
    if not sections:
        return 0

    # Batch d'embeddings (Mistral accepte plusieurs entrées)
    textes = [t for _, t, _ in sections]
    embeddings = get_llm().embed(textes)

    chunks_objets: list[DocumentChunk] = []
    for i, ((section, contenu, page), emb) in enumerate(zip(sections, embeddings)):
        chunks_objets.append(
            DocumentChunk(
                document_id=document.id,
                projet_id=document.projet_id,
                enveloppe=_guess_enveloppe(document.type),
                ordinal=i,
                texte=contenu,
                page_source=page,
                section=section,
                embedding=emb,
            )
        )

    db.bulk_save_objects(chunks_objets)
    db.commit()

    document.statut = "VECTORIZED"
    document.vectorized_at = datetime.utcnow()
    db.commit()
    return len(chunks_objets)


def _guess_enveloppe(doc_type: str) -> str:
    """Un document BPU/DPGF appartient à l'enveloppe financière."""
    return ENVELOPPE_FINANCIERE if doc_type in ("BPU", "DPGF") else ENVELOPPE_GENERALE


# ---------- Recherche ----------
def retrieve(
    db: Session,
    projet_id: UUID,
    question: str,
    *,
    enveloppe: str | None = None,
    top_k: int | None = None,
) -> list[ChunkResult]:
    """Recherche vectorielle dans un projet (et une enveloppe si précisée)."""
    top_k = top_k or settings.retrieval_top_k
    q_emb = get_llm().embed_one(question)

    # On ne récupère QUE les chunks du projet (isolation), filtrés par enveloppe.
    filtre_env = "AND c.enveloppe = :enveloppe" if enveloppe else ""
    params: dict = {"projet_id": str(projet_id), "q": str(q_emb), "k": top_k}
    if enveloppe:
        params["enveloppe"] = enveloppe

    sql = sa_text(f"""
        SELECT c.id, c.texte, c.page_source, c.section,
               1 - (c.embedding <=> CAST(:q AS vector)) AS score,
               d.nom_fichier, d.type
        FROM document_chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE c.projet_id = CAST(:projet_id AS uuid)
        {filtre_env}
        ORDER BY c.embedding <=> CAST(:q AS vector)
        LIMIT :k
    """)
    rows = db.execute(sql, params).fetchall()
    return [
        ChunkResult(
            chunk_id=r.id,
            texte=r.texte,
            score=float(r.score),
            page=r.page_source,
            section=r.section,
            document_nom=r.nom_fichier,
            document_type=r.type,
        )
        for r in rows
    ]


# ---------- Génération avec sources ----------
SYSTEM_PROMPT = """Tu es le copilote d'un conducteur de travaux BTP français.
Tu réponds aux questions sur un appel d'offres en te basant UNIQUEMENT sur les
extraits fournis (contexte). Tu cites toujours la source sous la forme
[Document, p.X, section]. Si l'information n'est pas dans le contexte, tu dis
« Je n'ai pas trouvé cette information dans les documents du marché. »
Tu es précis, professionnel, et tu ne fabriques rien."""


def answer_with_sources(
    db: Session,
    projet_id: UUID,
    question: str,
    *,
    enveloppe: str | None = None,
    history: list[dict] | None = None,
) -> dict:
    """Répond à une question sur le marché, en citant ses sources."""
    contextes = retrieve(db, projet_id, question, enveloppe=enveloppe)

    if not contextes:
        return {
            "reponse": (
                "Aucun document indexé pour ce projet. Uploadez d'abord le DCE "
                "(CCTP, CCAP, RC...) pour que je puisse répondre."
            ),
            "sources": [],
        }

    contexte_txt = "\n\n".join(
        f"[{i+1}] {c.document_nom} (p.{c.page}, § « {c.section} ») :\n{c.texte}"
        for i, c in enumerate(contextes)
    )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history[-6:])  # on garde un historique court
    messages.append({
        "role": "user",
        "content": f"Contexte (extraits du marché) :\n{contexte_txt}\n\nQuestion : {question}",
    })

    resp = get_llm().chat(messages, temperature=0.1)
    return {
        "reponse": resp["content"],
        "sources": [
            {
                "document": c.document_nom,
                "type": c.document_type,
                "page": c.page,
                "section": c.section,
                "score": round(c.score, 3),
            }
            for c in contextes
        ],
        "usage": resp["usage"],
    }
