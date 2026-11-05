"""
Écriture du modèle en SysML v2 textuel, au format validé dans
CATIA Magic Systems of Systems Architect SysML v2 Community 2026x.

Choix imposés par CATIA (constatés lors des essais) :
  - le texte est collé d'un seul coup dans le Textual Editor, dont la taille est
    limitée en édition Community : 11 026 octets passent, 26 088 non. D'où un
    format compact (pas d'indentation) et un budget de taille vérifié.
  - "satisfy X by UseCase::etape" et "UseCase.etape" sont refusés : le satisfy
    est écrit DANS l'action de l'étape.
  - les ids UserShaker en nom court (<id>) encombrent les diagrammes : ils sont
    écrits dans la documentation (doc /* id */).

Le rendu note aussi, pour chaque élément, son numéro de ligne dans le texte
(mod.lignes), pour la traçabilité Excel <-> SysML.
"""
from .noms import chaine, commentaire

BUDGET_OCTETS = 11000   # plus gros fichier accepté lors des essais : 11 026 octets


def rendre(mod):
    L = []
    lignes = {}

    def w(texte, cle=None):
        L.append(texte)
        if cle is not None:
            lignes[cle] = len(L)

    w(f"package {mod.package} {{")

    w("package Personas {")
    w("part def Persona;")
    for p in mod.personas:
        w(f"part {p.name} : Persona {{ doc /* {commentaire(p.id)} */ }}", p.id)
    w("}")

    w("package Components {")
    for c in mod.composants:
        w(f"part def {c.name} {{ doc /* {commentaire(c.id)} */ }}", c.id)
    w("}")

    w("package Needs {")
    for n in mod.besoins:
        w(f"requirement {n.name} {{ doc /* {commentaire(n.id)} */ }}", n.id)
    w("}")

    w("package UseCases {")
    for cu in mod.cas_usage:
        w(f"use case def {cu.name} {{", cu.id)
        w(f"doc /* {commentaire(cu.id)} */")
        for a, pid in cu.acteurs:
            w(f"actor {a} : Personas::Persona;", f"{cu.id}->{pid}")
        for e in cu.etapes:
            w(f"action {e.name} {{", e.id)
            w(f"doc /* {commentaire(e.id)} */")
            for d in e.declencheurs:
                w(f"attribute {d.name} = {chaine(d.texte)} {{ doc /* {commentaire(d.id)} */ }}", d.id)
            for b, nid in zip(e.besoins, e.besoin_ids):
                w(f"satisfy {b};", f"{e.id}->{nid}")
            w("}")
        for a, b in zip(cu.etapes, cu.etapes[1:]):
            w(f"first {a.name} then {b.name};", f"{a.id}=>{b.id}")
        w("}")
    w("}")

    w("}")
    mod.lignes = lignes
    return "\n".join(L) + "\n"


def taille_octets(texte):
    return len(texte.encode("utf-8"))
