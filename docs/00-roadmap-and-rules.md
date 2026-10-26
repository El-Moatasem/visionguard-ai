# Roadmap, rules, and definition of done

## Competition
- Track: Indie Developer. Problem: Push the Frontier.
- The participant guide specifies **Oct 27–Nov 4** for building, **Nov 4, 9 PM Eastern Time** for submission, public repository, 3-minute video, and clearly labeled work built during the hackathon.
- This starter was generated Oct 26 as pre-event reference material. Do not imply otherwise. Verify reuse rules with organizers.
- VisionGuard must go beyond a simple image analyzer; natural-language rules + temporal object identities + evidence and reproducible evaluation are the intended differentiators.
- Confirm that changing the application idea from CI Autopilot is permitted before final submission.

## Date compression
The six user-proposed milestones contain ten notional days, but the guide identifies nine calendar building days. Suggested concrete schedule:
- Tue Oct 27: Day 1 — API and SAM verification.
- Wed Oct 28: Day 2 — foundation.
- Thu–Fri Oct 29–30: Days 3–4 — tracking.
- Sat–Sun Oct 31–Nov 1: Days 5–6 — rules.
- Mon–Tue Nov 2–3: Days 7–8 — dashboard.
- Tue–Wed Nov 3–4: Days 9–10 — benchmark/demo **overlapping final dashboard day**. Freeze new scope by Nov 3 evening.
- Time zone: organizer deadline Eastern Time; check Discord before finalizing.

## Source attribution
- Hosted SAM and Muse integrations: Meta Model API.
- Parsers: third-party `meta_sam_parser` package. Preserve attribution and applicable license.
- Never imply the algorithm was developed or trained from scratch.
- Track contributions with dated git commits, issue logs, and a section in demo explaining the hackathon-specific work.

## Non-goals
- Real-time safety certification or emergency alarm replacement.
- Uncalibrated physical distance, speed or collision probability.
- Identifying individual workers or recording them without permission.
- Training a model, supporting all camera types, or full commercial compliance in ten days.

## Minimum demo acceptance criteria
1. Reviewer uploads/loads an authorized short clip.
2. SAM provides genuine tracked object identities for two prompt categories, or evidence makes the limitation explicit.
3. Reviewer enters a safety rule in plain English; Muse converts it to a strictly validated structured form.
4. A deterministic temporal engine produces reproducible candidate events with evidence.
5. Positive, negative, and ambiguous clips are presented with clear disclaimers.
6. Judges can replay video and inspect a timestamped explanation.
7. Public GitHub, clean tests, runnable instructions, working demo and 3-minute video.


## Optional accelerated solo MVP sprint (5 days)

This alternative schedule compresses the original ten-stage-day plan without changing the event submission deadline:

1. **Model validation:** Verify Meta credentials and real SAM tracks.
2. **Video prototype:** Upload/playback and early overlays.
3. **Tracking + rules:** Normalize identities and translate one safety rule.
4. **Evidence workflow:** Deterministic alert, timestamp, incident review.
5. **Evaluation + demo:** Positive/negative/uncertain cases and a 3-minute video.

Use **feature-based branch names**, never calendar-based names; see `09-git-workflow.txt`.
Reduce scope rather than skipping validation if computer vision processing requires longer.
