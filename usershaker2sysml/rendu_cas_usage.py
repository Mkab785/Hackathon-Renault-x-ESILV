"""
Traduction COMPLÈTE par cas d'usage : des textes SysML v2 autonomes, chacun collé seul
dans son propre projet CATIA Magic Community.

Limite de CATIA Magic Community : 20 000 caractères par texte (Textual Editor).
La taille est comptée avec des fins de ligne Windows (2 caractères), pour ne jamais
dépasser même si le texte est copié depuis le Bloc-notes : voir taille_catia().

Deux écritures :

  « compacte » (par défaut, option B choisie le 4 nov. 2026) : 4 codes pour 4 cas d'usage.
    Toute l'information de l'Excel est gardée, SAUF les liens des images des étapes
    (steps.image_url, qui restent dans l'Excel). Les données répétitives sont
    regroupées en texte :
      - états d'un composant : 1 attribut  states = "Off [id] ; Welcome [id] ; ..."
      - grille composant × étape : 1 attribut par composant dans le cas d'usage
          gridSteerByWireHalfWheel = "1: Normal ratio ; 3: Stowing > Stowed ; ..."
          (numéro = position de l'étape ; « > » = états successifs dans la même étape)
      - ressentis : 1 attribut par étape
          feedback = "leaMartin +2 | action | insight [id] ; ..."  (absent = persona absente)
      - groupes d'étapes : 1 attribut dans le cas d'usage
          stepGroups = "Charging [id]: 1-2 ; MVP · Lounge [id]: 3-5"

  « détaillée » : un attribut par donnée (un état, une case de la grille, un champ de
    ressenti), liens des images compris. Collée dans CATIA en 7 codes (4 nov. 2026) ;
    avec la limite de 20 000 caractères : 5 codes (UC4 coupé en 2 parties).

Découpage (les deux écritures) : un texte par cas d'usage s'il tient dans la limite ;
sinon le cas d'usage est coupé en parties successives, de préférence entre deux groupes
d'étapes. La partie 1 contient toutes les définitions du cas d'usage ; les suivantes
seulement le nécessaire pour être valides seules. Le lien entre deux parties est écrit
dans le doc du package (« suite de stepXX (partie 1) »).

Contenu (en plus du format validé : étapes, déclencheurs, besoins satisfaits,
enchaînement first ... then) :
    use_cases          description, story, status, folder
    personas           âge, genre, biographie
    components         rôle, catégorie, description, composant parent, états
    user_needs         description, lien, bibliothèque (libraryName)
    step_groups        groupe de chaque étape
    steps              description, texte libre du déclencheur, note (+ image en détaillée)
    step_component_states   la grille composant × étape, dans l'ordre
    persona_step_feedback   présence, action, insight, émotion (-5 à +5)
    step_unused_components  composants non utilisés à l'étape

Constructions utilisées : celles du format validé (package, part def, part, requirement,
use case def, actor, action, attribute = "texte" { doc }, satisfy, first ... then,
doc /* */), plus, en écriture détaillée, des attributs entiers (émotions) et booléens.
Les identifiants UserShaker et le nom exact de l'Excel sont dans doc /* id : nom */
ou entre crochets [id] dans les textes regroupés.
"""
import re
from collections import defaultdict

from .noms import KEYWORDS, Scope, camel, chaine, commentaire, pascal

LIMITE_CATIA = 20000     # caractères par texte, Textual Editor de CATIA Magic Community
COMPACTE, DETAILLEE = "compacte", "detaillee"


class ErreurDecoupage(Exception):
    """Une étape seule ne tient pas dans la limite : impossible de découper davantage."""


def taille_catia(texte):
    """Nombre de caractères comptés par CATIA, au pire (fins de ligne Windows \\r\\n)."""
    return len(texte) + texte.count("\n")


def _pos(v):
    """Position / ordre numérique ; une valeur illisible passe en dernier (les contrôles la signalent)."""
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 10 ** 6


def _txt(v):
    if v is None:
        return None
    s = " ".join(str(v).split())
    return s or None


def _attr(w, nom, valeur, doc_id=None):
    if valeur is None:
        return
    if nom in KEYWORDS:              # sécurité : un mot réservé est refusé comme nom par CATIA
        nom += "_"
    w(f"attribute {nom} = {chaine(valeur)}" + (f" {{ doc /* {commentaire(doc_id)} */ }}" if doc_id else ";"))


def _octets(texte):
    return len(texte.encode("utf-8"))


def _plages(nums):
    """[1, 2, 3, 5] -> "1-3, 5" """
    nums = sorted(set(nums))
    out, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(str(nums[i]) if i == j else f"{nums[i]}-{nums[j]}")
        i = j + 1
    return ", ".join(out)


def _score(f):
    if f.get("is_present") in (False, "false", "False", 0):
        return "absent"
    if f.get("emotion_score") is None:
        return "?"
    try:
        return f"{int(float(f['emotion_score'])):+d}"
    except (TypeError, ValueError):
        return str(f["emotion_score"])


def item_ressenti(pn, f):
    """Un ressenti en écriture compacte : « leaMartin +2 | action | insight [id] »."""
    return f"{pn} {_score(f)} | {_txt(f.get('action')) or ''} | {_txt(f.get('insight')) or ''} [{f['feedback_id']}]"


def item_etat(st):
    desc = _txt(st.get("description"))
    return f"{_txt(st['name'])} [{st['state_id']}]" + (f" ({desc})" if desc else "")


