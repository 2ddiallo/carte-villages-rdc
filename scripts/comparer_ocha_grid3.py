#!/usr/bin/env python3
"""Compare le référentiel GRID3 au jeu « DR Congo - Settlements » d'OCHA RDC.

Usage :
    python3 scripts/comparer_ocha_grid3.py

Les deux jeux prétendent recenser les localités de la RDC. On mesure :
volumétrie, répartition par province, recouvrement spatial et nominal,
fraîcheur et provenance. Les résultats sont résumés dans le README.

Le jeu OCHA (HDX, dataset « dr-congo-settlements », licence ODbL) est
téléchargé automatiquement : shapefile en projection World Mercator, reprojeté
ici en WGS84. Nécessite d'avoir déjà lancé moissonner_grid3.py et
preparer_limites.py.
"""

import json
import math
import re
import shutil
import sys
import tempfile
import unicodedata
import urllib.request
import zipfile
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lire_shapefile import lire  # noqa: E402

PROJET = Path(__file__).resolve().parent.parent
ARCHIVE_OCHA = (
    "https://data.humdata.org/dataset/609a58ef-f2fa-44e2-87f0-6e46dac4d45a/"
    "resource/673bb25c-5979-4d3f-91c2-826e318f457f/download/localite.zip"
)
PROVINCES_CARTE = ["Ituri", "Nord-Kivu", "Sud-Kivu", "Tanganyika", "Maniema", "Kwango",
                   "Haut-Katanga", "Kinshasa", "Kwilu", "Mai-Ndombe", "Haut-Lomami"]

A = 6378137.0                       # demi-grand axe WGS84
F = 1 / 298.257223563
E = math.sqrt(2 * F - F * F)


def mercator_vers_wgs84(x: float, y: float) -> tuple:
    """Inverse de la projection World Mercator ellipsoïdale (EPSG:3395)."""
    lon = math.degrees(x / A)
    t = math.exp(-y / A)
    lat = math.pi / 2 - 2 * math.atan(t)
    for _ in range(8):              # convergence en 3-4 tours en pratique
        sin_lat = math.sin(lat)
        lat = math.pi / 2 - 2 * math.atan(
            t * ((1 - E * sin_lat) / (1 + E * sin_lat)) ** (E / 2))
    return lon, math.degrees(lat)


def cle(nom) -> str:
    if not nom:
        return ""
    s = unicodedata.normalize("NFKD", str(nom)).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9\s]", " ", s.lower()).split())


def distance_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ---- Affectation d'une province par géométrie ------------------------------
def anneaux(geom):
    return [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]


def dans_anneau(x, y, anneau):
    dedans = False
    n = len(anneau)
    j = n - 1
    for i in range(n):
        xi, yi = anneau[i]
        xj, yj = anneau[j]
        if (yi > y) != (yj > y) and x < xi + (y - yi) * (xj - xi) / (yj - yi):
            dedans = not dedans
        j = i
    return dedans


def charger_provinces():
    d = json.load(open(PROJET / "data/provinces.geojson", encoding="utf-8"))
    zones = []
    for f in d["features"]:
        for poly in anneaux(f["geometry"]):
            xs = [p[0] for p in poly[0]]
            ys = [p[1] for p in poly[0]]
            zones.append({"nom": f["properties"]["nom"], "poly": poly,
                          "bbox": (min(xs), min(ys), max(xs), max(ys))})
    return zones


def province_de(lon, lat, zones):
    for z in zones:
        x0, y0, x1, y1 = z["bbox"]
        if not (x0 <= lon <= x1 and y0 <= lat <= y1):
            continue
        if dans_anneau(lon, lat, z["poly"][0]) and not any(
                dans_anneau(lon, lat, t) for t in z["poly"][1:]):
            return z["nom"]
    return None


def slug(nom):
    """« Mai-Ndombe » → « mai-ndombe », pour retrouver le fichier GRID3."""
    s = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode()
    return s.lower().replace(" ", "-")


def cle_province(nom):
    """Ramène les graphies divergentes (GRID3 / COD-AB / CHDC) à une clé unique."""
    s = unicodedata.normalize("NFKD", str(nom or "")).encode("ascii", "ignore").decode()
    return s.lower().replace("-", "").replace(" ", "")


