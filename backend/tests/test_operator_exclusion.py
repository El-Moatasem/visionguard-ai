"""Operator/pedestrian regression checks. Entirely offline, no model calls."""
from __future__ import annotations

from backend.app.services.safety_engine import evaluate_tracking
from backend.app.services.safety_rules import NormalizedZone, RuleSpec


def box(concept: str, ident: str, frame: int, bounds: tuple[float,float,float,float]):
    l,t,r,b=bounds
    return {"concept":concept,"track_id":f"{concept}:{ident}",
            "fragment_id":f"{concept}:{ident}#0","frame":frame,
            "box":{"left":l,"top":t,"right":r,"bottom":b}}


def scene(driver: bool, pedestrian: bool, explicit: bool=False):
    # forklift x20..80 y20..90. Driver sits within cab, feet above tire level.
    # Separate pedestrian overlaps in 2D but stands at ground level.
    observations=[]
    for frame in range(8):
        observations.append(box('forklift','lift',frame,(20,20,80,90)))
        if driver:
            observations.append(box('person','driver',frame,(42,29,54,65)))
        if pedestrian:
            observations.append(box('person','pedestrian',frame,(59,34,72,93)))
    report={"schema_version":1,"media_probe":{"width":100,"height":100,"fps":10},"boxes":observations,"gaps":[]}
    rule=RuleSpec(name='Worker and forklift',rule_type='person_and_forklift_in_zone',
                  min_duration_seconds=.5,max_observation_gap_frames=2,
                  excluded_operator_track_ids=['person:driver'] if explicit else [],
                  zone=NormalizedZone(name='Lane',x_min=.18,y_min=.25,x_max=.82,y_max=.99))
    return evaluate_tracking(report,rule)


def test_driver_only_no_pedestrian_hazard_event():
    result=scene(driver=True,pedestrian=False)
    assert result['event_count']==0, result['events']
    assert result['operator_candidate_count']==1
    assert result['review_count']>=1  # geometry is provisional, not an identity verdict


def test_pedestrian_in_front_still_generates_event():
    result=scene(driver=False,pedestrian=True)
    assert result['event_count']==1
    assert result['operator_candidate_count']==0
    assert result['events'][0]['actor_tracks']==['person:pedestrian','forklift:lift'] or set(result['events'][0]['actor_tracks'])=={'person:pedestrian','forklift:lift'}


def test_driver_and_pedestrian_one_event_only():
    result=scene(driver=True,pedestrian=True)
    assert result['event_count']==1
    assert 'person:driver' not in result['events'][0]['actor_tracks']
    assert 'person:pedestrian' in result['events'][0]['actor_tracks']


def test_manual_confirmation_excludes_operator_without_geometry_dependency():
    result=scene(driver=True,pedestrian=True,explicit=True)
    assert result['event_count']==1
    assert result['operator_excluded_count']==1
    assert result['operator_candidate_count']==0


def test_other_rule_types_not_affected():
    # Person-in-zone remains a separate rule with original semantics.
    boxes=[box('person','driver',f,(42,29,54,65)) for f in range(8)]
    report={'schema_version':1,'media_probe':{'width':100,'height':100,'fps':10},'boxes':boxes,'gaps':[]}
    rule=RuleSpec(name='Person zone',rule_type='person_in_zone',min_duration_seconds=.5,
                  zone=NormalizedZone(name='Everything',x_min=.1,y_min=.1,x_max=.95,y_max=.95))
    assert evaluate_tracking(report,rule)['event_count']==1