def _preparer(ds):
    S = {k: ds.get(k) for k in ds.sheets}
    d = {"S": S, "meta": ds.meta()}
    d["comp"] = {c["component_id"]: c for c in S.get("components", [])}
    etats = defaultdict(list)
    for st in sorted(S.get("component_states", []), key=lambda r: _pos(r["position"])):
        etats[st["component_id"]].append(st)
    d["etats"] = etats
    d["etat_nom"] = {st["state_id"]: st["name"] for st in S.get("component_states", [])}
    d["pers"] = {p["persona_id"]: p for p in S.get("personas", [])}
    d["besoin"] = {n["user_need_id"]: n for n in S.get("user_needs", [])}
    d["groupe"] = {g["group_id"]: g for g in S.get("step_groups", [])}
    for cle, onglet, tri in (("trig", "step_triggers", "position"), ("grille", "step_component_states", "sequence")):
        dd = defaultdict(list)
        for r in sorted(S.get(onglet, []), key=lambda r: _pos(r.get(tri) or 1)):
            dd[r["step_id"]].append(r)
        d[cle] = dd
    d["steps_uc"] = defaultdict(list)
    for s in sorted(S.get("steps", []), key=lambda r: _pos(r["position"])):
        d["steps_uc"][s["use_case_id"]].append(s)
    d["inutil"] = defaultdict(list)
    for u in S.get("step_unused_components", []):
        d["inutil"][u["step_id"]].append(u["component_id"])
    d["fb"] = defaultdict(list)
    for f in S.get("persona_step_feedback", []):
        d["fb"][f["step_id"]].append(f)
    d["nds"] = defaultdict(list)
    for r in S.get("step_user_needs", []):
        if r["user_need_id"] not in d["nds"][r["step_id"]]:
            d["nds"][r["step_id"]].append(r["user_need_id"])
    for cle, onglet, col in (("ucp", "use_case_personas", "persona_id"), ("ucc", "use_case_components", "component_id")):
        dd = defaultdict(list)
        for r in sorted(S.get(onglet, []), key=lambda r: _pos(r["position"])):
            if r[col] not in dd[r["use_case_id"]]:
                dd[r["use_case_id"]].append(r[col])
        d[cle] = dd
    return d


def _noms(d, p_ids, c_ids, n_ids):
    sc = Scope(["Persona"])
    p_nom = {pid: sc.uniq(camel(d["pers"][pid]["name"], "persona")) for pid in p_ids}
    sc = Scope()
    c_nom = {cid: sc.uniq(pascal(d["comp"][cid]["name"], "Component")) for cid in c_ids}
    sc = Scope()
    n_nom = {nid: sc.uniq(camel("need " + str(d["besoin"][nid]["name"]), "need")) for nid in n_ids}
    return p_nom, c_nom, n_nom


def _restes(d):
    """Personas, composants et besoins rattachés à aucun cas d'usage (ni acteur, ni ressenti,
    ni déclencheur, ni grille, ni besoin servi) : ils sont écrits avec le cas d'usage 1 pour
    que toute l'information de l'Excel soit dans les codes."""
    S = d["S"]
    p_vus, c_vus, n_vus = set(), set(), set()
    for uid, pids in d["ucp"].items():
        p_vus |= set(pids)
    for uid, cids in d["ucc"].items():
        c_vus |= set(cids)
    for s in S.get("steps", []):
        sid = s["step_id"]
        p_vus |= {f["persona_id"] for f in d["fb"].get(sid, [])}
        c_vus |= {t["component_id"] for t in d["trig"].get(sid, [])}
        c_vus |= {g["component_id"] for g in d["grille"].get(sid, [])}
        c_vus |= set(d["inutil"].get(sid, []))
        n_vus |= set(d["nds"].get(sid, []))
    for cid in list(c_vus):
        par = d["comp"].get(cid, {}).get("parent_component_id")
        if par in d["comp"]:
            c_vus.add(par)
    return ([p["persona_id"] for p in S.get("personas", []) if p["persona_id"] not in p_vus],
            [c["component_id"] for c in S.get("components", []) if c["component_id"] not in c_vus],
            [n["user_need_id"] for n in S.get("user_needs", []) if n["user_need_id"] not in n_vus])


def _cas_usage(d, num, uc, noms=None, restes=None):
    """Tout ce qu'il faut pour écrire un cas d'usage, avec des noms fixés une fois pour toutes
    (identiques quel que soit le découpage). noms = (p_nom, c_nom, n_nom) globaux pour le
    fichier unique ; sinon les noms sont choisis dans le seul cas d'usage."""
    comp, pers, besoin = d["comp"], d["pers"], d["besoin"]
    uid = uc["use_case_id"]
    etapes = d["steps_uc"].get(uid, [])
    sids = [s["step_id"] for s in etapes]
    p_ids = list(d["ucp"].get(uid, []))
    for sid in sids:
        for f in d["fb"].get(sid, []):
            if f["persona_id"] in pers and f["persona_id"] not in p_ids:
                p_ids.append(f["persona_id"])
    c_ids = list(d["ucc"].get(uid, []))
    for sid in sids:
        for cid in ([t["component_id"] for t in d["trig"].get(sid, [])]
                    + [g["component_id"] for g in d["grille"].get(sid, [])] + d["inutil"].get(sid, [])):
            if cid in comp and cid not in c_ids:
                c_ids.append(cid)
    for cid in list(c_ids):
        par = comp[cid].get("parent_component_id")
        if par in comp and par not in c_ids:
            c_ids.append(par)
    n_ids = []
    for sid in sids:
        for nid in d["nds"].get(sid, []):
            if nid in besoin and nid not in n_ids:
                n_ids.append(nid)
    if restes:
        p_ids += [x for x in restes[0] if x not in p_ids]
        c_ids += [x for x in restes[1] if x not in c_ids]
        n_ids += [x for x in restes[2] if x not in n_ids]
    if noms:
        p_nom, c_nom, n_nom = noms
    else:
        p_nom, c_nom, n_nom = _noms(d, p_ids, c_ids, n_ids)
    asc = Scope(["description", "story", "status", "folder", "stepGroups"])
    acteurs = [asc.uniq(p_nom[pid]) for pid in d["ucp"].get(uid, []) if pid in p_nom]
    s_nom = [asc.uniq(camel(f"step{_pos(s['position']):02d} {s['name']}", "step")) for s in etapes]
    g_nom = {cid: asc.uniq("grid" + c_nom[cid]) for cid in c_ids if cid in c_nom}
    return {"num": num, "uc": uc, "etapes": etapes, "s_nom": s_nom, "acteurs": acteurs, "g_nom": g_nom,
            "p_ids": p_ids, "p_nom": p_nom, "c_ids": c_ids, "c_nom": c_nom, "n_ids": n_ids, "n_nom": n_nom,
            "groupes": [s.get("group_id") for s in etapes]}


