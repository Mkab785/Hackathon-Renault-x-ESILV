"""
Point d'entrée unique de la traduction, utilisé par la ligne de commande, par
l'interface web, et plus tard par un assistant de correction :

    res = traduire(dataset)
    res.ok           -> True si un .sysml utilisable a été produit
    res.texte        -> le SysML v2 (None si des erreurs bloquantes)
    res.problemes    -> contrôles (erreurs / avertissements)
    res.couverture   -> chaque id UserShaker traduit est-il bien dans le texte ?
    res.trace        -> lignes (onglet, id, élément SysML) pour le CSV

Brancher un assistant (IA ou autre) plus tard :
    ds = lire_xlsx(...)            # ou depuis_dict(...)
    ds = assistant.corriger(ds)    # renvoie un Dataset au même schéma
    res = traduire(ds)             # rien d'autre ne change
"""
import csv
import io
import re
from collections import Counter
from dataclasses import dataclass, field

from .controles import controler, peut_traduire, Probleme
from .modele import construire, ErreurModele
from .rendu import rendre, taille_octets, BUDGET_OCTETS
from .schema import PRIMARY_KEY
from .verification import verifier_relecture

# Ce qui est traduit dans le format CATIA Community, et ce qui ne l'est pas (encore).
TRADUIT = ["use_cases", "steps", "step_triggers", "personas", "components", "user_needs"]
LIENS_TRADUITS = ["use_case_personas", "step_user_needs"]
NON_TRADUIT = {
    "step_groups": "groupes d'étapes (phases)",
    "persona_step_feedback": "ressentis et scores d'émotion",
    "component_states": "états en tant qu'éléments (leurs noms figurent dans les déclencheurs)",
    "use_case_components": "liste des composants par cas d'usage",
    "step_component_states": "grille composant × étape",
    "step_unused_components": "composants marqués « non utilisés »",
}
TEXTES_NON_TRADUITS = ("descriptions, histoire des cas d'usage, biographies, notes, images, "
                       "catégories et rôles des composants, composants parents")


@dataclass
class LigneCouverture:
    onglet: str
    attendus: int
    trouves: int

    @property
    def ok(self):
        return self.attendus == self.trouves


@dataclass
class Resultat:
    ok: bool
    texte: str = None
    package: str = ""
    problemes: list = field(default_factory=list)
    couverture: list = field(default_factory=list)
    trace: list = field(default_factory=list)
    trace_detail: list = field(default_factory=list)   # lignes lisibles Excel <-> SysML
    verification: list = field(default_factory=list)   # relecture du SysML comparée à l'Excel
    taille: int = 0
    budget: int = BUDGET_OCTETS

    @property
    def erreurs(self):
        return [p for p in self.problemes if p.gravite == "erreur"]

    @property
    def bloquants(self):
        return [p for p in self.problemes if p.bloque]

    @property
    def avertissements(self):
        return [p for p in self.problemes if p.gravite == "avertissement"]

    @property
    def dans_budget(self):
        return self.taille <= self.budget


def traduire(ds, budget=BUDGET_OCTETS):
    problemes = controler(ds)
    res = Resultat(ok=False, problemes=problemes, budget=budget)
    if not peut_traduire(problemes):
        return res
    try:
        mod = construire(ds)
    except (ErreurModele, KeyError, TypeError, ValueError) as e:
        problemes.append(Probleme("E99", "erreur", f"construction du modèle impossible : {e}", bloque=True))
        return res
    texte = rendre(mod)
    res.texte, res.package, res.trace = texte, mod.package, mod.trace
    res.trace_detail = trace_detaillee(ds, mod)
    res.verification = verifier_relecture(ds, texte)
    res.taille = taille_octets(texte)
    res.couverture = couverture(ds, texte)
    if not res.dans_budget:
        problemes.append(Probleme(
            "E20", "erreur",
            f"le modèle fait {res.taille} octets, au-delà du budget de {budget} octets accepté par "
            "CATIA Magic Community : il risque d'être refusé au collage.", bloque=False))
    ecarts = [v for v in res.verification if not v["ok"]]
    if ecarts:
        problemes.append(Probleme(
            "E21", "erreur", f"la relecture du SysML trouve {len(ecarts)} écart(s) avec l'Excel "
            "(voir la vérification).", bloque=False))
    res.ok = all(l.ok for l in res.couverture) and res.dans_budget and not ecarts
    return res


