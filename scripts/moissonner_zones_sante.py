#!/usr/bin/env python3
"""
Télécharge les limites des zones de santé (GRID3) et les prépare pour la carte.

Usage :
    python3 scripts/moissonner_zones_sante.py                 # les 26 provinces
    python3 scripts/moissonner_zones_sante.py --provinces Ituri Nord-Kivu
    python3 scripts/moissonner_zones_sante.py --cache ~/grid3    # garde les téléchargements

Source : GRID3 COD – Health Zones v9.0 (septembre 2026), CC BY 4.0, et les
paquets provinciaux plus récents pour le Nord-Kivu et l'Ituri (voir
`sources_grid3.py`). 519 zones de santé en RDC — la carte sanitaire officielle
du Ministère de la Santé, le même découpage que celui publié par OCHA.
Lecture sans dépendance : voir `lire_geopackage.py`.

Les polygones source sont énormes (plus d'un million de points au total,
jusqu'à ~7 300 pour une seule zone). Ils sont simplifiés plus fortement que les
limites administratives : ces contours ne servent qu'à situer.
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lire_geopackage import lire  # noqa: E402
from preparer_limites import compter_points, simplifier_geometrie  # noqa: E402
from sources_grid3 import VERSION, ajouter_options, cle_province, sources_par_province  # noqa: E402

RACINE = Path(__file__).resolve().parent.parent

# Plus grossier que pour les limites administratives (0,002°) : les contours
# sanitaires ne servent qu'à situer, et le gain de poids est décisif ici.
TOLERANCE_DEFAUT = 0.003

CHAMPS = ["province", "zonesante", "antenne", "date", "source_acronym"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prépare les limites des zones de santé (GRID3) pour la carte."
    )
    ajouter_options(parser)
    parser.add_argument("--tolerance", type=float, default=TOLERANCE_DEFAUT,
                        help=f"Tolérance de simplification en degrés (défaut : {TOLERANCE_DEFAUT})")
    args = parser.parse_args()

    print(f"Source : GRID3 COD – Health Zones {VERSION}, via HDX (CC BY 4.0)")
    print(f"Tolérance de simplification : {args.tolerance}° (≈ {args.tolerance * 111000:.0f} m)\n")

    with tempfile.TemporaryDirectory() as temporaire:
        sources = sources_par_province(
            "health_zones", args.provinces, Path(temporaire), cache=args.cache,
            archive=args.archive, paquets=not args.sans_paquets_provinciaux)
        print()

        zones = []
        points_avant = 0
        ignorees = 0
        par_province = {}

        for province in args.provinces:
            chemin_gpkg, table, _ = sources[cle_province(province)]
            for ligne in lire(chemin_gpkg, CHAMPS, table=table):
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

    points_apres = sum(compter_points(z["geometry"]) for z in zones)
    reduction = 100 * (1 - points_apres / points_avant) if points_avant else 0

    # Toutes les zones vivent dans un seul fichier : avec --provinces, on ne
    # remplace que celles des provinces demandées et l'on garde les autres.
    chemin = RACINE / "data" / "zones_sante.geojson"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    conservees = []
    if chemin.exists():
        demandees = {cle_province(p) for p in args.provinces}
        with open(chemin, encoding="utf-8") as fichier:
            conservees = [z for z in json.load(fichier)["features"]
                          if cle_province(z["properties"].get("province") or "") not in demandees]
    with open(chemin, "w", encoding="utf-8") as fichier:
        json.dump({"type": "FeatureCollection", "features": conservees + zones},
                  fichier, ensure_ascii=False, separators=(",", ":"))

    print()
    print(f"zones retenues : {len(zones)}"
          + (f" (+ {len(conservees)} d'autres provinces, conservées)" if conservees else ""))
    if ignorees:
        print(f"zones ignorées : {ignorees} (contour vide ou dégénéré après simplification)")
    print(f"points         : {points_avant} → {points_apres} (−{reduction:.0f} %)")
    print(f"fichier        : {chemin.name} ({chemin.stat().st_size / 1_048_576:.2f} Mo)")


if __name__ == "__main__":
    main()
