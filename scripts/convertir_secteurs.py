#!/usr/bin/env python3
"""
Reprend les couches coutumières du projet carte-rdc-v2 et les écrit en GeoJSON.

Usage :
    python3 scripts/convertir_secteurs.py
    python3 scripts/convertir_secteurs.py --source /chemin/vers/carte-rdc-v2/data

Produit :
    data/secteurs.geojson     737 secteurs, chefferies et cités (polygones)
    data/groupements.geojson  1 681 chefs-lieux de groupements (points)

Pourquoi ces données-là
───────────────────────
GRID3 et le COD-AB décrivent la RDC selon deux découpages : sanitaire (province
→ zone de santé → aire de santé) et administratif jusqu'au territoire. Ni l'un
ni l'autre ne descend au **secteur / chefferie** ni au **groupement**, qui sont
pourtant le niveau auquel les villages sont désignés sur le terrain — l'export
CHDC nomme d'ailleurs ses villages « X Gr Y », où Y est le groupement.

Aucune limite nationale à jour de ces niveaux n'existe. Le site officiel
rgc.cd est hors service. Ce qui a pu être récupéré, et qui reste ce qu'il y a
de mieux, ce sont deux archives MONUC déjà retraitées dans le projet voisin
carte-rdc-v2 :

  - 737 polygones de collectivités (473 secteurs, 260 chefferies, 4 cités),
    millésime **2010** ;
  - 1 681 chefs-lieux de groupements, millésime **2009**.

⚠ Ces couches sont un **repère**, pas une référence. Le découpage a bougé
depuis. Elles sont affichées avec leur millésime en légende et ne servent
jamais à motiver un verdict dans la console de contrôle.

⚠ Ne pas confondre avec l'admin 3 du COD-AB, qui n'est PAS le secteur mais la
zone de santé (519). La première version de la carte (projet carte-rdc)
étiquetait cette couche « Secteurs et chefferies » : c'était une erreur.

Format d'entrée : les fichiers `data/*.js` de carte-rdc-v2, soit une
affectation JavaScript enveloppant du TopoJSON (secteurs) ou un tableau
compact (groupements). Le TopoJSON est décodé ici, sans dépendance.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from preparer_limites import compter_points, simplifier_geometrie  # noqa: E402

RACINE = Path(__file__).resolve().parent.parent
SOURCE_DEFAUT = RACINE.parent / "carte-rdc-v2" / "data"

DECIMALES = 5

# Même tolérance que les limites administratives : ~220 m, invisible aux zooms
# où ces contours sont consultés, et 2,7 Mo qui tombent sous le mégaoctet.
TOLERANCE_DEFAUT = 0.002


def lire_affectation(chemin: Path, nom: str):
    """Extrait la valeur JSON d'un fichier `window.RDC_DATA["nom"] = …;`."""
    texte = chemin.read_text(encoding="utf-8")
    marqueur = f'"{nom}"]='
    position = texte.find(marqueur)
    if position < 0:
        sys.exit(f"{chemin.name} : affectation « {nom} » introuvable.")
    return json.loads(texte[position + len(marqueur):].rstrip().rstrip(";"))


def decoder_arcs(topologie: dict) -> list:
    """Déquantifie les arcs : deltas entiers → coordonnées en degrés."""
    transformation = topologie.get("transform")
    arcs = []
    for arc in topologie["arcs"]:
        points = []
        x = y = 0
        for delta in arc:
            # Sans transform, les coordonnées sont déjà absolues.
            if transformation:
                x += delta[0]
                y += delta[1]
                points.append([
                    x * transformation["scale"][0] + transformation["translate"][0],
                    y * transformation["scale"][1] + transformation["translate"][1],
                ])
            else:
                points.append([delta[0], delta[1]])
        arcs.append(points)
    return arcs


def assembler_anneau(indices: list, arcs: list) -> list:
    """Un anneau est une suite d'arcs ; un indice négatif signifie « à l'envers »."""
    anneau = []
    for indice in indices:
        if indice >= 0:
            morceau = arcs[indice]
        else:
            # ~i = -i - 1 : la convention TopoJSON pour l'arc inversé.
            morceau = arcs[~indice][::-1]
        # Le dernier point d'un arc est le premier du suivant : on l'écrit une fois.
        anneau.extend(morceau if not anneau else morceau[1:])
    return [[round(x, DECIMALES), round(y, DECIMALES)] for x, y in anneau]