def main():
    print("=" * 74)
    print("  GRID3 v8.0 (déc. 2025)  vs  OCHA « DR Congo - Settlements » (fév. 2017)")
    print("=" * 74)

    # ---- Chargement OCHA ---------------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        dossier = Path(tmp)
        archive = dossier / "localite.zip"
        print("\nTéléchargement du jeu OCHA depuis HDX (~3 Mo)…")
        requete = urllib.request.Request(ARCHIVE_OCHA, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(requete, timeout=300) as reponse, open(archive, "wb") as f:
            shutil.copyfileobj(reponse, f)
        with zipfile.ZipFile(archive) as z:
            z.extractall(dossier)
        ocha = lire(dossier / "Localite")
    zones = charger_provinces()
    for ligne in ocha:
        ligne["lon"], ligne["lat"] = mercator_vers_wgs84(ligne["_lon"], ligne["_lat"])
        ligne["province"] = province_de(ligne["lon"], ligne["lat"], zones)

    print(f"\nOCHA  : {len(ocha):>7} localités (RDC entière)")

    # ---- Chargement GRID3 (11 provinces de la carte) -----------------------
    grid3 = defaultdict(list)
    for p in PROVINCES_CARTE:
        f = PROJET / f"data/grid3_{slug(p)}.geojson"
        for feat in json.load(open(f, encoding="utf-8"))["features"]:
            lon, lat = feat["geometry"]["coordinates"]
            grid3[p].append({"nom": feat["properties"].get("localite"), "lon": lon, "lat": lat})
    total_grid3 = sum(len(v) for v in grid3.values())
    print(f"GRID3 : {total_grid3:>7} localités (11 provinces de la carte)")
    print(f"        127 942 localités sur la RDC entière")

    # ---- Comparaison par province ------------------------------------------
    # Les provinces OCHA sont affectées d'après le COD-AB : mêmes clés des deux côtés.
    ocha_par_prov = Counter(cle_province(l["province"]) for l in ocha if l["province"])
    print(f"\n{'PROVINCE':<15}{'OCHA':>9}{'GRID3':>9}{'RAPPORT':>10}")
    print("-" * 43)
    to, tg = 0, 0
    for p in PROVINCES_CARTE:
        o = ocha_par_prov.get(cle_province(p), 0)
        g = len(grid3[p])
        to += o
        tg += g
        print(f"{p:<15}{o:>9}{g:>9}{(g / o if o else 0):>9.1f}×")
    print("-" * 43)
    print(f"{'TOTAL':<15}{to:>9}{tg:>9}{(tg / to if to else 0):>9.1f}×")

    # ---- Fraîcheur et provenance -------------------------------------------
    annees = Counter()
    for l in ocha:
        m = str(l.get("MODIF") or "")
        if len(m) >= 4 and m[:4].isdigit():
            annees[m[:4]] += 1
    print("\nDate de dernière modification des enregistrements OCHA :")
    for annee, n in sorted(annees.items()):
        print(f"  {annee} : {n:>6}  ({100 * n / len(ocha):>4.1f} %)")

    print("\nOrigine déclarée (OCHA) :")
    for src, n in Counter(l.get("ORIGINE") for l in ocha).most_common(5):
        print(f"  {str(src):<34} {n:>6}")
    print("\nSource géométrique (OCHA) :")
    for src, n in Counter(l.get("SCE_GEO") for l in ocha).most_common(5):
        print(f"  {str(src):<34} {n:>6}")

    # ---- Recouvrement spatial et nominal ------------------------------------
    print("\n" + "=" * 74)
    print("  Recouvrement (distance < 2 km et noms similaires ≥ 0,85)")
    print("=" * 74)
    PAS = 0.02
    print(f"\n{'PROVINCE':<15}{'OCHA':>7}{'retrouvés':>11}{'%':>7}{'GRID3 seuls':>13}")
    print("-" * 53)
    stot = rtot = gtot = 0
    for p in PROVINCES_CARTE:
        pts = grid3[p]
        cellules = defaultdict(list)
        for i, g in enumerate(pts):
            cellules[(int(g["lat"] / PAS), int(g["lon"] / PAS))].append(i)

        cibles = [l for l in ocha if cle_province(l["province"]) == cle_province(p)]
        retrouves = 0
        apparies_grid3 = set()
        for l in cibles:
            noms_o = [cle(l.get("NOM1")), cle(l.get("NOM2"))]
            meilleur = None
            li, lj = int(l["lat"] / PAS), int(l["lon"] / PAS)
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    for i in cellules.get((li + di, lj + dj), []):
                        g = pts[i]
                        d = distance_m(l["lat"], l["lon"], g["lat"], g["lon"])
                        if d > 2000:
                            continue
                        s = max((SequenceMatcher(None, a, cle(g["nom"])).ratio()
                                 for a in noms_o if a), default=0.0)
                        if meilleur is None or s > meilleur[1]:
                            meilleur = (i, s)
            if meilleur and meilleur[1] >= 0.85:
                retrouves += 1
                apparies_grid3.add(meilleur[0])
        seuls = len(pts) - len(apparies_grid3)
        stot += len(cibles)
        rtot += retrouves
        gtot += seuls
        pct = 100 * retrouves / len(cibles) if cibles else 0
        print(f"{p:<15}{len(cibles):>7}{retrouves:>11}{pct:>6.0f}%{seuls:>13}")
    print("-" * 53)
    print(f"{'TOTAL':<15}{stot:>7}{rtot:>11}{100 * rtot / stot if stot else 0:>6.0f}%{gtot:>13}")


if __name__ == "__main__":
    main()
