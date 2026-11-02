# VisionGuard AI — final validation runbook

## What this release hardening changes

- Conservative geometry-based seated forklift **operator candidate** detection for the co-presence rule, with a `needs_review` record instead of a silent model-identity claim.
- Reviewer-confirmed operator track exclusions selected in the rule panel; explicit exclusions and heuristic candidates reported separately.
- Existing `person_in_zone`, `object_in_zone`, and `object_zone_entry` semantics retained. The latter still requires adjacent observed outside→inside frames.
- All **six synthetic replay fixtures** checked by a standalone, offline acceptance runner.
- Restores an older tracked Yarn v1 lockfile from commit `b9243f3` *only when missing*, then you must refresh it with current dependencies and commit it. The installer doesn't make external network calls.
- Ignores generated `frontend/next-env.d.ts` in git (but does not remove it from the git index; do that manually).
- Tightens the *illustrative* warehouse demo zone; you must draw a correct lane for each actual clip rather than trust the preset.
- Removes root-level docs/assets duplicates only when byte-for-byte identical to versions under `docs/`.
- Adds a hackathon feature-disclosure section to README when absent.

## Apply safely

```bash
# From the existing repository root; keep a clean checkpoint first.
git status --short
git switch -c fix/final-hackathon-hardening
python3 /path/to/VisionGuard_Final_Release_Hardening/apply_release.py --repo .
python3 /path/to/VisionGuard_Final_Release_Hardening/apply_release.py --repo . --apply
```

The dry run checks all anchors first; any unexpected local edits cause a SAFE STOP before writing. Backups are created beside your repository.

## CI and generated Next.js files

```bash
# At repository root. Ignore generated Next.js declaration files but keep them on disk.
git rm --cached frontend/next-env.d.ts  # only if tracked
cd frontend
corepack enable
yarn install             # reconcile historic lockfile with the current package.json
yarn install --frozen-lockfile
yarn typecheck
yarn build
cd ..
git add frontend/yarn.lock .gitignore
```

Do not push until `frontend/yarn.lock` exists and these checks pass. Never fabricate the yarn.lock manually.

## Back-end and all demos

```bash
source .venv/bin/activate
python -m pytest backend/tests/test_operator_exclusion.py -v
python -m pytest backend/tests -q
python -m backend.scripts.verify_all_replays
python -m compileall -q backend
```

| Demo | Route | Expected test |
| --- | --- | --- |
| Warehouse co-presence | `/replay?scenario=warehouse-copresence` | Observed event |
| Occlusion review | `/replay?scenario=occlusion-review` | Needs review around the missing observations |
| Clear aisle | `/replay?scenario=clear-aisle` | No match |
| Parking car dwell | `/replay?scenario=parking-car-dwell` | Observed event |
| Retail cart aisle | `/replay?scenario=retail-cart-aisle` | Observed event |
| Construction zone entry | `/replay?scenario=construction-zone-entry` | Observed entry event |

These are offline, synthetic **rule-engine** demonstrations. They do not prove SAM tracks those objects on real footage.

## Real warehouse video: must verify on your machine

1. Start backend without `--reload` while running billable requests. Use `FFMPEG_BIN=/opt/local/bin/ffmpeg` and `FFPROBE_BIN=/opt/local/bin/ffprobe` if on MacPorts.
2. If >25 MiB or >30 seconds, **Prepare for SAM** creates a short encoded clip. Analyze and play back the prepared clip, not the original.
3. Select `person` + `forklift`. Only click **Analyze** when you intend a paid request.
4. Pause and inspect boxes. Draw a **narrow, actual forklift lane** over the video; the illustrative preset is not a site-specific map.
5. In the Rule Panel, select a verified `person:*` operator track when you can identify the operator. Check the resulting exclusion count.
6. Confirm only pedestrians produce observed co-presence events. Geometry-only operator candidates remain visible as review items. Test a pedestrian near/in front of the vehicle.
7. Export a real evidence report; confirm source SHA-256, model, boxes, observed events and reviewer decisions.
8. Repeat the same workflow on a negative case; do not claim proof of safety from zero matches.

## Public demo / security

No public unauthenticated paid SAM API, upload storage or review persistence. Public Render should remain replay-only until authentication, quotas, retention and durable worker limits are implemented. Local run is the authentic dynamic video-analysis demonstration.

## Before recording / submitting

- [ ] All Python tests and six synthetic scenarios pass.
- [ ] Yarn frozen install, typecheck and production build pass.
- [ ] GitHub Actions green **after** the validated fix is pushed by you.
- [ ] One *real* SAM warehouse run shows driver/pedestrian handling correctly.
- [ ] Evidence exports are readable; screenshot included in README.
- [ ] README accurately separates real model output from six synthetic fixtures.
- [ ] Hackathon disclosure reflects actual commits and the prebuild baseline.
- [ ] Record 3-minute demo; submit before official deadline.

For one-command local validation:

```bash
bash /path/to/VisionGuard_Final_Release_Hardening/scripts/validate_release.sh
```

If `frontend/next-env.d.ts` is tracked, you must still run `git rm --cached frontend/next-env.d.ts` before staging. The archive builder intentionally excludes that generated file.
