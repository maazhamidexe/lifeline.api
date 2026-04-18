from __future__ import annotations

import os
import tempfile
from urllib.parse import urlparse
from urllib.request import urlopen

from lifelinecg_sdk.client import LifelineClient

HARDCODED_GENERATE_API_EMAIL = "asadirfan7533@gmail.com"
HARDCODED_GENERATE_API_PASSWORD = "lifelineasad9009"


class LifelineSDKClient:
    model_name = "lifelinecg-sdk"

    def __init__(self, api_key: str | None = None) -> None:
        resolved_api_key = api_key or os.getenv("LIFELINE_SDK_API_KEY")
        self.client = LifelineClient(api_key=resolved_api_key) if resolved_api_key else None

    @property
    def can_analyze(self) -> bool:
        return self.client is not None

    def analyze_from_file(self, image_bytes: bytes, mime_type: str) -> dict:
        if self.client is None:
            raise ValueError("LIFELINE_SDK_API_KEY is required for ECG analysis")

        if not image_bytes:
            raise ValueError("Empty ECG file")

        suffix = _suffix_for_mime_type(mime_type)
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(image_bytes)
            temp_path = temp_file.name

        try:
            sdk_result = self.client.analyze(temp_path)
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass

        return _normalize_sdk_result(sdk_result)

    def analyze_from_url(self, image_url: str) -> dict:
        if self.client is None:
            raise ValueError("LIFELINE_SDK_API_KEY is required for ECG analysis")

        if not image_url:
            raise ValueError("Image URL is required")

        parsed = urlparse(image_url)
        suffix = os.path.splitext(parsed.path)[1].lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
            suffix = ".png"

        try:
            with urlopen(image_url, timeout=20) as response:
                image_bytes = response.read()
        except Exception as exc:
            raise ValueError("Failed to fetch image from URL") from exc

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(image_bytes)
            temp_path = temp_file.name

        try:
            sdk_result = self.client.analyze(temp_path)
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass

        return _normalize_sdk_result(sdk_result)

    def generate_api_key(self) -> str:
        client = LifelineClient()
        try:
            sdk_result = client.generate_api_key(
                HARDCODED_GENERATE_API_EMAIL,
                HARDCODED_GENERATE_API_PASSWORD,
            )
        except Exception as exc:
            raise ValueError("Failed to generate API key from Lifeline SDK") from exc

        api_key = _extract_api_key(sdk_result)
        if not api_key:
            raise ValueError("SDK did not return a valid API key")

        return api_key


def _suffix_for_mime_type(mime_type: str) -> str:
    mime_map = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/webp": ".webp",
    }
    return mime_map.get(mime_type, ".png")


def _normalize_sdk_result(result: object) -> dict:
    if isinstance(result, dict):
        if "status" in result and "analysis" in result:
            return result

        diagnosis = str(result.get("diagnosis") or result.get("summary") or "No diagnosis provided")
        confidence_raw = result.get("confidence", 0.0)
        confidence = _to_confidence(confidence_raw)
        findings_raw = result.get("findings", [])
        findings = findings_raw if isinstance(findings_raw, list) else [str(findings_raw)]
        recommendation = str(result.get("recommendation") or "Please consult a clinician for full interpretation.")

        return {
            "status": "success",
            "analysis": {
                "diagnosis": diagnosis,
                "confidence": confidence,
                "findings": [str(item) for item in findings],
                "recommendation": recommendation,
            },
        }

    if isinstance(result, str):
        return {
            "status": "success",
            "analysis": {
                "diagnosis": result,
                "confidence": 0.0,
                "findings": ["See diagnosis for details."],
                "recommendation": "Please consult a clinician for full interpretation.",
            },
        }

    return {
        "status": "success",
        "analysis": {
            "diagnosis": "Analysis completed.",
            "confidence": 0.0,
            "findings": [str(result)],
            "recommendation": "Please consult a clinician for full interpretation.",
        },
    }


def _to_confidence(value: object) -> float:
    try:
        numeric = float(str(value))
    except (TypeError, ValueError):
        return 0.0

    if numeric < 0:
        return 0.0
    if numeric > 1:
        return 1.0
    return numeric


def _extract_api_key(result: object) -> str:
    if isinstance(result, str):
        return result.strip()

    if isinstance(result, dict):
        for key_name in ("api_key", "apiKey", "key", "token"):
            value = result.get(key_name)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return ""
