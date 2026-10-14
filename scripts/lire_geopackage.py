#!/usr/bin/env python3
"""
Lecteur de GeoPackage sans dépendance, sur le modèle de `lire_shapefile.py`.

Un GeoPackage (.gpkg) est une base SQLite : la table de données porte une
colonne par attribut et une colonne de géométrie au format « GeoPackage Binary »
(un petit en-tête, puis du WKB standard). Le module `sqlite3` de la
bibliothèque standard lit la base ; les quelques dizaines de lignes ci-dessous
décodent la géométrie. Aucune installation n'est donc nécessaire, ni GDAL, ni
geopandas — c'est le choix fait dès l'origine sur ce projet pour que les
scripts tournent sur un poste neuf.

Usage :
    from lire_geopackage import table_principale, lire

    table = table_principale(chemin)
    for ligne in lire(chemin, colonnes=["province", "zonesante"]):
        ligne["geometrie"]   # géométrie GeoJSON : {"type": "Polygon", ...}
        ligne["zonesante"]

Limites assumées : géométries 2D en WGS84 (c'est le cas des jeux GRID3). Les
coordonnées Z et M présentes dans le WKB sont lues puis écartées, GeoJSON ne
les portant pas ici.
"""

import sqlite3
import struct
from pathlib import Path

# Types WKB. Le millier indique la présence de Z (1000), M (2000) ou ZM (3000) :
# on le retire pour retrouver le type de base.
WKB_POINT = 1
WKB_LIGNE = 2
WKB_POLYGONE = 3
WKB_MULTIPOINT = 4
WKB_MULTILIGNE = 5
WKB_MULTIPOLYGONE = 6
WKB_COLLECTION = 7

NOMS_GEOJSON = {
    WKB_POINT: "Point",
    WKB_LIGNE: "LineString",
    WKB_POLYGONE: "Polygon",
    WKB_MULTIPOINT: "MultiPoint",
    WKB_MULTILIGNE: "MultiLineString",
    WKB_MULTIPOLYGONE: "MultiPolygon",
}

# Nombre de doubles dans l'enveloppe, selon l'indicateur des drapeaux d'en-tête.
TAILLE_ENVELOPPE = {0: 0, 1: 4, 2: 6, 3: 6, 4: 8}


class GeoPackageIllisible(Exception):
    """Le fichier n'a pas la forme attendue d'un GeoPackage de points ou de polygones."""


def _lire_wkb(donnees: bytes, position: int) -> tuple:
    """Décode une géométrie WKB. Renvoie (géométrie GeoJSON, position suivante)."""
    (ordre,) = struct.unpack_from("<B", donnees, position)
    prefixe = "<" if ordre == 1 else ">"
    (code,) = struct.unpack_from(prefixe + "I", donnees, position + 1)
    position += 5

    dimensions = 2 + (1 if 1000 <= code < 3000 else 0) + (2 if code >= 3000 else 0)
    type_base = code % 1000

    def points(nombre: int, position: int) -> tuple:
        format_lecture = prefixe + "d" * (nombre * dimensions)
        valeurs = struct.unpack_from(format_lecture, donnees, position)
        position += struct.calcsize(format_lecture)
        # Seules les deux premières dimensions (x, y) sont conservées.
        liste = [[valeurs[i], valeurs[i + 1]] for i in range(0, len(valeurs), dimensions)]
        return liste, position

    if type_base == WKB_POINT:
        liste, position = points(1, position)
        return {"type": "Point", "coordinates": liste[0]}, position

    if type_base in (WKB_LIGNE, WKB_MULTIPOINT):
        (nombre,) = struct.unpack_from(prefixe + "I", donnees, position)
        position += 4
        if type_base == WKB_MULTIPOINT:
            # Un MultiPoint est une suite de Points WKB complets, pas de doubles bruts.
            coordonnees = []
            for _ in range(nombre):
                geometrie, position = _lire_wkb(donnees, position)
                coordonnees.append(geometrie["coordinates"])
            return {"type": "MultiPoint", "coordinates": coordonnees}, position
        liste, position = points(nombre, position)
        return {"type": "LineString", "coordinates": liste}, position

    if type_base == WKB_POLYGONE:
        (nombre_anneaux,) = struct.unpack_from(prefixe + "I", donnees, position)
        position += 4
        anneaux = []
        for _ in range(nombre_anneaux):
            (nombre,) = struct.unpack_from(prefixe + "I", donnees, position)
            position += 4
            anneau, position = points(nombre, position)
            anneaux.append(anneau)
        return {"type": "Polygon", "coordinates": anneaux}, position

    if type_base in (WKB_MULTILIGNE, WKB_MULTIPOLYGONE, WKB_COLLECTION):
        (nombre,) = struct.unpack_from(prefixe + "I", donnees, position)
        position += 4
        parties = []
        for _ in range(nombre):
            geometrie, position = _lire_wkb(donnees, position)
            parties.append(geometrie)
        if type_base == WKB_COLLECTION:
            return {"type": "GeometryCollection", "geometries": parties}, position
        return {
            "type": NOMS_GEOJSON[type_base],
            "coordinates": [p["coordinates"] for p in parties],
        }, position

    raise GeoPackageIllisible(f"Type WKB non géré : {code}")


