from app.modules.cfe.parser import extract_service_number

def test_single_number():
    value, error = extract_service_number('123456789012')
    assert value == '123456789012' and error is None

def test_multiple_numbers():
    value, error = extract_service_number('12345678 99999999')
    assert value == '' and error
