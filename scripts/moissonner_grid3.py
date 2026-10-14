#!/usr/bin/env python3
"""
Télécharge le référentiel des localités GRID3 et l'écrit en GeoJSON, une
province par fichier.

Usage :
    python3 scripts/moissonner_grid3.py                    # les 26 provinces
    python3 scripts/moissonner_grid3.py --provinces Ituri Nord-Kivu
    python3 scripts/moissonner_grid3.py --archive /chemin/vers/archive.zip

Source : GRID3 COD – Settlement Names v8.0 (décembre 2025), produit par
CIESIN/Columbia et WorldPop avec l'INS et le Ministère de la Santé.
Licence CC BY 4.0 — l'attribution est obligatoire sur la carte.
127 942 localités nommées sur toute la RDC.

⚠ Changement de source (septembre 2026)
────────────────────────────────────────
Ce script interrogeait le service ArcGIS de GRID3
(services3.arcgis.com/BU6Aadhn6tbBEdyk). Ce service est devenu privé : toute
requête, même un simple comptage, répond désormais « Token Required »
(code 499). Il n'est plus utilisable sans compte ArcGIS.

Le même jeu v8.0 reste publié en accès libre sur HDX, sous forme d'une archive
de 26 GeoPackage — un par province. C'est cette archive qui est téléchargée
ici. Le contenu est identique (contrôlé : Ituri donne 6 418 localités des deux
côtés, mêmes identifiants) et le fichier de sortie n'a pas changé de forme.

Au passage, cette source est plus robuste : un téléchargement unique de 10 Mo
au lieu de 64 requêtes paginées, pas de dépendance à la disponibilité d'une API.

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
import shutil
import sqlite3
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

# Archive « GRID3_COD_v8_province_settlement_names.zip » du jeu HDX
# « grid3-cod-settlement-names-v8-0 » : 26 GeoPackage, 10,4 Mo.
ARCHIVE_HDX = (
    "https://data.humdata.org/dataset/5b8ce4e9-2525-4f1b-988d-91ab212c9c6b/"
    "resource/4aea8452-198c-40c5-b938-b6a24f160738/download/"
    "grid3_cod_v8_province_settlement_names.zip"
)

PROVINCES_RDC = [
    "Bas-Uele", "Equateur", "Haut-Katanga", "Haut-Lomami", "Haut-Uele", "Ituri",
    "Kasaï", "Kasaï-Central", "Kasaï-Oriental", "Kinshasa", "Kongo-Central",
    "Kwango", "Kwilu", "Lomami", "Lualaba", "Mai-Ndombe", "Maniema", "Mongala",
    "Nord-Kivu", "Nord-Ubangi", "Sankuru", "Sud-Kivu", "Sud-Ubangi",
    "Tanganyika", "Tshopo", "Tshuapa",
]

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
    "grid3id": "grid3id",
}

# Emprise approximative de la RDC, avec une petite marge (même que convertir_villages.py).
RDC_LAT_MIN, RDC_LAT_MAX = -14.0, 6.0
RDC_LON_MIN, RDC_LON_MAX = 11.0, 32.0

# Corrections des valeurs mal orthographiées dans les données source.
CORRECTIONS_TYPE = {"Quaŕtier": "Quartier"}


def slug(texte: str) -> str:
    """« Nord-Kivu » → « nord-kivu », pour les noms de fichiers."""
    sans_accent = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return sans_accent.lower().replace(" ", "-")


def cle_province(nom: str) -> str:
    """Clé de comparaison tolérante aux variantes d'écriture d'une province.

    « Kasaï-Central », « Kasai Central » et « kasaicentral » se rejoignent.
    """
    sans_accent = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode()
    return sans_accent.lower().replace("-", "").replace(" ", "").replace("'", "")


def telecharger_archive(destination: Path) -> Path:
    """Télécharge l'archive des GeoPackage depuis HDX."""
    print("Téléchargement de l'archive GRID3 depuis HDX (~10 Mo)…")
    try:
        with urllib.request.urlopen(ARCHIVE_HDX, timeout=300) as reponse, \
                open(destination, "wb") as fichier:
            shutil.copyfileobj(reponse, fichier)
    except (urllib.error.URLError, TimeoutError) as erreur:
        sys.exit(
            f"Échec du téléchargement : {erreur}\n"
            "Si le lien a changé, retrouver la ressource « province settlement names » sur\n"
            "https://data.humdata.org/dataset/grid3-cod-settlement-names-v8-0"
        )
    print(f"    {destination.stat().st_size / 1_048_576:.1f} Mo téléchargés\n")
    return destination


