#!/usr/bin/env python3
"""
Télécharge les limites des zones de santé et les prépare pour la carte.

Usage :
    python3 scripts/moissonner_zones_sante.py
    python3 scripts/moissonner_zones_sante.py --tolerance 0.002
    python3 scripts/moissonner_zones_sante.py --provinces Ituri Nord-Kivu

Source : GRID3 COD – Health Zones v8.0 (janvier 2026), même millésime que le
référentiel des localités utilisé par moissonner_grid3.py. Le champ
« zonesante » y porte exactement les mêmes valeurs : le filtre de la carte et
les limites affichées désignent donc bien les mêmes entités.
Licence CC BY 4.0 — l'attribution est obligatoire.
519 zones de santé en RDC, 115 sur les 4 provinces suivies.

Les polygones source sont très détaillés (jusqu'à ~7 300 points pour une seule
zone). Ils sont simplifiés (Douglas-Peucker) et leurs coordonnées arrondies,
sans quoi le fichier dépasserait plusieurs mégaoctets. La simplification est
purement visuelle : ces contours ne sont pas une référence sanitaire ou
juridique.

La routine de simplification est celle de preparer_limites.py, importée pour
éviter d'en tenir deux copies.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from preparer_limites import compter_points, simplifier_geometrie  # noqa: E402

SERVICE = (
    "https://services3.arcgis.com/BU6Aadhn6tbBEdyk/arcgis/rest/services/"
    "GRID3_COD_health_zones_v8_0/FeatureServer/0"
)

PROVINCES_DEFAUT = ["Ituri", "Nord-Kivu", "Sud-Kivu", "Tanganyika"]
RACINE = Path(__file__).resolve().parent.parent

# Plus grossier que pour les limites administratives (0,002°) : les contours
# sanitaires ne servent qu'à situer, et le gain de poids est décisif ici.
TOLERANCE_DEFAUT = 0.003

TAILLE_PAGE = 200  # polygones lourds : pages plus petites que pour les points


def slug(texte: str) -> str:
    sans_accent = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return sans_accent.lower().replace(" ", "-")


def interroger(params: dict, tentatives: int = 3) -> dict:
    url = f"{SERVICE}/query?{urllib.parse.urlencode(params)}"
    for essai in range(1, tentatives + 1):
        try:
            with urllib.request.urlopen(url, timeout=180) as reponse:
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


def moissonner(provinces: list) -> list:
    """Télécharge les zones de santé des provinces demandées, page par page."""
    liste = ",".join(f"'{p}'" for p in provinces)
    features = []
    offset = 0
    while True:
        reponse = interroger({
            "where": f"province IN ({liste})",
            "outFields": "province,zonesante,antenne,date,source_acronym",
            "orderByFields": "OBJECTID",
            "resultOffset": offset,
            "resultRecordCount": TAILLE_PAGE,
            "f": "geojson",
        })
        page = reponse.get("features", [])
        if not page:
            break
        features.extend(page)
        print(f"    {len(features)} zones téléchargées…", end="\r", flush=True)
        if len(page) < TAILLE_PAGE:
            break
        offset += TAILLE_PAGE
    print(" " * 50, end="\r")
    return features


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Télécharge les limites des zones de santé (GRID3) pour la carte."
    )
    parser.add_argument("--provinces", nargs="+", default=PROVINCES_DEFAUT,
                        help=f"Provinces à moissonner (défaut : {' '.join(PROVINCES_DEFAUT)})")
    parser.add_argument("--tolerance", type=float, default=TOLERANCE_DEFAUT,
                        help=f"Tolérance de simplification en degrés (défaut : {TOLERANCE_DEFAUT})")
    args = parser.parse_args()

    print("Source : GRID3 COD – Health Zones v8.0 (CC BY 4.0)")
    print(f"Tolérance de simplification : {args.tolerance}° (≈ {args.tolerance * 111000:.0f} m)\n")

    features = moissonner(args.provinces)
    if not features:
        raise SystemExit(
            f"Aucune zone de santé trouvée pour : {', '.join(args.provinces)}\n"
            "Vérifier l'orthographe des noms de provinces."
        )

    points_avant = sum(compter_points(f["geometry"]) for f in features)
    zones = []
    ignorees = 0
    for feature in features:
        geometrie = simplifier_geometrie(feature["geometry"], args.tolerance)
        if not geometrie:
            ignorees += 1
            continue
        proprietes = feature["properties"]
        zones.append({
            "type": "Feature",
            "geometry": geometrie,
            "properties": {
                "nom": proprietes["zonesante"],
                "province": proprietes["province"],
                "antenne": proprietes.get("antenne"),
            },
        })

    chemin = RACINE / "data" / "zones_sante.geojson"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as fichier:
        json.dump({"type": "FeatureCollection", "features": zones},
                  fichier, ensure_ascii=False, separators=(",", ":"))

    points_apres = sum(compter_points(f["geometry"]) for f in zones)
    reduction = 100 * (1 - points_apres / points_avant) if points_avant else 0
    taille_mo = chemin.stat().st_size / 1_048_576

    print(f"zones téléchargées : {len(features)}")
    if ignorees:
        print(f"zones ignorées     : {ignorees} (contour dégénéré après simplification)")
    print(f"points             : {points_avant} → {points_apres} (−{reduction:.0f} %)")
    print(f"fichier            : {chemin.name} ({taille_mo:.2f} Mo)\n")

    par_province = {}
    for zone in zones:
        par_province[zone["properties"]["province"]] = par_province.get(
            zone["properties"]["province"], 0) + 1
    for province in args.provinces:
        print(f"  {province:<12} {par_province.get(province, 0):>3} zones de santé")


if __name__ == "__main__":
    main()
