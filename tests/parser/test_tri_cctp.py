"""Test standalone de l'agent Tri/Go-No-Go sur le CCTP Touet.

Aucune DB nécessaire : on appelle directement analyser_marche().
Ça prouve que la VALEUR (l'analyse IA) fonctionne, indépendamment de l'infra.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

backend = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(backend))

# Charger la config depuis le .env racine
os.chdir(backend)

from app.services.parser import parse_bytes
from app.agents.tri_go_nogo import analyser_marche

PDF = Path(__file__).parent / "cctp_touet.pdf"
data = PDF.read_bytes()

print("=" * 72)
print("AGENT TRI / GO-NO-GO — TEST SUR CCTP RÉEL")
print("=" * 72)

print("\n⏳ Parsing du CCTP...")
parsed = parse_bytes(data, PDF.name, "application/pdf")
print(f"   ✅ {parsed.nb_pages} pages, {len(parsed.texte_brut)} caractères extraits")

print("\n🤖 Lancement de l'agent IA Tri (Mistral)...")
print("   (peut prendre 10-30 secondes selon le modèle)")
try:
    result = analyser_marche(parsed.texte_brut)
except Exception as e:
    print(f"\n❌ Échec de l'agent : {e}")
    print("\nVérifiez votre .env :")
    print("  - LLM_BACKEND doit être 'mistral_api' (avec MISTRAL_API_KEY)")
    print("    ou 'local' (avec Ollama qui tourne sur LOCAL_LLM_BASE_URL)")
    sys.exit(1)

print("\n" + "=" * 72)
print(f"VERDICT : {result.verdict}   (score {result.score}/100)")
print("=" * 72)

print(f"\n📋 SYNTHÈSE :\n{result.synthese}")

print("\n🔑 INFOS CLÉS EXTRAITES :")
infos = result.infos
for k, v in infos.items():
    if v is None or v == [] or v == "":
        continue
    if isinstance(v, list) and len(v) > 5:
        print(f"  • {k} : {len(v)} éléments")
        for item in v[:5]:
            print(f"      - {item}")
    else:
        print(f"  • {k} : {v}")

print(f"\n🚩 RED FLAGS ({len(result.red_flags)}) :")
if result.red_flags:
    for rf in result.red_flags:
        sev = rf.get("severite", "?")
        emoji = {"CRITIQUE": "🔴", "ATTENTION": "🟠", "INFO": "🔵"}.get(sev, "⚪")
        print(f"  {emoji} [{rf.get('type','?')}] {rf.get('libelle','')}")
else:
    print("  (aucun)")

print(f"\n💪 POINTS FORTS ({len(result.points_forts)}) :")
for pf in result.points_forts:
    print(f"  ✅ {pf}")

print(f"\n📊 Modèle utilisé : {result.model_used}")
print(f"🏷️  Version du prompt : tri-v1.0")

# Dump JSON pour archivage
out = Path(__file__).parent / "tri_resultat.json"
out.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False, default=str))
print(f"\n💾 Résultat complet sauvegardé : {out}")
