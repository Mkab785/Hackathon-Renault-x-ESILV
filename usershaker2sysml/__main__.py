"""
Ligne de commande :

    python -m usershaker2sysml "Renault E-Space concept_export_v1.0.xlsx"
    python -m usershaker2sysml fichier.xlsx -o sortie

Produit dans le dossier de sortie (par défaut : ./sortie) :
    UC1....sysml, UC2....sysml ...   un code SysML v2 par cas d'usage (traduction complète),
                                     chacun à coller dans son propre projet CATIA Magic Community
    code_entier/<Projet>CodeEntier.sysml   un seul code avec tous les cas d'usage, sans découpage,
                                     pour CATIA Magic sans la limite de 20 000 caractères
    <Projet>_trace.xlsx              traçabilité Excel <-> codes + vérification par relecture
    <Projet>_rapport.txt             contrôles, codes et tailles, couverture, vérification
Le fichier xlsx d'origine n'est jamais modifié.

Codes de sortie : 0 = codes prêts, 1 = codes produits mais à vérifier,
                  2 = aucun code (erreurs bloquantes ou fichier illisible).
"""
import argparse
import sys
from pathlib import Path

from . import lire_xlsx
from .rendu_cas_usage import LIMITE_CATIA
from .trace_xlsx import trace_xlsx_complet
from .traduction_complete import rapport_complet, traduire_complet


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog="usershaker2sysml",
                                 description="Traduit un export UserShaker (xlsx) en SysML v2 pour CATIA Magic, "
                                             "un code par cas d'usage.")
    ap.add_argument("xlsx", help="fichier exporté par UserShaker")
    ap.add_argument("-o", "--out", default="sortie", help="dossier de sortie (défaut : ./sortie)")
    ap.add_argument("--limite", type=int, default=LIMITE_CATIA,
                    help=f"caractères au plus par code (défaut : {LIMITE_CATIA}, limite de CATIA Community)")
    a = ap.parse_args(argv)

    src = Path(a.xlsx)
    if not src.exists():
        print(f"Fichier introuvable : {src}")
        return 2
    try:
        ds = lire_xlsx(src)
    except PermissionError:
        print(f"Accès refusé à {src.name} : le fichier est probablement ouvert dans Excel. "
              "Fermez-le puis relancez.")
        return 2
    except Exception as e:
        print(f"Impossible de lire le fichier : {e}")
        return 2

    res = traduire_complet(ds, limite=a.limite)
    rapport = rapport_complet(res, src.name)
    print(rapport)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    base = res.package or "rapport"
    ecrits = []
    try:
        (out / f"{base}_rapport.txt").write_text(rapport, encoding="utf-8")
        ecrits.append(out / f"{base}_rapport.txt")
        if not res.traduit:
            return 2
        for c in res.codes:
            (out / c["fichier"]).write_text(c["texte"], encoding="utf-8", newline="\n")
            ecrits.append(out / c["fichier"])
        if res.code_entier:                       # un seul code, pour CATIA Magic sans limite de taille
            entier = out / "code_entier"
            entier.mkdir(exist_ok=True)
            (entier / res.code_entier["fichier"]).write_text(res.code_entier["texte"], encoding="utf-8", newline="\n")
            ecrits.append(entier / res.code_entier["fichier"])
        (out / f"{base}_trace.xlsx").write_bytes(trace_xlsx_complet(res, src.name))
        ecrits.append(out / f"{base}_trace.xlsx")
    except PermissionError as e:
        print(f"Écriture impossible ({e.filename}) : le fichier est probablement ouvert (Excel, Bloc-notes). "
              "Fermez-le puis relancez.")
        return 2
    finally:
        for f in ecrits:
            print(f"Écrit : {f}")
    return 0 if res.ok else 1


if __name__ == "__main__":
    sys.exit(main())
