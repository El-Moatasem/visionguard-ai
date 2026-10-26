# Days 9–10 — Evaluation, final demo, submission (planned)

## Calendar note
Build period Oct 27–Nov 4 yields only nine dates; begin evaluations by Nov 2 and overlap final dashboard polish with Nov 3–4. Do **not** plan an extra day past the deadline.

## Evaluation plan
Use a small set of clips with clear rights. Manually mark event time windows before running the model. Include:
1. Positive: a pedestrian enters a defined forklift operating zone while equipment is moving.
2. Negative: a pedestrian remains outside the marked zone.
3. Ambiguous: occlusion/low resolution/motion uncertainty requires human review.

Report clip count, total annotated events, true positives, false positives, false negatives, event timestamp tolerance and limitations. Do not call small-sample measurements certified accuracy or accident prediction.

## Three-minute demo outline
- 0:00–0:20 — real-world problem and where Meta models enter.
- 0:20–0:50 — upload footage / show real SAM tracked objects.
- 0:50–1:25 — reviewer enters rule, Muse interprets it into a validated schema.
- 1:25–2:05 — show deterministic event timeline and replay evidence.
- 2:05–2:35 — compare positive, negative, ambiguous clips and performance report.
- 2:35–3:00 — architectural novelty, new hackathon-built code, limitations, GitHub link.

## Submission checklist
- [ ] Public repository is accessible with clean README and attributions.
- [ ] Exactly what was built during the hackathon is documented and shown.
- [ ] Tests pass in clean environment; live model workflow works with fresh inputs.
- [ ] 3-minute video and demo link available to judges without special login.
- [ ] Submitted before official Nov 4, 9 PM Eastern Time deadline.
- [ ] No embedded credentials, private footage, unlicensed media, or misleading safety claims.
