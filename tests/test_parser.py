import pytest

from app.modules.cfe.parser import extract_service_number


def test_single_number():
    value, error = extract_service_number("123456789012")

    assert value == "123456789012"
    assert error is None


def test_multiple_numbers():
    value, error = extract_service_number(
        "12345678 99999999"
    )

    assert value == ""
    assert error is not None


@pytest.mark.parametrize(
    "text",
    [
        "",
        "hola",
        "ABC123456789012",
        "123456789012 texto",
        "1234-5678-9012",
    ],
)
def test_invalid_input(text):
    value, error = extract_service_number(text)

    assert value == ""
    assert error is not None


def test_duplicate_same_number_is_rejected_as_extra_text():
    value, error = extract_service_number(
        "123456789012 123456789012"
    )

    assert value == ""
    assert error is not None
