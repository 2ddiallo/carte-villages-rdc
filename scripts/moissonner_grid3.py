#!/usr/bin/env python3
"""
Télécharge le référentiel des localités GRID3 et l'écrit en GeoJSON, une
province par fichier.

Usage :
    python3 scripts/moissonner_grid3.py
    python3 scripts/moissonner_grid3.py --provinces Ituri Nord-Kivu
    python3 scripts/moissonner_grid3.py --sortie data/

Source : GRID3 COD – Settlement Names v8.0 (décembre 2025), produit par
CIESIN/Columbia et WorldPop avec l'INS et le Ministère de la Santé.
Licence CC BY 4.0 — l'attribution est obligatoire sur la carte.
127 942 localités nommées sur toute la RDC.

Le service ArcGIS renvoie au maximum 2 000 objets par requête : la moisson
est paginée (paramètre resultOffset), triée sur OBJECTID pour garantir un
parcours stable.

Contrôles effectués :
  - coordonnées manquantes ou hors emprise RDC → point rejeté
  - identifiant grid3id dupliqué               → dédoublonné (1re occurrence)
  - type de localité mal orthographié à la source (« Quaŕtier ») → corrigé
  - propriétés vides                           → retirées (allège le fichier)
"""

import argparse
import json
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SERVICE = (
    "https://services3.arcgis.com/BU6Aadhn6tbBEdyk/arcgis/rest/services/"
    "GRID3_COD_settlement_names_v8_0/FeatureServer/0"
)

PROVINCES_DEFAUT = ["Ituri", "Nord-Kivu", "Sud-Kivu", "Tanganyika"]

# Attributs conservés. Les autres champs du service (prov_uid, zs_uid, as_uid,
# sourceid, lat/lon redondants avec la géométrie) n'apportent rien à la carte.
CHAMPS = [
    "province",
    "zonesante",
    "airesante",
    "localite",
    "localitetype",
    "localite_alt",
    "enclav",
    "source_acronym",
    "date",
    "precision_",
    "grid3id",
]

TAILLE_PAGE = 2000

# Emprise approximative de la RDC, avec une petite marge (même que convertir_villages.py).
RDC_LAT_MIN, RDC_LAT_MAX = -14.0, 6.0
RDC_LON_MIN, RDC_LON_MAX = 11.0, 32.0

# Corrections des valeurs mal orthographiées dans les données source.
CORRECTIONS_TYPE = {"Quaŕtier": "Quartier"}


def slug(texte: str) -> str:
    """« Nord-Kivu » → « nord-kivu », pour les noms de fichiers."""
    sans_accent = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return sans_accent.lower().replace(" ", "-")


def interroger(params: dict, tentatives: int = 3) -> dict:
    """Appelle le service ArcGIS et renvoie la réponse JSON décodée."""
    url = f"{SERVICE}/query?{urllib.parse.urlencode(params)}"
    for essai in range(1, tentatives + 1):
        try:
            with urllib.request.urlopen(url, timeout=120) as reponse:
                donnees = json.loads(reponse.read().decode("utf-8"))
            if "error" in donnees:
                sys.exit(f"Erreur du service GRID3 : {donnees['error'].get('message')}")
            return donnees
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as erreur:
            if essai == tentatives:
                sys.exit(f"Échec de la requête après {tentatives} tentatives : {erreur}")
            print(f"    (tentative {essai} échouée : {erreur} — nouvel essai)")
            time.sleep(2 * essai)
    return {}


def compter(province: str) -> int:
    reponse = interroger({
        "where": f"province='{province}'",
        "returnCountOnly": "true",
        "f": "json",
    })
    return reponse.get("count", 0)


