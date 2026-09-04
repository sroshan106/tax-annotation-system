import pathlib, pytest

FORMS = pathlib.Path(__file__).parent.parent / "forms"

@pytest.fixture
def f1040_path():
    return FORMS / "f1040.pdf"

@pytest.fixture
def f1040sb_path():
    return FORMS / "f1040sb.pdf"
