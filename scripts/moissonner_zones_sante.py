#!/usr/bin/env python3
"""
Télécharge les limites des zones de santé (GRID3) et les prépare pour la carte.

Usage :
    python3 scripts/moissonner_zones_sante.py                 # les 26 provinces
    python3 scripts/moissonner_zones_sante.py --provinces Ituri Nord-Kivu
    python3 scripts/moissonner_zones_sante.py --archive /chemin/vers/archive.zip

Source : GRID3 COD – Health Zones v8.0 (janvier 2026), CC BY 4.0.
519 zones de santé en RDC — la carte sanitaire officielle du Ministère de la
Santé, le même découpage que celui publié par OCHA.

⚠ Changement de source (septembre 2026), comme pour moissonner_grid3.py : le
service ArcGIS de GRID3 est devenu privé (« Token Required »). Le jeu v8.0
reste publié en accès libre sur HDX sous forme d'une archive de GeoPackage,
un par province — c'est elle qui est utilisée ici. Voir `lire_geopackage.py`
pour la lecture sans dépendance.

Les polygones source sont énormes (plus d'un million de points au total,
jusqu'à ~7 300 pour une seule zone). Ils sont simplifiés plus fortement que les
limites administratives : ces contours ne servent qu'à situer.
"""

import argparse
import json
import shutil
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lire_geopackage import lire  # noqa: E402
from moissonner_grid3 import PROVINCES_RDC, cle_province  # noqa: E402
from preparer_limites import compter_points, simplifier_geometrie  # noqa: E402

# Archive « GRID3_COD_v8_province_health_zones.zip » du jeu HDX
# « grid3-cod-health-zones-v8-0 » : 26 GeoPackage, 46 Mo.
ARCHIVE_HDX = (
    "https://data.humdata.org/dataset/21bee45b-081e-4029-befa-29f7936612dd/"
    "resource/971c7a38-dbf8-4742-b7fd-94c5c0d41d2e/download/"
    "grid3_cod_v8_province_health_zones.zip"
)

RACINE = Path(__file__).resolve().parent.parent

# Plus grossier que pour les limites administratives (0,002°) : les contours
# sanitaires ne servent qu'à situer, et le gain de poids est décisif ici.
TOLERANCE_DEFAUT = 0.003

CHAMPS = ["province", "zonesante", "antenne", "date", "source_acronym"]


def telecharger_archive(destination: Path) -> Path:
    print("Téléchargement de l'archive des zones de santé depuis HDX (~46 Mo)…")
    try:
        with urllib.request.urlopen(ARCHIVE_HDX, timeout=600) as reponse, \
                open(destination, "wb") as fichier:
            shutil.copyfileobj(reponse, fichier)
    except (urllib.error.URLError, TimeoutError) as erreur:
        sys.exit(
            f"Échec du téléchargement : {erreur}\n"
            "Si le lien a changé, retrouver la ressource « province health zones » sur\n"
            "https://data.humdata.org/dataset/grid3-cod-health-zones-v8-0"
        )
    print(f"    {destination.stat().st_size / 1_048_576:.1f} Mo téléchargés\n")
    return destination


def extraire(archive: Path, dossier: Path) -> dict:
    """Extrait les GeoPackage. Renvoie {clé de province: chemin}."""
    with zipfile.ZipFile(archive) as zip_archive:
        zip_archive.extractall(dossier)
    fichiers = {}
    for chemin in dossier.rglob("*.gpkg"):
        milieu = chemin.stem.removeprefix("GRID3_COD_").removesuffix("_health_zones_v8_0")
        fichiers[cle_province(milieu)] = chemin
    if not fichiers:
        sys.exit(f"Aucun GeoPackage trouvé dans {archive.name} — archive inattendue ?")
    return fichiers


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prépare les limites des zones de santé (GRID3) pour la carte."
    )
    parser.add_argument("--provinces", nargs="+", default=PROVINCES_RDC,
                        help="Provinces à retenir (défaut : les 26)")
    parser.add_argument("--tolerance", type=float, default=TOLERANCE_DEFAUT,
                        help=f"Tolérance de simplification en degrés (défaut : {TOLERANCE_DEFAUT})")
    parser.add_argument("--archive", type=Path, default=None,
                        help="Archive HDX déjà téléchargée (évite de la reprendre)")
    args = parser.parse_args()

    print("Source : GRID3 COD – Health Zones v8.0, via HDX (CC BY 4.0)")
    print(f"Tolérance de simplification : {args.tolerance}° (≈ {args.tolerance * 111000:.0f} m)\n")

    with tempfile.TemporaryDirectory() as temporaire:
        dossier = Path(temporaire)
        archive = args.archive or telecharger_archive(dossier / "health_zones.zip")
        fichiers = extraire(archive, dossier / "gpkg")

        inconnues = [p for p in args.provinces if cle_province(p) not in fichiers]
        if inconnues:
            sys.exit(f"Provinces absentes de l'archive : {', '.join(inconnues)}")

        zones = []
        points_avant = 0
        ignorees = 0
        par_province = {}

        for province in args.provinces:
            for ligne in lire(fichiers[cle_province(province)], CHAMPS):
                brute = ligne.get("geometrie")
                if not brute:
                    ignorees += 1
                    continue
                points_avant += compter_points(brute)
                geometrie = simplifier_geometrie(brute, args.tolerance)
                if not geometrie:
                    ignorees += 1
                    continue
                zones.append({
                    "type": "Feature",
                    "geometry": geometrie,
                    "properties": {
                        "nom": ligne.get("zonesante"),
                        "province": ligne.get("province") or province,
                        "antenne": ligne.get("antenne"),
                    },
                })
                par_province[province] = par_province.get(province, 0) + 1
            print(f"    {province:<16} {par_province.get(province, 0):>3} zones", flush=True)

    if not zones:
        sys.exit("Aucune zone de santé retenue — vérifier les noms de provinces.")

    chemin = RACINE / "data" / "zones_sante.geojson"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as fichier:
        json.dump({"type": "FeatureCollection", "features": zones},
                  fichier, ensure_ascii=False, separators=(",", ":"))

    points_apres = sum(compter_points(z["geometry"]) for z in zones)
    reduction = 100 * (1 - points_apres / points_avant) if points_avant else 0

    print()
    print(f"zones retenues : {len(zones)}")
    if ignorees:
        print(f"zones ignorées : {ignorees} (contour vide ou dégénéré après simplification)")
    print(f"points         : {points_avant} → {points_apres} (−{reduction:.0f} %)")
    print(f"fichier        : {chemin.name} ({chemin.stat().st_size / 1_048_576:.2f} Mo)")


if __name__ == "__main__":
    main()
