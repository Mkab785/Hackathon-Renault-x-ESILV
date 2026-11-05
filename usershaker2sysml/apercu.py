"""
Données lisibles pour l'interface : ce que contient le modèle, avec les noms
d'origine UserShaker (et le nom SysML correspondant), plus la matrice
besoins × étapes. N'est appelé que si la traduction a réussi (données valides).
"""
from collections import defaultdict

from .modele import _pos


def apercu(ds, res):
    sysml = {}
    for onglet, id_, elem in res.trace:
        sysml.setdefault(id_, elem.split("::")[-1].split(" ")[0])

    pname = {p["persona_id"]: p["name"] for p in ds.get("personas")}
    cname = {c["component_id"]: c["name"] for c in ds.get("components")}
    sname = {s["state_id"]: s["name"] for s in ds.get("component_states")}

    trig = defaultdict(list)
    for t in sorted(ds.get("step_triggers"), key=lambda r: (r["step_id"], _pos(r["position"]))):
        trig[t["step_id"]].append({
            "type": "déclencheur" if t["kind"] == "trigger" else "condition",
            "texte": f"{cname.get(t['component_id'], '?')} {t.get('operator') or 'is'} "
                     f"{sname.get(t['state_id'], '?')}",
        })
    nds = defaultdict(list)
    for r in ds.get("step_user_needs"):
        if r["user_need_id"] not in nds[r["step_id"]]:
            nds[r["step_id"]].append(r["user_need_id"])
    ucp = defaultdict(list)
    for r in sorted(ds.get("use_case_personas"), key=lambda r: _pos(r["position"])):
        if r["persona_id"] not in ucp[r["use_case_id"]]:
            ucp[r["use_case_id"]].append(r["persona_id"])
    steps = defaultdict(list)
    for s in sorted(ds.get("steps"), key=lambda r: _pos(r["position"])):
        steps[s["use_case_id"]].append(s)

    cas = []
    for uc in sorted(ds.get("use_cases"), key=lambda r: _pos(r["position"])):
        cas.append({
            "id": uc["use_case_id"],
            "nom": uc["name"],
            "sysml": sysml.get(uc["use_case_id"], ""),
            "acteurs": [pname.get(p, p) for p in ucp.get(uc["use_case_id"], [])],
            "etapes": [{
                "id": s["step_id"],
                "position": _pos(s["position"]),
                "nom": s["name"],
                "sysml": sysml.get(s["step_id"], ""),
                "declencheurs": trig.get(s["step_id"], []),
                "besoins": nds.get(s["step_id"], []),
            } for s in steps.get(uc["use_case_id"], [])],
        })

    servi = defaultdict(int)
    for lst in nds.values():
        for n in lst:
            servi[n] += 1
    besoins = [{
        "id": n["user_need_id"],
        "nom": n["name"],
        "sysml": sysml.get(n["user_need_id"], ""),
        "nb_etapes": servi.get(n["user_need_id"], 0),
    } for n in ds.get("user_needs")]

    return {
        "projet": ds.meta().get("project_name") or "",
        "export": ds.meta().get("exported_at") or "",
        "cas_usage": cas,
        "besoins": besoins,
        "compteurs": {
            "cas d'usage": len(ds.get("use_cases")),
            "étapes": len(ds.get("steps")),
            "personas": len(ds.get("personas")),
            "composants": len(ds.get("components")),
            "besoins": len(ds.get("user_needs")),
            "liens besoin–étape": sum(len(v) for v in nds.values()),
        },
    }
