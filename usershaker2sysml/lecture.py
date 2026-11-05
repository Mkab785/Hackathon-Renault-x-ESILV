"""
Lecture / écriture des données UserShaker.

Deux portes d'entrée, même résultat (un objet Dataset) :
    lire_xlsx(chemin)            -> fichier exporté par UserShaker (ou corrigé)
    depuis_dict({onglet: [..]})  -> données déjà en mémoire (ex. renvoyées par
                                    un assistant de correction, sans passer par
                                    un fichier)

Et une sortie :
    ecrire_xlsx(dataset, chemin) -> réécrit un xlsx au même format (pour garder
                                    une version corrigée, l'original n'est jamais
                                    modifié)

Aucune valeur n'est transformée ici, sauf : une cellule vide ou "" devient None
(le readme dit qu'une cellule vide veut dire "non renseigné").
"""
import io
from pathlib import Path

import openpyxl

from .schema import SHEETS


class Dataset:
    """Les onglets d'un export. sheets[nom] = liste de lignes (dict colonne -> valeur)."""

    def __init__(self):
        self.sheets = {}         # onglet -> [ {colonne: valeur} ]
        self.rows = {}           # onglet -> [ numéro de ligne Excel ] (pour les messages)
        self.columns = {}        # onglet -> colonnes trouvées, dans l'ordre du fichier
        self.unknown_sheets = []  # onglets présents mais hors schéma (ignorés)
        self.readme = []         # lignes brutes de l'onglet readme (recopiées telles quelles)
        self.source = None       # chemin du fichier lu, si lu depuis un fichier

    # -- accès pratiques --
    def get(self, sheet):
        return self.sheets.get(sheet, [])

    def has(self, sheet):
        return sheet in self.sheets

    def meta(self):
        return {r.get("key"): r.get("value") for r in self.get("meta")}

    def row_number(self, sheet, index):
        r = self.rows.get(sheet)
        return r[index] if r and index < len(r) else None


def _clean(v):
    if isinstance(v, str) and v == "":
        return None
    return v


def lire_xlsx(chemin, nom=None):
    """chemin : chemin du fichier, ou son contenu (octets), ou un objet fichier ouvert."""
    if isinstance(chemin, (bytes, bytearray)):
        source, nom = io.BytesIO(chemin), nom or "fichier.xlsx"
    elif hasattr(chemin, "read"):
        source, nom = chemin, nom or getattr(chemin, "name", "fichier.xlsx")
    else:
        source = Path(chemin)
        nom = nom or str(source)
    wb = openpyxl.load_workbook(source, data_only=True, read_only=True)
    try:
        return _lire_classeur(wb, nom)
    finally:
        wb.close()


def _lire_classeur(wb, nom):
    ds = Dataset()
    ds.source = nom
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        if ws.title == "readme":
            ds.readme = [[_clean(v) for v in r] for r in rows]
            continue
        if ws.title not in SHEETS:
            ds.unknown_sheets.append(ws.title)
            continue
        if not rows:
            ds.sheets[ws.title], ds.rows[ws.title], ds.columns[ws.title] = [], [], []
            continue
        head = [h for h in rows[0]]
        # on coupe les colonnes vides de fin
        while head and head[-1] in (None, ""):
            head.pop()
        recs, nums = [], []
        for i, r in enumerate(rows[1:], start=2):
            vals = list(r[:len(head)])
            if all(v is None or v == "" for v in vals):
                continue
            recs.append({str(h): _clean(v) for h, v in zip(head, vals) if h not in (None, "")})
            nums.append(i)
        ds.sheets[ws.title] = recs
        ds.rows[ws.title] = nums
        ds.columns[ws.title] = [str(h) for h in head if h not in (None, "")]
    return ds


def depuis_dict(donnees):
    """donnees = {onglet: [ {colonne: valeur}, ... ]}. Les numéros de ligne sont
    calculés comme si l'onglet était écrit dans Excel (en-tête en ligne 1)."""
    ds = Dataset()
    for name, recs in donnees.items():
        if name == "readme":
            ds.readme = [[_clean(v) for v in r] for r in recs]
            continue
        if name not in SHEETS:
            ds.unknown_sheets.append(name)
            continue
        recs = [{k: _clean(v) for k, v in r.items()} for r in recs]
        ds.sheets[name] = recs
        ds.rows[name] = list(range(2, len(recs) + 2))
        cols = []
        for r in recs:
            for k in r:
                if k not in cols:
                    cols.append(k)
        ds.columns[name] = cols or list(SHEETS[name])
    return ds


def ecrire_xlsx(ds, chemin):
    """Écrit le Dataset au format d'export (onglets dans l'ordre du schéma)."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    if ds.readme:
        ws = wb.create_sheet("readme")
        for r in ds.readme:
            ws.append(list(r))
    for name, cols_schema in SHEETS.items():
        if not ds.has(name):
            continue
        cols = list(ds.columns.get(name) or cols_schema)
        for c in cols_schema:          # colonnes du schéma toujours présentes
            if c not in cols:
                cols.append(c)
        ws = wb.create_sheet(name)
        ws.append(cols)
        for r in ds.get(name):
            ws.append([r.get(c) for c in cols])
    wb.save(chemin)
    return Path(chemin)