def _definitions(d, w, complet, p_ids, p_nom, c_ids, c_nom, n_ids, n_nom, etapes, ecriture=DETAILLEE):
    """Packages Personas, Components, Needs. complet=False : le strict nécessaire
    (part def Persona et les besoins satisfaits par les étapes données)."""
    comp, pers, besoin = d["comp"], d["pers"], d["besoin"]
    # Personas
    w("package Personas {")
    w("part def Persona;")
    if complet:
        for pid in p_ids:
            p = pers[pid]
            w(f"part {p_nom[pid]} : Persona {{")
            w(f"doc /* {commentaire(pid)} : {commentaire(_txt(p['name']))} */")
            _attr(w, "ageCategory", _txt(p.get("age_category")))
            _attr(w, "gender", _txt(p.get("gender")))
            _attr(w, "biography", _txt(p.get("biography")))
            w("}")
    w("}")

    # Composants et leurs états (partie 1 seulement : rien d'autre n'y fait référence)
    if complet:
        w("package Components {")
        for cid in c_ids:
            c = comp[cid]
            w(f"part def {c_nom[cid]} {{")
            w(f"doc /* {commentaire(cid)} : {commentaire(_txt(c['name']))} */")
            _attr(w, "role", _txt(c.get("role")))
            _attr(w, "category", _txt(c.get("category")))
            _attr(w, "description", _txt(c.get("description")))
            par = c.get("parent_component_id")
            if par in c_nom:
                _attr(w, "parent", c_nom[par])
            if ecriture == COMPACTE:
                if d["etats"].get(cid):
                    _attr(w, "states", " ; ".join(item_etat(st) for st in d["etats"][cid]))
            else:
                for m, st in enumerate(d["etats"].get(cid, []), 1):
                    _attr(w, f"state{m}", _txt(st["name"]), st["state_id"])
                    _attr(w, f"state{m}Description", _txt(st.get("description")))
            w("}")
        w("}")

    # Besoins : tous en partie 1 ; ensuite seulement ceux satisfaits dans la partie
    w("package Needs {")
    if complet:
        for nid in n_ids:
            nb = besoin[nid]
            w(f"requirement {n_nom[nid]} {{")
            w(f"doc /* {commentaire(nid)} : {commentaire(_txt(nb['name']))} */")
            _attr(w, "description", _txt(nb.get("description")))
            _attr(w, "referenceUrl", _txt(nb.get("reference_url")))
            _attr(w, "libraryName", _txt(nb.get("library_name")))      # « library » est un mot réservé
            w("}")
    else:
        vus = []
        for s in etapes:
            for nid in d["nds"].get(s["step_id"], []):
                if nid in n_nom and nid not in vus:
                    vus.append(nid)
                    w(f"requirement {n_nom[nid]} {{ doc /* {commentaire(nid)} : "
                      f"{commentaire(_txt(besoin[nid]['name']))} */ }}")
    w("}")


