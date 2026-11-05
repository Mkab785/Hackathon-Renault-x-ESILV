"""
Vérification par RELECTURE : le texte SysML produit est relu (sans utiliser le
modèle interne du traducteur) puis comparé directement aux lignes de l'Excel.

Si le traducteur avait un défaut (étape oubliée, ordre inversé, besoin rattaché
à la mauvaise étape, déclencheur faux...), la relecture le verrait, parce qu'elle
part des deux bouts : ce qui est écrit dans le .sysml et ce qui est écrit dans
l'Excel.

Pour chaque élément traduit, on vérifie :
  persona, composant, besoin : présent (id dans doc), nom identique
  cas d'usage : présent, nom, acteurs = personas de use_case_personas, nombre d'étapes
  étape : présente dans le BON cas d'usage, nom, place dans l'enchaînement
          first/then = position Excel, déclencheurs (ordre, type, texte, id),
          besoins satisfaits = step_user_needs
"""
import re
import unicodedata
from collections import defaultdict

_DOC = r"doc /\* (.*?) \*/"
_STR = r'"((?:[^"\\]|\\.)*)"'


def _norm(s):
    s = unicodedata.normalize("NFD", "" if s is None else str(s))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _meme_nom(excel, sysml):
    """Le nom SysML est-il bien le nom Excel (à la mise en forme près) ?"""
    e, x = _norm(excel), _norm(sysml)
    if not e:                       # nom Excel sans lettres ni chiffres : rien à comparer
        return True
    if x.startswith("n") and e[0].isdigit():
        x = x[1:]
    return x == e or (x.startswith(e) and x[len(e):].isdigit())


def _unescape(s):
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t", "r": "\r"}.get(m.group(1), m.group(1)), s)


# ---------------------------------------------------------------- relecture du texte
def relire(texte):
    """Analyse le texte SysML (format du traducteur, indentation libre)."""
    m = {"personas": {}, "composants": {}, "besoins": {}, "cas": {}}
    paquet = None
    uc = act = None
    attente_doc = None
    for n, brut in enumerate(texte.splitlines(), start=1):
        l = brut.strip()
        if not l:
            continue
        g = re.match(r"package (\w+) \{$", l)
        if g:
            paquet = g.group(1)
            continue
        if attente_doc is not None:
            g = re.match(_DOC + "$", l)
            if g:
                attente_doc["id"] = g.group(1)
                if attente_doc is uc:
                    m["cas"][g.group(1)] = uc
                attente_doc = None
                continue
        g = re.match(r"part (\w+) : Persona \{ " + _DOC + r" \}$", l)
        if g and paquet == "Personas":
            m["personas"][g.group(2)] = (g.group(1), n)
            continue
        g = re.match(r"part def (\w+) \{ " + _DOC + r" \}$", l)
        if g and paquet == "Components":
            m["composants"][g.group(2)] = (g.group(1), n)
            continue
        g = re.match(r"requirement (\w+) \{ " + _DOC + r" \}$", l)
        if g and paquet == "Needs":
            m["besoins"][g.group(2)] = (g.group(1), n)
            continue
        g = re.match(r"use case def (\w+) \{$", l)
        if g:
            uc = {"nom": g.group(1), "ligne": n, "id": None, "acteurs": [], "actions": {}, "ordre": []}
            attente_doc = uc
            continue
        g = re.match(r"actor (\w+) : Personas::Persona;$", l)
        if g and uc is not None:
            uc["acteurs"].append((g.group(1), n))
            continue
        g = re.match(r"action (\w+) \{$", l)
        if g and uc is not None:
            act = {"nom": g.group(1), "ligne": n, "id": None, "attributs": [], "satisfy": []}
            uc["actions"][g.group(1)] = act
            attente_doc = act
            continue
        g = re.match(r"attribute (\w+) = " + _STR + r" \{ " + _DOC + r" \}$", l)
        if g and act is not None:
            act["attributs"].append((g.group(1), _unescape(g.group(2)), g.group(3), n))
            continue
        g = re.match(r"satisfy Needs::(\w+);$", l)
        if g and act is not None:
            act["satisfy"].append((g.group(1), n))
            continue
        g = re.match(r"first (\w+) then (\w+);$", l)
        if g and uc is not None:
            uc["ordre"].append((g.group(1), g.group(2), n))
            continue
        if l == "}":
            if act is not None:
                act = None
            elif uc is not None and paquet == "UseCases":
                uc = None
    return m


