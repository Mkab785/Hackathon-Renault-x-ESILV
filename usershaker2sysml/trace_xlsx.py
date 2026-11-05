"""
Traçabilité au format Excel, lisible par un humain :
    onglet « Lisez-moi »     comment lire le fichier
    onglet « Traçabilité »   une ligne par élément traduit : Excel <-> SysML
    onglet « Vérification »  relecture du SysML comparée à l'Excel (conforme / écart)
"""
import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .traduction import COLONNES_TRACE

_ENTETE = PatternFill("solid", fgColor="1F2A44")
_OK = PatternFill("solid", fgColor="E5F5EC")
_KO = PatternFill("solid", fgColor="FBE9E7")


def _feuille(ws, entetes, lignes, largeurs):
    ws.append(entetes)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = _ENTETE
        c.alignment = Alignment(vertical="center", wrap_text=True)
    for l in lignes:
        ws.append(l)
    for i, w in enumerate(largeurs, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(vertical="top", wrap_text=True)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


def trace_xlsx(res, source=""):
    """Renvoie le contenu du fichier .xlsx (octets)."""
    wb = Workbook()
    lm = wb.active
    lm.title = "Lisez-moi"
    ok = sum(1 for v in res.verification if v["ok"])
    texte = [
        ["Traçabilité UserShaker → SysML v2"],
        [f"Fichier source : {source}" if source else ""],
        [f"Modèle : {res.package}.sysml ({res.taille} octets)"],
        [f"Relecture du SysML : {ok} élément(s) conforme(s) sur {len(res.verification)}"],
        [""],
        ["Onglet « Traçabilité » : une ligne = un élément de l'Excel et l'endroit où il se trouve dans le SysML."],
        ["   Onglet Excel / Ligne Excel : où trouver la donnée dans l'export UserShaker (ligne 1 = en-têtes)."],
        ["   Dans l'Excel : ce que dit l'Excel (nom, déclencheur, lien étape → besoin...)."],
        ["   Type SysML : ce que l'élément est devenu (part, requirement, action, satisfy...)."],
        ["   Élément SysML : son nom dans le modèle (Paquet::Élément)."],
        ["   Ligne du .sysml : numéro de ligne dans le fichier .sysml (ou dans le Textual Editor de CATIA)."],
        ["   Id UserShaker : identifiant stable de la ligne ; il est aussi écrit dans le SysML (doc /* id */)."],
        [""],
        ["Onglet « Vérification » : le .sysml produit est relu indépendamment du traducteur et comparé"],
        ["   à l'Excel (noms, acteurs, ordre des étapes, déclencheurs, besoins satisfaits)."],
        ["   « conforme » = identique ; sinon la colonne Écarts dit ce qui diffère."],
        [""],
        ["Astuce : utiliser les filtres de la ligne d'en-tête (ex. Onglet Excel = steps)."],
    ]
    for l in texte:
        lm.append(l)
    lm["A1"].font = Font(bold=True, size=14)
    lm["A4"].font = Font(bold=True, color="1F8A4C" if ok == len(res.verification) else "C0362C")
    lm.column_dimensions["A"].width = 110

    ws = wb.create_sheet("Traçabilité")
    _feuille(ws, [t for _, t in COLONNES_TRACE],
             [[r[k] for k, _ in COLONNES_TRACE] for r in res.trace_detail],
             [16, 11, 60, 26, 60, 14, 28])

    wv = wb.create_sheet("Vérification")
    _feuille(wv, ["Statut", "Catégorie", "Onglet Excel", "Ligne Excel", "Dans l'Excel",
                  "Dans le SysML (relu)", "Ligne du .sysml", "Écarts", "Id UserShaker"],
             [["conforme" if v["ok"] else "ÉCART", v["categorie"], v["onglet"], v["ligne_excel"], v["excel"],
               v["sysml"], v["ligne_sysml"], " ; ".join(v["ecarts"]), v["id"]] for v in res.verification],
             [11, 13, 14, 11, 60, 60, 14, 45, 28])
    for row in wv.iter_rows(min_row=2):
        fill = _OK if row[0].value == "conforme" else _KO
        row[0].fill = fill
        row[0].font = Font(bold=True)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


COLONNES_TRACE_COMPLET = [
    ("onglet_excel", "Onglet Excel"),
    ("ligne_excel", "Ligne Excel"),
    ("dans_excel", "Dans l'Excel"),
    ("type_sysml", "Type SysML"),
    ("fichier", "Code (fichier .sysml)"),
    ("element_sysml", "Élément SysML"),
    ("ligne_sysml", "Ligne du code"),
    ("id", "Id UserShaker"),
]


def trace_xlsx_complet(res, source=""):
    """Traçabilité de la traduction complète (un code par cas d'usage). Renvoie les octets du .xlsx."""
    wb = Workbook()
    lm = wb.active
    lm.title = "Lisez-moi"
    ok = sum(1 for v in res.verification if v["ok"])
    texte = [
        ["Traçabilité UserShaker → SysML v2 (traduction complète, un code par cas d'usage)"],
        [f"Fichier source : {source}" if source else ""],
        [f"Codes : {len(res.codes)} (un projet CATIA par code, au plus {res.limite} caractères chacun)"],
        [f"Relecture des codes : {ok} élément(s) conforme(s) sur {len(res.verification)}"],
        [""],
        ["Onglet « Codes » : les fichiers .sysml, leur cas d'usage et leur taille."],
        ["Onglet « Traçabilité » : une ligne = une donnée de l'Excel et l'endroit où elle se trouve dans les codes."],
        ["   Onglet Excel / Ligne Excel : où trouver la donnée dans l'export UserShaker (ligne 1 = en-têtes)."],
        ["   Dans l'Excel : ce que dit l'Excel (nom, déclencheur, état d'un composant, ressenti...)."],
        ["   Type SysML : ce que la donnée est devenue (part, requirement, action, satisfy, attribute...)."],
        ["   Code / Élément / Ligne du code : le fichier .sysml, l'élément, et la ligne dans le Textual Editor de CATIA."],
        ["   Id UserShaker : identifiant stable ; il est aussi écrit dans le SysML (doc /* id */ ou [id])."],
        [""],
        ["Onglet « Vérification » : les codes sont relus indépendamment du traducteur et comparés à l'Excel"],
        ["   (noms, infos, états, acteurs, ordre des étapes, déclencheurs, besoins, groupes, textes, grille, ressentis)."],
        ["   « conforme » = identique ; sinon la colonne Écarts dit ce qui diffère."],
        [""],
        ["Non traduit : liens des images des étapes (steps.image_url), couleurs (personas.color, step_groups.color), "
         "champs de bibliothèque (sauf le nom de bibliothèque des besoins), onglet meta sauf nom du projet et date."],
        ["Astuce : utiliser les filtres de la ligne d'en-tête (ex. Onglet Excel = steps)."],
    ]
    for l in texte:
        lm.append(l)
    lm["A1"].font = Font(bold=True, size=14)
    lm["A4"].font = Font(bold=True, color="1F8A4C" if ok == len(res.verification) else "C0362C")
    lm.column_dimensions["A"].width = 110

    wc = wb.create_sheet("Codes")
    _feuille(wc, ["Code (fichier .sysml)", "Cas d'usage", "Partie", "Étapes", "Caractères", "Lignes"],
             [[c["fichier"], f"{c['numero']}. {c['cas_usage']}",
               f"{c['partie']}/{c['parties']}" if c["parties"] > 1 else "", c["etapes"], c["caracteres"], c["lignes"]]
              for c in res.codes], [46, 44, 9, 9, 12, 9])

    ws = wb.create_sheet("Traçabilité")
    _feuille(ws, [t for _, t in COLONNES_TRACE_COMPLET],
             [[r[k] for k, _ in COLONNES_TRACE_COMPLET] for r in res.trace_detail],
             [20, 11, 60, 26, 40, 50, 12, 28])

    wv = wb.create_sheet("Vérification")
    _feuille(wv, ["Statut", "Catégorie", "Onglet Excel", "Ligne Excel", "Dans l'Excel",
                  "Dans le SysML (relu)", "Code", "Ligne du code", "Écarts", "Id UserShaker"],
             [["conforme" if v["ok"] else "ÉCART", v["categorie"], v["onglet"], v["ligne_excel"], v["excel"],
               v["sysml"], v["fichier"], v["ligne_sysml"], " ; ".join(v["ecarts"]), v["id"]] for v in res.verification],
             [11, 13, 14, 11, 60, 60, 40, 12, 45, 28])
    for row in wv.iter_rows(min_row=2):
        fill = _OK if row[0].value == "conforme" else _KO
        row[0].fill = fill
        row[0].font = Font(bold=True)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