def _etape(d, u, w, s, sn, ecriture=DETAILLEE):
    """Une étape (action) avec déclencheurs, besoins satisfaits et, selon l'écriture,
    la grille et les ressentis."""
    comp = d["comp"]
    compacte = ecriture == COMPACTE
    w(f"action {sn} {{")
    w(f"doc /* {commentaire(s['step_id'])} : {commentaire(_txt(s['name']))} */")
    ssc = Scope(["group", "description", "triggerText", "note", "imageUrl", "feedback", "unusedComponents"])
    g = d["groupe"].get(s.get("group_id"))
    if g and not compacte:
        _attr(w, "group", _txt(g["name"]), g["group_id"])
    _attr(w, "description", _txt(s.get("description")))
    _attr(w, "triggerText", _txt(s.get("trigger_text")))
    _attr(w, "note", _txt(s.get("note")))
    if not compacte:
        _attr(w, "imageUrl", _txt(s.get("image_url")))
    for t in d["trig"].get(s["step_id"], []):
        tn = ssc.uniq("triggerEvent" if t["kind"] == "trigger" else "condition")
        texte = f"{comp[t['component_id']]['name']} {t.get('operator') or 'is'} {d['etat_nom'][t['state_id']]}"
        _attr(w, tn, texte, t["trigger_id"])
    for nid in d["nds"].get(s["step_id"], []):
        if nid in u["n_nom"]:
            w(f"satisfy Needs::{u['n_nom'][nid]};")
    if compacte:
        inutil = [u["c_nom"][cid] for cid in d["inutil"].get(s["step_id"], []) if cid in u["c_nom"]]
        if inutil:
            _attr(w, "unusedComponents", " ; ".join(inutil))
        fbs = d["fb"].get(s["step_id"], [])
        if fbs:
            _attr(w, "feedback", " ; ".join(item_ressenti(u["p_nom"].get(f["persona_id"], "persona"), f) for f in fbs))
        w("}")
        return
    for gr in d["grille"].get(s["step_id"], []):
        _attr(w, ssc.uniq(camel(comp[gr["component_id"]]["name"], "component")),
              _txt(d["etat_nom"].get(gr["state_id"])))
    for cid in d["inutil"].get(s["step_id"], []):
        _attr(w, ssc.uniq("unused" + u["c_nom"][cid]), _txt(comp[cid]["name"]))
    for f in d["fb"].get(s["step_id"], []):
        pn = u["p_nom"].get(f["persona_id"], "persona")
        if f.get("is_present") in (False, "false", "False", 0):
            w(f"attribute {ssc.uniq(pn + 'Present')} = false {{ doc /* {commentaire(f['feedback_id'])} */ }}")
            continue
        if f.get("emotion_score") is not None:
            try:
                val = str(int(float(f["emotion_score"])))
            except (TypeError, ValueError):
                val = chaine(f["emotion_score"])
            w(f"attribute {ssc.uniq(pn + 'Emotion')} = {val} {{ doc /* {commentaire(f['feedback_id'])} */ }}")
        _attr(w, ssc.uniq(pn + "Action"), _txt(f.get("action")))
        _attr(w, ssc.uniq(pn + "Insight"), _txt(f.get("insight")))
    w("}")


def _groupes_et_grille(d, u, w, etapes):
    """Écriture compacte, dans le cas d'usage : groupes d'étapes puis grille composant × étape,
    pour les étapes données."""
    groupes = {}
    for s in etapes:
        g = d["groupe"].get(s.get("group_id"))
        if g:
            groupes.setdefault(g["group_id"], (g, []))[1].append(_pos(s["position"]))
    if groupes:
        _attr(w, "stepGroups", " ; ".join(f"{_txt(g['name'])} [{gid}]: {_plages(nums)}"
                                          for gid, (g, nums) in groupes.items()))
    par_comp = {}
    for s in etapes:
        for gr in d["grille"].get(s["step_id"], []):
            par_comp.setdefault(gr["component_id"], {}).setdefault(_pos(s["position"]), []).append(
                _txt(d["etat_nom"].get(gr["state_id"])) or "?")
    return [(u["g_nom"][cid], " ; ".join(f"{p}: {' > '.join(st)}" for p, st in par_comp[cid].items()))
            for cid in u["c_ids"] if cid in par_comp]


def _rendre(d, u, i, j, k, n, ecriture=DETAILLEE):
    """Texte de la partie k/n du cas d'usage u, avec les étapes i..j-1 (k=n=1 : cas d'usage entier)."""
    uc, num, etapes, s_nom = u["uc"], u["num"], u["etapes"], u["s_nom"]
    projet = d["meta"].get("project_name") or "UserShakerProject"
    export = d["meta"].get("exported_at") or ""
    complet = k == 1
    L = []
    w = L.append
    if n == 1:
        package = pascal(f"UC{num} {uc['name']}", f"UC{num}")
        w(f"package {package} {{")
        w(f"doc /* {commentaire(projet)} - cas d'usage {num} - export {commentaire(export)} */")
    else:
        package = pascal(f"UC{num} {uc['name']} Part {k}", f"UC{num}Part{k}")
        if i < j:
            a, b = _pos(etapes[i]["position"]), _pos(etapes[j - 1]["position"])
            quoi = f"étape {a}" if a == b else f"étapes {a} à {b}"
        else:
            quoi = "définitions seulement"
        notes = []
        if k > 1 and i > 0:
            notes.append(f"suite de {s_nom[i - 1]} (partie {k - 1})")
        if k < n and j < len(etapes):
            notes.append(f"suivie de {s_nom[j]} (partie {k + 1})")
        quoi += "".join(f" ; {x}" for x in notes)
        w(f"package {package} {{")
        w(f"doc /* {commentaire(projet)} - cas d'usage {num}, partie {k}/{n} : {quoi} - export {commentaire(export)} */")

    _definitions(d, w, complet, u["p_ids"], u["p_nom"], u["c_ids"], u["c_nom"], u["n_ids"], u["n_nom"],
                 etapes[i:j], ecriture)

    # Cas d'usage
    w(f"use case def {pascal(uc['name'], 'UseCase')} {{")
    w(f"doc /* {commentaire(uc['use_case_id'])} : {commentaire(_txt(uc['name']))} */")
    if complet:
        _attr(w, "description", _txt(uc.get("description")))
        _attr(w, "story", _txt(uc.get("story")))
        _attr(w, "status", _txt(uc.get("status")))
        _attr(w, "folder", _txt(uc.get("folder")))
    grille = _groupes_et_grille(d, u, w, etapes[i:j]) if ecriture == COMPACTE else []
    for a in u["acteurs"]:
        w(f"actor {a} : Personas::Persona;")
    for nom, val in grille:
        _attr(w, nom, val)
    for s, sn in zip(etapes[i:j], s_nom[i:j]):
        _etape(d, u, w, s, sn, ecriture)
    for a, b in zip(s_nom[i:j], s_nom[i + 1:j]):
        w(f"first {a} then {b};")
    w("}")
    w("}")
    return package, "\n".join(L) + "\n"