def _chaine(uc):
    """Ordre des actions d'après les first/then. Renvoie (liste, problème éventuel)."""
    suiv = {}
    cibles = set()
    for a, b, _ in uc["ordre"]:
        if a in suiv:
            return [], f"« {a} » a deux étapes suivantes"
        suiv[a] = b
        cibles.add(b)
    noms = list(uc["actions"])
    if not noms:
        return [], ""
    debuts = [x for x in noms if x not in cibles]
    if len(debuts) != 1:
        return [], f"{len(debuts)} début(s) d'enchaînement au lieu de 1"
    ordre, cur, vus = [], debuts[0], set()
    while cur is not None:
        if cur in vus:
            return [], "boucle dans l'enchaînement"
        vus.add(cur)
        ordre.append(cur)
        cur = suiv.get(cur)
    if len(ordre) != len(noms):
        return ordre, f"{len(noms) - len(ordre)} étape(s) hors de l'enchaînement"
    return ordre, ""


# ---------------------------------------------------------------- comparaison
def _crit(nom, excel, sysml, ok, ecart=""):
    """Un critère comparé : valeur lue dans l'Excel, valeur relue dans le SysML."""
    return {"nom": nom, "excel": excel, "sysml": sysml, "ok": bool(ok), "ecart": "" if ok else ecart}


