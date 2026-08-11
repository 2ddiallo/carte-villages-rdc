#!/usr/bin/env python3
"""
Compare l'export CHDC au référentiel GRID3, province par province.

Usage :
    python3 scripts/rapprocher_chdc_grid3.py
    python3 scripts/rapprocher_chdc_grid3.py --seuil-nom 0.90

Objectif : savoir combien des villages de l'export CHDC existent déjà dans le
référentiel GRID3, et lesquels n'y sont pas. Les deux couches restant
distinctes sur la carte, ce rapprochement ne modifie aucune donnée — il sert
à mesurer le recouvrement et à repérer les villages CHDC que GRID3 ignore.

Méthode : pour chaque village CHDC, on cherche les localités GRID3 dans un
rayon de 2 km (indexation par cellules), puis on compare les noms normalisés
avec le nom principal et le nom alternatif GRID3.

Les noms CHDC suivent le format « Village Gr Groupement » (« Dada Gr Dhendro ») :
le suffixe à partir de « Gr » désigne le groupement, pas le village, et doit
être écarté avant comparaison — sans quoi « Dada » et « Dada Gr Dhendro » ne
se ressemblent qu'à 50 %. Les variantes entre parenthèses (« Sab'ba (Saba) »)
sont testées séparément, chacune contre chaque nom GRID3.

    apparié sûr      distance < 500 m  et similarité ≥ seuil
    apparié probable distance < 2 km   et similarité ≥ seuil
                     ou distance < 500 m et similarité ≥ 0,60
    absent           aucun candidat retenu

Sorties :
  - un tableau récapitulatif à l'écran
  - data/rapprochement_chdc_absents.csv : villages CHDC sans correspondance,
    avec le meilleur candidat GRID3 trouvé, pour vérification manuelle
"""

import argparse
import csv
import json
import math
import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

PROVINCES_DEFAUT = ["Ituri", "Nord-Kivu", "Sud-Kivu", "Tanganyika", "Maniema",
                    "Kwango", "Haut-Katanga", "Kinshasa", "Kwilu", "Mai-Ndombe",
                    "Haut-Lomami"]

RACINE = Path(__file__).resolve().parent.parent

# Mots sans valeur discriminante dans les noms de villages congolais.
MOTS_PARASITES = {"cite", "village", "loc", "localite", "centre"}

# « Dada Gr Dhendro » → on ne garde que « Dada ». Le suffixe est le groupement.
SUFFIXE_GROUPEMENT = re.compile(r"\s+(?:gr|grp|groupement)\b.*$", re.IGNORECASE)

RAYON_SUR_M = 500
RAYON_PROBABLE_M = 2000
SEUIL_FAIBLE = 0.60

# Taille des cellules d'indexation : 0,02° ≈ 2,2 km.
PAS_CELLULE = 0.02


def slug(texte: str) -> str:
    sans_accent = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return sans_accent.lower().replace(" ", "-")


def cle_province(nom) -> str:
    """Ramène les graphies divergentes d'une province à une clé unique."""
    s = unicodedata.normalize("NFKD", str(nom or "")).encode("ascii", "ignore").decode()
    return s.lower().replace("-", "").replace(" ", "")


def normaliser(nom) -> str:
    """« Sab'ba » → « sabba ». Accents, ponctuation et mots parasites retirés."""
    if not nom:
        return ""
    sans_accent = unicodedata.normalize("NFKD", str(nom)).encode("ascii", "ignore").decode()
    # Les apostrophes (droites ou typographiques) sont supprimées, pas remplacées
    # par un espace : « Sab'ba » et « Sabba » doivent se confondre.
    sans_apostrophe = re.sub(r"['‘’ʼ]", "", sans_accent.lower())
    sans_ponctuation = re.sub(r"[^a-z0-9\s]", " ", sans_apostrophe)
    mots = [m for m in sans_ponctuation.split() if m not in MOTS_PARASITES]
    return " ".join(mots)


