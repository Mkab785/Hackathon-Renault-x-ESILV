"""
Lecture d'un modèle SysML v2 pour l'afficher sur le site (onglet « Modèle lu dans le SysML »).

Ne lit QUE le texte des codes .sysml : ni l'Excel, ni le traducteur. Chaque code est analysé
par relire_code (le même lecteur que la vérification Excel <-> SysML), puis les codes sont
assemblés en un seul graphe :

    noeuds  personas, composants, états des composants, besoins, cas d'usage, étapes
    liens   acteur        persona   -> cas d'usage   (actor ... : Personas::Persona)
            contient      cas       -> étape         (action dans le use case def)
            suit          étape     -> étape         (first ... then ; ou « suite de ... » entre deux parties)
            satisfait     étape     -> besoin        (satisfy Needs::...)
            etat_de       composant -> état          (attribute states = "Off [id] ; ...")
            met_dans      étape     -> état          (attribute gridXxx = "1: Off ; 2: A > B ; ...")
            declenche     état      -> étape         (attribute triggerEvent = "Composant is état")
            condition     état      -> étape         (attribute condition = "Composant is état")
            ressent       persona   -> étape         (attribute feedback = "nom +2 | action | insight [id] ; ...")

Chaque noeud et chaque lien garde le fichier et la ligne du code d'où il vient, et
l'identifiant UserShaker quand le code le donne (doc /* id : nom */ ou [id]).
Une référence introuvable n'est jamais inventée : elle part dans « avertissements ».

Format lu : l'écriture compacte du traducteur (celle du site et de traduire.bat), un code
par cas d'usage ou par partie de cas d'usage, ou le CODE ENTIER (tous les cas d'usage dans un
seul fichier). Les codes d'un même cas d'usage coupé en parties sont réunis (même identifiant
de cas d'usage). Le nombre de cas d'usage et de fichiers est libre.
"""
import re
from collections import OrderedDict

from .relecture_complete import relire_code
from .rendu_cas_usage import decouper_code_entier

RE_ETAT = re.compile(r"^(.*?) \[(\S+)\](?: \((.*)\))?$")
RE_GRILLE = re.compile(r"^(\d+): (.*)$")
RE_GROUPE = re.compile(r"^(.*) \[(\S+)\]: (.+)$")
RE_RESSENTI = re.compile(r"^(\w+) (\S+) \| (.*?) \| (.*) \[(\S+)\]$")
RE_PARTIE = re.compile(r"partie (\d+)/(\d+)")
RE_SUITE = re.compile(r"suite de (\w+) \(partie \d+\)")
RE_POSITION = re.compile(r"^step(\d+)")


def _items(valeur):
    return [x.strip() for x in re.split(r" ; ", valeur or "") if x.strip()]


def _plages(texte):
    """« 1-2, 4 » -> [1, 2, 4]."""
    out = []
    for morceau in texte.split(","):
        morceau = morceau.strip()
        if re.fullmatch(r"\d+-\d+", morceau):
            a, b = (int(x) for x in morceau.split("-"))
            out += list(range(a, b + 1))
        elif morceau.isdigit():
            out.append(int(morceau))
    return out


def _score(s):
    try:
        return int(s)
    except ValueError:
        return None


class _Graphe:
    def __init__(self):
        self.noeuds = OrderedDict()
        self.liens = []
        self.avertissements = []
        self._vus = set()

    def noeud(self, cle, type_, nom, libelle, uid, fichier, ligne, **autres):
        n = self.noeuds.get(cle)
        if n is None:
            n = {"cle": cle, "type": type_, "nom": nom, "libelle": libelle or nom, "uid": uid,
                 "attrs": {}, "sources": []}
            self.noeuds[cle] = n
        n.update({k: v for k, v in autres.items() if k not in n})
        if fichier and {"fichier": fichier, "ligne": ligne} not in n["sources"]:
            n["sources"].append({"fichier": fichier, "ligne": ligne})
        return n

    def lien(self, de, vers, type_, fichier, ligne, **autres):
        cle = (de, vers, type_, autres.get("texte"))
        if cle in self._vus:
            return
        self._vus.add(cle)
        self.liens.append({"de": de, "vers": vers, "type": type_, "fichier": fichier, "ligne": ligne, **autres})

    def avertir(self, fichier, ligne, texte):
        self.avertissements.append({"fichier": fichier, "ligne": ligne, "texte": texte})