def moissonner(province: str) -> list:
    """Télécharge toutes les localités d'une province, page par page."""
    features = []
    offset = 0
    while True:
        reponse = interroger({
            "where": f"province='{province}'",
            "outFields": ",".join(CHAMPS),
            "orderByFields": "OBJECTID",
            "resultOffset": offset,
            "resultRecordCount": TAILLE_PAGE,
            "f": "geojson",
        })
        page = reponse.get("features", [])
        if not page:
            break
        features.extend(page)
        print(f"    {len(features)} localités téléchargées…", end="\r", flush=True)
        if len(page) < TAILLE_PAGE:
            break
        offset += TAILLE_PAGE
    print(" " * 50, end="\r")
    return features


def nettoyer(features: list) -> tuple:
    """Valide, dédoublonne et allège. Renvoie (features propres, rejets, doublons)."""
    propres = []
    rejets = 0
    vus = set()
    doublons = 0

    for feature in features:
        geometrie = feature.get("geometry") or {}
        coordonnees = geometrie.get("coordinates") or []
        if len(coordonnees) < 2 or coordonnees[0] is None or coordonnees[1] is None:
            rejets += 1
            continue
        lon, lat = float(coordonnees[0]), float(coordonnees[1])
        if not (RDC_LAT_MIN <= lat <= RDC_LAT_MAX and RDC_LON_MIN <= lon <= RDC_LON_MAX):
            rejets += 1
            continue

        proprietes = feature.get("properties") or {}
        identifiant = proprietes.get("grid3id")
        if identifiant:
            if identifiant in vus:
                doublons += 1
                continue
            vus.add(identifiant)

        if proprietes.get("localitetype") in CORRECTIONS_TYPE:
            proprietes["localitetype"] = CORRECTIONS_TYPE[proprietes["localitetype"]]

        # Retirer les propriétés vides : à 25 000 points, cela pèse.
        proprietes = {
            cle: valeur for cle, valeur in proprietes.items()
            if valeur not in (None, "")
        }

        propres.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
            "properties": proprietes,
        })

    return propres, rejets, doublons


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Télécharge le référentiel des localités GRID3 (RDC) en GeoJSON."
    )
    parser.add_argument("--provinces", nargs="+", default=PROVINCES_DEFAUT,
                        help=f"Provinces à moissonner (défaut : {' '.join(PROVINCES_DEFAUT)})")
    parser.add_argument("--sortie", type=Path, default=None,
                        help="Dossier de sortie (défaut : data/)")
    args = parser.parse_args()

    dossier = args.sortie or Path(__file__).resolve().parent.parent / "data"
    dossier.mkdir(parents=True, exist_ok=True)

    print("Source : GRID3 COD – Settlement Names v8.0 (CC BY 4.0)\n")
    total_ecrit = 0
    resume = []

    for province in args.provinces:
        print(f"{province}")
        attendu = compter(province)
        if attendu == 0:
            print("    aucune localité — nom de province incorrect ?\n")
            continue
        print(f"    {attendu} localités annoncées par le service")

        features = moissonner(province)
        propres, rejets, doublons = nettoyer(features)

        chemin = dossier / f"grid3_{slug(province)}.geojson"
        with open(chemin, "w", encoding="utf-8") as fichier:
            json.dump({"type": "FeatureCollection", "features": propres},
                      fichier, ensure_ascii=False, separators=(",", ":"))

        taille_mo = chemin.stat().st_size / 1_048_576
        print(f"    téléchargées           : {len(features)}")
        if len(features) != attendu:
            print(f"    ⚠ écart avec l'annonce : {attendu - len(features)}")
        if rejets:
            print(f"    rejetées (coordonnées) : {rejets}")
        if doublons:
            print(f"    doublons supprimés     : {doublons}")
        print(f"    écrites                : {len(propres)}")
        print(f"    fichier                : {chemin.name} ({taille_mo:.1f} Mo)\n")

        total_ecrit += len(propres)
        resume.append((province, len(propres), taille_mo))

    print("─" * 46)
    for province, nombre, taille in resume:
        print(f"{province:<14} {nombre:>7} localités   {taille:>5.1f} Mo")
    print(f"{'TOTAL':<14} {total_ecrit:>7} localités")


if __name__ == "__main__":
    main()
