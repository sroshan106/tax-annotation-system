from app.models import AnnotationSet
from tools.extract_widgets import extract, infer_type


def test_extraction_output_is_a_valid_annotation_set(f1040_path):
    AnnotationSet.model_validate(extract(f1040_path, "f1040", 2024))


def test_extraction_finds_the_expected_order_of_magnitude_of_widgets(f1040_path):
    assert len(extract(f1040_path, "f1040", 2024)["annotations"]) > 150


def test_rects_are_converted_to_top_left_and_stay_on_the_page(f1040_path):
    doc = extract(f1040_path, "f1040", 2024)
    for a in doc["annotations"]:
        assert 0 <= a["box"]["y"] <= 792
        assert a["box"]["y"] + a["box"]["height"] <= 792.5


def test_type_inference_follows_the_irs_naming_convention():
    assert infer_type("topmostSubform[0].Page1[0].c1_1[0]", "/Btn") == "checkbox"
    assert infer_type("topmostSubform[0].Page1[0].f1_04[0]", "/Tx") == "text"


def test_every_draft_annotation_carries_its_acrofieldname_hint(f1040_path):
    doc = extract(f1040_path, "f1040", 2024)
    assert all(a["acroFieldName"] for a in doc["annotations"])
