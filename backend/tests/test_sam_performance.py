"""No-network regression checks for heavy SAM output and large video batches."""
import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from backend.app.services.sam import save_outputs, summarize
from backend.scripts.batch_test_videos import cached, main, output_for


def fake_result():
    box = NS(kind="box", object_id=0, frame=NS(frame_index=2),
             left=10, top=20, right=30, bottom=60)
    mask = NS(kind="mask", object_id=0, frame=NS(frame_index=2),
              mask=NS(width=1080, height=720, encoding="one_bit"))
    return NS(outcome=NS(status="completed"), diagnostics=[],
              media={"width":1080, "height":720, "fps":12}, records=[box, mask])


def test_summary_never_expands_masks_by_default(tmp_path, monkeypatch):
    # No meta_sam_parser imported/installed: default processing must not need it.
    result = fake_result()
    summary = summarize(result, "person")
    assert summary["box_count"] == 1 and summary["mask_count"] == 1
    assert "foreground_pixels" not in summary["masks"][0]
    loc = save_outputs(result, "person", tmp_path, summary)
    assert json.loads((loc / "summary.json").read_text()) == summary
    assert not list(loc.glob("*.svg"))


def test_save_uses_supplied_summary_not_duplicate_work(tmp_path, monkeypatch):
    result = fake_result()
    import backend.app.services.sam as sam
    summary = summarize(result, "person")
    monkeypatch.setattr(sam, "summarize", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("duplicate summary")))
    loc = save_outputs(result, "person", tmp_path, summary)
    assert (loc / "summary.json").exists()


def test_batch_dry_run_no_paid_inference(tmp_path, monkeypatch):
    source = tmp_path / "samples"
    source.mkdir()
    (source / "one.mp4").write_bytes(b"\x00\x00\x00\x18ftypisom" + b"\x00"*50)
    dest = tmp_path / "batch"
    import backend.scripts.batch_test_videos as batch
    monkeypatch.setattr(batch, "run_video", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("paid request")))
    assert main(["--directory", str(source), "--output", str(dest)]) == 0
    data = json.loads((dest / "manifest.json").read_text())
    assert data["live_calls_requested"] is False
    assert data["results"][0]["status"] == "eligible"
    assert (dest / "manifest.csv").exists()


def test_batch_cache_only_after_all_concepts_completed(tmp_path):
    clip = tmp_path / "source.mp4"
    clip.write_bytes(b"fake")
    dest = output_for(clip, tmp_path / "outputs")
    person = dest / "person"
    person.mkdir(parents=True)
    (person / "summary.json").write_text('{"outcome":"completed"}')
    assert not cached(dest, ["person", "forklift"])
    forklift = dest / "forklift"
    forklift.mkdir()
    (forklift / "summary.json").write_text('{"outcome":"completed"}')
    assert cached(dest, ["person", "forklift"])


def test_partial_cache_detects_missing_single_concept(tmp_path):
    from backend.scripts.batch_test_videos import missing_concepts
    dest = tmp_path / "output"
    (dest / "person").mkdir(parents=True)
    (dest / "person" / "summary.json").write_text('{"outcome":"completed"}')
    assert missing_concepts(dest, ["person", "forklift"]) == ["forklift"]


def test_tracking_background_job_is_synchronous():
    # FastAPI runs sync BackgroundTasks in a worker thread, never in the ASGI loop.
    import inspect
    from backend.app.services.tracking_jobs import process_job
    assert not inspect.iscoroutinefunction(process_job)


def test_prepare_requires_tools_and_never_silently_skips(monkeypatch, tmp_path):
    import backend.scripts.prepare_demo_clips as prep
    monkeypatch.setattr(prep.shutil, "which", lambda _exe: None)
    with pytest.raises(RuntimeError, match="FFmpeg"):
        prep.prepare(tmp_path / "source.mp4", tmp_path / "out.mp4")
