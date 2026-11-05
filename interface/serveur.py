"""
Interface web locale du traducteur UserShaker -> SysML v2.

    python interface/serveur.py          (ou double-clic sur lancer_interface.bat)

Ouvre http://127.0.0.1:8000 dans le navigateur. Le serveur n'écoute que sur ce
PC ; aucune donnée ne part sur Internet. Python standard + openpyxl uniquement.

Traduction complète : un code SysML v2 par cas d'usage (cas d'usage indépendants), affichés
ensemble sur la page comme un seul modèle (usershaker2sysml/traduction_complete.py).

API (JSON) — utilisable aussi par d'autres outils de l'équipe :
    POST /api/analyser     corps = octets du .xlsx, en-tête X-Nom-Fichier
                           -> contrôles, codes SysML, vérification, traçabilité, aperçu, rapport, jeton
    GET  /lib/gsap.min.js, /lib/ScrollTrigger.min.js, /lib/encode-sans.woff2 -> animations et police (copies locales)
    GET  /api/trace.xlsx?jeton=...  -> traçabilité lisible (Excel)
    GET  /api/codes.zip?jeton=...   -> les codes .sysml + traçabilité + rapport
    POST /api/chat         corps = {"jeton", "messages": [{role, content}], "fournisseur": "claude"|"api",
                                       "mode": "rapide"|"pousse" (Claude seulement ; poussé par défaut)}
                           -> réponse de l'IA
    POST /api/chat/flux    même corps -> réponse au fur et à mesure, une ligne JSON par événement :
                           {"texte": morceau}... puis {"fin": réponse complète} ou {"erreur": message}
    POST /api/invite       corps = {"jeton", "question"} -> texte à coller dans un chat externe
    POST /api/assistant    corps = {"jeton": "..."} -> propositions de corrections (à brancher)
                           (voir interface/assistant.py)

Modèle lu dans le SysML (onglet du même nom) : ne lit QUE le texte des codes .sysml.
    GET  /modele                     -> page du lecteur seul (ouvrir des fichiers .sysml, ou ?jeton=...)
    GET  /api/modele?jeton=...       -> graphe lu dans les codes de la session (usershaker2sysml/modele_sysml.py)
    POST /api/modele                 corps = {"fichiers": [{"nom", "texte"}]} -> même chose pour des .sysml choisis
    GET  /api/grammaire?jeton=...    -> contrôle de grammaire OMG par SysML2Tools, s'il est installé
    POST /api/grammaire              corps = {"fichiers": [...]} -> même chose pour des .sysml choisis
"""
import io
import json
import os
import socket
import sys
import threading
import uuid
import webbrowser
import zipfile
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote, quote

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))          # pour importer usershaker2sysml

from usershaker2sysml import lire_xlsx, apercu  # noqa: E402
from usershaker2sysml.traduction_complete import traduire_complet, rapport_complet, NON_TRADUIT_COMPLET  # noqa: E402
from usershaker2sysml.trace_xlsx import trace_xlsx_complet  # noqa: E402
from usershaker2sysml.modele_sysml import lire_modele  # noqa: E402
from usershaker2sysml.controle_omg import controler_grammaire  # noqa: E402
from urllib.parse import urlparse, parse_qs  # noqa: E402
import assistant  # noqa: E402

PAGE = ICI / "page" / "index.html"
PAGE_MODELE = ICI / "page" / "modele.html"       # lecteur seul : ouvrir des fichiers .sysml
# fichiers de la page (copies locales : le site marche sans Internet). Liste fermée : rien d'autre n'est servi.
#   GSAP (animations) et Encode Sans (police libre, licence OFL : lib/OFL-Encode-Sans.txt).
LIBS = {
    "/lib/gsap.min.js": ("gsap.min.js", "text/javascript; charset=utf-8"),
    "/lib/ScrollTrigger.min.js": ("ScrollTrigger.min.js", "text/javascript; charset=utf-8"),
    "/lib/encode-sans.woff2": ("encode-sans.woff2", "font/woff2"),
    # charte R-monie : polices libres (licence OFL) et logos vectorisés
    **{f"/lib/{f}": (f, "font/woff2") for f in (
        "space-grotesk-latin-500-normal.woff2", "space-grotesk-latin-700-normal.woff2",
        "ibm-plex-sans-latin-300-normal.woff2", "ibm-plex-sans-latin-400-normal.woff2",
        "ibm-plex-sans-latin-500-normal.woff2", "ibm-plex-sans-latin-600-normal.woff2")},
    **{f"/lib/{f}": (f, "image/svg+xml") for f in (
        "logo_rm.svg", "logo_rmonie_fond_sombre.svg", "logo_rmonie_fond_clair.svg",
        "logo_texte_fond_sombre.svg", "logo_texte_fond_clair.svg")},
}
# code de l'onglet « Modèle lu dans le SysML » (fichiers de la page, liste fermée elle aussi)
PAGE_FICHIERS = {
    "/modele.js": ("modele.js", "text/javascript; charset=utf-8"),
    "/modele.css": ("modele.css", "text/css; charset=utf-8"),
    "/analyses.js": ("analyses.js", "text/javascript; charset=utf-8"),     # onglet « Analyses »
    "/theme.css": ("theme.css", "text/css; charset=utf-8"),
    "/outils.js": ("outils.js", "text/javascript; charset=utf-8"),           # export d'un schéma en image (lecteur)
}
TAILLE_MAX = 30 * 1024 * 1024
SESSIONS = {}            # jeton -> (Dataset, Resultat, nom du fichier)  (en mémoire, le temps de la session)
_VERROU = threading.Lock()


