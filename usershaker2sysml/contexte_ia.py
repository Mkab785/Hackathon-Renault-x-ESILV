"""
Texte de contexte envoyé à l'assistant IA (Claude, une IA avec clé API, ou un chat externe
par copier-coller).

Il contient UNIQUEMENT des données lues dans l'export UserShaker, les résultats des
contrôles / de la vérification, et les codes SysML produits par le traducteur.

Inclus : projet, personas, composants (rôle, catégorie), besoins (et combien d'étapes
les servent), cas d'usage (description courte, acteurs), étapes dans l'ordre avec
ligne Excel, déclencheurs structurés, déclencheur en texte libre, besoins servis,
scores d'émotion des personas ; problèmes détectés ; résultat de la vérification ;
ce qui n'est pas traduit en SysML ; les codes SysML produits (un par cas d'usage, traduction
complète), lignes numérotées comme dans les fichiers .sysml et l'onglet Export de l'interface.
Le résumé Excel ne reprend pas les textes longs ni la grille : ils sont dans les codes.
"""
import re
import unicodedata
from collections import defaultdict



def _pos(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 10 ** 6

REGLES = """Tu es l'assistant d'un ingénieur système. Il prépare l'import de données UX (outil UserShaker) dans un modèle SysML v2 pour CATIA Magic. Tu reçois UNIQUEMENT les codes SysML v2 produits par le traducteur (un code par cas d'usage, lignes numérotées) et le résultat des contrôles automatiques des données. Tu ne reçois pas l'Excel.

Règles :
- Pour toute question sur le modèle, base-toi sur les codes SysML fournis : ce sont eux qui sont importés dans CATIA. Cite le code et la ligne (ex. [UC4 ligne 42]).
- Dans les codes : la grille composant × étape est dans les attributs grid… du cas d'usage (« 3: Stowing > Stowed » = à l'étape 3, l'état passe à Stowing puis Stowed), les ressentis dans l'attribut feedback de chaque étape (persona, score, action, insight), les états de chaque composant dans son attribut states, les groupes d'étapes dans stepGroups.
- Chaque code est autonome : une persona, un composant ou un besoin est déclaré dans chaque code qui l'utilise. Les identifiants dans doc /* */ ou entre crochets [ ] sont les identifiants UserShaker.
- Réponds en français et va droit au but : la réponse d'abord, en liste ou petit tableau, sans introduction, sans répéter la question ni les données, sans conclusion. Détaille seulement si on te le demande.
- Appuie-toi uniquement sur les codes fournis. Si une information n'y figure pas, dis-le explicitement. N'invente aucune étape, aucun besoin, aucun composant, aucune valeur.
- Quand tu cites un élément, donne son nom exact, le code et la ligne.
- Sépare clairement ce qui est constaté dans les codes de ce qui est une suggestion de ta part.
- Tu ne modifies rien : toute correction est une proposition que l'ingénieur valide ou refuse, puis que l'équipe UX applique dans UserShaker."""


def _court(t, n=220):
    t = " ".join(str(t or "").split())
    return t if len(t) <= n else t[: n - 1] + "…"


def contexte(ds, res):
    """Contexte COMPLET (codes SysML entiers, environ 34 000 tokens) : « Copier pour un chat externe ».
    Pas de résumé de l'Excel : sommaire des codes, contrôles, codes."""
    L = _sommaire(res)
    _traduction(res, L.append)
    return "\n".join(L)


def _sommaire(res):
    """Ce que l'IA reçoit en tête : la liste des codes SysML (pas de résumé de l'Excel) et les contrôles."""
    L = [f"PROJET : {getattr(res, 'projet', '') or '?'}"]
    codes = getattr(res, "codes", None) or []
    if codes:
        L.append(f"CODES SYSML ({len(codes)}) :")
        for c in codes:
            L.append(f"- {_etiquette(c)} : fichier {c['fichier']}, cas d'usage « {c['cas_usage']} »"
                     + (f", partie {c['partie']}/{c['parties']}" if c["parties"] > 1 else "")
                     + f", {c['etapes']} étape(s), {c['texte'].count(chr(10))} lignes")
    pbs = res.problemes
    L.append("")
    L.append(f"CONTRÔLES AUTOMATIQUES DES DONNÉES : {len(pbs)} problème(s)")
    for p in pbs[:40]:
        ou = ", ".join(x for x in (p.onglet, f"ligne {p.ligne}" if p.ligne else "", p.colonne) if x)
        L.append(f"- [{p.code} {'bloquant' if p.bloque else p.gravite}] {ou} : {p.message}")
    if len(pbs) > 40:
        L.append(f"- … et {len(pbs) - 40} autre(s)")
    return L


def _entete_traduction(res, w):
    codes = getattr(res, "codes", None)
    ok = sum(1 for v in res.verification if v["ok"])
    w(f"TRADUCTION SYSML : {len(codes)} code(s), un par cas d'usage, vérifiés par relecture : "
      f"{ok}/{len(res.verification)} éléments conformes.")
    w("Non traduit (reste dans l'Excel) : liens des images des étapes, couleurs, champs de bibliothèque, infos d'export de l'onglet meta.")


def _etiquette(c):
    return f"UC{c['numero']}" + (f"-partie{c['partie']}" if c["parties"] > 1 else "")


def _traduction(res, w):
    codes = getattr(res, "codes", None)
    if codes:
        _entete_traduction(res, w)
        for c in codes:
            lab = _etiquette(c)
            lignes = c["texte"].rstrip("\n").split("\n")
            w("")
            w(f"=== CODE {lab} : fichier {c['fichier']}, cas d'usage {c['numero']} « {c['cas_usage']} »"
              + (f", partie {c['partie']}/{c['parties']}" if c["parties"] > 1 else "")
              + f" ({len(lignes)} lignes, numéro à gauche) ===")
            for i, l in enumerate(lignes, 1):
                w(f"{i:>3}| {l}")
    elif getattr(res, "texte", None) is not None:
        ok = sum(1 for v in res.verification if v["ok"])
        w(f"TRADUCTION SYSML : produite ({res.taille} octets), vérifiée par relecture : {ok}/{len(res.verification)} éléments conformes.")
        w("Non traduit dans le SysML (limite de taille de CATIA Community) : groupes d'étapes, ressentis et "
          "émotions, états en tant qu'éléments, grille composant × étape, textes longs.")
        lignes = res.texte.rstrip("\n").split("\n")
        w("")
        w(f"TEXTE SYSML COMPLET ({len(lignes)} lignes, numéro de ligne à gauche) :")
        for i, l in enumerate(lignes, 1):
            w(f"{i:>3}| {l}")
    else:
        w("TRADUCTION SYSML : non produite (erreurs bloquantes).")


def invite_complete(ds, res, question=""):
    """Texte complet à coller dans un chat externe (Claude.ai, ChatGPT...)."""
    q = question.strip() or "(écris ta question ici)"
    return f"{REGLES}\n\n=== DONNÉES DU PROJET ===\n{contexte(ds, res)}\n=== FIN DES DONNÉES ===\n\nQUESTION : {q}\n"


# =============================== contexte CIBLÉ (assistant intégré) ===============================
# Envoyer les codes entiers coûte environ 34 000 tokens par question : trop pour une offre gratuite
# (Groq : 8 000 tokens par minute). L'assistant intégré reçoit donc le sommaire des codes, puis SEULEMENT les
# passages des codes SysML liés à la question, avec les numéros de ligne des fichiers, dans un
# budget de tokens fixé par assistant.py. Rien n'est réécrit : les lignes sont copiées telles quelles
# (une ligne très longue est coupée et marquée « [coupé] »).

# Guide du site, ajouté aux consignes de l'assistant intégré (pas au chat externe) : il peut indiquer
# où voir quelque chose et mettre un lien [[aller:section]] ou [[aller:section/vue]], transformé en bouton par la page.
GUIDE_SITE = """
- Tu aides aussi à se repérer sur le site. Sections [identifiant] :
[tableau] Tableau de bord : état de la traduction, cas d'usage, couverture, actions rapides.
[controles] Contrôles des données : erreurs et avertissements sur l'Excel (codes E.., A..).
[verif] Vérification Excel ↔ SysML : chaque élément comparé à l'Excel, critère par critère ; vues [verif/elements] et [verif/trace] (toutes les correspondances) ; filtre « écarts » ; recherche. Cliquer « UC4 ligne N » ouvre le code à cette ligne.
[apercu] Aperçu du modèle : cas d'usage, acteurs, étapes.
[modele] Modèle lu dans le SysML, graphes dessinés depuis les codes : [modele/ensemble], [modele/cas], [modele/composant], [modele/trace] ; bouton Plein écran ; clic sur un élément = fiche et extrait du code.
[matrice] Analyses : [matrice/matrice] besoins × étapes, [matrice/couverture] couverture des besoins, [matrice/emotions] parcours émotionnel, [matrice/composants] composants × étapes.
[export] Export vers CATIA : codes à copier ou télécharger (Community : un par cas d'usage ; CATIA complet : code entier), zip, traçabilité .xlsx, rapport .txt, marche à suivre dans CATIA.
[assistant] Assistant IA. [traducteur] Comment fonctionne le traducteur (code Python).
- Si on te demande où voir ou comment faire quelque chose sur le site : réponds en 1 à 3 lignes et ajoute le lien, ex. [[aller:matrice/emotions]]. N'utilise que ces identifiants.
- Pour un élément précis (composant, étape, besoin, persona, cas d'usage), ajoute son nom SysML tel qu'écrit dans les codes, pour que le site l'ouvre directement : [[aller:modele/composant/NomSysML]] (vue choisie automatiquement selon l'élément) ou [[aller:verif/elements/NomSysML]] pour sa vérification. Un lien par élément cité ; jamais de nom absent des codes."""

REGLES_EXTRAITS = REGLES + """
- Tu ne reçois que des EXTRAITS des codes SysML : les passages liés à la question, avec les numéros de ligne des fichiers (« … » = lignes non envoyées ; « passage identique dans … » = le même texte est aussi à ces lignes d'autres codes). Si l'information n'est pas dans les extraits, dis-le et invite à préciser la question (nom de l'étape, du composant, du besoin, ou le cas d'usage, ex. UC2). Ne déduis jamais le contenu des lignes non envoyées.""" + GUIDE_SITE

LONGUEUR_LIGNE = 500          # caractères au plus par ligne de code envoyée
_DEBUT = re.compile(r"^(package |part def |part |requirement |use case def |action |first |actor )")
_MOTS_VIDES = set("""les des une est que qui quoi quel quels quelle quelles pour dans avec par sur pas sont aux son ses
leur leurs plus moins tout tous toute toutes cette ces cet comment combien quand elle ils elles mais donc car
fait faire peut peuvent entre chaque autre autres aussi alors ainsi tres bien bon bonne veux voir donne donner
dit dire liste lister montre montrer explique expliquer the and for with""".split())
# mot de la question (sans accents) -> genres de passages à favoriser
_GENRES = {"besoin": ("besoin", "etape"), "requirement": ("besoin",), "need": ("besoin",), "satisf": ("besoin", "etape"),
           "couvert": ("besoin", "etape"), "composant": ("composant",), "etat": ("composant", "cas"),
           "state": ("composant",), "persona": ("persona",), "acteur": ("persona", "cas"), "etape": ("etape",),
           "step": ("etape",), "declench": ("etape",), "trigger": ("etape",), "condition": ("etape",),
           "emotion": ("etape",), "ressenti": ("etape",), "feedback": ("etape",), "insight": ("etape",),
           "grille": ("cas",), "groupe": ("cas",), "usage": ("cas",), "enchain": ("suite",), "ordre": ("suite",),
           "succession": ("suite",)}
_GENRE_DE = {"package ": "autre", "part def ": "composant", "part ": "persona", "requirement ": "besoin",
             "use case def ": "cas", "action ": "etape", "first ": "suite", "actor ": "cas"}


def _forme(mot):
    """Forme tolérante d'un mot : lettres doublées réduites, pluriel enlevé (« personnas » -> « persona »)."""
    mot = re.sub(r"(.)\1+", r"\1", mot)
    return mot[:-1] if len(mot) > 4 and mot.endswith(("s", "x")) else mot


def _proche(a, b):
    """Vrai si a et b (formes tolérantes, 5 lettres et plus) diffèrent d'au plus une lettre."""
    if abs(len(a) - len(b)) > 1 or min(len(a), len(b)) < 5:
        return False
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    return a[i + 1:] == b[i + 1:] or a[i + 1:] == b[i:] or a[i:] == b[i + 1:]


def estimer_tokens(texte):
    """Estimation PRUDENTE (on surestime) : les identifiants hexadécimaux et le code coûtent cher."""
    return int(len(texte) / 2.2) + 1


def _sans_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def _segments(codes):
    """Découpe chaque code en passages : une persona, un composant, un besoin, l'en-tête d'un cas
    d'usage, une étape, la suite des first ... then. Renvoie [{k, debut, fin, genre, texte}] (lignes 1..n)."""
    out = []
    for k, c in enumerate(codes):
        lignes = c["texte"].rstrip("\n").split("\n")
        courant = None
        for n, l in enumerate(lignes, 1):
            m = _DEBUT.match(l.strip())
            if m:
                genre = _GENRE_DE[m.group(1)]
                if not (courant and genre in ("suite",) and courant["genre"] == genre):
                    courant = {"k": k, "debut": n, "fin": n, "genre": genre}
                    out.append(courant)
            if courant:
                courant["fin"] = n
        for s in out:
            if s["k"] == k:
                s["texte"] = _sans_accents("\n".join(lignes[s["debut"] - 1:s["fin"]]))
    return out


def _formater(c, lignes, debut, fin):
    return [f"{i:>3}| " + (l if len(l) <= LONGUEUR_LIGNE else l[:LONGUEUR_LIGNE] + "…[coupé]")
            for i, l in enumerate(lignes[debut - 1:fin], debut)]


def extraits(res, question, budget):
    """Passages des codes SysML liés à la question, dans un budget de tokens (estimation prudente)."""
    codes = getattr(res, "codes", None) or []
    if not codes:
        return "TRADUCTION SYSML : non produite (erreurs bloquantes)."
    q = _sans_accents(question or "")
    brut = {m for m in re.findall(r"[a-z0-9]{3,}", q) if m not in _MOTS_VIDES}
    mots = {_forme(m) for m in brut}                    # fautes de frappe courantes et pluriels tolérés
    qf = " ".join(_forme(m) for m in re.findall(r"[a-z0-9]+", q))
    genres = {g for cle, gs in _GENRES.items() if cle in q or _forme(cle) in qf
              or any(_proche(_forme(cle), m) for m in mots) for g in gs}
    uc_vise = {int(x) for x in re.findall(r"\buc\s*-?\s*(\d+)", q)} | \
              {int(x) for x in re.findall(r"cas d.usage (?:n.?\s*)?(\d+)", q)}
    etapes_visees = {int(x) for x in re.findall(r"etape\s*(?:n.?\s*)?(\d+)", q)}
    lignes_visees = {int(x) for x in re.findall(r"ligne\s*(\d+)", q)}
    segs = _segments(codes)
    vocab = {}                                          # mot du code -> forme tolérante (pour les mots proches)
    for s in segs:
        s["formes"] = " ".join(_forme(x) for x in re.findall(r"[a-z0-9]+", s["texte"]))
        for x in set(s["formes"].split()):
            vocab.setdefault(x, x)
    proches = {m: {v for v in vocab if v != m and _proche(m, v)} for m in mots if m not in vocab}
    for s in segs:
        c = codes[s["k"]]
        score = 0
        for m in mots:
            if m in s["formes"] or any(v in s["formes"].split() for v in proches.get(m, ())):
                score += 3 if len(m) >= 5 else 1
        if s["genre"] in genres:
            score += 2
        if uc_vise:
            if c["numero"] in uc_vise:
                score += 4
                if etapes_visees and s["genre"] == "etape" and any(
                        re.search(rf"^action step0*{e}\w* \{{", s["texte"]) for e in etapes_visees):
                    score += 8
                if any(s["debut"] <= n <= s["fin"] for n in lignes_visees):
                    score += 12
            else:
                score = score // 2
        s["score"] = 0 if s["genre"] == "autre" else score       # lignes « package … » : sans intérêt seules
    lignes_de = [c["texte"].rstrip("\n").split("\n") for c in codes]
    entetes = [_entete_code(c, len(lignes_de[k])) for k, c in enumerate(codes)]
    retenus, cout, ouverts = [], 160, set()     # 160 : lignes d'en-tête de la partie traduction et note

    deja = {}                                            # un passage identique dans plusieurs codes n'est envoyé qu'une fois

    def prendre(s):
        """Ajoute le passage s'il tient dans le budget (en-tête du code et « … » compris)."""
        nonlocal cout
        cle = "\n".join(lignes_de[s["k"]][s["debut"] - 1:s["fin"]])
        if cle in deja:
            if s["k"] != deja[cle]["k"] and cout + 12 <= budget:
                deja[cle].setdefault("aussi", []).append((s["k"], s["debut"], s["fin"]))
                cout += 12                                     # la mention « passage identique dans … »
            return
        t = estimer_tokens("\n".join(_formater(codes[s["k"]], lignes_de[s["k"]], s["debut"], s["fin"]))) + 4
        if s["k"] not in ouverts:
            t += estimer_tokens(entetes[s["k"]]) + 6
        if cout + t > budget:
            return
        retenus.append(s)
        ouverts.add(s["k"])
        deja[cle] = s
        cout += t

    for s in sorted((s for s in segs if s["score"] > 0), key=lambda s: (-s["score"], s["fin"] - s["debut"])):
        prendre(s)
    note = ""
    if not retenus:                         # question générale : vue d'ensemble du modèle
        note = ("(Aucun passage ne correspond clairement à la question : voici une vue d'ensemble — personas, "
                "besoins, en-tête de chaque cas d'usage.)")
        for s in segs:
            if s["genre"] == "cas" and s["texte"].startswith("use case def"):
                prendre(dict(s, fin=min(s["fin"], s["debut"] + 4)))
        for genre in ("persona", "besoin"):
            for s in segs:
                if s["genre"] == genre:
                    prendre(s)
    L = []
    _entete_traduction(res, L.append)
    L.append(f"EXTRAITS DES CODES liés à la question ({len(retenus)} passage(s) ; « … » = lignes non envoyées). {note}".rstrip())
    for k, c in enumerate(codes):
        mien = sorted((s for s in retenus if s["k"] == k), key=lambda s: s["debut"])
        if not mien:
            continue
        L.append("")
        L.append(entetes[k])
        fin = 0
        for s in mien:
            if s["debut"] > fin + 1:
                L.append("  …")
            L += _formater(c, lignes_de[k], max(s["debut"], fin + 1), s["fin"])
            if s.get("aussi"):
                L.append("     (passage identique dans " + " ; ".join(
                    f"{_etiquette(codes[k2])} lignes {a}-{b}" for k2, a, b in s["aussi"]) + ")")
            fin = max(fin, s["fin"])
        if fin < len(lignes_de[k]):
            L.append("  …")
    return "\n".join(L)


def _entete_code(c, nb_lignes):
    return (f"=== CODE {_etiquette(c)} : fichier {c['fichier']}, cas d'usage {c['numero']} « {c['cas_usage']} » "
            f"(extraits sur {nb_lignes} lignes, numéro de ligne du fichier à gauche) ===")


def contexte_cible(ds, res, question, budget, detaille=False):
    """Sommaire des codes et contrôles + extraits des codes dans le budget de tokens restant.
    Aucun résumé de l'Excel (detaille est gardé pour compatibilité, il ne change plus rien)."""
    resume = "\n".join(_sommaire(res))
    reste = max(300, budget - estimer_tokens(resume) - 60)
    return resume + "\n\n" + extraits(res, question, reste)