def couverture(ds, texte):
    """Compte, pour chaque onglet traduit, combien d'ids se retrouvent dans le texte."""
    docs = Counter(re.findall(r"doc /\* (.*?) \*/", texte))
    lignes = []
    for sheet in TRADUIT:
        ids = [r.get(PRIMARY_KEY[sheet]) for r in ds.get(sheet)]
        lignes.append(LigneCouverture(sheet, len(ids), sum(1 for i in ids if docs.get(i))))
    # liens
    blocs = _blocs_use_cases(texte)
    n_act = sum(len(re.findall(r"^actor ", b, re.M)) for b in blocs)
    attendus = len({(r.get("use_case_id"), r.get("persona_id")) for r in ds.get("use_case_personas")})
    lignes.append(LigneCouverture("use_case_personas", attendus, n_act))
    n_sat = len(re.findall(r"^satisfy ", texte, re.M))
    attendus = len({(r.get("step_id"), r.get("user_need_id")) for r in ds.get("step_user_needs")})
    lignes.append(LigneCouverture("step_user_needs", attendus, n_sat))
    n_succ = len(re.findall(r"^first \S+ then \S+;$", texte, re.M))
    par_uc = Counter(r.get("use_case_id") for r in ds.get("steps"))
    attendus = sum(max(n - 1, 0) for n in par_uc.values())
    lignes.append(LigneCouverture("enchaînements d'étapes", attendus, n_succ))
    return lignes


def _blocs_use_cases(texte):
    return re.split(r"^use case def ", texte, flags=re.M)[1:]


TYPES_SYSML = {
    "personas": "part (persona)",
    "components": "part def (composant)",
    "user_needs": "requirement (besoin)",
    "use_cases": "use case def",
    "use_case_personas": "actor",
    "steps": "action (étape)",
    "step_triggers": "attribute (déclencheur)",
    "step_user_needs": "satisfy (étape -> besoin)",
    "ordre": "first … then … (enchaînement)",
}

COLONNES_TRACE = [
    ("onglet_excel", "Onglet Excel"),
    ("ligne_excel", "Ligne Excel"),
    ("dans_excel", "Dans l'Excel"),
    ("type_sysml", "Type SysML"),
    ("element_sysml", "Élément SysML"),
    ("ligne_sysml", "Ligne du .sysml"),
    ("id", "Id UserShaker"),
]


def trace_detaillee(ds, mod):
    """Une ligne par élément traduit : où il est dans l'Excel, ce qu'il y dit, où il est dans le SysML."""
    idx = {}
    for sheet, pk in PRIMARY_KEY.items():
        for i, r in enumerate(ds.get(sheet)):
            idx.setdefault((sheet, r.get(pk)), i)
    for sheet, a, b in (("use_case_personas", "use_case_id", "persona_id"),
                        ("step_user_needs", "step_id", "user_need_id")):
        for i, r in enumerate(ds.get(sheet)):
            idx.setdefault((sheet, f"{r.get(a)}->{r.get(b)}"), i)
    nom = {}
    for sheet, pk in PRIMARY_KEY.items():
        for r in ds.get(sheet):
            nom[r.get(pk)] = r.get("name")
    comp = {c["component_id"]: c["name"] for c in ds.get("components")}
    etat = {s["state_id"]: s["name"] for s in ds.get("component_states")}
    trig = {t["trigger_id"]: t for t in ds.get("step_triggers")}
    pos = {s["step_id"]: s.get("position") for s in ds.get("steps")}

    def libelle(onglet, cle):
        if onglet == "step_triggers":
            t = trig[cle]
            k = "déclencheur" if t["kind"] == "trigger" else "condition"
            return f"{k} : {comp.get(t['component_id'])} {t.get('operator') or 'is'} {etat.get(t['state_id'])}"
        if onglet == "use_case_personas":
            u, p = cle.split("->")
            return f"{nom.get(p)} participe à « {nom.get(u)} »"
        if onglet == "step_user_needs":
            s, n = cle.split("->")
            return f"l'étape « {nom.get(s)} » sert le besoin « {nom.get(n)} »"
        if onglet == "steps":
            return f"étape {pos.get(cle)} : {nom.get(cle)}"
        return nom.get(cle)

    lignes = []
    for onglet, cle, elem in mod.trace:
        i = idx.get((onglet, cle))
        lignes.append({
            "onglet_excel": onglet,
            "ligne_excel": ds.row_number(onglet, i) if i is not None else None,
            "id": cle,
            "dans_excel": libelle(onglet, cle),
            "type_sysml": TYPES_SYSML.get(onglet, ""),
            "element_sysml": elem.replace(f"{mod.package}::", "", 1),
            "ligne_sysml": mod.lignes.get(cle),
        })
    # enchaînements : déduits de la colonne position de l'onglet steps
    for cu in mod.cas_usage:
        for a, b in zip(cu.etapes, cu.etapes[1:]):
            i = idx.get(("steps", b.id))
            lignes.append({
                "onglet_excel": "steps",
                "ligne_excel": ds.row_number("steps", i) if i is not None else None,
                "id": f"{a.id}=>{b.id}",
                "dans_excel": f"étape {pos.get(a.id)} « {nom.get(a.id)} » puis étape {pos.get(b.id)} « {nom.get(b.id)} »",
                "type_sysml": TYPES_SYSML["ordre"],
                "element_sysml": f"UseCases::{cu.name} : first {a.name} then {b.name}",
                "ligne_sysml": mod.lignes.get(f"{a.id}=>{b.id}"),
            })
    lignes.sort(key=lambda l: (l["ligne_sysml"] or 10 ** 9))
    return lignes


