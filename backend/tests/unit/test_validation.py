import pytest
from firmsignal.api.validation import validate_company_name
from fastapi import HTTPException

def test_empty_string_raises():
    with pytest.raises(HTTPException) as exc:
        validate_company_name("")
    assert exc.value.status_code == 422

def test_whitespace_only_raises():
    with pytest.raises(HTTPException):
        validate_company_name("   ")

def test_too_short_raises():
    with pytest.raises(HTTPException):
        validate_company_name("A")

def test_too_long_raises():
    with pytest.raises(HTTPException):
        validate_company_name("A" * 101)

def test_xss_attempt_raises():
    with pytest.raises(HTTPException):
        validate_company_name("<script>alert(1)</script>")

def test_blocked_word_raises():
    with pytest.raises(HTTPException):
        validate_company_name("test")

def test_valid_company_passes():
    assert validate_company_name("Nvidia") == "Nvidia"

def test_strips_whitespace():
    assert validate_company_name("  Apple  ") == "Apple"

def test_ampersand_passes():
    assert validate_company_name("Johnson & Johnson") == "Johnson & Johnson"

def test_ticker_passes():
    assert validate_company_name("AAPL") == "AAPL"