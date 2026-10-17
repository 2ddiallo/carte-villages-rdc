#!/usr/bin/env python3
"""
Télécharge le référentiel des localités GRID3 et l'écrit en GeoJSON, une
province par fichier.

Usage :
    python3 scripts/moissonner_grid3.py                    # les 26 provinces
    python3 scripts/moissonner_grid3.py --provinces Ituri Nord-Kivu
    python3 scripts/moissonner_grid3.py --cache ~/grid3    # garde les téléchargements

Source : GRID3 COD – Settlement Names v9.0 (septembre 2026), produit par
CIESIN/Columbia avec le Ministère de la Santé. Pour le Nord-Kivu et l'Ituri,
les paquets provinciaux de GRID3, plus récents, remplacent la v9.0 (voir
`sources_grid3.py`). Licence CC BY 4.0 — l'attribution est obligatoire sur la
carte. 128 239 localités nommées sur toute la RDC.

Historique des sources
──────────────────────
Jusqu'en août 2026, ce script interrogeait le service ArcGIS de GRID3, devenu
privé (« Token Required », code 499). Il a alors basculé sur les archives de
GeoPackage publiées sur HDX (v8.0), puis sur la v9.0 quand HDX a retiré la
v8.0 en octobre 2026. Les adresses vivent toutes dans `sources_grid3.py`.

Lecture des GeoPackage
──────────────────────
Un GeoPackage est une base SQLite. Les tables portent une colonne `lat` et une
colonne `lon` en plus de la géométrie : on lit donc les coordonnées directement
en SQL, sans décoder le format binaire et sans aucune bibliothèque
géographique. Le module `sqlite3` de la bibliothèque standard suffit — comme
`lire_shapefile.py` évite déjà une dépendance pour lire les shapefiles d'OCHA.

Contrôles effectués :
  - coordonnées manquantes ou hors emprise RDC → point rejeté
  - identifiant grid3id dupliqué               → dédoublonné (1re occurrence)
  - type de localité mal orthographié à la source (« Quaŕtier ») → corrigé
  - propriétés vides                           → retirées (allège le fichier)
"""

import argparse
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# PROVINCES_RDC, slug et cle_province restent importables depuis ce module :
# plusieurs scripts les y prennent.
from sources_grid3 import (  # noqa: E402
    PROVINCES_RDC, VERSION, ajouter_options, cle_province, slug, sources_par_province,
)

# Colonnes lues dans le GeoPackage → nom de la propriété écrite en GeoJSON.
# La colonne s'appelle « precision » dans le GeoPackage et s'appelait
# « precision_ » dans le service ArcGIS. On garde « precision_ » en sortie :
# c'est ce nom que le bloc CONFIG d'index.html attend.
CHAMPS = {
    "province": "province",
    "zonesante": "zonesante",
    "airesante": "airesante",
    "localite": "localite",
    "localitetype": "localitetype",
    "localite_alt": "localite_alt",
    "enclav": "enclav",
    "source_acronym": "source_acronym",
    "date": "date",
    "precision": "precision_",
    "precision_": "precision_",   # orthographe des paquets provinciaux
    "grid3id": "grid3id",
}

# Emprise approximative de la RDC, avec une petite marge (même que convertir_villages.py).
RDC_LAT_MIN, RDC_LAT_MAX = -14.0, 6.0
RDC_LON_MIN, RDC_LON_MAX = 11.0, 32.0

# Corrections des valeurs mal orthographiées dans les données source.
CORRECTIONS_TYPE = {"Quaŕtier": "Quartier"}


