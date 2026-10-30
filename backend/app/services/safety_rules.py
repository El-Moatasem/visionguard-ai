"""Constrained safety policy model. Zones are reviewer-defined; Muse never controls geometry.

A match is an observed rule condition, NOT a confirmed physical danger or safety verdict.
"""
from __future__ import annotations

from typing import Literal
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
    rule_type: Literal["person_in_zone", "person_and_forklift_in_zone"]
    zone: NormalizedZone
    min_consecutive_frames: int = Field(default=3, ge=1, le=60)


class EvaluateRequest(StrictModel):
    rule: RuleSpec


class InterpretRequest(StrictModel):
    description: str = Field(min_length=8, max_length=500)


class RuleDraft(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    rule_type: Literal["person_in_zone", "person_and_forklift_in_zone"]
    min_consecutive_frames: int = Field(ge=1, le=60)
    rationale: str = Field(max_length=300)


# Constrained model output; no arbitrary Python, executable DSL, or zone positions.
DRAFT_JSON_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "visionguard_rule_draft",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "rule_type": {"type": "string", "enum": ["person_in_zone", "person_and_forklift_in_zone"]},
                "min_consecutive_frames": {"type": "integer"},
                "rationale": {"type": "string"},
            },
            "required": ["name", "rule_type", "min_consecutive_frames", "rationale"],
            "additionalProperties": False,
        },
    },
}
