#!/usr/bin/env python3
"""
Sources GRID3 de la carte : adresses HDX, téléchargement, choix du fichier
à lire pour chaque province. Partagé par les trois scripts de moisson
(localités, zones de santé, établissements de santé).

Version en vigueur : GRID3 COD v9.0 (septembre 2026), licence CC BY 4.0.

Deux sortes de fichiers
───────────────────────
1. Les archives nationales v9.0 : un zip par thème, contenant 26 GeoPackage
   (un par province), chacun d'une seule table.

2. Les paquets provinciaux, que GRID3 publie à part pour les provinces en
   situation d'urgence (Nord-Kivu, Ituri). Un seul GeoPackage par province,
   avec une table par thème. GRID3 les met à jour plus souvent que les
   archives nationales et déclare qu'ils **remplacent** la v9.0 pour leur
   province. Ils sont donc prioritaires ici.

   Le paquet du Nord-Kivu pèse ~330 Mo (ses aires de santé sont en pleine
   résolution). D'où l'option `--cache` des scripts : un dossier où les
   fichiers téléchargés sont gardés et réutilisés d'un script à l'autre.
   Sans cache, chaque script retélécharge ce dont il a besoin.

Quand GRID3 publie une nouvelle version
───────────────────────────────────────
Les adresses ci-dessous changent (HDX crée une nouvelle page par version et
retire l'ancienne : c'est ce qui a cassé la moisson v8.0 en octobre 2026).
Les retrouver sur https://data.humdata.org/organization/grid3 — ressources
« *_provinces.zip » — puis mettre à jour VERSION, ARCHIVES et, si GRID3 a
publié de nouveaux paquets, PAQUETS_PROVINCIAUX.
"""

import re
import shutil
import sqlite3
import sys
import unicodedata
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

VERSION = "v9.0"

# Une archive nationale par thème : 26 GeoPackage, un par province.
ARCHIVES = {
    "settlement_names": {
        "libelle": "GRID3 COD – Settlement Names v9.0",
        "page": "https://data.humdata.org/dataset/grid3-cod-settlement-names-v9-0",
        "url": "https://data.humdata.org/dataset/47670d14-423e-4de9-944f-1df0bfc054f7/"
               "resource/3b03de38-cb32-4d2a-b104-1a75bc108018/download/settlement_names_provinces.zip",
        "taille": "11 Mo",
    },
    "health_zones": {
        "libelle": "GRID3 COD – Health Zones v9.0",
        "page": "https://data.humdata.org/dataset/grid3-cod-health-zones-v9-0",
        "url": "https://data.humdata.org/dataset/d716af6d-d75b-4245-a293-39535c2ff955/"
               "resource/cb119324-9790-4253-9c52-260e71d097a2/download/health_zones_provinces.zip",
        "taille": "55 Mo",
    },
    "health_facilities": {
        "libelle": "GRID3 COD – Health Facilities v9.0",
        "page": "https://data.humdata.org/dataset/grid3-cod-health-facilities-v9-0",
        "url": "https://data.humdata.org/dataset/b5a19069-8e66-497d-ac1b-c3ee63e0ab31/"
               "resource/d442d3c4-7072-4581-a858-4bfa269cfc19/download/health_facilities_provinces.zip",
        "taille": "4 Mo",
    },
}

# Paquets provinciaux : ils remplacent la v9.0 pour leur province.
PAQUETS_PROVINCIAUX = {
    "Nord-Kivu": {
        "libelle": "GRID3 COD – Nord-Kivu – Geospatial Data Layers 20260928",
        "page": "https://data.humdata.org/dataset/grid3-cod-nord-kivu-geospatial-data-layers",
        "url": "https://data.humdata.org/dataset/19f38002-9dd4-4439-9381-0117c24326c7/"
               "resource/37e9232b-9299-4117-af69-51158bdea1ca/download/"
               "grid3_cod_nk_geospatial_data_layers.gpkg",
        "taille": "330 Mo",
    },
    "Ituri": {
        "libelle": "GRID3 COD – Ituri – Geospatial Data Layers 20260914",
        "page": "https://data.humdata.org/dataset/grid3-cod-ituri-geospatial-data-layers",
        "url": "https://data.humdata.org/dataset/0f7a292b-4f98-4492-a874-0a2edcc4ceda/"
               "resource/2d0301e6-980e-4fb0-aeba-ed01c1b0d613/download/"
               "grid3_cod_it_geospatial_data_layers.gpkg",
        "taille": "24 Mo",
    },
}

PROVINCES_RDC = [
    "Bas-Uele", "Equateur", "Haut-Katanga", "Haut-Lomami", "Haut-Uele", "Ituri",
    "Kasaï", "Kasaï-Central", "Kasaï-Oriental", "Kinshasa", "Kongo-Central",
    "Kwango", "Kwilu", "Lomami", "Lualaba", "Mai-Ndombe", "Maniema", "Mongala",
    "Nord-Kivu", "Nord-Ubangi", "Sankuru", "Sud-Kivu", "Sud-Ubangi",
    "Tanganyika", "Tshopo", "Tshuapa",
]


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


