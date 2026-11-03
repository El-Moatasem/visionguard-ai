# Retail preset metadata offline; no Meta calls.
from backend.app.services.demo_catalog import get_scenario
from backend.app.services.sceneops_concepts import normalize_concept
from backend.app.api.tracking import TrackingStartRequest


def test_retail_person_cart_box_support():
    concepts = ["person", "shopping_cart", "cardboard_box"]
    assert get_scenario("retail-clearance")["concepts"] == concepts
    assert [normalize_concept(c) for c in concepts] == concepts
    assert TrackingStartRequest(concepts=concepts).concepts == concepts
