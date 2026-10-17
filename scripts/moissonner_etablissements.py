#!/usr/bin/env python3
"""
Télécharge les établissements de santé GRID3 et les écrit en GeoJSON, une
province par fichier (data/etablissements_<province>.geojson).

Usage :
    python3 scripts/moissonner_etablissements.py
    python3 scripts/moissonner_etablissements.py --provinces Ituri Nord-Kivu
    python3 scripts/moissonner_etablissements.py --cache ~/grid3

Source : GRID3 COD – Health Facilities v9.0 (septembre 2026), CC BY 4.0, et
les paquets provinciaux plus récents pour le Nord-Kivu et l'Ituri (voir
`sources_grid3.py`). 38 995 établissements : hôpitaux, centres de santé,
postes de santé, sites de soins communautaires, bureaux de zone…

La carte n'en garde que ce qui sert à les situer et à les reconnaître : nom,
type, gestion, zone et aire de santé, site de vaccination fixe, provenance.
Le classement en niveaux (référence, centre, poste…) se fait dans
index.html, à partir du type : la donnée reste celle de GRID3.
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from moissonner_grid3 import RDC_LAT_MAX, RDC_LAT_MIN, RDC_LON_MAX, RDC_LON_MIN, lire_geopackage  # noqa: E402
from sources_grid3 import VERSION, ajouter_options, cle_province, slug, sources_par_province  # noqa: E402

RACINE = Path(__file__).resolve().parent.parent

# Colonne du GeoPackage → propriété écrite en GeoJSON.
CHAMPS = {
    "essnom1": "nom",
    "esstype": "type",
    "categorie": "gestion",
    "province": "province",
    "zonesante": "zonesante",
    "airesante": "airesante",
    "vaccfixe": "vaccfixe",
    "source_acronym": "source_acronym",
    "date": "date",
    "grid3id": "grid3id",
}


def convertir(lignes: list) -> tuple:
    """Lignes du GeoPackage → features GeoJSON. Renvoie (features, rejets, doublons)."""
    features, vus = [], set()
    rejets = doublons = 0
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
        if identifiant in vus:
            doublons += 1
            continue
        vus.add(identifiant)
        proprietes = {propriete: ligne[colonne] for colonne, propriete in CHAMPS.items()
                      if ligne.get(colonne) not in (None, "")}
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
            "properties": proprietes,
        })
    return features, rejets, doublons


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Télécharge les établissements de santé GRID3 (RDC) en GeoJSON."
    )
    ajouter_options(parser)
    args = parser.parse_args()

    print(f"Source : GRID3 COD – Health Facilities {VERSION}, via HDX (CC BY 4.0)\n")

    total = 0
    with tempfile.TemporaryDirectory() as temporaire:
        sources = sources_par_province(
            "health_facilities", args.provinces, Path(temporaire), cache=args.cache,
            archive=args.archive, paquets=not args.sans_paquets_provinciaux)
        print()

        for province in args.provinces:
            chemin_gpkg, table, _ = sources[cle_province(province)]
            colonnes = dict.fromkeys(["lat", "lon", *CHAMPS])
            features, rejets, doublons = convertir(lire_geopackage(chemin_gpkg, table, colonnes))

            chemin = RACINE / "data" / f"etablissements_{slug(province)}.geojson"
            with open(chemin, "w", encoding="utf-8") as fichier:
                json.dump({"type": "FeatureCollection", "features": features},
                          fichier, ensure_ascii=False, separators=(",", ":"))

            ecarts = [texte for texte, n in ((f"{rejets} rejetés", rejets),
                                             (f"{doublons} doublons", doublons),
                                             ("paquet provincial", table is not None)) if n]
            detail = f"  ({', '.join(ecarts)})" if ecarts else ""
            print(f"{province:<16} {len(features):>6} établissements   "
                  f"{chemin.stat().st_size / 1_048_576:>4.2f} Mo{detail}")
            total += len(features)

    print("─" * 50)
    print(f"{'TOTAL':<16} {total:>6} établissements")


if __name__ == "__main__":
    main()