def analyser(contenu, nom):
    ds = lire_xlsx(contenu, nom)        # lu en mémoire : aucun fichier temporaire, l'original n'est pas touché
    res = traduire_complet(ds)
    jeton = uuid.uuid4().hex
    with _VERROU:
        SESSIONS[jeton] = (ds, res, nom)
        while len(SESSIONS) > 20:
            SESSIONS.pop(next(iter(SESSIONS)))
    return {
        "jeton": jeton,
        "fichier": nom,
        "traduit": res.traduit,
        "ok": res.ok,
        "package": res.package,
        "projet": res.projet,
        "limite": res.limite,
        "codes": res.codes,
        "code_entier": res.code_entier,        # un seul code, tous les cas d'usage (CATIA Magic sans limite)
        "problemes": [p.to_dict() for p in res.problemes],
        "couverture": [{"onglet": l.onglet, "attendus": l.attendus, "trouves": l.trouves, "ok": l.ok}
                       for l in res.couverture],
        "non_traduit": NON_TRADUIT_COMPLET,
        "rapport": rapport_complet(res, nom),
        "apercu": apercu(ds, res) if res.traduit else None,
        "verification": res.verification,
        "trace_detail": res.trace_detail,
        "assistant": assistant.etat(),
    }


def modele(codes):
    """Graphe lu dans les codes, avec leur texte (la page montre la ligne d'où vient chaque élément)."""
    return dict(lire_modele(codes), textes=dict(codes))


def codes_de_session(jeton):
    """[(fichier, texte)] des codes SysML de la session, ou None."""
    with _VERROU:
        sess = SESSIONS.get(jeton)
    if not sess or not sess[1].traduit:
        return None
    return [(c["fichier"], c["texte"]) for c in sess[1].codes]


def codes_envoyes(demande):
    """[(nom, texte)] des fichiers .sysml envoyés par la page (bouton « Lire des fichiers .sysml »)."""
    fichiers = demande.get("fichiers") if isinstance(demande, dict) else None
    if not isinstance(fichiers, list) or not fichiers or not all(isinstance(f, dict) for f in fichiers):
        raise ValueError("aucun fichier .sysml reçu")
    return [(str(f.get("nom") or f"code{k + 1}.sysml"), str(f.get("texte") or "")) for k, f in enumerate(fichiers)]


