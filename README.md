# Carte des villages — RDC

**Carte en ligne : <https://2ddiallo.github.io/carte-villages-rdc/>**

⚠️ **Cette adresse est publique** — voir la section [Confidentialité](#confidentialité-des-données)
avant toute mise à jour avec des données réelles.

Carte web légère (Leaflet) couvrant **11 provinces** : Ituri, Nord-Kivu,
Sud-Kivu, Tanganyika, Maniema, Kwango, Haut-Katanga, Kinshasa, Kwilu,
Mai-Ndombe et Haut-Lomami. Elle superpose deux jeux de données qui restent
**indépendants, jamais fusionnés** :

| Couche | Contenu | Points | Origine |
|---|---|---:|---|
| **Référentiel GRID3** | Toutes les localités nommées des 11 provinces | **60 726** | Donnée ouverte (CC BY 4.0) |
| **Données CHDC** | L'export opérationnel mensuel | 10 852 | Export partenaire |

Les 4 provinces de l'Est sont cochées à l'ouverture ; les 7 autres se chargent
à la demande. Tout activer d'emblée représenterait 17 Mo et 60 000 points.

Fonctions : clustering, popup d'attributs, limites de **provinces, de
territoires et de zones de santé**, noms de villages au zoom, bascule de fond
de carte Standard / Satellite, filtres (province, territoire, zone de santé,
type de localité),
recherche par **nom de village**, par **zone de santé** ou par **coordonnées
GPS**, et zoom rapproché direct au clic sur un village.

**Aucun abonnement, aucune clé API, aucun serveur à administrer** : une page
HTML statique + des fichiers GeoJSON, hébergés gratuitement (GitHub Pages).

## Sources et attributions

L'attribution est **obligatoire** (elle figure dans le bandeau en bas de la
carte, ne pas la retirer) :