def telecharger(url: str, destination: Path, libelle: str, page: str) -> Path:
    """Télécharge `url` vers `destination`, sauf si le fichier y est déjà."""
    if destination.exists() and destination.stat().st_size > 0:
        print(f"    {destination.name} : déjà présent dans le cache, réutilisé")
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    partiel = destination.with_name(destination.name + ".partiel")
    print(f"    Téléchargement de {libelle}…", flush=True)
    try:
        with urllib.request.urlopen(url, timeout=600) as reponse, open(partiel, "wb") as fichier:
            shutil.copyfileobj(reponse, fichier)
    except (urllib.error.URLError, TimeoutError) as erreur:
        partiel.unlink(missing_ok=True)
        sys.exit(
            f"Échec du téléchargement : {erreur}\n"
            f"Si le lien a changé, retrouver la ressource sur {page}\n"
            "et mettre à jour scripts/sources_grid3.py."
        )
    partiel.rename(destination)
    print(f"    {destination.stat().st_size / 1_048_576:.1f} Mo téléchargés", flush=True)
    return destination


def _nom_dans_zip(info: zipfile.ZipInfo) -> str:
    """Nom de fichier d'une entrée de zip, accents compris.

    Les archives GRID3 n'indiquent pas l'encodage UTF-8 de leurs noms : Python
    les lit alors en CP437, et « Kasaï » devient illisible. On les relit en UTF-8.
    """
    nom = info.filename
    if not info.flag_bits & 0x800:
        try:
            nom = nom.encode("cp437").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return nom


def extraire_archive(archive: Path, dossier: Path, theme: str) -> dict:
    """Extrait les GeoPackage d'une archive nationale.

    Renvoie {clé de province: chemin}. Le suffixe de version est retiré quel
    qu'il soit : « GRID3_COD_Kasaï-Central_health_zones_v9_0.gpkg » → Kasaï-Central.
    """
    motif = re.compile(rf"^GRID3_COD_(.+)_{theme}_v\d+_\d+$", re.IGNORECASE)
    dossier.mkdir(parents=True, exist_ok=True)
    fichiers = {}
    with zipfile.ZipFile(archive) as zip_archive:
        for info in zip_archive.infolist():
            nom = Path(_nom_dans_zip(info)).name
            if not nom.lower().endswith(".gpkg"):
                continue
            correspondance = motif.match(Path(nom).stem)
            if not correspondance:
                continue
            chemin = dossier / nom
            with zip_archive.open(info) as source, open(chemin, "wb") as cible:
                shutil.copyfileobj(source, cible)
            fichiers[cle_province(correspondance.group(1))] = chemin
    if not fichiers:
        sys.exit(f"Aucun GeoPackage « {theme} » trouvé dans {archive.name} — archive inattendue ?")
    return fichiers


def table_du_theme(chemin: Path, theme: str) -> str:
    """Nom de la table d'un thème dans un paquet provincial (casse variable selon GRID3)."""
    connexion = sqlite3.connect(f"file:{chemin}?mode=ro", uri=True)
    try:
        tables = [ligne[0] for ligne in connexion.execute(
            "SELECT table_name FROM gpkg_contents WHERE data_type = 'features'"
        )]
    finally:
        connexion.close()
    retenues = [t for t in tables if theme.lower() in t.lower()]
    if len(retenues) != 1:
        sys.exit(f"{chemin.name} : table « {theme} » introuvable ou ambiguë parmi {tables}")
    return retenues[0]


def sources_par_province(theme: str, provinces: list, travail: Path,
                         cache: Path = None, archive: Path = None,
                         paquets: bool = True) -> dict:
    """Pour chaque province demandée : (chemin du GeoPackage, table, libellé de source).

    `table` vaut None pour les GeoPackage d'archive (une seule table).
    `archive` : archive nationale déjà téléchargée, prioritaire sur le cache.
    `paquets=False` ignore les paquets provinciaux (v9.0 partout).
    """
    depot = cache or travail
    resultat = {}

    a_paquet = [p for p in provinces if paquets and p in PAQUETS_PROVINCIAUX]
    for province in a_paquet:
        paquet = PAQUETS_PROVINCIAUX[province]
        chemin = telecharger(paquet["url"], depot / Path(paquet["url"]).name,
                             f"{paquet['libelle']} (~{paquet['taille']})", paquet["page"])
        resultat[cle_province(province)] = (chemin, table_du_theme(chemin, theme), paquet["libelle"])

    restantes = [p for p in provinces if p not in a_paquet]
    if restantes:
        source = ARCHIVES[theme]
        if archive is None:
            archive = telecharger(source["url"], depot / Path(source["url"]).name,
                                  f"{source['libelle']} (~{source['taille']})", source["page"])
        fichiers = extraire_archive(archive, travail / theme, theme)
        inconnues = [p for p in restantes if cle_province(p) not in fichiers]
        if inconnues:
            sys.exit(
                f"Provinces absentes de l'archive : {', '.join(inconnues)}\n"
                f"Orthographes acceptées : {', '.join(PROVINCES_RDC)}"
            )
        for province in restantes:
            resultat[cle_province(province)] = (fichiers[cle_province(province)], None,
                                                source["libelle"])
    return resultat


def ajouter_options(parser) -> None:
    """Options communes aux trois scripts de moisson."""
    parser.add_argument("--provinces", nargs="+", default=PROVINCES_RDC,
                        help="Provinces à traiter (défaut : les 26)")
    parser.add_argument("--cache", type=Path, default=None,
                        help="Dossier où garder et réutiliser les fichiers téléchargés")
    parser.add_argument("--archive", type=Path, default=None,
                        help="Archive nationale HDX déjà téléchargée (*_provinces.zip)")
    parser.add_argument("--sans-paquets-provinciaux", action="store_true",
                        help="Lire la v9.0 partout, y compris pour le Nord-Kivu et l'Ituri")