def lire_geopackage(chemin: Path, table: str = None, champs: dict = CHAMPS) -> list:
    """Lit une table de points (lat/lon en colonnes). Renvoie une liste de dictionnaires.

    `table` : à préciser pour un paquet provincial (plusieurs tables).
    """
    connexion = sqlite3.connect(f"file:{chemin}?mode=ro", uri=True)
    try:
        if table is None:
            tables = [ligne[0] for ligne in connexion.execute(
                "SELECT table_name FROM gpkg_contents WHERE data_type = 'features'"
            )]
            if not tables:
                sys.exit(f"{chemin.name} : aucune table de données.")
            table = tables[0]

        colonnes = [ligne[1] for ligne in connexion.execute(f'PRAGMA table_info("{table}")')]
        manquantes = [c for c in ("lat", "lon") if c not in colonnes]
        if manquantes:
            sys.exit(f"{chemin.name} ({table}) : colonnes {manquantes} absentes — format inattendu.")

        lues = ["lat", "lon"] + [c for c in champs if c in colonnes and c not in ("lat", "lon")]
        requete = 'SELECT "%s" FROM "%s"' % ('","'.join(lues), table)
        return [dict(zip(lues, ligne)) for ligne in connexion.execute(requete)]
    finally:
        connexion.close()


def nettoyer(lignes: list) -> tuple:
    """Valide, dédoublonne et allège. Renvoie (features, rejets, doublons)."""
    features = []
    rejets = 0
    vus = set()
    doublons = 0

    for ligne in lignes:
        lat, lon = ligne.get("lat"), ligne.get("lon")
        if lat is None or lon is None:
            rejets += 1
            continue
        lat, lon = float(lat), float(lon)
        if not (RDC_LAT_MIN <= lat <= RDC_LAT_MAX and RDC_LON_MIN <= lon <= RDC_LON_MAX):
            rejets += 1
            continue

        identifiant = ligne.get("grid3id")
        if identifiant:
            if identifiant in vus:
                doublons += 1
                continue
            vus.add(identifiant)

        proprietes = {}
        for colonne, propriete in CHAMPS.items():
            valeur = ligne.get(colonne)
            if valeur in (None, ""):
                continue          # propriété vide : à 25 000 points, cela pèse
            if colonne == "localitetype":
                valeur = CORRECTIONS_TYPE.get(valeur, valeur)
            proprietes[propriete] = valeur

        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
            "properties": proprietes,
        })

    return features, rejets, doublons


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Télécharge le référentiel des localités GRID3 (RDC) en GeoJSON."
    )
    ajouter_options(parser)
    parser.add_argument("--sortie", type=Path, default=None,
                        help="Dossier de sortie (défaut : data/)")
    args = parser.parse_args()

    dossier_sortie = args.sortie or Path(__file__).resolve().parent.parent / "data"
    dossier_sortie.mkdir(parents=True, exist_ok=True)

    print(f"Source : GRID3 COD – Settlement Names {VERSION}, via HDX (CC BY 4.0)\n")

    with tempfile.TemporaryDirectory() as temporaire:
        sources = sources_par_province(
            "settlement_names", args.provinces, Path(temporaire), cache=args.cache,
            archive=args.archive, paquets=not args.sans_paquets_provinciaux)
        print()

        total_ecrit = 0
        resume = []

        for province in args.provinces:
            chemin_gpkg, table, _ = sources[cle_province(province)]
            lignes = lire_geopackage(chemin_gpkg, table)
            features, rejets, doublons = nettoyer(lignes)

            chemin = dossier_sortie / f"grid3_{slug(province)}.geojson"
            with open(chemin, "w", encoding="utf-8") as fichier:
                json.dump({"type": "FeatureCollection", "features": features},
                          fichier, ensure_ascii=False, separators=(",", ":"))

            taille_mo = chemin.stat().st_size / 1_048_576
            ecarts = []
            if rejets:
                ecarts.append(f"{rejets} rejetées")
            if doublons:
                ecarts.append(f"{doublons} doublons")
            if table is not None:
                ecarts.append("paquet provincial")
            detail = f"  ({', '.join(ecarts)})" if ecarts else ""
            print(f"{province:<16} {len(features):>7} localités   {taille_mo:>5.2f} Mo{detail}")

            total_ecrit += len(features)
            resume.append((province, len(features)))

    print("─" * 46)
    print(f"{'TOTAL':<16} {total_ecrit:>7} localités   "
          f"{len(resume)} province{'s' if len(resume) > 1 else ''}")


if __name__ == "__main__":
    main()
