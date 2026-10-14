/*
 * noms.js — comparaison des noms de localités congolaises.
 *
 * Le problème que ce fichier traite : un même village s'écrit différemment
 * d'une source à l'autre. « Dhetchumbu » et « Dhechunbu », « Alibha » et
 * « Aliba », « Sab'ba » et « Saba » désignent le même lieu ; « Zumbe » et
 * « Zumbe 1 » désignent deux lieux voisins mais distincts. Comparer les
 * chaînes brutes ne permet ni de rapprocher les premiers ni de séparer les
 * seconds.
 *
 * Trois niveaux de lecture d'un nom, du plus fidèle au plus permissif :
 *
 *   1. normalise  — accents, apostrophes et ponctuation retirés, mots
 *                   parasites écartés. Sert à l'affichage et au score.
 *   2. base + qualificatif — « Zumbe 1 » → base « zumbe », qualificatif « 1 ».
 *                   Deux noms de même base et de qualificatifs différents sont
 *                   des voisins distincts, jamais un doublon.
 *   3. cle        — clé phonétique, volontairement grossière. Elle ne sert
 *                   qu'à *retrouver* des candidats (blocage), jamais à
 *                   conclure : la décision revient au score calculé sur le
 *                   niveau 1.
 *
 * Ce module est la seule implémentation de ces règles dans le projet — elles
 * ne sont pas dupliquées en Python. Les scripts Python ne préparent que les
 * données ; tout ce qui compare des noms vit ici. Les cas attendus sont dans
 * tests/cas_noms.json, exécutés par tests/tests.html.
 *
 * Aucune dépendance. Expose window.Noms.
 */