def _decouper(d, u, budget, mesure, ecriture):
    """Bornes [(i, j)] des parties. Coupe de préférence entre deux groupes d'étapes."""
    nb = len(u["etapes"])
    g = u["groupes"]
    taille = lambda i, j, k: mesure(_rendre(d, u, i, j, k, 99, ecriture)[1])   # 99 : majorant de « k/n »
    parts, i, k = [], 0, 1
    while i < nb or (k == 1 and nb == 0):
        fins_groupes = [j for j in range(i + 1, nb + 1) if j == nb or g[j] != g[j - 1]]
        ok = [j for j in fins_groupes if taille(i, j, k) <= budget]
        if not ok:
            ok = [j for j in range(i + 1, nb + 1) if taille(i, j, k) <= budget]
        if not ok:
            if k == 1 and taille(0, 0, 1) <= budget:      # définitions seules en partie 1
                parts.append((0, 0))
                k += 1
                if nb == 0:
                    break
                continue
            quoi = f"l'étape « {u['etapes'][i]['name']} » ne tient pas seule" if nb else "les définitions ne tiennent pas"
            raise ErreurDecoupage(f"cas d'usage « {u['uc']['name']} » : {quoi} dans la limite de {budget}.")
        j = max(ok)
        parts.append((i, j))
        i, k = j, k + 1
    return parts


def rendre_cas_usage(ds, budget=LIMITE_CATIA, ecriture=COMPACTE, mesure=None):
    """Renvoie [(nom_fichier, nom_package, texte, infos)], dans l'ordre des cas d'usage puis des parties.
    budget=None : un texte par cas d'usage, sans découpage.
    mesure : fonction de taille (par défaut taille_catia : caractères, fins de ligne Windows)."""
    mesure = mesure or taille_catia
    d = _preparer(ds)
    restes = _restes(d)
    sorties = []
    for num, uc in enumerate(sorted(d["S"].get("use_cases", []), key=lambda r: _pos(r["position"])), 1):
        u = _cas_usage(d, num, uc, restes=restes if num == 1 else None)
        package, entier = _rendre(d, u, 0, len(u["etapes"]), 1, 1, ecriture)
        if budget is None or mesure(entier) <= budget:
            bornes = [(0, len(u["etapes"]))]
        else:
            bornes = _decouper(d, u, budget, mesure, ecriture)
        n = len(bornes)
        for k, (i, j) in enumerate(bornes, 1):
            package, texte = (package, entier) if n == 1 else _rendre(d, u, i, j, k, n, ecriture)
            sids = [s["step_id"] for s in u["etapes"][i:j]]
            infos = {"cas_usage": uc["name"], "numero": num, "partie": k, "parties": n, "ecriture": ecriture,
                     "etapes": len(sids), "noms_etapes": u["s_nom"][i:j],
                     "personas": len(u["p_ids"]) if k == 1 else 0,
                     "composants": len(u["c_ids"]) if k == 1 else 0,
                     "etats": sum(len(d["etats"].get(c, [])) for c in u["c_ids"]) if k == 1 else 0,
                     "grille": sum(len(d["grille"].get(s, [])) for s in sids),
                     "ressentis": sum(len(d["fb"].get(s, [])) for s in sids),
                     "caracteres": len(texte), "taille_catia": taille_catia(texte),
                     "octets": _octets(texte), "lignes": texte.count("\n"),
                     "attributs": len(re.findall(r"^attribute ", texte, re.M))}
            sorties.append((f"{package}.sysml", package, texte, infos))
    return sorties


def rendre_code_entier(ds):
    """CODE ENTIER : un seul texte SysML v2 avec tous les cas d'usage, en écriture compacte (le même
    format que les codes par cas d'usage). Personas, composants et besoins sont définis une seule
    fois, puis chaque cas d'usage dans le package UseCases. Sans découpage : pour CATIA Magic sans la
    limite de 20 000 caractères de l'édition Community (version complète chez le client).
    Renvoie (nom_fichier, nom_package, texte, infos)."""
    d = _preparer(ds)
    S = d["S"]
    projet = d["meta"].get("project_name") or "UserShakerProject"
    export = d["meta"].get("exported_at") or ""
    p_ids = [p["persona_id"] for p in S.get("personas", [])]
    c_ids = [c["component_id"] for c in S.get("components", [])]
    n_ids = [n["user_need_id"] for n in S.get("user_needs", [])]
    noms = _noms(d, p_ids, c_ids, n_ids)
    package = pascal(f"{projet} Code Entier", "UserShakerProjectCodeEntier")
    ucs = sorted(S.get("use_cases", []), key=lambda r: _pos(r["position"]))
    L = []
    w = L.append
    w(f"package {package} {{")
    w(f"doc /* {commentaire(projet)} - code entier, {len(ucs)} cas d'usage, sans découpage - export {commentaire(export)} */")
    _definitions(d, w, True, p_ids, noms[0], c_ids, noms[1], n_ids, noms[2], [], COMPACTE)
    w("package UseCases {")
    usc = Scope()
    for num, uc in enumerate(ucs, 1):
        u = _cas_usage(d, num, uc, noms)
        w(f"use case def {usc.uniq(pascal(uc['name'], 'UseCase'))} {{")
        w(f"doc /* {commentaire(uc['use_case_id'])} : {commentaire(_txt(uc['name']))} */")
        _attr(w, "description", _txt(uc.get("description")))
        _attr(w, "story", _txt(uc.get("story")))
        _attr(w, "status", _txt(uc.get("status")))
        _attr(w, "folder", _txt(uc.get("folder")))
        grille = _groupes_et_grille(d, u, w, u["etapes"])
        for a in u["acteurs"]:
            w(f"actor {a} : Personas::Persona;")
        for nom, val in grille:
            _attr(w, nom, val)
        for s, sn in zip(u["etapes"], u["s_nom"]):
            _etape(d, u, w, s, sn, COMPACTE)
        for a, b in zip(u["s_nom"], u["s_nom"][1:]):
            w(f"first {a} then {b};")
        w("}")
    w("}")
    w("}")
    texte = "\n".join(L) + "\n"
    infos = {"cas_usage": len(ucs), "etapes": len(S.get("steps", [])), "caracteres": len(texte),
             "taille_catia": taille_catia(texte), "octets": _octets(texte), "lignes": texte.count("\n")}
    return f"{package}.sysml", package, texte, infos