def geometrie_geojson(geometrie: dict, arcs: list):
    if geometrie["type"] == "Polygon":
        return {"type": "Polygon",
                "coordinates": [assembler_anneau(a, arcs) for a in geometrie["arcs"]]}
    if geometrie["type"] == "MultiPolygon":
        return {"type": "MultiPolygon",
                "coordinates": [[assembler_anneau(a, arcs) for a in polygone]
                                for polygone in geometrie["arcs"]]}
    return None


def ecrire(features: list, chemin: Path, libelle: str) -> None:
    with open(chemin, "w", encoding="utf-8") as fichier:
        json.dump({"type": "FeatureCollection", "features": features},
                  fichier, ensure_ascii=False, separators=(",", ":"))
    print(f"{libelle:<38} {len(features):>5} entités   "
          f"{chemin.name} ({chemin.stat().st_size / 1_048_576:.2f} Mo)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convertit les couches coutumières de carte-rdc-v2 en GeoJSON."
    )
    parser.add_argument("--source", type=Path, default=SOURCE_DEFAUT,
                        help=f"Dossier data/ de carte-rdc-v2 (défaut : {SOURCE_DEFAUT})")
    parser.add_argument("--tolerance", type=float, default=TOLERANCE_DEFAUT,
                        help=f"Tolérance de simplification en degrés (défaut : {TOLERANCE_DEFAUT})")
    args = parser.parse_args()

    if not args.source.exists():
        sys.exit(
            f"Dossier introuvable : {args.source}\n"
            "Ces couches proviennent du projet carte-rdc-v2. Indiquer son dossier\n"
            "data/ avec --source, ou récupérer les archives MONUC d'origine."
        )

    sortie = RACINE / "data"
    sortie.mkdir(parents=True, exist_ok=True)

    # --- Secteurs, chefferies et cités (polygones, 2010) ------------------
    topologie = lire_affectation(args.source / "secteurs.js", "secteurs")
    arcs = decoder_arcs(topologie)
    secteurs = []
    ignorees = 0
    points_avant = 0
    for geometrie in topologie["objects"]["data"]["geometries"]:
        brute = geometrie_geojson(geometrie, arcs)
        if not brute:
            ignorees += 1
            continue
        points_avant += compter_points(brute)
        forme = simplifier_geometrie(brute, args.tolerance)
        if not forme:
            ignorees += 1
            continue
        proprietes = geometrie.get("properties", {})
        secteurs.append({
            "type": "Feature",
            "geometry": forme,
            "properties": {
                "nom": proprietes.get("nom"),
                "type": proprietes.get("type"),      # Secteur, Chefferie ou Cité
                "code": proprietes.get("code"),
                "millesime": "2010",
                "source": "Archive MONUC (collectivités)",
            },
        })
    if ignorees:
        print(f"⚠ {ignorees} géométries non gérées ou dégénérées après simplification")
    ecrire(secteurs, sortie / "secteurs.geojson", "Secteurs, chefferies et cités (2010)")
    points_apres = sum(compter_points(s["geometry"]) for s in secteurs)
    print(f"   points : {points_avant} → {points_apres} "
          f"(−{100 * (1 - points_apres / points_avant):.0f} %)")

    types = {}
    for secteur in secteurs:
        types[secteur["properties"]["type"]] = types.get(secteur["properties"]["type"], 0) + 1
    print("   " + ", ".join(f"{nombre} {libelle.lower()}{'s' if nombre > 1 else ''}"
                            for libelle, nombre in sorted(types.items())))

    # --- Chefs-lieux de groupements (points, 2009) ------------------------
    # Format compact de carte-rdc-v2 : [nom, territoire, secteur, longitude, latitude].
    brut = lire_affectation(args.source / "groupements.js", "groupements")
    groupements = []
    for nom, territoire, secteur, lon, lat in brut:
        groupements.append({
            "type": "Feature",
            "geometry": {"type": "Point",
                         "coordinates": [round(lon, DECIMALES), round(lat, DECIMALES)]},
            "properties": {
                "nom": nom,
                "territoire": territoire,
                "secteur": secteur,
                "millesime": "2009",
                "source": "Archive MONUC (groupements)",
            },
        })
    ecrire(groupements, sortie / "groupements.geojson", "Chefs-lieux de groupements (2009)")

    print("\n⚠ Millésimes 2009-2010 : ces deux couches situent, elles ne font pas foi.")


if __name__ == "__main__":
    main()