- **Localités** — [GRID3 COD – Settlement Names v8.0](https://data.grid3.org/datasets/GRID3::grid3-cod-settlement-names-v8-0/about)
  (décembre 2025), produit par CIESIN/Columbia et WorldPop avec l'INS et le
  Ministère de la Santé. Licence **CC BY 4.0**. 127 942 localités sur toute la
  RDC, dont 60 726 sur les 11 provinces couvertes.
- **Limites des zones de santé** — [GRID3 COD – Health Zones v8.0](https://data.humdata.org/dataset/grid3-cod-health-zones-v8-0)
  (janvier 2026). Licence **CC BY 4.0**. 519 zones de santé en RDC, 263 sur les
  11 provinces. Même millésime v8.0 que les localités : le champ `zonesante` y
  porte exactement les mêmes valeurs, donc le filtre de la carte et les limites
  affichées désignent bien les mêmes entités (vérifié : aucun orphelin d'un
  côté ni de l'autre).
- **Limites administratives** — [COD-AB](https://data.humdata.org/dataset/cod-ab-cod),
  OCHA Field Information Services Section, mise à jour du 16 avril 2026.
  Licence **CC BY-IGO**. 26 provinces (ADM1), 164 territoires (ADM2), dont 71
  sur les provinces couvertes.
- **Fond satellite** — Esri World Imagery. **Fond standard** — OpenStreetMap.

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

## GRID3 face aux sources onusiennes

Question légitime : pourquoi s'appuyer sur GRID3 plutôt que sur un jeu OCHA /
Nations unies ? Comparaison faite avec les données réelles, pas sur réputation.

### Les localités : OCHA « DR Congo - Settlements » (fév. 2017)

C'est le jeu de localités publié par OCHA RDC sur HDX
([`dr-congo-settlements`](https://data.humdata.org/dataset/dr-congo-settlements),
licence ODbL, shapefile en projection World Mercator).

| | OCHA 2017 | GRID3 v8.0 |
|---|---:|---:|
| Localités (RDC entière) | 26 710 | **127 942** |
| Sur les 11 provinces de la carte | 13 984 | **60 726** — 4,3× plus |
| Dernière modification | 71 % en **1994**, rien après 2010 | décembre 2025 |
| Origine des positions | 74 % « ancienne base » MONUC / GNS, 24 % relevés GPS | relevés terrain PNLP / IMA / CIESIN, 2021-2022 |

**Recouvrement mesuré** (11 provinces) : 75 % des localités OCHA ont un point
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

Sur les 263 zones des 11 provinces, **245 portent un nom identique**. Les 18
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
├── index.html                          La carte (page unique, autonome)
├── data/
│   ├── grid3_ituri.geojson             Localités GRID3, un fichier par province
│   ├── grid3_nord-kivu.geojson           (11 fichiers générés — ne pas éditer
│   ├── grid3_sud-kivu.geojson             à la main)
│   ├── grid3_tanganyika.geojson
│   ├── grid3_maniema.geojson
│   ├── grid3_kwango.geojson
│   ├── grid3_haut-katanga.geojson
│   ├── grid3_kinshasa.geojson
│   ├── grid3_kwilu.geojson
│   ├── grid3_mai-ndombe.geojson
│   ├── grid3_haut-lomami.geojson
│   ├── villages.geojson                Couche CHDC (générée)
│   ├── provinces.geojson               Limites ADM1 — 26 provinces (générée)
│   ├── territoires.geojson             Limites ADM2 — 71 territoires (générée)
│   ├── zones_sante.geojson             Limites des 263 zones de santé (générée)
│   └── rapprochement_chdc_absents.csv  Villages CHDC sans équivalent GRID3
├── data_source/
│   └── Villages_CHDC_2607.xlsx         Dernier export CHDC reçu
└── scripts/
    ├── convertir_villages.py           Export CHDC (Excel/CSV) → GeoJSON
    ├── moissonner_grid3.py             Téléchargement du référentiel GRID3
    ├── preparer_limites.py             Téléchargement + simplification COD-AB
    ├── moissonner_zones_sante.py       Limites des zones de santé (GRID3)
    ├── attribuer_territoires.py        Ajoute le territoire aux points GRID3
    └── rapprocher_chdc_grid3.py        Compare CHDC et GRID3 (diagnostic)
```

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
décembre 2025). **Les commandes doivent être lancées dans cet ordre** :
`attribuer_territoires.py` a besoin des fichiers produits avant lui.

```bash
python3 scripts/moissonner_grid3.py
python3 scripts/preparer_limites.py
python3 scripts/moissonner_zones_sante.py
python3 scripts/attribuer_territoires.py
```

- `moissonner_grid3.py` interroge le service ArcGIS de GRID3 par pages de
  2 000 objets et écrit un GeoJSON par province (~1,7 Mo chacun).
- `preparer_limites.py` télécharge l'archive COD-AB depuis HDX (~24 Mo) et
  simplifie les contours (Douglas-Peucker, tolérance 0,002° ≈ 220 m) : les
  provinces passent de 97 600 à 21 548 points. Les contours de la carte sont
  donc **indicatifs**, pas une référence juridique.
- `moissonner_zones_sante.py` télécharge les 263 zones de santé et les
  simplifie plus fortement (tolérance 0,003° ≈ 330 m) : les polygones source
  sont énormes (1 024 294 points au total, jusqu'à ~7 300 pour une seule zone)
  et tombent à 14 997 points, soit 0,29 Mo. Sans cela le fichier pèserait
  plusieurs mégaoctets pour un simple habillage.
- `attribuer_territoires.py` ajoute le champ `territoire` à chaque point GRID3
  par recoupement géométrique (99,4 % des points ; les 0,6 % restants sont à
  moins de ~220 m d'une limite).

Pour vérifier le recouvrement avec l'export CHDC après coup :

```bash
python3 scripts/rapprocher_chdc_grid3.py
```

## Confidentialité des données

Le dépôt et le site sont **publics** (condition du plan gratuit de GitHub
Pages) : quiconque a le lien peut voir la carte et les données qu'elle
affiche.

- La couche **GRID3** est une donnée ouverte : sa publication ne pose aucun
  problème.
- La couche **CHDC** est le point sensible. Publier des attributs
  opérationnels (statuts type « déplacement signalé ») sur des localités du
  Nord-Kivu ou de l'Ituri à une adresse publique est une décision à prendre
  consciemment, en contexte de conflit.

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

Trois niveaux de limites, activables séparément dans le panneau « Habillage » :
provinces (trait plein), territoires (tirets) et **zones de santé** (pointillés
verts). Le vert distingue le découpage **sanitaire** du découpage
**administratif** — ils ne se superposent pas.

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

- **Volumétrie** : 24 529 + 9 712 = 34 241 points affichables simultanément,
  pour ~6,8 Mo de GeoJSON GRID3 (chargé par province, en parallèle) plus
  3,6 Mo pour CHDC. Confortable sur une connexion de bureau. Pour un usage
  terrain en 3G instable, il faudrait passer à des tuiles vectorielles
  (MapLibre + PMTiles) — non fait, car non nécessaire à ce stade.
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
