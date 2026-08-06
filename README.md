# Carte des villages — RDC (Est)

**Carte en ligne : <https://2ddiallo.github.io/carte-villages-rdc/>**

⚠️ **Cette adresse est publique** — voir la section [Confidentialité](#confidentialité-des-données)
avant toute mise à jour avec des données réelles.

Carte web légère (Leaflet) couvrant **Ituri, Nord-Kivu, Sud-Kivu et Tanganyika**.
Elle superpose deux jeux de données qui restent **indépendants, jamais fusionnés** :

| Couche | Contenu | Points | Origine |
|---|---|---:|---|
| **Référentiel GRID3** | Toutes les localités nommées des 4 provinces | **24 529** | Donnée ouverte (CC BY 4.0) |
| **Données CHDC** | L'export opérationnel mensuel | 9 712 | Export partenaire |

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
  RDC, dont 24 529 sur les 4 provinces.
- **Limites des zones de santé** — [GRID3 COD – Health Zones v8.0](https://data.humdata.org/dataset/grid3-cod-health-zones-v8-0)
  (janvier 2026). Licence **CC BY 4.0**. 519 zones de santé en RDC, 115 sur les
  4 provinces. Même millésime v8.0 que les localités : le champ `zonesante` y
  porte exactement les mêmes valeurs, donc le filtre de la carte et les limites
  affichées désignent bien les mêmes entités (vérifié : 115 = 115, aucun
  orphelin d'un côté ni de l'autre).
- **Limites administratives** — [COD-AB](https://data.humdata.org/dataset/cod-ab-cod),
  OCHA Field Information Services Section, mise à jour du 16 avril 2026.
  Licence **CC BY-IGO**. 26 provinces (ADM1), 164 territoires (ADM2).
- **Fond satellite** — Esri World Imagery. **Fond standard** — OpenStreetMap.

Remplace geoBoundaries, utilisé jusqu'ici pour les provinces : COD-AB est le
jeu de référence humanitaire pour la RDC, porte les codes officiels (pcode) et
descend au territoire.

### Pourquoi deux couches et pas une seule

Le rapprochement des deux jeux (`scripts/rapprocher_chdc_grid3.py`) donne un
recouvrement de **35 %** seulement : sur 9 712 villages CHDC, environ 3 400
retrouvent leur équivalent GRID3, et 1 476 n'ont **aucune** localité GRID3 dans
un rayon de 2 km. Ce chiffre est stable entre les seuils de similarité 0,70 et
0,85 — ce n'est pas un artefact de réglage.

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

## Structure du projet

```
carte-villages-rdc/
├── index.html                          La carte (page unique, autonome)
├── data/
│   ├── grid3_ituri.geojson             Localités GRID3, un fichier par province
│   ├── grid3_nord-kivu.geojson           (générés — ne pas éditer à la main)
│   ├── grid3_sud-kivu.geojson
│   ├── grid3_tanganyika.geojson
│   ├── villages.geojson                Couche CHDC (générée)
│   ├── provinces.geojson               Limites ADM1 — 26 provinces (générée)
│   ├── territoires.geojson             Limites ADM2 — 29 territoires (générée)
│   ├── zones_sante.geojson             Limites des 115 zones de santé (générée)
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

C'est la seule opération récurrente.

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
- `moissonner_zones_sante.py` télécharge les 115 zones de santé et les
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
