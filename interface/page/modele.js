/* Onglet « Modèle lu dans le SysML » (et page /modele).
   Tout ce qui est dessiné vient de /api/modele, qui ne lit que le texte des codes .sysml
   (usershaker2sysml/modele_sysml.py) : rien ne vient de l'Excel ni du traducteur.
   Quatre vues : rubans personas -> cas d'usage -> besoins, parcours d'un cas d'usage, graphe des états d'un composant,
   traçabilité besoins -> étapes -> cas d'usage. Les trois premières ont aussi une forme technique, en colonnes (« Vue technique »). Les dessins suivent la largeur de leur zone (ResizeObserver).
   Un clic sur un élément ouvre sa fiche : nom SysML, id UserShaker, fichier et ligne du code, extrait.
   Utilisation : RMonieModele.monter(element, {jeton}) ou RMonieModele.monter(element, {fichiers: [{nom, texte}]}). */
(() => {
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const nb = n => Number(n).toLocaleString("fr-FR");
  const GENRES = {
    persona: ["Persona", "var(--mo-persona)", n => `part ${n.nom} : Persona`],
    composant: ["Composant", "var(--mo-composant)", n => `part def ${n.nom}`],
    etat: ["État de composant", "var(--mo-etat)", n => `élément de « states » du composant`],
    besoin: ["Besoin utilisateur", "var(--mo-besoin)", n => `requirement ${n.nom}`],
    cas: ["Cas d'usage", "var(--mo-cas)", n => `use case def ${n.nom}`],
    etape: ["Étape", "var(--mo-etape)", n => `action ${n.nom}`],
  };
  // validée (écarts daltonisme et vision normale) par le contrôle de palette ; le premier ton est le ruban du logo
  const COULEURS_CAS = ["#C9304F", "#2176B8", "#C07A0C", "#6B4DB8", "#0E8C74", "#8C3A9E"];
  const COULEURS_PERSONAS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"];   // celles de analyses.js
  // relations : [libellé vu depuis la source, libellé vu depuis la cible]
  const RELATIONS = {
    acteur: ["Acteur de", "Acteurs"], contient: ["Étapes", "Dans le cas d'usage"],
    suit: ["Suivie de", "Après"], satisfait: ["Satisfait", "Satisfait par"],
    etat_de: ["États", "État de"], met_dans: ["Met dans l'état", "Mis dans cet état par"],
    declenche: ["Déclenche", "Déclenchée quand"], condition: ["Condition de", "Conditions"],
    ressent: ["Ressentis", "Ressentis"],
  };

  function couper(texte, max, lignes = 2){
    const mots = String(texte ?? "").split(/\s+/).filter(Boolean), out = [];
    let cur = "";
    for (const m of mots){
      if ((cur + " " + m).trim().length <= max) cur = (cur + " " + m).trim();
      else { if (cur) out.push(cur); cur = m.length > max ? m.slice(0, max - 1) + "…" : m; }
      if (out.length === lignes) break;
    }
    if (out.length < lignes && cur) out.push(cur);
    if (out.length === lignes && mots.join(" ").length > out.join(" ").length + 1){
      const d = out[lignes - 1]; out[lignes - 1] = (d.length > max - 1 ? d.slice(0, max - 1) : d) + "…";
    }
    return out.length ? out : [""];
  }
  const couleurScore = s => s == null ? "#9b8f94" : s >= 3 ? "#1e7f47" : s >= 1 ? "#5ea36f" : s === 0 ? "#9b8f94" : s >= -2 ? "#d0802f" : "#c0392b";

  function monter(racine, options){
    racine.classList.add("mo");
    const E = {G: null, N: {}, sortants: {}, entrants: {}, vue: "ensemble", style: "technique", cas: null, comp: null, sel: null, plein: false,
               textes: {}, source: options.fichiers ? "fichiers" : "session", jeton: options.jeton};
    const entree = document.createElement("input");
    entree.type = "file"; entree.accept = ".sysml"; entree.multiple = true; entree.hidden = true;
    entree.addEventListener("change", () => { if (entree.files.length) lireFichiers([...entree.files]); entree.value = ""; });

    async function lireFichiers(fs){
      const fichiers = await Promise.all(fs.map(async f => ({nom: f.name, texte: await f.text()})));
      E.source = "fichiers"; E.fichiers = fichiers;
      charger();
    }

    async function appeler(chemin){
      const r = E.source === "fichiers"
        ? await fetch(chemin, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({fichiers: E.fichiers})})
        : await fetch(`${chemin}?jeton=${encodeURIComponent(E.jeton)}`);
      const d = await r.json().catch(() => ({erreur: `réponse illisible du serveur (${r.status})`}));
      if (!r.ok || d.erreur) throw new Error(d.erreur || `erreur ${r.status}`);
      return d;
    }

    async function charger(){
      racine.innerHTML = '<p class="mo-explic">Lecture des codes SysML…</p>';
      try {
        const G = await appeler("/api/modele");
        preparer(G);
        dessinerTout();
        controlerGrammaire();
      } catch (e){
        racine.innerHTML = `<div class="mo-erreur">Lecture impossible : ${esc(e.message)}</div>`;
        racine.append(entree);
      }
    }

    async function controlerGrammaire(){
      const z = racine.querySelector("[data-grammaire]");
      if (!z) return;
      try {
        const c = await appeler("/api/grammaire");
        if (!c.disponible){ z.className = "mo-pastille"; z.innerHTML = `<i></i>Grammaire OMG : SysML2Tools non installé (contrôle facultatif)`; z.title = c.detail; return; }
        if (c.ok === null){ z.className = "mo-pastille att"; z.innerHTML = `<i></i>Grammaire OMG : contrôle non abouti`; z.title = c.detail; return; }
        const nerr = c.erreurs.filter(e => e.gravite === "erreur").length;
        z.className = "mo-pastille " + (c.ok ? "ok" : "err");
        z.innerHTML = c.ok ? `<i></i>Grammaire SysML v2 de l'OMG : 0 erreur sur ${c.fichiers} fichier${c.fichiers > 1 ? "s" : ""} (SysML2Tools)`
                           : `<i></i>Grammaire OMG : ${nerr} erreur${nerr > 1 ? "s" : ""} (SysML2Tools)`;
        z.title = c.ok ? c.detail : c.erreurs.slice(0, 8).map(e => `${e.fichier} ligne ${e.ligne} : ${e.message}`).join("\n");
      } catch (e){ z.className = "mo-pastille att"; z.innerHTML = `<i></i>Grammaire OMG : ${esc(e.message)}`; }
    }

    function preparer(G){
      E.G = G; E.N = {}; E.sortants = {}; E.entrants = {}; E.textes = G.textes || {};
      G.noeuds.forEach(n => { E.N[n.cle] = n; E.sortants[n.cle] = []; E.entrants[n.cle] = []; });
      G.liens.forEach(l => { E.sortants[l.de]?.push(l); E.entrants[l.vers]?.push(l); });
      E.couleurCas = {};
      G.cas_usage.forEach((u, k) => E.couleurCas[u.cle] = COULEURS_CAS[k % COULEURS_CAS.length]);
      E.numCas = {}; G.cas_usage.forEach((u, k) => E.numCas[u.cle] = k + 1);
      if (!E.cas || !E.N[E.cas]) E.cas = G.cas_usage[0]?.cle || null;
      const comps = G.noeuds.filter(n => n.type === "composant");
      if (!E.comp || !E.N[E.comp]) E.comp = comps[0]?.cle || null;
      E.sel = null;
    }

    // ---------------------------------------------------------------- cadre
    function dessinerTout(){
      const G = E.G, F = G.fichiers;
      const fichiersTxt = F.map(f => `<code title="${esc(f.package)} : ${nb(f.lignes)} lignes, ${nb(f.caracteres)} caractères">${esc(f.nom)}</code>`).join("");
      if (!G.noeuds.length){
        racine.innerHTML = `
          <div class="mo-erreur"><b>Aucun élément reconnu dans ${F.length > 1 ? "ces fichiers" : "ce fichier"}</b> (${F.map(f => esc(f.nom)).join(", ")}).
            Ce lecteur comprend le format écrit par le traducteur R-monie : il ne lit pas un code SysML v2 écrit autrement. Rien n'a été vérifié.</div>
          <div class="mo-actions" style="margin-top:12px"><button class="mo-btn principal" data-action="fichiers">Lire d'autres fichiers .sysml…</button>
            ${E.jeton ? '<button class="mo-btn" data-action="session">Revenir aux codes de la session</button>' : ""}</div>`;
        racine.append(entree);
        return;
      }
      racine.innerHTML = `
        <div class="mo-source">
          <div class="lu">Ce qui suit est <b>lu dans ${F.length} fichier${F.length > 1 ? "s" : ""} SysML v2</b>
            ${E.source === "session" ? "(les codes produits pour ce fichier)" : "(choisis sur ce PC)"} : ${F.length > 6 ? `<details class="mo-fichiers"><summary>voir les ${F.length} fichiers</summary>${fichiersTxt}</details>` : fichiersTxt}</div>
          <div class="mo-actions">
            <button class="mo-btn" data-action="fichiers" title="Afficher n'importe quels codes .sysml produits par le traducteur, par exemple ceux du dossier sortie">Lire des fichiers .sysml…</button>
            ${E.source === "fichiers" && E.jeton ? '<button class="mo-btn" data-action="session">Revenir aux codes de la session</button>' : ""}
            <button class="mo-btn ${E.plein ? "principal" : ""}" data-action="plein" title="${E.plein ? "Échap pour quitter" : "Utiliser tout l'écran"}">${E.plein ? "✕ Quitter le plein écran" : "⛶ Plein écran"}</button>
          </div>
        </div>
        <div class="mo-controle">
          <span class="mo-pastille ${G.avertissements.length ? "att" : "ok"}"><i></i>${G.avertissements.length
            ? `${G.avertissements.length} référence${G.avertissements.length > 1 ? "s" : ""} non retrouvée${G.avertissements.length > 1 ? "s" : ""} dans les codes`
            : "Toutes les références des codes retrouvées (satisfy, acteurs, grilles, déclencheurs)"}</span>
          ${pastilleSyntaxe(G.syntaxe)}
          <span class="mo-pastille attente" data-grammaire><i></i>Grammaire OMG : contrôle en cours…</span>
        </div>
        <div data-syntaxe-extrait></div>
        <div class="mo-compteurs">${Object.entries(G.compteurs).map(([k, v]) => `<span><b>${nb(v)}</b>${esc(k)}</span>`).join("")}</div>
        <div class="mo-barre"><span class="mo-seg">${[["ensemble", "Vue d'ensemble"], ["cas", "Cas d'usage"], ["composant", "Composants"], ["trace", "Traçabilité"]]
          .map(([v, t]) => `<button data-vue="${v}" class="${E.vue === v ? "actif" : ""}">${t}</button>`).join("")}</span>
          <span class="mo-seg" role="group" aria-label="Style des schémas">${[["technique", "Vue technique", "Schémas en colonnes, au plus près du code SysML"], ["ux", "Vue UX", "Schémas de lecture : rubans, parcours, graphe des états"]]
          .map(([v, t, q]) => `<button data-style="${v}" title="${q}">${t}</button>`).join("")}</span>
          <button class="mo-btn" data-action="image" title="Le schéma affiché, en image, pour les slides ou un rapport">Télécharger le schéma (.png)</button></div>
        <div class="mo-corps"><div class="mo-vue" data-vue-zone></div><aside class="mo-fiche" data-fiche></aside></div>
        ${G.avertissements.length ? `<details class="mo-avert"><summary>Références non retrouvées (rien n'a été inventé à leur place)</summary><ul>${
          G.avertissements.map(a => `<li>${esc(a.fichier)}${a.ligne ? ` ligne ${a.ligne}` : ""} : ${esc(a.texte)}</li>`).join("")}</ul></details>` : ""}`;
      racine.querySelector("[data-syntaxe-extrait]").innerHTML = listeSyntaxe(G.syntaxe);
      racine.append(entree);
      if (typeof bulle !== "undefined") racine.append(bulle);
      dessinerVue();
      fiche();
    }

    // Contrôle de syntaxe : une pastille, puis la liste des lignes signalées (clic : extrait du code).
    function diagnosticsSyntaxe(S){ return (S?.diagnostics || []).filter(d => d.gravite !== "info"); }
    function pastilleSyntaxe(S){
      if (!S) return "";
      const n = diagnosticsSyntaxe(S).length;
      if (S.statut === "correct" && !n) return `<span class="mo-pastille ok" title="Contrôle du format produit par le générateur : CATIA reste l'autorité finale"><i></i>Syntaxe : format du générateur respecté</span>`;
      return `<span class="mo-pastille ${S.statut === "erreur" ? "err" : "att"}"><i></i>Syntaxe ${S.statut === "erreur" ? "en erreur" : "à vérifier"} : ${n} signalement${n > 1 ? "s" : ""}</span>`;
    }
    function listeSyntaxe(S){
      const L = diagnosticsSyntaxe(S);
      if (!L.length) return "";
      return `<details class="mo-avert" open><summary>Syntaxe : lignes à regarder (CATIA reste l'autorité finale)</summary><ul>${
        L.map((d, k) => `<li><span class="mo-lien" data-syntaxe="${k}">${esc(d.fichier)}, ligne ${d.ligne}</span> [${esc(d.code)}] ${esc(d.message)}</li>`).join("")}</ul><div data-syntaxe-zone></div></details>`;
    }
    function extraitSyntaxe(k){
      const d = diagnosticsSyntaxe(E.G.syntaxe)[k], zone = racine.querySelector("[data-syntaxe-zone]");
      if (!d || !zone) return;
      zone.innerHTML = extraitHtml(d.fichier, d.ligne);
    }

    function dessinerVue(){
      racine.querySelectorAll("[data-vue]").forEach(b => b.classList.toggle("actif", b.dataset.vue === E.vue));
      const z = racine.querySelector("[data-vue-zone]");
      E.dispo = Math.max(320, z.clientWidth - 4);      // largeur utilisable : les diagrammes s'y adaptent
      E.largeur = z.clientWidth;
      // la traçabilité n'a qu'une forme : le choix du style ne la concerne pas
      racine.querySelectorAll("[data-style]").forEach(b => { b.classList.toggle("actif", b.dataset.style === E.style); b.disabled = E.vue === "trace"; });
      const vues = E.style === "technique" ? {ensemble: vueEnsembleTechnique, cas: vueCasTechnique, composant: vueComposantTechnique, trace: vueTrace}
                                           : {ensemble: vueEnsemble, cas: vueCas, composant: vueComposant, trace: vueTrace};
      z.innerHTML = vues[E.vue]();
      marquerSelection();
      const cle = `${E.style}/${E.vue}/${E.cas}/${E.comp}`;
      if (cle !== E.dernierDessin) animerVue(z);      // pas au simple redimensionnement
      E.dernierDessin = cle;
    }

    // Le schéma se construit sous les yeux quand on change de vue : chevrons, courbes et rubans.
    function animerVue(z){
      if (matchMedia("(prefers-reduced-motion: reduce)").matches || !z.animate) return;
      const DOUX = "cubic-bezier(.2,.8,.2,1)";
      z.querySelectorAll(".chevron").forEach((c, k) => c.animate(
        [{opacity: 0, transform: "translateX(-12px)"}, {opacity: 1, transform: "none"}],
        {duration: 320, delay: Math.min(k * 45, 500), easing: DOUX, fill: "backwards"}));
      z.querySelectorAll(".courbe,.transition").forEach(p => {
        const L = p.getTotalLength();
        if (L > 0) p.animate([{strokeDasharray: L, strokeDashoffset: L}, {strokeDasharray: L, strokeDashoffset: 0}], {duration: 850, delay: 180, easing: "ease-in-out", fill: "backwards"});
      });
      if (E.style === "technique") z.querySelectorAll(".nd").forEach((n, k) => n.animate([{opacity: 0}, {opacity: 1}], {duration: 260, delay: Math.min(k * 18, 360), fill: "backwards"}));
      z.querySelectorAll(".flux").forEach((f, k) => f.animate([{opacity: 0}, {opacity: getComputedStyle(f).opacity}], {duration: 450, delay: Math.min(k * 14, 450), easing: DOUX, fill: "backwards"}));
    }

    // ---------------------------------------------------------------- dessin en colonnes
    // cols : [{titre, sections: [{titre?, noeuds: [{cle, titre, sous?, couleur?, alerte?}]}]}] ; aretes : [{a, b, classe, label?}]
    function colonnes(cols, aretes, o = {}){
      const PAD = 16, HAUT = 36, n = cols.length, GMIN = o.ecart || 120;
      let W = o.largeur || 220, G = GMIN;
      if (E.dispo){                                   // remplir la place : boîtes plus larges, puis écarts plus grands
        W = Math.max(W, Math.min(o.largeurMax || 360, Math.floor((E.dispo - 2 * PAD - (n - 1) * GMIN) / n)));
        if (n > 1) G = Math.max(GMIN, Math.floor((E.dispo - 2 * PAD - n * W) / (n - 1)));
      }
      let x = PAD, hMax = 0;
      const pos = {}, morceaux = [];
      cols.forEach((col, ci) => {
        let y = HAUT;
        morceaux.push(`<text class="entete-col" x="${x}" y="22">${esc(couper(col.titre, Math.floor(W / 7.6), 1)[0])}</text>`);
        col.sections.forEach(sec => {
          if (sec.titre){ morceaux.push(`<text class="entete-col" x="${x}" y="${y + 14}" style="font-size:11px"><title>${esc(sec.titre)}</title>${esc(couper(sec.titre, Math.floor(W / 7.4), 1)[0])}</text>`); y += 24; }
          sec.noeuds.forEach(n => {
            const lt = couper(n.titre, Math.floor((W - 22) / 6.7), n.lignes || 2);
            const ls = n.sous ? couper(n.sous, Math.floor((W - 22) / 6.1), 1) : [];
            const h = 12 + lt.length * 15 + ls.length * 14;
            pos[n.cle + "@" + ci] = {x, y, w: W, h};
            pos[n.cle] = pos[n.cle] || pos[n.cle + "@" + ci];
            morceaux.push(boite(n, x, y, W, h, lt, ls));
            y += h + (o.vertical || 9);
          });
          y += 10;
        });
        hMax = Math.max(hMax, y);
        x += W + G;
      });
      const traits = aretes.map(e => {
        const A = pos[e.a + "@" + e.ca] || pos[e.a], B = pos[e.b + "@" + e.cb] || pos[e.b];
        if (!A || !B) return "";
        const [g, d] = A.x <= B.x ? [A, B] : [B, A];
        const x1 = g.x + g.w, y1 = g.y + g.h / 2, x2 = d.x, y2 = d.y + d.h / 2, dx = Math.max(40, (x2 - x1) / 2);
        const info = `${lib(e.a)} → ${lib(e.b)}${e.label ? " : " + e.label : ""}`;
        return `<path class="ar ${e.classe || ""}" data-a="${esc(e.a)}" data-b="${esc(e.b)}" d="M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}"><title>${esc(info)}</title></path>`;
      }).join("");
      const w = x - G + PAD, h = hMax + PAD;
      return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" style="width:100%;height:auto;max-width:${w}px" role="img" aria-label="${esc(o.titre || "diagramme du modèle")}">${traits}${morceaux.join("")}</svg>`;
    }

    function boite(n, x, y, w, h, lt, ls){
      const coul = n.couleur || GENRES[E.N[n.cle]?.type]?.[1] || "#999";
      return `<g class="nd${n.alerte ? " alerte" : ""}" data-cle="${esc(n.cle)}" tabindex="0">
        <title>${esc(n.infobulle || n.titre)}</title>
        <rect class="fond" x="${x}" y="${y}" width="${w}" height="${h}" rx="7"/>
        <rect class="barre" x="${x}" y="${y}" width="5" height="${h}" rx="2" style="fill:${coul}"/>
        ${lt.map((t, k) => `<text class="titre" x="${x + 13}" y="${y + 19 + k * 15}">${esc(t)}</text>`).join("")}
        ${ls.map((t, k) => `<text class="sous" x="${x + 13}" y="${y + 19 + lt.length * 15 + k * 14 - 1}">${esc(t)}</text>`).join("")}
      </g>`;
    }

    const lib = c => E.N[c]?.libelle || c;
    const noeudsDe = type => E.G.noeuds.filter(n => n.type === type);
    const etiquetteEtape = c => { const n = E.N[c]; return `UC${E.numCas[n.cas]} · ${n.position}. ${n.libelle}`; };

    // ---------------------------------------------------------------- vue d'ensemble : les rubans
    // Personas -> cas d'usage -> besoins. La largeur d'un ruban vaut le nombre d'étapes : présence de la persona
    // (ses ressentis) à gauche, étapes qui satisfont le besoin à droite.
    function vueEnsemble(){
      const U = E.G.cas_usage, D = Math.max(E.dispo, 620), PAD = 14, BARRE = 12, HAUT = 34;
      const flux = [];
      U.forEach(u => {
        const c = E.couleurCas[u.cle], parP = new Map(u.acteurs.map(p => [p, 0])), parB = new Map();
        u.etapes.forEach(e => {
          E.N[e].ressentis.forEach(r => { if (r.persona && !r.absent && parP.has(r.persona)) parP.set(r.persona, parP.get(r.persona) + 1); });
          E.sortants[e].filter(l => l.type === "satisfait").forEach(l => parB.set(l.vers, (parB.get(l.vers) || 0) + 1));
        });
        parP.forEach((n, p) => flux.push({a: p, b: u.cle, n: Math.max(n, 1), c, cote: "g", info: `${lib(p)} joue dans « ${lib(u.cle)} » : présente à ${n} étape${n > 1 ? "s" : ""}`}));
        parB.forEach((n, b) => flux.push({a: u.cle, b, n, c, cote: "d", info: `« ${lib(u.cle)} » satisfait « ${lib(b)} » par ${n} étape${n > 1 ? "s" : ""}`}));
      });
      // gros projet : la largeur par étape diminue, pour que les rubans tiennent sur environ 620 px de haut
      const parCote = c => flux.filter(f => f.cote === c).reduce((t, f) => t + f.n, 0);
      const UNITE = Math.max(1, Math.min(5.5, 620 / Math.max(parCote("g"), parCote("d"), 1)));
      const somme = (cle, cote, sens) => flux.filter(f => f.cote === cote && f[sens] === cle).reduce((t, f) => t + f.n, 0) * UNITE;
      const rang = {}; U.forEach((u, k) => rang[u.cle] = k);
      const centre = b => { const L = flux.filter(f => f.b === b); return L.length ? L.reduce((t, f) => t + rang[f.a] * f.n, 0) / L.reduce((t, f) => t + f.n, 0) : 99; };
      const personas = noeudsDe("persona").map(n => ({n, h: Math.max(somme(n.cle, "g", "a"), 6)}));
      const cas = U.map(u => ({n: E.N[u.cle], h: Math.max(somme(u.cle, "g", "b"), somme(u.cle, "d", "a"), 6)}));
      const besoins = noeudsDe("besoin").sort((a, b) => centre(a.cle) - centre(b.cle)).map(n => ({n, h: Math.max(somme(n.cle, "d", "b"), 6)}));
      const total = L => L.reduce((t, x) => t + x.h, 0);
      const H = Math.max(total(personas) + 26 * personas.length, total(cas) + 40 * cas.length, total(besoins) + 34 * besoins.length, 380);
      const placer = L => {
        const gap = L.length > 1 ? (H - total(L)) / (L.length - 1) : 0;
        let y = HAUT + (L.length > 1 ? 0 : (H - total(L)) / 2);
        L.forEach(x => { x.y = y; x.lg = x.y; x.ld = x.y; y += x.h + gap; });
      };
      [personas, cas, besoins].forEach(placer);
      const LAB = Math.min(280, Math.max(150, D * .24));
      const xP = PAD + LAB, xB = D - PAD - LAB - BARRE, xU = Math.round((xP + xB) / 2 - BARRE / 2);
      const pos = {}; [...personas, ...cas, ...besoins].forEach(x => pos[x.n.cle] = x);
      const yMilieu = c => pos[c].y + pos[c].h / 2;
      const ordre = [...flux].sort((f, g) => f.cote === g.cote ? (yMilieu(f.a) - yMilieu(g.a)) || (yMilieu(f.b) - yMilieu(g.b)) : 0);
      let rubans = "";
      ordre.forEach(f => {
        const e = f.n * UNITE, A = pos[f.a], B = pos[f.b], x1 = (f.cote === "g" ? xP : xU) + BARRE, x2 = f.cote === "g" ? xU : xB;
        const y1 = A.ld, y2 = B.lg, m = (x1 + x2) / 2;
        A.ld += e; B.lg += e;
        rubans += `<path class="ar flux" style="--c:${f.c}" data-a="${esc(f.a)}" data-b="${esc(f.b)}" data-bulle="${esc(f.info)}"
          d="M${x1},${y1} C${m},${y1} ${m},${y2} ${x2},${y2} L${x2},${y2 + e} C${m},${y2 + e} ${m},${y1 + e} ${x1},${y1 + e} Z"/>`;
      });
      const noeud = (x, xb, couleur, etiquette) => `<g class="nd" data-cle="${esc(x.n.cle)}" tabindex="0">
        <title>${esc(x.n.libelle)}</title>${etiquette}
        <rect class="plein" x="${xb}" y="${x.y}" width="${BARRE}" height="${x.h}" style="--c:${couleur}"/></g>`;
      const lignes = (t, xt, yc, ancre, max) => {
        const L = couper(t, max, 2), y0 = yc - (L.length - 1) * 7.5 + 4;
        return L.map((m, k) => `<text class="titre lisible" x="${xt}" y="${y0 + k * 15}" text-anchor="${ancre}">${esc(m)}</text>`).join("");
      };
      const maxCar = Math.floor((LAB - 12) / 6.7);
      const dessinP = personas.map(x => noeud(x, xP, "var(--vin,#6E2033)", lignes(x.n.libelle, xP - 10, x.y + x.h / 2, "end", maxCar))).join("");
      const dessinB = besoins.map(x => noeud(x, xB, "var(--vin,#6E2033)", lignes(x.n.libelle, xB + BARRE + 10, x.y + x.h / 2, "start", maxCar))).join("");
      const dessinU = cas.map((x, k) => {
        const u = U[k], yc = x.y + x.h / 2, L = couper(`${k + 1}. ${x.n.libelle}`, 26, 2), y0 = yc - (L.length - 1) * 8 - 2;
        return noeud(x, xU, E.couleurCas[u.cle], L.map((m, j) => `<text class="titre lisible" x="${xU + BARRE + 8}" y="${y0 + j * 16}">${esc(m)}</text>`).join("")
          + `<text class="sous lisible" x="${xU + BARRE + 8}" y="${y0 + L.length * 16}">${u.etapes.length} étapes</text>`);
      }).join("");
      const titres = `<text class="sect" x="${xP + BARRE}" y="16" text-anchor="end">Personas</text>
        <text class="sect" x="${xU + BARRE + 8}" y="16">Cas d'usage</text><text class="sect" x="${xB}" y="16">Besoins</text>`;
      const svg = `<svg width="${D}" height="${H + HAUT + PAD}" viewBox="0 0 ${D} ${H + HAUT + PAD}" role="img" aria-label="Personas, cas d'usage et besoins du modèle">${titres}${rubans}${dessinP}${dessinU}${dessinB}</svg>`;
      const comps = noeudsDe("composant").map(c => ({c, cas: U.filter(u => u.grille[c.cle])})).sort((a, b) => b.cas.length - a.cas.length);
      const legende = U.map(u => `<span class="mo-leg"><i style="--c:${E.couleurCas[u.cle]}">${E.numCas[u.cle]}</i>${esc(lib(u.cle))}</span>`).join("");
      const matrice = comps.map(({c, cas: L}) => `<button class="mo-mat-l" data-comp="${esc(c.cle)}" title="Ouvrir le composant ${esc(c.libelle)}">
        <span class="nom">${esc(c.libelle)}<small>${c.etats.length} états</small></span>
        <span class="pts">${U.map(u => `<i class="${L.includes(u) ? "on" : ""}" style="--c:${E.couleurCas[u.cle]}" title="${L.includes(u) ? "Utilisé" : "Absent"} : ${esc(lib(u.cle))}">${L.includes(u) ? E.numCas[u.cle] : ""}</i>`).join("")}</span></button>`).join("");
      return `<p class="mo-explic">Qui joue dans quel cas d'usage (<code>actor</code>), et quels besoins ils servent (<code>satisfy</code>). Un ruban est d'autant plus large qu'il compte d'étapes. Survoler pour suivre, cliquer pour la fiche.</p>
        <div class="mo-dessin">${svg}</div>
        <div class="mo-bloc"><h4>Composants mobilisés par cas d'usage</h4><div class="mo-legende">${legende}</div><div class="mo-mat">${matrice}</div></div>`;
    }

    // ---------------------------------------------------------------- un cas d'usage : le parcours
    // Une colonne par étape, du haut vers le bas : phases, étapes, déclencheurs, émotions, besoins, états des composants.
    function vueCas(){
      const U = E.G.cas_usage, u = U.find(x => x.cle === E.cas);
      if (!u) return '<p class="mo-explic">Aucun cas d\'usage dans ces codes.</p>';
      const choix = `<div class="mo-choix">${U.map(x => `<button data-cas="${esc(x.cle)}" class="${x.cle === u.cle ? "actif" : ""}">${E.numCas[x.cle]}. ${esc(lib(x.cle))}</button>`).join("")}</div>`;
      const cas = E.N[u.cle], n = Math.max(u.etapes.length, 1);
      const LAB = Math.round(Math.min(210, Math.max(132, E.dispo * .19)));
      const D = Math.max(E.dispo, LAB + n * 104 + 16), cw = (D - LAB - 12) / n, X = k => LAB + k * cw;
      const ix = {}; u.etapes.forEach((e, k) => ix[e] = k);
      const titre = (t, y) => `<text class="sect" x="10" y="${y}">${esc(t)}</text>`;
      let s = "", y = 8;
      // phases (groupes d'étapes)
      if (u.groupes.length){
        u.groupes.forEach(g => {
          const ks = g.etapes.map(e => ix[e]).filter(k => k !== undefined);
          if (!ks.length) return;
          const x1 = X(Math.min(...ks)), x2 = X(Math.max(...ks) + 1), L = x2 - x1 - 4;
          s += `<g class="groupe"><title>Groupe d'étapes ${esc(g.nom)} [${esc(g.uid)}]</title><rect x="${x1}" y="${y}" width="${L}" height="24"/><text x="${x1 + 8}" y="${y + 16}">${esc(couper(g.nom, Math.floor(L / 6.6), 1)[0])}</text></g>`;
        });
        s += titre("Phases", y + 16);
        y += 32;
      }
      // étapes en chevrons : le sens de lecture est celui des first … then
      const hC = 66, yC = y;
      s += titre("Étapes", y + hC / 2 + 4);
      u.etapes.forEach((e, k) => {
        const x = X(k), w = cw - 2, N = k ? 10 : 0, P = 12, L = couper(`${E.N[e].position}. ${E.N[e].libelle}`, Math.floor((w - N - P - 12) / 6.7), 3);
        const y0 = y + hC / 2 - (L.length - 1) * 7.5 + 4;
        s += `<g class="nd chevron" data-cle="${esc(e)}" tabindex="0"><title>action ${esc(E.N[e].nom)}</title>
          <polygon points="${x},${y} ${x + w - P},${y} ${x + w},${y + hC / 2} ${x + w - P},${y + hC} ${x},${y + hC} ${x + N},${y + hC / 2}"/>
          ${L.map((t, j) => `<text class="titre" x="${x + N + 8}" y="${y0 + j * 15}">${esc(t)}</text>`).join("")}</g>`;
      });
      y += hC + 16;
      // déclencheurs
      const carDec = Math.floor((cw - 12) / 5.9);
      const decs = u.etapes.map(e => E.N[e].declencheurs.flatMap(d => couper((d.type === "declenche" ? "Quand " : "Si ") + d.texte, carDec, 3).map(t => ({t, d}))));
      const nDec = Math.max(1, ...decs.map(d => d.length));
      if (decs.some(d => d.length)){
        s += titre("Déclencheurs", y + 10);
        decs.forEach((L, k) => L.forEach((l, j) => {
          s += `<text class="dec" x="${X(k) + 6}" y="${y + 10 + j * 14}" ${l.d.etat ? `data-cle="${esc(l.d.etat)}"` : ""} data-bulle="${esc((l.d.type === "declenche" ? "triggerEvent" : "condition") + " : " + l.d.texte)}">${esc(l.t)}</text>`;
        }));
        y += nDec * 14 + 18;
      }
      // émotions : une courbe par persona, sur un seul axe
      const personas = [...new Set([...u.acteurs, ...u.etapes.flatMap(e => E.N[e].ressentis.map(r => r.persona)).filter(Boolean)])];
      const scores = u.etapes.flatMap(e => E.N[e].ressentis.map(r => r.score)).filter(v => typeof v === "number");
      const hE = 176, yE = y + 6, M = Math.max(3, ...scores.map(Math.abs));
      const Y = v => yE + hE / 2 - v / M * (hE / 2 - 14);
      const coulP = {}; noeudsDe("persona").forEach((p, k) => coulP[p.cle] = COULEURS_PERSONAS[k % COULEURS_PERSONAS.length]);   // une persona garde sa couleur d'un cas à l'autre
      if (scores.length){
        s += titre("Émotions", yE + 8);
        s += `<line class="axe zero" x1="${LAB}" x2="${D - 12}" y1="${Y(0)}" y2="${Y(0)}"/><line class="axe" x1="${LAB}" x2="${D - 12}" y1="${Y(M)}" y2="${Y(M)}"/><line class="axe" x1="${LAB}" x2="${D - 12}" y1="${Y(-M)}" y2="${Y(-M)}"/>
          <text class="lbl" x="${LAB - 6}" y="${Y(M) + 4}" text-anchor="end">+${M}</text><text class="lbl" x="${LAB - 6}" y="${Y(0) + 4}" text-anchor="end">0</text><text class="lbl" x="${LAB - 6}" y="${Y(-M) + 4}" text-anchor="end">−${M}</text>`;
        const etiquettes = [];
        personas.forEach((p, ip) => {
          const dx = (ip - (personas.length - 1) / 2) * 4;
          const pts = u.etapes.map((e, k) => { const r = E.N[e].ressentis.find(x => x.persona === p); return r && !r.absent && typeof r.score === "number" ? {x: X(k) + cw / 2 + dx, y: Y(r.score), r, e} : null; });
          let trace = "", suite = false;
          pts.forEach(q => { if (!q){ suite = false; return; } trace += `${suite ? "L" : "M"}${q.x.toFixed(1)},${q.y.toFixed(1)} `; suite = true; });
          s += `<path class="courbe" d="${trace}" style="stroke:${coulP[p]}"/>`;
          pts.forEach(q => { if (!q) return;
            const b = `${lib(p)}, étape ${E.N[q.e].position} : ${q.r.score > 0 ? "+" : ""}${q.r.score}${q.r.insight ? ". " + q.r.insight : ""}${q.r.action ? " (" + q.r.action + ")" : ""}`;
            s += `<g class="point" data-cle="${esc(q.e)}" data-bulle="${esc(b)}"><circle class="cible" cx="${q.x}" cy="${q.y}" r="13"/><circle cx="${q.x}" cy="${q.y}" r="4.5" style="fill:${coulP[p]}"/></g>`; });
          const premier = pts.find(Boolean);
          if (premier) etiquettes.push({p, y: premier.y + 4});
        });
        // noms au bout des courbes, sans se chevaucher
        etiquettes.sort((a, b) => a.y - b.y).forEach((l, k, L) => { if (k && l.y - L[k - 1].y < 15) l.y = L[k - 1].y + 15; });
        const trop = etiquettes.length ? etiquettes[etiquettes.length - 1].y - (yE + hE - 24) : 0;
        if (trop > 0) etiquettes.forEach(l => { l.y -= trop; });
        const carNom = Math.floor((LAB - 50) / 6.2);
        etiquettes.forEach(l => { s += `<g class="nd etiq" data-cle="${esc(l.p)}"><circle cx="16" cy="${l.y + 16}" r="4.5" style="fill:${coulP[l.p]}"/><text class="sous" x="26" y="${l.y + 20}">${esc(couper(lib(l.p), carNom, 1)[0])}</text></g>`; });
        y = yE + hE + 26;
      }
      // besoins : un point sur chaque étape qui le satisfait
      const sat = new Map();
      u.etapes.forEach((e, k) => E.sortants[e].filter(l => l.type === "satisfait").forEach(l => { if (!sat.has(l.vers)) sat.set(l.vers, []); sat.get(l.vers).push(k); }));
      const rBesoins = [...sat.entries()].sort((a, b) => a[1][0] - b[1][0]);
      const carLab = Math.floor((LAB - 14) / 5.9);
      if (rBesoins.length){
        s += titre("Besoins satisfaits", y + 4); y += 14;
        rBesoins.forEach(([b, ks]) => {
          const L = couper(lib(b), carLab, 2), yc = y + 15;
          s += `<g class="nd etiq" data-cle="${esc(b)}"><title>${esc(lib(b))}</title>${L.map((t, j) => `<text class="sous" x="10" y="${yc + 4 - (L.length - 1) * 6.5 + j * 13}">${esc(t)}</text>`).join("")}</g>`;
          if (ks.length > 1) s += `<line class="lien-besoin" x1="${X(ks[0]) + cw / 2}" x2="${X(ks[ks.length - 1]) + cw / 2}" y1="${yc}" y2="${yc}"/>`;
          ks.forEach(k => { s += `<circle class="pt-besoin" data-cle="${esc(u.etapes[k])}" cx="${X(k) + cw / 2}" cy="${yc}" r="6.5" data-bulle="${esc(`« ${E.N[u.etapes[k]].libelle} » satisfait « ${lib(b)} »`)}"/>`; });
          y += 33;
        });
        y += 12;
      }
      // états des composants : une frise, les composants qui changent le plus d'abord
      const lignesGrille = Object.keys(u.grille).map(c => {
        const blocs = [];
        u.etapes.forEach((e, k) => {
          const v = u.grille[c][e], dernier = blocs[blocs.length - 1];
          if (!v){ return; }
          const dec = E.N[e].declencheurs.some(d => v.etats.includes(d.etat));
          if (dernier && dernier.texte === v.texte && dernier.fin === k - 1 && !dec && !dernier.dec){ dernier.fin = k; }
          else blocs.push({texte: v.texte, debut: k, fin: k, dec, etat: v.etats.find(Boolean)});
        });
        return {c, blocs};
      }).sort((a, b) => b.blocs.length - a.blocs.length);
      if (lignesGrille.length){
        s += titre("États des composants", y + 4); y += 14;
        const carComp = Math.floor((LAB - 14) / 5.9);
        lignesGrille.forEach(({c, blocs}) => {
          s += `<g class="nd etiq" data-cle="${esc(c)}"><title>${esc(lib(c))}</title><text class="sous" x="10" y="${y + 17}">${esc(couper(lib(c), carComp, 1)[0])}</text></g>`;
          blocs.forEach(b => {
            const x = X(b.debut) + 1, w = (b.fin - b.debut + 1) * cw - 3, t = b.texte.replace(/ > /g, " → ");
            const eteint = /^(off|idle|hidden|closed|locked|inactive|standby)\b/i.test(b.texte) && !b.dec;
            s += `<g class="bloc${eteint ? " eteint" : ""}${b.dec ? " declenche" : ""}" ${b.etat ? `data-cle="${esc(b.etat)}"` : ""} data-bulle="${esc(`${lib(c)} : ${t}, étape${b.fin > b.debut ? `s ${E.N[u.etapes[b.debut]].position} à ${E.N[u.etapes[b.fin]].position}` : " " + E.N[u.etapes[b.debut]].position}${b.dec ? ". Cet état déclenche l'étape." : ""}`)}">
              <rect x="${x}" y="${y + 3}" width="${w}" height="21"/><text x="${x + 7}" y="${y + 18}">${esc(couper(t, Math.max(3, Math.floor((w - 12) / 5.8)), 1)[0])}</text></g>`;
          });
          y += 27;
        });
      }
      // repères de colonnes, sous tout le reste
      let reperes = "";
      for (let k = 0; k <= n; k++) reperes += `<line class="repere" x1="${X(k)}" x2="${X(k)}" y1="${yC + hC + 4}" y2="${y}"/>`;
      const h = y + 12;
      const svg = `<svg width="${D}" height="${h}" viewBox="0 0 ${D} ${h}" role="img" aria-label="Parcours du cas d'usage ${esc(cas.libelle)}">${reperes}${s}</svg>`;
      const acteurs = `<div class="mo-legende">${personas.map(p => `<span class="mo-leg persona" data-cle="${esc(p)}"><i style="--c:${coulP[p]}"></i>${esc(lib(p))}</span>`).join("")}<span class="mo-leg discret">${u.fichiers.map(esc).join(", ")}</span></div>`;
      return `${choix}<p class="mo-explic"><code>use case def ${esc(cas.nom)}</code>, lu de gauche à droite dans l'ordre des <code>first … then</code>. Bloc encadré : l'état qui déclenche l'étape. Bloc gris : composant au repos. Survoler pour le détail, cliquer pour la fiche et sa ligne de code.</p>
        ${acteurs}<div class="mo-dessin">${svg}</div>
        <details class="mo-bloc mo-detail"><summary>Voir ces données en tableaux</summary>${tableGrille(u)}${tableRessentis(u)}</details>`;
    }

    function tableGrille(u){
      const comps = Object.keys(u.grille);
      if (!comps.length) return "";
      const tete = u.etapes.map(e => `<th title="action ${esc(E.N[e].nom)}">${E.N[e].position}. ${esc(couper(E.N[e].libelle, 18, 1)[0])}</th>`).join("");
      const lignes = comps.map(c => {
        let avant = null;
        const cases = u.etapes.map(e => {
          const v = u.grille[c][e];
          if (!v) { avant = null; return '<td class="vide">—</td>'; }
          const dec = E.N[e].declencheurs.some(d => v.etats.includes(d.etat));
          const change = avant !== null && avant !== v.texte;
          avant = v.texte;
          const cible = v.etats.find(Boolean);
          return `<td class="${change ? "change" : ""}${dec ? " decl" : ""}" ${cible ? `data-cle="${esc(cible)}"` : ""} title="${dec ? "État qui déclenche l'étape. " : ""}${esc(v.texte)}">${esc(v.texte).replace(/ &gt; /g, " → ")}</td>`;
        }).join("");
        return `<tr><th class="ligne" data-cle="${esc(c)}">${esc(lib(c))}</th>${cases}</tr>`;
      }).join("");
      return `<div class="mo-bloc"><h4>Composants × étapes</h4><p class="mo-explic">Lu dans les attributs <code>grid…</code> du cas d'usage. En gras : l'état change par rapport à l'étape précédente.
        Trait rouge : cet état déclenche l'étape. « → » : états successifs dans la même étape.</p>
        <div class="mo-tablezone"><table class="mo-table"><thead><tr><th>Composant</th>${tete}</tr></thead><tbody>${lignes}</tbody></table></div></div>`;
    }

    function tableRessentis(u){
      const personas = [...new Set(u.etapes.flatMap(e => E.N[e].ressentis.map(r => r.persona)).filter(Boolean))];
      if (!personas.length) return "";
      const tete = u.etapes.map(e => `<th>${E.N[e].position}.</th>`).join("");
      const lignes = personas.map(p => `<tr><th class="ligne" data-cle="${esc(p)}">${esc(lib(p))}</th>${u.etapes.map(e => {
        const r = E.N[e].ressentis.find(x => x.persona === p);
        if (!r) return '<td class="vide">—</td>';
        if (r.absent) return `<td data-cle="${esc(e)}" title="absente à cette étape">absente</td>`;
        return `<td data-cle="${esc(e)}" title="${esc([r.action, r.insight].filter(Boolean).join(" — "))} [${esc(r.uid)}]"><span class="mo-score" style="background:${couleurScore(r.score)}">${r.score > 0 ? "+" : ""}${r.score ?? "?"}</span> ${esc(couper(r.insight || r.action || "", 30, 1)[0])}</td>`;
      }).join("")}</tr>`).join("");
      return `<div class="mo-bloc"><h4>Ressentis des personas</h4><p class="mo-explic">Lu dans l'attribut <code>feedback</code> de chaque étape : émotion de −5 à +5, puis le ressenti.</p>
        <div class="mo-tablezone"><table class="mo-table"><thead><tr><th>Persona</th>${tete}</tr></thead><tbody>${lignes}</tbody></table></div></div>`;
    }

    // ---------------------------------------------------------------- un composant : le graphe de ses états
    // Les codes ne déclarent pas de transitions (pas de state def) : elles sont déduites ici de l'ordre des
    // étapes dans les grilles, et la page le dit.
    function transitionsDe(c){
      const T = new Map();
      E.G.cas_usage.forEach(u => {
        const ligne = u.grille[c.cle];
        if (!ligne) return;
        let avant = null;
        u.etapes.forEach(e => {
          const v = ligne[e];
          if (!v){ avant = null; return; }
          v.etats.filter(Boolean).forEach(st => {
            if (avant && avant !== st){
              const k = avant + "|" + st, t = T.get(k) || {a: avant, b: st, ou: []};
              t.ou.push(`${E.numCas[u.cle]}.${E.N[e].position}`);
              T.set(k, t);
            }
            avant = st;
          });
        });
      });
      return [...T.values()];
    }
    function grapheEtats(c){
      const etats = c.etats.map(k => E.N[k]), T = transitionsDe(c), n = etats.length;
      const D = Math.max(E.dispo, 380), W = Math.min(170, Math.max(124, D / 5)), Ho = 52;
      const rx = n > 1 ? Math.min(D / 2 - W / 2 - 16, 90 + n * 44) : 0, ry = n > 2 ? Math.min(190, 56 + n * 26) : 0;
      const cx = D / 2, cy = ry + Ho / 2 + 22, pos = {};
      etats.forEach((st, k) => { const a = -Math.PI / 2 + 2 * Math.PI * k / n - (n === 2 ? Math.PI / 2 : 0); pos[st.cle] = {x: cx + rx * Math.cos(a), y: cy + ry * Math.sin(a)}; });
      const bord = (p, q) => {     // point du bord de la boîte de p, dans la direction de q
        const dx = q.x - p.x, dy = q.y - p.y, k = Math.min((W / 2 + 4) / (Math.abs(dx) || 1e-6), (Ho / 2 + 4) / (Math.abs(dy) || 1e-6));
        return {x: p.x + dx * k, y: p.y + dy * k};
      };
      let arcs = "";
      T.forEach(t => {
        const P = pos[t.a], Q = pos[t.b];
        if (!P || !Q) return;
        const dx = Q.x - P.x, dy = Q.y - P.y, L = Math.hypot(dx, dy) || 1, cote = 30;      // deux sens : deux courbes distinctes
        const C = {x: (P.x + Q.x) / 2 - dy / L * cote, y: (P.y + Q.y) / 2 + dx / L * cote};
        const A = bord(P, C), B = bord(Q, C), f = t.ou.length;
        arcs += `<path class="ar transition" data-a="${esc(t.a)}" data-b="${esc(t.b)}" marker-end="url(#mo-fleche)" style="stroke-width:${1.4 + Math.min(f - 1, 3) * .8}"
          data-bulle="${esc(`${lib(t.a)} → ${lib(t.b)} : ${f} fois (étapes ${t.ou.join(", ")})`)}" d="M${A.x.toFixed(1)},${A.y.toFixed(1)} Q${C.x.toFixed(1)},${C.y.toFixed(1)} ${B.x.toFixed(1)},${B.y.toFixed(1)}"/>`;
        if (f > 1) arcs += `<text class="lbl lisible" x="${C.x.toFixed(1)}" y="${C.y.toFixed(1)}" text-anchor="middle">${f} fois</text>`;
      });
      const noeuds = etats.map(st => {
        const p = pos[st.cle], etapes = E.entrants[st.cle].filter(l => l.type === "met_dans").length;
        const decl = E.sortants[st.cle].filter(l => l.type === "declenche" || l.type === "condition").length;
        const jamais = !etapes && !decl, L = couper(st.libelle, Math.floor((W - 14) / 6.7), 2), x = p.x - W / 2, y = p.y - Ho / 2;
        const sous = jamais ? "aucune étape" : `${etapes} étape${etapes > 1 ? "s" : ""}${decl ? `, déclenche ${decl}` : ""}`;
        return `<g class="nd etat${jamais ? " alerte" : ""}${decl ? " declenche" : ""}" data-cle="${esc(st.cle)}" tabindex="0"><title>${esc(st.libelle)}${st.description ? " : " + esc(st.description) : ""}</title>
          <rect class="fond" x="${x}" y="${y}" width="${W}" height="${Ho}"/>
          ${L.map((t, k) => `<text class="titre" x="${p.x}" y="${y + (L.length > 1 ? 16 : 22) + k * 14}" text-anchor="middle">${esc(t)}</text>`).join("")}
          <text class="sous" x="${p.x}" y="${y + Ho - 7}" text-anchor="middle">${esc(sous)}</text></g>`;
      }).join("");
      const h = cy + ry + Ho / 2 + 22;
      return {nb: T.length, svg: `<svg width="${D}" height="${h}" viewBox="0 0 ${D} ${h}" role="img" aria-label="États du composant ${esc(c.libelle)}">
        <defs><marker id="mo-fleche" markerWidth="9" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L8,4 L0,8 z" style="fill:var(--vin,#6E2033)"/></marker></defs>${arcs}${noeuds}</svg>`};
    }
    function vueComposant(){
      const comps = noeudsDe("composant");
      if (!comps.length) return '<p class="mo-explic">Aucun composant dans ces codes.</p>';
      const c = E.N[E.comp] || comps[0];
      const choix = `<div class="mo-choix">${comps.map(x => `<button data-comp="${esc(x.cle)}" class="${x.cle === c.cle ? "actif" : ""}">${esc(x.libelle)}</button>`).join("")}</div>`;
      const etats = c.etats.map(k => E.N[k]);
      const etapes = new Map(), aretes = [];
      etats.forEach(st => {
        aretes.push({a: c.cle, b: st.cle, classe: "met"});
        E.entrants[st.cle].filter(l => l.type === "met_dans").forEach(l => { etapes.set(l.de, true); aretes.push({a: st.cle, b: l.de, classe: "met"}); });
        E.sortants[st.cle].filter(l => l.type === "declenche" || l.type === "condition").forEach(l => { etapes.set(l.vers, true); aretes.push({a: st.cle, b: l.vers, classe: l.type}); });
      });
      const ordre = E.G.cas_usage.flatMap(u => u.etapes).filter(e => etapes.has(e));
      const detail = colonnes([
        {titre: "Composant", sections: [{noeuds: [{cle: c.cle, titre: c.libelle, sous: c.attrs.role ? `rôle : ${c.attrs.role}` : c.nom}]}]},
        {titre: `États (${etats.length})`, sections: [{noeuds: etats.map(st => ({cle: st.cle, titre: st.libelle, sous: st.description || "", lignes: 2,
          alerte: !E.entrants[st.cle].some(l => l.type === "met_dans")}))}]},
        {titre: "Étapes où il est dans cet état", sections: E.G.cas_usage.map(u => ({titre: `${E.numCas[u.cle]}. ${lib(u.cle)}`,
          noeuds: u.etapes.filter(e => etapes.has(e)).map(e => ({cle: e, titre: `${E.N[e].position}. ${E.N[e].libelle}`, couleur: E.couleurCas[u.cle], lignes: 1}))})).filter(s => s.noeuds.length)},
      ], aretes, {ecart: 120, largeur: 215, titre: `Composant ${c.libelle}`});
      const graphe = grapheEtats(c);
      const inutil = E.G.noeuds.filter(n => n.type === "etape" && n.inutilises.includes(c.cle));
      return `${choix}<p class="mo-explic"><code>part def ${esc(c.nom)}</code>${c.attrs.description ? " : " + esc(c.attrs.description) : ""}
        Ses états viennent de l'attribut <code>states</code>. <b>Les flèches sont déduites</b> de l'ordre des étapes dans les grilles : le code ne déclare pas de transitions.
        Bord rouge : un état qui déclenche une étape. Fond rouge : un état qu'aucune étape n'utilise.</p>
        <div class="mo-dessin">${graphe.svg}</div>
        ${graphe.nb ? "" : '<p class="mo-explic">Aucun changement d\'état dans les grilles pour ce composant.</p>'}
        <details class="mo-bloc mo-detail"><summary>Voir chaque état et ses étapes</summary><div class="mo-dessin">${detail}</div></details>
        ${ordre.length ? "" : '<p class="mo-explic">Ce composant n\'apparaît dans aucune grille.</p>'}
        ${inutil.length ? `<p class="mo-explic">Marqué non utilisé (<code>unusedComponents</code>) aux étapes : ${inutil.map(n => `<span class="mo-lien" data-cle="${esc(n.cle)}">${esc(etiquetteEtape(n.cle))}</span>`).join(", ")}.</p>` : ""}`;
    }

    // ---------------------------------------------------------------- vue technique : schémas en colonnes, au plus près du code
    // vue d'ensemble
    function vueEnsembleTechnique(){
      const U = E.G.cas_usage;
      const parCas = {};                         // cas -> {besoins: Map(besoin -> nb d'étapes), composants: Set}
      U.forEach(u => {
        const b = new Map(), c = new Set(Object.keys(u.grille));
        u.etapes.forEach(e => E.sortants[e].filter(l => l.type === "satisfait").forEach(l => b.set(l.vers, (b.get(l.vers) || 0) + 1)));
        parCas[u.cle] = {b, c};
      });
      const aretes = [];
      E.G.liens.filter(l => l.type === "acteur").forEach(l => aretes.push({a: l.de, b: l.vers, classe: "acteur"}));
      U.forEach(u => {
        parCas[u.cle].b.forEach((n, b) => aretes.push({a: u.cle, b, classe: "satisfait", label: `satisfait par ${n} étape${n > 1 ? "s" : ""}`}));
        parCas[u.cle].c.forEach(c => aretes.push({a: u.cle, b: c, classe: "utilise"}));
      });
      const besoins = noeudsDe("besoin"), comps = noeudsDe("composant");
      const svg = colonnes([
        {titre: "Personas et besoins", sections: [
          {titre: "Personas (actor)", noeuds: noeudsDe("persona").map(n => ({cle: n.cle, titre: n.libelle, sous: n.attrs.ageCategory || n.nom}))},
          {titre: `Besoins (satisfy)`, noeuds: besoins.map(n => ({cle: n.cle, titre: n.libelle, alerte: !E.entrants[n.cle].some(l => l.type === "satisfait")}))},
        ]},
        {titre: "Cas d'usage", sections: [{noeuds: U.map(u => ({cle: u.cle, titre: `${E.numCas[u.cle]}. ${lib(u.cle)}`, sous: `${u.etapes.length} étapes`, couleur: E.couleurCas[u.cle]}))}]},
        {titre: "Composants (grilles)", sections: [
          {noeuds: comps.map(n => ({cle: n.cle, titre: n.libelle, sous: `${n.etats.length} états${n.attrs.role ? " · " + n.attrs.role : ""}`, lignes: 1}))},
        ]},
      ], aretes, {largeur: 205, ecart: 120, largeurMax: 380, titre: "Vue d'ensemble du modèle"});
      return `<p class="mo-explic">À gauche, les personas qui jouent dans les cas d'usage (<code>actor</code>) et les besoins que les cas d'usage satisfont par leurs étapes
        (<code>satisfy</code>) ; à droite, les composants qu'ils utilisent (grille composant × étape). Survoler un élément pour suivre ses liens, cliquer pour sa fiche.</p>
        <div class="mo-dessin">${svg}</div>`;
    }

    // ---------------------------------------------------------------- un cas d'usage
    function vueCasTechnique(){
      const U = E.G.cas_usage, u = U.find(x => x.cle === E.cas);
      if (!u) return '<p class="mo-explic">Aucun cas d\'usage dans ces codes.</p>';
      const choix = `<div class="mo-choix">${U.map(x => `<button data-cas="${esc(x.cle)}" class="${x.cle === u.cle ? "actif" : ""}">${E.numCas[x.cle]}. ${esc(lib(x.cle))}</button>`).join("")}</div>`;
      const cas = E.N[u.cle];
      const acteurs = `<div class="mo-acteurs">Acteurs : ${u.acteurs.map(p => `<span class="mo-puce" style="color:var(--mo-persona)" data-cle="${esc(p)}">${esc(lib(p))}</span>`).join("") || "aucun"}
        · fichier${u.fichiers.length > 1 ? "s" : ""} ${u.fichiers.map(esc).join(", ")}</div>`;
      // flux des étapes
      const GAP = 46, PAD = 16, yGr = 12, yEt = 54, nE = Math.max(u.etapes.length, 1);
      const BW = Math.max(168, Math.min(300, Math.floor(((E.dispo || 0) - 2 * PAD - (nE - 1) * GAP) / nE)));
      const ix = {};
      u.etapes.forEach((e, k) => ix[e] = k);
      const X = k => PAD + k * (BW + GAP);
      const lignesEt = u.etapes.map(e => couper(`${E.N[e].position}. ${E.N[e].libelle}`, Math.floor((BW - 22) / 7), 2));
      const hEt = 14 + Math.max(...lignesEt.map(l => l.length)) * 15 + 14;
      const decs = u.etapes.map(e => E.N[e].declencheurs);
      const hDec = Math.max(0, ...decs.map(d => d.reduce((s, x) => s + couper((x.type === "declenche" ? "⚡ " : "si ") + x.texte, Math.floor((BW - 8) / 6.2), 2).length, 0))) * 13 + 8;
      let s = "";
      u.groupes.forEach(g => {
        const ks = g.etapes.map(e => ix[e]).filter(k => k !== undefined);
        if (!ks.length) return;
        const x1 = X(Math.min(...ks)), x2 = X(Math.max(...ks)) + BW;
        s += `<g class="groupe"><title>Groupe d'étapes ${esc(g.nom)} [${esc(g.uid)}]</title><rect x="${x1}" y="${yGr}" width="${x2 - x1}" height="24" rx="6"/><text x="${x1 + 10}" y="${yGr + 16}">${esc(g.nom)}</text></g>`;
      });
      const suites = E.G.liens.filter(l => l.type === "suit" && ix[l.de] !== undefined && ix[l.vers] !== undefined);
      suites.forEach(l => {
        const a = ix[l.de], b = ix[l.vers], y = yEt + hEt / 2;
        if (b === a + 1) s += `<path class="ar suit" data-a="${esc(l.de)}" data-b="${esc(l.vers)}" d="M${X(a) + BW},${y} L${X(b) - 6},${y}" marker-end="url(#mo-fleche)"><title>first ${esc(E.N[l.de].nom)} then ${esc(E.N[l.vers].nom)}${l.entre_parties ? " (entre deux parties)" : ""}</title></path>`;
        else s += `<path class="ar suit" data-a="${esc(l.de)}" data-b="${esc(l.vers)}" d="M${X(a) + BW / 2},${yEt} C${X(a) + BW / 2},${yEt - 40} ${X(b) + BW / 2},${yEt - 40} ${X(b) + BW / 2},${yEt - 6}" marker-end="url(#mo-fleche)"/>`;
      });
      u.etapes.forEach((e, k) => {
        s += boite({cle: e, titre: "", couleur: E.couleurCas[u.cle], infobulle: `action ${E.N[e].nom}`}, X(k), yEt, BW, hEt, lignesEt[k], E.N[e].groupe ? [] : []);
        let y = yEt + hEt + 16;
        decs[k].forEach(d => {
          couper((d.type === "declenche" ? "⚡ " : "si ") + d.texte, Math.floor((BW - 8) / 6.2), 2).forEach((t, j) => {
            s += `<text class="dec" x="${X(k) + 4}" y="${y}" ${d.etat ? `data-cle="${esc(d.etat)}"` : ""} style="fill:${d.type === "declenche" ? "var(--err,#c0392b)" : "var(--att,#a35f00)"}">${esc(t)}<title>${d.type === "declenche" ? "triggerEvent" : "condition"} = "${esc(d.texte)}"</title></text>`;
            y += 13;
          });
        });
      });
      // besoins satisfaits, placés sous les étapes qui les servent
      const yB = yEt + hEt + hDec + 70, sat = {};
      u.etapes.forEach((e, k) => E.sortants[e].filter(l => l.type === "satisfait").forEach(l => (sat[l.vers] = sat[l.vers] || []).push(k)));
      const besoins = Object.keys(sat).sort((a, b) => (sat[a].reduce((x, y) => x + y, 0) / sat[a].length) - (sat[b].reduce((x, y) => x + y, 0) / sat[b].length));
      const BBW = Math.max(178, Math.min(260, BW)), posB = {};
      let xb = PAD;
      besoins.forEach(b => {
        const moyen = X(sat[b].reduce((x, y) => x + y, 0) / sat[b].length) + BW / 2 - BBW / 2;
        xb = Math.max(xb, moyen); posB[b] = xb; xb += BBW + 14;
      });
      const hB = 14 + 2 * 15;
      besoins.forEach(b => sat[b].forEach(k => {
        const x1 = X(k) + BW - 10, y0 = yEt + hEt, y1 = yEt + hEt + hDec + 6, x2 = posB[b] + BBW / 2, y2 = yB;
        s = `<path class="ar satisfait" data-a="${esc(u.etapes[k])}" data-b="${esc(b)}" d="M${x1},${y0} L${x1},${y1} C${x1},${y1 + 50} ${x2},${y2 - 50} ${x2},${y2}"><title>${esc(E.N[u.etapes[k]].libelle)} satisfait « ${esc(lib(b))} »</title></path>` + s;
      }));
      besoins.forEach(b => { s += boite({cle: b, titre: lib(b)}, posB[b], yB, BBW, hB, couper(lib(b), Math.floor((BBW - 22) / 7), 2), []); });
      if (besoins.length) s += `<text class="entete-col" x="${PAD}" y="${yB - 10}">Besoins satisfaits (satisfy)</text>`;
      const w = Math.max(X(u.etapes.length - 1) + BW, xb) + PAD, h = yB + hB + PAD;
      const svg = `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" aria-label="Étapes du cas d'usage ${esc(cas.libelle)}">
        <defs><marker id="mo-fleche" markerWidth="9" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="currentColor" style="fill:var(--texte,#241A1D)"/></marker></defs>${s}</svg>`;
      return `${choix}<p class="mo-explic"><code>use case def ${esc(cas.nom)}</code> : les étapes (<code>action</code>) dans l'ordre des <code>first … then</code>,
        leurs déclencheurs, et les besoins qu'elles satisfont.</p>${acteurs}<div class="mo-dessin">${svg}</div>${tableGrille(u)}${tableRessentis(u)}`;
    }

    // ---------------------------------------------------------------- un composant
    function vueComposantTechnique(){
      const comps = noeudsDe("composant");
      if (!comps.length) return '<p class="mo-explic">Aucun composant dans ces codes.</p>';
      const c = E.N[E.comp] || comps[0];
      const choix = `<div class="mo-choix">${comps.map(x => `<button data-comp="${esc(x.cle)}" class="${x.cle === c.cle ? "actif" : ""}">${esc(x.libelle)}</button>`).join("")}</div>`;
      const etats = c.etats.map(k => E.N[k]);
      const etapes = new Map(), aretes = [];
      etats.forEach(st => {
        aretes.push({a: c.cle, b: st.cle, classe: "met"});
        E.entrants[st.cle].filter(l => l.type === "met_dans").forEach(l => { etapes.set(l.de, true); aretes.push({a: st.cle, b: l.de, classe: "met"}); });
        E.sortants[st.cle].filter(l => l.type === "declenche" || l.type === "condition").forEach(l => { etapes.set(l.vers, true); aretes.push({a: st.cle, b: l.vers, classe: l.type}); });
      });
      const ordre = E.G.cas_usage.flatMap(u => u.etapes).filter(e => etapes.has(e));
      const svg = colonnes([
        {titre: "Composant", sections: [{noeuds: [{cle: c.cle, titre: c.libelle, sous: c.attrs.role ? `rôle : ${c.attrs.role}` : c.nom}]}]},
        {titre: `États (${etats.length})`, sections: [{noeuds: etats.map(st => ({cle: st.cle, titre: st.libelle, sous: st.description || "", lignes: 2,
          alerte: !E.entrants[st.cle].some(l => l.type === "met_dans")}))}]},
        {titre: "Étapes où il est dans cet état", sections: E.G.cas_usage.map(u => ({titre: `${E.numCas[u.cle]}. ${lib(u.cle)}`,
          noeuds: u.etapes.filter(e => etapes.has(e)).map(e => ({cle: e, titre: `${E.N[e].position}. ${E.N[e].libelle}`, couleur: E.couleurCas[u.cle], lignes: 1}))})).filter(s => s.noeuds.length)},
      ], aretes, {ecart: 120, largeur: 215, titre: `Composant ${c.libelle}`});
      const inutil = E.G.noeuds.filter(n => n.type === "etape" && n.inutilises.includes(c.cle));
      return `${choix}<p class="mo-explic"><code>part def ${esc(c.nom)}</code>${c.attrs.description ? " : " + esc(c.attrs.description) : ""}
        Ses états viennent de l'attribut <code>states</code> ; les liens vers les étapes viennent des grilles des cas d'usage.
        Pointillés rouges : l'état déclenche l'étape (<code>triggerEvent</code>) ; orange : condition. En rouge : un état qu'aucune étape n'utilise.</p>
        <div class="mo-dessin">${svg}</div>
        ${ordre.length ? "" : '<p class="mo-explic">Ce composant n\'apparaît dans aucune grille.</p>'}
        ${inutil.length ? `<p class="mo-explic">Marqué non utilisé (<code>unusedComponents</code>) aux étapes : ${inutil.map(n => `<span class="mo-lien" data-cle="${esc(n.cle)}">${esc(etiquetteEtape(n.cle))}</span>`).join(", ")}.</p>` : ""}`;
    }
    // ---------------------------------------------------------------- traçabilité
    function vueTrace(){
      const U = E.G.cas_usage, etapes = U.flatMap(u => u.etapes);
      const rang = {}; etapes.forEach((e, k) => rang[e] = k);
      const besoins = noeudsDe("besoin").map(b => ({b, ks: E.entrants[b.cle].filter(l => l.type === "satisfait").map(l => rang[l.de]).filter(k => k !== undefined)}))
        .sort((x, y) => (x.ks.length ? Math.min(...x.ks) : 1e9) - (y.ks.length ? Math.min(...y.ks) : 1e9));
      const aretes = [];
      E.G.liens.filter(l => l.type === "satisfait").forEach(l => aretes.push({a: l.vers, b: l.de, classe: "satisfait"}));
      U.forEach(u => u.etapes.forEach(e => aretes.push({a: e, b: u.cle, classe: "contient"})));
      const sansBesoin = etapes.filter(e => !E.sortants[e].some(l => l.type === "satisfait"));
      const nonCouverts = besoins.filter(x => !x.ks.length);
      const svg = colonnes([
        {titre: "Besoins utilisateur", sections: [{noeuds: besoins.map(({b, ks}) => ({cle: b.cle, titre: b.libelle, sous: ks.length ? `${ks.length} étape${ks.length > 1 ? "s" : ""}` : "aucune étape", alerte: !ks.length}))}]},
        {titre: "Étapes (satisfy)", sections: U.map(u => ({titre: `${E.numCas[u.cle]}. ${lib(u.cle)}`, noeuds: u.etapes.map(e => ({cle: e, titre: `${E.N[e].position}. ${E.N[e].libelle}`, couleur: E.couleurCas[u.cle], lignes: 1, alerte: sansBesoin.includes(e)}))}))},
        {titre: "Cas d'usage", sections: [{noeuds: U.map(u => ({cle: u.cle, titre: `${E.numCas[u.cle]}. ${lib(u.cle)}`, sous: `${u.etapes.length} étapes`, couleur: E.couleurCas[u.cle]}))}]},
      ], aretes, {ecart: 120, largeur: 215, titre: "Traçabilité besoins, étapes, cas d'usage"});
      return `<p class="mo-explic">Chaque besoin, les étapes qui le satisfont (<code>satisfy Needs::…</code>) et leur cas d'usage.
        ${nonCouverts.length ? `<b style="color:var(--err)">${nonCouverts.length} besoin${nonCouverts.length > 1 ? "s" : ""} satisfait${nonCouverts.length > 1 ? "s" : ""} par aucune étape.</b>` : "Tous les besoins sont satisfaits par au moins une étape."}
        ${sansBesoin.length ? `${sansBesoin.length} étape${sansBesoin.length > 1 ? "s" : ""} ne satisfai${sansBesoin.length > 1 ? "ent" : "t"} aucun besoin (en rouge).` : ""}</p>
        <div class="mo-dessin">${svg}</div>`;
    }

    // ---------------------------------------------------------------- fiche d'un élément
    function fiche(){
      const z = racine.querySelector("[data-fiche]");
      if (!z) return;
      const n = E.N[E.sel];
      z.classList.toggle("ouverte", !!n);
      if (!n) return;
      const [genre, coul, decl] = GENRES[n.type];
      let h = `<button class="mo-fermer" data-action="fermer" aria-label="Fermer la fiche">×</button><div class="genre" style="color:${coul}">${genre}</div><h4>${esc(n.libelle)}</h4><div class="sysml">${esc(decl(n))}</div>`;
      if (n.uid) h += `<h5>Identifiant UserShaker</h5><span class="mo-uid">${esc(n.uid)}</span>`;
      h += `<h5>Dans le code SysML</h5><ul>${n.sources.map((s, k) => `<li><span class="mo-lien" data-extrait="${k}">${esc(s.fichier)}, ligne ${s.ligne}</span></li>`).join("")}</ul><div data-extrait-zone></div>`;
      if (n.type === "etat") h += `<h5>Composant</h5><span class="mo-lien" data-cle="${esc(n.composant)}">${esc(lib(n.composant))}</span>${n.description ? `<p>${esc(n.description)}</p>` : ""}`;
      if (n.type === "etape"){
        h += `<h5>Cas d'usage</h5><span class="mo-lien" data-cle="${esc(n.cas)}">${esc(lib(n.cas))}</span>, étape ${n.position}${n.groupe ? `, groupe « ${esc(n.groupe)} »` : ""}`;
        if (n.declencheurs.length) h += `<h5>Déclencheurs</h5><ul>${n.declencheurs.map(d => `<li>${d.type === "declenche" ? "Quand" : "Si"} ${d.etat ? `<span class="mo-lien" data-cle="${esc(d.etat)}">${esc(d.texte)}</span>` : esc(d.texte)} <span class="mo-uid">${esc(d.uid)}</span></li>`).join("")}</ul>`;
        if (n.ressentis.length) h += `<h5>Ressentis</h5><ul>${n.ressentis.map(r => `<li><span class="mo-lien" data-cle="${esc(r.persona || "")}">${esc(lib(r.persona))}</span>
          ${r.absent ? "absente" : `<span class="mo-score" style="background:${couleurScore(r.score)}">${r.score > 0 ? "+" : ""}${r.score ?? "?"}</span>`}
          ${esc([r.action, r.insight].filter(Boolean).join(" — "))}</li>`).join("")}</ul>`;
        if (n.inutilises.length) h += `<h5>Composants non utilisés</h5>${n.inutilises.map(c => `<span class="mo-lien" data-cle="${esc(c)}">${esc(lib(c))}</span>`).join(", ")}`;
      }
      const attrs = Object.entries(n.attrs || {});
      if (attrs.length) h += `<h5>Attributs</h5><dl>${attrs.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>`;
      // liens, regroupés
      const groupes = {};
      E.sortants[n.cle].forEach(l => { if (l.type !== "contient" || n.type === "cas") (groupes[RELATIONS[l.type][0]] = groupes[RELATIONS[l.type][0]] || []).push([l.vers, l]); });
      E.entrants[n.cle].forEach(l => (groupes[RELATIONS[l.type][1]] = groupes[RELATIONS[l.type][1]] || []).push([l.de, l]));
      const nomLien = c => E.N[c]?.type === "etape" ? etiquetteEtape(c) : lib(c);
      for (const [titre, items] of Object.entries(groupes)){
        if (n.type === "etape" && ["Ressentis", "Déclenchée quand", "Conditions", "Dans le cas d'usage"].includes(titre)) continue;   // déjà affichés plus haut
        const vus = new Set();
        const liste = items.filter(([c, l]) => { const k = c + (l.texte || ""); if (vus.has(k)) return false; vus.add(k); return true; });
        h += `<h5>${esc(titre)} (${liste.length})</h5><ul>${liste.map(([c, l]) => `<li><span class="mo-lien" data-cle="${esc(c)}">${esc(nomLien(c))}</span>${l.texte && l.type !== "declenche" && l.type !== "condition" ? ` <span class="sysml">${esc(l.texte)}</span>` : ""}
          <span class="sysml" title="${esc(l.fichier)}">l.${l.ligne ?? "?"}</span></li>`).join("")}</ul>`;
      }
      z.innerHTML = h;
    }

    function extrait(k){
      const n = E.N[E.sel], s = n?.sources[k], zone = racine.querySelector("[data-extrait-zone]");
      if (!s || !zone) return;
      zone.innerHTML = extraitHtml(s.fichier, s.ligne);
    }
    function extraitHtml(fichier, ligne){
      const lignes = (E.textes[fichier] || "").split("\n");
      if (!lignes.length || !ligne) return "";
      const de = Math.max(1, ligne - 2), a = Math.min(lignes.length, ligne + 3);
      let h = "";
      for (let i = de; i <= a; i++) h += `<span class="${i === ligne ? "vise" : ""}"><span class="n">${i}</span>${esc(lignes[i - 1].length > 160 ? lignes[i - 1].slice(0, 159) + "…" : lignes[i - 1])}</span>`;
      return `<pre class="mo-extrait" aria-label="Extrait de ${esc(fichier)}">${h}</pre>`;
    }

    function choisir(cle){
      if (!E.N[cle]) return;
      E.sel = cle;
      fiche(); extrait(0); marquerSelection();
    }
    function marquerSelection(){
      racine.querySelectorAll(".nd").forEach(g => g.classList.toggle("sel", g.dataset.cle === E.sel));
    }

    // ---------------------------------------------------------------- plein écran
    // Le lecteur occupe toute la fenêtre (et tout l'écran si le navigateur l'accepte). Pour quitter :
    // le bouton « Quitter le plein écran » ou la touche Échap.
    function pleinEcran(oui){
      E.plein = oui;
      racine.classList.toggle("mo-plein", oui);
      document.documentElement.classList.toggle("mo-sans-defilement", oui);
      try {
        if (oui && !document.fullscreenElement && racine.requestFullscreen) racine.requestFullscreen().catch(() => {});
        if (!oui && document.fullscreenElement) document.exitFullscreen().catch(() => {});
      } catch { /* plein écran du navigateur refusé : la fenêtre entière suffit */ }
      if (E.G) requestAnimationFrame(() => dessinerVue());      // la place a changé : redessiner à la nouvelle largeur
      const b = racine.querySelector('[data-action="plein"]');
      if (b){ b.textContent = oui ? "✕ Quitter le plein écran" : "⛶ Plein écran"; b.classList.toggle("principal", oui); b.title = oui ? "Échap pour quitter" : "Utiliser tout l'écran"; }
    }
    document.addEventListener("fullscreenchange", () => {
      if (!document.fullscreenElement && E.plein) pleinEcran(false);
      else if (E.G) requestAnimationFrame(() => dessinerVue());
    });
    // la zone change de largeur (fenêtre, plein écran) : les dessins sont refaits à la nouvelle largeur
    let minuterieTaille = null;
    const siLargeurChange = () => {
      clearTimeout(minuterieTaille);
      minuterieTaille = setTimeout(() => {
        const z = racine.querySelector("[data-vue-zone]");
        if (E.G && z && z.offsetParent && Math.abs(z.clientWidth - E.largeur) > 16) dessinerVue();
      }, 120);
    };
    if (window.ResizeObserver) new ResizeObserver(siLargeurChange).observe(racine); else window.addEventListener("resize", siLargeurChange);
    const fermerFiche = () => { E.sel = null; fiche(); marquerSelection(); };
    document.addEventListener("keydown", e => {
      if (e.key !== "Escape") return;
      if (E.sel) fermerFiche(); else if (E.plein) pleinEcran(false);
    });

    // ---------------------------------------------------------------- événements
    racine.addEventListener("click", e => {
      const t = e.target;
      const act = t.closest("[data-action]");
      if (act){
        if (act.dataset.action === "fermer") fermerFiche();
        else if (act.dataset.action === "fichiers") entree.click();
        else if (act.dataset.action === "plein") pleinEcran(!E.plein);
        else if (act.dataset.action === "image"){
          const svg = racine.querySelector("[data-vue-zone] svg");
          if (svg) window.RMonieOutils?.imageSvg(svg, `R-monie_${E.vue}_${E.vue === "trace" ? "tracabilite" : E.style}.png`);
          else if (window.toast) window.toast("Pas de schéma à enregistrer dans cette vue.");
        }
        else { E.source = "session"; charger(); }
        return;
      }
      const st = t.closest("[data-style]"); if (st){ if (!st.disabled){ E.style = st.dataset.style; dessinerVue(); } return; }
      const v = t.closest("[data-vue]"); if (v && v.tagName === "BUTTON"){ E.vue = v.dataset.vue; dessinerVue(); return; }
      const c = t.closest("[data-cas]"); if (c){ E.cas = c.dataset.cas; dessinerVue(); return; }
      const k = t.closest("[data-comp]"); if (k){ E.comp = k.dataset.comp; E.vue = "composant"; dessinerVue(); return; }
      const x = t.closest("[data-extrait]"); if (x){ extrait(+x.dataset.extrait); return; }
      const sy = t.closest("[data-syntaxe]"); if (sy){ extraitSyntaxe(+sy.dataset.syntaxe); return; }
      const n = t.closest("[data-cle]"); if (n && n.dataset.cle) choisir(n.dataset.cle);
    });
    racine.addEventListener("dblclick", e => {           // double-clic : ouvrir la vue de l'élément
      const n = e.target.closest("[data-cle]"), x = n && E.N[n.dataset.cle];
      if (!x) return;
      if (x.type === "cas"){ E.vue = "cas"; E.cas = x.cle; dessinerVue(); }
      else if (x.type === "etape"){ E.vue = "cas"; E.cas = x.cas; dessinerVue(); }
      else if (x.type === "composant" || x.type === "etat"){ E.vue = "composant"; E.comp = x.type === "etat" ? x.composant : x.cle; dessinerVue(); }
    });
    racine.addEventListener("keydown", e => {
      const n = e.target.closest?.(".nd");
      if (n && (e.key === "Enter" || e.key === " ")){ e.preventDefault(); choisir(n.dataset.cle); }
    });
    racine.addEventListener("mouseover", e => {
      const n = e.target.closest(".nd"), svg = e.target.closest("svg");
      if (!n || !svg) return;
      const cle = n.dataset.cle, voisins = new Set([cle]);
      svg.querySelectorAll(".ar").forEach(a => {
        const on = a.dataset.a === cle || a.dataset.b === cle;
        a.classList.toggle("on", on);
        if (on){ voisins.add(a.dataset.a); voisins.add(a.dataset.b); }
      });
      svg.querySelectorAll(".nd").forEach(g => g.classList.toggle("on", voisins.has(g.dataset.cle)));
      racine.classList.add("survol");
    });
    racine.addEventListener("mouseout", e => {
      if (e.target.closest(".nd") && !e.relatedTarget?.closest?.(".nd")) racine.classList.remove("survol");
    });

    // bulle au survol des marques (ruban, point de courbe, bloc d'état)
    const bulle = document.createElement("div");
    bulle.className = "mo-bulle"; bulle.hidden = true;
    racine.append(bulle);
    const placerBulle = e => {
      const m = 14, w = bulle.offsetWidth, h = bulle.offsetHeight;
      bulle.style.left = Math.max(8, Math.min(e.clientX + m, innerWidth - w - 8)) + "px";
      bulle.style.top = (e.clientY + m + h > innerHeight ? e.clientY - h - m : e.clientY + m) + "px";
    };
    racine.addEventListener("mousemove", e => {
      const c = e.target.closest?.("[data-bulle]");
      if (!c){ bulle.hidden = true; return; }
      if (bulle.textContent !== c.dataset.bulle) bulle.textContent = c.dataset.bulle;
      bulle.hidden = false;
      placerBulle(e);
    });
    racine.addEventListener("mouseleave", () => { bulle.hidden = true; });

    if (options.fichiers){ E.fichiers = options.fichiers; }
    charger();
    // Ouvrir la bonne vue sur un élément, désigné par son nom SysML (ou son nom de l'Excel) : utilisé par les
    // liens de l'assistant IA. Renvoie false si le modèle n'est pas encore chargé, null si l'élément n'existe pas.
    function montrer(nom, vue){
      if (!E.G) return false;
      const bas = String(nom || "").toLowerCase(), ordre = ["composant", "etape", "besoin", "persona", "cas", "etat"];
      const x = E.G.noeuds.filter(n => (n.nom || "").toLowerCase() === bas || (n.libelle || "").toLowerCase() === bas)
        .sort((a, b) => ordre.indexOf(a.type) - ordre.indexOf(b.type))[0];
      if (!x) return null;
      if (x.type === "composant" || x.type === "etat"){ E.vue = "composant"; E.comp = x.type === "etat" ? x.composant : x.cle; }
      else if (x.type === "etape"){ E.vue = "cas"; E.cas = x.cas; }
      else if (x.type === "cas"){ E.vue = "cas"; E.cas = x.cle; }
      else E.vue = ["ensemble", "trace"].includes(vue) ? vue : "ensemble";
      dessinerVue(); choisir(x.cle);
      racine.querySelector(".mo-barre")?.scrollIntoView({block: "start", behavior: "smooth"});
      return true;
    }
    return {recharger: charger, lireFichiers, montrer};
  }

  window.RMonieModele = {monter};
})();
