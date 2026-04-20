import pytest

from app.services.vlm_client import (
    LifelineAuthenticationError,
    LifelineServiceUnavailableError,
    LifelineValidationError,
    _dynamic_result_to_text,
    _normalize_sdk_result,
    _raise_classified_upstream_error,
    _suffix_for_mime_type,
    _to_confidence,
)


class _FakeResponse:
    def __init__(self, status_code=None, json_body=None, text=""):
        self.status_code = status_code
        self._json_body = json_body
        self.text = text

    def json(self):
        if isinstance(self._json_body, Exception):
            raise self._json_body
        return self._json_body


class _FakeException(Exception):
    def __init__(self, message, response=None):
        super().__init__(message)
        self.response = response


def test_suffix_for_mime_type_maps_known_types():
    assert _suffix_for_mime_type("image/png") == ".png"
    assert _suffix_for_mime_type("image/jpeg") == ".jpg"
    assert _suffix_for_mime_type("image/jpg") == ".jpg"
    assert _suffix_for_mime_type("image/webp") == ".webp"


def test_suffix_for_mime_type_defaults_to_png():
    assert _suffix_for_mime_type("image/gif") == ".png"


def test_to_confidence_clamps_range():
    assert _to_confidence(-1) == 0.0
    assert _to_confidence(2.3) == 1.0
    assert _to_confidence("0.6") == 0.6
    assert _to_confidence("not-a-number") == 0.0


def test_normalize_sdk_result_extracts_core_fields():
    payload = {
        "diagnosis": "Atrial fibrillation",
        "confidence": "0.9",
        "findings": ["Irregular rhythm"],
        "recommendation": "Follow up with cardiologist",
    }

    normalized = _normalize_sdk_result(payload)

    assert normalized["status"] == "success"
    assert normalized["analysis"]["diagnosis"] == "Atrial fibrillation"
    assert normalized["analysis"]["confidence"] == 0.9
    assert normalized["analysis"]["findings"] == ["Irregular rhythm"]
    assert normalized["analysis"]["recommendation"] == "Follow up with cardiologist"


def test_dynamic_result_to_text_prefers_final_report():
    payload = {
        "final_report": "ST elevation in anterior leads",
        "description": "fallback",
    }
    assert _dynamic_result_to_text(payload) == "ST elevation in anterior leads"


def test_raise_classified_error_for_offline():
    with pytest.raises(LifelineServiceUnavailableError):
        _raise_classified_upstream_error(Exception("Connection timeout"), operation="analyze")


def test_raise_classified_error_for_validation_400():
    exc = _FakeException(
        "bad request",
        response=_FakeResponse(status_code=400, json_body={"detail": "Invalid ECG"}),
    )

    with pytest.raises(LifelineValidationError) as raised:
        _raise_classified_upstream_error(exc, operation="analyze")

    assert "Invalid ECG" in str(raised.value)


def test_raise_classified_error_for_auth_401():
    exc = _FakeException("401 unauthorized")
    with pytest.raises(LifelineAuthenticationError):
        _raise_classified_upstream_error(exc, operation="analyze")
