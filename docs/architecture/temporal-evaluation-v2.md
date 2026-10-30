# Safety-event temporal architecture v2

`SAM summary records -> tracking_report (report schema 1, with gaps and SAM media metadata) -> safety_engine RuleSpec -> evidence-first response schema 2 -> SafetyRulePanel`.

**Only reviewer-approved rule specs are executable.** Muse Spark emits schema-constrained proposals or an explicit `unsupported` response with a reason; it never supplies region geometry or a danger verdict.

The temporal evaluator retains actor/source IDs with strict concept namespacing, refuses malformed numeric geometry, detects contradictory duplicate observations, and avoids across-object merging. A fully observed event requires consecutive source frame indices and consistent fragments. A bounded gap may produce a separate review candidate if actual observations meet the configured zone condition at sampled frames. Empty or missing frames do not constitute evidence of occupancy, and the engine does not extrapolate motion.

`event_count` counts observed matches only. `review_count` includes provisional candidate episodes plus localized relevant gaps. `uncertainty_count` refers to localized raw tracking gaps, not every sparse candidate. The headline `outcome` is merely the highest-priority class; always inspect the independent lists.

No automatic physical-distance, vehicle-speed, emergency intervention or safety-certification claim is supported.
