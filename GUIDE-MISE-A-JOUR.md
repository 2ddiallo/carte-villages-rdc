# Guide de mise à jour de la carte

Ce guide décrit **la seule opération que tu auras à refaire régulièrement** :
publier un nouvel export CHDC sur la carte en ligne.

Carte : <https://2ddiallo.github.io/carte-villages-rdc/>

Trois cas de figure, du plus fréquent au plus rare :

- [A. Nouvel export, mêmes colonnes, mêmes provinces](#a--le-cas-normal) — 5 minutes
- [B. L'export contient de nouvelles colonnes](#b--lexport-a-de-nouvelles-colonnes)
- [C. Des villages dans une province non couverte](#c--des-villages-dans-une-nouvelle-province)

Et à la fin : [vérifications avant publication](#vérifications-avant-de-publier)
et [dépannage](#dépannage).

---

## Avant de commencer (une seule fois)

Ouvre le Terminal et place-toi dans le dossier du projet. **Toutes les
commandes de ce guide se lancent depuis là.**

```bash
cd ~/Desktop/"Claude Code"/carte-villages-rdc
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

## A — Le cas normal

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

## B — L'export a de nouvelles colonnes

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

## C — Des villages dans une nouvelle province

⚠️ **À connaître : la carte n'affiche que 4 provinces.** Tout village CHDC situé
ailleurs est chargé mais **jamais affiché, et sans aucun message d'erreur.**

Dans l'export de juillet 2026, **1 140 des 10 852 villages sont dans ce cas** :

| Province | Villages | Sur la carte |
|---|---:|---|
| Ituri | 3 504 | oui |
| Nord-Kivu | 2 659 | oui |
| Sud-Kivu | 2 096 | oui |
| Tanganyika | 1 453 | oui |
| Maniema | 283 | **non** |
| Kwango | 275 | **non** |
| Haut-Katanga | 165 | **non** |
| Kinshasa | 129 | **non** |
| Kwilu | 120 | **non** |
| Maï Ndombe | 119 | **non** |
| Haut-Lomami | 49 | **non** |

Pour savoir ce que contient ton nouvel export :

```bash
python3 -c "
import json, collections
d = json.load(open('data/villages.geojson'))['features']
for p, n in collections.Counter(f['properties']['Province'] for f in d).most_common():
    print('%-16s %6d' % (p, n))
"
```

### Ajouter une province

Exemple avec le **Maniema**. Le nom doit être écrit exactement comme dans
GRID3 (voir la liste en bas de ce guide).

**1. Télécharger ses données** — les trois premières commandes sont
indépendantes, la quatrième a besoin des précédentes :

```bash
python3 scripts/moissonner_grid3.py --provinces Ituri Nord-Kivu Sud-Kivu Tanganyika Maniema
python3 scripts/preparer_limites.py --provinces Ituri Nord-Kivu Sud-Kivu Tanganyika Maniema
python3 scripts/moissonner_zones_sante.py --provinces Ituri Nord-Kivu Sud-Kivu Tanganyika Maniema
python3 scripts/attribuer_territoires.py --provinces Ituri Nord-Kivu Sud-Kivu Tanganyika Maniema
```

> Il faut **relister toutes les provinces** à chaque fois, pas seulement la
> nouvelle : ces scripts réécrivent les fichiers de limites en entier.

**2. Déclarer la province dans la carte** — dans `index.html`, bloc `CONFIG` :

```js
provinces: [
  { nom: "Ituri",      fichier: "data/grid3_ituri.geojson" },
  { nom: "Nord-Kivu",  fichier: "data/grid3_nord-kivu.geojson" },
  { nom: "Sud-Kivu",   fichier: "data/grid3_sud-kivu.geojson" },
  { nom: "Tanganyika", fichier: "data/grid3_tanganyika.geojson" },
  { nom: "Maniema",    fichier: "data/grid3_maniema.geojson" },   // ← ajout
],
```

Le nom du fichier suit toujours la même règle : préfixe `grid3_`, puis le nom
de la province en minuscules, sans accent, espaces remplacés par des tirets.
Exemples : `Maniema` → `grid3_maniema.geojson`, `Mai-Ndombe` →
`grid3_mai-ndombe.geojson`, `Kasaï-Central` → `grid3_kasai-central.geojson`.

**3. Vérifier en local puis publier** (étapes 3 et 4 du cas A), en ajoutant
`index.html` :

```bash
git add data/ index.html && git commit -m "Ajout de la province du Maniema" && git push
```

---

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
→ Vérifie d'abord leur province (cas C ci-dessus), puis que la case **Données
CHDC** est cochée, et qu'aucun filtre n'est actif (bouton « Réinitialiser les
filtres »).

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

- **Modifier un fichier de `data/` à la main.** Ils sont tous générés et seront
  écrasés à la prochaine exécution des scripts.
- **Committer `data_source/`.** C'est volontairement exclu.
- **Retirer les mentions d'attribution** en bas de la carte (GRID3, OCHA) : les
  licences CC BY les rendent obligatoires.

---

## Annexe — noms de provinces reconnus par GRID3

À écrire exactement ainsi (accents et traits d'union compris) :

```
Bas-Uele          Equateur          Haut-Katanga      Haut-Lomami
Haut-Uele         Ituri             Kasaï             Kasaï-Central
Kasaï-Oriental    Kinshasa          Kongo-Central     Kwango
Kwilu             Lomami            Lualaba           Mai-Ndombe
Maniema           Mongala           Nord-Kivu         Nord-Ubangi
Sankuru           Sud-Kivu          Sud-Ubangi        Tanganyika
Tshopo            Tshuapa
```

(26 provinces — liste relevée directement dans le service GRID3.)

Attention : le CHDC écrit « Maï Ndombe », GRID3 écrit « Mai-Ndombe ». Pour les
commandes de la partie C, c'est **l'orthographe GRID3** qui compte.
