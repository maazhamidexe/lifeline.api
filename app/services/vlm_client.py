from __future__ import annotations

import os
import tempfile
import logging
from urllib.parse import urlparse
from urllib.request import urlopen
from typing import Optional

from lifelinecg_sdk import LifelineClient

DEFAULT_HARDCODED_SDK_API_KEY = "dasa_32753404569591298172"
DEFAULT_SDK_BASE_URL = "https://asad999-lifelineopenapi.hf.space"
DEFAULT_GENERATE_API_EMAIL = "asadirfan7533@gmail.com"
DEFAULT_GENERATE_ADMIN_SECRET = "lifelineasad9009"

logger = logging.getLogger("lifeline.api.vlm_client")


class LifelineServiceUnavailableError(RuntimeError):
    """Raised when the upstream Lifeline service is unreachable or down."""


class LifelineClientRequestError(ValueError):
    """Raised when the upstream request fails for a non-outage reason."""


class LifelineAuthenticationError(ValueError):
    """Raised when SDK key or admin secret is invalid/misconfigured."""


class LifelineValidationError(ValueError):
    """Raised when upstream rejects request payload/content (HTTP 400)."""


class LifelineSdkVersionError(ValueError):
    """Raised when installed SDK version does not support required methods."""


class LifelineSDKClient:
    model_name = "lifelinecg-sdk"

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None) -> None:
        self.base_url = base_url or DEFAULT_SDK_BASE_URL
        resolved_api_key = api_key or DEFAULT_HARDCODED_SDK_API_KEY
        self.client = (
            LifelineClient(api_key=resolved_api_key, base_url=self.base_url)
            if resolved_api_key
            else None
        )

    @property
    def can_analyze(self) -> bool:
        return self.client is not None

    def health_status(self) -> dict:
        upstream_reachable = _is_upstream_reachable(self.base_url)
        logger.info(
            "vlm_health_check sdk_configured=%s upstream_reachable=%s base_url=%s",
            self.can_analyze,
            upstream_reachable,
            self.base_url,
        )
        return {
            "status": "ok" if upstream_reachable else "degraded",
            "service": "lifeline-api",
            "sdk_configured": self.can_analyze,
            "lifeline_upstream_reachable": upstream_reachable,
        }

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
            # Try analyze_dynamic first if available (newer SDK versions)
            if hasattr(self.client, "analyze_dynamic"):
                logger.info("Using analyze_dynamic method")
                sdk_result = self.client.analyze_dynamic(
                    prompt="Analyze this ECG image and provide diagnosis and findings.",
                    image_path=temp_path,
                )
                description = _dynamic_result_to_text(sdk_result)
                return {
                    "status": "success",
                    "analysis": {
                        "diagnosis": description,
                        "confidence": 0.85,
                        "findings": ["See diagnosis for details."],
                        "recommendation": "Please consult a clinician for full interpretation.",
                    },
                }
            else:
                # Fall back to analyze() for older SDK versions
                logger.info("Using analyze method (analyze_dynamic not available)")
                sdk_result = self.client.analyze(temp_path)
                normalized_result = _normalize_sdk_result(sdk_result)
                return _enhance_analysis_with_dynamic_fallback(
                    client=self.client,
                    temp_path=temp_path,
                    normalized_result=normalized_result,
                )
        except Exception as exc:
            logger.warning("analyze_from_file failed: %s", str(exc))
            _raise_classified_upstream_error(exc, operation="analyze")
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass

        raise LifelineClientRequestError("Failed to analyze ECG using Lifeline service")

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
            # Try analyze_dynamic first if available (newer SDK versions)
            if hasattr(self.client, "analyze_dynamic"):
                logger.info("Using analyze_dynamic method")
                sdk_result = self.client.analyze_dynamic(
                    prompt="Analyze this ECG image and provide diagnosis and findings.",
                    image_path=temp_path,
                )
                description = _dynamic_result_to_text(sdk_result)
                return {
                    "status": "success",
                    "analysis": {
                        "diagnosis": description,
                        "confidence": 0.85,
                        "findings": ["See diagnosis for details."],
                        "recommendation": "Please consult a clinician for full interpretation.",
                    },
                }
            else:
                # Fall back to analyze() for older SDK versions
                logger.info("Using analyze method (analyze_dynamic not available)")
                sdk_result = self.client.analyze(temp_path)
                normalized_result = _normalize_sdk_result(sdk_result)
                return _enhance_analysis_with_dynamic_fallback(
                    client=self.client,
                    temp_path=temp_path,
                    normalized_result=normalized_result,
                )
        except Exception as exc:
            logger.warning("analyze_from_url failed: %s", str(exc))
            _raise_classified_upstream_error(exc, operation="analyze")
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass

        raise LifelineClientRequestError("Failed to analyze ECG using Lifeline service")

    def analyze_dynamic(
        self,
        prompt: str,
        context: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
        mime_type: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> object:
        if self.client is None:
            raise ValueError("LIFELINE_SDK_API_KEY is required for ECG analysis")

        if not prompt or not prompt.strip():
            raise ValueError("Prompt is required for dynamic analysis")

        if not hasattr(self.client, "analyze_dynamic"):
            raise LifelineSdkVersionError(
                "Installed lifelinecg-sdk does not support analyze_dynamic. "
                "Upgrade to lifelinecg-sdk==0.1.4 and restart the API service."
            )

        resolved_image_bytes = image_bytes
        resolved_mime_type = mime_type or "image/png"

        if image_url and resolved_image_bytes is None:
            try:
                with urlopen(image_url, timeout=20) as response:
                    resolved_image_bytes = response.read()
            except Exception as exc:
                raise ValueError("Failed to fetch image from URL") from exc

        temp_path: Optional[str] = None
        if resolved_image_bytes is not None:
            suffix = _suffix_for_mime_type(resolved_mime_type)
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file.write(resolved_image_bytes)
                temp_path = temp_file.name

        try:
            kwargs = {"prompt": prompt}
            if context:
                kwargs["context"] = context
            if temp_path:
                kwargs["image_path"] = temp_path

            try:
                return self.client.analyze_dynamic(**kwargs)
            except TypeError:
                # Backward compatibility with positional SDK signatures.
                if temp_path and context:
                    return self.client.analyze_dynamic(prompt, temp_path, context)
                if temp_path:
                    return self.client.analyze_dynamic(prompt, temp_path)
                return self.client.analyze_dynamic(prompt)
        except Exception as exc:
            logger.warning("analyze_dynamic failed: %s", str(exc))
            _raise_classified_upstream_error(exc, operation="analyze_dynamic")
        finally:
            if temp_path:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def generate_api_key(self, email: str = DEFAULT_GENERATE_API_EMAIL) -> str:
        client = LifelineClient(base_url=self.base_url)
        try:
            sdk_result = client.generate_api_key(
                email=email,
                admin_secret=DEFAULT_GENERATE_ADMIN_SECRET,
            )
        except TypeError:
            # Backward compatibility for SDK signatures that still expect positional args.
            try:
                sdk_result = client.generate_api_key(
                    email,
                    DEFAULT_GENERATE_ADMIN_SECRET,
                )
            except Exception as exc:
                logger.warning("generate_api_key failed: %s", str(exc))
                _raise_classified_upstream_error(exc, operation="generate_api_key")
        except Exception as exc:
            logger.warning("generate_api_key failed: %s", str(exc))
            _raise_classified_upstream_error(exc, operation="generate_api_key")

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
        # Pass through already normalized payloads only when diagnosis is meaningful.
        if "status" in result and "analysis" in result and isinstance(result.get("analysis"), dict):
            analysis_obj = result["analysis"]
            diagnosis = _extract_first_string(
                analysis_obj,
                ("diagnosis", "summary", "description", "impression", "report", "text"),
            )
            if diagnosis and not _is_placeholder_diagnosis(diagnosis):
                return result

        diagnosis = _extract_first_string(
            result,
            (
                "diagnosis",
                "summary",
                "description",
                "generated_description",
                "impression",
                "report",
                "analysis_text",
                "text",
                "result",
                "message",
                "response",
            ),
        ) or "No diagnosis provided"

        confidence_raw = _extract_first_value(result, ("confidence", "score", "probability"), default=0.0)
        confidence = _to_confidence(confidence_raw)

        findings = _extract_string_list(result, ("findings", "abnormalities", "observations", "conditions"))

        # Some upstream payloads expose only a list of conditions.
        if _is_placeholder_diagnosis(diagnosis) and findings:
            diagnosis = "; ".join(findings[:3])

        if not findings:
            findings_text = _extract_first_string(result, ("findings_text", "observations_text"))
            if findings_text:
                findings = [findings_text]
            elif diagnosis != "No diagnosis provided":
                findings = ["See diagnosis for details."]
            else:
                findings = ["No major findings detected."]

        recommendation = _extract_first_string(
            result,
            ("recommendation", "advice", "next_steps", "plan"),
        ) or "Please consult a clinician for full interpretation."

        return {
            "status": "success",
            "analysis": {
                "diagnosis": diagnosis,
                "confidence": confidence,
                "findings": [str(item) for item in findings if str(item).strip()],
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


def _extract_first_value(source: object, keys: tuple[str, ...], default: object = None) -> object:
    if isinstance(source, dict):
        for key in keys:
            if key in source and source[key] is not None:
                return source[key]
        for value in source.values():
            nested = _extract_first_value(value, keys, default=None)
            if nested is not None:
                return nested
    elif isinstance(source, list):
        for item in source:
            nested = _extract_first_value(item, keys, default=None)
            if nested is not None:
                return nested
    return default


def _extract_first_string(source: object, keys: tuple[str, ...]) -> str:
    value = _extract_first_value(source, keys, default=None)
    if isinstance(value, str) and value.strip():
        return value.strip()
    if value is not None and not isinstance(value, (dict, list)):
        rendered = str(value).strip()
        return rendered
    return ""


def _extract_string_list(source: object, keys: tuple[str, ...]) -> list[str]:
    value = _extract_first_value(source, keys, default=[])
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _extract_api_key(result: object) -> str:
    if isinstance(result, str):
        return result.strip()

    if isinstance(result, dict):
        for key_name in ("api_key", "apiKey", "key", "token"):
            value = result.get(key_name)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return ""


def _is_placeholder_diagnosis(value: str) -> bool:
    normalized = value.strip().lower()
    placeholders = {
        "",
        "no diagnosis provided",
        "analysis completed.",
        "analysis completed",
        "n/a",
        "none",
    }
    return normalized in placeholders


def _dynamic_result_to_text(result: object) -> str:
    if isinstance(result, str):
        text = result.strip()
        if text:
            return text

    if isinstance(result, dict):
        # Check for explicit fields in order of priority
        for key in (
            "final_report",  # New Lifeline SDK response format
            "diagnosis",
            "summary",
            "description",
            "generated_description",
            "response",
            "answer",
            "text",
            "message",
            "report",
        ):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                text = value.strip()
                if not _is_placeholder_diagnosis(text):
                    return text

    rendered = str(result).strip()
    if rendered and not _is_placeholder_diagnosis(rendered):
        return rendered
    
    return "Analysis completed. Please consult with a healthcare provider for full ECG interpretation."


def _enhance_analysis_with_dynamic_fallback(
    client: LifelineClient,
    temp_path: str,
    normalized_result: dict,
) -> dict:
    analysis = normalized_result.get("analysis") if isinstance(normalized_result, dict) else None
    if not isinstance(analysis, dict):
        return normalized_result

    diagnosis = str(analysis.get("diagnosis") or "")
    if not _is_placeholder_diagnosis(diagnosis):
        return normalized_result

    if not hasattr(client, "analyze_dynamic"):
        return normalized_result

    try:
        dynamic_result = client.analyze_dynamic(
            prompt="Provide a concise ECG diagnosis and key findings from this image.",
            image_path=temp_path,
        )
        dynamic_text = _dynamic_result_to_text(dynamic_result)
        if dynamic_text and not _is_placeholder_diagnosis(dynamic_text):
            analysis["diagnosis"] = dynamic_text
            findings = analysis.get("findings")
            if findings == ["No major findings detected."]:
                analysis["findings"] = ["See diagnosis for details."]
    except Exception as exc:
        logger.info("dynamic fallback after analyze returned no enrichment: %s", str(exc))

    return normalized_result


def _is_upstream_offline_error(exc: Exception) -> bool:
    message = str(exc).lower()
    offline_markers = (
        "connection",
        "timeout",
        "timed out",
        "service unavailable",
        "temporarily unavailable",
        "unreachable",
        "failed to establish a new connection",
        "max retries exceeded",
        "name or service not known",
        "nodename nor servname provided",
        "503",
    )
    return any(marker in message for marker in offline_markers)


def _is_upstream_auth_error(exc: Exception) -> bool:
    message = str(exc).lower()
    auth_markers = (
        "unauthorized",
        "forbidden",
        "authentication",
        "invalid api key",
        "api key is invalid",
        "invalid key",
        "invalid token",
        "permission denied",
        "401",
        "403",
        "invalid admin secret",
        "admin_secret",
    )
    return any(marker in message for marker in auth_markers)


def _raise_classified_upstream_error(exc: Exception, operation: str) -> None:
    message = str(exc).lower()
    upstream_status = _extract_upstream_status_code(exc)
    upstream_detail = _extract_upstream_error_detail(exc)

    if _is_upstream_offline_error(exc):
        raise LifelineServiceUnavailableError(
            "Lifeline service is temporarily unavailable. Please try again shortly."
        ) from exc

    if upstream_status == 400:
        detail = (
            f"Upstream Lifeline rejected the request (400). {upstream_detail}"
            if upstream_detail
            else "Upstream Lifeline rejected the request (400). Check ECG image format/content and retry."
        )
        raise LifelineValidationError(detail) from exc

    if _is_upstream_auth_error(exc):
        if "admin" in message and "secret" in message:
            raise LifelineAuthenticationError(
                "Invalid Lifeline admin secret. Update LIFELINE_ADMIN_SECRET and retry."
            ) from exc
        raise LifelineAuthenticationError(
            "Invalid Lifeline SDK API key. Update LIFELINE_SDK_API_KEY and retry."
        ) from exc

    if operation == "generate_api_key":
        raise LifelineClientRequestError("Failed to generate API key from Lifeline service") from exc
    if operation == "analyze_dynamic":
        raise LifelineClientRequestError("Failed to run dynamic ECG analysis") from exc
    raise LifelineClientRequestError("Failed to analyze ECG using Lifeline service") from exc


def _extract_upstream_status_code(exc: Exception) -> Optional[int]:
    response = getattr(exc, "response", None)
    if response is None:
        return None

    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    return None


def _extract_upstream_error_detail(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    if response is None:
        return ""

    try:
        json_body = response.json()
        if isinstance(json_body, dict):
            for key in ("detail", "message", "error"):
                value = json_body.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            return str(json_body)
    except Exception:
        pass

    text_body = getattr(response, "text", "")
    if isinstance(text_body, str) and text_body.strip():
        return text_body.strip()[:400]

    return ""


def _is_upstream_reachable(base_url: str) -> bool:
    try:
        with urlopen(base_url, timeout=5) as response:
            return 200 <= response.status < 500
    except Exception as exc:
        logger.debug("upstream reachability check failed: %s", str(exc))
        return False
