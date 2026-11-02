"""Deterministic tests for the generic SceneOps object and replay scenarios. No Meta calls."""
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backend.app.main import app
from backend.app.services.demo_catalog import SCENARIOS
from backend.app.services.safety_engine import evaluate_tracking
from backend.app.services.safety_rules import RuleSpec
from backend.app.services.tracking_report import build_tracking_report
from backend.app.services.replay_fixtures import get_scenario
from backend.app.services.sceneops_concepts import concept_prompt, normalize_concept

client = TestClient(app)


def rule(kind, concept, duration=.3):
    return RuleSpec(name="Scenario test", rule_type=kind, concept=concept,
                    zone={"name":"zone","x_min":.3,"y_min":.2,"x_max":.8,"y_max":.85},
                    min_duration_seconds=duration,max_observation_gap_frames=2)


def box(kind,track,frame,x=.5,y=.5,fragment="0"):
    return {"concept":kind,"track_id":f"{kind}:{track}","fragment_id":f"{kind}:{track}#{fragment}",
            "frame":frame,"box":{"left":x*100-5,"right":x*100+5,"top":y*100-5,"bottom":y*100+5}}


def report(boxes, fps=10):
    return {"schema_version":1,"media_probe":{"fps":fps,"width":100,"height":100},
            "media_metadata":{},"boxes":boxes,"gaps":[]}


def test_car_parking_dwell_requires_consecutive_observations():
    car=[box("car","one",i) for i in range(10)]
    assert evaluate_tracking(report(car),rule("object_in_zone","car",.5))["event_count"]==1
    assert evaluate_tracking(report(car[::2]),rule("object_in_zone","car",.5))["event_count"]==0
    assert evaluate_tracking(report(car),rule("object_in_zone","shopping_cart",.5))["event_count"]==0


def test_cart_occupancy_not_automatically_blockage():
    cart=[box("shopping_cart","c",i) for i in range(10)]
    result=evaluate_tracking(report(cart),rule("object_in_zone","shopping_cart",.5))
    assert result["event_count"]==1
    assert "center observed" in result["events"][0]["reason"]
    assert "distance" in result["disclaimer"]


def test_zone_entry_observed_transition_only():
    person=[box("person","p",2,.2),box("person","p",3,.5),box("person","p",4,.5),box("person","p",5,.5)]
    r=evaluate_tracking(report(person),rule("object_zone_entry","person",.3))
    assert r["event_count"]==1
    assert r["events"][0]["start_frame"]==3
    assert r["events"][0]["actor_tracks"]==["person:p"]
    assert r["events"][0]["contains_missing_observations"] is False


def test_missing_zone_transition_is_review_only():
    person=[box("person","p",2,.2),box("person","p",4,.5),box("person","p",5,.5),box("person","p",6,.5)]
    r=evaluate_tracking(report(person),rule("object_zone_entry","person",.3))
    assert r["event_count"]==0
    assert r["review_count"]>=1
    assert "exact crossing unverified" in r["review_items"][0]["reason"]


def test_zone_entry_never_infers_entering_without_outside_observation():
    r=evaluate_tracking(report([box("person","p",i,.5) for i in range(10)]),rule("object_zone_entry","person",.3))
    assert r["event_count"]==0


def test_whitelist_and_strict_rule_validation():
    assert normalize_concept("shopping cart")=="shopping_cart"
    assert concept_prompt("cardboard_box")=="cardboard box"
    with pytest.raises(ValueError):normalize_concept("any arbitrary unsafe or expensive prompt")
    with pytest.raises(ValidationError):RuleSpec(name="bad",rule_type="object_in_zone",zone={"x_min":0,"y_min":0,"x_max":1,"y_max":1})
    with pytest.raises(ValidationError):RuleSpec(name="bad",rule_type="unsupported",zone={"x_min":0,"y_min":0,"x_max":1,"y_max":1})


def test_tracking_report_supports_generic_concept_and_normalizes_id():
    summary={"outcome":"completed","concept":"shopping_cart","boxes":[{"object_id":"1","frame":1,"left":5,"top":10,"right":20,"bottom":50}]}
    data=build_tracking_report([summary],{"fps":10,"width":640,"height":360})
    assert data["boxes"][0]["track_id"]=="shopping_cart:1"
    assert data["concepts_requested"]==["shopping_cart"]


