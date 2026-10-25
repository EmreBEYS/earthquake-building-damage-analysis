import pymupdf


def test_pymupdf_runtime_dependency_is_available() -> None:
    assert callable(pymupdf.open)
