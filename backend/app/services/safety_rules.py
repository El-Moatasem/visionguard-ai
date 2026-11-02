"""Constrained, reviewer-approved safety policies. No automatic danger verdicts."""
from __future__ import annotations

from typing import Literal
from backend.app.services.sceneops_concepts import CONCEPT_PROMPTS, normalize_concept
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NormalizedZone(StrictModel):
    name: str = Field(default="Operating area", min_length=1, max_length=64)
    x_min: float = Field(ge=0, le=1, allow_inf_nan=False)
    y_min: float = Field(ge=0, le=1, allow_inf_nan=False)
    x_max: float = Field(ge=0, le=1, allow_inf_nan=False)
    y_max: float = Field(ge=0, le=1, allow_inf_nan=False)

    @model_validator(mode="after")
    def nonempty(self):
        if self.x_max <= self.x_min or self.y_max <= self.y_min:
            raise ValueError("Zone must have positive width and height")
        return self


class RuleSpec(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    rule_type: Literal["person_in_zone", "person_and_forklift_in_zone", "object_in_zone", "object_zone_entry"]
    zone: NormalizedZone
    concept: str | None = None
    # Reviewer-identified operator tracks; applies ONLY to forklift co-presence.
    excluded_operator_track_ids: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def validate_concept(self):
        if self.rule_type in {"object_in_zone", "object_zone_entry"}:
            if self.concept is None:
                raise ValueError("A concept is required for a generic SceneOps rule")
            self.concept = normalize_concept(self.concept)
        elif self.concept is not None:
            raise ValueError("Legacy rule types cannot select a different concept")
        if self.excluded_operator_track_ids:
            if self.rule_type != "person_and_forklift_in_zone":
                raise ValueError("Operator track exclusions apply only to forklift co-presence")
            if len(set(self.excluded_operator_track_ids)) != len(self.excluded_operator_track_ids):
                raise ValueError("Operator track exclusions must be unique")
            if any(not (track.startswith("person:") and 7 < len(track) <= 120)
                   for track in self.excluded_operator_track_ids):
                raise ValueError("Operator tracks must have validated person: identifiers")
        return self
    min_duration_seconds: float = Field(default=0.5, gt=0, le=30, allow_inf_nan=False)
    # Missing source frame indices allowed for a *provisional* association, never proof of visibility.
    max_observation_gap_frames: int = Field(default=2, ge=0, le=30)


class EvaluateRequest(StrictModel):
    rule: RuleSpec


class InterpretRequest(StrictModel):
    description: str = Field(min_length=8, max_length=500)


class RuleDraft(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    rule_type: Literal["person_in_zone", "person_and_forklift_in_zone", "unsupported"]
    min_duration_seconds: float = Field(gt=0, le=30, allow_inf_nan=False)
    rationale: str = Field(min_length=1, max_length=300)


# Exact schema fields intentionally required for Meta's constrained JSON output.
DRAFT_JSON_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "visionguard_rule_draft",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "rule_type": {"type": "string", "enum": ["person_in_zone", "person_and_forklift_in_zone", "unsupported"]},
                "min_duration_seconds": {"type": "number"},
                "rationale": {"type": "string"},
            },
            "required": ["name", "rule_type", "min_duration_seconds", "rationale"],
            "additionalProperties": False,
        },
    },
}