(function (global) {
  "use strict";

  // Mots sans valeur discriminante dans les noms de villages congolais.
  // « Cité Mbandaka » et « Mbandaka » doivent se confondre.
  const MOTS_PARASITES = new Set([
    "cite", "village", "loc", "localite", "camp", "campement", "quartier",
    "mission", "poste", "site", "chefferie", "groupement", "gr",
  ]);

  // Qualificatifs qui distinguent deux lieux de même nom. Ils sont détachés du
  // nom, pas supprimés : « Zumbe 1 » et « Zumbe 2 » sont bien deux villages.
  const QUALIFICATIFS = new Set([
    "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "i", "ii", "iii", "iv", "v", "vi",
    "a", "b", "c",
    "centre", "cente", "nord", "sud", "est", "ouest",
    "haut", "bas", "grand", "grande", "petit", "petite",
    "ancien", "ancienne", "nouveau", "nouvelle", "vieux",
  ]);

  // Seuils de décision, mesurés sur les paires réelles de
  // data/rapprochement_chdc_absents.csv. Jaro-Winkler est généreux sur les
  // noms courts : « Aru » et « Rumu » obtiennent 0,72, « Urima » et
  // « Godria » 0,70, alors qu'ils n'ont rien à voir. Les vraies variantes
  // d'un même nom, elles, sont au-dessus de 0,85 (« Esibi » / « Essebi » :
  // 0,86 ; « Dhetchumbu » / « Dhechunbu » : 0,93). D'où un plancher de
  // « proche » nettement plus haut qu'il n'y paraît nécessaire.
  const SEUIL_VARIANTE = 0.85;
  const SEUIL_PROCHE = 0.8;

  // « Dada Gr Dhendro » → « Dada ». Le suffixe désigne le groupement, pas le
  // village : sans ce retrait, « Dada » et « Dada Gr Dhendro » ne se
  // ressemblent qu'à moitié. Règle reprise de rapprocher_chdc_grid3.py.
  const SUFFIXE_GROUPEMENT = /\s+(?:gr|grp|groupement)\b.*$/i;

  /* ------------------------------------------------------------------ *
   * Niveau 1 — normalisation fidèle
   * ------------------------------------------------------------------ */

  /**
   * « Sab'ba (Saba) » → « sabba (saba) » → traité plus loin.
   * Les apostrophes sont supprimées, pas remplacées par un espace : « Sab'ba »
   * et « Sabba » doivent se confondre.
   */
  function normaliser(nom) {
    if (nom === null || nom === undefined) return "";
    const sansAccent = String(nom)
      .normalize("NFKD")
      .replace(/[̀-ͯ]/g, "");
    const sansApostrophe = sansAccent.toLowerCase().replace(/['‘’ʼ`´]/g, "");
    const sansPonctuation = sansApostrophe.replace(/[^a-z0-9\s]/g, " ");
    const mots = sansPonctuation.split(/\s+/).filter(Boolean);
    // Un mot parasite n'est retiré que s'il en reste un autre : une localité
    // réellement nommée « Camp » ne doit pas devenir une chaîne vide.
    const utiles = mots.filter((m) => !MOTS_PARASITES.has(m));
    return (utiles.length ? utiles : mots).join(" ");
  }

  /**
   * Sépare le nom de son qualificatif de rang : « Zumbe 1 » → { base: "zumbe",
   * qualificatif: "1" }. Sans qualificatif, celui-ci vaut "".
   */
  function decomposer(nom) {
    const mots = normaliser(nom).split(" ").filter(Boolean);
    if (mots.length > 1 && QUALIFICATIFS.has(mots[mots.length - 1])) {
      return { base: mots.slice(0, -1).join(" "), qualificatif: mots[mots.length - 1] };
    }
    return { base: mots.join(" "), qualificatif: "" };
  }

  /**
   * Toutes les écritures d'un nom, la principale en premier.
   * « Sab'ba (Saba) Gr Sesele » → ["sabba", "saba"] avec retirerGroupement.
   */
  function variantes(nom, options) {
    if (!nom) return [];
    const retirerGroupement = !!(options && options.retirerGroupement);
    let base = String(nom);
    if (retirerGroupement) base = base.replace(SUFFIXE_GROUPEMENT, "").trim();

    const formes = [base.replace(/\([^)]*\)/g, " ")];
    let trouve;
    const parentheses = /\(([^)]*)\)/g;
    while ((trouve = parentheses.exec(base)) !== null) formes.push(trouve[1]);

    const resultat = [];
    for (const forme of formes) {
      const normalisee = normaliser(forme);
      if (normalisee && !resultat.includes(normalisee)) resultat.push(normalisee);
    }
    return resultat;
  }

  /* ------------------------------------------------------------------ *
   * Niveau 3 — clé phonétique
   * ------------------------------------------------------------------ */

  // Caractère de travail, jamais présent dans un nom : il met le son /tʃ/ de
  // côté le temps que le « c » dur devienne « k », puis reprend sa place.
  const MARQUEUR = "\u0001";

  // Équivalences observées dans les sources congolaises. L'ordre compte : les
  // digrammes sont traités avant les lettres seules, sans quoi le « h » de
  // « dh » disparaîtrait trop tôt.
  const REGLES_PHONETIQUES = [
    // Le son /tʃ/ s'écrit tsh (Tshiluba), tch, ch — et /ʃ/ s'écrit sh. Les
    // deux sont régulièrement confondus d'une source à l'autre : on les
    // réunit sous un caractère provisoire, pour ne pas le confondre avec le
    // « c » dur traité juste après.
    [/tsch|tsh|tch|ch|sh/g, MARQUEUR],
    [/c/g, "k"],
    [new RegExp(MARQUEUR, "g"), "c"],

    // « h » de transcription : Alur et Lendu écrivent bh, dh, th là où
    // d'autres sources écrivent b, d, t. « Alibha » = « Aliba ».
    [/ph/g, "f"],
    [/bh/g, "b"],
    [/dh/g, "d"],
    [/th/g, "t"],
    [/gh/g, "g"],
    [/kh/g, "k"],
    [/mh/g, "m"],
    [/nh/g, "n"],
    [/dj/g, "j"],

    [/qu|q/g, "k"],
    [/x/g, "ks"],
    [/ou/g, "u"],   // transcription française vs anglaise
    [/y/g, "i"],
    [/w/g, "u"],
    [/l/g, "r"],    // une seule liquide dans beaucoup de langues bantoues
    [/h/g, ""],     // les « h » restants sont muets ou instables

    // Nasale devant consonne : elle s'assimile au son suivant (mb / nb, mp /
    // np, nd / md) et les sources hésitent. « Dhetchumbu » = « Dhechunbu ».
    [/[mn](?=[bcdfgjkpqrstvxz])/g, "n"],
  ];

  /** Clé grossière servant à retrouver des candidats, jamais à conclure. */
  function clePhonetique(texte) {
    let cle = normaliser(texte).replace(/\s+/g, "");
    for (const [motif, remplacement] of REGLES_PHONETIQUES) {
      cle = cle.replace(motif, remplacement);
    }
    // Lettres doublées réduites : « Ofoo » = « Ofo », « Sabba » = « Saba ».
    return cle.replace(/([a-z0-9])\1+/g, "$1");
  }

  /**
   * Clés de blocage d'un nom : la clé du nom entier, plus celle de chaque mot
   * d'au moins trois lettres. « Rodo Aliba » produit la clé de l'ensemble et
   * celles de « rodo » et « aliba », ce qui permet de retrouver « Alibha ».
   */
  function clesBlocage(nom) {
    const { base } = decomposer(nom);
    const cles = new Set();
    const entier = clePhonetique(base);
    if (entier) cles.add(entier);
    for (const mot of base.split(" ")) {
      if (mot.length >= 3) {
        const cle = clePhonetique(mot);
        if (cle) cles.add(cle);
      }
    }
    return Array.from(cles);
  }

  /* ------------------------------------------------------------------ *
   * Similarité
   * ------------------------------------------------------------------ */

  /**
   * Jaro-Winkler. Préféré à une distance d'édition simple parce que les noms
   * comparés ici sont courts et partagent souvent leur début : c'est
   * exactement le cas que le bonus de préfixe de Winkler traite bien.
   */
  function jaroWinkler(a, b) {
    if (!a || !b) return 0;
    if (a === b) return 1;

    const fenetre = Math.max(0, Math.floor(Math.max(a.length, b.length) / 2) - 1);
    const prisA = new Array(a.length).fill(false);
    const prisB = new Array(b.length).fill(false);
    let communs = 0;

    for (let i = 0; i < a.length; i++) {
      const debut = Math.max(0, i - fenetre);
      const fin = Math.min(i + fenetre + 1, b.length);
      for (let j = debut; j < fin; j++) {
        if (prisB[j] || a[i] !== b[j]) continue;
        prisA[i] = prisB[j] = true;
        communs++;
        break;
      }
    }
    if (communs === 0) return 0;

    // Transpositions : caractères communs mais dans un ordre différent.
    let transpositions = 0;
    let k = 0;
    for (let i = 0; i < a.length; i++) {
      if (!prisA[i]) continue;
      while (!prisB[k]) k++;
      if (a[i] !== b[k]) transpositions++;
      k++;
    }
    transpositions /= 2;

    const jaro =
      (communs / a.length + communs / b.length + (communs - transpositions) / communs) / 3;

    let prefixe = 0;
    while (prefixe < 4 && prefixe < a.length && prefixe < b.length && a[prefixe] === b[prefixe]) {
      prefixe++;
    }
    return jaro + prefixe * 0.1 * (1 - jaro);
  }

  /* ------------------------------------------------------------------ *
   * Analyse et comparaison
   * ------------------------------------------------------------------ */

  /**
   * Décompose un nom une fois pour toutes. Les objets produits sont conservés
   * dans le référentiel : à 128 000 localités, il ne faut pas recalculer.
   */
  function analyser(nom, options) {
    const formes = variantes(nom, options);
    const principale = formes[0] || "";
    const { base, qualificatif } = decomposer(principale);
    return {
      brut: nom === null || nom === undefined ? "" : String(nom),
      normalise: principale,
      variantes: formes,
      base: base,
      qualificatif: qualificatif,
      cle: clePhonetique(base),
      cles: clesBlocage(principale),
    };
  }

  /**
   * Compare deux noms déjà analysés (ou bruts). Renvoie le score et, surtout,
   * de quoi expliquer ce score à l'écran : c'est un outil de contrôle, il doit
   * dire pourquoi il conclut.
   *
   * `verdict` vaut :
   *   "identique"      — même écriture normalisée
   *   "variante"       — écritures différentes, même lieu très probable
   *   "meme-base"      — même base, qualificatifs différents (Zumbe 1 / Zumbe 2)
   *   "proche"         — se ressemblent sans certitude
   *   "different"      — rien de commun
   */
  function comparer(a, b, options) {
    const seuil = (options && options.seuil) || SEUIL_VARIANTE;
    const analyseA = a && a.normalise !== undefined ? a : analyser(a, options);
    const analyseB = b && b.normalise !== undefined ? b : analyser(b, options);

    // Chaque variante de l'un contre chaque variante de l'autre : « Sab'ba
    // (Saba) » doit pouvoir s'apparier par « saba » comme par « sabba ».
    let score = 0;
    for (const formeA of analyseA.variantes.length ? analyseA.variantes : [""]) {
      for (const formeB of analyseB.variantes.length ? analyseB.variantes : [""]) {
        score = Math.max(score, jaroWinkler(formeA, formeB));
      }
    }

    const memeCle = !!analyseA.cle && analyseA.cle === analyseB.cle;
    const clesCommunes = analyseA.cles.filter((c) => analyseB.cles.includes(c));
    const memeBase = !!analyseA.base && analyseA.base === analyseB.base;
    const qualificatifsDifferents =
      memeBase && analyseA.qualificatif !== analyseB.qualificatif;

    let verdict;
    if (analyseA.normalise && analyseA.normalise === analyseB.normalise) {
      verdict = "identique";
    } else if (qualificatifsDifferents) {
      verdict = "meme-base";
    } else if (memeCle || score >= seuil) {
      verdict = "variante";
    } else if (clesCommunes.length || score >= SEUIL_PROCHE) {
      verdict = "proche";
    } else {
      verdict = "different";
    }

    return {
      score: score,
      verdict: verdict,
      memeCle: memeCle,
      clesCommunes: clesCommunes,
      memeBase: memeBase,
      qualificatifsDifferents: qualificatifsDifferents,
      a: analyseA,
      b: analyseB,
    };
  }

  global.Noms = {
    normaliser: normaliser,
    decomposer: decomposer,
    variantes: variantes,
    clePhonetique: clePhonetique,
    clesBlocage: clesBlocage,
    jaroWinkler: jaroWinkler,
    analyser: analyser,
    comparer: comparer,
    SEUIL_VARIANTE: SEUIL_VARIANTE,
    SEUIL_PROCHE: SEUIL_PROCHE,
    MOTS_PARASITES: MOTS_PARASITES,
    QUALIFICATIFS: QUALIFICATIFS,
  };
})(typeof window !== "undefined" ? window : globalThis);
