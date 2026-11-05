/* Onglet « Analyses » : graphes calculés à partir du modèle LU DANS LES CODES SysML (/api/modele),
   comme l'onglet « Modèle lu dans le SysML » : rien ne vient de l'Excel, rien n'est inventé.
     couverture  nombre d'étapes qui satisfont chaque besoin (satisfy)
     emotions    émotion de chaque persona, étape par étape (attribut feedback), par cas d'usage
     composants  à quelle étape chaque composant change d'état (attributs grid…), tous les cas d'usage
   (La matrice besoins × étapes reste dans index.html.)
   Utilisation : RMonieAnalyses.afficher(element, vue, {jeton}). */
(() => {
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  // palette catégorielle de référence (validée daltonisme) : personas, dans l'ordre fixe du modèle
  const SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"];
  const SEQ = {fort: "#2a78d6", faible: "#cde2fb"};          // une teinte, clair -> foncé
  const cache = {};                                         // jeton -> graphe
  let etat = {cas: null};

  async function modele(jeton){
    if (!cache[jeton]){
      const r = await fetch(`/api/modele?jeton=${encodeURIComponent(jeton)}`);
      const d = await r.json();
      if (!r.ok || d.erreur) throw new Error(d.erreur || `erreur ${r.status}`);
      const N = {}; d.noeuds.forEach(n => N[n.cle] = n);
      cache[jeton] = {G: d, N};
    }
    return cache[jeton];
  }

  function bulle(){
    let b = document.getElementById("an-bulle");
    if (!b){ b = document.createElement("div"); b.id = "an-bulle"; b.className = "an-bulle"; b.hidden = true; document.body.append(b); }
    return b;
  }
  function brancherBulles(z){
    const b = bulle();
    z.addEventListener("mousemove", e => {
      const t = e.target.closest("[data-bulle]");
      if (!t){ b.hidden = true; return; }
      b.innerHTML = t.dataset.bulle; b.hidden = false;
      const x = Math.min(e.clientX + 14, innerWidth - b.offsetWidth - 8), y = e.clientY + 14 + b.offsetHeight > innerHeight ? e.clientY - b.offsetHeight - 10 : e.clientY + 14;
      b.style.left = x + "px"; b.style.top = y + "px";
    });
    z.addEventListener("mouseleave", () => b.hidden = true);
  }

  async function afficher(z, vue, {jeton}){
    z.innerHTML = '<p class="intro">Lecture du modèle dans les codes SysML…</p>';
    let M;
    try { M = await modele(jeton); }
    catch (e){ z.innerHTML = `<p class="erreur-lecture">Lecture impossible : ${esc(e.message)}</p>`; return; }
    if (!etat.cas || !M.N[etat.cas]) etat.cas = M.G.cas_usage[0]?.cle || null;
    const dessiner = () => {
      z.innerHTML = {couverture, emotions, composants}[vue](M);
      if (!z.dataset.branche){ brancherBulles(z); z.dataset.branche = "1"; }
    };
    z.onclick = e => { const c = e.target.closest("[data-an-cas]"); if (c){ etat.cas = c.dataset.anCas; dessiner(); } };
    dessiner();
  }

  // ------------------------------------------------------------ couverture des besoins
  function couverture({G, N}){
    const etiquette = e => { const n = N[e]; const k = G.cas_usage.findIndex(u => u.cle === n.cas) + 1; return `UC${k} · ${n.position}. ${n.libelle}`; };
    const B = G.noeuds.filter(n => n.type === "besoin").map(b => {
      const etapes = G.liens.filter(l => l.type === "satisfait" && l.vers === b.cle).map(l => l.de);
      return {b, etapes};
    }).sort((x, y) => y.etapes.length - x.etapes.length || x.b.libelle.localeCompare(y.b.libelle));
    const max = Math.max(1, ...B.map(x => x.etapes.length));
    const LG = 330, LB = 420, H = 26, PAD = 8;
    const w = LG + LB + 90, h = B.length * H + 34;
    let s = "";
    for (let v = 0; v <= max; v++){                      // graduations entières, discrètes
      const x = LG + (v / max) * LB;
      s += `<line x1="${x}" y1="18" x2="${x}" y2="${h - 6}" stroke="var(--ligne)" stroke-width="1"/><text x="${x}" y="12" text-anchor="middle" class="an-axe">${v}</text>`;
    }
    B.forEach(({b, etapes}, i) => {
      const y = 22 + i * H, n = etapes.length, lg = (n / max) * LB;
      const liste = etapes.map(e => `• ${esc(etiquette(e))}`).join("<br>") || "aucune étape";
      const bul = esc(`<b>${esc(b.libelle)}</b><br>${n} étape${n > 1 ? "s" : ""} (satisfy)<br>${liste}`);
      s += `<g data-bulle="${bul}"><rect x="0" y="${y - 2}" width="${w}" height="${H}" fill="transparent"/>
        <text x="${LG - 10}" y="${y + 13}" text-anchor="end" class="an-lib">${esc(b.libelle.length > 46 ? b.libelle.slice(0, 45) + "…" : b.libelle)}</text>
        ${n ? `<path d="M${LG},${y + 3} h${Math.max(lg - 4, 0)} a4,4 0 0 1 4,4 v6 a4,4 0 0 1 -4,4 h-${Math.max(lg - 4, 0)} z" fill="${SEQ.fort}"/>
              <text x="${LG + lg + 6}" y="${y + 13}" class="an-val">${n}</text>`
            : `<text x="${LG + 4}" y="${y + 13}" class="an-val an-alerte">⚠ 0 : satisfait par aucune étape</text>`}</g>`;
    });
    const zero = B.filter(x => !x.etapes.length).length;
    return `<p class="intro">Nombre d'étapes qui satisfont chaque besoin, lu dans les <code>satisfy Needs::…</code> des codes SysML.
      ${zero ? `<b class="an-alerte">${zero} besoin${zero > 1 ? "s" : ""} satisfait${zero > 1 ? "s" : ""} par aucune étape.</b>` : "Tous les besoins sont satisfaits par au moins une étape."}
      Survoler une barre pour la liste des étapes.</p>
      <div class="an-zone"><svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" aria-label="Couverture des besoins">${s}</svg></div>
      ${tableau(["Besoin", "Étapes", "Lesquelles"], B.map(({b, etapes}) => [b.libelle, etapes.length, etapes.map(etiquette).join(" ; ") || "—"]))}`;
  }

  // ------------------------------------------------------------ parcours émotionnel
  function choixCas(G, N){
    return `<div class="nav-uc">${G.cas_usage.map((u, k) => `<a href="javascript:void 0" data-an-cas="${esc(u.cle)}" class="${u.cle === etat.cas ? "actif" : ""}">${k + 1}. ${esc(N[u.cle].libelle)}</a>`).join("")}</div>`;
  }

  function emotions({G, N}){
    const u = G.cas_usage.find(x => x.cle === etat.cas);
    if (!u) return "<p class='intro'>Aucun cas d'usage.</p>";
    const personas = G.noeuds.filter(n => n.type === "persona");
    const couleur = {}; personas.forEach((p, i) => couleur[p.cle] = SERIES[i % SERIES.length]);   // couleur liée à la persona, pas au rang
    const pres = personas.filter(p => u.etapes.some(e => N[e].ressentis.some(r => r.persona === p.cle)));
    const E = u.etapes.map(e => N[e]);
    const ML = 46, MR = 150, MT = 18, HC = 280, PASX = Math.max(110, Math.min(170, 900 / Math.max(E.length, 1)));
    const w = ML + (E.length - 1) * PASX + MR + 20, h = MT + HC + 64;
    const X = i => ML + 20 + i * PASX, Y = v => MT + (5 - v) / 10 * HC;
    let s = "";
    [-5, -2.5, 0, 2.5, 5].forEach(v => {
      s += `<line x1="${ML}" y1="${Y(v)}" x2="${w - MR + 10}" y2="${Y(v)}" stroke="${v === 0 ? "var(--ligne-forte)" : "var(--ligne)"}" stroke-width="1" ${v === 0 ? "" : 'stroke-dasharray="2 4"'}/>`;
      if (Number.isInteger(v)) s += `<text x="${ML - 8}" y="${Y(v) + 4}" text-anchor="end" class="an-axe">${v > 0 ? "+" : ""}${v}</text>`;
    });
    E.forEach((n, i) => {
      s += `<text x="${X(i)}" y="${MT + HC + 20}" text-anchor="middle" class="an-axe">${n.position}</text>
            <text x="${X(i)}" y="${MT + HC + 36}" text-anchor="middle" class="an-axe an-petit">${esc(n.libelle.length > 18 ? n.libelle.slice(0, 17) + "…" : n.libelle)}</text>`;
    });
    const fins = [];
    pres.forEach((p, ip) => {
      const dx = (ip - (pres.length - 1) / 2) * 8;        // léger décalage : deux personas au même score restent visibles
      const XP = i => X(i) + dx;
      const pts = E.map((n, i) => { const r = n.ressentis.find(x => x.persona === p.cle); return r && !r.absent && r.score != null ? {i, r, n} : null; });
      let d = "", leve = true;
      pts.forEach(q => { if (!q){ leve = true; return; } d += `${leve ? "M" : "L"}${XP(q.i)},${Y(q.r.score)} `; leve = false; });
      s += `<path d="${d}" fill="none" stroke="${couleur[p.cle]}" stroke-width="2" stroke-linejoin="round"/>`;
      pts.forEach(q => {
        if (!q) return;
        const bul = esc(`<b>${esc(p.libelle)}</b> · étape ${q.n.position}. ${esc(q.n.libelle)}<br>émotion <b>${q.r.score > 0 ? "+" : ""}${q.r.score}</b>${q.r.insight ? "<br>" + esc(q.r.insight) : ""}${q.r.action ? "<br><i>" + esc(q.r.action) + "</i>" : ""}`);
        s += `<circle cx="${XP(q.i)}" cy="${Y(q.r.score)}" r="5" fill="${couleur[p.cle]}" stroke="#fff" stroke-width="2"/>
              <circle cx="${XP(q.i)}" cy="${Y(q.r.score)}" r="7" fill="transparent" data-bulle="${bul}"/>`;
      });
      const der = [...pts].reverse().find(Boolean);
      if (der) fins.push({p, y: Y(der.r.score), x: X(der.i) + (pres.length - 1) * 4});
    });
    fins.sort((a, b) => a.y - b.y);                       // étiquettes directes, sans chevauchement
    let dernier = -1e9;
    fins.forEach(f => { const y = Math.max(f.y, dernier + 14); dernier = y; s += `<text x="${f.x + 12}" y="${y + 4}" class="an-lib">${esc(f.p.libelle)}</text>`; });
    const legende = `<div class="an-legende">${pres.map(p => `<span><i style="background:${couleur[p.cle]}"></i>${esc(p.libelle)}</span>`).join("")}</div>`;
    const absents = E.flatMap(n => n.ressentis.filter(r => r.absent).map(r => `${N[r.persona]?.libelle || "?"} (étape ${n.position})`));
    return `${choixCas(G, N)}<p class="intro">Émotion de chaque persona à chaque étape (−5 à +5), lue dans l'attribut <code>feedback</code> des étapes.
      ${absents.length ? `Absente, donc pas de point : ${esc(absents.join(", "))}.` : ""} Survoler un point pour le ressenti.</p>
      ${legende}<div class="an-zone"><svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" aria-label="Parcours émotionnel">${s}</svg></div>
      ${tableau(["Persona", ...E.map(n => `${n.position}. ${n.libelle}`)], pres.map(p => [p.libelle, ...E.map(n => {
        const r = n.ressentis.find(x => x.persona === p.cle);
        return !r ? "—" : r.absent ? "absente" : (r.score > 0 ? "+" : "") + r.score;
      })]))}`;
  }

  // ------------------------------------------------------------ composants × étapes
  function composants({G, N}){
    const comps = G.noeuds.filter(n => n.type === "composant");
    const cols = G.cas_usage.flatMap((u, k) => u.etapes.map((e, j) => ({u, k, e, j})));
    const C = 26, GAP = 2, LG = 230, HT = 46;
    const w = LG + cols.length * (C + GAP) + 70, h = HT + comps.length * (C + GAP) + 10;
    let s = "", xs = LG;
    G.cas_usage.forEach((u, k) => {                     // en-têtes des cas d'usage
      const n = u.etapes.length, lg = n * (C + GAP) - GAP;
      s += `<text x="${xs + lg / 2}" y="14" text-anchor="middle" class="an-lib" style="font-weight:600">UC${k + 1}</text>
            <line x1="${xs}" y1="20" x2="${xs + lg}" y2="20" stroke="var(--ligne-forte)"/>`;
      u.etapes.forEach((e, j) => s += `<text x="${xs + j * (C + GAP) + C / 2}" y="${HT - 8}" text-anchor="middle" class="an-axe">${N[e].position}</text>`);
      xs += n * (C + GAP);
    });
    comps.forEach((c, r) => {
      const y = HT + r * (C + GAP);
      let changements = 0;
      s += `<text x="${LG - 10}" y="${y + C / 2 + 4}" text-anchor="end" class="an-lib">${esc(c.libelle.length > 32 ? c.libelle.slice(0, 31) + "…" : c.libelle)}</text>`;
      cols.forEach(({u, k, e, j}, i) => {
        const x = LG + i * (C + GAP), v = u.grille[c.cle]?.[e];
        const avant = j > 0 ? u.grille[c.cle]?.[u.etapes[j - 1]] : null;
        const change = v && ((avant && avant.texte.split(" > ").pop() !== v.texte.split(" > ")[0]) || v.texte.includes(" > "));
        if (change) changements++;
        const titre = `<b>${esc(c.libelle)}</b> · UC${k + 1} étape ${N[e].position}. ${esc(N[e].libelle)}<br>` +
          (v ? `état : <b>${esc(v.texte.replace(/ > /g, " → "))}</b>${change ? "<br>change d'état à cette étape" : ""}` : "absent de la grille à cette étape");
        s += `<rect x="${x}" y="${y}" width="${C}" height="${C}" rx="3" fill="${v ? (change ? SEQ.fort : SEQ.faible) : "#fff"}"
                ${v ? "" : 'stroke="var(--ligne)"'} data-bulle="${esc(titre)}"/>`;
      });
      s += `<text x="${LG + cols.length * (C + GAP) + 8}" y="${y + C / 2 + 4}" class="an-val">${changements}</text>`;
    });
    s += `<text x="${LG + cols.length * (C + GAP) + 8}" y="${HT - 8}" class="an-axe">chang.</text>`;
    const legende = `<div class="an-legende"><span><i style="background:${SEQ.fort}"></i>change d'état à cette étape</span>
      <span><i style="background:${SEQ.faible}"></i>même état qu'à l'étape précédente</span><span><i style="background:#fff;outline:1px solid var(--ligne)"></i>absent de la grille</span></div>`;
    return `<p class="intro">Pour chaque composant, les étapes où il change d'état, lues dans les attributs <code>grid…</code> des cas d'usage
      (« A > B » dans une case compte comme un changement). Dernière colonne : nombre de changements. Survoler une case pour l'état.</p>
      ${legende}<div class="an-zone"><svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" aria-label="Composants × étapes">${s}</svg></div>`;
  }

  function tableau(tete, lignes){
    return `<details class="an-table"><summary>Voir en tableau</summary><div class="an-zone"><table class="mo-table"><thead><tr>${tete.map(t => `<th>${esc(t)}</th>`).join("")}</tr></thead>
      <tbody>${lignes.map(l => `<tr>${l.map(c => `<td style="cursor:default">${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div></details>`;
  }

  window.RMonieAnalyses = {afficher, oublier: () => { for (const k in cache) delete cache[k]; etat.cas = null; }};
})();
