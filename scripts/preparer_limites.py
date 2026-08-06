#!/usr/bin/env python3
"""
Télécharge les limites administratives officielles de la RDC et les prépare
pour la carte : provinces (ADM1) et territoires (ADM2).

Usage :
    python3 scripts/preparer_limites.py
    python3 scripts/preparer_limites.py --tolerance 0.001
    python3 scripts/preparer_limites.py --provinces Ituri Nord-Kivu

Source : Common Operational Dataset – Administrative Boundaries (COD-AB),
OCHA Field Information Services Section, mise à jour du 16 avril 2026.
Licence CC BY-IGO — l'attribution est obligatoire sur la carte.
26 provinces (ADM1), 164 territoires (ADM2).

Remplace le fichier geoBoundaries utilisé jusqu'ici : COD-AB est le jeu de
référence humanitaire pour la RDC, il porte les codes officiels (pcode) et
descend au territoire, ce que geoBoundaries ne fournissait pas.

Les fichiers source pèsent 4 à 10 Mo par niveau : les contours sont
simplifiés (Douglas-Peucker) et les coordonnées arrondies pour que la carte
reste légère. La simplification est purement visuelle — ces contours ne
doivent pas servir de référence juridique ou de calcul de surface.
"""

import argparse
import json
import math
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ARCHIVE_COD_AB = (
    "https://data.humdata.org/dataset/f42132b9-8cc6-4201-b020-9259c56e8868/"
    "resource/97260e2b-65b1-41e3-aef2-fb0e6874e406/download/cod_admin_boundaries.geojson.zip"
)

PROVINCES_DEFAUT = ["Ituri", "Nord-Kivu", "Sud-Kivu", "Tanganyika"]

RACINE = Path(__file__).resolve().parent.parent

# 0,002° ≈ 220 m à l'équateur : invisible au zoom province, divise le poids par ~10.
TOLERANCE_DEFAUT = 0.002
DECIMALES = 5  # ≈ 1 m


def distance_point_segment(point, debut, fin) -> float:
    """Distance perpendiculaire d'un point à un segment, en degrés."""
    (x, y), (x1, y1), (x2, y2) = point, debut, fin
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x - x1, y - y1)
    # Projection du point sur le segment, bornée à [0, 1].
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))


def douglas_peucker(points: list, tolerance: float) -> list:
    """Simplifie une ligne en conservant ses points caractéristiques.

    Implémentation itérative : les anneaux administratifs comptent parfois
    plus de 100 000 points, ce qui ferait exploser la pile en récursif.
    """
    if len(points) < 3:
        return points
    garder = [False] * len(points)
    garder[0] = garder[-1] = True
    pile = [(0, len(points) - 1)]

    while pile:
        debut, fin = pile.pop()
        distance_max, indice_max = 0.0, None
        for i in range(debut + 1, fin):
            distance = distance_point_segment(points[i], points[debut], points[fin])
            if distance > distance_max:
                distance_max, indice_max = distance, i
        if indice_max is not None and distance_max > tolerance:
            garder[indice_max] = True
            pile.append((debut, indice_max))
            pile.append((indice_max, fin))

    return [p for p, g in zip(points, garder) if g]


def simplifier_anneau(anneau: list, tolerance: float) -> list:
    """Simplifie un anneau fermé et le referme. Renvoie [] s'il devient dégénéré."""
    simplifie = douglas_peucker(anneau, tolerance)
    if len(simplifie) < 4:
        return []
    if simplifie[0] != simplifie[-1]:
        simplifie.append(simplifie[0])
    return [[round(x, DECIMALES), round(y, DECIMALES)] for x, y in simplifie]


def simplifier_geometrie(geometrie: dict, tolerance: float) -> dict:
    """Simplifie un Polygon ou un MultiPolygon."""
    type_geometrie = geometrie["type"]

    if type_geometrie == "Polygon":
        anneaux = [a for a in (simplifier_anneau(r, tolerance) for r in geometrie["coordinates"]) if a]
        return {"type": "Polygon", "coordinates": anneaux} if anneaux else None

    if type_geometrie == "MultiPolygon":
        polygones = []
        for polygone in geometrie["coordinates"]:
            anneaux = [a for a in (simplifier_anneau(r, tolerance) for r in polygone) if a]
            if anneaux:
                polygones.append(anneaux)
        return {"type": "MultiPolygon", "coordinates": polygones} if polygones else None

    return geometrie


def compter_points(geometrie: dict) -> int:
    if geometrie is None:
        return 0
    if geometrie["type"] == "Polygon":
        return sum(len(anneau) for anneau in geometrie["coordinates"])
    if geometrie["type"] == "MultiPolygon":
        return sum(len(anneau) for polygone in geometrie["coordinates"] for anneau in polygone)
    return 0


