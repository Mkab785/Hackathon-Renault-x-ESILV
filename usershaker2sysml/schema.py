"""
Schéma d'export UserShaker 1.0, recopié de l'onglet "readme" du fichier
"Renault E-Space concept_export_v1.0.xlsx". Rien n'est ajouté : si le readme
change, c'est ce fichier qu'il faut mettre à jour.

C'est le CONTRAT d'entrée du traducteur : un xlsx exporté par UserShaker, ou un
xlsx corrigé par un assistant (IA ou humain), doit le respecter.

Pour chaque colonne :
    type      : "id", "text", "int", "enum", "bool", "url"
    required  : True si le readme dit "always filled"
    values    : valeurs autorisées pour un enum
    fk        : onglet visé par une clé étrangère (ex. "use_cases")
"""

SCHEMA_VERSION = "1.0"


def col(type_, required=False, values=None, fk=None):
    return {"type": type_, "required": required, "values": values, "fk": fk}


# Ordre des onglets = ordre du readme.
SHEETS = {
    "meta": {
        "key": col("text", True),
        "value": col("text", True),
    },
    "use_cases": {
        "use_case_id": col("id", True),
        "position": col("int", True),
        "name": col("text", True),
        "description": col("text"),
        "story": col("text"),
        "status": col("enum", True, ["new", "in_progress", "ready", "frozen"]),
        "folder": col("text"),
    },
    "step_groups": {
        "group_id": col("id", True),
        "use_case_id": col("id", True, fk="use_cases"),
        "position": col("int", True),
        "name": col("text", True),
        "color": col("text"),
    },
    "steps": {
        "step_id": col("id", True),
        "use_case_id": col("id", True, fk="use_cases"),
        "position": col("int", True),
        "name": col("text", True),
        "description": col("text"),
        "trigger_text": col("text"),
        "group_id": col("id", fk="step_groups"),
        "note": col("text"),
        "image_url": col("url"),
    },
    "step_triggers": {
        "trigger_id": col("id", True),
        "step_id": col("id", True, fk="steps"),
        "kind": col("enum", True, ["trigger", "condition"]),
        "position": col("int", True),
        "component_id": col("id", True, fk="components"),
        "state_id": col("id", True, fk="component_states"),
        "operator": col("enum", True, ["is"]),
    },
    "personas": {
        "persona_id": col("id", True),
        "name": col("text", True),
        "age_category": col("enum", False, ["child", "young_adult", "active_adult", "senior"]),
        "gender": col("enum", False, ["female", "male", "other"]),
        "biography": col("text"),
        "color": col("text"),
        "library_id": col("id"),
        "library_name": col("text"),
        "library_link_mode": col("enum", False, ["linked", "copied"]),
    },
    "use_case_personas": {
        "use_case_id": col("id", True, fk="use_cases"),
        "persona_id": col("id", True, fk="personas"),
        "position": col("int", True),
    },
    "persona_step_feedback": {
        "feedback_id": col("id", True),
        "step_id": col("id", True, fk="steps"),
        "persona_id": col("id", True, fk="personas"),
        "is_present": col("bool", True),
        "action": col("text"),
        "insight": col("text"),
        "emotion_score": col("int"),
    },
    "components": {
        "component_id": col("id", True),
        "name": col("text", True),
        "role": col("enum", True, ["trigger", "reactive", "object"]),
        "category": col("text"),
        "parent_component_id": col("id", fk="components"),
        "description": col("text"),
        "library_id": col("id"),
        "library_name": col("text"),
        "library_link_mode": col("enum", False, ["linked", "copied"]),
    },
    "component_states": {
        "state_id": col("id", True),
        "component_id": col("id", True, fk="components"),
        "position": col("int", True),
        "name": col("text", True),
        "description": col("text"),
    },
    "use_case_components": {
        "use_case_id": col("id", True, fk="use_cases"),
        "component_id": col("id", True, fk="components"),
        "position": col("int", True),
    },
    "step_component_states": {
        "step_id": col("id", True, fk="steps"),
        "component_id": col("id", True, fk="components"),
        "state_id": col("id", True, fk="component_states"),
        "sequence": col("int", True),
    },
    "step_unused_components": {
        "step_id": col("id", True, fk="steps"),
        "component_id": col("id", True, fk="components"),
    },
    "user_needs": {
        "user_need_id": col("id", True),
        "name": col("text", True),
        "description": col("text"),
        "reference_url": col("url"),
        "library_id": col("id", True),
        "library_name": col("text"),
    },
    "step_user_needs": {
        "step_id": col("id", True, fk="steps"),
        "user_need_id": col("id", True, fk="user_needs"),
    },
}

# Colonne "id" propre à chaque onglet (les onglets de liaison n'en ont pas).
PRIMARY_KEY = {
    "use_cases": "use_case_id",
    "step_groups": "group_id",
    "steps": "step_id",
    "step_triggers": "trigger_id",
    "personas": "persona_id",
    "persona_step_feedback": "feedback_id",
    "components": "component_id",
    "component_states": "state_id",
    "user_needs": "user_need_id",
}

# Les positions vont 1, 2, 3… sans trou "à l'intérieur de leur parent" (readme).
# onglet -> (colonne de position, colonne(s) du parent)
POSITION_GROUPS = {
    "use_cases": ("position", ()),
    "step_groups": ("position", ("use_case_id",)),
    "steps": ("position", ("use_case_id",)),
    "step_triggers": ("position", ("step_id",)),
    "use_case_personas": ("position", ("use_case_id",)),
    "component_states": ("position", ("component_id",)),
    "use_case_components": ("position", ("use_case_id",)),
    "step_component_states": ("sequence", ("step_id", "component_id")),
}

# Onglets indispensables pour produire le modèle SysML (format CATIA Community).
REQUIRED_FOR_TRANSLATION = [
    "use_cases", "steps", "step_triggers", "personas", "use_case_personas",
    "components", "component_states", "user_needs", "step_user_needs",
]

# Score d'émotion : "From -5 (very negative) to +5 (very positive)".
EMOTION_MIN, EMOTION_MAX = -5, 5