def extraire(archive: Path, dossier: Path) -> dict:
    """Extrait les GeoPackage. Renvoie {clé de province: chemin du fichier}."""
    with zipfile.ZipFile(archive) as zip_archive:
        zip_archive.extractall(dossier)

    fichiers = {}
    for chemin in dossier.rglob("*.gpkg"):
        # « GRID3_COD_Kasaï-Central_settlement_names_v8_0.gpkg » → « Kasaï-Central »
        milieu = chemin.stem.removeprefix("GRID3_COD_").removesuffix("_settlement_names_v8_0")
        fichiers[cle_province(milieu)] = chemin
    if not fichiers:
        sys.exit(f"Aucun GeoPackage trouvé dans {archive.name} — archive inattendue ?")
    return fichiers


def lire_geopackage(chemin: Path) -> list:
    """Lit une table de localités. Renvoie une liste de dictionnaires."""
    connexion = sqlite3.connect(f"file:{chemin}?mode=ro", uri=True)
    try:
        tables = [ligne[0] for ligne in connexion.execute(
            "SELECT table_name FROM gpkg_contents WHERE data_type = 'features'"
        )]
        if not tables:
            sys.exit(f"{chemin.name} : aucune table de données.")

        colonnes = [ligne[1] for ligne in connexion.execute(f'PRAGMA table_info("{tables[0]}")')]
        manquantes = [c for c in ("lat", "lon") if c not in colonnes]
        if manquantes:
            sys.exit(f"{chemin.name} : colonnes {manquantes} absentes — format inattendu.")

        lues = ["lat", "lon"] + [c for c in CHAMPS if c in colonnes]
        requete = 'SELECT "%s" FROM "%s"' % ('","'.join(lues), tables[0])
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
    parser.add_argument("--provinces", nargs="+", default=PROVINCES_RDC,
                        help="Provinces à écrire (défaut : les 26)")
    parser.add_argument("--sortie", type=Path, default=None,
                        help="Dossier de sortie (défaut : data/)")
    parser.add_argument("--archive", type=Path, default=None,
                        help="Archive HDX déjà téléchargée (évite de la reprendre)")
    args = parser.parse_args()

    dossier_sortie = args.sortie or Path(__file__).resolve().parent.parent / "data"
    dossier_sortie.mkdir(parents=True, exist_ok=True)

    print("Source : GRID3 COD – Settlement Names v8.0, via HDX (CC BY 4.0)\n")

    with tempfile.TemporaryDirectory() as temporaire:
        dossier = Path(temporaire)
        archive = args.archive or telecharger_archive(dossier / "settlement_names.zip")
        fichiers = extraire(archive, dossier / "gpkg")

        inconnues = [p for p in args.provinces if cle_province(p) not in fichiers]
        if inconnues:
            sys.exit(
                f"Provinces absentes de l'archive : {', '.join(inconnues)}\n"
                f"Orthographes acceptées : {', '.join(PROVINCES_RDC)}"
            )

        total_ecrit = 0
        resume = []

        for province in args.provinces:
            lignes = lire_geopackage(fichiers[cle_province(province)])
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
            detail = f"  ({', '.join(ecarts)})" if ecarts else ""
            print(f"{province:<16} {len(features):>7} localités   {taille_mo:>5.2f} Mo{detail}")

            total_ecrit += len(features)
            resume.append((province, len(features)))

    print("─" * 46)
    print(f"{'TOTAL':<16} {total_ecrit:>7} localités   "
          f"{len(resume)} province{'s' if len(resume) > 1 else ''}")


if __name__ == "__main__":
    main()
