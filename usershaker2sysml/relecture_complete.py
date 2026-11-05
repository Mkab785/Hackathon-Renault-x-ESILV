"""
Relecture des codes de la traduction complète (un code par cas d'usage, écriture compacte),
SANS utiliser le traducteur : chaque code est relu ligne à ligne, puis comparé à l'Excel
élément par élément. Le résultat a la même forme que la vérification de l'ancienne
traduction (une ligne par persona, composant, besoin, cas d'usage et étape, avec des
critères Excel / SysML), plus le code et la ligne où se trouve l'élément.

Les textes de l'Excel sont comparés espaces normalisés (le traducteur écrit chaque texte
sur une seule ligne). Les liens des images (steps.image_url) ne sont pas traduits.
"""
import re
from collections import defaultdict

from .verification import _crit, _meme_nom, _unescape

_STR = r'"((?:[^"\\]|\\.)*)"'
RE_ATTR = re.compile(r"^attribute (\w+) = " + _STR + r"(?:;| \{ doc /\* (\S+) \*/ \})$")
RE_DOC = re.compile(r"^doc /\* (\S+)(?: : (.*?))? \*/$")
RE_REQ1 = re.compile(r"^requirement (\w+) \{ doc /\* (\S+)(?: : (.*?))? \*/ \}$")


def _txt(v):
    if v is None:
        return None
    s = " ".join(str(v).split())
    return s or None