def decouper_code_entier(texte):
    """Code entier -> [(cas d'usage, texte)] : un texte par cas d'usage, chacun avec les définitions
    communes, LIGNES CONSERVÉES (les lignes des autres cas d'usage sont remplacées par des lignes
    vides), pour relire le code entier avec les mêmes outils que les codes par cas d'usage.
    Renvoie None si le texte n'est pas un code entier (pas de package UseCases au premier niveau)."""
    lignes = texte.split("\n")
    prof, debut_uc, blocs, ouvert = 0, None, [], None
    for n, l in enumerate(lignes):
        s = l.strip()
        if prof == 1 and s == "package UseCases {":
            debut_uc = n
        elif debut_uc is not None and prof == 2 and s.startswith("use case def ") and s.endswith("{"):
            ouvert = n
        prof += s.count("{") - s.count("}")
        if ouvert is not None and prof == 2 and n > ouvert:
            blocs.append((ouvert, n))
            ouvert = None
        if debut_uc is not None and prof == 1 and n > debut_uc and s == "}":
            fin_uc = n
            break
    else:
        return None
    if debut_uc is None or not blocs:
        return None
    out = []
    for a, b in blocs:
        garde = [x if (n < debut_uc or n > fin_uc or a <= n <= b) and n not in (debut_uc, fin_uc) else ""
                 for n, x in enumerate(lignes)]
        nom = lignes[a].strip()[len("use case def "):-1].strip()
        out.append((nom, "\n".join(garde)))
    return out


def rendre_fichier_unique(ds):
    """Traduction complète (écriture détaillée) en UN SEUL texte, tous les cas d'usage, avec
    personas, composants et besoins définis une seule fois. Dépasse la limite de CATIA
    Community (environ 61 000 caractères) : utile seulement sans cette limite.
    Renvoie (nom_fichier, nom_package, texte, infos)."""
    d = _preparer(ds)
    S = d["S"]
    projet = d["meta"].get("project_name") or "UserShakerProject"
    export = d["meta"].get("exported_at") or ""
    p_ids = [p["persona_id"] for p in S.get("personas", [])]
    c_ids = [c["component_id"] for c in S.get("components", [])]
    n_ids = [n["user_need_id"] for n in S.get("user_needs", [])]
    noms = _noms(d, p_ids, c_ids, n_ids)
    package = pascal(f"{projet} Complet", "UserShakerProjectComplet")
    L = []
    w = L.append
    w(f"package {package} {{")
    w(f"doc /* {commentaire(projet)} - traduction complète, tous les cas d'usage - export {commentaire(export)} */")
    _definitions(d, w, True, p_ids, noms[0], c_ids, noms[1], n_ids, noms[2], [])
    w("package UseCases {")
    usc = Scope()
    for num, uc in enumerate(sorted(S.get("use_cases", []), key=lambda r: _pos(r["position"])), 1):
        u = _cas_usage(d, num, uc, noms)
        w(f"use case def {usc.uniq(pascal(uc['name'], 'UseCase'))} {{")
        w(f"doc /* {commentaire(uc['use_case_id'])} : {commentaire(_txt(uc['name']))} */")
        _attr(w, "description", _txt(uc.get("description")))
        _attr(w, "story", _txt(uc.get("story")))
        _attr(w, "status", _txt(uc.get("status")))
        _attr(w, "folder", _txt(uc.get("folder")))
        for a in u["acteurs"]:
            w(f"actor {a} : Personas::Persona;")
        for s, sn in zip(u["etapes"], u["s_nom"]):
            _etape(d, u, w, s, sn)
        for a, b in zip(u["s_nom"], u["s_nom"][1:]):
            w(f"first {a} then {b};")
        w("}")
    w("}")
    w("}")
    texte = "\n".join(L) + "\n"
    infos = {"octets": _octets(texte), "caracteres": len(texte), "lignes": texte.count("\n"),
             "cas_usage": len(S.get("use_cases", [])), "etapes": len(S.get("steps", [])),
             "personas": len(p_ids), "composants": len(c_ids), "etats": len(S.get("component_states", [])),
             "besoins": len(n_ids), "grille": len(S.get("step_component_states", [])),
             "ressentis": len(S.get("persona_step_feedback", []))}
    return f"{package}.sysml", package, texte, infos


def verifier_fichier_unique(ds, sortie):
    """Même relecture que verifier_cas_usage, sur le texte unique (chaque cas d'usage y est en entier)."""
    fichier, package, texte, _ = sortie
    nb = len(ds.get("use_cases"))
    return verifier_cas_usage(ds, [(fichier, package, texte, {"numero": k, "partie": 1}) for k in range(1, nb + 1)])