def decoder_geometrie(blob: bytes):
    """Décode une colonne de géométrie GeoPackage. Renvoie None si elle est vide."""
    if not blob or len(blob) < 8 or blob[:2] != b"GP":
        return None

    drapeaux = blob[3]
    prefixe = "<" if drapeaux & 0x01 else ">"
    indicateur = (drapeaux >> 1) & 0x07
    if drapeaux & 0x10:                      # géométrie explicitement vide
        return None
    if indicateur not in TAILLE_ENVELOPPE:
        raise GeoPackageIllisible(f"Indicateur d'enveloppe inconnu : {indicateur}")

    position = 8 + TAILLE_ENVELOPPE[indicateur] * 8
    geometrie, _ = _lire_wkb(blob, position)
    # `prefixe` n'est utile que pour l'en-tête ; le WKB porte son propre ordre.
    del prefixe
    return geometrie


def table_principale(chemin: Path) -> str:
    """Nom de la (première) table de données du GeoPackage."""
    connexion = sqlite3.connect(f"file:{chemin}?mode=ro", uri=True)
    try:
        tables = [ligne[0] for ligne in connexion.execute(
            "SELECT table_name FROM gpkg_contents WHERE data_type = 'features'"
        )]
    finally:
        connexion.close()
    if not tables:
        raise GeoPackageIllisible(f"{Path(chemin).name} : aucune table de données.")
    return tables[0]


def colonnes(chemin: Path, table: str = None) -> list:
    """Liste des colonnes de la table de données."""
    table = table or table_principale(chemin)
    connexion = sqlite3.connect(f"file:{chemin}?mode=ro", uri=True)
    try:
        return [ligne[1] for ligne in connexion.execute(f'PRAGMA table_info("{table}")')]
    finally:
        connexion.close()


def lire(chemin: Path, colonnes_voulues: list = None, geometrie: bool = True):
    """Parcourt la table de données. Produit un dictionnaire par ligne.

    `colonnes_voulues` filtre les attributs (les colonnes absentes sont
    ignorées sans erreur). La géométrie décodée est placée sous la clé
    « geometrie ».
    """
    chemin = Path(chemin)
    table = table_principale(chemin)
    presentes = colonnes(chemin, table)

    connexion = sqlite3.connect(f"file:{chemin}?mode=ro", uri=True)
    try:
        nom_geometrie = None
        if geometrie:
            ligne = connexion.execute(
                "SELECT column_name FROM gpkg_geometry_columns WHERE table_name = ?",
                (table,),
            ).fetchone()
            nom_geometrie = ligne[0] if ligne else None

        attributs = [c for c in (colonnes_voulues or presentes)
                     if c in presentes and c != nom_geometrie]
        lues = attributs + ([nom_geometrie] if nom_geometrie else [])

        requete = 'SELECT "%s" FROM "%s"' % ('","'.join(lues), table)
        for valeurs in connexion.execute(requete):
            resultat = dict(zip(attributs, valeurs))
            if nom_geometrie:
                resultat["geometrie"] = decoder_geometrie(valeurs[-1])
            yield resultat
    finally:
        connexion.close()