def trace_csv(res):
    """Table de traçabilité au format CSV (séparateur ; pour Excel en français)."""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow([t for _, t in COLONNES_TRACE])
    for row in res.trace_detail:
        w.writerow(["" if row[k] is None else row[k] for k, _ in COLONNES_TRACE])
    return buf.getvalue()


def ecrire_trace(res, chemin):
    with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
        f.write(trace_csv(res))


def rapport_texte(res, source=""):
    """Rapport lisible (console ou fichier)."""
    out = []
    p = out.append
    p("=" * 70)
    p("TRADUCTION USERSHAKER -> SYSML V2" + (f"  ({source})" if source else ""))
    p("=" * 70)
    nb, ne, na = len(res.bloquants), len(res.erreurs), len(res.avertissements)
    p(f"Contrôles : {nb} bloquant(s), {ne} erreur(s) au total, {na} avertissement(s)")
    for pb in res.bloquants:
        p("  " + str(pb))
    autres = [x for x in res.erreurs if not x.bloque]
    for pb in autres:
        p("  " + str(pb))
    if res.texte is None:
        p("")
        p("=> AUCUN MODÈLE PRODUIT : corriger d'abord les erreurs bloquantes.")
        if res.avertissements:
            p("")
            p("Avertissements :")
            for pb in res.avertissements:
                p("  " + str(pb))
        return "\n".join(out) + "\n"
    p("")
    p(f"Taille : {res.taille} octets (budget CATIA Community : {res.budget}) "
      + ("OK" if res.dans_budget else "TROP GROS"))
    p("")
    p("Couverture (ids UserShaker retrouvés dans le modèle) :")
    p(f"  {'onglet':<26}{'attendus':>9}{'trouvés':>9}")
    for l in res.couverture:
        p(f"  {l.onglet:<26}{l.attendus:>9}{l.trouves:>9}" + ("" if l.ok else "   <-- MANQUE"))
    ok_v = sum(1 for v in res.verification if v["ok"])
    p("")
    p(f"Relecture du SysML comparée à l'Excel : {ok_v}/{len(res.verification)} élément(s) conforme(s)")
    for v in res.verification:
        if not v["ok"]:
            p(f"  [ÉCART] {v['categorie']} {v['onglet']} ligne {v['ligne_excel']} : {' ; '.join(v['ecarts'])}")
    p("")
    p("Non traduit dans ce format (limite de taille CATIA Community) :")
    for k, v in NON_TRADUIT.items():
        p(f"  - {k} : {v}")
    p(f"  - textes : {TEXTES_NON_TRADUITS}")
    if res.avertissements:
        p("")
        p(f"Avertissements ({na}) — à remonter à l'équipe UX :")
        for pb in res.avertissements:
            p("  " + str(pb))
    p("")
    p("=> MODÈLE PRÊT POUR CATIA" if res.ok else "=> MODÈLE PRODUIT, MAIS À VÉRIFIER (voir ci-dessus)")
    return "\n".join(out) + "\n"
