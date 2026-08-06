#!/usr/bin/env python3
"""
Convertit l'export mensuel des villages (Excel ou CSV) en GeoJSON pour la carte web.

Usage :
    python3 scripts/convertir_villages.py data_source/Villages_CHDC_2607.xlsx
    python3 scripts/convertir_villages.py export.csv --sortie data/villages.geojson
    python3 scripts/convertir_villages.py export.xlsx --col-lat Y --col-lon X

Formats acceptés : .xlsx, .xls, .csv (encodage UTF-8 ou Latin-1, virgule
décimale tolérée).

Les colonnes de coordonnées sont détectées automatiquement parmi les noms
usuels (Latitude/lat/y, Longitude/lon/lng/x — indifférent à la casse) et
peuvent être forcées avec --col-lat / --col-lon. Toutes les autres colonnes
sont conservées telles quelles et deviennent les attributs disponibles pour
le popup de la carte — aucune modification du script n'est nécessaire si
des colonnes sont ajoutées.

Contrôles effectués :
  - coordonnées manquantes ou non numériques  → ligne rejetée
  - coordonnées hors limites terrestres        → ligne rejetée
  - coordonnées hors de l'emprise RDC          → avertissement (ligne conservée)
  - doublons exacts (même nom + mêmes coords)  → dédoublonnés (première occurrence gardée)

Les lignes rejetées sont écrites dans un fichier *_rejets.csv à côté du
fichier source, avec la raison du rejet, pour correction dans le fichier
d'origine.
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

# Emprise approximative de la RDC, avec une petite marge.
RDC_LAT_MIN, RDC_LAT_MAX = -14.0, 6.0
RDC_LON_MIN, RDC_LON_MAX = 11.0, 32.0

CANDIDATS_LAT = ["lat", "latitude", "y"]
CANDIDATS_LON = ["lon", "lng", "long", "longitude", "x"]
CANDIDATS_NOM = ["nom", "village", "name", "nom_village"]


def lire_fichier(chemin: Path) -> pd.DataFrame:
    suffixe = chemin.suffix.lower()
    if suffixe in (".xlsx", ".xls"):
        df = pd.read_excel(chemin, dtype=str)
    elif suffixe == ".csv":
        for encodage in ("utf-8-sig", "latin-1"):
            try:
                df = pd.read_csv(chemin, dtype=str, encoding=encodage)
                break
            except UnicodeDecodeError:
                continue
        else:
            sys.exit(f"Impossible de lire {chemin} (encodage non reconnu).")
    else:
        sys.exit(f"Format non pris en charge : {suffixe} (attendu : .xlsx, .xls ou .csv)")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def trouver_colonne(colonnes, candidats, forcee, role):
    if forcee:
        if forcee in colonnes:
            return forcee
        sys.exit(f"Colonne « {forcee} » ({role}) absente. Colonnes trouvées : {', '.join(colonnes)}")
    par_minuscule = {c.lower(): c for c in colonnes}
    for candidat in candidats:
        if candidat in par_minuscule:
            return par_minuscule[candidat]
    sys.exit(
        f"Aucune colonne {role} reconnue (cherché : {', '.join(candidats)}).\n"
        f"Colonnes trouvées : {', '.join(colonnes)}\n"
        f"Utilisez --col-lat / --col-lon pour indiquer les bons noms."
    )


def en_nombre(serie: pd.Series) -> pd.Series:
    """Convertit en float en tolérant la virgule décimale et les espaces."""
    return pd.to_numeric(
        serie.astype(str).str.strip().str.replace(",", ".", regex=False),
        errors="coerce",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Convertit un export de villages (Excel/CSV) en GeoJSON.")
    parser.add_argument("fichier_entree", type=Path, help="Chemin du fichier source (.xlsx, .xls ou .csv)")
    parser.add_argument("--sortie", type=Path, default=None,
                        help="Chemin du GeoJSON de sortie (défaut : data/villages.geojson)")
    parser.add_argument("--col-lat", default=None, help="Nom de la colonne latitude (défaut : détection auto)")
    parser.add_argument("--col-lon", default=None, help="Nom de la colonne longitude (défaut : détection auto)")
    parser.add_argument("--col-nom", default=None,
                        help="Colonne du nom de village, utilisée pour le dédoublonnage (défaut : détection auto)")
    args = parser.parse_args()

    if not args.fichier_entree.exists():
        sys.exit(f"Fichier introuvable : {args.fichier_entree}")

    sortie = args.sortie or Path(__file__).resolve().parent.parent / "data" / "villages.geojson"

    df = lire_fichier(args.fichier_entree)
    total = len(df)

    col_lat = trouver_colonne(df.columns, CANDIDATS_LAT, args.col_lat, "latitude")
    col_lon = trouver_colonne(df.columns, CANDIDATS_LON, args.col_lon, "longitude")
    par_minuscule = {c.lower(): c for c in df.columns}
    col_nom = args.col_nom or next(
        (par_minuscule[c] for c in CANDIDATS_NOM if c in par_minuscule), None
    )
    print(f"Colonnes utilisées    : latitude = {col_lat}, longitude = {col_lon}, nom = {col_nom or '(aucune)'}")

    lat = en_nombre(df[col_lat])
    lon = en_nombre(df[col_lon])

    # --- Rejets : coordonnées inutilisables -------------------------------
    raisons = pd.Series("", index=df.index)
    raisons[lat.isna() | lon.isna()] = "coordonnées manquantes ou non numériques"
    hors_monde = (~raisons.astype(bool)) & (
        (lat < -90) | (lat > 90) | (lon < -180) | (lon > 180)
    )
    raisons[hors_monde] = "coordonnées hors limites (lat ±90, lon ±180)"

    rejets = df[raisons.astype(bool)].copy()
    if len(rejets):
        rejets["raison_rejet"] = raisons[raisons.astype(bool)]
        chemin_rejets = args.fichier_entree.with_name(args.fichier_entree.stem + "_rejets.csv")
        rejets.to_csv(chemin_rejets, index=False, encoding="utf-8-sig")

    valides = df[~raisons.astype(bool)].copy()
    valides["_lat"] = lat[valides.index]
    valides["_lon"] = lon[valides.index]

    # --- Avertissement : hors emprise RDC (conservés) ---------------------
    hors_rdc = valides[
        (valides["_lat"] < RDC_LAT_MIN) | (valides["_lat"] > RDC_LAT_MAX)
        | (valides["_lon"] < RDC_LON_MIN) | (valides["_lon"] > RDC_LON_MAX)
    ]

    # --- Dédoublonnage ----------------------------------------------------
    if col_nom:
        cles_doublon = [col_nom, "_lat", "_lon"]
    else:
        cles_doublon = list(valides.columns)
    avant = len(valides)
    valides = valides.drop_duplicates(subset=cles_doublon, keep="first")
    nb_doublons = avant - len(valides)

    # --- Écriture du GeoJSON ---------------------------------------------
    colonnes_attributs = [c for c in df.columns if c not in (col_lat, col_lon)]
    features = []
    for ligne in valides.to_dict("records"):
        proprietes = {
            c: (None if pd.isna(ligne[c]) else ligne[c]) for c in colonnes_attributs
        }
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [round(ligne["_lon"], 6), round(ligne["_lat"], 6)],
            },
            "properties": proprietes,
        })

    sortie.parent.mkdir(parents=True, exist_ok=True)
    with open(sortie, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features},
                  f, ensure_ascii=False, separators=(",", ":"))

    # --- Rapport ----------------------------------------------------------
    taille_mo = sortie.stat().st_size / 1_048_576
    print(f"Lignes lues            : {total}")
    print(f"Villages exportés      : {len(features)}")
    if len(rejets):
        print(f"Lignes rejetées        : {len(rejets)}  → détail dans {chemin_rejets}")
    if nb_doublons:
        print(f"Doublons supprimés     : {nb_doublons}")
    if len(hors_rdc):
        print(f"Hors emprise RDC       : {len(hors_rdc)} (conservés — vérifier ces coordonnées)")
    print(f"Fichier écrit          : {sortie} ({taille_mo:.1f} Mo)")


if __name__ == "__main__":
    main()
