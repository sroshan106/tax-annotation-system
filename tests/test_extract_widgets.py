import pytest
from app.models import AnnotationSet
from tools.extract_widgets import extract, infer_type


@pytest.fixture(scope="module")
def doc():
    from tests.conftest import FORMS
    return extract(FORMS / "f1040.pdf", "f1040", 2024)


def test_extraction(doc):
    AnnotationSet.model_validate(doc)
    assert len(doc["annotations"]) > 150
    assert all(a["acroFieldName"] for a in doc["annotations"])
    for a in doc["annotations"]:
        assert 0 <= a["box"]["y"] <= 792
        assert a["box"]["y"] + a["box"]["height"] <= 792.5


def test_infer_type():
    assert infer_type("c1_1[0]", "/Btn") == "checkbox"
    assert infer_type("f1_04[0]", "/Tx") == "text"
