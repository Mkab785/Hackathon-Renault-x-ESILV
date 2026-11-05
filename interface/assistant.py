r"""
Assistant IA de l'interface. Trois fournisseurs possibles, au choix dans l'onglet « Assistant IA » :

1. CLAUDE (ton abonnement Claude, sans clé d'API)
   L'interface appelle Claude Code installé sur ce PC (« claude -p ») : les questions
   passent par l'abonnement avec lequel Claude Code est connecté.
   Installation (PowerShell) :  irm https://claude.ai/install.ps1 | iex
   Connexion, une seule fois :  & "$env:USERPROFILE\.local\bin\claude.exe"   puis choisir
   l'abonnement Claude, puis /exit.
   Claude Code est cherché dans : variable CLAUDE_CLI, puis %USERPROFILE%\.local\bin\claude.exe
   (~/.local/bin/claude hors Windows), puis le PATH.
   La réponse est envoyée à la page au fur et à mesure qu'elle est écrite (repondre_flux).
   Claude est appelé sans aucun outil (il ne peut ni lire ni modifier de fichier), dans un
   dossier temporaire vide, sans serveur MCP, avec nos consignes à la place des siennes.
   La variable ANTHROPIC_API_KEY n'est pas transmise, pour ne jamais basculer sur l'API payante.
   Deux modes, au choix dans la page (MODES ci-dessous) :
     « Raisonnement rapide » = Claude Haiku, effort de réflexion bas (plus rapide, moins fiable) ;
     « Raisonnement poussé » = Claude Sonnet, effort de réflexion bas (par défaut, fiable pour croiser les données).

2. CODEX (ton abonnement ChatGPT, sans clé d'API)
   L'interface appelle Codex CLI installé sur ce PC (« codex exec ») : les questions passent
   par le compte ChatGPT avec lequel Codex est connecté (« codex login »).
   Installation : npm install -g @openai/codex   puis  codex login  (choisir « Sign in with ChatGPT »).
   Codex est cherché dans : variable CODEX_CLI, puis le PATH (codex, codex.cmd).
   Lancé en lecture seule (--sandbox read-only), dans un dossier temporaire vide, sans session
   enregistrée (--ephemeral) ; OPENAI_API_KEY et CODEX_API_KEY ne sont pas transmises, pour
   rester sur l'abonnement. Le modèle est celui du compte Codex (ou la variable CODEX_MODELE).
   Deux modes (MODES_CODEX) : « Raisonnement rapide » = effort low, « Raisonnement poussé » = effort medium.
   La réponse arrive en une fois (Codex ne la donne pas morceau par morceau).

3. CLÉ API : n'importe quelle IA compatible avec l'API « chat completions » d'OpenAI
   (Groq, OpenAI, Mistral, OpenRouter...). Fichier V1/cle_api.txt (lignes sans # devant) :
       cle = <la clé>
       url = https://api.groq.com/openai/v1/chat/completions      (facultatif)
       modele = openai/gpt-oss-120b                                 (facultatif)
   Sans url ni modele : Groq et openai/gpt-oss-120b. L'ancien fichier cle_groq.txt
   (une ligne = la clé) est encore lu si cle_api.txt ne contient pas de clé.
   Variables d'environnement possibles : API_KEY, API_URL, API_MODELE.
   La clé n'est lue que sur ce PC, n'est jamais envoyée au navigateur et ne doit jamais
   être partagée (ni dans un chat, ni sur GitHub).
   Chaque question tient en 6 000 tokens au plus (BUDGETS ci-dessous) : la liste des codes et
   seulement les passages des codes SysML liés à la question (contexte_ia.contexte_cible), pour
   passer sous la limite d'une offre gratuite (ex. Groq : 8 000 tokens par minute).

Budgets de tokens par question (BUDGETS) : clé API 4 500 en entrée + 1 500 pour la réponse ;
Claude et Codex 16 000 en entrée (extraits plus larges). « Copier pour un chat externe »
garde tout (codes entiers, environ 34 000 tokens).

L'IA reçoit les données de l'export, les résultats des contrôles et les codes SysML ;
elle a pour consigne de ne rien inventer et ne modifie rien.

------------------------------------------------------------------------------
Pour l'équipe — propositions de corrections (pas encore branchées dans la page) :
proposer(ds, problemes) doit renvoyer
    {"disponible": bool, "message": str,
     "propositions": [{"onglet", "id", "colonne", "avant", "apres", "raison", "code"}]}
Règles : proposer sans inventer, rester dans le schéma (schema.py), ne jamais
modifier l'xlsx d'origine (nouveau Dataset via depuis_dict, puis ecrire_xlsx).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from usershaker2sysml.contexte_ia import REGLES_EXTRAITS, contexte_cible, estimer_tokens, invite_complete

DOSSIER = Path(__file__).resolve().parent.parent
FICHIER_CLE = DOSSIER / "cle_api.txt"
ANCIEN_FICHIER_CLE = DOSSIER / "cle_groq.txt"      # ancien nom, encore lu
URL_DEFAUT = "https://api.groq.com/openai/v1/chat/completions"
MODELE_DEFAUT = "openai/gpt-oss-120b"
DELAI = 120          # secondes
# Tokens par question (estimation prudente, voir contexte_ia.estimer_tokens) et historique envoyé.
#   entree : consignes + résumé + extraits des codes + historique ; sortie : réponse (raisonnement compris)
BUDGETS = {
    "api": {"entree": 4500, "sortie": 1500, "messages": 4, "caracteres": 700},
    "claude": {"entree": 16000, "sortie": None, "messages": 6, "caracteres": 2000},
    "codex": {"entree": 16000, "sortie": None, "messages": 6, "caracteres": 2000},
}
MAX_MESSAGES = BUDGETS["api"]["messages"]        # historique envoyé (questions + réponses), clé API
MAX_CARACTERES = BUDGETS["api"]["caracteres"]    # par message de l'historique (la question en cours : x2)


def _lire_fichier(chemin):
    """Lit cle = / url = / modele = ; une ligne seule (sans « = ») est la clé."""
    r = {}
    try:
        lignes = chemin.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return r
    for ligne in lignes:
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#"):
            continue
        m = re.match(r"^(cl[eé]|key|url|mod[eè]le|model)\s*[=:]\s*(.+)$", ligne, re.I)
        if m:
            k = m.group(1).lower()
            k = "url" if k == "url" else "modele" if k.startswith("mod") else "cle"
            r.setdefault(k, m.group(2).strip())
        elif "cle" not in r:
            r["cle"] = ligne
    return r


def reglages():
    """Clé, adresse et modèle de l'IA « clé API » (variables d'environnement, puis cle_api.txt,
    puis l'ancien cle_groq.txt, puis les valeurs par défaut)."""
    f, ancien = _lire_fichier(FICHIER_CLE), _lire_fichier(ANCIEN_FICHIER_CLE)
    env = lambda *noms: next((os.environ[n].strip() for n in noms if (os.environ.get(n) or "").strip()), "")
    return {
        "cle": env("API_KEY", "GROQ_API_KEY") or f.get("cle") or ancien.get("cle") or "",
        "url": env("API_URL", "GROQ_URL") or f.get("url") or ancien.get("url") or URL_DEFAUT,
        "modele": env("API_MODELE", "GROQ_MODELE") or f.get("modele") or ancien.get("modele") or MODELE_DEFAUT,
    }


