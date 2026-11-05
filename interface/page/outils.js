// Outils partagés : enregistrer un schéma du lecteur en image, pour les slides ou un rapport.
(() => {
  const PROPRIETES = ["fill", "fill-opacity", "stroke", "stroke-width", "stroke-dasharray", "stroke-opacity", "opacity",
    "font-family", "font-size", "font-weight", "font-style", "text-anchor", "dominant-baseline"];

  function copierStyles(source, copie){
    const s = getComputedStyle(source);
    copie.setAttribute("style", PROPRIETES.map(p => `${p}:${s.getPropertyValue(p)}`).join(";"));
    [...source.children].forEach((c, k) => { if (copie.children[k]) copierStyles(c, copie.children[k]); });
  }

  // Le schéma tel qu'il est affiché, sur fond blanc, en PNG deux fois plus net que l'écran.
  async function imageSvg(svg, nom){
    const message = t => window.toast?.(t);
    try {
      const L = +svg.getAttribute("width") || svg.clientWidth, H = +svg.getAttribute("height") || svg.clientHeight;
      const copie = svg.cloneNode(true);
      copierStyles(svg, copie);
      copie.setAttribute("xmlns", "http://www.w3.org/2000/svg");
      copie.setAttribute("width", L);
      copie.setAttribute("height", H);
      copie.querySelectorAll("title").forEach(t => t.remove());
      const fond = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      fond.setAttribute("width", L); fond.setAttribute("height", H); fond.setAttribute("fill", "#fff");
      copie.insertBefore(fond, copie.firstChild);
      const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(copie)], {type: "image/svg+xml;charset=utf-8"}));
      const img = new Image();
      await new Promise((ok, non) => { img.onload = ok; img.onerror = () => non(new Error("dessin illisible")); img.src = url; });
      const echelle = Math.min(2, 8000 / Math.max(L, H));
      const toile = document.createElement("canvas");
      toile.width = Math.round(L * echelle); toile.height = Math.round(H * echelle);
      toile.getContext("2d").drawImage(img, 0, 0, toile.width, toile.height);
      URL.revokeObjectURL(url);
      const blob = await new Promise(ok => toile.toBlob(ok, "image/png"));
      if (!blob) throw new Error("image trop grande");
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob); a.download = nom;
      document.body.append(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 1500);
      message(`Schéma téléchargé : ${nom}`);
    } catch (e){ message("Image impossible : " + e.message); }
  }

  window.RMonieOutils = {imageSvg};
})();
