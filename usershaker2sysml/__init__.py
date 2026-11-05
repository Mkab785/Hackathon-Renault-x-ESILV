"""Traducteur UserShaker (xlsx) -> SysML v2 textuel pour CATIA Magic. Version V1.

Traduction complète (site et ligne de commande) : traduire_complet -> un code par cas d'usage.
Ancienne traduction résumée en un seul code (validée 62/62) : traduire.
"""
from .lecture import lire_xlsx, depuis_dict, ecrire_xlsx, Dataset
from .controles import controler, peut_traduire, Probleme
from .traduction import traduire, ecrire_trace, trace_csv, rapport_texte, Resultat
from .traduction_complete import traduire_complet, rapport_complet, ResultatComplet, NON_TRADUIT_COMPLET
from .rendu_cas_usage import rendre_cas_usage, LIMITE_CATIA, taille_catia
from .relecture_complete import verifier_complet, relire_code
from .apercu import apercu
from .trace_xlsx import trace_xlsx, trace_xlsx_complet
from .verification import verifier_relecture, relire

__version__ = "1.1"