def lire_cle():
    return reglages()["cle"]


def _service(url):
    return urllib.parse.urlparse(url).hostname or url


def etat_api():
    """Ce que la page peut savoir (jamais la clé elle-même)."""
    r = reglages()
    return {"disponible": bool(r["cle"]), "nom": "Clé API", "modele": r["modele"], "service": _service(r["url"]),
            "fichier_cle": str(FICHIER_CLE)}


class ErreurAssistant(Exception):
    pass


def _appel(messages):
    r = reglages()
    cle, url, modele, service = r["cle"], r["url"], r["modele"], _service(r["url"])
    if not cle:
        raise ErreurAssistant(f"Clé API absente : écrire « cle = ta_clé » dans le fichier {FICHIER_CLE.name} "
                              "(dossier V1), puis réessayer.")
    corps = {
        "model": modele,
        "messages": messages,
        "temperature": 0.2,
        "max_completion_tokens": BUDGETS["api"]["sortie"],
    }
    if modele.startswith("openai/gpt-oss"):
        corps["reasoning_effort"] = "low"     # réponses plus rapides, moins de tokens
    req = urllib.request.Request(
        url, data=json.dumps(corps).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {cle}", "Content-Type": "application/json",
                 "User-Agent": "usershaker2sysml-interface/1.1"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=DELAI) as rep:
            data = json.loads(rep.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
        except Exception:
            detail = ""
        if e.code == 401:
            raise ErreurAssistant(f"Clé API refusée par {service} (invalide ou supprimée) : mettre une clé valide "
                                  f"dans {FICHIER_CLE.name}.")
        if e.code == 429:
            attente = e.headers.get("retry-after") if e.headers else None
            raise ErreurAssistant(f"Limite de {service} atteinte (par minute ou par jour)."
                                  + (f" Réessayer dans {attente} s." if attente else " Réessayer plus tard.")
                                  + " Chaque question envoie au plus 6 000 tokens : attendre une minute entre "
                                    "deux questions longues, ou utiliser Claude.")
        if e.code == 413:
            raise ErreurAssistant(f"Demande trop longue pour {service} (environ 6 000 tokens envoyés). "
                                  "Raccourcir la question ou démarrer une nouvelle conversation, ou utiliser Claude.")
        raise ErreurAssistant(f"{service} a répondu une erreur {e.code}" + (f" : {detail}" if detail else "."))
    except urllib.error.URLError as e:
        raise ErreurAssistant(f"Impossible de joindre {service} (connexion Internet, proxy ou pare-feu) : {e.reason}")
    except TimeoutError:
        raise ErreurAssistant(f"{service} n'a pas répondu en {DELAI} s. Réessayer.")
    try:
        texte = (data["choices"][0]["message"].get("content") or "").strip()
    except (KeyError, IndexError, TypeError):
        raise ErreurAssistant(f"Réponse de {service} dans un format inattendu.")
    if not texte:
        raise ErreurAssistant(f"{service} a renvoyé une réponse vide. Reformuler la question ou réessayer.")
    usage = data.get("usage") or {}
    return texte, round(time.time() - t0, 1), usage.get("total_tokens"), modele


def _historique_propre(historique, fournisseur="api"):
    b = BUDGETS[fournisseur]
    garde = [m for m in historique if m.get("role") in ("user", "assistant") and str(m.get("content") or "").strip()]
    propre = []
    for i, m in enumerate(garde[-b["messages"]:]):
        dernier = i == len(garde[-b["messages"]:]) - 1
        texte = str(m["content"])
        n = b["caracteres"] * (2 if dernier else 1)
        propre.append({"role": m["role"], "content": texte if len(texte) <= n else texte[:n] + "…"})
    if not propre or propre[-1]["role"] != "user":
        raise ErreurAssistant("Aucune question à envoyer.")
    return propre


def _systeme(ds, res, propre, fournisseur="api"):
    """Consignes + données, dans le budget de tokens du fournisseur. Les extraits des codes SysML sont
    choisis d'après la question en cours et la question précédente (pour « et pour l'étape 3 ? »)."""
    questions = [m["content"] for m in propre if m["role"] == "user"][-2:]
    reste = (BUDGETS[fournisseur]["entree"] - estimer_tokens(REGLES_EXTRAITS)
             - sum(estimer_tokens(m["content"]) + 4 for m in propre)
             - estimer_tokens("\n\n=== DONNÉES DU PROJET ===\n\n=== FIN DES DONNÉES ===") - 20)
    donnees = contexte_cible(ds, res, " ".join(questions), reste, detaille=fournisseur in ("claude", "codex"))
    return f"{REGLES_EXTRAITS}\n\n=== DONNÉES DU PROJET ===\n{donnees}\n=== FIN DES DONNÉES ==="


def repondre_api(ds, res, historique):
    """historique : [{"role": "user"|"assistant", "content": "..."}], la dernière entrée = question."""
    propre = _historique_propre(historique, "api")
    texte, duree, tokens, modele = _appel([{"role": "system", "content": _systeme(ds, res, propre, "api")}] + propre)
    return {"reponse": texte, "fournisseur": "api", "modele": modele, "duree": duree, "tokens": tokens}


# =============================== Claude (abonnement) ===============================

DELAI_CLAUDE = 180       # secondes
# mode -> (nom affiché, modèle, effort de réflexion)
MODES = {
    "rapide": ("Raisonnement rapide", "haiku", "low"),
    "pousse": ("Raisonnement poussé", "sonnet", "low"),
}
MODE_DEFAUT = "pousse"


def _mode(mode):
    return mode if mode in MODES else MODE_DEFAUT
_CACHE_ETAT = {"quand": 0.0, "commande": None, "valeur": None}
_VERROU_ETAT = threading.Lock()
DUREE_CACHE = 30         # secondes entre deux vérifications « claude auth status »


def trouver_claude():
    """Commande (liste) pour lancer Claude Code, ou None s'il n'est pas installé."""
    perso = (os.environ.get("CLAUDE_CLI") or "").strip().strip('"')
    if perso:
        if perso.lower().endswith(".py"):            # faux Claude des tests
            return [sys.executable, perso]
        return [perso] if Path(perso).exists() or shutil.which(perso) else None
    nom = "claude.exe" if os.name == "nt" else "claude"
    local = Path.home() / ".local" / "bin" / nom
    if local.exists():
        return [str(local)]
    trouve = shutil.which("claude")
    return [trouve] if trouve else None


def _env_claude():
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)               # toujours l'abonnement, jamais l'API payante
    return env


