"""Test honnête du parser sur un vrai CCTP public.

On affiche :
  - nb de pages détectées
  - texte des 2 premières pages (pour voir la qualité d'extraction)
  - les sections/titres détectés par notre chunker
  - une vérification : retrouve-t-on le délai, le montant, les lots ?

C'est volontairement brut : on voit ce que pdfplumber sort vraiment.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ajouter le backend au path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.services.parser import parse_bytes
from app.services.rag import _split_sections
from app.services.classifier import classify

PDF = Path(__file__).parent / "cctp_touet.pdf"
data = PDF.read_bytes()

print("=" * 70)
print(f"Fichier : {PDF.name} ({len(data)} octets)")
print("=" * 70)

parsed = parse_bytes(data, PDF.name, "application/pdf")
print(f"\n📄 Pages détectées : {parsed.nb_pages}")
print(f"📏 Longueur texte total : {len(parsed.texte_brut)} caractères")

print("\n" + "─" * 70)
print("EXTRAIT PAGE 1 (400 premiers caractères bruts) :")
print("─" * 70)
if parsed.pages:
    print(parsed.pages[0].texte[:400])
else:
    print("(vide)")

print("\n" + "─" * 70)
print("CLASSIFICATION AUTOMATIQUE :")
print("─" * 70)
cls = classify(parsed)
print(f"  Type deviné : {cls.type}  (confiance {cls.confidence:.2f}, méthode {cls.methode})")

print("\n" + "─" * 70)
print("TITRES DE SECTIONS DÉTECTÉS PAR LE CHUNKER :")
print("─" * 70)
sections = _split_sections(parsed)
print(f"  → {len(sections)} chunks générés")
for i, (section, contenu, page) in enumerate(sections[:15]):
    print(f"  [{i+1}] p.{page} § « {section[:60]} » ({len(contenu)} car.)")
if len(sections) > 15:
    print(f"  ... et {len(sections) - 15} autres")

print("\n" + "─" * 70)
print("TEST MÉTIER : retrouve-t-on les infos clés dans le texte ?")
print("─" * 70)
texte = parsed.texte_brut.lower()

criteres = {
    "délai (mois/jours)": any(m in texte for m in ("délai", "mois", "jours", "jour")),
    "montant (€/euro)": any(m in texte for m in ("€", "euros", "montant", "prix")),
    "lot(s)": "lot" in texte,
    "article(s)": "article" in texte,
    "réception (travaux)": "réception" in texte or "reception" in texte,
    "pénalité(s)": "pénalit" in texte or "penalit" in texte,
    "garantie": "garantie" in texte,
    "CCAG": "ccag" in texte,
}
for k, found in criteres.items():
    print(f"  {'✅' if found else '❌'} {k}")

# Extraction ciblée : lignes contenant des mots-clés importants
print("\n" + "─" * 70)
print("LIGNES CONTENANT « DÉLAI » OU « MONTANT » OU « PÉNALITÉ » :")
print("─" * 70)
mots = ("délai", "montant", "pénalit", "penalit", "garantie")
for ligne in parsed.texte_brut.split("\n"):
    if any(m in ligne.lower() for m in mots) and len(ligne.strip()) > 10:
        print(f"  → {ligne.strip()[:120]}")
