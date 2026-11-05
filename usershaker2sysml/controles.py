"""
Contrôles des données UserShaker avant traduction.

Deux niveaux :
  - "erreur"        : le schéma du readme n'est pas respecté. Si la donnée fautive
                      sert au modèle SysML, l'erreur BLOQUE la traduction
                      (bloque=True) : on ne produit pas un modèle faux.
  - "avertissement" : données valides mais incohérentes ou incomplètes (besoin
                      servi par aucune étape, étape sans déclencheur, trou dans
                      les positions...). Ce sont les points à remonter à l'UX.

Chaque problème a un code stable (E.. / A..) pour que l'interface web, et plus
tard un assistant IA, puissent les traiter un par un.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict

from .schema import (SHEETS, PRIMARY_KEY, POSITION_GROUPS, REQUIRED_FOR_TRANSLATION,
                     EMOTION_MIN, EMOTION_MAX, SCHEMA_VERSION)

# Colonnes réellement utilisées pour construire le modèle SysML.
# Une erreur sur l'une d'elles bloque la traduction.
USED_COLUMNS = {
    "use_cases": {"use_case_id", "position", "name"},
    "steps": {"step_id", "use_case_id", "position", "name"},
    "step_triggers": {"trigger_id", "step_id", "kind", "position", "component_id", "state_id"},
    "personas": {"persona_id", "name"},
    "use_case_personas": {"use_case_id", "persona_id", "position"},
    "components": {"component_id", "name"},
    "component_states": {"state_id", "component_id", "name"},
    "user_needs": {"user_need_id", "name"},
    "step_user_needs": {"step_id", "user_need_id"},
    # utilisées en plus par la traduction complète (4 codes) : une erreur de clé y est bloquante
    "step_component_states": {"step_id", "component_id", "state_id"},
    "persona_step_feedback": {"feedback_id", "step_id", "persona_id"},
    "use_case_components": {"use_case_id", "component_id"},
    "step_unused_components": {"step_id", "component_id"},
}


@dataclass
class Probleme:
    code: str
    gravite: str          # "erreur" | "avertissement"
    message: str          # en français, lisible par un ingénieur système
    onglet: str = ""
    ligne: int = None     # numéro de ligne Excel (en-tête = 1)
    colonne: str = ""
    id: str = ""          # id UserShaker concerné, si connu
    bloque: bool = False  # True : empêche la traduction

    def to_dict(self):
        return asdict(self)

    def __str__(self):
        loc = self.onglet
        if self.ligne:
            loc += f" ligne {self.ligne}"
        if self.colonne:
            loc += f", colonne {self.colonne}"
        tag = "BLOQUANT" if self.bloque else self.gravite.upper()
        return f"[{tag} {self.code}] {loc} : {self.message}"


def _is_int(v):
    if isinstance(v, bool):
        return False
    if isinstance(v, int):
        return True
    if isinstance(v, float) and v.is_integer():
        return True
    if isinstance(v, str):
        try:
            int(v.strip())
            return True
        except ValueError:
            return False
    return False


def _as_int(v):
    return int(v) if not isinstance(v, str) else int(v.strip())


def _is_bool(v):
    if isinstance(v, bool):
        return True
    return isinstance(v, str) and v.strip().lower() in ("true", "false")


class _Collect:
    def __init__(self, ds):
        self.ds = ds
        self.items = []

    def add(self, code, gravite, message, onglet="", index=None, colonne="", id_="", bloque=None):
        ligne = self.ds.row_number(onglet, index) if (onglet and index is not None) else None
        if bloque is None:
            bloque = gravite == "erreur" and colonne in USED_COLUMNS.get(onglet, set())
        self.items.append(Probleme(code, gravite, message, onglet, ligne, colonne, id_, bloque))


def controler(ds):
    """Renvoie la liste des Probleme trouvés dans le Dataset."""
    c = _Collect(ds)
    _structure(ds, c)
    _valeurs(ds, c)
    _cles(ds, c)
    _positions(ds, c)
    _meta(ds, c)
    _coherence(ds, c)
    return c.items


def peut_traduire(problemes):
    return not any(p.bloque for p in problemes)


# ---------------------------------------------------------------- structure
def _structure(ds, c):
    if not any(ds.has(name) for name in SHEETS if name != "meta"):
        trouves = ", ".join(ds.unknown_sheets) or "aucun"
        c.add("E00", "erreur",
              "ce fichier n'est pas un export UserShaker : aucun des onglets attendus (use_cases, steps, "
              f"personas, components, user_needs...) n'a été trouvé. Onglets présents : {trouves}.",
              bloque=True)
        return
    for name in REQUIRED_FOR_TRANSLATION:
        if not ds.has(name):
            c.add("E01", "erreur", f"onglet « {name} » absent : il est nécessaire au modèle SysML.",
                  onglet=name, bloque=True)
    for name in SHEETS:
        if ds.has(name):
            found = set(ds.columns.get(name, []))
            for colname, spec in SHEETS[name].items():
                if colname not in found and ds.get(name):
                    c.add("E02", "erreur", f"colonne « {colname} » absente.", onglet=name,
                          colonne=colname,
                          bloque=colname in USED_COLUMNS.get(name, set()))
    for name in ds.unknown_sheets:
        c.add("A01", "avertissement", f"onglet « {name} » inconnu du schéma : ignoré.", onglet=name)


# ---------------------------------------------------------------- valeurs
def _valeurs(ds, c):
    for name, cols in SHEETS.items():
        pk = PRIMARY_KEY.get(name)
        for i, r in enumerate(ds.get(name)):
            rid = r.get(pk) if pk else ""
            for colname, spec in cols.items():
                if colname not in r:
                    continue  # déjà signalé (colonne absente)
                v = r.get(colname)
                if v is None:
                    if spec["required"]:
                        c.add("E03", "erreur", "valeur obligatoire vide.", name, i, colname, rid or "")
                    continue
                t = spec["type"]
                if t == "int" and not _is_int(v):
                    c.add("E04", "erreur", f"« {v} » n'est pas un nombre entier.", name, i, colname, rid or "")
                elif t == "bool" and not _is_bool(v):
                    c.add("E04", "erreur", f"« {v} » n'est pas vrai/faux.", name, i, colname, rid or "")
                elif t == "enum" and str(v) not in spec["values"]:
                    c.add("E05", "erreur",
                          f"valeur « {v} » non autorisée (attendu : {', '.join(spec['values'])}).",
                          name, i, colname, rid or "")
                elif (t == "id" or colname == "name") and isinstance(v, str) and v != v.strip():
                    c.add("A02", "avertissement", "espaces en début ou fin de valeur.",
                          name, i, colname, rid or "")
            # score d'émotion
            if name == "persona_step_feedback" and _is_int(r.get("emotion_score")):
                s = _as_int(r["emotion_score"])
                if not EMOTION_MIN <= s <= EMOTION_MAX:
                    c.add("E06", "erreur", f"score d'émotion {s} hors de l'échelle -5…+5.",
                          name, i, "emotion_score", rid or "")


# ---------------------------------------------------------------- clés
def _ids(ds, sheet):
    pk = PRIMARY_KEY[sheet]
    return {r.get(pk) for r in ds.get(sheet) if r.get(pk) is not None}


def _cles(ds, c):
    # ids uniques
    for name, pk in PRIMARY_KEY.items():
        cnt = Counter(r.get(pk) for r in ds.get(name) if r.get(pk) is not None)
        for i, r in enumerate(ds.get(name)):
            v = r.get(pk)
            if v is not None and cnt[v] > 1:
                c.add("E07", "erreur", f"id « {v} » présent {cnt[v]} fois dans l'onglet.",
                      name, i, pk, v)
    # clés étrangères
    for name, cols in SHEETS.items():
        pk = PRIMARY_KEY.get(name)
        for colname, spec in cols.items():
            target = spec["fk"]
            if not target:
                continue
            if not ds.has(target):
                if ds.get(name) and any(r.get(colname) for r in ds.get(name)):
                    c.add("A03", "avertissement",
                          f"la colonne « {colname} » pointe vers l'onglet « {target} », absent du fichier : "
                          "liens non vérifiés.", name, colonne=colname)
                continue
            known = _ids(ds, target)
            for i, r in enumerate(ds.get(name)):
                v = r.get(colname)
                if v is not None and v not in known:
                    c.add("E08", "erreur", f"« {v} » ne correspond à aucune ligne de l'onglet « {target} ».",
                          name, i, colname, (r.get(pk) if pk else "") or "")
    # doublons dans les onglets de liaison
    for name, keys in (("use_case_personas", ("use_case_id", "persona_id")),
                       ("use_case_components", ("use_case_id", "component_id")),
                       ("step_user_needs", ("step_id", "user_need_id")),
                       ("step_unused_components", ("step_id", "component_id"))):
        seen = Counter(tuple(r.get(k) for k in keys) for r in ds.get(name))
        done = set()
        for i, r in enumerate(ds.get(name)):
            key = tuple(r.get(k) for k in keys)
            if seen[key] > 1 and key not in done:
                done.add(key)
                c.add("A04", "avertissement", f"lien {key} présent {seen[key]} fois (doublon).", name, i)


# ---------------------------------------------------------------- positions
def _positions(ds, c):
    for name, (poscol, parents) in POSITION_GROUPS.items():
        groups = defaultdict(list)
        for i, r in enumerate(ds.get(name)):
            if _is_int(r.get(poscol)):
                groups[tuple(r.get(p) for p in parents)].append((_as_int(r[poscol]), i))
        for key, lst in groups.items():
            vals = sorted(v for v, _ in lst)
            if vals != list(range(1, len(vals) + 1)):
                where = f" (parent {', '.join(str(k) for k in key)})" if key else ""
                c.add("A05", "avertissement",
                      f"les valeurs de « {poscol} » ne vont pas de 1 à {len(vals)} sans trou ni doublon"
                      f"{where} : trouvé {vals}.", name, lst[0][1], poscol,
                      bloque=False)


# ---------------------------------------------------------------- meta
def _meta(ds, c):
    if not ds.has("meta"):
        c.add("A06", "avertissement", "onglet « meta » absent : nom du projet et décomptes inconnus.",
              onglet="meta")
        return
    m = ds.meta()
    if str(m.get("schema_version")) != SCHEMA_VERSION:
        c.add("A07", "avertissement",
              f"version de schéma « {m.get('schema_version')} », le traducteur suit la {SCHEMA_VERSION}.",
              onglet="meta")
    if not m.get("project_name"):
        c.add("A06", "avertissement", "project_name absent : le paquet SysML s'appellera « UserShakerProject ».",
              onglet="meta")
    for name in SHEETS:
        key = f"count_{name}"
        if key in m and ds.has(name) and _is_int(m[key]) and _as_int(m[key]) != len(ds.get(name)):
            c.add("A08", "avertissement",
                  f"meta annonce {m[key]} lignes, le fichier en contient {len(ds.get(name))}.", onglet=name)


# ---------------------------------------------------------------- cohérence
def _coherence(ds, c):
    state_comp = {r.get("state_id"): r.get("component_id") for r in ds.get("component_states")}
    group_uc = {r.get("group_id"): r.get("use_case_id") for r in ds.get("step_groups")}
    step_uc = {r.get("step_id"): r.get("use_case_id") for r in ds.get("steps")}
    names = {}
    for sheet in ("components", "component_states"):
        pk = PRIMARY_KEY[sheet]
        names.update({r.get(pk): r.get("name") for r in ds.get(sheet)})

    # un état doit appartenir au composant observé
    for sheet in ("step_triggers", "step_component_states"):
        pk = PRIMARY_KEY.get(sheet)
        for i, r in enumerate(ds.get(sheet)):
            sid, cid = r.get("state_id"), r.get("component_id")
            if sid in state_comp and cid is not None and state_comp[sid] != cid:
                c.add("E09", "erreur",
                      f"l'état « {names.get(sid, sid)} » n'appartient pas au composant « {names.get(cid, cid)} ».",
                      sheet, i, "state_id", (r.get(pk) if pk else "") or "",
                      bloque=sheet == "step_triggers")

    # un groupe doit être dans le même cas d'usage que l'étape
    for i, r in enumerate(ds.get("steps")):
        g = r.get("group_id")
        if g in group_uc and group_uc[g] != r.get("use_case_id"):
            c.add("E10", "erreur", "le groupe de l'étape appartient à un autre cas d'usage.",
                  "steps", i, "group_id", r.get("step_id") or "")

    # 1re ligne de déclencheur = trigger, les suivantes = condition (readme)
    for i, r in enumerate(ds.get("step_triggers")):
        if not _is_int(r.get("position")) or r.get("kind") not in ("trigger", "condition"):
            continue
        expected = "trigger" if _as_int(r["position"]) == 1 else "condition"
        if r["kind"] != expected:
            c.add("A09", "avertissement",
                  f"kind « {r['kind']} » en position {r['position']} : le readme attend « {expected} ».",
                  "step_triggers", i, "kind", r.get("trigger_id") or "")

    # parent de composant : pas lui-même, pas de boucle
    parent = {r.get("component_id"): r.get("parent_component_id") for r in ds.get("components")}
    for i, r in enumerate(ds.get("components")):
        cur, seen = r.get("component_id"), set()
        while cur is not None and parent.get(cur) is not None:
            if cur in seen:
                c.add("E11", "erreur", "boucle dans les composants parents.", "components", i,
                      "parent_component_id", r.get("component_id") or "")
                break
            seen.add(cur)
            cur = parent.get(cur)

    # --- complétude (avertissements utiles à l'équipe UX) ---
    served = {r.get("user_need_id") for r in ds.get("step_user_needs")}
    for i, r in enumerate(ds.get("user_needs")):
        if r.get("user_need_id") not in served:
            c.add("A10", "avertissement", f"le besoin « {r.get('name')} » n'est servi par aucune étape.",
                  "user_needs", i, "", r.get("user_need_id") or "")

    steps_with_need = {r.get("step_id") for r in ds.get("step_user_needs")}
    steps_with_trigger = {r.get("step_id") for r in ds.get("step_triggers")}
    for i, r in enumerate(ds.get("steps")):
        if r.get("step_id") not in steps_with_need:
            c.add("A11", "avertissement", f"l'étape « {r.get('name')} » ne sert aucun besoin utilisateur.",
                  "steps", i, "", r.get("step_id") or "")
        if ds.has("step_triggers") and r.get("step_id") not in steps_with_trigger:
            c.add("A12", "avertissement", f"l'étape « {r.get('name')} » n'a pas de déclencheur structuré.",
                  "steps", i, "", r.get("step_id") or "")

    uc_steps = Counter(r.get("use_case_id") for r in ds.get("steps"))
    uc_pers = Counter(r.get("use_case_id") for r in ds.get("use_case_personas"))
    for i, r in enumerate(ds.get("use_cases")):
        u = r.get("use_case_id")
        if not uc_steps[u]:
            c.add("A13", "avertissement", f"le cas d'usage « {r.get('name')} » n'a aucune étape.",
                  "use_cases", i, "", u or "")
        if ds.has("use_case_personas") and not uc_pers[u]:
            c.add("A14", "avertissement", f"le cas d'usage « {r.get('name')} » n'a aucun persona.",
                  "use_cases", i, "", u or "")

    used_personas = {r.get("persona_id") for r in ds.get("use_case_personas")}
    for i, r in enumerate(ds.get("personas")):
        if ds.has("use_case_personas") and r.get("persona_id") not in used_personas:
            c.add("A15", "avertissement", f"le persona « {r.get('name')} » ne participe à aucun cas d'usage.",
                  "personas", i, "", r.get("persona_id") or "")

    if ds.has("use_case_components"):
        used_comps = {r.get("component_id") for r in ds.get("use_case_components")}
        for i, r in enumerate(ds.get("components")):
            if r.get("component_id") not in used_comps:
                c.add("A16", "avertissement",
                      f"le composant « {r.get('name')} » n'apparaît dans aucun cas d'usage.",
                      "components", i, "", r.get("component_id") or "")

    # un ressenti par étape × persona du cas d'usage (readme)
    if ds.has("persona_step_feedback") and ds.has("use_case_personas"):
        uc_p = defaultdict(set)
        for r in ds.get("use_case_personas"):
            uc_p[r.get("use_case_id")].add(r.get("persona_id"))
        have = {(r.get("step_id"), r.get("persona_id")) for r in ds.get("persona_step_feedback")}
        pname = {r.get("persona_id"): r.get("name") for r in ds.get("personas")}
        for i, r in enumerate(ds.get("steps")):
            for p in sorted(uc_p.get(r.get("use_case_id"), ()), key=str):
                if (r.get("step_id"), p) not in have:
                    c.add("A17", "avertissement",
                          f"pas de ressenti pour « {pname.get(p, p)} » à l'étape « {r.get('name')} ».",
                          "steps", i, "", r.get("step_id") or "")
        for i, r in enumerate(ds.get("persona_step_feedback")):
            u = step_uc.get(r.get("step_id"))
            if u is not None and r.get("persona_id") not in uc_p.get(u, set()):
                c.add("A18", "avertissement", "ressenti d'un persona qui ne fait pas partie du cas d'usage.",
                      "persona_step_feedback", i, "persona_id", r.get("feedback_id") or "")

    # noms en double : le traducteur les distingue (suffixe 2, 3...) mais c'est à signaler
    def dup(sheet, scope_col, label):
        cnt = Counter((r.get(scope_col) if scope_col else None, str(r.get("name")).strip().lower())
                      for r in ds.get(sheet) if r.get("name"))
        done = set()
        for i, r in enumerate(ds.get(sheet)):
            k = (r.get(scope_col) if scope_col else None, str(r.get("name")).strip().lower())
            if r.get("name") and cnt[k] > 1 and k not in done:
                done.add(k)
                c.add("A19", "avertissement", f"{cnt[k]} {label} portent le nom « {r.get('name')} ».",
                      sheet, i, "name", r.get(PRIMARY_KEY[sheet]) or "")
    dup("use_cases", None, "cas d'usage")
    dup("steps", "use_case_id", "étapes du même cas d'usage")
    dup("personas", None, "personas")
    dup("components", None, "composants")
    dup("user_needs", None, "besoins")