def telecharger_archive(dossier: Path) -> Path:
    """Télécharge l'archive COD-AB et extrait les niveaux ADM1 et ADM2."""
    archive = dossier / "cod_admin_boundaries.geojson.zip"
    print("Téléchargement du COD-AB depuis HDX (~24 Mo)…")
    with urllib.request.urlopen(ARCHIVE_COD_AB, timeout=300) as reponse, \
            open(archive, "wb") as fichier:
        shutil.copyfileobj(reponse, fichier)
    with zipfile.ZipFile(archive) as zip_archive:
        zip_archive.extract("cod_admin1.geojson", dossier)
        zip_archive.extract("cod_admin2.geojson", dossier)
    print(f"    {archive.stat().st_size / 1_048_576:.1f} Mo téléchargés\n")
    return dossier


def ecrire(features: list, chemin: Path, libelle: str, points_avant: int) -> None:
    with open(chemin, "w", encoding="utf-8") as fichier:
        json.dump({"type": "FeatureCollection", "features": features},
                  fichier, ensure_ascii=False, separators=(",", ":"))
    points_apres = sum(compter_points(f["geometry"]) for f in features)
    taille_mo = chemin.stat().st_size / 1_048_576
    reduction = 100 * (1 - points_apres / points_avant) if points_avant else 0
    print(f"{libelle}")
    print(f"    entités          : {len(features)}")
    print(f"    points           : {points_avant} → {points_apres} (−{reduction:.0f} %)")
    print(f"    fichier          : {chemin.name} ({taille_mo:.2f} Mo)\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prépare les limites administratives COD-AB (RDC) pour la carte."
    )
    parser.add_argument("--provinces", nargs="+", default=PROVINCES_DEFAUT,
                        help="Provinces dont on garde les territoires "
                             f"(défaut : {' '.join(PROVINCES_DEFAUT)})")
    parser.add_argument("--tolerance", type=float, default=TOLERANCE_DEFAUT,
                        help=f"Tolérance de simplification en degrés (défaut : {TOLERANCE_DEFAUT})")
    parser.add_argument("--source", type=Path, default=None,
                        help="Dossier contenant déjà cod_admin1/2.geojson (évite le téléchargement)")
    args = parser.parse_args()

    dossier_sortie = RACINE / "data"
    dossier_sortie.mkdir(parents=True, exist_ok=True)

    print("Source : COD-AB, OCHA FISS, 16 avril 2026 (CC BY-IGO)")
    print(f"Tolérance de simplification : {args.tolerance}° (≈ {args.tolerance * 111000:.0f} m)\n")

    with tempfile.TemporaryDirectory() as temporaire:
        dossier = args.source or telecharger_archive(Path(temporaire))

        # --- Provinces (ADM1) : les 26, pour garder le contexte national ---
        with open(dossier / "cod_admin1.geojson", encoding="utf-8") as fichier:
            adm1 = json.load(fichier)
        points_avant = sum(compter_points(f["geometry"]) for f in adm1["features"])
        provinces = []
        for feature in adm1["features"]:
            geometrie = simplifier_geometrie(feature["geometry"], args.tolerance)
            if geometrie:
                provinces.append({
                    "type": "Feature",
                    "geometry": geometrie,
                    "properties": {
                        "nom": feature["properties"]["adm1_name"],
                        "pcode": feature["properties"]["adm1_pcode"],
                    },
                })
        ecrire(provinces, dossier_sortie / "provinces.geojson", "Provinces (ADM1)", points_avant)

        # --- Territoires (ADM2) : seulement les provinces demandées ---------
        with open(dossier / "cod_admin2.geojson", encoding="utf-8") as fichier:
            adm2 = json.load(fichier)
        retenus = [f for f in adm2["features"]
                   if f["properties"]["adm1_name"] in args.provinces]
        if not retenus:
            raise SystemExit(
                f"Aucun territoire trouvé pour : {', '.join(args.provinces)}\n"
                "Vérifier l'orthographe des noms de provinces."
            )
        points_avant = sum(compter_points(f["geometry"]) for f in retenus)
        territoires = []
        for feature in retenus:
            geometrie = simplifier_geometrie(feature["geometry"], args.tolerance)
            if geometrie:
                territoires.append({
                    "type": "Feature",
                    "geometry": geometrie,
                    "properties": {
                        "nom": feature["properties"]["adm2_name"],
                        "province": feature["properties"]["adm1_name"],
                        "pcode": feature["properties"]["adm2_pcode"],
                    },
                })
        ecrire(territoires, dossier_sortie / "territoires.geojson",
               f"Territoires (ADM2) — {', '.join(args.provinces)}", points_avant)


if __name__ == "__main__":
    main()
