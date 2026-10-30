# Muse Spark reviewer-approved rule drafting

The optional `POST /api/v1/rules/interpret` endpoint accepts a short plain-English instruction (`description`, 8–500 characters). It sends only this text to Muse Spark 1.3 using `MODEL_API_KEY`; it never sends source footage or tracking observations.

It requests constrained JSON (`name`, `rule_type`, `min_duration_seconds`, `rationale`), with the two supported rule types. The response is validated in `RuleDraft`. No code execution, natural-language expression parsing, unsafe rule DSL, or arbitrary inferred zones exist.

The frontend displays the draft, its rationale and an explicit **Approve and apply draft** button. The user must verify the choice of rule and determine the operating zone. A draft is not automatically executed.

**Limitations:** The model may misunderstand instructions despite JSON conformance. Manual selection remains available without Meta credits. Remote calls may return rate limits or billing errors. Error responses avoid echoing raw provider details. Demo-only backend has no authentication or per-user budget policy.
