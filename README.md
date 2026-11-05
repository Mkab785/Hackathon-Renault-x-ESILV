# R-monie — traducteur UserShaker → SysML v2 (CATIA Magic)

Projet de l'équipe 904 (ESILV S9 × Renault, hackathon 2026). R-monie transforme l'export Excel
d'un parcours utilisateur **UserShaker** en **code SysML v2** importable dans **CATIA Magic**,
avec un site local pour vérifier la traduction, lire le modèle et poser des questions à un
assistant IA. Seule dépendance : `openpyxl`.

> Aucun export UserShaker n'est fourni dans ce dépôt : utilisez votre propre fichier `.xlsx`.
> La clé API de l'assistant n'est jamais versionnée (`cle_api.txt` est dans `.gitignore`).

## Démarrage rapide (Windows)

1. **Python 3.8 ou plus** : https://www.python.org/downloads/ — à l'installation, cocher
   **« Add python.exe to PATH »**.
2. Double-clic sur **`installer.bat`** (une seule fois). Il installe **seulement `openpyxl`**, le module
   obligatoire. Claude Code, Codex et la clé API sont facultatifs et ne sont pas installés (voir point 5).
   Les `.bat` utilisent la commande `python`, ou à défaut le lanceur `py` de Windows.
3. Double-clic sur **`lancer_interface.bat`** : le site s'ouvre dans le navigateur
   (`http://127.0.0.1:8000`, page locale). Laisser la fenêtre noire ouverte.
4. **« Ouvrir un export UserShaker (.xlsx) »**, ou le déposer dans la zone prévue. Déjà des codes `.sysml` ? Lien
   « Les ouvrir dans le lecteur de modèle » sous la zone de dépôt.
5. Facultatif : l'**assistant IA** (Claude via Claude Code, Codex via Codex CLI, ou une clé API : copier
   `cle_api.exemple.txt` en `cle_api.txt` et y mettre sa propre clé), et le **contrôle de
   grammaire OMG** par SysML2Tools. Voir plus bas.

## Contenu du dossier

| Élément | Rôle |
|---|---|
| `lancer_interface.bat` | lance le site local |
| `traduire.bat` | traduction en ligne de commande (glisser un `.xlsx` dessus) |
| `installer.bat`, `requirements.txt` | installation de `openpyxl` |
| `cle_api.exemple.txt` | modèle du fichier de clé API (facultatif) |
| `usershaker2sysml/` | le traducteur : lecture, contrôles, codes SysML, relecture, lecteur de modèle, contexte de l'IA |
| `interface/` | le site : `serveur.py`, `assistant.py`, `page/` (page, lecteur de modèle, police et animations locales) |

Les résultats de `traduire.bat` sont écrits dans un dossier `sortie\`, créé au premier lancement.

Transforme un export UserShaker (`.xlsx` brut) en **un code SysML v2 par cas d'usage**,
prêts pour **CATIA Magic Systems of Systems Architect SysML v2 Community 2026x**.
Le fichier xlsx d'origine n'est jamais modifié.

- **Toute l'information de l'Excel** est traduite (étapes, déclencheurs, besoins, enchaînement,
  états des composants, grille composant × étape, ressentis et émotions, groupes d'étapes,
  descriptions, histoires, biographies…), **sauf** les liens des images des étapes, les couleurs
  (personas, groupes d'étapes), les champs de bibliothèque et les infos d'export de l'onglet `meta`
  autres que le nom du projet et la date (détail dans l'onglet « Comment fonctionne le traducteur »).
- L'édition Community refuse les textes de plus de **20 000 caractères** : chaque cas d'usage
  donne un code autonome sous cette limite (4 codes pour l'export Renault, le plus gros à
  19 363 caractères). Un cas d'usage trop long serait coupé automatiquement en parties.
- Les cas d'usage sont indépendants : **un projet CATIA par code**. Sur le site, les codes
  sont affichés ensemble, comme un seul modèle.
- **Le nombre de cas d'usage est libre** (1, 3, 5…) : il y a autant de codes que de cas d'usage,
  plus les parties si l'un d'eux dépasse la limite. Vérifié de 1 à 6 cas d'usage (relecture
  conforme à 100 %, même modèle lu sur le site).
- **Code entier** : un seul code avec tous les cas d'usage, sans découpage, pour un client qui a
  **CATIA Magic complet** (pas la limite de 20 000 caractères de Community). Personas, composants
  et besoins y sont définis une seule fois. Il est relu et comparé à l'Excel comme les autres
  codes (62/62 et 606/606 sur l'export E-Space, 44 422 caractères). Sur le site : onglet Export,
  « Version de CATIA Magic chez le client : Complète : code entier ».

## Lancer

Prérequis : Python 3.8+ et `openpyxl` (`python -m pip install openpyxl`).

### Interface web (recommandé)

Double-clic sur **`lancer_interface.bat`** : le navigateur s'ouvre sur
`http://127.0.0.1:8000` (page locale). Laisser la fenêtre noire ouverte pendant l'utilisation.

