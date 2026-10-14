/*
 * controle.js — les contrôles appliqués à un village qu'on demande d'ajouter.
 *
 * Le besoin : on reçoit régulièrement des demandes d'ajout de villages, avec
 * un nom et des coordonnées GPS. Rien ne dit aujourd'hui si ces coordonnées
 * sont plausibles, ni si le lieu figure déjà dans la base sous une autre
 * graphie. Le rapprochement mesuré entre l'export CHDC et GRID3 donne l'ordre
 * de grandeur du problème : 35 % de recouvrement seulement, et 1 719 villages
 * sans aucune localité connue à moins de 2 km.
 *
 * Huit contrôles, chacun produisant un drapeau motivé (voir CONTROLES). Le
 * verdict agrégé — nouveau / à vérifier / doublon ou invalide — ne sert qu'à
 * *ordonner la file de revue*. Il ne décide jamais à la place de l'opérateur :
 * aucune source n'est assez fiable en RDC pour qu'un automate tranche seul.
 *
 * Ce fichier ne connaît ni le DOM ni Leaflet. C'est délibéré : si la mémoire
 * des décisions passe un jour d'un CSV local à une base partagée, seule la
 * couche d'entrée/sortie change.
 *
 * Dépend de js/noms.js. Expose window.Controle.
 */