def _lancer(commande, entree=None, cwd=None, delai=30):
    options = {}
    if os.name == "nt":
        options["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)   # pas de fenêtre noire
    return subprocess.run(commande, input=entree, capture_output=True, cwd=cwd, timeout=delai,
                          env=_env_claude(), **options)


def etat_claude(forcer=False):
    commande = trouver_claude()
    base = {"nom": "Claude (ton abonnement)", "modele": MODES[MODE_DEFAUT][1],
            "modes": {k: {"nom": v[0], "modele": v[1], "effort": v[2], "detail": v[1].capitalize()} for k, v in MODES.items()},
            "mode_defaut": MODE_DEFAUT}
    if not commande:
        return dict(base, disponible=False, installe=False, connecte=False,
                    detail="Claude Code n'est pas installé sur ce PC (voir le README).")
    with _VERROU_ETAT:
        c = _CACHE_ETAT
        if (not forcer and c["commande"] == commande and c["valeur"] is not None
                and time.time() - c["quand"] < DUREE_CACHE):
            return c["valeur"]
    try:
        r = _lancer(commande + ["auth", "status"], delai=30)
        try:
            info = json.loads(r.stdout.decode("utf-8", "replace"))
        except ValueError:
            info = {}
        connecte = r.returncode == 0 and info.get("loggedIn", True) is not False
        if connecte:
            valeur = dict(base, disponible=True, installe=True, connecte=True, detail="")
        else:
            valeur = dict(base, disponible=False, installe=True, connecte=False,
                          detail="Claude Code est installé mais pas connecté : ouvrir PowerShell, lancer "
                                 "& \"$env:USERPROFILE\\.local\\bin\\claude.exe\", choisir l'abonnement Claude, puis /exit.")
    except (OSError, subprocess.TimeoutExpired) as e:
        valeur = dict(base, disponible=False, installe=True, connecte=False,
                      detail=f"Claude Code ne répond pas ({e.__class__.__name__}).")
    with _VERROU_ETAT:
        _CACHE_ETAT.update(quand=time.time(), commande=commande, valeur=valeur)
    return valeur


def _invite_claude(propre):
    """« claude -p » ne garde pas de conversation : on lui renvoie l'échange précédent en texte."""
    question = propre[-1]["content"]
    avant = propre[:-1]
    if not avant:
        return question
    lignes = ["Échange précédent avec l'utilisateur (pour le contexte) :"]
    for m in avant:
        lignes.append(("[Question] " if m["role"] == "user" else "[Ta réponse] ") + m["content"])
    lignes += ["", "Nouvelle question : " + question]
    return "\n".join(lignes)


def _resultat_claude(data, erreur_brute, t0, modele_demande="Claude"):
    """Interprète la dernière ligne (« result ») de Claude Code. Renvoie (texte, durée, tokens, modèle)."""
    if not isinstance(data, dict) or "result" not in data:
        raise ErreurAssistant(f"Claude Code a renvoyé une erreur : {(erreur_brute or 'aucune sortie')[:400]}")
    texte = str(data.get("result") or "").strip()
    if data.get("is_error"):
        bas = texte.lower()
        if "login" in bas or "logged in" in bas or "auth" in bas:
            with _VERROU_ETAT:
                _CACHE_ETAT["valeur"] = None
            raise ErreurAssistant("Claude Code n'est pas connecté à l'abonnement. Ouvrir PowerShell, lancer "
                                  "& \"$env:USERPROFILE\\.local\\bin\\claude.exe\", choisir l'abonnement Claude, "
                                  f"puis /exit, et réessayer. (Message de Claude Code : {texte})")
        if "limit" in bas:
            raise ErreurAssistant(f"Limite d'utilisation de l'abonnement atteinte. (Message de Claude Code : {texte})")
        raise ErreurAssistant(f"Claude Code a renvoyé une erreur : {texte or 'sans détail'}")
    if not texte:
        raise ErreurAssistant("Claude a renvoyé une réponse vide. Reformuler la question ou réessayer.")
    modeles = list((data.get("modelUsage") or {}).keys())
    usage = data.get("usage") or {}
    tokens = sum(int(usage.get(k) or 0) for k in ("input_tokens", "output_tokens",
                                                  "cache_creation_input_tokens", "cache_read_input_tokens")) or None
    duree = round((data.get("duration_ms") or (time.time() - t0) * 1000) / 1000, 1)
    return texte, duree, tokens, (modeles[0] if modeles else modele_demande)


def flux_claude(systeme, invite, mode=None):
    """Lance Claude Code et donne la réponse au fur et à mesure :
    ("texte", morceau)... puis ("fin", (texte, durée, tokens, modèle)).
    mode : "rapide" (Haiku) ou "pousse" (Sonnet), voir MODES."""
    _, modele_claude, effort = MODES[_mode(mode)]
    commande = trouver_claude()
    if not commande:
        raise ErreurAssistant("Claude Code n'est pas installé sur ce PC. Dans PowerShell : "
                              "irm https://claude.ai/install.ps1 | iex   puis se connecter (voir le README).")
    with tempfile.TemporaryDirectory(prefix="assistant_claude_") as dossier:
        consignes = Path(dossier) / "consignes.txt"
        consignes.write_text(systeme, encoding="utf-8")
        travail = Path(dossier) / "vide"
        travail.mkdir()                               # dossier vide : aucun fichier de projet chargé
        args = commande + ["-p", "--output-format", "stream-json", "--verbose", "--include-partial-messages",
                           "--tools", "",              # aucun outil : ni lecture ni écriture de fichiers
                           "--strict-mcp-config",      # aucun serveur MCP
                           "--no-session-persistence",
                           "--permission-prompts", "none",
                           "--max-turns", "1",
                           "--system-prompt-file", str(consignes)]
        args += ["--model", modele_claude, "--effort", effort]
        options = {}
        if os.name == "nt":
            options["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        t0 = time.time()
        with tempfile.TemporaryFile() as err:
            try:
                proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err,
                                        cwd=str(travail), env=_env_claude(), **options)
            except OSError as e:
                raise ErreurAssistant(f"Impossible de lancer Claude Code : {e}")
            minuterie = threading.Timer(DELAI_CLAUDE, proc.kill)
            minuterie.start()
            resultat, autre = None, []
            try:
                try:
                    proc.stdin.write(invite.encode("utf-8"))
                    proc.stdin.close()
                except OSError:
                    pass
                for brut in proc.stdout:
                    ligne = brut.decode("utf-8", "replace").strip()
                    if not ligne:
                        continue
                    try:
                        ev = json.loads(ligne)
                    except ValueError:
                        autre.append(ligne)
                        continue
                    if not isinstance(ev, dict):
                        continue
                    if ev.get("type") == "stream_event":
                        delta = (ev.get("event") or {}).get("delta") or {}
                        if delta.get("type") == "text_delta" and delta.get("text"):
                            yield "texte", delta["text"]
                    elif "result" in ev and ev.get("type", "result") == "result":
                        resultat = ev
                proc.wait()
            finally:
                minuterie.cancel()
                if proc.poll() is None:
                    proc.kill()
            if resultat is None and time.time() - t0 >= DELAI_CLAUDE - 1:
                raise ErreurAssistant(f"Claude n'a pas répondu en {DELAI_CLAUDE} s. Réessayer.")
            err.seek(0)
            erreur_brute = err.read().decode("utf-8", "replace").strip() or "\n".join(autre)
    yield "fin", _resultat_claude(resultat, erreur_brute, t0, modele_claude)


def _appel_claude(systeme, invite, mode=None):
    fin = None
    for genre, valeur in flux_claude(systeme, invite, mode):
        if genre == "fin":
            fin = valeur
    return fin


def repondre_claude(ds, res, historique, mode=None):
    propre = _historique_propre(historique, "claude")
    texte, duree, tokens, modele = _appel_claude(_systeme(ds, res, propre, "claude"), _invite_claude(propre), mode)
    return {"reponse": texte, "fournisseur": "claude", "modele": modele, "duree": duree, "tokens": tokens,
            "mode": _mode(mode)}


def repondre_flux(ds, res, historique, fournisseur=None, mode=None):
    """Comme repondre, mais au fur et à mesure : ("texte", morceau)... puis ("fin", réponse complète).
    Claude : morceau par morceau ; clé API : la réponse arrive en une fois."""
    if fournisseur == "groq":
        fournisseur = "api"
    if fournisseur not in FOURNISSEURS:
        fournisseur = etat()["par_defaut"]
    if fournisseur == "claude":
        propre = _historique_propre(historique, "claude")
        for genre, valeur in flux_claude(_systeme(ds, res, propre, "claude"), _invite_claude(propre), mode):
            if genre == "texte":
                yield "texte", valeur
            else:
                texte, duree, tokens, modele = valeur
                yield "fin", {"reponse": texte, "fournisseur": "claude", "modele": modele, "duree": duree,
                              "tokens": tokens, "mode": _mode(mode)}
        return
    if fournisseur == "codex":
        propre = _historique_propre(historique, "codex")
        for genre, valeur in flux_codex(_systeme(ds, res, propre, "codex"), _invite_claude(propre), mode):
            if genre == "texte":
                yield "texte", valeur
            else:
                texte, duree, tokens, modele = valeur
                yield "fin", {"reponse": texte, "fournisseur": "codex", "modele": modele, "duree": duree,
                              "tokens": tokens, "mode": _mode_codex(mode)}
        return
    r = repondre(ds, res, historique, fournisseur)
    yield "texte", r["reponse"]
    yield "fin", r


# =============================== Codex (abonnement ChatGPT) ===============================

DELAI_CODEX = 180        # secondes
# mode -> (nom affiché, effort de raisonnement). Le modèle est celui du compte Codex (pas imposé).
MODES_CODEX = {
    "rapide": ("Raisonnement rapide", "low"),
    "pousse": ("Raisonnement poussé", "medium"),
}
_CACHE_CODEX = {"quand": 0.0, "commande": None, "valeur": None}


def _mode_codex(mode):
    return mode if mode in MODES_CODEX else MODE_DEFAUT


def trouver_codex():
    """Commande (liste) pour lancer Codex CLI, ou None s'il n'est pas installé."""
    perso = (os.environ.get("CODEX_CLI") or "").strip().strip('"')
    if perso:
        if perso.lower().endswith(".py"):            # faux Codex des tests
            return [sys.executable, perso]
        return [perso] if Path(perso).exists() or shutil.which(perso) else None
    trouve = shutil.which("codex")                    # Windows : codex.cmd (npm) ou codex.exe, via PATHEXT
    if trouve:
        return [trouve]
    if os.name == "nt":
        npm = Path(os.environ.get("APPDATA", "")) / "npm" / "codex.cmd"
        if npm.exists():
            return [str(npm)]
    return None


def _env_codex():
    env = dict(os.environ)
    for cle in ("OPENAI_API_KEY", "CODEX_API_KEY"):   # toujours l'abonnement ChatGPT, jamais l'API payante
        env.pop(cle, None)
    return env


def _modele_codex():
    return (os.environ.get("CODEX_MODELE") or "").strip()


def etat_codex(forcer=False):
    commande = trouver_codex()
    base = {"nom": "Codex (ton abonnement ChatGPT)", "modele": _modele_codex() or "modèle du compte Codex",
            "modes": {k: {"nom": v[0], "modele": _modele_codex() or "Codex", "effort": v[1], "detail": f"effort {v[1]}"}
                      for k, v in MODES_CODEX.items()},
            "mode_defaut": MODE_DEFAUT}
    if not commande:
        return dict(base, disponible=False, installe=False, connecte=False,
                    detail="Codex n'est pas installé sur ce PC (voir le README).")
    with _VERROU_ETAT:
        c = _CACHE_CODEX
        if (not forcer and c["commande"] == commande and c["valeur"] is not None
                and time.time() - c["quand"] < DUREE_CACHE):
            return c["valeur"]
    try:
        options = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if os.name == "nt" else {}
        r = subprocess.run(commande + ["login", "status"], capture_output=True, timeout=30, env=_env_codex(),
                           stdin=subprocess.DEVNULL, **options)
        if r.returncode == 0:
            valeur = dict(base, disponible=True, installe=True, connecte=True, detail="")
        else:
            valeur = dict(base, disponible=False, installe=True, connecte=False,
                          detail="Codex est installé mais pas connecté : dans PowerShell, lancer « codex login » "
                                 "et choisir « Sign in with ChatGPT ».")
    except (OSError, subprocess.TimeoutExpired) as e:
        valeur = dict(base, disponible=False, installe=True, connecte=False,
                      detail=f"Codex ne répond pas ({e.__class__.__name__}).")
    with _VERROU_ETAT:
        _CACHE_CODEX.update(quand=time.time(), commande=commande, valeur=valeur)
    return valeur


def flux_codex(systeme, invite, mode=None):
    """Lance « codex exec --json » ; donne ("texte", réponse) puis ("fin", (texte, durée, tokens, modèle)).
    Événements lus (JSON Lines) : item.completed (item.type = agent_message, item.text),
    turn.completed (usage), turn.failed / error (message)."""
    _, effort = MODES_CODEX[_mode_codex(mode)]
    commande = trouver_codex()
    if not commande:
        raise ErreurAssistant("Codex n'est pas installé sur ce PC. Dans PowerShell : npm install -g @openai/codex "
                              "puis codex login (voir le README).")
    args = commande + ["exec", "--json", "--skip-git-repo-check", "--ephemeral", "--sandbox", "read-only",
                       "-c", f"model_reasoning_effort={effort}"]
    if _modele_codex():
        args += ["-m", _modele_codex()]
    args.append("-")                                   # la consigne et la question arrivent par l'entrée standard
    entree = f"{systeme}\n\n=== QUESTION DE L'UTILISATEUR ===\n{invite}\n"
    options = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if os.name == "nt" else {}
    t0 = time.time()
    with tempfile.TemporaryDirectory(prefix="assistant_codex_") as dossier, tempfile.TemporaryFile() as err:
        try:
            proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err,
                                    cwd=dossier, env=_env_codex(), **options)
        except OSError as e:
            raise ErreurAssistant(f"Impossible de lancer Codex : {e}")
        minuterie = threading.Timer(DELAI_CODEX, proc.kill)
        minuterie.start()
        textes, usage, erreur = [], {}, None
        try:
            try:
                proc.stdin.write(entree.encode("utf-8"))
                proc.stdin.close()
            except OSError:
                pass
            for brut in proc.stdout:
                try:
                    ev = json.loads(brut.decode("utf-8", "replace"))
                except ValueError:
                    continue
                if not isinstance(ev, dict):
                    continue
                genre = ev.get("type")
                if genre == "item.completed" and (ev.get("item") or {}).get("type") == "agent_message":
                    textes.append(str(ev["item"].get("text") or ""))
                elif genre == "turn.completed":
                    usage = ev.get("usage") or {}
                elif genre in ("turn.failed", "error"):
                    detail = ev.get("error") if isinstance(ev.get("error"), dict) else {}
                    erreur = detail.get("message") or ev.get("message") or "erreur sans détail"
            proc.wait()
        finally:
            minuterie.cancel()
            if proc.poll() is None:
                proc.kill()
        err.seek(0)
        brut_err = err.read().decode("utf-8", "replace").strip()
    texte = "\n\n".join(x for x in textes if x.strip()).strip()
    if not texte:
        if time.time() - t0 >= DELAI_CODEX - 1:
            raise ErreurAssistant(f"Codex n'a pas répondu en {DELAI_CODEX} s. Réessayer.")
        message = erreur or brut_err[-400:] or "aucune réponse"
        bas = message.lower()
        if "login" in bas or "auth" in bas or "401" in bas:
            with _VERROU_ETAT:
                _CACHE_CODEX["valeur"] = None
            raise ErreurAssistant(f"Codex n'est pas connecté : lancer « codex login » dans PowerShell. (Message : {message})")
        if "limit" in bas or "429" in bas:
            raise ErreurAssistant(f"Limite d'utilisation de l'abonnement atteinte. (Message de Codex : {message})")
        raise ErreurAssistant(f"Codex a renvoyé une erreur : {message}")
    tokens = sum(int(usage.get(k) or 0) for k in ("input_tokens", "output_tokens")) or None
    yield "texte", texte
    yield "fin", (texte, round(time.time() - t0, 1), tokens, _modele_codex() or "Codex")