def test_catalog_and_new_synthetic_fixtures_are_consistent():
    res=client.get('/api/v1/demo/scenarios')
    assert res.status_code==200
    items=res.json()["items"]
    assert len(items)>=7
    assert client.get('/api/v1/demo/scenarios/not-real').status_code==404
    for sid in ['parking-car-dwell','retail-cart-aisle','construction-zone-entry']:
        fixture=get_scenario(sid)
        result=client.post(f'/api/v1/replay/scenarios/{sid}/evaluate',json={'rule':fixture['default_rule']})
        assert result.status_code==200, (sid,result.text)
        assert result.json()["event_count"]>=1,(sid,result.json())
        assert fixture["provenance"]=="synthetic_fixture"
        assert fixture["video_asset_included"] is False


def test_upload_as_demo_keeps_scenario_metadata_in_library(tmp_path,monkeypatch):
    import backend.app.services.video_store as store
    monkeypatch.setenv('VIDEO_STORAGE_DIR',str(tmp_path))
    fake=b'\x00\x00\x00\x18ftypisom'+b'\x00'*50
    response=client.post('/api/v1/videos?scenario_id=parking-loading-zone', files={'file':('demo.mp4',fake,'video/mp4')})
    assert response.status_code==201,response.text
    uploaded=response.json()
    assert uploaded['scenario_id']=='parking-loading-zone'
    assert uploaded['suggested_concepts']==['car']
    assert uploaded['library_source']=='demo'
    assert client.get('/api/v1/videos').json()['items'][0]['id']==uploaded['id']
    assert client.post('/api/v1/videos?scenario_id=fake',files={'file':('demo.mp4',fake,'video/mp4')}).status_code==422


def test_tracking_job_explicit_concepts_preflight(monkeypatch,tmp_path):
    import backend.app.services.tracking_jobs as jobs
    import backend.app.services.video_store as store
    from backend.app.services.sceneops_concepts import CONCEPT_PROMPTS
    monkeypatch.setenv('VIDEO_STORAGE_DIR',str(tmp_path))
    monkeypatch.setenv('MODEL_API_KEY','local-test-placeholder')
    from uuid import uuid4
    videoid=uuid4().hex
    path=tmp_path / f'{videoid}.mp4';path.write_bytes(b'fake')
    (tmp_path/f'{videoid}.json').write_text(__import__('json').dumps({'id':videoid,'media_type':'video/mp4','sam_compatible_container':True,'suggested_concepts':['car']}))
    monkeypatch.setattr(jobs,'probe_video',lambda p:{'available':True,'width':640,'height':360,'fps':10,'codec':'h264','duration_seconds':4})
    item=jobs.create_job(videoid)
    assert item['concepts']==['car']
    with pytest.raises(jobs.TrackingError):jobs.create_job(videoid,['not-approved'])
    jobs._ACTIVE.discard(item['id'])


def test_parking_rule_can_create_evidence_snapshot_without_model_call(tmp_path, monkeypatch):
    from uuid import uuid4
    import backend.app.services.evidence_store as evidence
    import backend.app.services.video_store as store
    videoid=uuid4().hex
    jobid=str(uuid4())
    monkeypatch.setenv('VIDEO_STORAGE_DIR',str(tmp_path/'uploads'))
    store.storage_dir().mkdir(parents=True)
    (store.storage_dir()/f'{videoid}.json').write_text(__import__('json').dumps({
        'id':videoid,'name':'parking-test.mp4','sha256':'0'*64,'media_type':'video/mp4'}))
    monkeypatch.setattr(evidence,'get_job',lambda _: {'id':jobid,'video_id':videoid,'status':'completed','model':'sam-3.1'})
    monkeypatch.setattr(evidence,'get_result',lambda _: report([box('car','one',f) for f in range(10)]))
    captured=evidence.create_evidence(evidence.CreateEvidence(tracking_job_id=jobid,
        rule=rule('object_in_zone','car',.5)))
    assert captured['evaluation']['event_count']==1
    assert captured['source']['model']=='sam-3.1'
    assert captured['observations'][0]['sampled_boxes']
    assert captured['source']['model_output_independently_validated'] is False
