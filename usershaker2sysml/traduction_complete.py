"""
Traduction complète (utilisée par le site et la ligne de commande) :

    export UserShaker (xlsx brut)
      -> contrôles des données (controles.py)
      -> un code SysML v2 par cas d'usage, écriture compacte (rendu_cas_usage.py),
         chacun sous la limite de CATIA Magic Community (20 000 caractères) ;
         un cas d'usage trop long est coupé en parties
      -> relecture indépendante des codes, comparée à l'Excel élément par élément
         (relecture_complete.py), traçabilité et couverture.

Les cas d'usage sont indépendants : chaque code se colle seul, dans son propre projet
CATIA. Sur le site, les codes sont affichés ensemble, comme un seul modèle.

En plus : le CODE ENTIER (res.code_entier), un seul texte avec tous les cas d'usage, sans
découpage, pour CATIA Magic sans la limite de 20 000 caractères (version complète). Il est relu
et comparé à l'Excel de la même façon (res.code_entier["verification_ok"] / ["verification_total"]).
Le nombre de cas d'usage (1, 3, 4, 5...) et de codes n'est jamais fixé : il suit l'export.
Seuls les liens des images des étapes ne sont pas traduits (ils restent dans l'Excel).
"""
from collections import OrderedDict
from dataclasses import dataclass, field

from .controles import Probleme, controler, peut_traduire
from .noms import pascal
from .relecture_complete import verifier_complet
from .rendu_cas_usage import LIMITE_CATIA, ErreurDecoupage, rendre_cas_usage, rendre_code_entier, decouper_code_entier
from .traduction import LigneCouverture

NON_TRADUIT_COMPLET = {     # colonnes de l'Excel absentes des codes (elles restent dans l'Excel)
    "steps.image_url": "liens des images des étapes",
    "personas.color, step_groups.color": "couleurs d'affichage des personas et des groupes d'étapes",
    "personas.library_*, components.library_*, user_needs.library_id":
        "champs de bibliothèque UserShaker (le nom de bibliothèque des besoins, lui, est traduit)",
    "meta": "informations d'export autres que le nom du projet et la date (entreprise, id du projet, nombres de lignes)",
}

ORDRE_COUVERTURE = ["personas", "components", "component_states", "user_needs", "use_cases", "use_case_personas",
                    "use_case_components", "step_groups", "steps", "step_triggers", "step_user_needs",
                    "step_component_states", "persona_step_feedback", "step_unused_components",
                    "enchaînements d'étapes"]


@dataclass
class ResultatComplet:
    ok: bool
    problemes: list = field(default_factory=list)
    codes: list = field(default_factory=list)          # un dict par code (voir traduire_complet)
    projet: str = ""
    package: str = ""                                   # nom de base des fichiers (rapport, traçabilité)
    limite: int = LIMITE_CATIA
    verification: list = field(default_factory=list)   # une ligne par élément relu (relecture_complete)
    trace_detail: list = field(default_factory=list)   # une ligne par donnée de l'Excel
    trace: list = field(default_factory=list)          # (onglet, id, élément SysML) pour l'aperçu
    couverture: list = field(default_factory=list)
    code_entier: dict = None                            # un seul code, tous les cas d'usage (voir code_entier())

    @property
    def traduit(self):
        return bool(self.codes)

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
    def plus_gros(self):
        return max((c["taille_catia"] for c in self.codes), default=0)


def traduire_complet(ds, limite=LIMITE_CATIA):
    problemes = controler(ds)
    projet = ds.meta().get("project_name") or ""
    res = ResultatComplet(ok=False, problemes=problemes, limite=limite, projet=projet,
                          package=pascal(projet, "UserShakerProject"))
    if not peut_traduire(problemes):
        return res
    try:
        sorties = rendre_cas_usage(ds, limite)
    except ErreurDecoupage as e:
        problemes.append(Probleme("E22", "erreur", f"traduction impossible sous la limite de CATIA : {e}", bloque=True))
        return res
    except (KeyError, TypeError, ValueError) as e:
        problemes.append(Probleme("E99", "erreur", f"traduction impossible : {e}", bloque=True))
        return res
    res.codes = [{"fichier": f, "package": p, "texte": t, "numero": i["numero"], "partie": i["partie"],
                  "parties": i["parties"], "cas_usage": i["cas_usage"], "etapes": i["etapes"],
                  "caracteres": i["caracteres"], "taille_catia": i["taille_catia"], "lignes": i["lignes"]}
                 for f, p, t, i in sorties]
    res.verification, res.trace_detail = verifier_complet(ds, [(c["fichier"], c["texte"]) for c in res.codes])
    res.trace = [(t["onglet_excel"], t["id"], t["element_sysml"]) for t in res.trace_detail if t["ligne_sysml"]]
    res.couverture = couverture_complete(res.trace_detail)
    trop = [c for c in res.codes if c["taille_catia"] > limite]
    if trop:   # ne devrait pas arriver : le découpage garantit la limite
        problemes.append(Probleme("E20", "erreur", f"{len(trop)} code(s) au-delà de {limite} caractères.", bloque=False))
    ecarts = [v for v in res.verification if not v["ok"]]
    if ecarts:
        problemes.append(Probleme(
            "E21", "erreur", f"la relecture des codes trouve {len(ecarts)} écart(s) avec l'Excel "
            "(voir la vérification).", bloque=False))
    res.ok = all(l.ok for l in res.couverture) and not ecarts and not trop
    try:
        res.code_entier = code_entier(ds)
    except (KeyError, TypeError, ValueError) as e:     # ne bloque jamais les codes par cas d'usage
        problemes.append(Probleme("E23", "avertissement", f"code entier non produit : {e}"))
    return res