def archive_codes(res, nom):
    """Zip : les codes .sysml, la traçabilité et le rapport."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for c in res.codes:
            z.writestr(c["fichier"], c["texte"])
        if res.code_entier:
            z.writestr("code_entier/" + res.code_entier["fichier"], res.code_entier["texte"])
        z.writestr(f"{res.package}_trace.xlsx", trace_xlsx_complet(res, nom))
        z.writestr(f"{res.package}_rapport.txt", rapport_complet(res, nom))
    return buf.getvalue()


class Handler(BaseHTTPRequestHandler):
    server_version = "UserShaker2SysML/1.0"

    def log_message(self, fmt, *args):   # console plus calme
        pass

    def _json(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _flux(self, evenements):
        """Envoie la réponse de l'IA au fur et à mesure (une ligne JSON par événement)."""
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

        def ecrire(obj):
            self.wfile.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))
            self.wfile.flush()
        try:
            for genre, valeur in evenements:
                ecrire({"texte": valeur} if genre == "texte" else {"fin": valeur})
        except assistant.ErreurAssistant as e:
            ecrire({"erreur": str(e)})
        except (BrokenPipeError, ConnectionResetError):
            pass                                  # page fermée pendant la réponse
        except Exception as e:
            ecrire({"erreur": f"erreur interne : {e}"})

    def _corps(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > TAILLE_MAX:
            raise ValueError("fichier trop volumineux")
        return self.rfile.read(n)

    def do_GET(self):
        if self.path.split("?")[0] in ("/", "/index.html", "/modele"):
            data = (PAGE_MODELE if self.path.startswith("/modele") else PAGE).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        elif self.path.startswith("/api/trace.xlsx") or self.path.startswith("/api/codes.zip"):
            jeton = parse_qs(urlparse(self.path).query).get("jeton", [""])[0]
            with _VERROU:
                sess = SESSIONS.get(jeton)
            if not sess or not sess[1].traduit:
                return self._json(404, {"erreur": "session expirée : rechargez le fichier"})
            ds, res, nom = sess
            if self.path.startswith("/api/trace.xlsx"):
                data, type_, fichier = (trace_xlsx_complet(res, nom),
                                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                        f"{res.package}_trace.xlsx")
            else:
                data, type_, fichier = archive_codes(res, nom), "application/zip", f"{res.package}_codes_sysml.zip"
            self.send_response(200)
            self.send_header("Content-Type", type_)
            self.send_header("Content-Disposition", f'attachment; filename="{fichier}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif self.path.split("?")[0] in LIBS:
            fichier, type_ = LIBS[self.path.split("?")[0]]
            data = (ICI / "page" / "lib" / fichier).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", type_)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "max-age=86400")
            self.end_headers()
            self.wfile.write(data)
        elif self.path.split("?")[0] in PAGE_FICHIERS:
            fichier, type_ = PAGE_FICHIERS[self.path.split("?")[0]]
            data = (ICI / "page" / fichier).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", type_)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        elif self.path.split("?")[0] in ("/api/modele", "/api/grammaire"):
            codes = codes_de_session(parse_qs(urlparse(self.path).query).get("jeton", [""])[0])
            if codes is None:
                return self._json(404, {"erreur": "session expirée : rechargez le fichier"})
            lire = modele if self.path.startswith("/api/modele") else controler_grammaire
            return self._json(200, lire(codes))
        elif self.path.split("?")[0] == "/api/etat":
            self._json(200, {"ok": True, "assistant": assistant.etat(forcer="rafraichir" in self.path)})
        else:
            self._json(404, {"erreur": "page inconnue"})

    def do_POST(self):
        try:
            if self.path == "/api/analyser":
                nom = unquote(self.headers.get("X-Nom-Fichier") or "fichier.xlsx")
                contenu = self._corps()
                if not contenu:
                    return self._json(400, {"erreur": f"« {nom} » est vide (0 octet) : ré-exporter le fichier depuis UserShaker."})
                try:
                    return self._json(200, analyser(contenu, nom))
                except Exception as e:
                    detail = str(e)
                    if "zip" in detail.lower() or "not supported" in detail.lower():
                        detail = "ce n'est pas un classeur Excel .xlsx valide (un .xls ancien format ou un .csv ne sont pas acceptés)"
                    return self._json(400, {"erreur": f"Impossible de lire « {nom} » : {detail}."})
            if self.path in ("/api/modele", "/api/grammaire"):
                try:
                    codes = codes_envoyes(json.loads(self._corps() or b"{}"))
                except ValueError as e:
                    return self._json(400, {"erreur": str(e)})
                lire = modele if self.path == "/api/modele" else controler_grammaire
                return self._json(200, lire(codes))
            if self.path in ("/api/assistant", "/api/chat", "/api/invite", "/api/chat/flux"):
                demande = json.loads(self._corps() or b"{}")
                with _VERROU:
                    sess = SESSIONS.get(demande.get("jeton"))
                if not sess:
                    return self._json(404, {"erreur": "session expirée : rechargez le fichier"})
                ds, res, _ = sess
                if self.path == "/api/invite":
                    return self._json(200, {"texte": assistant.invite(ds, res, demande.get("question") or "")})
                if self.path == "/api/chat/flux":
                    return self._flux(assistant.repondre_flux(ds, res, demande.get("messages") or [],
                                                              demande.get("fournisseur"), demande.get("mode")))
                if self.path == "/api/chat":
                    try:
                        return self._json(200, assistant.repondre(ds, res, demande.get("messages") or [],
                                                                    demande.get("fournisseur"), demande.get("mode")))
                    except assistant.ErreurAssistant as e:
                        return self._json(502, {"erreur": str(e)})
                return self._json(200, assistant.proposer(ds, res.problemes))
            return self._json(404, {"erreur": "adresse inconnue"})
        except Exception as e:
            return self._json(500, {"erreur": f"erreur interne : {e}"})


def port_libre(depart=8000):
    for p in range(depart, depart + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    raise RuntimeError("aucun port libre entre 8000 et 8019")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    port = int(os.environ.get("PORT") or port_libre())
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"Interface ouverte sur {url}")
    print("Laisser cette fenêtre ouverte pendant l'utilisation. Ctrl+C pour arrêter.")
    if not os.environ.get("PAS_DE_NAVIGATEUR"):
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt.")


if __name__ == "__main__":
    main()