(function (global) {
  "use strict";

  const Noms = global.Noms;
  if (!Noms) throw new Error("controle.js requiert js/noms.js, chargé avant lui.");

  /* ------------------------------------------------------------------ *
   * Réglages
   * ------------------------------------------------------------------ */

  const SEUILS = {
    // Emprise de la RDC, avec une petite marge. Mêmes bornes que
    // convertir_villages.py, pour que les deux outils rejettent la même chose.
    latMin: -14, latMax: 6, lonMin: 11, lonMax: 32,

    doublonM: 250,          // en deçà : doublon probable
    voisinageM: 2000,       // au-delà : plus personne n'est comparé
    limiteAdminM: 500,      // sous cette distance d'une limite, l'écart s'explique
    ecartAdminM: 2000,      // au-delà, à l'intérieur d'une autre unité : anomalie

    decimalesMin: 3,        // 3 décimales ≈ 110 m ; 2 ≈ 1,1 km
    precisionGpsM: 500,     // précision GRID3 au-delà de laquelle on prévient

    homonymeM: 2000,        // un homonyme au-delà de cette distance n'est pas un doublon
  };

  // Taille des cellules d'indexation : 0,02° ≈ 2,2 km, soit un peu plus que le
  // rayon de voisinage — un balayage 3×3 suffit donc toujours.
  const PAS_CELLULE = 0.02;

  const CONTROLES = {
    C1: "Coordonnées lisibles et situées en RDC",
    C2: "Latitude et longitude non inversées",
    C3: "Précision des coordonnées suffisante",
    C4: "Cohérence avec la province et le territoire déclarés",
    C5: "Aucune localité connue à moins de 250 m",
    C6: "Aucun nom concordant dans un rayon de 2 km",
    C7: "Homonyme ailleurs dans le même territoire",
    C8: "Village déjà arbitré lors d'une session précédente",
  };

  const GRAVITES = { rouge: 3, orange: 2, info: 1 };

  /* ------------------------------------------------------------------ *
   * Géométrie
   * ------------------------------------------------------------------ */

  const RAYON_TERRE = 6371000;

  function distanceM(lat1, lon1, lat2, lon2) {
    const rad = Math.PI / 180;
    const dLat = (lat2 - lat1) * rad;
    const dLon = (lon2 - lon1) * rad;
    const a =
      Math.sin(dLat / 2) ** 2 +
      Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLon / 2) ** 2;
    return 2 * RAYON_TERRE * Math.asin(Math.min(1, Math.sqrt(a)));
  }

  /** Lancer de rayon sur un anneau. */
  function dansAnneau(lon, lat, anneau) {
    let dedans = false;
    for (let i = 0, j = anneau.length - 1; i < anneau.length; j = i++) {
      const [xi, yi] = anneau[i];
      const [xj, yj] = anneau[j];
      if ((yi > lat) !== (yj > lat) &&
          lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) {
        dedans = !dedans;
      }
    }
    return dedans;
  }

  /** Appartenance à un Polygon ou un MultiPolygon, trous compris. */
  function dansGeometrie(lon, lat, geometrie) {
    if (!geometrie) return false;
    const polygones =
      geometrie.type === "Polygon" ? [geometrie.coordinates] :
      geometrie.type === "MultiPolygon" ? geometrie.coordinates : [];
    for (const polygone of polygones) {
      if (!dansAnneau(lon, lat, polygone[0])) continue;
      // Le point est dans le contour : il ne doit être dans aucun trou.
      let dansTrou = false;
      for (let i = 1; i < polygone.length; i++) {
        if (dansAnneau(lon, lat, polygone[i])) { dansTrou = true; break; }
      }
      if (!dansTrou) return true;
    }
    return false;
  }

  /**
   * Distance au contour le plus proche, en mètres. Les degrés sont projetés
   * localement (équirectangulaire) : à l'échelle d'un territoire, l'erreur est
   * négligeable devant la tolérance de simplification des contours (~220 m).
   */
  function distanceAuContourM(lon, lat, geometrie) {
    if (!geometrie) return Infinity;
    const rad = Math.PI / 180;
    const metresParDegreLat = 111320;
    const metresParDegreLon = 111320 * Math.cos(lat * rad);
    const px = lon * metresParDegreLon;
    const py = lat * metresParDegreLat;

    let minimum = Infinity;
    const polygones =
      geometrie.type === "Polygon" ? [geometrie.coordinates] :
      geometrie.type === "MultiPolygon" ? geometrie.coordinates : [];

    for (const polygone of polygones) {
      for (const anneau of polygone) {
        for (let i = 0, j = anneau.length - 1; i < anneau.length; j = i++) {
          const ax = anneau[j][0] * metresParDegreLon, ay = anneau[j][1] * metresParDegreLat;
          const bx = anneau[i][0] * metresParDegreLon, by = anneau[i][1] * metresParDegreLat;
          const dx = bx - ax, dy = by - ay;
          const longueur = dx * dx + dy * dy;
          const t = longueur === 0 ? 0
            : Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / longueur));
          const distance = Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
          if (distance < minimum) minimum = distance;
        }
      }
    }
    return minimum;
  }

  function bbox(geometrie) {
    let xmin = Infinity, ymin = Infinity, xmax = -Infinity, ymax = -Infinity;
    const polygones =
      geometrie.type === "Polygon" ? [geometrie.coordinates] :
      geometrie.type === "MultiPolygon" ? geometrie.coordinates : [];
    for (const polygone of polygones) {
      for (const [x, y] of polygone[0]) {
        if (x < xmin) xmin = x;
        if (x > xmax) xmax = x;
        if (y < ymin) ymin = y;
        if (y > ymax) ymax = y;
      }
    }
    return [xmin, ymin, xmax, ymax];
  }

  /* ------------------------------------------------------------------ *
   * Référentiel
   * ------------------------------------------------------------------ */

  /**
   * Rassemble tout ce à quoi un candidat est confronté :
   *   - les localités GRID3 (référence extérieure, jamais modifiée) ;
   *   - les villages de la base interne (l'export en cours) ;
   *   - les limites administratives ;
   *   - les décisions déjà prises.
   *
   * Les points sont indexés par cellules géographiques et par clés
   * phonétiques, calculées ici une fois pour toutes.
   */
  function Referentiel() {
    this.points = [];
    this.cellules = new Map();
    this.parCle = new Map();
    this.limites = { provinces: [], territoires: [] };
    this.decisions = [];
  }

  Referentiel.prototype._indexer = function (indice) {
    const point = this.points[indice];
    const cle = Math.floor(point.lat / PAS_CELLULE) + "|" + Math.floor(point.lon / PAS_CELLULE);
    if (!this.cellules.has(cle)) this.cellules.set(cle, []);
    this.cellules.get(cle).push(indice);

    for (const cleNom of point.analyse.cles) {
      if (!this.parCle.has(cleNom)) this.parCle.set(cleNom, []);
      this.parCle.get(cleNom).push(indice);
    }
  };

  Referentiel.prototype.ajouterPoint = function (point) {
    point.analyse = Noms.analyser(point.nom, { retirerGroupement: point.source !== "grid3" });
    if (point.alt) {
      // Le nom alternatif de GRID3 est une graphie à part entière : il doit
      // permettre de retrouver le point, au même titre que le nom principal.
      for (const cle of Noms.clesBlocage(point.alt)) {
        if (!point.analyse.cles.includes(cle)) point.analyse.cles.push(cle);
      }
    }
    this.points.push(point);
    this._indexer(this.points.length - 1);
    return this.points.length - 1;
  };

  /** Charge un fichier ref/<province>.json (format compact). */
  Referentiel.prototype.ajouterProvinceGrid3 = function (donnees) {
    const c = donnees.colonnes;
    const iId = c.indexOf("id"), iNom = c.indexOf("nom"), iAlt = c.indexOf("alt");
    const iLat = c.indexOf("lat"), iLon = c.indexOf("lon"), iType = c.indexOf("type");
    const iZs = c.indexOf("zs"), iAs = c.indexOf("as"), iTerr = c.indexOf("terr");
    const iPrec = c.indexOf("prec");
    const valeur = (table, indice) => (indice >= 0 && table[indice] !== undefined ? table[indice] : "");

    for (const ligne of donnees.points) {
      this.ajouterPoint({
        source: "grid3",
        id: ligne[iId],
        nom: ligne[iNom],
        alt: ligne[iAlt],
        lat: ligne[iLat],
        lon: ligne[iLon],
        type: valeur(donnees.types, ligne[iType]),
        zoneSante: valeur(donnees.zs, ligne[iZs]),
        aireSante: valeur(donnees.as, ligne[iAs]),
        territoire: valeur(donnees.terr, ligne[iTerr]),
        province: donnees.province,
        precision: ligne[iPrec],
      });
    }
  };

  /** Charge la base interne (data/villages.geojson). */
  Referentiel.prototype.ajouterBaseInterne = function (geojson, champs) {
    const noms = Object.assign(
      { nom: "Village", province: "Province", territoire: "Territory", id: "Village_id" },
      champs || {}
    );
    for (const feature of geojson.features) {
      const [lon, lat] = feature.geometry.coordinates;
      const p = feature.properties || {};
      this.ajouterPoint({
        source: "base",
        id: p[noms.id] || "",
        nom: p[noms.nom] || "",
        alt: "",
        lat: lat,
        lon: lon,
        type: "",
        zoneSante: "",
        aireSante: "",
        territoire: p[noms.territoire] || "",
        province: p[noms.province] || "",
        precision: null,
        proprietes: p,
      });
    }
  };

  Referentiel.prototype.ajouterLimites = function (niveau, geojson) {
    this.limites[niveau] = geojson.features.map((f) => ({
      nom: f.properties.nom,
      province: f.properties.province || f.properties.nom,
      pcode: f.properties.pcode,
      geometrie: f.geometry,
      bbox: bbox(f.geometry),
    }));
  };

  Referentiel.prototype.ajouterDecisions = function (lignes) {
    this.decisions = lignes.map((ligne) =>
      Object.assign({}, ligne, {
        analyse: Noms.analyser(ligne.nom_propose, { retirerGroupement: true }),
        lat: parseFloat(ligne.latitude),
        lon: parseFloat(ligne.longitude),
      })
    );
  };

  /** Indices des points situés dans les cellules voisines d'une position. */
  Referentiel.prototype.voisinage = function (lat, lon) {
    const ligne = Math.floor(lat / PAS_CELLULE);
    const colonne = Math.floor(lon / PAS_CELLULE);
    const indices = [];
    for (let dl = -1; dl <= 1; dl++) {
      for (let dc = -1; dc <= 1; dc++) {
        const cellule = this.cellules.get((ligne + dl) + "|" + (colonne + dc));
        if (cellule) indices.push(...cellule);
      }
    }
    return indices;
  };

  /** Unité administrative contenant un point, au niveau demandé. */
  Referentiel.prototype.unite = function (niveau, lat, lon) {
    for (const unite of this.limites[niveau]) {
      const [xmin, ymin, xmax, ymax] = unite.bbox;
      if (lon < xmin || lon > xmax || lat < ymin || lat > ymax) continue;
      if (dansGeometrie(lon, lat, unite.geometrie)) return unite;
    }
    return null;
  };

  /* ------------------------------------------------------------------ *
   * Les huit contrôles
   * ------------------------------------------------------------------ */

  function drapeau(code, gravite, message, details) {
    return {
      code: code,
      intitule: CONTROLES[code],
      gravite: gravite,
      message: message,
      details: details || null,
    };
  }

  function dansEmprise(lat, lon) {
    return lat >= SEUILS.latMin && lat <= SEUILS.latMax &&
           lon >= SEUILS.lonMin && lon <= SEUILS.lonMax;
  }

  /** Nombre de décimales écrites, qui dit la précision revendiquée. */
  function decimales(valeur) {
    const texte = String(valeur).trim();
    const point = texte.indexOf(".");
    return point < 0 ? 0 : texte.length - point - 1;
  }

  function cleComparaison(texte) {
    return Noms.normaliser(texte).replace(/\s+/g, "");
  }

  /**
   * Applique les huit contrôles à un candidat.
   *
   * candidat : { nom, lat, lon, province, territoire, latBrute, lonBrute }
   *   latBrute / lonBrute sont les chaînes telles qu'écrites dans le fichier
   *   source : c'est d'elles qu'on lit le nombre de décimales (C3), une fois
   *   converties en nombre l'information est perdue.
   */
  function controler(candidat, referentiel, options) {
    const reglages = Object.assign({}, SEUILS, options || {});
    const drapeaux = [];
    const voisins = [];
    const lat = candidat.lat;
    const lon = candidat.lon;
    const analyse = Noms.analyser(candidat.nom, { retirerGroupement: true });

    /* --- C1 : coordonnées lisibles et en RDC ------------------------- */
    const coordonneesValides =
      Number.isFinite(lat) && Number.isFinite(lon) && !(lat === 0 && lon === 0);

    if (!coordonneesValides) {
      drapeaux.push(drapeau("C1", "rouge",
        lat === 0 && lon === 0
          ? "Coordonnées à 0, 0 — c'est le golfe de Guinée, pas la RDC."
          : "Coordonnées absentes ou illisibles."));
    } else if (!dansEmprise(lat, lon)) {
      drapeaux.push(drapeau("C1", "rouge",
        `Point hors de la RDC (${lat.toFixed(4)}, ${lon.toFixed(4)}).`,
        { attendu: `latitude ${reglages.latMin} à ${reglages.latMax}, ` +
                   `longitude ${reglages.lonMin} à ${reglages.lonMax}` }));

      /* --- C2 : inversion latitude / longitude ----------------------- */
      if (dansEmprise(lon, lat)) {
        drapeaux.push(drapeau("C2", "rouge",
          "En échangeant latitude et longitude, le point retombe en RDC : " +
          "les deux colonnes sont probablement inversées.",
          { correction: { lat: lon, lon: lat } }));
      }
    }

    if (!coordonneesValides) {
      return conclure(candidat, analyse, drapeaux, voisins, null, null);
    }

    /* --- C3 : précision revendiquée ---------------------------------- */
    const decimalesEcrites = Math.min(
      decimales(candidat.latBrute !== undefined ? candidat.latBrute : lat),
      decimales(candidat.lonBrute !== undefined ? candidat.lonBrute : lon)
    );
    if (decimalesEcrites < reglages.decimalesMin) {
      const metres = Math.round(111320 / Math.pow(10, decimalesEcrites));
      drapeaux.push(drapeau("C3", "orange",
        `Coordonnées à ${decimalesEcrites} décimale${decimalesEcrites > 1 ? "s" : ""} : ` +
        `la position n'est connue qu'à environ ${metres >= 1000 ? (metres / 1000).toFixed(1) + " km" : metres + " m"} près.`,
        { decimales: decimalesEcrites, incertitudeM: metres }));
    }

    /* --- C4 : cohérence administrative ------------------------------- */
    let provinceReelle = null;
    let territoireReel = null;
    if (dansEmprise(lat, lon)) {
      provinceReelle = referentiel.unite("provinces", lat, lon);
      territoireReel = referentiel.unite("territoires", lat, lon);

      // `annonce` porte l'accord : « Province déclarée », « Territoire déclaré ».
      const verifier = (niveau, declare, reelle, annonce) => {
        if (!declare || !reelle) return;
        if (cleComparaison(declare) === cleComparaison(reelle.nom)) return;
        const distance = distanceAuContourM(lon, lat, reelle.geometrie);
        if (distance < reglages.limiteAdminM) {
          drapeaux.push(drapeau("C4", "orange",
            `${annonce} « ${declare} », mais le point tombe dans ` +
            `« ${reelle.nom} » — à ${Math.round(distance)} m de la limite, ` +
            "l'écart peut venir du contour simplifié.",
            { niveau: niveau, declare: declare, reelle: reelle.nom, distanceLimiteM: distance }));
        } else {
          drapeaux.push(drapeau("C4", "rouge",
            `${annonce} « ${declare} », mais le point est à ` +
            `${Math.round(distance)} m à l'intérieur de « ${reelle.nom} ».`,
            { niveau: niveau, declare: declare, reelle: reelle.nom, distanceLimiteM: distance }));
        }
      };

      verifier("provinces", candidat.province, provinceReelle, "Province déclarée");
      verifier("territoires", candidat.territoire, territoireReel, "Territoire déclaré");

      if (candidat.province && !provinceReelle) {
        drapeaux.push(drapeau("C4", "orange",
          "Le point ne tombe dans aucune province : il est probablement " +
          "juste au-delà d'une frontière ou sur un lac."));
      }
    }

    /* --- C5 et C6 : voisinage ---------------------------------------- */
    for (const indice of referentiel.voisinage(lat, lon)) {
      const point = referentiel.points[indice];
      const distance = distanceM(lat, lon, point.lat, point.lon);
      if (distance > reglages.voisinageM) continue;
      const comparaison = Noms.comparer(analyse, point.analyse);
      voisins.push({ point: point, distanceM: distance, comparaison: comparaison });
    }
    voisins.sort((a, b) => a.distanceM - b.distanceM);

    const tresProches = voisins.filter((v) => v.distanceM <= reglages.doublonM);
    if (tresProches.length) {
      const memeNom = tresProches.filter(
        (v) => v.comparaison.verdict === "identique" || v.comparaison.verdict === "variante");
      if (memeNom.length) {
        const v = memeNom[0];
        drapeaux.push(drapeau("C5", "rouge",
          `« ${v.point.nom} » est à ${Math.round(v.distanceM)} m et porte le même nom : ` +
          "c'est très probablement le même village.",
          { voisin: v.point, distanceM: v.distanceM, similarite: v.comparaison.score }));
      } else {
        // « Amati 1 » à 200 m d'« Amati 9 » n'est pas un doublon : le
        // qualificatif de rang dit précisément que ce sont deux villages.
        // Les écarter ici évite le faux positif que C6 vient ensuite expliquer.
        const inexpliques = tresProches.filter((v) => !v.comparaison.qualificatifsDifferents);
        if (inexpliques.length) {
          const v = inexpliques[0];
          drapeaux.push(drapeau("C5", "orange",
            `${inexpliques.length} localité${inexpliques.length > 1 ? "s" : ""} déjà connue` +
            `${inexpliques.length > 1 ? "s" : ""} à moins de ${reglages.doublonM} m ` +
            `(la plus proche : « ${v.point.nom} », ${Math.round(v.distanceM)} m) — ` +
            "nom différent, à confirmer sur la photo satellite.",
            { nombre: inexpliques.length, plusProche: v.point, distanceM: v.distanceM }));
        }
      }
    }

    const concordants = voisins.filter(
      (v) => v.distanceM > reglages.doublonM &&
             (v.comparaison.verdict === "identique" || v.comparaison.verdict === "variante"));
    if (concordants.length) {
      const v = concordants[0];
      drapeaux.push(drapeau("C6", "orange",
        `« ${v.point.nom} » porte le même nom à ${Math.round(v.distanceM)} m : ` +
        "même village relevé deux fois, ou deux villages homonymes voisins ?",
        { voisin: v.point, distanceM: v.distanceM, similarite: v.comparaison.score }));
    }

    const memeBase = voisins.filter((v) => v.comparaison.qualificatifsDifferents);
    if (memeBase.length) {
      const v = memeBase[0];
      drapeaux.push(drapeau("C6", "info",
        `« ${v.point.nom} » est à ${Math.round(v.distanceM)} m : même nom de base, ` +
        "qualificatif différent — deux villages distincts, pas un doublon.",
        { voisin: v.point, distanceM: v.distanceM }));
    }

    /* --- C7 : homonyme ailleurs dans le même territoire --------------- */
    const territoireCandidat = candidat.territoire ||
      (territoireReel ? territoireReel.nom : "");
    if (territoireCandidat) {
      const dejaVus = new Set();
      const homonymes = [];
      for (const cle of analyse.cles) {
        for (const indice of referentiel.parCle.get(cle) || []) {
          if (dejaVus.has(indice)) continue;
          dejaVus.add(indice);
          const point = referentiel.points[indice];
          if (!point.territoire) continue;
          if (cleComparaison(point.territoire) !== cleComparaison(territoireCandidat)) continue;
          const distance = distanceM(lat, lon, point.lat, point.lon);
          if (distance <= reglages.homonymeM) continue;   // déjà traité par C5/C6
          const comparaison = Noms.comparer(analyse, point.analyse);
          if (comparaison.verdict === "identique" || comparaison.verdict === "variante") {
            homonymes.push({ point: point, distanceM: distance });
          }
        }
      }
      if (homonymes.length) {
        homonymes.sort((a, b) => a.distanceM - b.distanceM);
        const h = homonymes[0];
        drapeaux.push(drapeau("C7", "orange",
          `${homonymes.length} village${homonymes.length > 1 ? "s" : ""} de même nom ` +
          `dans le territoire de ${territoireCandidat}, le plus proche à ` +
          `${(h.distanceM / 1000).toFixed(1)} km. Les homonymes sont fréquents en RDC : ` +
          "à confirmer, ce n'est pas une erreur en soi.",
          { nombre: homonymes.length, plusProche: h.point, distanceM: h.distanceM }));
      }
    }

    /* --- C8 : décision antérieure ------------------------------------ */
    for (const decision of referentiel.decisions) {
      const memePlace = Number.isFinite(decision.lat) && Number.isFinite(decision.lon) &&
        distanceM(lat, lon, decision.lat, decision.lon) <= reglages.doublonM;
      const memeNom = Noms.comparer(analyse, decision.analyse).verdict !== "different";
      if (!memePlace || !memeNom) continue;
      drapeaux.push(drapeau("C8", decision.verdict === "rejete" ? "orange" : "info",
        `Déjà arbitré le ${decision.date || "?"} : ${decision.verdict}` +
        (decision.motif ? ` — « ${decision.motif} »` : "."),
        { decision: decision }));
      break;
    }

    return conclure(candidat, analyse, drapeaux, voisins, provinceReelle, territoireReel);
  }

  function conclure(candidat, analyse, drapeaux, voisins, provinceReelle, territoireReel) {
    const pire = drapeaux.reduce(
      (max, d) => Math.max(max, GRAVITES[d.gravite] || 0), 0);
    const verdict = pire >= GRAVITES.rouge ? "rouge"
      : pire >= GRAVITES.orange ? "orange"
      : "vert";

    return {
      candidat: candidat,
      analyse: analyse,
      verdict: verdict,
      libelleVerdict: {
        vert: "Nouveau village probable",
        orange: "À vérifier",
        rouge: "Doublon probable ou coordonnées invalides",
      }[verdict],
      drapeaux: drapeaux,
      voisins: voisins,
      provinceReelle: provinceReelle ? provinceReelle.nom : null,
      territoireReel: territoireReel ? territoireReel.nom : null,
    };
  }

  global.Controle = {
    Referentiel: Referentiel,
    controler: controler,
    distanceM: distanceM,
    dansGeometrie: dansGeometrie,
    distanceAuContourM: distanceAuContourM,
    dansEmprise: dansEmprise,
    decimales: decimales,
    SEUILS: SEUILS,
    CONTROLES: CONTROLES,
    PAS_CELLULE: PAS_CELLULE,
  };
})(typeof window !== "undefined" ? window : globalThis);
