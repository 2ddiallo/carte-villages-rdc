#!/usr/bin/env python3
"""Lecteur minimal de shapefile de points (.shp + .dbf), sans dépendance.

Suffisant pour comparer un gazetteer : géométrie ponctuelle et attributs.
"""

import struct
from pathlib import Path


def lire_dbf(chemin: Path) -> list:
    """Lit un fichier dBASE III et renvoie une liste de dictionnaires."""
    with open(chemin, "rb") as f:
        octets = f.read()

    nb_enreg, debut_donnees, taille_enreg = struct.unpack("<I H H", octets[4:12])

    # Descripteurs de champs : blocs de 32 octets jusqu'au marqueur 0x0D.
    champs = []
    pos = 32
    while octets[pos] != 0x0D:
        bloc = octets[pos:pos + 32]
        nom = bloc[:11].split(b"\x00")[0].decode("latin-1").strip()
        type_champ = chr(bloc[11])
        longueur = bloc[16]
        champs.append((nom, type_champ, longueur))
        pos += 32

    lignes = []
    for i in range(nb_enreg):
        base = debut_donnees + i * taille_enreg
        if octets[base:base + 1] == b"*":      # enregistrement supprimé
            continue
        curseur = base + 1
        ligne = {}
        for nom, type_champ, longueur in champs:
            brut = octets[curseur:curseur + longueur]
            curseur += longueur
            try:
                valeur = brut.decode("utf-8").strip()
            except UnicodeDecodeError:
                valeur = brut.decode("latin-1").strip()
            if type_champ in "NF":
                try:
                    valeur = float(valeur) if valeur else None
                except ValueError:
                    valeur = None
            ligne[nom] = valeur or None
        lignes.append(ligne)
    return lignes


def lire_shp_points(chemin: Path) -> list:
    """Renvoie la liste des (lon, lat) d'un shapefile de points."""
    with open(chemin, "rb") as f:
        octets = f.read()

    points = []
    pos = 100                                   # en-tête fixe
    while pos < len(octets):
        longueur_mots = struct.unpack(">I", octets[pos + 4:pos + 8])[0]
        contenu = pos + 8
        type_forme = struct.unpack("<I", octets[contenu:contenu + 4])[0]
        if type_forme == 1:                     # Point
            x, y = struct.unpack("<dd", octets[contenu + 4:contenu + 20])
            points.append((x, y))
        elif type_forme == 11:                  # PointZ
            x, y = struct.unpack("<dd", octets[contenu + 4:contenu + 20])
            points.append((x, y))
        else:
            points.append(None)                 # géométrie non ponctuelle
        pos = contenu + longueur_mots * 2
    return points


def lire(base: Path) -> list:
    """Assemble attributs et géométrie. `base` est le chemin sans extension."""
    attributs = lire_dbf(base.with_suffix(".dbf"))
    geometries = lire_shp_points(base.with_suffix(".shp"))
    for ligne, point in zip(attributs, geometries):
        ligne["_lon"], ligne["_lat"] = point if point else (None, None)
    return attributs


if __name__ == "__main__":
    import sys
    donnees = lire(Path(sys.argv[1]))
    print(f"{len(donnees)} enregistrements")
    print("colonnes :", [c for c in donnees[0] if not c.startswith('_')])
    for ligne in donnees[:3]:
        print(" ", {k: v for k, v in ligne.items()})
