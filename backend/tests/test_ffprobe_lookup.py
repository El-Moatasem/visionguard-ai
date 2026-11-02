"""FFprobe resolver regression tests; no real media or Meta API calls."""
from pathlib import Path

from backend.app.services import tracking_jobs


def test_explicit_ffprobe_override_when_not_on_path(tmp_path, monkeypatch):
    executable = tmp_path / "ffprobe"
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    monkeypatch.setenv("FFPROBE_BIN", str(executable))
    monkeypatch.setattr(tracking_jobs.shutil, "which", lambda name: None)
    assert tracking_jobs._ffprobe_executable() == str(executable)


def test_probe_uses_explicit_executable(tmp_path, monkeypatch):
    executable = tmp_path / "ffprobe"
    executable.write_text('''#!/bin/sh
printf '%s\\n' '{"streams":[{"width":640,"height":360,"avg_frame_rate":"12/1","codec_name":"h264","duration":"3.0"}]}'
''')
    executable.chmod(0o755)
    monkeypatch.setenv("FFPROBE_BIN", str(executable))
    monkeypatch.setattr(tracking_jobs.shutil, "which", lambda name: None)
    video = tmp_path / "test.mp4"
    video.write_bytes(b"fixture")
    probe = tracking_jobs.probe_video(video)
    assert probe["available"] is True
    assert probe["fps"] == 12
    assert probe["width"] == 640
    assert probe["height"] == 360
