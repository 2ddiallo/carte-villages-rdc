#!/usr/bin/env python3
"""
Construit le référentiel compact que charge la console de contrôle.

Usage :
    python3 scripts/construire_referentiel.py
    python3 scripts/construire_referentiel.py --provinces Ituri Nord-Kivu

La carte de consultation (index.html) lit les GeoJSON de `data/`, lisibles mais
lourds : 26 Mo pour les 26 provinces. La console de contrôle, elle, a besoin de
charger d'un coup la province d'un village proposé *et ses voisines* — un point
près d'une limite doit être comparé aux localités de l'autre côté. Il lui faut
donc un format plus dense.

D'où `ref/` : mêmes localités, réencodées.

  - les valeurs qui se répètent (type, zone de santé, aire de santé,
    territoire) sont remplacées par un indice dans un dictionnaire ;
  - chaque localité devient un tableau de valeurs, sans noms de champs répétés ;
  - les coordonnées sont arrondies à 5 décimales (~1 m).

Le gain est d'environ 3,5×. `ref/index.json` récapitule l'emprise et l'effectif
de chaque province : la console s'en sert pour décider quoi charger, sans
ouvrir les fichiers.

Ce que ce script ne fait PAS : calculer des clés phonétiques. Elles sont
recalculées dans le navigateur au chargement (quelques millisecondes pour une
province), pour que les règles de comparaison des noms n'existent qu'à un seul
endroit — `js/noms.js`. Une deuxième implémentation en Python finirait par
diverger, ce qui est précisément le problème que ce projet cherche à résoudre.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from moissonner_grid3 import PROVINCES_RDC, slug  # noqa: E402
from sources_grid3 import VERSION  # noqa: E402

RACINE = Path(__file__).resolve().parent.parent

# Ordre des valeurs dans chaque tableau de localité. La console lit cet ordre
# depuis le fichier lui-même (clé « colonnes ») : le changer ici ne casse rien.
COLONNES = ["id", "nom", "alt", "lat", "lon", "type", "zs", "as", "terr", "prec"]

SOURCE = f"GRID3 COD – Settlement Names {VERSION} (CC BY 4.0)"

DECIMALES = 5  # ≈ 1 m, très au-delà de la précision des relevés eux-mêmes


class Dictionnaire:
    """Attribue un indice stable à chaque valeur distincte rencontrée."""

    def __init__(self):
        self.valeurs = []
        self._indices = {}

    def indice(self, valeur):
        if valeur in (None, ""):
            return -1
        if valeur not in self._indices:
            self._indices[valeur] = len(self.valeurs)
            self.valeurs.append(valeur)
        return self._indices[valeur]


def construire_province(chemin: Path, province: str) -> dict:
    with open(chemin, encoding="utf-8") as fichier:
        features = json.load(fichier)["features"]

    types, zones, aires, territoires = (Dictionnaire() for _ in range(4))
    points = []
    lat_min = lon_min = float("inf")
    lat_max = lon_max = float("-inf")
    sans_nom = 0

    for feature in features:
        lon, lat = feature["geometry"]["coordinates"]
        proprietes = feature["properties"]
        nom = proprietes.get("localite") or ""
        if not nom:
            sans_nom += 1

        lat_min, lat_max = min(lat_min, lat), max(lat_max, lat)
        lon_min, lon_max = min(lon_min, lon), max(lon_max, lon)

        precision = proprietes.get("precision_")
        points.append([
            proprietes.get("grid3id") or "",
            nom,
            proprietes.get("localite_alt") or "",
            round(lat, DECIMALES),
            round(lon, DECIMALES),
            types.indice(proprietes.get("localitetype")),
            zones.indice(proprietes.get("zonesante")),
            aires.indice(proprietes.get("airesante")),
            territoires.indice(proprietes.get("territoire")),
            round(precision, 1) if isinstance(precision, (int, float)) else None,
        ])

    return {
        "province": province,
        "source": SOURCE,
        "colonnes": COLONNES,
        "types": types.valeurs,
        "zs": zones.valeurs,
        "as": aires.valeurs,
        "terr": territoires.valeurs,
        "bbox": [round(lon_min, DECIMALES), round(lat_min, DECIMALES),
                 round(lon_max, DECIMALES), round(lat_max, DECIMALES)],
        "points": points,
        "_sans_nom": sans_nom,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Construit le référentiel compact des localités pour la console de contrôle."
    )
    parser.add_argument("--provinces", nargs="+", default=PROVINCES_RDC,
                        help="Provinces à encoder (défaut : les 26)")
    args = parser.parse_args()

    dossier = RACINE / "ref"
    dossier.mkdir(parents=True, exist_ok=True)

    index = []
    total_points = 0
    total_source = 0
    total_compact = 0
    total_sans_nom = 0

    for province in args.provinces:
        source = RACINE / "data" / f"grid3_{slug(province)}.geojson"
        if not source.exists():
            sys.exit(
                f"Fichier manquant : {source.relative_to(RACINE)}\n"
                "Lancer d'abord : python3 scripts/moissonner_grid3.py"
            )

        donnees = construire_province(source, province)
        sans_nom = donnees.pop("_sans_nom")

        cible = dossier / f"{slug(province)}.json"
        with open(cible, "w", encoding="utf-8") as fichier:
            json.dump(donnees, fichier, ensure_ascii=False, separators=(",", ":"))

        taille_source = source.stat().st_size
        taille_compacte = cible.stat().st_size
        total_source += taille_source
        total_compact += taille_compacte
        total_points += len(donnees["points"])
        total_sans_nom += sans_nom

        index.append({
            "province": province,
            "fichier": f"ref/{cible.name}",
            "localites": len(donnees["points"]),
            "bbox": donnees["bbox"],
            "octets": taille_compacte,
        })

        alerte = f"   ⚠ {sans_nom} sans nom" if sans_nom else ""
        print(f"{province:<16} {len(donnees['points']):>7} localités   "
              f"{taille_source / 1_048_576:>5.2f} Mo → {taille_compacte / 1_048_576:>4.2f} Mo{alerte}")

    # Avec --provinces, l'index garde les entrées des provinces non retraitées.
    chemin_index = dossier / "index.json"
    if chemin_index.exists():
        traitees = {entree["province"] for entree in index}
        with open(chemin_index, encoding="utf-8") as fichier:
            index += [e for e in json.load(fichier)["provinces"] if e["province"] not in traitees]
        ordre = {p: i for i, p in enumerate(PROVINCES_RDC)}
        index.sort(key=lambda e: ordre.get(e["province"], len(ordre)))
    with open(chemin_index, "w", encoding="utf-8") as fichier:
        json.dump({
            "source": SOURCE,
            "colonnes": COLONNES,
            "provinces": index,
        }, fichier, ensure_ascii=False, indent=1)

    print("─" * 62)
    print(f"{'TOTAL':<16} {total_points:>7} localités   "
          f"{total_source / 1_048_576:>5.2f} Mo → {total_compact / 1_048_576:>4.2f} Mo "
          f"(÷{total_source / total_compact:.1f})")
    if total_sans_nom:
        print(f"\n⚠ {total_sans_nom} localités sans nom : elles restent dans le référentiel "
              "(leur position vaut contrôle de doublon) mais aucun rapprochement de nom "
              "ne pourra les concerner.")
    print(f"\nIndex : {chemin_index.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
