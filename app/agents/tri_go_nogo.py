"""Agent « Tri / Go-No-Go » — l'arme commerciale de Batião.

Lit un marché (texte extrait d'un DCE) et produit une fiche verdict :
  - verdict (JOUER / RISQUE / EVITER)
  - score 0-100
  - synthèse 3-5 lignes
  - red flags (clauses dangereuses, délais irréalistes, garanties lourdes…)
  - points forts
  - infos clés extraites (montant, délai, maître d'ouvrage, procédure, lots, dates)

C'est volontairement un agent PUR (pas de dépendance DB) : il prend du texte,
rend un dict. Comme ça on peut le tester en standalone, et l'API l'enroule
autour d'un projet existant.

La valeur n'est pas dans le code, elle est dans le PROMPT. Le prompt ci-dessous
encapsule des décennies de bon sens BTP français. À affiner avec le client.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.llm import get_llm

PROMPT_VERSION = "tri-v1.0"

SYSTEM_PROMPT = """Tu es un conducteur de travaux BTP français Senior (20 ans d'expérience).
On te donne le contenu d'un dossier de consultation (DCE / CCTP / CCAP / RC).
Ton job : aider une PME de construction à décider RAPIDEMENT si elle doit répondre
à cet appel d'offres (Go / No-Go), en moins de 2 minutes de lecture humaine.

Tu raisonnes comme un entrepreneur prudent qui a déjà perdu de l'argent sur de
mauvais marchés. Tu repères les pièges.

RED FLAGS que tu dois systématiquement chercher :
  - Délai d'exécution irréaliste (trop court pour le volume de travaux)
  - Pénalités de retard > 1/1000 du montant par jour, ou plafonnées trop bas
  - Garantie de bonne exécution > 5%, ou garantie décennale exigée à 100%
  - Retenue de garantie > 5%
  - Avance forfaitaire refusée ou < 5% sur gros chantier
  - CCAG-Travaux 2021 imposé avec clauses défavorables
  - Sous-traitance imposée ou interdite
  - Approvisionnements / matériaux imposés à des fournisseurs uniques
  - Conditions de paiement > 30 jours, ou délais flous
  - Marché à tranches avec conditionnement défavorable
  - Critères de sélection flous ou pondération défavorable au prix
  - Visites obligatoires non planifiables, questions à des dates serrées
  - Capacités financières exigées disproportionnées (CA min > 2x montant marché)
  - Qualifications requises trop strictes (Qualibat RGE etc. hors-sujet)

INFORMATIONS CLÉS à extraire (si présentes) :
  - Maître d'ouvrage, lieu, objet du marché
  - Montant estimé (ou fourchette)
  - Délai d'exécution (en mois / jours)
  - Procédure (MAPA, appel d'offres ouvert/restreint)
  - Nombre de lots + intitulés
  - Date limite de remise, dates de visites, dates de questions
  - Critères de jugement et pondération
  - CCAG applicable
  - Modalités de prix (ferme, révisable) et de paiement

RÈGLE DE NOTATION :
  70-100  → JOUER   (marché sain, rentable, jouable)
  40-69   → RISQUE  (jouable mais points de vigilance à traiter avant réponse)
  0-39    → EVITER  (trop risqué / clauses dangereuses / hors capacité)

Tu réponds UNIQUEMENT par un JSON strict de cette forme (pas de texte autour) :
{
  "verdict": "JOUER" | "RISQUE" | "EVITER",
  "score": <int 0-100>,
  "synthese": "<3 à 5 lignes max, ton direct>",
  "maitre_ouvrage": "..." | null,
  "objet": "..." | null,
  "lieu": "..." | null,
  "montant_estime": "..." | null,
  "delai_execution": "..." | null,
  "procedure": "..." | null,
  "nb_lots": <int> | null,
  "lots": ["...", "..."] | [],
  "date_remise": "..." | null,
  "ccag": "..." | null,
  "criteres": [{"critere": "...", "ponderation": "..."}] | [],
  "red_flags": [{"type": "...", "libelle": "...", "severite": "INFO|ATTENTION|CRITIQUE"}],
  "points_forts": ["...", "..."]
}

Si une information n'est pas dans le document, mets null (ne l'invente JAMAIS).
Sois précis, professionnel, français de France. Cite les chiffres exacts."""


@dataclass
class TriResult:
    verdict: str
    score: int
    synthese: str
    red_flags: list[dict]
    points_forts: list[dict]
    infos: dict
    model_used: str
    raw: dict

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "score": self.score,
            "synthese": self.synthese,
            "red_flags": self.red_flags,
            "points_forts": self.points_forts,
            "infos": self.infos,
            "model_used": self.model_used,
            "prompt_version": PROMPT_VERSION,
        }


def analyser_marche(texte: str, *, max_chars: int = 60_000) -> TriResult:
    """Analyse un texte de marché et renvoie un verdict Go/No-Go.

    `max_chars` : on tronque les très gros DCE pour rester dans la fenêtre du LLM.
    Pour un traitement plus fin, l'agent devrait d'abord résumer par lot puis
    synthétiser (évolution future).
    """
    if not texte or not texte.strip():
        raise ValueError("Texte du marché vide.")

    extrait = texte.strip()[:max_chars]

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Voici le contenu du marché :\n\n{extrait}"},
    ]

    resp = get_llm().chat(
        messages,
        model=settings.mistral_model_large,
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    try:
        data: dict[str, Any] = json.loads(resp["content"])
    except json.JSONDecodeError:
        data = get_llm().extract_json(resp["content"])

    # Normalisation défensive
    verdict = str(data.get("verdict", "RISQUE")).upper()
    if verdict not in ("JOUER", "RISQUE", "EVITER"):
        verdict = "RISQUE"
    score_raw = data.get("score", 50)
    try:
        score = max(0, min(100, int(score_raw)))
    except (TypeError, ValueError):
        score = 50

    infos = {
        k: data.get(k)
        for k in (
            "maitre_ouvrage", "objet", "lieu", "montant_estime", "delai_execution",
            "procedure", "nb_lots", "lots", "date_remise", "ccag", "criteres",
        )
    }

    return TriResult(
        verdict=verdict,
        score=score,
        synthese=str(data.get("synthese", "")),
        red_flags=data.get("red_flags", []) or [],
        points_forts=data.get("points_forts", []) or [],
        infos=infos,
        model_used=resp["model"],
        raw=data,
    )