def _litteral(v):
    """Contenu d'un littéral chaîne SysML (sans les guillemets), échappements retirés."""
    return v.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")


def verifier_cas_usage(ds, sorties):
    """Relit les textes produits et les compare à l'Excel, cas d'usage par cas d'usage
    (toutes ses parties ensemble). Renvoie [(cas_usage, nb_controles, [écarts])].

    Contrôles (les deux écritures) :
      - chaque texte : accolades équilibrées, besoins satisfaits définis dans le même texte ;
      - chaque identifiant UserShaker du cas d'usage présent (doc /* id */ ou [id]) :
        cas d'usage, étapes, déclencheurs, ressentis, groupes, personas, composants, états, besoins ;
      - chaque étape présente une seule fois ;
      - chaque case de la grille : bonne étape, bon composant, bons états dans le bon ordre ;
      - chaque ressenti : bonne étape, bonne persona, bon score, action et insight ;
      - autant de satisfy que de besoins dans chaque étape ;
      - enchaînement dans l'ordre de l'Excel (first ... then, ou noté entre deux parties).
    En écriture compacte, en plus : états de chaque composant dans l'ordre, groupe de chaque étape.
    """
    S = {k: ds.get(k) for k in ds.sheets}
    comp = {c["component_id"]: c for c in S.get("components", [])}
    etat_nom = {st["state_id"]: st["name"] for st in S.get("component_states", [])}
    etats = defaultdict(list)
    for st in sorted(S.get("component_states", []), key=lambda r: _pos(r["position"])):
        etats[st["component_id"]].append(st)
    groupe = {g["group_id"]: g for g in S.get("step_groups", [])}
    par_uc = defaultdict(list)
    for fichier, package, texte, infos in sorties:
        par_uc[infos["numero"]].append((fichier, texte, infos))
    ucs = sorted(S.get("use_cases", []), key=lambda r: _pos(r["position"]))
    res = []
    for num, uc in enumerate(ucs, 1):
        parts = sorted(par_uc.get(num, []), key=lambda x: x[2]["partie"])
        ecarts, n = [], 0
        if not parts:
            res.append((uc["name"], 1, ["aucun texte produit"]))
            continue
        compacte = parts[0][2].get("ecriture") == COMPACTE
        docs, actions, place = set(), {}, {}
        p_nom, c_nom, grille_lue, groupes_lus, etats_lus = {}, {}, {}, {}, {}
        for p, (fichier, texte, _) in enumerate(parts):
            n += 1
            if texte.count("{") != texte.count("}"):
                ecarts.append(f"{fichier} : accolades non équilibrées")
            for b in set(re.findall(r"satisfy Needs::(\w+);", texte)):
                n += 1
                if f"requirement {b} {{" not in texte:
                    ecarts.append(f"{fichier} : besoin {b} satisfait mais non défini dans ce texte")
            docs |= set(re.findall(r"doc /\* (\S+)", texte))
            docs |= set(re.findall(r"\[([A-Za-z0-9_-]+)\]", texte))
            for m in re.finditer(r"^part (\w+) : Persona \{\ndoc /\* (\S+) ", texte, re.M):
                p_nom[m.group(2)] = m.group(1)
            for m in re.finditer(r"^part def (\w+) \{\ndoc /\* (\S+) .*?\n(.*?)^\}$", texte, re.M | re.S):
                c_nom[m.group(2)] = m.group(1)
                st = re.search(r'^attribute states = "(.*)";$', m.group(3), re.M)
                if st:
                    etats_lus[m.group(2)] = _litteral(st.group(1))
            for m in re.finditer(r"^action (\w+) \{\ndoc /\* (\S+) .*?\n(.*?)^\}$", texte, re.M | re.S):
                if m.group(2) in actions:
                    ecarts.append(f"étape {m.group(2)} présente deux fois")
                actions[m.group(2)] = (m.group(1), m.group(3))
                place[m.group(1)] = p
            for m in re.finditer(r'^attribute (grid\w+) = "(.*)";$', texte, re.M):
                for item in _litteral(m.group(2)).split(" ; "):
                    pos, _, valeurs = item.partition(": ")
                    cle = (m.group(1), pos)
                    if cle in grille_lue:
                        ecarts.append(f"grille : {m.group(1)} étape {pos} écrite deux fois")
                    grille_lue[cle] = valeurs.split(" > ")
            for m in re.finditer(r'^attribute stepGroups = "(.*)";$', texte, re.M):
                for item in _litteral(m.group(1)).split(" ; "):
                    mm = re.match(r"^(.*) \[(\S+)\]: ([\d, -]+)$", item)
                    if not mm:
                        ecarts.append(f"groupes : « {item} » illisible")
                        continue
                    for plage in mm.group(3).split(", "):
                        a, _, b = plage.partition("-")
                        for x in range(int(a), int(b or a) + 1):
                            groupes_lus[x] = (mm.group(1), mm.group(2))
        etapes = sorted([s for s in S.get("steps", []) if s["use_case_id"] == uc["use_case_id"]],
                        key=lambda r: _pos(r["position"]))
        sids = {s["step_id"] for s in etapes}
        ids = {uc["use_case_id"]} | sids
        ids |= {t["trigger_id"] for t in S.get("step_triggers", []) if t["step_id"] in sids}
        ids |= {f["feedback_id"] for f in S.get("persona_step_feedback", []) if f["step_id"] in sids}
        ids |= {f["persona_id"] for f in S.get("persona_step_feedback", []) if f["step_id"] in sids}
        ids |= {s["group_id"] for s in etapes if s.get("group_id")}
        ids |= {r["persona_id"] for r in S.get("use_case_personas", []) if r["use_case_id"] == uc["use_case_id"]}
        cids = {r["component_id"] for r in S.get("use_case_components", []) if r["use_case_id"] == uc["use_case_id"]}
        cids |= {r["component_id"] for r in S.get("step_component_states", []) if r["step_id"] in sids}
        ids |= cids
        ids |= {st["state_id"] for st in S.get("component_states", []) if st["component_id"] in cids}
        ids |= {r["user_need_id"] for r in S.get("step_user_needs", []) if r["step_id"] in sids}
        for i in sorted(ids):
            n += 1
            if i not in docs:
                ecarts.append(f"identifiant {i} absent")
        if compacte:
            for cid in sorted(cids):
                if not etats.get(cid):
                    continue
                n += 1
                attendu = " ; ".join(item_etat(st) for st in etats[cid])
                if etats_lus.get(cid) != attendu:
                    ecarts.append(f"états de « {comp[cid]['name']} » : attendu « {attendu} », "
                                  f"lu « {etats_lus.get(cid)} »")
        grille_attendue = {}
        for s in etapes:
            pos = _pos(s["position"])
            if s["step_id"] not in actions:
                n += 1
                ecarts.append(f"étape « {s['name']} » absente")
                continue
            corps = actions[s["step_id"]][1]
            vals = re.findall(r"^attribute (\w+?)\d* = (.+?)(?: \{ doc /\* (\S+) \*/ \}|;)$", corps, re.M)
            lignes_grille = sorted([g for g in S.get("step_component_states", []) if g["step_id"] == s["step_id"]],
                                   key=lambda r: _pos(r.get("sequence") or 1))
            if compacte:
                for g in lignes_grille:
                    cle = ("grid" + c_nom.get(g["component_id"], "?"), str(pos))
                    grille_attendue.setdefault(cle, []).append(_txt(etat_nom.get(g["state_id"])) or "?")
                fb_lu = re.search(r'^attribute feedback = "(.*)";$', corps, re.M)
                fb_lu = _litteral(fb_lu.group(1)) if fb_lu else ""
                fbs = [f for f in S.get("persona_step_feedback", []) if f["step_id"] == s["step_id"]]
                for f in fbs:
                    n += 1
                    pn = p_nom.get(f["persona_id"], camel(str(f["persona_id"])))
                    if item_ressenti(pn, f) not in fb_lu.split(" ; "):
                        ecarts.append(f"ressenti {f['feedback_id']} ({pn}, « {s['name']} ») absent ou différent")
                if len(fb_lu.split(" ; ")) != len(fbs) and (fbs or fb_lu):
                    ecarts.append(f"« {s['name']} » : {len(fb_lu.split(' ; ')) if fb_lu else 0} ressentis "
                                  f"pour {len(fbs)} dans l'Excel")
                g = groupe.get(s.get("group_id"))
                if g:
                    n += 1
                    if groupes_lus.get(pos) != (_txt(g["name"]), g["group_id"]):
                        ecarts.append(f"« {s['name']} » : groupe attendu {g['name']}, lu {groupes_lus.get(pos)}")
            else:
                for g in lignes_grille:
                    n += 1
                    attendu = (camel(comp[g["component_id"]]["name"], "component"), chaine(etat_nom.get(g["state_id"])))
                    if attendu not in [(a, v) for a, v, _ in vals]:
                        ecarts.append(f"grille : « {s['name']} » / {comp[g['component_id']]['name']} = "
                                      f"{etat_nom.get(g['state_id'])} absent")
                for f in [f for f in S.get("persona_step_feedback", []) if f["step_id"] == s["step_id"]]:
                    if f.get("emotion_score") is None or f.get("is_present") in (False, "false", "False", 0):
                        continue
                    n += 1
                    trouve = [v for a, v, dd in vals if dd == f["feedback_id"]]
                    try:
                        attendu_e = str(int(float(f["emotion_score"])))
                    except (TypeError, ValueError):
                        attendu_e = chaine(f["emotion_score"])
                    if not trouve or trouve[0] != attendu_e:
                        ecarts.append(f"émotion {f['feedback_id']} : attendu {f['emotion_score']}, trouvé {trouve[:1]}")
            n += 1
            nb_satisfy = len(re.findall(r"^satisfy ", corps, re.M))
            attendus = len({r["user_need_id"] for r in S.get("step_user_needs", []) if r["step_id"] == s["step_id"]})
            if nb_satisfy != attendus:
                ecarts.append(f"« {s['name']} » : {nb_satisfy} satisfy pour {attendus} besoins")
        if compacte:
            for cle in sorted(set(grille_attendue) | set(grille_lue)):
                n += 1
                if grille_attendue.get(cle) != grille_lue.get(cle):
                    ecarts.append(f"grille : {cle[0]} étape {cle[1]} : attendu {grille_attendue.get(cle)}, "
                                  f"lu {grille_lue.get(cle)}")
        noms = [actions[s["step_id"]][0] for s in etapes if s["step_id"] in actions]
        for a, b in zip(noms, noms[1:]):
            n += 1
            pa, pb = place[a], place[b]
            if pa == pb:
                if f"first {a} then {b};" not in parts[pa][1]:
                    ecarts.append(f"enchaînement {a} -> {b} absent")
            elif pb != pa + 1 or f"suite de {a} (partie {pa + 1})" not in parts[pb][1].split("\n", 2)[1]:
                ecarts.append(f"enchaînement {a} -> {b} entre deux parties non indiqué")
        res.append((uc["name"], n, ecarts))
    return res
