"""
Fabrication de noms SysML v2 valides et lisibles à partir des noms UserShaker.

    "Welcome on board"  -> WelcomeOnBoard   (définitions : PascalCase)
    "Jacques Martin"    -> jacquesMartin    (usages : camelCase)

Règles : accents retirés, seuls lettres/chiffres gardés, pas de mot réservé
SysML (suffixe _), pas de chiffre en tête (préfixe n). Les doublons dans un
même espace de noms reçoivent un suffixe 2, 3...
"""
import re
import unicodedata

# Mots réservés SysML v2 (un nom identique doit être modifié). Liste de la spécification,
# complétée par les mots signalés manquants (OMG SYSML21-11 : constant, effect, feature,
# locale, meta, new) et par « library », refusé par CATIA comme nom d'attribut (4 nov. 2026).
KEYWORDS = set("""about abstract accept action actor after alias all allocate allocation analysis
and as assert assign assume at attribute bind binding by calc case comment concern connect
connection constant constraint crosses decide def default defined dependency derived do doc
else end entry enum event exhibit exit expose false filter first flow for fork frame from if
implies import in include individual inout interface istype item join language loop merge
message metadata multiplicity nonunique not null objective occurrence of or ordered out
package parallel part perform port private protected public redefines ref references render
rendering rep require requirement return satisfy send snapshot specializes stakeholder
standard start state subject subsets succession terminate then timeslice to transition true
until use variant variation verification verify via view viewpoint when while xor
hastype library locale meta new effect feature namespace const member""".split())


def strip_accents(s):
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")


def words(s):
    return re.findall(r"[A-Za-z0-9]+", strip_accents("" if s is None else str(s)))


def _safe(r, fallback):
    if not r:
        r = fallback
    if r[0].isdigit():
        r = "n" + r
    if r in KEYWORDS:
        r = r + "_"
    return r


def camel(s, fallback="x"):
    ws = words(s)
    if not ws:
        return _safe("", fallback)
    r = ws[0][0].lower() + ws[0][1:] + "".join(w[0].upper() + w[1:] for w in ws[1:])
    return _safe(r, fallback)


def pascal(s, fallback="X"):
    ws = words(s)
    r = "".join(w[0].upper() + w[1:] for w in ws)
    return _safe(r, fallback)


class Scope:
    """Garantit des noms uniques dans un même espace de noms."""

    def __init__(self, reserved=()):
        self.used = set(reserved)

    def uniq(self, base):
        name, i = base, 2
        while name in self.used:
            name = f"{base}{i}"
            i += 1
        self.used.add(name)
        return name


def chaine(s):
    """Littéral chaîne SysML v2 entre guillemets (échappements du standard KerML)."""
    s = "" if s is None else str(s)
    s = s.replace("\\", "\\\\").replace('"', '\\"').replace("\r", "").replace("\n", "\\n")
    return f'"{s}"'


def commentaire(s):
    """Contenu sûr pour un doc /* ... */ (on casse une éventuelle fin de commentaire)."""
    return ("" if s is None else str(s)).replace("*/", "* /").replace("\r", "").replace("\n", " ")