def lire_modele(codes):
    """codes : [(nom_du_fichier, texte_sysml)]. Renvoie le graphe (dict sérialisable en JSON)."""
    g = _Graphe()
    lus, fichiers = [], []
    for fichier, texte in codes:
        morceaux = decouper_code_entier(texte)        # code entier : un texte par cas d'usage, mêmes lignes
        for _, morceau in (morceaux or [(None, texte)]):
            c = relire_code(morceau)
            m = RE_PARTIE.search(c["entete"] or "")
            lus.append({"fichier": fichier, "c": c, "partie": int(m.group(1)) if m else 1,
                        "parties": int(m.group(2)) if m else 1, "texte": texte})
        c0 = lus[-1]["c"] if lus else {"package": None, "cas": None}
        fichiers.append({"nom": fichier, "package": c0["package"], "code_entier": bool(morceaux),
                         "cas_usage": (f"{len(morceaux)} cas d'usage" if morceaux else
                                       (c0["cas"] or {}).get("nom_doc") or (c0["cas"] or {}).get("nom")),
                         "partie": lus[-1]["partie"] if lus else 1, "parties": lus[-1]["parties"] if lus else 1,
                         "lignes": texte.count("\n") + 1, "caracteres": len(texte)})
    for f in fichiers:
        if f["package"] is None:
            g.avertir(f["nom"], None, "aucun package SysML reconnu dans ce fichier : il est ignoré")

    # noms SysML -> clés, par fichier puis pour tout le modèle (repli si absent du fichier)
    noms = {"persona": {}, "composant": {}, "besoin": {}}
    noms_globaux = {"persona": {}, "composant": {}, "besoin": {}}

    def retenir(type_, fichier, nom, cle):
        noms[type_][(fichier, nom)] = cle
        noms_globaux[type_].setdefault(nom, set()).add(cle)

    def trouver(type_, fichier, nom, ligne, quoi):
        cle = noms[type_].get((fichier, nom))
        if cle:
            return cle
        candidats = noms_globaux[type_].get(nom, set())
        if len(candidats) == 1:
            return next(iter(candidats))
        g.avertir(fichier, ligne, f"{quoi} « {nom} » introuvable dans le modèle"
                  + (" (nom ambigu)" if candidats else ""))
        return None

    def cle_de(type_, e):
        return f"{type_}:{e['id'] or e['nom']}"

    # 1. personas, composants (et leurs états), besoins
    composants_par_libelle = {}
    for l in lus:
        f, c = l["fichier"], l["c"]
        for e in c["personas"].values():
            cle = cle_de("persona", e)
            n = g.noeud(cle, "persona", e["nom"], e["nom_doc"], e["id"], f, e["ligne"])
            n["attrs"].update({k: v for k, v in e["attrs"].items() if k not in n["attrs"]})
            retenir("persona", f, e["nom"], cle)
        for e in c["composants"].values():
            cle = cle_de("composant", e)
            n = g.noeud(cle, "composant", e["nom"], e["nom_doc"], e["id"], f, e["ligne"], etats=[])
            for k, v in e["attrs"].items():
                if k != "states":
                    n["attrs"].setdefault(k, v)
            retenir("composant", f, e["nom"], cle)
            composants_par_libelle[n["libelle"]] = cle
            if "states" in e["attrs"] and not n["etats"]:
                ligne = e["lignes"].get("states")
                for item in _items(e["attrs"]["states"]):
                    m = RE_ETAT.match(item)
                    if not m:
                        g.avertir(f, ligne, f"état illisible dans {e['nom']} : « {item} »")
                        continue
                    ecle = f"etat:{m.group(2)}"
                    g.noeud(ecle, "etat", m.group(1), m.group(1), m.group(2), f, ligne,
                            composant=cle, description=m.group(3))
                    n["etats"].append(ecle)
                    g.lien(cle, ecle, "etat_de", f, ligne)
        for e in c["besoins"].values():
            cle = cle_de("besoin", e)
            n = g.noeud(cle, "besoin", e["nom"], e["nom_doc"], e["id"], f, e["ligne"])
            n["attrs"].update({k: v for k, v in e["attrs"].items() if k not in n["attrs"]})
            retenir("besoin", f, e["nom"], cle)

    def etat_de(comp_cle, nom_etat):
        for ecle in g.noeuds[comp_cle].get("etats", []):
            if g.noeuds[ecle]["nom"] == nom_etat:
                return ecle
        return None

    # 2. cas d'usage : parties réunies par identifiant, dans l'ordre des parties
    cas = OrderedDict()
    for l in lus:
        uc = l["c"]["cas"]
        if uc:
            cas.setdefault(uc["id"] or uc["nom"], []).append(l)
    cas_usage = []
    for uid, parts in cas.items():
        parts.sort(key=lambda l: l["partie"])
        uc0 = parts[0]["c"]["cas"]
        ccle = f"cas:{uid}"
        n_cas = g.noeud(ccle, "cas", uc0["nom"], uc0["nom_doc"], uc0["id"], parts[0]["fichier"], uc0["ligne"])
        etapes, groupes, grille = [], OrderedDict(), OrderedDict()
        par_position = {}
        acteurs = []
        for l in parts:
            f, uc = l["fichier"], l["c"]["cas"]
            g.noeud(ccle, "cas", uc["nom"], uc["nom_doc"], uc["id"], f, uc["ligne"])
            for k, v in uc["attrs"].items():
                if not k.startswith("grid") and k != "stepGroups":
                    n_cas["attrs"].setdefault(k, v)
            for nom_p, ligne in uc["acteurs"]:
                pcle = trouver("persona", f, nom_p, ligne, "acteur")
                if pcle:
                    g.lien(pcle, ccle, "acteur", f, ligne)
                    if pcle not in acteurs:
                        acteurs.append(pcle)
            premiere = None
            for rang, a in enumerate(uc["actions"].values(), start=len(etapes) + 1):
                ecle = f"etape:{a['id'] or uc['nom'] + '.' + a['nom']}"
                m = RE_POSITION.match(a["nom"])
                pos = int(m.group(1)) if m else rang
                n = g.noeud(ecle, "etape", a["nom"], a["nom_doc"], a["id"], f, a["ligne"],
                            cas=ccle, position=pos, declencheurs=[], ressentis=[], inutilises=[], groupe=None)
                n["attrs"].update({k: v for k, v in a["attrs"].items()
                                   if k not in ("feedback", "unusedComponents")})
                etapes.append(ecle)
                par_position[pos] = ecle
                premiere = premiere or ecle
                g.lien(ccle, ecle, "contient", f, a["ligne"])
                for nom_b, ligne in a["satisfy"]:
                    bcle = trouver("besoin", f, nom_b, ligne, "besoin satisfait")
                    if bcle:
                        g.lien(ecle, bcle, "satisfait", f, ligne)
                for attr, texte, did, ligne in a["declencheurs"]:
                    genre = "declenche" if attr.startswith("triggerEvent") else "condition"
                    d = {"type": genre, "texte": texte, "uid": did, "ligne": ligne, "composant": None, "etat": None}
                    for lib in sorted(composants_par_libelle, key=len, reverse=True):
                        if texte.startswith(lib + " "):
                            comp = composants_par_libelle[lib]
                            reste = texte[len(lib) + 1:]
                            for ecl in g.noeuds[comp]["etats"]:
                                nom_e = g.noeuds[ecl]["nom"]
                                if reste == nom_e or reste.endswith(" " + nom_e):
                                    d.update(composant=comp, etat=ecl, operateur=reste[:-len(nom_e)].strip() or None)
                                    break
                            break
                    n["declencheurs"].append(d)
                    if d["etat"]:
                        g.lien(d["etat"], ecle, genre, f, ligne, texte=texte)
                    else:
                        g.avertir(f, ligne, f"{a['nom']} : composant ou état non retrouvé dans « {texte} »")
                ligne_inutil = a["lignes"].get("unusedComponents")
                for nom_c in _items(a["attrs"].get("unusedComponents")):
                    ccomp = trouver("composant", f, nom_c, ligne_inutil, "composant non utilisé")
                    if ccomp:
                        n["inutilises"].append(ccomp)
                ligne_fb = a["lignes"].get("feedback")
                for item in _items(a["attrs"].get("feedback")):
                    m = RE_RESSENTI.match(item)
                    if not m:
                        g.avertir(f, ligne_fb, f"ressenti illisible dans {a['nom']} : « {item} »")
                        continue
                    pcle = trouver("persona", f, m.group(1), ligne_fb, "persona du ressenti")
                    r = {"persona": pcle, "score": _score(m.group(2)), "absent": m.group(2) == "absent",
                         "action": m.group(3) or None, "insight": m.group(4) or None, "uid": m.group(5)}
                    n["ressentis"].append(r)
                    if pcle:
                        g.lien(pcle, ecle, "ressent", f, ligne_fb, texte=m.group(2))
            for a_nom, b_nom, ligne in uc["ordre"]:
                ea = next((e for e in etapes if g.noeuds[e]["nom"] == a_nom and g.noeuds[e]["cas"] == ccle), None)
                eb = next((e for e in etapes if g.noeuds[e]["nom"] == b_nom and g.noeuds[e]["cas"] == ccle), None)
                if ea and eb:
                    g.lien(ea, eb, "suit", f, ligne)
                else:
                    g.avertir(f, ligne, f"enchaînement {a_nom} -> {b_nom} : étape introuvable")
            m = RE_SUITE.search(l["c"]["entete"] or "")
            if m and premiere:
                avant = next((e for e in etapes if g.noeuds[e]["nom"] == m.group(1)), None)
                if avant:
                    g.lien(avant, premiere, "suit", f, l["c"]["ligne_package"] + 1, entre_parties=True)
                else:
                    g.avertir(f, l["c"]["ligne_package"] + 1, f"étape précédente {m.group(1)} introuvable")
            # groupes d'étapes et grille composant x étape (positions = numéros d'étapes du cas d'usage)
            for item in _items(uc["attrs"].get("stepGroups")):
                m = RE_GROUPE.match(item)
                if m:
                    gr = groupes.setdefault(m.group(2), {"nom": m.group(1), "uid": m.group(2), "positions": []})
                    gr["positions"] += [p for p in _plages(m.group(3)) if p not in gr["positions"]]
            for attr, valeur in uc["attrs"].items():
                if not attr.startswith("grid"):
                    continue
                ligne = uc["lignes"].get(attr)
                comp = trouver("composant", f, attr[4:], ligne, "composant de la grille")
                if not comp:
                    continue
                for item in _items(valeur):
                    m = RE_GRILLE.match(item)
                    if not m:
                        g.avertir(f, ligne, f"case de grille illisible : « {item} »")
                        continue
                    grille.setdefault(comp, {})[int(m.group(1))] = {"texte": m.group(2), "ligne": ligne, "fichier": f}
        # résolution de la grille : position -> étape, texte -> états
        grille_res = OrderedDict()
        for comp, cases in grille.items():
            for pos, case in sorted(cases.items()):
                ecle = par_position.get(pos)
                if not ecle:
                    g.avertir(case["fichier"], case["ligne"], f"grille : pas d'étape n°{pos} dans {uc0['nom']}")
                    continue
                suite = [x.strip() for x in case["texte"].split(" > ")]
                etats = []
                for k, nom_e in enumerate(suite, start=1):
                    ecl = etat_de(comp, nom_e)
                    etats.append(ecl)
                    if ecl:
                        g.lien(ecle, ecl, "met_dans", case["fichier"], case["ligne"],
                               texte=f"{k}/{len(suite)}" if len(suite) > 1 else None)
                    else:
                        g.avertir(case["fichier"], case["ligne"],
                                  f"grille : état « {nom_e} » inconnu pour {g.noeuds[comp]['nom']}")
                grille_res.setdefault(comp, {})[ecle] = {"texte": case["texte"], "etats": etats}
        for gr in groupes.values():
            gr["etapes"] = [par_position[p] for p in gr["positions"] if p in par_position]
            for e in gr["etapes"]:
                g.noeuds[e]["groupe"] = gr["nom"]
        etapes.sort(key=lambda e: g.noeuds[e]["position"])
        cas_usage.append({"cle": ccle, "etapes": etapes, "acteurs": acteurs,
                          "groupes": [{k: v for k, v in gr.items() if k != "positions"} for gr in groupes.values()],
                          "grille": grille_res, "fichiers": [l["fichier"] for l in parts]})

    compteurs = OrderedDict()
    for type_, titre in (("persona", "personas"), ("composant", "composants"), ("etat", "états"),
                         ("besoin", "besoins"), ("cas", "cas d'usage"), ("etape", "étapes")):
        compteurs[titre] = sum(1 for n in g.noeuds.values() if n["type"] == type_)
    compteurs["enchaînements"] = sum(1 for l in g.liens if l["type"] == "suit")
    compteurs["satisfy"] = sum(1 for l in g.liens if l["type"] == "satisfait")
    return {"fichiers": fichiers, "noeuds": list(g.noeuds.values()), "liens": g.liens,
            "cas_usage": cas_usage, "compteurs": compteurs, "avertissements": g.avertissements}
