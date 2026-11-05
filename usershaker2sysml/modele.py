"""
Modèle intermédiaire : ce qui sera écrit en SysML v2, avant d'être écrit.

Construire le modèle d'abord permet de VÉRIFIER que chaque référence existe
(besoin satisfait, type d'acteur, enchaînement d'étapes) et que les noms sont
uniques, avant de produire le moindre texte. Le rendu (rendu.py) ne fait ensuite
que mettre en forme.

Correspondance UserShaker -> SysML v2 (format validé dans CATIA Magic Community) :
    projet (meta.project_name)   -> package
    personas                     -> part : Persona
    components                   -> part def
    user_needs                   -> requirement
    use_cases                    -> use case def
    use_case_personas            -> actor : Persona (dans le use case)
    steps                        -> action (dans le use case), ordre = position
    ordre des étapes             -> first <étape n> then <étape n+1>;
    step_triggers                -> attribute triggerEvent / condition = "<composant> is <état>"
    step_user_needs              -> satisfy <besoin>; (dans l'action)
    id UserShaker de chaque élément -> doc /* id */ (traçabilité)
"""
from collections import defaultdict
from dataclasses import dataclass, field

from .noms import Scope, camel, pascal


def _pos(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return int(float(v))


@dataclass
class Element:
    name: str
    id: str


@dataclass
class Declencheur:
    name: str      # triggerEvent, condition, condition2...
    id: str
    texte: str     # "<composant> is <état>"


@dataclass
class Etape:
    name: str
    id: str
    declencheurs: list = field(default_factory=list)
    besoins: list = field(default_factory=list)   # noms qualifiés "Needs::xxx"
    besoin_ids: list = field(default_factory=list)  # ids UserShaker correspondants


@dataclass
class CasUsage:
    name: str
    id: str
    acteurs: list = field(default_factory=list)   # [(nom, id persona)]
    etapes: list = field(default_factory=list)


@dataclass
class Modele:
    package: str
    projet: str
    personas: list = field(default_factory=list)
    composants: list = field(default_factory=list)
    besoins: list = field(default_factory=list)
    cas_usage: list = field(default_factory=list)
    trace: list = field(default_factory=list)     # (onglet, id, élément SysML)
    lignes: dict = field(default_factory=dict)    # clé de trace -> n° de ligne dans le .sysml (rempli au rendu)


class ErreurModele(Exception):
    """Incohérence interne du modèle (ne doit pas arriver si les contrôles passent)."""


def construire(ds):
    m = ds.meta()
    projet = m.get("project_name") or "UserShakerProject"
    mod = Modele(package=pascal(projet, "UserShakerProject"), projet=projet)
    P = mod.package

    # Personas
    sc = Scope(["Persona"])
    for p in ds.get("personas"):
        nm = sc.uniq(camel(p["name"], "persona"))
        mod.personas.append(Element(nm, p["persona_id"]))
        mod.trace.append(("personas", p["persona_id"], f"{P}::Personas::{nm}"))

    # Composants
    sc = Scope()
    for c in ds.get("components"):
        nm = sc.uniq(pascal(c["name"], "Component"))
        mod.composants.append(Element(nm, c["component_id"]))
        mod.trace.append(("components", c["component_id"], f"{P}::Components::{nm}"))

    # Besoins
    sc = Scope()
    need_ref = {}
    for n in ds.get("user_needs"):
        nm = sc.uniq(camel("need " + str(n["name"]), "need"))
        need_ref[n["user_need_id"]] = f"Needs::{nm}"
        mod.besoins.append(Element(nm, n["user_need_id"]))
        mod.trace.append(("user_needs", n["user_need_id"], f"{P}::Needs::{nm}"))

    comp_name = {c["component_id"]: c["name"] for c in ds.get("components")}
    state_name = {s["state_id"]: s["name"] for s in ds.get("component_states")}
    pname = {p["persona_id"]: p["name"] for p in ds.get("personas")}

    steps_by_uc = defaultdict(list)
    for s in sorted(ds.get("steps"), key=lambda r: (r["use_case_id"], _pos(r["position"]))):
        steps_by_uc[s["use_case_id"]].append(s)
    trig = defaultdict(list)
    for t in sorted(ds.get("step_triggers"), key=lambda r: (r["step_id"], _pos(r["position"]))):
        trig[t["step_id"]].append(t)
    ucp = defaultdict(list)
    for r in sorted(ds.get("use_case_personas"), key=lambda r: _pos(r["position"])):
        if r["persona_id"] not in ucp[r["use_case_id"]]:
            ucp[r["use_case_id"]].append(r["persona_id"])
    nds = defaultdict(list)
    for r in ds.get("step_user_needs"):
        if r["user_need_id"] not in nds[r["step_id"]]:   # un doublon de lien n'est écrit qu'une fois
            nds[r["step_id"]].append(r["user_need_id"])

    # Cas d'usage
    usc = Scope()
    for uc in sorted(ds.get("use_cases"), key=lambda r: _pos(r["position"])):
        un = usc.uniq(pascal(uc["name"], "UseCase"))
        cu = CasUsage(un, uc["use_case_id"])
        mod.trace.append(("use_cases", uc["use_case_id"], f"{P}::UseCases::{un}"))
        asc = Scope()   # acteurs et étapes partagent l'espace de noms du use case
        for pid in ucp.get(uc["use_case_id"], []):
            an = asc.uniq(camel(pname[pid], "persona"))
            cu.acteurs.append((an, pid))
            mod.trace.append(("use_case_personas", f"{uc['use_case_id']}->{pid}",
                              f"{P}::UseCases::{un}::{an}"))
        for s in steps_by_uc.get(uc["use_case_id"], []):
            sn = asc.uniq(camel(f"step{_pos(s['position']):02d} {s['name']}", "step"))
            et = Etape(sn, s["step_id"])
            q = f"{P}::UseCases::{un}::{sn}"
            mod.trace.append(("steps", s["step_id"], q))
            ssc = Scope()
            for t in trig.get(s["step_id"], []):
                tn = ssc.uniq("triggerEvent" if t["kind"] == "trigger" else "condition")
                op = t.get("operator") or "is"
                et.declencheurs.append(Declencheur(
                    tn, t["trigger_id"], f"{comp_name[t['component_id']]} {op} {state_name[t['state_id']]}"))
                mod.trace.append(("step_triggers", t["trigger_id"], f"{q}::{tn}"))
            for nid in nds.get(s["step_id"], []):
                et.besoins.append(need_ref[nid])
                et.besoin_ids.append(nid)
                mod.trace.append(("step_user_needs", f"{s['step_id']}->{nid}", f"{q} satisfy {need_ref[nid]}"))
            cu.etapes.append(et)
        mod.cas_usage.append(cu)

    verifier(mod)
    return mod


def verifier(mod):
    """Chaque référence pointe vers un élément déclaré, chaque nom est unique dans son espace."""
    errs = []

    def uniques(noms, ou):
        vus = set()
        for n in noms:
            if not n:
                errs.append(f"nom vide dans {ou}")
            if n in vus:
                errs.append(f"nom « {n} » en double dans {ou}")
            vus.add(n)

    uniques([e.name for e in mod.personas] + ["Persona"], "Personas")
    uniques([e.name for e in mod.composants], "Components")
    uniques([e.name for e in mod.besoins], "Needs")
    uniques([c.name for c in mod.cas_usage], "UseCases")
    besoins = {f"Needs::{e.name}" for e in mod.besoins}
    personas = {e.id for e in mod.personas}
    for cu in mod.cas_usage:
        uniques([a for a, _ in cu.acteurs] + [e.name for e in cu.etapes], f"UseCases::{cu.name}")
        for _, pid in cu.acteurs:
            if pid not in personas:
                errs.append(f"acteur de {cu.name} : persona {pid} inconnu")
        for e in cu.etapes:
            uniques([d.name for d in e.declencheurs], f"{cu.name}::{e.name}")
            for b in e.besoins:
                if b not in besoins:
                    errs.append(f"{cu.name}::{e.name} satisfait {b}, qui n'existe pas")
    if errs:
        raise ErreurModele("; ".join(errs))
