# Carte des villages — RDC

**Carte en ligne : <https://2ddiallo.github.io/carte-villages-rdc/>**

⚠️ **Cette adresse est publique** — voir la section [Confidentialité](#confidentialité-des-données)
avant toute mise à jour avec des données réelles.

Deux outils, un même socle de données :

- **La carte** (`index.html`) — consultation, publiée en ligne.
- **La console de contrôle** (`controle.html`) — vérification des villages
  qu'on demande d'ajouter à la base. **Locale, non publiée.**

## La carte

Carte web légère (Leaflet) couvrant les **26 provinces**. Elle superpose deux
jeux de données qui restent **indépendants, jamais fusionnés** :

| Couche | Contenu | Points | Origine |
|---|---|---:|---|
| **Référentiel GRID3** | Toutes les localités nommées de la RDC | **127 942** | Donnée ouverte (CC BY 4.0) |
| **Données CHDC** | L'export opérationnel mensuel | 10 852 | Export partenaire |

Les 4 provinces de l'Est sont cochées à l'ouverture ; les 22 autres se chargent
à la demande. Tout activer d'emblée représenterait 40 Mo et 128 000 points.

Fonctions : clustering, popup d'attributs, **cinq niveaux de découpage**
(provinces, territoires, zones de santé, secteurs et chefferies, chefs-lieux de
groupements), noms au zoom, bascule Standard / Satellite, filtres (province,
territoire, zone de santé, type de localité), recherche par **nom de village**,
par **zone de santé** ou par **coordonnées GPS**, et zoom rapproché direct au
clic sur un village.

**Aucun abonnement, aucune clé API, aucun serveur à administrer** : une page
HTML statique + des fichiers GeoJSON, hébergés gratuitement (GitHub Pages).

## La console de contrôle

`controle.html` répond à un problème concret : on demande régulièrement
d'ajouter des villages à la base, et rien ne permettait de vérifier si les
coordonnées GPS proposées étaient plausibles, ni si le lieu y figurait déjà
sous une autre graphie.

On y dépose l'export à contrôler (ou on saisit une demande isolée). Chaque
village est confronté au référentiel GRID3 national, à la base interne et aux
limites administratives, par **huit contrôles** :

| | Contrôle | Ce qu'il attrape |
|---|---|---|
| C1 | Coordonnées lisibles et en RDC | champs vides, `0, 0`, points hors du pays |
| C2 | Latitude / longitude non inversées | propose la correction |
| C3 | Précision des coordonnées | 2 décimales = 1,1 km d'incertitude |
| C4 | Province et territoire déclarés | point tombant ailleurs qu'annoncé |
| C5 | Aucune localité à moins de 250 m | le doublon franc |
| C6 | Aucun nom concordant à moins de 2 km | le doublon caché par la graphie |
| C7 | Homonyme dans le même territoire | fréquent en RDC, jamais bloquant seul |
| C8 | Décision déjà prise | rappelle un rejet antérieur |

Le verdict — 🟢 nouveau · 🟠 à vérifier · 🔴 doublon ou coordonnées invalides —
**trie la file de revue, il ne décide pas**. Aucune source n'est assez fiable en
RDC pour qu'un automate tranche seul. L'opérateur voit le candidat et ses
voisins sur fond satellite, avec distances, noms normalisés et scores de
similarité, puis accepte, fusionne, corrige la position ou rejette. Les
décisions s'exportent en CSV et se rechargent à la session suivante.

**Le fichier déposé ne quitte pas l'ordinateur** : tout est lu et traité dans le
navigateur. Rien n'est téléversé, rien n'est publié. Mode d'emploi complet :
[GUIDE-MISE-A-JOUR.md](GUIDE-MISE-A-JOUR.md#contrôler-des-ajouts-de-villages).

## Sources et attributions

L'attribution est **obligatoire** (elle figure dans le bandeau en bas de la
carte, ne pas la retirer) :

- **Localités** — GRID3 COD – Settlement Names **v8.0** (décembre 2025), produit
  par CIESIN/Columbia et WorldPop avec l'INS et le Ministère de la Santé.
  Licence **CC BY 4.0**. **127 942 localités**, les 26 provinces.
- **Limites des zones de santé** — GRID3 COD – Health Zones **v8.0**
  (janvier 2026). Licence **CC BY 4.0**. **519 zones de santé**. Même millésime
  v8.0 que les localités : le champ `zonesante` y porte exactement les mêmes
  valeurs, donc le filtre de la carte et les limites affichées désignent bien
  les mêmes entités (vérifié : aucun orphelin d'un côté ni de l'autre).

  > ℹ️ **Les pages HDX de la v8.0 ont été retirées** : GRID3 publie depuis
  > septembre 2026 la **v9.0**, qui les remplace —
  > [Settlement Names v9.0](https://data.humdata.org/dataset/grid3-cod-settlement-names-v9-0)
  > et [Health Zones v9.0](https://data.humdata.org/dataset/grid3-cod-health-zones-v9-0).
  > Les données de ce dépôt restent celles de la v8.0 ; passer à la v9.0
  > suppose de relancer les scripts de moisson et de revérifier les comptages.
- **Limites administratives** — [COD-AB](https://data.humdata.org/dataset/cod-ab-cod),
  OCHA Field Information Services Section, mise à jour du 16 avril 2026.
  Licence **CC BY-IGO**. 26 provinces (ADM1), **164 territoires** (ADM2).
- **Secteurs, chefferies et cités** (737) et **chefs-lieux de groupements**
  (1 681) — archives MONUC, millésimes **2010** et **2009**, reprises du projet
  voisin `carte-rdc-v2`. Voir l'avertissement ci-dessous.
- **Fond satellite** — Esri World Imagery. **Fond standard** — OpenStreetMap.

### ⚠ Le service ArcGIS de GRID3 est devenu privé (septembre 2026)

`moissonner_grid3.py` et `moissonner_zones_sante.py` interrogeaient l'API
ArcGIS de GRID3 (`services3.arcgis.com/BU6Aadhn6tbBEdyk`). Ce service **répond
désormais « Token Required » (code 499)** à toute requête, y compris un simple
comptage. Il n'est plus utilisable sans compte ArcGIS.

Les deux scripts ont été réécrits pour lire les **mêmes jeux v8.0 publiés en
accès libre sur HDX**, sous forme d'archives de GeoPackage — un fichier par
province. C'est plus robuste : un téléchargement unique au lieu de dizaines de
requêtes paginées, et pas de dépendance à la disponibilité d'une API.

Contrôle effectué avant bascule : sur l'Ituri, les deux sources donnent
**6 418 localités, les mêmes identifiants, les mêmes coordonnées**. Rien n'a
changé dans les fichiers produits.

Les GeoPackage sont lus par `scripts/lire_geopackage.py`, écrit pour ce projet :
un GeoPackage est une base SQLite, `sqlite3` suffit à la lire et une soixantaine
de lignes décodent la géométrie binaire. **Aucune installation supplémentaire**
— même parti pris que `lire_shapefile.py` pour les shapefiles d'OCHA. Le
décodeur a été contrôlé face à geopandas : écart nul sur 6 418 points et sur
36 multipolygones de zones de santé.

### ⚠ Secteurs et groupements : des millésimes de 2009-2010

Ni GRID3 ni le COD-AB ne descendent au **secteur / chefferie** ni au
**groupement** — c'est pourtant à ce niveau que les villages sont désignés sur
le terrain, et l'export CHDC nomme d'ailleurs ses villages « X Gr Y ».

Aucune limite nationale à jour de ces niveaux n'existe. Le site officiel rgc.cd
est hors service. Les 737 collectivités (2010) et 1 681 chefs-lieux de
groupements (2009) affichés ici viennent d'archives MONUC : **c'est ce qu'il y a
de mieux, ce n'est pas à jour**. Ces deux couches sont affichées en ambre, avec
leur millésime en légende, décochées par défaut, et **ne motivent jamais un
verdict** dans la console de contrôle.

Ne pas confondre avec l'admin 3 du COD-AB, qui n'est pas le secteur mais la
**zone de santé** (519). La première version de la carte (projet `carte-rdc`)
étiquetait cette couche « Secteurs et chefferies » : c'était une erreur.

Remplace geoBoundaries, utilisé jusqu'ici pour les provinces : COD-AB est le
jeu de référence humanitaire pour la RDC, porte les codes officiels (pcode) et
descend au territoire.

### Pourquoi deux couches et pas une seule

Le rapprochement des deux jeux (`scripts/rapprocher_chdc_grid3.py`) donne un
recouvrement de **35 %** seulement : sur 10 852 villages CHDC, 3 766 retrouvent
leur équivalent GRID3, et 1 719 n'ont **aucune** localité GRID3 dans un rayon
de 2 km. Ce chiffre est stable entre les seuils de similarité 0,70 et 0,85 —
ce n'est pas un artefact de réglage.

Trois causes, aucune n'étant une erreur de l'une ou l'autre source :

1. **Graphies différentes** pour un même village (« Dhetchumbu » / « Dhechunbu »,
   « Zumbe » / « Zumbe 1 »).
2. **Coordonnées imprécises** : les deux sources placent parfois des villages
   distincts au même point (relevés rattachés au centre d'une aire de santé).
   Le champ `precision_` de GRID3 donne la précision en mètres.
3. **Couvertures réellement différentes** : chaque source connaît des villages
   que l'autre ignore.

Fusionner produirait donc autant de faux doublons que de vrais. Les deux
couches sont superposables à l'écran, ce qui permet de comparer visuellement
sans rien écraser.

## Comment les graphies divergentes sont rattrapées

C'est le cœur du problème posé plus haut : « Dhetchumbu » et « Dhechunbu »
désignent le même village, « Zumbe » et « Zumbe 1 » deux villages voisins mais
distincts. Comparer les chaînes de caractères ne permet ni de rapprocher les
premiers ni de séparer les seconds.

Tout est dans **`js/noms.js`**, seule implémentation de ces règles dans le
projet. Trois niveaux de lecture d'un nom :

1. **Le nom normalisé** — accents, apostrophes et ponctuation retirés, mots
   sans valeur discriminante écartés (`cite`, `village`, `quartier`, `camp`,
   `mission`…), suffixe de groupement retiré (« Dada Gr Dhendro » → « Dada »),
   variantes entre parenthèses traitées à part (« Sab'ba (Saba) » donne
   `sabba` **et** `saba`). Sert à l'affichage et au score.

2. **Base + qualificatif de rang** — « Zumbe 1 » se lit base `zumbe` +
   qualificatif `1`. Deux noms de même base et de qualificatifs différents sont
   des **voisins distincts, jamais un doublon**. Le score de similarité seul ne
   sait pas faire cette distinction : « Zumbe » et « Zumbe 1 » se ressemblent à
   0,94.

3. **La clé phonétique** — volontairement grossière, elle sert à *retrouver*
   des candidats, jamais à conclure. Équivalences observées dans les sources
   congolaises :

   | Règle | Exemple |
   |---|---|
   | `tsh` = `tch` = `ch` = `sh` | Tshikapa / Chikapa |
   | `bh` = `b`, `dh` = `d`, `th` = `t` | Alibha / Aliba |
   | `ou` = `u`, `y` = `i`, `w` = `u` | Kwilu / Kuilu |
   | `l` = `r` (une seule liquide) | Kalemie / Karemie |
   | `dj` = `j`, `ph` = `f`, `q` = `k` | Djugu / Jugu |
   | lettres doublées réduites | Ofoo / Ofo, Sabba / Saba |
   | nasale assimilée devant consonne | Dhetchumbu / Dhechunbu |

Le score final est un **Jaro-Winkler** et non une distance d'édition simple :
les noms comparés sont courts et partagent souvent leur début, cas que le bonus
de préfixe traite bien.

### Les seuils, et pourquoi ils sont si hauts

Mesuré sur les paires réelles de `data/rapprochement_chdc_absents.csv` :

| Paire | Score | Verdict |
|---|---:|---|
| Dhetchumbu / Dhechunbu | 0,93 | variante — même village |
| Esibi / Essebi (592 m) | 0,86 | variante — même village |
| **Aru / Rumu** | **0,72** | **rien à voir** |
| **Urima / Godria** | **0,70** | **rien à voir** |
| Bolo / Loba (21 m !) | 0,50 | deux villages |

Sur des noms de quatre ou cinq lettres, Jaro-Winkler donne 0,70 à des noms sans
aucun rapport. D'où un plancher de « proche » à **0,80** et un seuil de
« variante » à **0,85** — des valeurs qui paraissent sévères et ne le sont pas.

La clé phonétique rattrape ce que le score manque : « Rodo Aliba » et « Alibha »
n'obtiennent que 0,42, mais partagent une clé de mot — c'est le blocage, pas le
score, qui les met face à face.

Ces règles sont **contrôlées** : `tests/tests.html` rejoue 52 cas tirés de
divergences réellement observées. Toute modification de `js/noms.js` doit les
repasser.

## GRID3 face aux sources onusiennes

Question légitime : pourquoi s'appuyer sur GRID3 plutôt que sur un jeu OCHA /
Nations unies ? Comparaison faite avec les données réelles, pas sur réputation.

### Les localités : OCHA « DR Congo - Settlements » (fév. 2017)

*Comparaison menée en août 2026, quand la carte ne couvrait que 11 provinces.
Les chiffres portent donc sur ce périmètre ; les conclusions valent pour
l'ensemble.*

C'est le jeu de localités publié par OCHA RDC sur HDX
([`dr-congo-settlements`](https://data.humdata.org/dataset/dr-congo-settlements),
licence ODbL, shapefile en projection World Mercator).

| | OCHA 2017 | GRID3 v8.0 |
|---|---:|---:|
| Localités (RDC entière) | 26 710 | **127 942** |
| Sur les 11 provinces alors couvertes | 13 984 | **60 726** — 4,3× plus |
| Dernière modification | 71 % en **1994**, rien après 2010 | décembre 2025 |
| Origine des positions | 74 % « ancienne base » MONUC / GNS, 24 % relevés GPS | relevés terrain PNLP / IMA / CIESIN, 2021-2022 |

**Recouvrement mesuré** (sur ces 11 provinces) : 75 % des localités OCHA ont un point
GRID3 à moins de 2 km — médiane de 823 m — mais seulement **34 % correspondent
aussi par le nom**. L'écart est donc surtout **nominal** : GRID3 connaît le
lieu, mais les graphies ont divergé en trente ans. À l'inverse, **56 127
localités GRID3 (92 %) n'ont aucun équivalent OCHA.**

### Ce que OCHA apporte que GRID3 n'a pas

La comparaison n'est pas à sens unique. OCHA porte la **hiérarchie
administrative coutumière**, absente de GRID3 :

| Champ OCHA | Renseigné | Équivalent GRID3 |
|---|---:|---|
| `TERRITOIRE` | 99,9 % | aucun (ajouté ici par géométrie) |
| `COLLECTIV` (collectivité / chefferie) | 96,0 % | **aucun** |
| `GROUPEMENT` | 27,5 % | **aucun** |
| `CODE_INS` (code INS) | 14,0 % | aucun |

GRID3 est structuré selon le découpage **sanitaire** (province → zone de santé
→ aire de santé), OCHA selon le découpage **administratif coutumier**
(territoire → collectivité → groupement). Pour un travail sur les chefferies et
groupements, le jeu OCHA reste la référence malgré son âge.

### Les zones de santé : les deux sources concordent

Contrôle rassurant sur la couche affichée par la carte :

| | OCHA (sept. 2019) | GRID3 v8.0 (janv. 2026) |
|---|---:|---:|
| Zones de santé en RDC | 519 | **519** |

Sur les 263 zones de ces 11 provinces, **245 portent un nom identique**. Les 18
écarts sont des subdivisions de Kinshasa (Kalamu 1/2, Masina 1/2, Maluku 1/2,
Mont Ngafula 1/2) et trois renommages en Ituri (Gety, Mongbwalu, Nyankunde) —
pas un désaccord de découpage. C'est bien la carte sanitaire officielle du
Ministère de la Santé dans les deux cas.

### Et OpenStreetMap ?

[HOT OSM](https://data.humdata.org/dataset/hotosm_cod_populated_places) publie
un extrait actualisé quotidiennement. Sur les 4 provinces de l'Est, il compte
84 377 nœuds `place` — mais **78 970 sont sans nom** (bâti cartographié à
distance). Il ne reste que ~5 400 lieux nommés, moins que GRID3, sous licence
ODbL contaminante en cas de fusion. Non retenu.

### Conclusion

GRID3 est retenu comme socle parce qu'il est **4,3× plus dense, trente ans plus
récent, et issu de relevés GPS de terrain**. C'est aussi une production
conjointe CIESIN/Columbia, WorldPop, INS et Ministère de la Santé — pas une
source tierce face à l'ONU, mais le référentiel que les acteurs humanitaires
utilisent aujourd'hui en RDC.

Ses limites, à garder en tête : pas de hiérarchie administrative coutumière, et
un découpage provincial qui diverge parfois du COD-AB d'OCHA (2,2 % des points
tombent hors des limites de leur propre province, jusqu'à 17,5 % au Mai-Ndombe,
province de lacs et marécages aux contours mouvants).

Pour rejouer cette comparaison : `scripts/comparer_ocha_grid3.py`.

## Structure du projet

```
carte-villages-rdc/
├── index.html                          La carte publique (page unique)
├── controle.html                       La console de contrôle (LOCALE, non publiée)
├── js/
│   ├── noms.js                         Comparaison des noms de localités
│   └── controle.js                     Les huit contrôles, sans dépendance à l'UI
├── data/                               Tout est généré — ne rien éditer à la main
│   ├── grid3_<province>.geojson          26 fichiers, 0,4 à 3 Mo chacun
│   ├── villages.geojson                  Couche CHDC
│   ├── provinces.geojson                 26 provinces (ADM1)
│   ├── territoires.geojson               164 territoires (ADM2)
│   ├── zones_sante.geojson               519 zones de santé
│   ├── secteurs.geojson                  737 secteurs et chefferies (2010)
│   ├── groupements.geojson               1 681 chefs-lieux (2009)
│   └── rapprochement_chdc_absents.csv     Villages CHDC sans équivalent GRID3
├── ref/                                Référentiel compact lu par la console
│   ├── <province>.json                   Mêmes localités, 4,8× plus légères
│   └── index.json                        Emprise et effectif de chaque province
├── tests/
│   ├── tests.html                        52 contrôles sur js/noms.js
│   ├── cas_noms.json                     Les cas attendus
│   └── lot_epreuve.csv                   Jeu d'épreuve : un cas par contrôle
├── data_source/                        Exports bruts du partenaire — jamais publiés
└── scripts/
    ├── moissonner_grid3.py             Localités GRID3 (HDX) → GeoJSON
    ├── preparer_limites.py             COD-AB → provinces et territoires
    ├── moissonner_zones_sante.py       Zones de santé GRID3 (HDX)
    ├── attribuer_territoires.py        Ajoute le territoire aux points GRID3
    ├── convertir_secteurs.py           Secteurs et groupements (archives MONUC)
    ├── construire_referentiel.py       data/ → ref/ (format compact)
    ├── convertir_villages.py           Export CHDC (Excel/CSV) → GeoJSON
    ├── lire_geopackage.py              Lecteur GeoPackage sans dépendance
    ├── lire_shapefile.py               Lecteur shapefile sans dépendance
    ├── comparer_ocha_grid3.py          Comparaison GRID3 / OCHA (diagnostic)
    └── rapprocher_chdc_grid3.py        Comparaison CHDC / GRID3 (diagnostic)
```

**Où vivent les règles.** Python ne fait que *préparer les données*. Tout ce qui
*compare des noms* est en JavaScript, dans `js/noms.js`, et nulle part ailleurs.
Une seconde implémentation des règles de graphie finirait par diverger de la
première — ce qui est exactement le problème que ce projet cherche à résoudre.

## Mise à jour mensuelle de la couche CHDC

C'est la seule opération récurrente. **Procédure pas à pas, avec
dépannage et cas particuliers : [GUIDE-MISE-A-JOUR.md](GUIDE-MISE-A-JOUR.md).**
Le résumé ci-dessous suffit pour un export habituel.

1. Déposer le nouvel export (`.xlsx`, `.xls` ou `.csv`) dans `data_source/`.
2. Depuis le dossier du projet :

   ```bash
   python3 scripts/convertir_villages.py data_source/mon_export.xlsx
   ```

   Le script détecte automatiquement les colonnes de coordonnées et écrit
   `data/villages.geojson`, avec un rapport : lignes lues, rejetées
   (coordonnées manquantes/invalides — détail dans un fichier `*_rejets.csv` à
   corriger dans la source), doublons supprimés, points hors emprise RDC.

3. Publier (voir avertissement de confidentialité ci-dessous) :

   ```bash
   git add data/ && git commit -m "MAJ villages 2026-08" && git push
   ```

   `data_source/` est volontairement exclu du dépôt (voir `.gitignore`) : les
   exports bruts du partenaire restent en local, seule la couche qui en dérive
   est publiée.

   GitHub Pages republie le site automatiquement en ~1 minute.

### Format attendu de l'export CHDC

- Colonnes de coordonnées reconnues automatiquement (indifférent à la
  casse) : `Latitude`/`lat`/`y` et `Longitude`/`lon`/`lng`/`x`. Autres noms
  possibles via `--col-lat` / `--col-lon`.
- Toutes les autres colonnes sont conservées comme attributs — on peut en
  ajouter sans toucher au script.

## Mise à jour du référentiel GRID3

À refaire seulement à la sortie d'une nouvelle version GRID3 (v8.0 date de
décembre 2025). **Dans cet ordre** — `attribuer_territoires.py` a besoin des
fichiers produits avant lui, et `construire_referentiel.py` de tous les autres :

```bash
python3 scripts/moissonner_grid3.py
python3 scripts/preparer_limites.py
python3 scripts/moissonner_zones_sante.py
python3 scripts/attribuer_territoires.py
python3 scripts/construire_referentiel.py
```

Plus aucune liste de provinces à passer : les 26 sont le défaut partout.

- `moissonner_grid3.py` télécharge l'archive HDX des GeoPackage (~10 Mo) et
  écrit un GeoJSON par province. Total : **127 942 localités**, 40 Mo.
- `preparer_limites.py` télécharge l'archive COD-AB (~24 Mo) et simplifie les
  contours (Douglas-Peucker, tolérance 0,002° ≈ 220 m) : les provinces passent
  de 97 600 à 21 548 points, les 164 territoires de 224 696 à 48 339. Les
  contours de la carte sont donc **indicatifs**, pas une référence juridique.
- `moissonner_zones_sante.py` télécharge l'archive HDX des zones de santé
  (~46 Mo) et simplifie plus fortement (0,003° ≈ 330 m) : les 519 polygones
  passent de **4 131 532 à 74 576 points**, soit 1,46 Mo. Sans cela le fichier
  pèserait des dizaines de mégaoctets pour un simple habillage.
- `attribuer_territoires.py` ajoute le champ `territoire` à chaque point GRID3
  par recoupement géométrique : **98,2 %** des points. Les 1,8 % restants sont
  à moins de ~220 m d'une limite, ou sur un lac.
- `construire_referentiel.py` réencode `data/` en `ref/` pour la console :
  dictionnaires de valeurs répétées, tableaux sans noms de champs, 5 décimales.
  **40 Mo → 8,4 Mo**, soit ~320 Ko par province. La console charge la province
  d'un candidat *et ses voisines* (un village près d'une limite doit être
  comparé aux localités de l'autre côté).

Les secteurs et groupements ne bougent pas — leurs sources sont figées depuis
2009-2010 :

```bash
python3 scripts/convertir_secteurs.py
```

Pour rejouer la comparaison avec l'export CHDC :

```bash
python3 scripts/rapprocher_chdc_grid3.py
```

## Contrôles

```bash
python3 -m http.server 8137
```

- <http://localhost:8137/tests/tests.html> — 52 contrôles sur `js/noms.js`.
  Tout doit être au vert.
- <http://localhost:8137/controle.html> avec `tests/lot_epreuve.csv` — un cas
  par contrôle (coordonnées inversées, `0, 0`, deux décimales, mauvaise
  province, doublon à 80 m sous une autre graphie, homonyme à 127 km,
  qualificatif de rang, village isolé). Chacun doit déclencher le sien.

Le jeu d'épreuve est **fabriqué à partir de vraies localités de l'Ituri** : les
voisins affichés sont réels, seuls les candidats sont forgés.

## Confidentialité des données

Le dépôt et le site sont **publics** (condition du plan gratuit de GitHub
Pages) : quiconque a le lien peut voir la carte et les données qu'elle affiche.

- La couche **GRID3** est une donnée ouverte : sa publication ne pose aucun
  problème.
- La couche **CHDC** est le point sensible. Publier des attributs opérationnels
  (statuts type « déplacement signalé ») sur des localités du Nord-Kivu ou de
  l'Ituri à une adresse publique est une décision à prendre consciemment, en
  contexte de conflit.
- Les **villages en cours de contrôle** ne sont, eux, jamais en ligne : la
  console les lit dans le navigateur et n'envoie rien. Les fichiers déposés et
  les `decisions_*.csv` téléchargés sont exclus du dépôt par `.gitignore`.

### Ce que le site publie exactement

Le workflow de déploiement ne met **pas** tout le dépôt en ligne : il recopie
une liste blanche (`index.html`, `data/`, `js/`, `.nojekyll`) dans un dossier
`_site/` et ne publie que lui. `controle.html`, `ref/`, `tests/`, `scripts/` et
`data_source/` restent hors du site.

Ajouter un fichier au dépôt ne le publie donc pas : il faut l'ajouter à la
liste dans `.github/workflows/pages.yml`. Un garde-fou échoue le déploiement si
`index.html` en vient à référencer un fichier resté hors du site — mieux vaut
l'apprendre là qu'en découvrant une carte muette en production.

Vérification après coup : `…github.io/carte-villages-rdc/controle.html` doit
renvoyer **404**.

**Options si un accès restreint est nécessaire** : Cloudflare Pages +
Cloudflare Access (accès nominatif par e-mail, gratuit jusqu'à 50 comptes), un
fichier HTML autonome partagé via un espace privé (Drive/SharePoint), ou un
chiffrement de la page par phrase secrète.

## Utiliser la carte

### Recherche

Un seul champ, trois usages :

- **Nom de village** — « Rethy », « Mahagi ». Ne cherche que dans les couches
  et provinces actives.
- **Zone de santé, aire de santé, territoire** — les résultats « Ensembles »
  cadrent la carte sur l'emprise correspondante. **Indispensable pour les
  villes** : le référentiel GRID3 s'arrête au niveau de la localité, si bien
  que Bunia, Goma ou Bukavu n'existent pas comme point unique — Bunia est
  éclatée en 188 quartiers et avenues. Chercher « Bunia » renvoie donc la
  *zone de santé* Bunia, pas un village.
- **Coordonnées GPS** — « -1.1833, 29.45 » ou « -1,1833 29,45 » (latitude puis
  longitude). La carte zoome et pose un repère.

### Habillage

Cinq niveaux de limites, activables séparément dans le panneau « Habillage ».
**La couleur dit à quel découpage on a affaire** — ils ne se superposent pas :

| Couleur | Découpage | Niveau | Millésime |
|---|---|---|---|
| Blanc, trait plein | administratif | province | 2026 |
| Blanc, tirets | administratif | territoire | 2026 |
| Vert, pointillés | **sanitaire** | zone de santé | 2026 |
| Ambre, tirets longs | **coutumier** | secteur / chefferie | **2010** |
| Ambre, pastilles | **coutumier** | chef-lieu de groupement | **2009** |

Les deux couches coutumières sont **décochées par défaut** et se chargent au
premier cochage (2,2 Mo). Leur millésime est rappelé dans la légende : ce sont
des repères, pas des références.

Les noms apparaissent par plages de zoom, pour ne pas saturer : provinces
jusqu'à z7, territoires z8–z10, secteurs z9–z11, zones de santé z11–z12,
villages et groupements à partir de z13.

### Filtres

Province, territoire, zone de santé, type de localité. Les listes déroulantes
ne proposent que des valeurs présentes dans les provinces cochées.

Zone de santé et type de localité n'existent que dans GRID3 : quand l'un des
deux est renseigné, la couche CHDC est **masquée** plutôt que filtrée à tort.

### Changer les champs affichés dans le popup

Éditer le bloc `CONFIG` en haut du `<script>` dans `index.html`, dans la couche
concernée :

```js
couches: {
  grid3: {
    champsPopup: [
      { champ: "localitetype", libelle: "Type" },
      // ajouter ici : { champ: "nom_propriete", libelle: "Texte affiché" },
    ],
  },
}
```

## Tester en local

Le GeoJSON étant chargé par la page, il faut un petit serveur local (ouvrir
`index.html` en double-cliquant ne suffit pas) :

```bash
python3 -m http.server 8000
```

puis ouvrir <http://localhost:8000>.

## Hébergement — GitHub Pages (déjà en place)

Dépôt public `2ddiallo/carte-villages-rdc`, publié par GitHub Pages depuis la
branche `main` (racine). La carte est en ligne à
<https://2ddiallo.github.io/carte-villages-rdc/> et se republie
automatiquement en 1 à 2 minutes après chaque `git push`.

Les chemins de la page sont **relatifs** (`data/…`), elle fonctionne donc
indifféremment à la racine d'un domaine ou dans un sous-chemin.

Pour reproduire la configuration ailleurs : **Settings → Pages → Source :
Deploy from a branch → Branch : main / (root) → Save**. Un dépôt nommé
`<compte>.github.io` donnerait une URL racine, sans sous-chemin.

Une version antérieure de ce projet est archivée sur l'organisation
`villages-drc`. En local, son historique reste accessible sur la branche
`archive-villages-drc` et son dépôt sous le remote `villages-drc`.

## Fond satellite : choix retenu

**Esri World Imagery**, actif **par défaut à l'ouverture** de la carte :
gratuit, sans clé API, sans quota à surveiller. Le bouton « Standard »
permet de rebasculer sur OpenStreetMap.

En zones rurales de RDC, l'imagerie Esri réelle s'arrête vers le zoom 17
(au-delà, le service renvoie une tuile « Map data not yet available »). Le
niveau natif est donc plafonné à 17 (`maxNativeZoom`) : Leaflet agrandit ces
tuiles plutôt que d'afficher le placeholder. Cette limite est structurelle
(imagerie haute résolution non captée) : la variante Esri « Clarity » et les
autres fonds gratuits ne couvrent pas mieux le rural — testé.

Si la résolution s'avère insuffisante sur certaines zones, seule piste :
**Mapbox Satellite** (gratuit < 50 000 chargements/mois, nécessite une clé
API ; couverture parfois différente, sans garantie de gain en rural). Pour
basculer, remplacer `satelliteLayer` dans `index.html` par :

```js
const satelliteLayer = L.tileLayer(
  "https://api.mapbox.com/styles/v1/mapbox/satellite-streets-v12/tiles/{z}/{x}/{y}?access_token=VOTRE_CLE",
  { attribution: "&copy; Mapbox &copy; Maxar", maxZoom: 19, tileSize: 512, zoomOffset: -1 }
);
```

## Notes techniques

- **Volumétrie** : le référentiel national pèse 40 Mo, mais rien n'est chargé
  d'avance — chaque province (0,4 à 3 Mo) descend au cochage de sa case. À
  l'ouverture, les 4 provinces de l'Est représentent 24 529 points GRID3 et
  ~6,8 Mo, plus 3,6 Mo pour la couche CHDC. Confortable sur une connexion de
  bureau. Pour un usage terrain en 3G instable, il faudrait passer à des tuiles
  vectorielles (MapLibre + PMTiles) — non fait, car non nécessaire à ce stade.
- **Côté console**, le référentiel compact de `ref/` change les ordres de
  grandeur : construire l'index d'une province (6 000 localités, clés
  phonétiques comprises) prend ~220 ms, et contrôler un candidat ~1 ms.
- **Clustering** : plugin Leaflet.markercluster, chargement par tranches
  (`chunkedLoading`). En dessous du zoom 12, les points individuels
  s'affichent (rendu canvas).
- Les marqueurs sont créés **une seule fois** puis réutilisés : changer un
  filtre ne recrée pas 34 000 objets.
- Un clic sur un village recentre et zoome dessus (niveau `zoomClicVillage`
  dans le bloc CONFIG, 18 par défaut) et ouvre son popup.
- **Étiquettes** : une seule famille de noms est visible à la fois, chaque
  niveau ayant sa plage de zoom exclusive — provinces jusqu'à z7, territoires
  z8–z10, zones de santé z11–z12, villages à partir de z13.
  ⚠️ Leaflet écrit `opacity: 0.9` en **style inline** sur chaque tooltip
  permanent (`Tooltip.onAdd`). Les règles CSS qui masquent les étiquettes
  doivent donc porter `!important`, sinon elles sont silencieusement ignorées
  et tous les noms restent visibles à tous les zooms.
- Les limites administratives sont non cliquables (posées sous les villages
  dans des panes Leaflet dédiées) et changent de couleur selon le fond de
  carte actif (blanc sur satellite, bleu marine sur standard).
