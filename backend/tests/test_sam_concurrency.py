"""Offline bounded-concurrency regression tests: no paid Meta inference."""
import pytest

from backend.app.services import tracking_jobs as jobs


def _video(tmp_path, vid):
    path = tmp_path / (vid + '.mp4')
    path.write_bytes(b'fake-small-mp4')
    return path, {'id': vid, 'sam_compatible_container': True, 'suggested_concepts': ['person'],
                  'scenario_id': None, 'media_type': 'video/mp4'}


def test_two_distinct_jobs_use_two_slots_and_third_gets_409(tmp_path, monkeypatch):
    monkeypatch.setenv('VIDEO_STORAGE_DIR', str(tmp_path / 'uploads'))
    monkeypatch.setenv('SAM_MAX_ACTIVE_JOBS', '2')
    monkeypatch.setattr(jobs, 'api_configured', lambda: True)
    monkeypatch.setattr(jobs, 'probe_video', lambda p: {
        'available': True, 'width': 640, 'height': 360, 'fps': 12,
        'codec': 'h264', 'duration_seconds': 4})
    monkeypatch.setattr(jobs, 'get_video_file', lambda vid: _video(tmp_path, vid))
    created=[]
    try:
        for i in range(2):
            job=jobs.create_job(f'{i+1:032x}', ['person'])
            created.append(job['id'])
        assert len(jobs._ACTIVE) >= 2
        with pytest.raises(jobs.TrackingError) as e:
            jobs.create_job('3'*32, ['person'])
        assert e.value.status_code==409
    finally:
        with jobs._LOCK:
            for job_id in created: jobs._ACTIVE.discard(job_id)


def test_default_one_job_and_invalid_limit(monkeypatch):
    monkeypatch.delenv('SAM_MAX_ACTIVE_JOBS', raising=False)
    assert jobs.sam_max_active_jobs() == 1
    monkeypatch.setenv('SAM_MAX_ACTIVE_JOBS','2')
    assert jobs.sam_max_active_jobs()==2
    for invalid in ('0','3','ten','-1'):
        monkeypatch.setenv('SAM_MAX_ACTIVE_JOBS',invalid)
        with pytest.raises(jobs.TrackingError) as e:
            jobs.sam_max_active_jobs()
        assert e.value.status_code==503