def code_entier(ds):
    """Le code entier, relu et comparé à l'Excel comme les codes par cas d'usage."""
    fichier, package, texte, infos = rendre_code_entier(ds)
    parts = decouper_code_entier(texte) or []
    verification, trace = verifier_complet(ds, [(fichier, t) for _, t in parts]) if parts else ([], [])
    return {"fichier": fichier, "package": package, "texte": texte, "numero": None, "partie": 1, "parties": 1,
            "cas_usage": f"tous les cas d'usage ({infos['cas_usage']})", "nb_cas_usage": infos["cas_usage"],
            "etapes": infos["etapes"], "caracteres": infos["caracteres"], "taille_catia": infos["taille_catia"],
            "lignes": infos["lignes"], "verification_ok": sum(1 for v in verification if v["ok"]),
            "verification_total": len(verification),
            "lignes_excel_retrouvees": sum(1 for x in trace if x["ligne_sysml"]), "lignes_excel": len(trace)}


def couverture_complete(trace_detail):
    """Pour chaque onglet : lignes de l'Excel attendues, et retrouvées dans les codes."""
    comptes = OrderedDict((o, [0, 0]) for o in ORDRE_COUVERTURE)
    for t in trace_detail:
        o = "enchaînements d'étapes" if "=>" in str(t["id"]) else t["onglet_excel"]
        c = comptes.setdefault(o, [0, 0])
        c[0] += 1
        c[1] += 1 if t["ligne_sysml"] else 0
    return [LigneCouverture(o, a, f) for o, (a, f) in comptes.items() if a]


def rapport_complet(res, source=""):
    """Rapport lisible (console ou fichier) de la traduction complète."""
    out = []
    p = out.append
    p("=" * 70)
    p("TRADUCTION USERSHAKER -> SYSML V2, COMPLÈTE PAR CAS D'USAGE" + (f"  ({source})" if source else ""))
    p("=" * 70)
    nb, ne, na = len(res.bloquants), len(res.erreurs), len(res.avertissements)
    p(f"Contrôles : {nb} bloquant(s), {ne} erreur(s) au total, {na} avertissement(s)")
    for pb in res.bloquants:
        p("  " + str(pb))
    for pb in [x for x in res.erreurs if not x.bloque]:
        p("  " + str(pb))
    if not res.traduit:
        p("")
        p("=> AUCUN CODE PRODUIT : corriger d'abord les erreurs bloquantes.")
    else:
        p("")
        p(f"Codes pour CATIA Magic Community ({len(res.codes)}) — un projet CATIA par code, "
          f"limite {res.limite} caractères par code :")
        for c in res.codes:
            partie = f", partie {c['partie']}/{c['parties']}" if c["parties"] > 1 else ""
            p(f"  {c['fichier']:<48} {c['caracteres']:>6} caractères (pire cas {c['taille_catia']})"
              f"  cas d'usage {c['numero']}{partie}, {c['etapes']} étape(s)"
              + ("" if c["taille_catia"] <= res.limite else "   <-- TROP GROS"))
        ce = res.code_entier
        if ce:
            p("")
            p(f"Code entier (CATIA Magic sans limite, un seul projet) : {ce['fichier']}, {ce['caracteres']} caractères, "
              f"{ce['nb_cas_usage']} cas d'usage ; relu : {ce['verification_ok']}/{ce['verification_total']} éléments conformes, "
              f"{ce['lignes_excel_retrouvees']}/{ce['lignes_excel']} lignes de l'Excel retrouvées.")
        p("")
        p("Couverture (lignes de l'Excel retrouvées dans les codes) :")
        p(f"  {'onglet':<26}{'attendues':>10}{'trouvées':>10}")
        for l in res.couverture:
            p(f"  {l.onglet:<26}{l.attendus:>10}{l.trouves:>10}" + ("" if l.ok else "   <-- MANQUE"))
        ok_v = sum(1 for v in res.verification if v["ok"])
        p("")
        p(f"Relecture des codes comparée à l'Excel : {ok_v}/{len(res.verification)} élément(s) conforme(s)")
        for v in res.verification:
            if not v["ok"]:
                p(f"  [ÉCART] {v['categorie']} {v['onglet']} ligne {v['ligne_excel']} : {' ; '.join(v['ecarts'])}")
        p("")
        p("Non traduit :")
        for k, v in NON_TRADUIT_COMPLET.items():
            p(f"  - {v} ({k})")
    if res.avertissements:
        p("")
        p(f"Avertissements ({na}) — à remonter à l'équipe UX :")
        for pb in res.avertissements:
            p("  " + str(pb))
    p("")
    return "\n".join(out) + "\n"
