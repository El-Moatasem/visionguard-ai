"""SceneOps bounded object-concept registry; SAM receives noun phrases, never free-form commands."""
from __future__ import annotations

CONCEPT_PROMPTS = {
    "person": "person",
    "forklift": "forklift",
    "car": "car",
    "shopping_cart": "shopping cart",
    "cardboard_box": "cardboard box",
    "excavator": "excavator",
}


def normalize_concept(value: str) -> str:
    key = value.strip().lower().replace(" ", "_")
    if key not in CONCEPT_PROMPTS:
        raise ValueError(f"Unsupported concept {value!r}; select from the approved SceneOps registry")
    return key


def concept_prompt(key: str) -> str:
    return CONCEPT_PROMPTS[normalize_concept(key)]
