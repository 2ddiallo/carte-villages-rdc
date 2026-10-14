# Guide d'utilisation de la carte

Deux opérations récurrentes, et une qui ne se refait presque jamais.

Carte publique : <https://2ddiallo.github.io/carte-villages-rdc/>
Console de contrôle : en local seulement, elle n'est pas en ligne.

- [**Contrôler des ajouts de villages**](#contrôler-des-ajouts-de-villages) —
  à chaque demande d'ajout reçue
- [**Publier un nouvel export CHDC**](#publier-un-nouvel-export-chdc) —
  une fois par mois, 5 minutes
- [Mettre à jour le référentiel GRID3](#mettre-à-jour-le-référentiel-grid3) —
  à la sortie d'une nouvelle version, une fois par an au plus

Et à la fin : [vérifications avant publication](#vérifications-avant-de-publier)
et [dépannage](#dépannage).

---

## Avant de commencer (une seule fois)

Ouvre le Terminal et place-toi dans le dossier du projet. **Toutes les
commandes de ce guide se lancent depuis là.**

```bash
cd ~/Documents/30_Projets_perso/Claude_Code/carte-villages-rdc
```

Vérifie que tout est en place :

```bash
python3 --version && git status
```

Tu dois voir un numéro de version Python (3.9 ou plus) et la branche `main`.
Si `python3` est introuvable, installe Python depuis <https://www.python.org/downloads/>.

Le script de conversion a besoin de la bibliothèque `pandas`. Si l'étape 2
échoue avec `ModuleNotFoundError: No module named 'pandas'` :

```bash
python3 -m pip install pandas openpyxl
```

---

## Contrôler des ajouts de villages

C'est l'opération à faire **à chaque fois qu'on te demande d'ajouter des
villages**. Elle ne modifie rien : elle produit un avis motivé, village par
village, et garde la trace de tes décisions.

### 1. Ouvrir la console

```bash
python3 -m http.server 8137
```

Puis <http://localhost:8137/controle.html>.

> Cette page **n'est pas en ligne** et ne doit pas l'être. Elle sert à examiner
> des demandes internes. Le fichier que tu y déposes est lu **dans ton
> navigateur** : rien n'est envoyé nulle part, rien n'est publié.
>
> En revanche il faut une connexion internet : les fonds de carte (satellite et
> OpenStreetMap) viennent du réseau.

### 2. Recharger la mémoire des décisions

En bas de la page d'accueil, choisir le dernier `decisions_*.csv` que tu as
exporté. Sans lui, un village que tu as déjà rejeté le mois dernier repassera
sans que rien ne te le signale (c'est le contrôle **C8**).

Si c'est ta toute première session, sauter cette étape.

### 3. Déposer le fichier à contrôler

Glisser l'export (`.xlsx`, `.xls` ou `.csv`) sur la zone en pointillés.

La console propose une correspondance de colonnes — latitude, longitude, nom du
village, province, territoire. **Les vérifier**, elles sont devinées d'après les
en-têtes. Latitude, longitude et nom sont indispensables ; province et
territoire sont facultatifs, mais sans eux le contrôle C4 (« le point tombe-t-il
là où on l'annonce ? ») ne peut rien dire.

Puis « Lancer le contrôle ». Le référentiel de la ou des provinces concernées se
charge à ce moment-là — quelques secondes.

### 4. Passer la file en revue

Les compteurs en haut trient tout :

| | Ce que ça veut dire | Quoi faire |
|---|---|---|
| 🔴 **Doublon / invalide** | coordonnées inutilisables, ou village déjà connu au même endroit | commencer par là |
| 🟠 **À vérifier** | quelque chose cloche sans être disqualifiant | regarder chacun |
| 🟢 **Nouveau** | les huit contrôles passent | survol rapide |

Pour chaque village, le panneau de droite donne :

- **le verdict et ses motifs**, un par contrôle déclenché, en toutes lettres ;
- **la situation réelle du point** : dans quelle province et quel territoire il
  tombe vraiment, d'après la géométrie — pas d'après ce qui est déclaré ;
- **les localités connues à moins de 2 km**, avec leur distance, leur source
  (GRID3 ou base interne), leur précision GPS quand elle est connue, et surtout
  **les deux noms ramenés à leur forme comparée**, avec le score. C'est la
  colonne qui répond à « est-ce le même village mal orthographié, ou deux
  villages voisins ? ».

Sur la carte : le candidat est l'épingle, ses voisins sont des pastilles
étiquetées de leur distance. Les deux cercles marquent 250 m (le seuil de
doublon) et 2 km (au-delà, plus personne n'est comparé). Le fond satellite
permet de voir s'il y a du bâti à l'endroit annoncé.

Flèches ↑ ↓ (ou `j` / `k`) pour passer d'un village au suivant.

### 5. Décider

Quatre gestes :

- **Accepter** — le village est nouveau, il peut entrer dans la base.
- **Fusionner** — c'est un village déjà connu sous un autre nom. Choisir lequel
  dans la liste déroulante : le nom proposé devient un alias, et l'export
  gardera le lien entre les deux.
- **Corriger la position** — faire glisser l'épingle sur la carte. **Les huit
  contrôles sont aussitôt rejoués** sur la nouvelle position : le verdict peut
  changer, c'est normal et c'est le but.
- **Rejeter** — avec un motif, qui sera repris dans l'export et te sera rappelé
  si le village revient.

Le champ « motif » est facultatif mais fortement conseillé sur les rejets :
c'est lui que tu reliras dans six mois.

### 6. Exporter

« Exporter les décisions » télécharge un `decisions_AAAA-MM-JJ.csv` : une ligne
par village arbitré, avec le verdict du contrôle, les drapeaux déclenchés, ta
décision, ton motif, et le village retenu en cas de fusion.

**Garder ce fichier.** C'est la mémoire du système : tu le rechargeras à l'étape
2 de la prochaine session. Il n'est pas versionné dans le dépôt (voir
`.gitignore`) — le ranger dans le dossier de travail de l'équipe.

Les villages acceptés sont ensuite à ajouter à la base source par les moyens
habituels ; la console ne l'écrit pas à ta place.

### Une seule demande reçue par message

Pas besoin de fabriquer un fichier : la page d'accueil a un formulaire. Nom du
village, coordonnées collées telles quelles (`-1.1833, 29.45` ou
`-1,1833 29,45`), province si on la connaît, et « Contrôler ».

### Ce que la console ne fait pas

- Elle ne **prouve pas** qu'un village existe : elle signale les incohérences.
  L'imagerie satellite Esri plafonne au zoom 17 en rural congolais — on y voit
  s'il y a du bâti, pas de quoi trancher entre deux hameaux voisins.
- Elle n'écrit **rien** dans la base source.
- Elle ne travaille **qu'à une personne à la fois**. Deux opérateurs en
  parallèle produiraient deux fichiers de décisions sans lien entre eux.
- L'absence de voisin n'est **pas une anomalie** : 1 719 villages de l'export
  CHDC n'ont aucune localité GRID3 à moins de 2 km. GRID3 ne connaît pas tout.

---

## Publier un nouvel export CHDC

Tu as reçu un nouvel export CHDC, avec les mêmes colonnes qu'avant.

### 1. Déposer le fichier

Copie l'export dans le dossier `data_source/`. Formats acceptés : `.xlsx`,
`.xls`, `.csv`.

> **Le dossier `data_source/` n'est jamais publié.** Il est exclu du dépôt
> (voir `.gitignore`) : les exports bruts du partenaire restent sur ton
> ordinateur, seule la couche qui en dérive part en ligne.

### 2. Convertir en GeoJSON

Remplace le nom du fichier par le tien :

```bash
python3 scripts/convertir_villages.py data_source/Villages_CHDC_2607.xlsx
```

Tu obtiens un rapport de ce type :

```
Colonnes utilisées    : latitude = Latitude, longitude = Longitude, nom = Village
Lignes lues            : 10919
Villages exportés      : 10852
Lignes rejetées        : 47  → détail dans data_source/Villages_CHDC_2607_rejets.csv
Doublons supprimés     : 20
Fichier écrit          : data/villages.geojson (3.6 Mo)
```

**Lis ce rapport, ne le survole pas.** Il est ta seule alerte si quelque chose
cloche.

| Ligne | Ce que ça veut dire | Quoi faire |
|---|---|---|
| Lignes lues | Nombre de lignes du fichier source | Comparer au nombre attendu |
| Villages exportés | Ce qui ira sur la carte | — |
| Lignes rejetées | Coordonnées vides ou non numériques | Voir ci-dessous |
| Doublons supprimés | Même nom **et** mêmes coordonnées | Normal, rien à faire |
| Hors emprise RDC | Coordonnées hors du pays | **À corriger** : souvent une latitude et une longitude inversées |

**Les lignes rejetées ne sont pas perdues** : elles sont listées dans un
fichier `..._rejets.csv` à côté de ton export, avec la colonne
`raison_rejet`. Ouvre-le dans Excel. Dans l'export de juillet 2026, les 47
rejets étaient tous des lignes `N/A- settlement` sans coordonnées — donc sans
intérêt pour une carte. Si en revanche tu y trouves de vrais villages,
corrige les coordonnées **dans le fichier source**, puis relance l'étape 2.

### 3. Vérifier avant de publier

Lance la carte en local :

```bash
python3 -m http.server 8000
```

Ouvre <http://localhost:8000> dans ton navigateur. Coche **Données CHDC** dans
le panneau « Couches » et vérifie que le compteur en bas à droite correspond à
ce que tu attends. Cherche deux ou trois nouveaux villages par leur nom.

Pour arrêter le serveur : `Ctrl + C` dans le Terminal.

> Ouvrir `index.html` en double-cliquant **ne marche pas** — le navigateur
> refuse alors de lire les fichiers de données. Il faut passer par la commande
> ci-dessus.

### 4. Publier

```bash
git add data/
git commit -m "MAJ villages août 2026"
git push
```

C'est tout. GitHub reconstruit et met la carte en ligne **en une à deux
minutes**. Pour suivre :

```bash
gh run watch
```

Ou en regardant l'onglet *Actions* du dépôt :
<https://github.com/2ddiallo/carte-villages-rdc/actions>

### 5. Confirmer

Recharge <https://2ddiallo.github.io/carte-villages-rdc/> **en vidant le cache**
(`Cmd + Shift + R`), sans quoi ton navigateur peut te resservir l'ancienne
version.

---

### L'export a de nouvelles colonnes

**Rien à faire côté script** : `convertir_villages.py` conserve automatiquement
toutes les colonnes du fichier source comme attributs. Une nouvelle colonne est
donc déjà dans les données.

Mais elle **n'apparaîtra pas dans la bulle** au clic sur un village tant que tu
ne l'as pas déclarée. Ouvre `index.html`, cherche le bloc `CONFIG` en haut du
`<script>`, et repère la partie `chdc` :

```js
chdc: {
  libelle: "Données CHDC",
  ...
  champsPopup: [
    { champ: "Territory", libelle: "Territoire" },
    { champ: "Province",  libelle: "Province" },
    { champ: "Quartier",  libelle: "Quartier" },
    { champ: "Quartier1", libelle: "Quartier (2)" },
    // ↓ ajoute ta ligne ici
    { champ: "Nom_exact_de_la_colonne", libelle: "Texte à afficher" },
  ],
},
```

- `champ` : le nom **exact** de la colonne dans ton export (respecte les
  majuscules et les accents).
- `libelle` : ce que verront les utilisateurs.

Les champs vides sont automatiquement masqués : pas besoin de remplir la
colonne pour tous les villages.

N'oublie pas d'ajouter `index.html` à la publication :

```bash
git add data/ index.html && git commit -m "MAJ villages + nouvelle colonne" && git push
```

---

## Mettre à jour le référentiel GRID3

À refaire **seulement à la sortie d'une nouvelle version GRID3** (la v8.0 date
de décembre 2025). Une fois par an au plus.

Les 26 provinces sont couvertes : un export contenant des villages de n'importe
quelle province est désormais affiché et contrôlé sans rien avoir à déclarer.
Il n'y a plus de liste de provinces à passer aux scripts.

**Dans cet ordre** — chaque script a besoin des fichiers produits avant lui :

```bash
python3 scripts/moissonner_grid3.py
python3 scripts/preparer_limites.py
python3 scripts/moissonner_zones_sante.py
python3 scripts/attribuer_territoires.py
python3 scripts/construire_referentiel.py
```

Compter une vingtaine de minutes : 80 Mo à télécharger et beaucoup de contours
à simplifier. Chaque script affiche son bilan — les lire, pas les survoler.

Puis vérifier en local et publier :

```bash
git add data/ ref/ && git commit -m "Référentiel GRID3 v8.1" && git push
```

> **Si un script s'arrête sur « Token Required »** : le service ArcGIS de GRID3
> est devenu privé en septembre 2026 et les scripts ont été réécrits pour lire
> HDX. Un message d'erreur de ce type signifierait qu'une vieille version des
> scripts a été remise en service. Voir la section correspondante du README.

## Vérifications avant de publier

**Le dépôt et la carte sont publics.** Quiconque a le lien voit les données.

L'export actuel ne contient que la hiérarchie administrative (`Country`,
`Province`, `Territory`, `Village`, `Quartier`, `Quartier1` et leurs
identifiants) — rien de sensible. **Mais si un futur export contient des
statuts opérationnels** (déplacements signalés, incidents sécuritaires,
présence de groupes armés, données nominatives), ils deviendront publics au
prochain `git push`.

Prends dix secondes avant chaque publication pour lister les colonnes :

```bash
python3 -c "
import json
d = json.load(open('data/villages.geojson'))['features']
print('Colonnes publiées :')
for c in d[0]['properties']: print('  -', c)
"
```

Si une colonne te fait hésiter, **ne publie pas** et parlons-en. Une donnée
poussée sur un dépôt public reste dans l'historique Git même après
suppression, et peut avoir été copiée ou indexée entre-temps.

Pour publier malgré tout sans la colonne gênante, il suffit de la supprimer du
fichier Excel avant de relancer l'étape 2.

---

## Dépannage

**`ModuleNotFoundError: No module named 'pandas'`**
→ `python3 -m pip install pandas openpyxl`

**`Aucune colonne latitude reconnue`**
→ Les colonnes de coordonnées ont un nom inhabituel. Indique-les :
```bash
python3 scripts/convertir_villages.py data_source/export.xlsx --col-lat Y --col-lon X
```

**Beaucoup de « Hors emprise RDC » dans le rapport**
→ Latitude et longitude sont probablement inversées dans la source. En RDC, la
latitude est comprise entre -14 et 6, la longitude entre 11 et 32.

**Des villages ne s'affichent pas sur la carte**
→ Vérifie que la province est cochée dans le panneau (les 26 y sont, mais seules
les 4 de l'Est le sont d'emblée), que la case **Données CHDC** est cochée, et
qu'aucun filtre n'est actif (bouton « Réinitialiser les filtres »).

---

### Côté console de contrôle

**« Impossible de lire cas_noms.json » sur la page de contrôles**
→ La page a été ouverte par double-clic. Il faut passer par le serveur local :
`python3 -m http.server 8137`, puis `http://localhost:8137/…`.

**Les accents sont abîmés (« dÃ©jÃ  ») dans un CSV déposé**
→ Le fichier est enregistré dans un vieil encodage. La console lit l'UTF-8 (et
tous les `.xlsx`, quelle que soit leur origine). Réenregistrer le CSV en
« UTF-8 » depuis Excel, ou l'enregistrer en `.xlsx`.

**« Latitude, longitude et nom du village sont indispensables »**
→ La détection automatique n'a pas reconnu les en-têtes. Les choisir à la main
dans les listes déroulantes : elles proposent toutes les colonnes du fichier.

**Tous les villages sortent en 🔴 avec « Point hors de la RDC »**
→ Latitude et longitude sont probablement inversées dans la source. Le contrôle
C2 le dit village par village et propose la correction. En RDC, la latitude est
comprise entre −14 et 6, la longitude entre 11 et 32.

**Un village n'a aucun voisin alors qu'il devrait**
→ Regarde d'abord si sa province a bien été chargée (le bandeau l'indique au
lancement). Sinon, c'est peut-être simplement vrai : GRID3 ignore 1 719 des
villages de l'export CHDC.

**La console est lente au lancement**
→ Normal la première fois : elle charge les limites administratives, la base
interne et le référentiel des provinces concernées. Ensuite, chaque contrôle
prend environ une milliseconde.

**La carte en ligne n'a pas changé après le push**
→ Recharge en vidant le cache (`Cmd + Shift + R`). Si c'est toujours le cas,
regarde <https://github.com/2ddiallo/carte-villages-rdc/actions> : le
déploiement a peut-être échoué, ou GitHub connaît une panne (à vérifier sur
<https://www.githubstatus.com>).

**`git push` refusé**
→ Quelqu'un a modifié le dépôt entre-temps : `git pull --rebase` puis
`git push`.

**J'ai publié quelque chose que je ne voulais pas**
→ Ne fais rien d'autre et signale-le. Retirer une donnée de l'historique Git
demande une manipulation particulière ; un simple nouveau commit ne suffit pas.

---

## Ce qu'il ne faut jamais faire

- **Modifier un fichier de `data/` ou de `ref/` à la main.** Ils sont tous
  générés et seront écrasés à la prochaine exécution des scripts.
- **Mettre `controle.html` en ligne.** Le workflow de publication ne recopie
  qu'une liste blanche de fichiers ; ne pas l'y ajouter.
- **Committer un `decisions_*.csv`.** Ils sont exclus du dépôt : ils portent le
  détail de demandes internes, et le dépôt est public.
- **Committer `data_source/`.** C'est volontairement exclu.
- **Retirer les mentions d'attribution** en bas de la carte (GRID3, OCHA) : les
  licences CC BY les rendent obligatoires.

---

## Annexe — orthographe des provinces

Les 26 provinces, telles que GRID3 les écrit (accents et traits d'union
compris). Utile seulement si l'on veut limiter un script à quelques provinces
avec `--provinces` :

```
Bas-Uele          Equateur          Haut-Katanga      Haut-Lomami
Haut-Uele         Ituri             Kasaï             Kasaï-Central
Kasaï-Oriental    Kinshasa          Kongo-Central     Kwango
Kwilu             Lomami            Lualaba           Mai-Ndombe
Maniema           Mongala           Nord-Kivu         Nord-Ubangi
Sankuru           Sud-Kivu          Sud-Ubangi        Tanganyika
Tshopo            Tshuapa
```

Les divergences entre sources (« Mai-Ndombe » côté GRID3, « Maï-Ndombe » côté
OCHA, « Maï Ndombe » côté CHDC) sont rattrapées automatiquement partout : dans
les scripts comme dans la carte, les noms sont ramenés à une clé unique.