def repondre_codex(ds, res, historique, mode=None):
    propre = _historique_propre(historique, "codex")
    fin = None
    for genre, valeur in flux_codex(_systeme(ds, res, propre, "codex"), _invite_claude(propre), mode):
        if genre == "fin":
            fin = valeur
    texte, duree, tokens, modele = fin
    return {"reponse": texte, "fournisseur": "codex", "modele": modele, "duree": duree, "tokens": tokens,
            "mode": _mode_codex(mode)}


# =============================== choix du fournisseur ===============================

FOURNISSEURS = ("claude", "codex", "api")


def etat(forcer=False):
    """État pour la page : Claude par défaut s'il est connecté, sinon Codex, sinon la clé API si elle est là."""
    f = {"claude": etat_claude(forcer), "codex": etat_codex(forcer), "api": etat_api()}
    defaut = next((n for n in FOURNISSEURS if f[n]["disponible"]), None)
    return {"disponible": defaut is not None, "par_defaut": defaut, "fournisseurs": f}


def repondre(ds, res, historique, fournisseur=None, mode=None):
    """historique : [{"role": "user"|"assistant", "content": "..."}], la dernière entrée = question."""
    if fournisseur == "groq":            # ancien nom
        fournisseur = "api"
    if fournisseur not in FOURNISSEURS:
        fournisseur = etat()["par_defaut"]
    if fournisseur == "claude":
        return repondre_claude(ds, res, historique, mode)
    if fournisseur == "codex":
        return repondre_codex(ds, res, historique, mode)
    if fournisseur == "api":
        return repondre_api(ds, res, historique)
    raise ErreurAssistant("Aucun assistant disponible : connecter Claude Code ou Codex, ou écrire une clé dans cle_api.txt "
                          "(voir le README). En attendant, « Copier pour un chat externe » fonctionne.")


def invite(ds, res, question=""):
    """Texte à copier dans un chat externe si aucun assistant n'est disponible."""
    return invite_complete(ds, res, question)


def proposer(ds, problemes):
    return {
        "disponible": False,
        "message": "Propositions de corrections automatiques : pas encore branchées (voir interface/assistant.py).",
        "propositions": [],
    }