def _rang(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 10 ** 6


# ---------------------------------------------------------------- relecture d'un code
def relire_code(texte):
    """Analyse un code. Renvoie un dict :
    package, ligne_package, entete (doc du package), personas / composants / besoins
    {id: {nom, nom_doc, ligne, attrs, lignes}}, cas (ou None) :
    {nom, id, nom_doc, ligne, attrs, lignes, acteurs [(nom, ligne)], actions {nom: action},
     ordre [(a, b, ligne)]}, action : {nom, id, nom_doc, ligne, attrs, lignes,
     declencheurs [(attribut, texte, id, ligne)], satisfy [(besoin, ligne)]}."""
    c = {"package": None, "ligne_package": None, "entete": "", "personas": {}, "composants": {},
         "besoins": {}, "cas": None}
    section = None
    elem = None          # persona / composant / besoin en cours
    cas = act = None
    attente = None       # élément qui attend sa ligne doc

    def ouvrir(e, n, nom):
        e.update({"nom": nom, "ligne": n, "id": None, "nom_doc": None, "attrs": {}, "lignes": {}})
        return e

    for n, brut in enumerate(texte.splitlines(), start=1):
        l = brut.strip()
        if not l:
            continue
        if attente is not None:
            g = RE_DOC.match(l)
            if g:
                attente["id"], attente["nom_doc"] = g.group(1), g.group(2)
                cible = attente.get("_dans")
                if cible is not None:
                    cible[g.group(1)] = attente
                attente = None
                continue
            attente = None
        g = re.match(r"^package (\w+) \{$", l)
        if g:
            if c["package"] is None:
                c["package"], c["ligne_package"] = g.group(1), n
            else:
                section = g.group(1)
            continue
        if c["package"] is not None and not c["entete"] and n == c["ligne_package"] + 1:
            g = re.match(r"^doc /\* (.*) \*/$", l)
            if g:
                c["entete"] = g.group(1)
                continue
        if section == "Personas" and cas is None:
            g = re.match(r"^part (\w+) : Persona \{$", l)
            if g:
                elem = ouvrir({"_dans": c["personas"]}, n, g.group(1))
                attente = elem
                continue
        if section == "Components" and cas is None:
            g = re.match(r"^part def (\w+) \{$", l)
            if g:
                elem = ouvrir({"_dans": c["composants"]}, n, g.group(1))
                attente = elem
                continue
        if section == "Needs" and cas is None:
            g = RE_REQ1.match(l)
            if g:
                e = ouvrir({}, n, g.group(1))
                e["id"], e["nom_doc"], e["minimal"] = g.group(2), g.group(3), True
                c["besoins"][g.group(2)] = e
                continue
            g = re.match(r"^requirement (\w+) \{$", l)
            if g:
                elem = ouvrir({"_dans": c["besoins"]}, n, g.group(1))
                attente = elem
                continue
        g = re.match(r"^use case def (\w+) \{$", l)
        if g:
            section = None
            cas = ouvrir({}, n, g.group(1))
            cas.update({"acteurs": [], "actions": {}, "ordre": []})
            c["cas"] = cas
            attente = cas
            continue
        if cas is not None:
            g = re.match(r"^actor (\w+) : Personas::Persona;$", l)
            if g and act is None:
                cas["acteurs"].append((g.group(1), n))
                continue
            g = re.match(r"^action (\w+) \{$", l)
            if g and act is None:
                act = ouvrir({}, n, g.group(1))
                act.update({"declencheurs": [], "satisfy": []})
                cas["actions"][g.group(1)] = act
                attente = act
                continue
            g = re.match(r"^first (\w+) then (\w+);$", l)
            if g and act is None:
                cas["ordre"].append((g.group(1), g.group(2), n))
                continue
            g = re.match(r"^satisfy Needs::(\w+);$", l)
            if g and act is not None:
                act["satisfy"].append((g.group(1), n))
                continue
        g = RE_ATTR.match(l)
        if g:
            nom, val, doc = g.group(1), _unescape(g.group(2)), g.group(3)
            cible = act if act is not None else (cas if cas is not None else elem)
            if cible is None:
                continue
            if cible is act and doc and re.match(r"^(triggerEvent|condition)\d*$", nom):
                act["declencheurs"].append((nom, val, doc, n))
            else:
                cible["attrs"][nom] = val
                cible["lignes"][nom] = n
            continue
        if l == "}":
            if act is not None:
                act = None
            elif cas is not None:
                cas = None
            elif elem is not None:
                elem = None
            else:
                section = None
            continue
    for dico in (c["personas"], c["composants"], c["besoins"]):
        for e in dico.values():
            e.pop("_dans", None)
    return c


def _items(valeur, sep=r" ; "):
    return [x for x in re.split(sep, valeur or "") if x] if valeur else []


# ---------------------------------------------------------------- comparaison à l'Excel
def verifier_complet(ds, codes):
    """codes : [(fichier, texte)] dans l'ordre. Renvoie (verification, trace) :
    verification : une ligne par persona, composant, besoin, cas d'usage, étape ;
    trace : une ligne par donnée de l'Excel (où elle est dans quel code, à quelle ligne)."""
    rn = ds.row_number
    lus = [(f, relire_code(t)) for f, t in codes]
    out, trace = [], []

    # index des occurrences
    occ = {"personas": defaultdict(list), "composants": defaultdict(list), "besoins": defaultdict(list)}
    for k, (f, c) in enumerate(lus):
        for cle in occ:
            for i, e in c[cle].items():
                occ[cle][i].append((k, e))
    parts_uc = defaultdict(list)            # id du cas d'usage -> [(k, cas)] dans l'ordre des parties
    for k, (f, c) in enumerate(lus):
        if c["cas"] and c["cas"]["id"]:
            m = re.search(r"partie (\d+)/(\d+)", c["entete"] or "")
            parts_uc[c["cas"]["id"]].append((int(m.group(1)) if m else 1, k, c["cas"]))
    for uid in parts_uc:
        parts_uc[uid] = [(k, cas) for _, k, cas in sorted(parts_uc[uid])]
    action_de = {}                          # id d'étape -> (k, cas, action)
    for uid, parts in parts_uc.items():
        for k, cas in parts:
            for a in cas["actions"].values():
                if a["id"]:
                    action_de.setdefault(a["id"], (k, cas, a))

    def fichier(k):
        return lus[k][0]

    # identifiants SysML -> ids Excel, par cas d'usage (toutes ses parties)
    def table(uid, cle):
        t = {}
        for k, _ in parts_uc.get(uid, []):
            for i, e in lus[k][1][cle].items():
                t[e["nom"]] = i
        return t

    def ligne(cat, onglet, idx, id_, nom_excel, nom_sysml, k, lsys, criteres, excel, sysml, parent=""):
        ecarts = [c["ecart"] for c in criteres if not c["ok"]]
        out.append({"categorie": cat, "onglet": onglet, "ligne_excel": rn(onglet, idx) if idx is not None else None,
                    "id": id_, "parent": parent, "nom_excel": nom_excel, "nom_sysml": nom_sysml,
                    "code": k, "fichier": fichier(k) if k is not None else "", "ligne_sysml": lsys,
                    "criteres": criteres, "ok": not ecarts, "ecarts": ecarts, "excel": excel, "sysml": sysml})

    def tr(onglet, idx, id_, dans_excel, type_sysml, k, element, lsys):
        trace.append({"onglet_excel": onglet, "ligne_excel": rn(onglet, idx) if idx is not None else None,
                      "id": id_, "dans_excel": dans_excel, "type_sysml": type_sysml,
                      "code": k, "fichier": fichier(k) if k is not None else "", "element_sysml": element,
                      "ligne_sysml": lsys})

    def infos(ex, sy):
        return [f"{a} : {v}" for a, v in ex.items() if v is not None], [f"{a} : {v}" for a, v in sy.items() if v is not None]

    def nom_ok(excel, e, prefixe=""):
        nd = e["nom_doc"]
        brut = e["nom"][len(prefixe):] if prefixe and e["nom"].startswith(prefixe) else e["nom"]
        return nd == _txt(excel) and _meme_nom(excel, brut)

    # ---- personas, composants, besoins
    nom_comp = {c["component_id"]: c["name"] for c in ds.get("components")}
    idx_etat = {st["state_id"]: i for i, st in enumerate(ds.get("component_states"))}
    etats = defaultdict(list)
    for st in sorted(ds.get("component_states"), key=lambda r: _rang(r.get("position"))):
        etats[st["component_id"]].append(st)
    for cat, onglet, pk, cle, prefixe, champs, type_sysml in (
            ("Persona", "personas", "persona_id", "personas", "",
             (("ageCategory", "age_category"), ("gender", "gender"), ("biography", "biography")), "part (persona)"),
            ("Composant", "components", "component_id", "composants", "",
             (("role", "role"), ("category", "category"), ("description", "description")), "part def (composant)"),
            ("Besoin", "user_needs", "user_need_id", "besoins", "need",
             (("description", "description"), ("referenceUrl", "reference_url"), ("libraryName", "library_name")),
             "requirement (besoin)")):
        for i, r in enumerate(ds.get(onglet)):
            liste = occ[cle].get(r[pk], [])
            if not liste:
                ligne(cat, onglet, i, r[pk], r.get("name"), "", None, None,
                      [_crit("Présence", r[pk], "—", False, "absent des codes")], r.get("name"), "—")
                tr(onglet, i, r[pk], r.get("name"), type_sysml, None, "—", None)
                continue
            # toutes les copies (un élément peut être écrit dans plusieurs codes) sont relues ;
            # une copie « minimale » (besoin répété dans une partie 2) n'a que l'id et le nom
            completes = [(kk, x) for kk, x in liste if not x.get("minimal")] or liste
            k, e = completes[0]
            ec_nom = [f"{fichier(kk)} : {x['nom']} ({x['nom_doc']})" for kk, x in liste
                      if not nom_ok(r.get("name"), x, prefixe)]
            crits = [_crit("Nom", r.get("name"), f"{e['nom']} ({e['nom_doc']})", not ec_nom,
                           f"nom différent de « {r.get('name')} » : " + " ; ".join(ec_nom))]
            ex = {a: _txt(r.get(col)) for a, col in champs}
            if cat == "Composant" and r.get("parent_component_id"):
                ex["parent"] = _txt(nom_comp.get(r["parent_component_id"], r["parent_component_id"]))

            def lu_infos(kk, x):
                sy = {a: x["attrs"].get(a) for a in ex}
                if sy.get("parent"):
                    par = next((y for y in lus[kk][1]["composants"].values() if y["nom"] == sy["parent"]), None)
                    sy["parent"] = par["nom_doc"] if par else sy["parent"]
                return sy
            diff = [(kk, lu_infos(kk, x)) for kk, x in completes if lu_infos(kk, x) != ex]
            a_ex, a_sy = infos(ex, diff[0][1] if diff else lu_infos(k, e))
            crits.append(_crit("Infos", a_ex, a_sy, not diff,
                               "infos différentes de l'Excel dans " + ", ".join(fichier(kk) for kk, _ in diff)))
            if cat == "Composant":
                attendu = [f"{_txt(st['name'])} [{st['state_id']}]" + (f" ({_txt(st['description'])})"
                           if _txt(st.get("description")) else "") for st in etats.get(r[pk], [])]
                diff_e = [(kk, _items(x["attrs"].get("states"), r"(?<=[\])]) ; ")) for kk, x in completes]
                diff_e = [(kk, lu) for kk, lu in diff_e if lu != attendu]
                lu = diff_e[0][1] if diff_e else attendu
                ec = []
                if diff_e:
                    manque = [x for x in attendu if x not in lu]
                    trop = [x for x in lu if x not in attendu]
                    if manque:
                        ec.append("état(s) absent(s) : " + " ; ".join(manque))
                    if trop:
                        ec.append("état(s) en trop : " + " ; ".join(trop))
                    if not manque and not trop:
                        ec.append("ordre des états différent de l'Excel (colonne position)")
                    ec.append("dans " + ", ".join(fichier(kk) for kk, _ in diff_e))
                crits.append(_crit("États", attendu, lu, not diff_e, " ; ".join(ec)))
                lst = e["lignes"].get("states")
                for st in etats.get(r[pk], []):
                    trouve = st["state_id"] in (e["attrs"].get("states") or "")
                    tr("component_states", idx_etat.get(st["state_id"]), st["state_id"],
                       f"état « {st['name']} » de « {r.get('name')} »", "attribute states (état)",
                       k if trouve else None, f"Components::{e['nom']} · states" if trouve else "—",
                       lst if trouve else None)
            ligne(cat, onglet, i, r[pk], r.get("name"), e["nom"], k, e["ligne"], crits,
                  r.get("name"), f"{e['nom']} — {fichier(k)}" + (f" (+{len(liste) - 1} autre(s) code(s))" if len(liste) > 1 else ""))
            tr(onglet, i, r[pk], r.get("name"), type_sysml, k,
               {"personas": "Personas::", "composants": "Components::", "besoins": "Needs::"}[cle] + e["nom"], e["ligne"])

    # ---- cas d'usage et étapes
    pnom = {p["persona_id"]: p["name"] for p in ds.get("personas")}
    etat_nom = {x["state_id"]: x["name"] for x in ds.get("component_states")}
    besoin_nom = {b["user_need_id"]: b["name"] for b in ds.get("user_needs")}
    groupe = {g["group_id"]: g for g in ds.get("step_groups")}
    idx_onglet = {}
    for onglet, pk in (("step_groups", "group_id"), ("persona_step_feedback", "feedback_id"),
                       ("step_triggers", "trigger_id")):
        for i, r in enumerate(ds.get(onglet)):
            idx_onglet.setdefault((onglet, r[pk]), i)
    ucp, ucc = defaultdict(list), defaultdict(list)
    ucp_i, ucc_i = {}, {}
    for i, r in enumerate(ds.get("use_case_personas")):
        if r["persona_id"] not in ucp[r["use_case_id"]]:
            ucp[r["use_case_id"]].append(r["persona_id"])
            ucp_i[(r["use_case_id"], r["persona_id"])] = i
    for i, r in enumerate(ds.get("use_case_components")):
        if r["component_id"] not in ucc[r["use_case_id"]]:
            ucc[r["use_case_id"]].append(r["component_id"])
            ucc_i[(r["use_case_id"], r["component_id"])] = i
    etapes = defaultdict(list)
    for i, r in enumerate(ds.get("steps")):
        etapes[r["use_case_id"]].append((i, r))
    trig = defaultdict(list)
    for r in ds.get("step_triggers"):
        trig[r["step_id"]].append(r)
    nds, nds_i = defaultdict(list), {}
    for i, r in enumerate(ds.get("step_user_needs")):
        if r["user_need_id"] not in nds[r["step_id"]]:
            nds[r["step_id"]].append(r["user_need_id"])
            nds_i[(r["step_id"], r["user_need_id"])] = i
    grille = defaultdict(list)
    for i, r in enumerate(ds.get("step_component_states")):
        grille[r["step_id"]].append((i, r))
    fb = defaultdict(list)
    for i, r in enumerate(ds.get("persona_step_feedback")):
        fb[r["step_id"]].append((i, r))
    inutil = defaultdict(list)
    for i, r in enumerate(ds.get("step_unused_components")):
        inutil[r["step_id"]].append((i, r))

    def score(f):
        if f.get("is_present") in (False, "false", "False", 0):
            return "absent"
        if f.get("emotion_score") is None:
            return "?"
        try:
            return f"{int(float(f['emotion_score'])):+d}"
        except (TypeError, ValueError):
            return str(f["emotion_score"])

    for i, u in enumerate(ds.get("use_cases")):
        uid = u["use_case_id"]
        parts = parts_uc.get(uid, [])
        etp = sorted(etapes.get(uid, []), key=lambda t: _rang(t[1]["position"]))
        n_ex = len(etp)
        if not parts:
            ligne("Cas d'usage", "use_cases", i, uid, u.get("name"), "", None, None,
                  [_crit("Présence", uid, "—", False, "absent des codes")], u.get("name"), "—")
            tr("use_cases", i, uid, u.get("name"), "use case def", None, "—", None)
            for j, r in etp:
                ligne("Étape", "steps", j, r["step_id"], r.get("name"), "", None, None,
                      [_crit("Présence", r["step_id"], "—", False, "cas d'usage absent des codes")],
                      f"{r.get('position')}. {r.get('name')}", "—", uid)
            continue
        k0, cas0 = parts[0]
        t_pers, t_comp = table(uid, "personas"), table(uid, "composants")
        id_pers = {v: kk for kk, v in t_pers.items()}
        id_comp = {v: kk for kk, v in t_comp.items()}

        # enchaînement sur toutes les parties
        suiv, cibles, ec_ch = {}, set(), []
        noms_actions = []
        for p_, (k, cas) in enumerate(parts):
            avant = bool(noms_actions)              # une étape existe déjà dans une partie précédente
            noms_actions += list(cas["actions"])
            for a, b, _ in cas["ordre"]:
                if a in suiv:
                    ec_ch.append(f"« {a} » a deux étapes suivantes")
                suiv[a] = b
                cibles.add(b)
            if p_ > 0 and avant:
                m = re.search(r"suite de (\w+) \(partie (\d+)\)", lus[k][1]["entete"] or "")
                premier = next(iter(cas["actions"]), None)
                if m and premier:
                    suiv[m.group(1)] = premier
                    cibles.add(premier)
                elif premier:
                    ec_ch.append(f"partie {p_ + 1} : lien avec la partie précédente absent")
        ordre = []
        debuts = [x for x in noms_actions if x not in cibles]
        if len(debuts) == 1:
            cur, vus = debuts[0], set()
            while cur is not None and cur not in vus:
                vus.add(cur)
                ordre.append(cur)
                cur = suiv.get(cur)
            if len(ordre) != len(noms_actions):
                ec_ch.append(f"{len(noms_actions) - len(ordre)} étape(s) hors de l'enchaînement")
        elif noms_actions:
            ec_ch.append(f"{len(debuts)} début(s) d'enchaînement au lieu de 1")

        crits = [_crit("Nom", u.get("name"), f"{cas0['nom']} ({cas0['nom_doc']})", nom_ok(u.get("name"), cas0),
                       f"nom différent : « {u.get('name')} » / {cas0['nom']}")]
        ex_act = [pnom.get(p, p) for p in ucp.get(uid, [])]
        lus_act = [a for a, _ in cas0["acteurs"]]
        crits.append(_crit("Acteurs", ex_act, lus_act,
                           sorted(ucp.get(uid, [])) == sorted(str(t_pers.get(a)) for a in lus_act)
                           and all(sorted(a for a, _ in cas["acteurs"]) == sorted(lus_act) for _, cas in parts),
                           "acteurs différents des personas du cas d'usage"))
        n_sy = sum(len(cas["actions"]) for _, cas in parts)
        crits.append(_crit("Nombre d'étapes", n_ex, n_sy, n_sy == n_ex, f"{n_sy} action(s) pour {n_ex} étape(s)"))
        crits.append(_crit("Enchaînement", f"positions 1 à {n_ex}",
                           f"{len(ordre)} action(s) reliées" + (f" sur {len(parts)} codes" if len(parts) > 1 else ""),
                           not ec_ch, "enchaînement : " + " ; ".join(ec_ch)))
        ex_t = {a: _txt(u.get(a)) for a in ("description", "story", "status", "folder")}
        sy_t = {a: cas0["attrs"].get(a) for a in ex_t}
        a_ex, a_sy = infos(ex_t, sy_t)
        crits.append(_crit("Textes", a_ex, a_sy, ex_t == sy_t, "textes différents de l'Excel"))
        # groupes d'étapes
        ex_g = {}
        for _, r in etp:
            g = groupe.get(r.get("group_id"))
            if g:
                ex_g.setdefault((_txt(g["name"]), g["group_id"]), []).append(_rang(r["position"]))
        sy_g = {}
        for k, cas in parts:
            for item in _items(cas["attrs"].get("stepGroups")):
                m = re.match(r"^(.*) \[(\S+)\]: ([\d, -]+)$", item)
                if not m:
                    sy_g.setdefault(("?", item), [])
                    continue
                for plage in m.group(3).split(", "):
                    a, _, b = plage.partition("-")
                    sy_g.setdefault((m.group(1), m.group(2)), []).extend(range(int(a), int(b or a) + 1))
        ex_gs = {k_: sorted(v) for k_, v in ex_g.items()}
        sy_gs = {k_: sorted(v) for k_, v in sy_g.items()}
        crits.append(_crit("Groupes", [f"{n} : étapes {', '.join(map(str, v))}" for (n, _), v in ex_gs.items()],
                           [f"{n} : étapes {', '.join(map(str, v))}" for (n, _), v in sy_gs.items()],
                           ex_gs == sy_gs, "groupes d'étapes différents de l'Excel"))
        ex_c = [nom_comp.get(c_, c_) for c_ in ucc.get(uid, [])]
        manq = [nom_comp.get(c_, c_) for c_ in ucc.get(uid, []) if c_ not in id_comp]
        crits.append(_crit("Composants", ex_c, sorted(t_comp), not manq,
                           "composant(s) du cas d'usage absent(s) du code : " + " ; ".join(manq)))
        ligne("Cas d'usage", "use_cases", i, uid, u.get("name"), cas0["nom"], k0, cas0["ligne"], crits,
              f"{u.get('name')} — acteurs : {', '.join(map(str, ex_act))} — {n_ex} étape(s)",
              f"{cas0['nom']} — {len(parts)} code(s) : {', '.join(fichier(k) for k, _ in parts)}")
        tr("use_cases", i, uid, u.get("name"), "use case def", k0, cas0["nom"], cas0["ligne"])
        for pid in ucp.get(uid, []):
            nom_a = id_pers.get(pid)
            la = next((n for a, n in cas0["acteurs"] if a == nom_a), None)
            tr("use_case_personas", ucp_i.get((uid, pid)), f"{uid}->{pid}",
               f"{pnom.get(pid)} participe à « {u.get('name')} »", "actor", k0 if la else None,
               f"{cas0['nom']}::{nom_a}" if la else "—", la)
        for cid in ucc.get(uid, []):
            e = next((lus[k][1]["composants"][cid] for k, _ in parts if cid in lus[k][1]["composants"]), None)
            kk = next((k for k, _ in parts if cid in lus[k][1]["composants"]), None)
            tr("use_case_components", ucc_i.get((uid, cid)), f"{uid}->{cid}",
               f"« {nom_comp.get(cid)} » est un composant de « {u.get('name')} »", "part def (composant du code)",
               kk, f"Components::{e['nom']}" if e else "—", e["ligne"] if e else None)
        for (gn, gid), pos in ex_gs.items():
            kk = next((k for k, cas in parts if gid in (cas["attrs"].get("stepGroups") or "")), None)
            cas_g = next((cas for k, cas in parts if k == kk), None)
            tr("step_groups", idx_onglet.get(("step_groups", gid)), gid, f"groupe « {gn} » (étapes {', '.join(map(str, pos))})",
               "attribute stepGroups", kk, f"{cas0['nom']} · stepGroups" if kk is not None else "—",
               cas_g["lignes"].get("stepGroups") if cas_g else None)

        rang_excel = {r["step_id"]: n + 1 for n, (_, r) in enumerate(etp)}
        for j, r in etp:
            sid = r["step_id"]
            pos = _rang(r["position"])
            ex_trig = sorted(trig.get(sid, []), key=lambda t: _rang(t["position"]))
            ex_txt = [f"{'Quand' if t['kind'] == 'trigger' else 'Et si'} {nom_comp.get(t['component_id'])} "
                      f"{t.get('operator') or 'is'} {etat_nom.get(t['state_id'])}" for t in ex_trig]
            ex_b = sorted(str(besoin_nom.get(x, x)) for x in nds.get(sid, ()))
            excel = (f"{r.get('position')}. {r.get('name')}" + (" | " + " ; ".join(ex_txt) if ex_txt else "")
                     + (" | sert : " + " ; ".join(ex_b) if ex_b else ""))
            trouve = action_de.get(sid)
            if trouve is None or trouve[1]["id"] != uid:
                ligne("Étape", "steps", j, sid, r.get("name"), "", None, None,
                      [_crit("Présence", sid, "—", False,
                             "rangée dans un autre cas d'usage" if trouve else "absente des codes")], excel, "—", uid)
                tr("steps", j, sid, f"étape {r.get('position')} : {r.get('name')}", "action (étape)", None, "—", None)
                continue
            k, cas, a = trouve
            crits = [_crit("Nom", r.get("name"), f"{a['nom']} ({a['nom_doc']})",
                           a["nom_doc"] == _txt(r.get("name")) and _meme_nom(r.get("name"), re.sub(r"^step\d+", "", a["nom"])),
                           f"nom différent : « {r.get('name')} » / {a['nom']}")]
            rang = ordre.index(a["nom"]) + 1 if a["nom"] in ordre else None
            crits.append(_crit("Rang", rang_excel[sid], rang if rang is not None else "?", rang == rang_excel[sid],
                               f"rang {rang if rang is not None else '?'} dans l'enchaînement SysML, "
                               f"{rang_excel[sid]} dans l'Excel"))
            lus_t = a["declencheurs"]
            sy_txt = [f"{'Quand' if an.startswith('triggerEvent') else 'Et si'} {txt}" for an, txt, _, _ in lus_t]
            ec_t = []
            if len(lus_t) != len(ex_trig):
                ec_t.append(f"{len(lus_t)} déclencheur(s) dans le SysML, {len(ex_trig)} dans l'Excel")
            for t, (an, txt, aid, _) in zip(ex_trig, lus_t):
                attendu = f"{nom_comp.get(t['component_id'])} {t.get('operator') or 'is'} {etat_nom.get(t['state_id'])}"
                if aid != t["trigger_id"]:
                    ec_t.append(f"déclencheur {t['position']} : id {aid} au lieu de {t['trigger_id']}")
                if txt != attendu:
                    ec_t.append(f"déclencheur {t['position']} : « {txt} » au lieu de « {attendu} »")
                if (t["kind"] == "trigger") != an.startswith("triggerEvent"):
                    ec_t.append(f"déclencheur {t['position']} : {an} alors que l'Excel dit « {t['kind']} »")
            crits.append(_crit("Déclencheurs", ex_txt, sy_txt, not ec_t, " ; ".join(ec_t)))
            t_bes = {e["nom"]: i_ for i_, e in lus[k][1]["besoins"].items()}
            sat = [t_bes.get(b) for b, _ in a["satisfy"]]
            ec_b = []
            if sorted(map(str, sat)) != sorted(nds.get(sid, [])):
                manq = sorted(str(besoin_nom.get(x, x)) for x in set(nds.get(sid, [])) - set(sat))
                trop = [b for b, _ in a["satisfy"] if t_bes.get(b) not in nds.get(sid, [])]
                if manq:
                    ec_b.append("besoin(s) non satisfait(s) dans le SysML : " + " ; ".join(manq))
                if trop:
                    ec_b.append("satisfy en trop : " + " ; ".join(trop))
            crits.append(_crit("Besoins servis", ex_b, sorted(b for b, _ in a["satisfy"]), not ec_b, " ; ".join(ec_b)))
            g = groupe.get(r.get("group_id"))
            ex_gr = f"{_txt(g['name'])} [{g['group_id']}]" if g else "aucun"
            sy_gr = next((f"{n} [{gid}]" for (n, gid), v in sy_gs.items() if pos in v), "aucun")
            crits.append(_crit("Groupe", ex_gr, sy_gr, ex_gr == sy_gr, f"groupe « {sy_gr} » au lieu de « {ex_gr} »"))
            ex_tx = {"description": _txt(r.get("description")), "triggerText": _txt(r.get("trigger_text")),
                     "note": _txt(r.get("note"))}
            sy_tx = {x: a["attrs"].get(x) for x in ex_tx}
            a_ex, a_sy = infos(ex_tx, sy_tx)
            crits.append(_crit("Textes", a_ex, a_sy, ex_tx == sy_tx, "textes différents de l'Excel"))
            # grille : états des composants à cette étape (attributs grid… du cas d'usage)
            ex_gr_ = defaultdict(list)
            for _, gr in sorted(grille.get(sid, []), key=lambda t: _rang(t[1].get("sequence") or 1)):
                ex_gr_[gr["component_id"]].append(_txt(etat_nom.get(gr["state_id"])) or "?")
            sy_gr_, lgn_gr = {}, {}
            for nom_attr, val in cas["attrs"].items():
                if not nom_attr.startswith("grid"):
                    continue
                cid = t_comp.get(nom_attr[4:])
                for item in _items(val, r" ; (?=\d+: )"):
                    p_, _, etats_ = item.partition(": ")
                    if _rang(p_) == pos:
                        sy_gr_[cid or nom_attr] = etats_.split(" > ")
                        lgn_gr[cid] = cas["lignes"][nom_attr]
            ex_aff = [f"{nom_comp.get(c_, c_)} : {' > '.join(v)}" for c_, v in ex_gr_.items()]
            sy_aff = [f"{nom_comp.get(c_, c_)} : {' > '.join(v)}" for c_, v in sy_gr_.items()]
            crits.append(_crit("Grille", ex_aff, sy_aff, dict(ex_gr_) == sy_gr_,
                               "états des composants différents : " + " ; ".join(
                                   sorted(set(ex_aff) ^ set(sy_aff)))))
            for i_g, gr in grille.get(sid, []):
                l_ = lgn_gr.get(gr["component_id"])
                tr("step_component_states", i_g, f"{sid}->{gr['component_id']}",
                   f"étape {r.get('position')} « {r.get('name')} » : {nom_comp.get(gr['component_id'])} = "
                   f"{etat_nom.get(gr['state_id'])}", "attribute grid… (grille)", k if l_ else None,
                   f"{cas['nom']} · grid{id_comp.get(gr['component_id'], '?')}" if l_ else "—", l_)
            # ressentis
            ex_f = sorted(f"{id_pers.get(f['persona_id'], '?')} {score(f)} | {_txt(f.get('action')) or ''} | "
                          f"{_txt(f.get('insight')) or ''} [{f['feedback_id']}]" for _, f in fb.get(sid, []))
            sy_f = sorted(_items(a["attrs"].get("feedback"), r"(?<=\]) ; "))
            crits.append(_crit("Ressentis", ex_f, sy_f, ex_f == sy_f, "ressentis différents : " + " ; ".join(
                sorted(set(ex_f) ^ set(sy_f)))))
            l_fb = a["lignes"].get("feedback")
            for i_f, f in fb.get(sid, []):
                ok_f = f["feedback_id"] in (a["attrs"].get("feedback") or "")
                tr("persona_step_feedback", i_f, f["feedback_id"],
                   f"{pnom.get(f['persona_id'])} à l'étape « {r.get('name')} » : {score(f)}", "attribute feedback (ressenti)",
                   k if ok_f else None, f"{cas['nom']}::{a['nom']} · feedback" if ok_f else "—", l_fb if ok_f else None)
            ex_u = sorted(id_comp.get(x["component_id"], "?") for _, x in inutil.get(sid, []))
            sy_u = sorted(_items(a["attrs"].get("unusedComponents")))
            if ex_u or sy_u:
                crits.append(_crit("Non utilisés", ex_u, sy_u, ex_u == sy_u, "composants non utilisés différents"))
                for i_u, x in inutil.get(sid, []):
                    tr("step_unused_components", i_u, f"{sid}->{x['component_id']}",
                       f"« {nom_comp.get(x['component_id'])} » non utilisé à l'étape « {r.get('name')} »",
                       "attribute unusedComponents", k, f"{cas['nom']}::{a['nom']} · unusedComponents",
                       a["lignes"].get("unusedComponents"))
            sysml = (f"{a['nom']} (rang {rang if rang is not None else '?'}) — {fichier(k)}"
                     + (" | " + " ; ".join(f"{an} = {txt}" for an, txt, _, _ in lus_t) if lus_t else "")
                     + (" | satisfy " + " ; ".join(b for b, _ in a["satisfy"]) if a["satisfy"] else ""))
            ligne("Étape", "steps", j, sid, r.get("name"), a["nom"], k, a["ligne"], crits, excel, sysml, uid)
            tr("steps", j, sid, f"étape {r.get('position')} : {r.get('name')}", "action (étape)", k,
               f"{cas['nom']}::{a['nom']}", a["ligne"])
            for t, (an, txt, aid, n_) in zip(ex_trig, lus_t):
                tr("step_triggers", idx_onglet.get(("step_triggers", t["trigger_id"])), t["trigger_id"],
                   f"{'déclencheur' if t['kind'] == 'trigger' else 'condition'} : {nom_comp.get(t['component_id'])} "
                   f"{t.get('operator') or 'is'} {etat_nom.get(t['state_id'])}", "attribute (déclencheur)", k,
                   f"{cas['nom']}::{a['nom']}::{an}", n_)
            for x in nds.get(sid, []):
                b_nom = next((b for b, _ in a["satisfy"] if t_bes.get(b) == x), None)
                tr("step_user_needs", nds_i.get((sid, x)), f"{sid}->{x}",
                   f"l'étape « {r.get('name')} » sert le besoin « {besoin_nom.get(x)} »", "satisfy (étape -> besoin)",
                   k if b_nom else None, f"{cas['nom']}::{a['nom']} satisfy Needs::{b_nom}" if b_nom else "—",
                   next((n_ for b, n_ in a["satisfy"] if b == b_nom), None))
        # enchaînements
        for (j1, r1), (j2, r2) in zip(etp, etp[1:]):
            a1, a2 = action_de.get(r1["step_id"]), action_de.get(r2["step_id"])
            lsys, kk, elem = None, None, "—"
            if a1 and a2:
                if a1[0] == a2[0]:
                    lsys = next((n_ for x, y, n_ in a1[1]["ordre"] if x == a1[2]["nom"] and y == a2[2]["nom"]), None)
                    kk, elem = a1[0], f"{a1[1]['nom']} : first {a1[2]['nom']} then {a2[2]['nom']}"
                elif f"suite de {a1[2]['nom']} " in (lus[a2[0]][1]["entete"] or ""):
                    lsys, kk = lus[a2[0]][1]["ligne_package"] + 1, a2[0]
                    elem = f"{lus[a2[0]][1]['package']} : suite de {a1[2]['nom']} (doc du package)"
            tr("steps", j2, f"{r1['step_id']}=>{r2['step_id']}",
               f"étape {r1.get('position')} « {r1.get('name')} » puis étape {r2.get('position')} « {r2.get('name')} »",
               "first … then … (enchaînement)", kk if lsys else None, elem if lsys else "—", lsys)
    trace.sort(key=lambda t: (10 ** 6 if t["code"] is None else t["code"], t["ligne_sysml"] or 10 ** 9))
    return out, trace
