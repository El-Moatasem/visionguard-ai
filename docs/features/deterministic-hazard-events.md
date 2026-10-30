# Deterministic observed-event rules

The word *hazard* means **a potential rule-defined situation worth reviewing**, not a verified unsafe condition.

1. Use SAM 3.1's saved per-frame boxes and fragment labels.
2. Check whether each actor's **person bottom-center (floor-contact proxy) or forklift box center** falls in a normalized human-defined rectangle.
3. For co-presence, require a person and forklift **in the same observed frame and same zone**. This does not measure motion or 3D separation.
4. Start an episode only when the *same actor fragment(s)* satisfy the condition for the reviewer-specified duration in directly observed consecutive source frames. Reset on missing frames, changes of fragment, or zone exit.
5. Return start/end frame indices and approximate times when FPS is available. An event can be reviewed by clicking it in the UI.
6. Return explicit uncertainty metadata for missing tracking observations. Localize gaps to the monitored region; return review items and observed events independently.

The absence of matching detections is not a safety guarantee. Users must review the original scene and the provenance of tracking results. This is a research and demonstration tool, not a machine-safety interlock or emergency service.
