# VisionGuard AI — Real demo media candidates (2 Nov 2026)

These real stock photographs are for **illustrative gallery thumbnails only**. The six replay scenarios remain synthetic numeric fixtures, not frames from these videos or Meta SAM output. Images are from Unsplash pages marked free under the Unsplash License. Photo CDN URLs are referenced by the Gallery; if they fail to load, the original vector illustration appears. To bundle assets locally, download the photo from its source page and replace each `url` in `STOCK_PHOTOS` with `/demo-thumbnails/<name>.jpg` after placing the file under `frontend/public/demo-thumbnails/`.

The linked Pexels videos are **candidate footage**, not validated results. Download and use only if you have rights for your specific intended use. The Pexels Terms restrict certain AI/ML dataset and evaluation uses; don't presume that free stock-video licensing automatically authorizes uploading to a third-party model for evaluation. Where uncertain, obtain creator permission or use your own consented video. No video files are bundled.

| Synthetic scenario | Real thumbnail/photo source | Candidate real video source | Tracking concepts and rule | Notes |
|---|---|---|---|---|
| Warehouse co-presence | [Andy Sartori — forklift and worker](https://unsplash.com/photos/a-man-standing-in-a-warehouse-next-to-a-forklift-TFno87ae_dg) | [Worker approaching forklift](https://www.pexels.com/video/man-walking-towards-the-forklift-inside-the-warehouse-4294434/) | `person`, `forklift`; `person_and_forklift_in_zone` | Validate driver and pedestrian separately |
| Occlusion review | [Jhonatan Londono — forklift in warehouse](https://unsplash.com/photos/a-forklift-parked-inside-of-a-warehouse-_FF8CJbcios) | [Warehouse worker and equipment](https://www.pexels.com/video/man-working-inside-the-warehouse-4291728/) | `person`, `forklift`; co-presence plus gap review | Photo/video do not guarantee occlusion |
| Clear aisle | [Brian Wangenheim — empty warehouse](https://unsplash.com/photos/a-large-empty-warehouse-with-no-people-in-it-D7A6CiIFVk8) | [Warehouse worker in storage](https://www.pexels.com/video/warehouse-storage-with-worker-walking-38707991/) | `person`, `forklift`; negative control | Choose a zone with no qualifying match |
| Parking car dwell | [Iain — aerial parking lot](https://unsplash.com/photos/aerial-view-of-a-parking-lot-filled-with-cars-9Be9zl05K1k) | [Aerial cars in parking lot](https://www.pexels.com/video/aerial-view-of-busy-parking-lot-with-moving-vehicles-40242636/) | `car`; `object_in_zone` | Does not validate parking legality |
| Retail cart aisle | [Ninthgrid — shopper and cart](https://unsplash.com/photos/a-woman-pushing-a-shopping-cart-through-a-grocery-aisle-mybgdVT2vkw) | [Cart moving in supermarket](https://www.pexels.com/video/a-man-walking-inside-the-supermarket-4081583/) | `shopping_cart`; `object_in_zone` | No physical aisle-clearance estimate |
| Construction zone entry | [Infinara — excavator and worker](https://unsplash.com/photos/construction-site-with-excavators-and-worker-GTYwYTsZ0-o) | [Excavator and workers on site](https://www.pexels.com/video/man-driving-excavator-11355862/) | `person`, `excavator`; `object_zone_entry` for `person` | Needs consecutive outside→inside observations |

## Audio and privacy

The release update strips audio (`-an`) from MP4s prepared by the web application's `Prepare for SAM` service and from CLI-prepared clips. Original uploads remain unchanged with any sound they have. **IMPORTANT:** The current backend also permits eligible unprepared MP4/MOV uploads to go directly to SAM; if those sources have sound, it may still be transmitted. Until an audio-free preflight is enforced for all SAM requests, only send confirmed silent files or use `Prepare for SAM` first. Video processing limits remain 25 MiB, 30 seconds, maximum 1080p/30 FPS per model-job guard.

## Final cleanup

`frontend/yarn.lock` is present in `main` and should remain committed; both GitHub Actions workflows were green on `4584e1d` when checked 2 Nov 2026. `.gitignore` already ignores `/frontend/next-env.d.ts`, but the generated file is still tracked. Run `git rm --cached frontend/next-env.d.ts` and commit the index change. Root `architecture/visionguard-demo-architecture.md` remains and duplicates `docs/architecture/visionguard-demo-architecture.md`; compare files before removing. Root `assets/` is already absent. Obsolete full ZIP instructions were removed from the release guide by this patch.

Keep author/photographer/source links when distributing media. Do not describe stock photos as analyzed frames, safety incidents, or SAM model evidence. Uploads and evidence may contain personal data; never publish those files without authorization.