def verifier_relecture(ds, texte):
    """Renvoie une ligne par élément traduit :
    {categorie, onglet, ligne_excel, id, parent, nom_excel, nom_sysml, ligne_sysml,
     criteres: [{nom, excel, sysml, ok, ecart}], ok, ecarts, excel, sysml}"""
    s = relire(texte)
    out = []
    rn = ds.row_number

    def ligne(cat, onglet, i, id_, nom_excel, nom_sysml, lsys, criteres, excel, sysml, parent=""):
        ecarts = [c["ecart"] for c in criteres if not c["ok"]]
        out.append({"categorie": cat, "onglet": onglet, "ligne_excel": rn(onglet, i), "id": id_,
                    "parent": parent, "nom_excel": nom_excel, "nom_sysml": nom_sysml,
                    "ligne_sysml": lsys, "criteres": criteres, "ok": not ecarts, "ecarts": ecarts,
                    "excel": excel, "sysml": sysml})

    for cat, onglet, pk, cle in (("Persona", "personas", "persona_id", "personas"),
                                 ("Composant", "components", "component_id", "composants"),
                                 ("Besoin", "user_needs", "user_need_id", "besoins")):
        for i, r in enumerate(ds.get(onglet)):
            trouve = s[cle].get(r[pk])
            if not trouve:
                ligne(cat, onglet, i, r[pk], r.get("name"), "", None,
                      [_crit("Présence", r[pk], "—", False, "absent du SysML")], r.get("name"), "—")
                continue
            nom_sysml = trouve[0][4:] if cle == "besoins" and trouve[0].startswith("need") else trouve[0]
            c = _crit("Nom", r.get("name"), trouve[0], _meme_nom(r.get("name"), nom_sysml),
                      f"nom différent : « {r.get('name')} » / {trouve[0]}")
            ligne(cat, onglet, i, r[pk], r.get("name"), trouve[0], trouve[1], [c], r.get("name"), trouve[0])

    besoin_par_nom = {v[0]: k for k, v in s["besoins"].items()}
    pnom = {p["persona_id"]: p["name"] for p in ds.get("personas")}
    comp = {c["component_id"]: c["name"] for c in ds.get("components")}
    etat = {x["state_id"]: x["name"] for x in ds.get("component_states")}
    besoin_nom = {b["user_need_id"]: b["name"] for b in ds.get("user_needs")}
    ucp = defaultdict(list)
    for r in ds.get("use_case_personas"):
        if r["persona_id"] not in ucp[r["use_case_id"]]:
            ucp[r["use_case_id"]].append(r["persona_id"])
    etapes = defaultdict(list)
    for i, r in enumerate(ds.get("steps")):
        etapes[r["use_case_id"]].append((i, r))
    trig = defaultdict(list)
    for r in ds.get("step_triggers"):
        trig[r["step_id"]].append(r)
    nds = defaultdict(set)
    for r in ds.get("step_user_needs"):
        nds[r["step_id"]].add(r["user_need_id"])

    def pos(v):
        return int(float(v))

    for i, u in enumerate(ds.get("use_cases")):
        uid = u["use_case_id"]
        cu = s["cas"].get(uid)
        n_ex = len(etapes.get(uid, []))
        if not cu:
            ligne("Cas d'usage", "use_cases", i, uid, u.get("name"), "", None,
                  [_crit("Présence", uid, "—", False, "absent du SysML")], u.get("name"), "—")
            for j, r in etapes.get(uid, []):
                ligne("Étape", "steps", j, r["step_id"], r.get("name"), "", None,
                      [_crit("Présence", r["step_id"], "—", False, "cas d'usage absent du SysML")],
                      f"{r.get('position')}. {r.get('name')}", "—", uid)
            continue
        crits = [_crit("Nom", u.get("name"), cu["nom"], _meme_nom(u.get("name"), cu["nom"]),
                       f"nom différent : « {u.get('name')} » / {cu['nom']}")]
        ex_act = [pnom.get(p, p) for p in ucp.get(uid, [])]
        sy_act = [a for a, _ in cu["acteurs"]]
        a_ex, a_sy = sorted(_norm(x) for x in ex_act), sorted(_norm(x) for x in sy_act)
        crits.append(_crit("Acteurs", ex_act, sy_act,
                           len(a_ex) == len(a_sy) and all(_meme_nom(e, x) for e, x in zip(a_ex, a_sy)),
                           "acteurs différents des personas du cas d'usage"))
        crits.append(_crit("Nombre d'étapes", n_ex, len(cu["actions"]), len(cu["actions"]) == n_ex,
                           f"{len(cu['actions'])} action(s) pour {n_ex} étape(s)"))
        ordre, pb = _chaine(cu)
        crits.append(_crit("Enchaînement", f"positions 1 à {n_ex}",
                           f"{len(ordre)} action(s) reliées par first … then …" if not pb else pb,
                           not pb, "enchaînement : " + pb))
        ligne("Cas d'usage", "use_cases", i, uid, u.get("name"), cu["nom"], cu["ligne"], crits,
              f"{u.get('name')} — acteurs : {', '.join(map(str, ex_act))} — {n_ex} étape(s)",
              f"{cu['nom']} — acteurs : {', '.join(sy_act)} — {len(cu['actions'])} action(s)")

        par_id = {a["id"]: a for a in cu["actions"].values()}
        rang_excel = {r["step_id"]: k + 1 for k, (_, r) in
                      enumerate(sorted(etapes.get(uid, []), key=lambda t: pos(t[1]["position"])))}
        for j, r in etapes.get(uid, []):
            sid = r["step_id"]
            a = par_id.get(sid)
            ex_trig = sorted(trig.get(sid, []), key=lambda t: pos(t["position"]))
            ex_txt = [f"{'Quand' if t['kind'] == 'trigger' else 'Et si'} {comp.get(t['component_id'])} "
                      f"{t.get('operator') or 'is'} {etat.get(t['state_id'])}" for t in ex_trig]
            ex_b = sorted(str(besoin_nom.get(n, n)) for n in nds.get(sid, ()))
            excel = (f"{r.get('position')}. {r.get('name')}"
                     + (" | " + " ; ".join(ex_txt) if ex_txt else "")
                     + (" | sert : " + " ; ".join(ex_b) if ex_b else ""))
            if a is None:
                ailleurs = any(sid == x["id"] for c in s["cas"].values() for x in c["actions"].values())
                ligne("Étape", "steps", j, sid, r.get("name"), "", None,
                      [_crit("Présence", sid, "—", False,
                             "rangée dans un autre cas d'usage" if ailleurs else "absente du SysML")],
                      excel, "—", uid)
                continue
            crits = []
            nom = re.sub(r"^step\d+", "", a["nom"])
            crits.append(_crit("Nom", r.get("name"), a["nom"], _meme_nom(r.get("name"), nom),
                               f"nom différent : « {r.get('name')} » / {a['nom']}"))
            rang = (ordre.index(a["nom"]) + 1) if a["nom"] in ordre else None
            crits.append(_crit("Rang", rang_excel[sid], rang if rang is not None else "?",
                               rang == rang_excel[sid],
                               f"rang {rang if rang is not None else '?'} dans l'enchaînement SysML, "
                               f"{rang_excel[sid]} dans l'Excel"))
            lus = a["attributs"]
            sy_txt = [f"{'Quand' if an.startswith('triggerEvent') else 'Et si'} {txt}" for an, txt, _, _ in lus]
            ec_t = []
            if len(lus) != len(ex_trig):
                ec_t.append(f"{len(lus)} déclencheur(s) dans le SysML, {len(ex_trig)} dans l'Excel")
            for t, (an, txt, aid, _) in zip(ex_trig, lus):
                attendu = f"{comp.get(t['component_id'])} {t.get('operator') or 'is'} {etat.get(t['state_id'])}"
                if aid != t["trigger_id"]:
                    ec_t.append(f"déclencheur {t['position']} : id {aid} au lieu de {t['trigger_id']}")
                if txt != attendu:
                    ec_t.append(f"déclencheur {t['position']} : « {txt} » au lieu de « {attendu} »")
                if (t["kind"] == "trigger") != an.startswith("triggerEvent"):
                    ec_t.append(f"déclencheur {t['position']} : {an} alors que l'Excel dit « {t['kind']} »")
            crits.append(_crit("Déclencheurs", ex_txt, sy_txt, not ec_t, " ; ".join(ec_t)))
            sat = {besoin_par_nom.get(b) for b, _ in a["satisfy"]}
            attendus = set(nds.get(sid, ()))
            ec_b = []
            if sat != attendus:
                manq = sorted(str(besoin_nom.get(n, n)) for n in attendus - sat)
                trop = [b for b, _ in a["satisfy"] if besoin_par_nom.get(b) not in attendus]
                if manq:
                    ec_b.append("besoin(s) non satisfait(s) dans le SysML : " + " ; ".join(manq))
                if trop:
                    ec_b.append("satisfy en trop : " + " ; ".join(trop))
            crits.append(_crit("Besoins servis", ex_b, sorted(b for b, _ in a["satisfy"]), not ec_b, " ; ".join(ec_b)))
            sysml = (f"{a['nom']} (rang {rang if rang is not None else '?'})"
                     + (" | " + " ; ".join(f"{an} = {txt}" for an, txt, _, _ in lus) if lus else "")
                     + (" | satisfy " + " ; ".join(b for b, _ in a["satisfy"]) if a["satisfy"] else ""))
            ligne("Étape", "steps", j, sid, r.get("name"), a["nom"], a["ligne"], crits, excel, sysml, uid)
    return out


def resume(verif):
    n = len(verif)
    ok = sum(1 for v in verif if v["ok"])
    return ok, n

