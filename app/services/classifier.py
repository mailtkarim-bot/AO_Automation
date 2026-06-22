"""Classification automatique des pièces d'un DCE.

Un DCE contient typiquement : CCTP, CCAP, RC (règlement de consultation),
AAPC, BPU/DPGF, plans, CCAG, acte d'engagement. On les reconnaît à deux
niveaux :
  1. heuristique rapide (nom de fichier + mots-clés du début) ;
  2. LLM en confirmation si doute.

C'est plus rapide et moins coûteux que de tout envoyer au LLM.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.llm import get_llm
from app.services.parser import ParsedDoc

DOC_TYPES = ("CCTP", "CCAP", "RC", "RCAP", "AAPC", "BPU", "DPGF", "PA", "CCAG", "AE", "AUTRE")

# Règles par ordre de priorité. (regex sur le nom, regex sur le début du texte)
_HEURISTICS: list[tuple[str, re.Pattern[str], re.Pattern[str] | None]] = [
    ("CCTP", re.compile(r"cctp", re.I), re.compile(r"cahier des clauses techniques", re.I)),
    ("CCAP", re.compile(r"ccap", re.I), re.compile(r"clauses administratives", re.I)),
    ("DPGF", re.compile(r"dpgf", re.I), re.compile(r"d[ée]tail estimatif|d[ée]composition du prix global", re.I)),
    ("BPU",  re.compile(r"\bbpu\b", re.I), re.compile(r"bordereau des prix unitaires", re.I)),
    ("RCAP", re.compile(r"rcap", re.I), re.compile(r"r[èe]glement de la consultation", re.I)),
    ("RC",   re.compile(r"\brc\b|\br[èe]glement\b", re.I), re.compile(r"r[èe]glement de la consultation", re.I)),
    ("AAPC", re.compile(r"aapc|avis d'appel|aac", re.I),
     re.compile(r"avis d'appel public [àa] la concurrence", re.I)),
    ("PA",   re.compile(r"\.pdf$|plans?|dwg|dxf", re.I), re.compile(r"[ÉE]chelle\s*1/", re.I)),
    ("CCAG", re.compile(r"ccag", re.I), re.compile(r"cahier des clauses administratives g[ée]n[ée]rales", re.I)),
    ("AE",   re.compile(r"acte d'engagement|\bae\b", re.I),
     re.compile(r"acte d'engagement", re.I)),
]


@dataclass
class Classification:
    type: str
    confidence: float
    methode: str  # "heuristique" | "llm"


def classify(parsed: ParsedDoc) -> Classification:
    nom = parsed.nom
    texte_tete = (parsed.pages[0].texte if parsed.pages else parsed.texte_brut)[:2500].lower()

    # 1. Heuristique
    for type_attendu, rx_nom, rx_txt in _HEURISTICS:
        nom_match = rx_nom.search(nom)
        txt_match = rx_txt.search(texte_tete) if rx_txt else None
        if nom_match and txt_match:
            return Classification(type_attendu, 0.95, "heuristique")
        if nom_match:
            return Classification(type_attendu, 0.75, "heuristique")
        if txt_match:
            return Classification(type_attendu, 0.85, "heuristique")

    # 2. LLM en cas d'échec (sur un échantillon de texte)
    echantillon = texte_tete[:2000] or "(document vide ou binaire)"
    prompt = (
        "Tu classifies une pièce d'un dossier de consultation d'entreprise (DCE) BTP français.\n"
        f"Nom du fichier : {nom}\n\n"
        f"Début du contenu :\n{echantillon}\n\n"
        "Réponds UNIQUEMENT par un objet JSON de la forme :\n"
        '{"type": "<un parmi: CCTP|CCAP|RC|RCAP|AAPC|BPU|DPGF|PA|CCAG|AE|AUTRE>", '
        '"confidence": <0-1>}\n'
        "Pas de texte autour."
    )
    try:
        resp = get_llm().chat(
            [{"role": "user", "content": prompt}],
            model=None,  # modèle par défaut = Large
            temperature=0.0,
            max_tokens=200,
            response_format={"type": "json_object"},
        )
        import json
        data = json.loads(resp["content"])
        t = str(data.get("type", "AUTRE")).upper()
        if t not in DOC_TYPES:
            t = "AUTRE"
        return Classification(t, float(data.get("confidence", 0.5)), "llm")
    except Exception:
        return Classification("AUTRE", 0.2, "llm-fallback")
