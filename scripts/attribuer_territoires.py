#!/usr/bin/env python3
"""
Ajoute le territoire à chaque localité GRID3, par recoupement géométrique.

Usage :
    python3 scripts/attribuer_territoires.py
    python3 scripts/attribuer_territoires.py --provinces Ituri Maniema

Le référentiel GRID3 est organisé selon le découpage sanitaire (province →
zone de santé → aire de santé) et ne porte aucun champ « territoire ».
L'export CHDC, lui, est organisé par territoire. Pour que le filtre de la
carte s'applique aux deux couches, on attribue ici à chaque point GRID3 le
territoire dont le polygone le contient (COD-AB ADM2).

Le test est un lancer de rayon (ray casting), avec les trous des polygones
pris en compte. Les contours utilisés sont ceux, simplifiés, de
data/territoires.geojson : à moins de ~220 m d'une limite, l'attribution
peut basculer sur le territoire voisin. C'est sans effet pour un filtre
d'affichage, mais ces valeurs ne sont pas une source administrative.

À relancer après chaque exécution de moissonner_grid3.py ou de
preparer_limites.py. Le champ ajouté est « territoire ».
"""

import argparse
import json
import unicodedata
from pathlib import Path

PROVINCES_DEFAUT = ["Ituri", "Nord-Kivu", "Sud-Kivu", "Tanganyika"]
RACINE = Path(__file__).resolve().parent.parent


def slug(texte: str) -> str:
    sans_accent = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return sans_accent.lower().replace(" ", "-")


def cle_province(nom: str) -> str:
    """Comparaison tolérante aux variantes d'écriture entre sources.

    GRID3 écrit « Mai-Ndombe », COD-AB « Maï-Ndombe » : sans cette
    normalisation, aucun territoire ne serait rattaché à cette province.
    """
    sans_accent = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode()
    return sans_accent.lower().replace("-", "").replace(" ", "").replace("'", "")


def anneaux_polygones(geometrie: dict) -> list:
    """Normalise Polygon / MultiPolygon en une liste de polygones (1er anneau = contour)."""
    if geometrie["type"] == "Polygon":
        return [geometrie["coordinates"]]
    if geometrie["type"] == "MultiPolygon":
        return geometrie["coordinates"]
    return []


def bbox(polygone: list) -> tuple:
    contour = polygone[0]
    xs = [p[0] for p in contour]
    ys = [p[1] for p in contour]
    return min(xs), min(ys), max(xs), max(ys)


def dans_anneau(x: float, y: float, anneau: list) -> bool:
    """Lancer de rayon horizontal : compte les croisements avec les segments."""
    dedans = False
    n = len(anneau)
    j = n - 1
    for i in range(n):
        xi, yi = anneau[i]
        xj, yj = anneau[j]
        if (yi > y) != (yj > y):
            # Abscisse de l'intersection du segment avec l'horizontale passant par y.
            x_intersection = xi + (y - yi) * (xj - xi) / (yj - yi)
            if x < x_intersection:
                dedans = not dedans
        j = i
    return dedans


def dans_polygone(x: float, y: float, polygone: list) -> bool:
    if not dans_anneau(x, y, polygone[0]):
        return False
    # Les anneaux suivants sont des trous : un point dedans est hors du polygone.
    return not any(dans_anneau(x, y, trou) for trou in polygone[1:])


def charger_territoires() -> list:
    chemin = RACINE / "data" / "territoires.geojson"
    if not chemin.exists():
        raise SystemExit(
            f"Fichier manquant : {chemin}\n"
            "Lancer d'abord : python3 scripts/preparer_limites.py"
        )
    with open(chemin, encoding="utf-8") as fichier:
        donnees = json.load(fichier)

    territoires = []
    for feature in donnees["features"]:
        proprietes = feature["properties"]
        for polygone in anneaux_polygones(feature["geometry"]):
            territoires.append({
                "nom": proprietes["nom"],
                "province": proprietes["province"],
                "polygone": polygone,
                "bbox": bbox(polygone),
            })
    return territoires


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Attribue son territoire à chaque localité GRID3."
    )
    parser.add_argument("--provinces", nargs="+", default=PROVINCES_DEFAUT,
                        help=f"Provinces à traiter (défaut : {' '.join(PROVINCES_DEFAUT)})")
    args = parser.parse_args()

    territoires = charger_territoires()
    print(f"{len(territoires)} polygones de territoires chargés\n")

    total_attribues = 0
    total_points = 0

    for province in args.provinces:
        chemin = RACINE / "data" / f"grid3_{slug(province)}.geojson"
        if not chemin.exists():
            raise SystemExit(
                f"Fichier manquant : {chemin}\n"
                "Lancer d'abord : python3 scripts/moissonner_grid3.py"
            )
        with open(chemin, encoding="utf-8") as fichier:
            donnees = json.load(fichier)

        # On ne teste que les territoires de la province concernée.
        candidats = [t for t in territoires
                     if cle_province(t["province"]) == cle_province(province)]
        if not candidats:
            print(f"{province:<14} ⚠ aucun territoire dans territoires.geojson — "
                  f"relancer preparer_limites.py avec cette province")
            continue
        attribues = 0

        for feature in donnees["features"]:
            x, y = feature["geometry"]["coordinates"]
            for territoire in candidats:
                x0, y0, x1, y1 = territoire["bbox"]
                if not (x0 <= x <= x1 and y0 <= y <= y1):
                    continue
                if dans_polygone(x, y, territoire["polygone"]):
                    feature["properties"]["territoire"] = territoire["nom"]
                    attribues += 1
                    break

        with open(chemin, "w", encoding="utf-8") as fichier:
            json.dump(donnees, fichier, ensure_ascii=False, separators=(",", ":"))

        nombre = len(donnees["features"])
        sans = nombre - attribues
        print(f"{province:<12} {attribues:>6} / {nombre:<6} attribués"
              + (f"   ({sans} hors limites)" if sans else ""))
        total_attribues += attribues
        total_points += nombre

    print(f"\n{'TOTAL':<12} {total_attribues:>6} / {total_points:<6} "
          f"({100 * total_attribues / total_points:.1f} %)")


if __name__ == "__main__":
    main()