def variantes_nom(nom, retirer_groupement: bool = False) -> list:
    """Toutes les écritures possibles d'un nom, la principale en premier.

    « Sab'ba (Saba) Gr Sesele » → ['sabba', 'saba']  (côté CHDC)
    """
    if not nom:
        return []
    base = str(nom)
    if retirer_groupement:
        base = SUFFIXE_GROUPEMENT.sub("", base).strip()
    formes = [re.sub(r"\([^)]*\)", " ", base)]           # sans la parenthèse
    formes += re.findall(r"\(([^)]*)\)", base)            # le contenu de chaque parenthèse
    variantes = []
    for forme in formes:
        normalisee = normaliser(forme)
        if normalisee and normalisee not in variantes:
            variantes.append(normalisee)
    return variantes


def similarite(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def distance_m(lat1, lon1, lat2, lon2) -> float:
    """Haversine, en mètres."""
    r = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def charger_grid3(province: str) -> list:
    chemin = RACINE / "data" / f"grid3_{slug(province)}.geojson"
    if not chemin.exists():
        raise SystemExit(
            f"Fichier manquant : {chemin}\n"
            "Lancer d'abord : python3 scripts/moissonner_grid3.py"
        )
    with open(chemin, encoding="utf-8") as fichier:
        donnees = json.load(fichier)
    points = []
    for feature in donnees["features"]:
        lon, lat = feature["geometry"]["coordinates"]
        proprietes = feature["properties"]
        points.append({
            "lat": lat,
            "lon": lon,
            "nom": proprietes.get("localite", ""),
            "noms_normalises": list(dict.fromkeys(
                variantes_nom(proprietes.get("localite"))
                + variantes_nom(proprietes.get("localite_alt"))
            )),
            "zonesante": proprietes.get("zonesante", ""),
            "grid3id": proprietes.get("grid3id", ""),
        })
    return points


def charger_chdc() -> dict:
    chemin = RACINE / "data" / "villages.geojson"
    if not chemin.exists():
        raise SystemExit(f"Fichier manquant : {chemin}")
    with open(chemin, encoding="utf-8") as fichier:
        donnees = json.load(fichier)
    par_province = defaultdict(list)
    for feature in donnees["features"]:
        lon, lat = feature["geometry"]["coordinates"]
        proprietes = feature["properties"]
        # L'export CHDC écrit « Maï Ndombe » là où GRID3 écrit « Mai-Ndombe » :
        # on indexe sur une clé normalisée pour que les deux se retrouvent.
        par_province[cle_province(proprietes.get("Province"))].append({
            "lat": lat,
            "lon": lon,
            "nom": proprietes.get("Village", ""),
            "noms_normalises": variantes_nom(proprietes.get("Village"), retirer_groupement=True),
            "territoire": proprietes.get("Territory", ""),
        })
    return par_province


def indexer(points: list) -> dict:
    """Range les points GRID3 dans des cellules, pour ne comparer que le voisinage."""
    cellules = defaultdict(list)
    for indice, point in enumerate(points):
        cle = (int(point["lat"] / PAS_CELLULE), int(point["lon"] / PAS_CELLULE))
        cellules[cle].append(indice)
    return cellules


def voisins(cellules: dict, points: list, lat: float, lon: float) -> list:
    ligne, colonne = int(lat / PAS_CELLULE), int(lon / PAS_CELLULE)
    resultat = []
    for dl in (-1, 0, 1):
        for dc in (-1, 0, 1):
            resultat.extend(cellules.get((ligne + dl, colonne + dc), []))
    return resultat


def apparier(village: dict, cellules: dict, points: list, seuil: float) -> tuple:
    """Renvoie (statut, meilleur candidat, distance, similarité)."""
    meilleur = None
    for indice in voisins(cellules, points, village["lat"], village["lon"]):
        point = points[indice]
        distance = distance_m(village["lat"], village["lon"], point["lat"], point["lon"])
        if distance > RAYON_PROBABLE_M:
            continue
        score = max(
            (similarite(nom_chdc, nom_grid3)
             for nom_chdc in village["noms_normalises"]
             for nom_grid3 in point["noms_normalises"]),
            default=0.0,
        )
        if meilleur is None or (score, -distance) > (meilleur[2], -meilleur[1]):
            meilleur = (indice, distance, score)

    if meilleur is None:
        return "absent", None, None, None

    indice, distance, score = meilleur
    if distance < RAYON_SUR_M and score >= seuil:
        statut = "sur"
    elif score >= seuil or (distance < RAYON_SUR_M and score >= SEUIL_FAIBLE):
        statut = "probable"
    else:
        statut = "absent"
    return statut, points[indice], distance, score


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare l'export CHDC au référentiel GRID3."
    )
    parser.add_argument("--seuil-nom", type=float, default=0.85,
                        help="Similarité minimale des noms (0 à 1, défaut : 0.85)")
    parser.add_argument("--provinces", nargs="+", default=PROVINCES_DEFAUT,
                        help="Provinces à comparer (défaut : les 11 de la carte)")
    args = parser.parse_args()

    chdc = charger_chdc()
    lignes_absents = []
    resume = []

    print(f"Seuil de similarité des noms : {args.seuil_nom}\n")
    print(f"{'Province':<12} {'CHDC':>6} {'GRID3':>7} {'sûrs':>6} {'probab.':>8} {'absents':>8} {'GRID3 seuls':>12}")
    print("─" * 65)

    for province in args.provinces:
        villages = chdc.get(cle_province(province), [])
        points = charger_grid3(province)
        cellules = indexer(points)

        comptes = {"sur": 0, "probable": 0, "absent": 0}
        grid3_apparies = set()

        for village in villages:
            statut, candidat, distance, score = apparier(village, cellules, points, args.seuil_nom)
            comptes[statut] += 1
            if statut == "absent":
                lignes_absents.append({
                    "province": province,
                    "territoire": village["territoire"],
                    "village_chdc": village["nom"],
                    "latitude": round(village["lat"], 6),
                    "longitude": round(village["lon"], 6),
                    "meilleur_candidat_grid3": candidat["nom"] if candidat else "",
                    "distance_m": round(distance) if distance is not None else "",
                    "similarite": round(score, 2) if score is not None else "",
                })
            elif candidat:
                grid3_apparies.add(candidat["grid3id"])

        grid3_seuls = len(points) - len(grid3_apparies)
        print(f"{province:<12} {len(villages):>6} {len(points):>7} "
              f"{comptes['sur']:>6} {comptes['probable']:>8} {comptes['absent']:>8} {grid3_seuls:>12}")
        resume.append((province, len(villages), len(points), comptes, grid3_seuls))

    print("─" * 65)
    totaux = {
        "chdc": sum(r[1] for r in resume),
        "grid3": sum(r[2] for r in resume),
        "sur": sum(r[3]["sur"] for r in resume),
        "probable": sum(r[3]["probable"] for r in resume),
        "absent": sum(r[3]["absent"] for r in resume),
        "seuls": sum(r[4] for r in resume),
    }
    print(f"{'TOTAL':<12} {totaux['chdc']:>6} {totaux['grid3']:>7} "
          f"{totaux['sur']:>6} {totaux['probable']:>8} {totaux['absent']:>8} {totaux['seuls']:>12}")

    recouvrement = 100 * (totaux["sur"] + totaux["probable"]) / totaux["chdc"]
    print(f"\nRecouvrement CHDC couvert par GRID3 : {recouvrement:.1f} %")

    if lignes_absents:
        chemin = RACINE / "data" / "rapprochement_chdc_absents.csv"
        with open(chemin, "w", encoding="utf-8-sig", newline="") as fichier:
            writer = csv.DictWriter(fichier, fieldnames=list(lignes_absents[0].keys()))
            writer.writeheader()
            writer.writerows(lignes_absents)
        print(f"Villages CHDC sans correspondance   : {chemin.name} ({len(lignes_absents)} lignes)")


if __name__ == "__main__":
    main()
