"""
Contrôle indépendant de la grammaire SysML v2 avec SysML2Tools (DEMA Consulting, open source),
qui analyse les codes avec la grammaire officielle de l'OMG.

Facultatif : si l'outil n'est pas installé, le contrôle est simplement indiqué « non disponible ».
Installation (une fois) :
    winget install Microsoft.DotNet.SDK.8
    dotnet tool install -g DemaConsulting.SysML2Tools.Tool --version 0.1.0-beta.5

On n'utilise que sa commande « lint » : sa version beta lit les codes sans erreur, mais ne
modélise pas encore le contenu des cas d'usage (étapes, enchaînements, satisfy). L'affichage
du modèle sur le site passe donc par modele_sysml.py.
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

RE_ERREUR = re.compile(r"^(.*?)\((\d+),(\d+)\): (error|warning): (.*)$")


def trouver_outil():
    chemin = shutil.which("sysml2tools")
    if chemin:
        return chemin
    for nom in ("sysml2tools.exe", "sysml2tools"):                 # outil .NET global pas encore dans le PATH
        p = Path.home() / ".dotnet" / "tools" / nom
        if p.exists():
            return str(p)
    return None


def controler_grammaire(codes, delai=120):
    """codes : [(nom_du_fichier, texte)]. Renvoie
    {disponible, ok, erreurs [{fichier, ligne, colonne, gravite, message}], fichiers, detail}."""
    outil = trouver_outil()
    if not outil:
        return {"disponible": False, "ok": None, "erreurs": [], "fichiers": len(codes),
                "detail": "SysML2Tools n'est pas installé sur ce PC (contrôle facultatif)."}
    with tempfile.TemporaryDirectory(prefix="r-monie-") as dossier:
        chemins = []
        for k, (nom, texte) in enumerate(codes):
            sur = re.sub(r"[^\w.-]", "_", Path(nom).name) or f"code{k}.sysml"
            p = Path(dossier) / f"{k:02d}_{sur}"
            p.write_text(texte, encoding="utf-8", newline="\n")
            chemins.append(p)
        noms = {str(p.resolve()).lower(): nom for p, (nom, _) in zip(chemins, codes)}
        try:
            r = subprocess.run([outil, "lint", *map(str, chemins)], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=delai)
        except (OSError, subprocess.TimeoutExpired) as e:
            return {"disponible": True, "ok": None, "erreurs": [], "fichiers": len(codes),
                    "detail": f"SysML2Tools n'a pas pu être lancé : {e}"}
    erreurs = []
    for ligne in (r.stdout + "\n" + r.stderr).splitlines():
        m = RE_ERREUR.match(ligne.strip())
        if m:
            fichier = noms.get(str(Path(m.group(1)).resolve()).lower(), Path(m.group(1)).name)
            erreurs.append({"fichier": fichier, "ligne": int(m.group(2)), "colonne": int(m.group(3)),
                            "gravite": "erreur" if m.group(4) == "error" else "avertissement",
                            "message": m.group(5)})
    ok = r.returncode == 0 and not any(e["gravite"] == "erreur" for e in erreurs)
    return {"disponible": True, "ok": ok, "erreurs": erreurs, "fichiers": len(codes),
            "detail": "grammaire SysML v2 de l'OMG, commande « sysml2tools lint »"}