1. Choisir ou déposer l'xlsx (s'il est ouvert dans Excel, le fermer d'abord).
2. Le site s'ouvre sur le **tableau de bord** : bandeau d'état (vert = prêt pour CATIA,
   orange = à vérifier, rouge = aucun code), les **3 étapes** cliquables (contrôles des données,
   traduction vérifiée, prêt pour CATIA), les chiffres clés, puis 4 cartes : les cas d'usage et
   leurs codes (boutons « Code SysML » et « Étapes »), la couverture des besoins, les contrôles et
   la vérification (avec les points à remonter), et les **actions rapides** (copier les codes,
   code entier, zip, traçabilité, modèle SysML, assistant IA).
3. Le **menu à gauche** mène à chaque écran, rangés dans l'ordre du travail (Synthèse, Données,
   Modèle, Livrables, Aide), avec un badge d'état. En bas de chaque écran, **« ← Précédent »** et
   **« Suivant → »** pour avancer sans se perdre. « Changer de fichier » en haut à droite.
   Écrans :
   - **Contrôles des données** : erreurs et avertissements (onglet, ligne, colonne, id) ;
   - **Vérification Excel ↔ SysML** : preuve que la traduction est fidèle (voir plus bas) ;
   - **Aperçu du modèle** : cas d'usage, acteurs, étapes dans l'ordre, déclencheurs, besoins ;
   - **Analyses** : quatre graphes. **Besoins × étapes** (matrice ; en rouge un besoin servi par
     aucune étape ou une étape sans besoin), puis, lus dans les codes SysML comme le lecteur de
     modèle : **Couverture des besoins** (nombre d'étapes qui satisfont chaque besoin),
     **Parcours émotionnel** (émotion −5 à +5 de chaque persona, étape par étape, par cas d'usage),
     **Composants × étapes** (à quelle étape chaque composant change d'état, tous cas d'usage).
     Survoler un point ou une case pour le détail ; « Voir en tableau » sous chaque graphe ;
   - **Modèle lu dans le SysML** : le modèle redessiné à partir des seuls codes `.sysml` (voir plus bas) ;
   - **Export vers CATIA** : un onglet par code (taille, « Copier ce code », « Télécharger .sysml »),
     « Tous les codes (.zip) », traçabilité .xlsx, rapport .txt, couverture ;
   - **Assistant IA** : chat sur le modèle avec Claude, Codex (abonnements) ou une IA avec clé API.
   - **Comment fonctionne le traducteur** : le parcours Excel → SysML, la correspondance des onglets, les règles d'écriture, le rôle de chaque fichier Python, et un élément du fichier chargé suivi de l'Excel jusqu'au code.

**Présentation R-monie.** La page présente l'outil comme le produit d'une startup, R-monie,
proposé à Renault pour le concept E-Space. Tant qu'aucun fichier n'est chargé, l'accueil montre :
- ce que fait l'outil et ses résultats réels sur l'export E-Space (62 éléments sur 62 conformes,
  606 lignes de l'Excel retrouvées dans les codes, 4 codes sous la limite de CATIA Community) ;
- un exemple réel : la ligne 19 de l'onglet steps devient la ligne 162 du code UC4 ;
- un seul bouton : **Ouvrir un export UserShaker (.xlsx)**.

Charte : noir rubis et grenat, d'après la teinte « rubis noir » annoncée par Renault pour le
concept (teinte approchée, Renault ne publie pas de code couleur). Police : NouvelR, la police de
Renault, si elle est installée sur le PC (sa licence la réserve à Renault, elle n'est donc pas
fournie) ; sinon **Encode Sans**, police libre (licence OFL, `interface/page/lib/OFL-Encode-Sans.txt`).
Pas de logo Renault.

Animations : bibliothèque **GSAP** (avec ScrollTrigger), en copie locale dans `interface/page/lib`,
comme la police : pas besoin d'Internet. Elles ne changent que l'apparence : le trait de l'accueil
qui relie la ligne de l'Excel à la ligne de SysML (une fois, au chargement), l'arrivée des
résultats, la barre d'onglets qui reste en haut, l'ouverture des sections. Si « Réduire les
animations » est activé dans Windows ou dans le navigateur, la page ne bouge pas. Si GSAP ne se
charge pas, la page fonctionne comme sans animation.

### Ligne de commande

- **Le plus simple** : glisser le fichier `.xlsx` sur `traduire.bat`.
- Ou, depuis ce dossier : `python -m usershaker2sysml "export.xlsx" -o sortie`

Résultats dans `sortie\` :

| Fichier | Contenu |
|---|---|
| `UC1….sysml`, `UC2….sysml`… | un code par cas d'usage, à coller chacun dans son projet CATIA (Community) |
| `code_entier\<Projet>CodeEntier.sysml` | un seul code, tous les cas d'usage, pour CATIA Magic complet (sans limite) |
| `<Projet>_trace.xlsx` | traçabilité Excel ↔ codes + vérification par relecture |
| `<Projet>_rapport.txt` | contrôles, codes et tailles, couverture, vérification |

Code de sortie : 0 = prêt, 1 = produit mais à vérifier, 2 = aucun code (erreurs bloquantes).

## Importer dans CATIA

**CATIA Magic Community** : pour **chaque** code (un par cas d'usage). **CATIA Magic complet** :
une seule fois, avec le **code entier**.
1. Nouveau projet SysML v2 vide, clic droit sur le package **Model** > Textual Editor > Open.
2. Tout sélectionner, coller le code, appliquer.
3. Clic droit sur le package > Validation > Validate : aucune erreur attendue.
4. Diagramme : Action Flow View sur le `use case def`, y glisser les actions (« Create Symbols »),
   puis **Display Relations** : les flèches de succession apparaissent dans l'ordre des étapes.

## Où se trouve chaque information dans un code

| UserShaker | SysML v2 |
|---|---|
| projet, cas d'usage | `package UC<n><Nom>`, `use case def` (description, story, status) |
| personas | `part … : Persona` (ageCategory, gender, biography) |
| components, component_states | `part def` (role, description…) et `attribute states = "Off [id] ; …"` |
| user_needs | `requirement` (description, libraryName…) |
| use_case_personas | `actor … : Personas::Persona` |
| step_groups | `attribute stepGroups = "Charging [id]: 1-2 ; …"` dans le cas d'usage |
| step_component_states (grille) | `attribute grid<Composant> = "1: Off ; 3: Stowing > Stowed ; …"` (n° d'étape : état ; « > » = états successifs) |
| steps | `action` (description, triggerText), ordre = `first … then …` |
| step_triggers | `attribute triggerEvent / condition = "<composant> is <état>"` |
| step_user_needs | `satisfy Needs::…;` dans l'action |
| persona_step_feedback | `attribute feedback = "leaMartin +2 \| action \| insight [id] ; …"` dans l'action |
| id et nom exact de chaque élément | `doc /* id : nom */` ou `[id]` |

## Vérifier la traduction

Après chaque traduction, les codes sont **relus par un module indépendant**
(`relecture_complete.py`, qui n'utilise pas le traducteur) et comparés à l'Excel :

- persona, composant, besoin : présent, même nom, mêmes infos ; composant : mêmes états dans le même ordre ;
- cas d'usage : nom, acteurs, nombre d'étapes, enchaînement complet, textes, groupes, composants ;
- étape : dans le bon cas d'usage, nom, **rang** dans l'enchaînement, déclencheurs, besoins
  servis, groupe, textes, **grille** (état de chaque composant à cette étape) et **ressentis**.

Résultat sur l'export Renault : **62/62 éléments conformes**, **606/606 lignes de l'Excel
retrouvées** dans les codes. La relecture détecte un code modifié à la main (case de grille,
score, état, groupe, besoin, texte, déclencheur, ordre, étape supprimée).

Où le voir : onglet « Vérification Excel ↔ SysML » (par élément, ou toutes les correspondances
avec recherche ; « UC4 · ligne N » ouvre le code à la bonne ligne), fichier `_trace.xlsx`
(onglets Codes, Traçabilité, Vérification), rapport.

## Ce que fait le traducteur

1. **Lecture** (`lecture.py`) : xlsx, ou données déjà en mémoire (`depuis_dict`).
2. **Contrôles** (`controles.py`) contre le schéma officiel du readme UserShaker (`schema.py`) :
   une erreur sur une donnée utilisée **bloque** (on ne produit pas un modèle faux) ;
   les avertissements sont à remonter à l'équipe UX.
3. **Codes** (`rendu_cas_usage.py`) : un code par cas d'usage, écriture compacte, noms SysML
   valides (mots réservés évités), découpage automatique si un code dépasse 20 000 caractères.
   Personas, composants ou besoins rattachés à aucun cas d'usage sont écrits avec le cas d'usage 1.
4. **Relecture, traçabilité, couverture** (`relecture_complete.py`, `traduction_complete.py`, `trace_xlsx.py`).

L'ancienne traduction résumée en un seul code (`traduire`, validée 62/62 dans CATIA, sans
grille ni ressentis) reste dans le paquet, mais n'est plus utilisée par le site.

### Codes des contrôles

| Code | Sens | Bloque ? |
|---|---|---|
| E01 | onglet nécessaire absent | oui |
| E02 | colonne absente | si utilisée |
| E03 | valeur obligatoire vide | si utilisée |
| E04 | type invalide (entier, vrai/faux) | si utilisée |
| E05 | valeur hors liste autorisée | si utilisée |
| E06 | score d'émotion hors -5…+5 | non |
| E07 | id en double | si utilisée |
| E08 | lien vers une ligne inexistante (y compris grille, ressentis, composants d'un cas d'usage) | si utilisée |
| E09 | état qui n'appartient pas au composant | oui (déclencheurs) |
| E10 | groupe d'un autre cas d'usage | non |
| E11 | boucle dans les composants parents | non |
| E20 | code au-delà de la limite CATIA (ne devrait pas arriver : découpage automatique) | non (mais « à vérifier ») |
| E21 | la relecture des codes trouve un écart avec l'Excel | non (mais « à vérifier ») |
| E22 | une étape seule dépasse la limite de 20 000 caractères | oui |
| A01 | onglet inconnu | — |
| A02 | espaces en début/fin d'id ou de nom | — |
| A03 | lien vers un onglet absent du fichier | — |
| A04 | lien en double | — |
| A05 | positions avec trou ou doublon | — |
| A06–A08 | meta absente / version / décomptes faux | — |
| A09 | kind trigger/condition mal ordonné | — |
| A10 | besoin servi par aucune étape | — |
| A11 | étape qui ne sert aucun besoin | — |
| A12 | étape sans déclencheur structuré | — |
| A13–A14 | cas d'usage sans étape / sans persona | — |
| A15–A16 | persona / composant jamais utilisé | — |
| A17–A18 | ressenti manquant / persona hors du cas d'usage | — |
| A19 | noms en double | — |

## Lecteur de modèle : vue technique et vue UX

Dans « Modèle lu dans le SysML », chaque vue (ensemble, cas d'usage, composants) existe en deux styles :
**Vue technique** (par défaut : schémas en colonnes, au plus près du code SysML) et **Vue UX** (schémas de
lecture : rubans, parcours, graphe des états), au choix par les boutons à côté des vues. La fiche d'un
élément (clic sur une persona, un composant…) s'ouvre dans un panneau flottant à droite, par-dessus le
schéma ; ✕ ou Échap pour la fermer. Bouton « Télécharger le schéma (.png) » pour les slides.
Repris du travail UX de l'équipe (dossier V3).

## Apparence

Charte R-monie, reprise de la présentation de l'équipe (`interface/page/theme.css`) :
- logo RM vectorisé (`interface/page/lib/logo_*.svg` : monogramme, logo complet pour fond sombre ou
  clair, texte seul), aussi utilisé comme icône d'onglet ;
- polices libres (licence OFL, fichiers dans `interface/page/lib/`) : **Space Grotesk** pour les titres,
  **IBM Plex Sans** pour le texte ;
- couleurs : nuit `#1A0B0E`, rubis `#E8546C`, grenat `#6E1734`, gris clair `#EEEAEC` ;
- titres de section suivis d'une étiquette numérotée en capitales rubis (« 02. DONNÉES · TRAÇABILITÉ ») et
  d'un trait rubis, cartes à coins arrondis et filet fin ; bandeau sombre, contenu sur fond clair.

Le fichier ne fait que surcharger l'apparence : le supprimer (et sa ligne `<link>` dans `index.html`)
rend l'ancien style.

## Assistant IA

L'onglet **Assistant IA** permet de poser des questions sur le modèle. L'IA reçoit **uniquement du
SysML** : la liste des codes, le résultat des contrôles automatiques et **les passages des codes
liés à la question** (recopiés tels quels, avec les numéros de ligne des fichiers). **Aucun résumé
de l'Excel** n'est envoyé. Consignes : se baser sur les codes, ne rien inventer, citer le code et
la ligne (ex. UC4 ligne 42), dire quand l'information n'est pas dans ce qu'elle a reçu. Un passage
identique dans plusieurs codes (une persona déclarée dans chaque code qui l'utilise) n'est envoyé
qu'une fois, avec la mention « passage identique dans UC2 lignes … ». Elle ne modifie rien.

L'assistant sert aussi de **guide du site** : « où je vois les émotions des personas ? ». Il répond
en une à trois lignes avec un bouton qui ouvre directement la bonne section (et la bonne vue, par
exemple Analyses › Parcours émotionnel). Pour un élément précis (« où voir le Floating front logo ? »),
le bouton ouvre directement cet élément : le composant sélectionné avec sa fiche dans « Modèle lu dans
le SysML », l'étape dans son cas d'usage, ou la recherche faite dans la Vérification. Il reçoit pour cela une courte description des sections
du site, comptée dans le budget de tokens.

**Revenir en arrière** : après un clic sur « UC4 ligne N » (qui ouvre le code dans Export vers
CATIA) ou sur un bouton de l'assistant, un bouton « ← Retour à … » apparaît en bas de l'écran. Il
ramène à la section d'où l'on vient, au même endroit de la page, et fait clignoter la ligne cliquée.
Effort de réflexion bas, consigne de répondre court, réponse affichée au fur et à mesure.

**Budget de tokens par question** (`BUDGETS` dans `interface/assistant.py`, estimation prudente) :
- **clé API** : 6 000 tokens au plus (4 500 en entrée + 1 500 pour la réponse), historique des
  4 derniers messages ; tient sous la limite gratuite de Groq (8 000 tokens par minute) ;
- **Claude** et **Codex** : 16 000 en entrée (extraits plus larges), 6 derniers messages ;
- **Copier pour un chat externe** : les codes entiers (environ 28 000 tokens), toujours sans résumé de l'Excel.
Les passages sont choisis d'après la question (noms d'étapes, de composants, de besoins, « UC2 »,
« étape 3 », « ligne 162 »…) : une question précise donne une meilleure réponse. Le nombre réel de
tokens est affiché sous chaque réponse.

En haut de l'onglet, choisir l'assistant : **Claude (ton abonnement)**, **Codex (ton abonnement
ChatGPT)** ou **Clé API**. Par défaut : Claude s'il est prêt, sinon Codex, sinon la clé API.
Sans assistant ou sans Internet : « Copier pour un chat externe ».

Avec Claude et avec Codex, deux boutons choisissent le type de raisonnement (le mode est rappelé
sous chaque réponse) :
- **Raisonnement rapide** : Claude Haiku, effort bas ; Codex, effort `low`. Plus rapide, mais
  Haiku s'est trompé sur des questions qui croisent beaucoup de données.
- **Raisonnement poussé** (par défaut) : Claude Sonnet, effort bas ; Codex, effort `medium`.
  Plus lent, plus fiable.

### Claude (ton abonnement, sans clé d'API)

L'interface passe par **Claude Code** installé sur le PC (abonnement, pas d'API payante).
1. Installer (PowerShell) : `irm https://claude.ai/install.ps1 | iex`
2. Se connecter : `& "$env:USERPROFILE\.local\bin\claude.exe"`, choisir l'abonnement, puis `/exit`.
3. Relancer l'interface : « Claude (ton abonnement) — prêt ».

Claude est lancé sans aucun outil (il ne peut ni lire ni modifier de fichier), dans un dossier
temporaire vide, sans serveur MCP ; `ANTHROPIC_API_KEY` n'est pas transmise. Réglage
facultatif : `CLAUDE_CLI` (chemin de claude.exe). Les deux modes sont définis dans `MODES`
(`interface/assistant.py`).

### Codex (ton abonnement ChatGPT, sans clé d'API)

Pour qui a ChatGPT (Plus, Pro, Business…) et pas Claude. L'interface passe par **Codex CLI**
installé sur le PC.
1. Installer Node.js (https://nodejs.org), puis dans PowerShell : `npm install -g @openai/codex`
2. Se connecter : `codex login`, choisir **Sign in with ChatGPT** ; vérifier avec `codex login status`.
3. Relancer l'interface : « Codex (ton abonnement ChatGPT) — prêt ».

Codex est lancé avec `codex exec` en **lecture seule** (`--sandbox read-only`), dans un dossier
temporaire vide, sans session enregistrée (`--ephemeral`) ; `OPENAI_API_KEY` et `CODEX_API_KEY`
ne sont pas transmises, pour rester sur l'abonnement. Le modèle est celui de ton compte Codex ;
pour en imposer un : variable `CODEX_MODELE`. Autre réglage facultatif : `CODEX_CLI` (chemin de
codex). La réponse arrive en une fois (pas au fur et à mesure comme avec Claude). Les deux
modes sont définis dans `MODES_CODEX` (`interface/assistant.py`). Testé avec un faux Codex qui
reproduit le format documenté ; pas encore avec un vrai compte ChatGPT.

### Clé API (une autre IA)

N'importe quelle IA compatible avec l'API « chat completions » d'OpenAI (Groq, OpenAI,
Mistral, OpenRouter…). Copier `cle_api.exemple.txt` en **`cle_api.txt`** (même dossier) et y
écrire sa propre clé (Bloc-notes) :

```
cle = la_clé
url = https://api.groq.com/openai/v1/chat/completions
modele = openai/gpt-oss-120b
```

`url` et `modele` sont facultatifs (par défaut : Groq, `openai/gpt-oss-120b`). L'ancien fichier
`cle_groq.txt` est encore lu si `cle_api.txt` ne contient pas de clé. Variables d'environnement
possibles : `API_KEY`, `API_URL`, `API_MODELE`.

**Limite gratuite :** Groq gratuit accepte 8 000 tokens par minute ; une question en envoie 6 000
au plus. Deux questions longues dans la même minute peuvent donc être refusées : la page
l'indique, il suffit d'attendre une minute.

**Sécurité :** la clé est un mot de passe. Elle n'est lue que par le serveur local, jamais envoyée
au navigateur. Ne jamais partager `cle_api.txt` ni `cle_groq.txt` (chat, mail, GitHub).

**Confidentialité :** à chaque question, les données et les codes partent chez l'assistant choisi,
hors du PC.

## Brancher des propositions de corrections (IA) plus tard

**Dans l'interface** : écrire `proposer(ds, problemes)` dans `interface/assistant.py`
(appelé par `POST /api/assistant`), qui renvoie une liste de propositions
`{onglet, id, colonne, avant, apres, raison, code}`. Le format est décrit en tête du fichier.
L'API du serveur (`POST /api/analyser`, `POST /api/assistant`) est décrite en tête
de `interface/serveur.py`.

**Côté traducteur** : le contrat d'entrée est le schéma de `schema.py`. Un assistant doit renvoyer des
données au **même format** ; rien d'autre ne change :

```python
from usershaker2sysml import lire_xlsx, depuis_dict, ecrire_xlsx, controler, traduire_complet

ds = lire_xlsx("export.xlsx")
problemes = controler(ds)          # liste de Probleme (code, message, onglet, ligne, id...)
# ... l'assistant propose des corrections, l'ingénieur valide ...
ds_corrige = depuis_dict(donnees_corrigees)   # ou lire_xlsx("export_corrige.xlsx")
res = traduire_complet(ds_corrige)  # res.codes, res.problemes, res.verification, res.trace_detail
ecrire_xlsx(ds_corrige, "export_corrige.xlsx")   # garder la version corrigée
```

## Lire le modèle SysML sur le site

L'onglet **Modèle lu dans le SysML** (et la page **`/modele`**, lien « Les ouvrir dans le lecteur
de modèle » sur l'accueil) dessine le modèle **en ne lisant que le texte des codes `.sysml`** :
ni l'Excel, ni le traducteur. C'est la preuve que l'information est bien dans le SysML.

- Quatre vues : **ensemble** (personas, cas d'usage, besoins, composants), **un cas d'usage**
  (étapes et `first … then`, groupes, déclencheurs, besoins satisfaits, grille composant × étape,
  ressentis), **un composant** (ses états et les étapes qui le mettent dans chaque état),
  **traçabilité** (besoin → étapes → cas d'usage, en rouge ce qui n'est pas couvert).
- **Plein écran** : bouton « ⛶ Plein écran » (toute la fenêtre, et tout l'écran si le navigateur
  l'accepte) ; pour revenir : « ✕ Quitter le plein écran » ou la touche Échap. La page `/modele`
  utilise toute la largeur de la fenêtre.
- Le lecteur ouvre aussi le **code entier** (un seul fichier, tous les cas d'usage).
- Un clic sur un élément ouvre sa **fiche** : nom SysML, identifiant UserShaker, fichier et ligne
  du code, avec l'extrait du code. Double-clic : ouvrir la vue de l'élément.
- **Lire des fichiers .sysml…** : afficher n'importe quels codes produits par le traducteur (par
  exemple ceux du dossier `sortie`), un ou plusieurs, cas d'usage coupés en parties compris.
- Une référence introuvable (un `satisfy` vers un besoin absent, un état inconnu dans une grille)
  n'est jamais inventée : elle est listée à part.

Lecteur : `usershaker2sysml/modele_sysml.py`, qui s'appuie sur la relecture des codes déjà utilisée
pour la vérification (`relecture_complete.py`). Page : `interface/page/modele.js`, `modele.css`,
`modele.html`. Adresses : `/api/modele` (graphe) et `/api/grammaire` (contrôle ci-dessous).

**Contrôle de grammaire OMG (facultatif).** Si **SysML2Tools** est installé, le site lance
`sysml2tools lint` sur les codes et affiche le résultat (grammaire SysML v2 officielle de l'OMG,
0 erreur sur les 4 codes de l'export E-Space, test du 5 nov. 2026). Installation, une fois :

    winget install Microsoft.DotNet.SDK.8
    dotnet tool install -g DemaConsulting.SysML2Tools.Tool --version 0.1.0-beta.5

(puis relancer l'interface). Sans lui, le site affiche « non installé » et tout le reste marche.
Sa version beta lit les codes sans erreur mais ne modélise pas encore le contenu des cas d'usage
(étapes, enchaînements, satisfy) ni les valeurs des attributs : c'est pourquoi l'affichage passe
par notre lecteur, et SysML2Tools sert de contrôle indépendant.
