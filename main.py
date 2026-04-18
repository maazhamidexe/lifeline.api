import os
from typing import Optional
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.schemas import AnalyzeEcgResponse, GenerateApiKeyResponse
from app.services.vlm_client import (
    LifelineClientRequestError,
    LifelineSDKClient,
    LifelineServiceUnavailableError,
)

MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}


def _parse_csv_env(name: str, default: str) -> list[str]:
    raw_value = os.getenv(name, default)
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _parse_bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


CORS_ALLOW_ORIGINS = _parse_csv_env("CORS_ALLOW_ORIGINS", "*")
CORS_ALLOW_METHODS = _parse_csv_env("CORS_ALLOW_METHODS", "*")
CORS_ALLOW_HEADERS = _parse_csv_env("CORS_ALLOW_HEADERS", "*")
CORS_EXPOSE_HEADERS = _parse_csv_env("CORS_EXPOSE_HEADERS", "")
CORS_MAX_AGE_SECONDS = int(os.getenv("CORS_MAX_AGE_SECONDS", "600"))

# Star origin cannot be combined with credentialed requests in browsers.
CORS_ALLOW_CREDENTIALS = (
    False
    if "*" in CORS_ALLOW_ORIGINS
    else _parse_bool_env("CORS_ALLOW_CREDENTIALS", True)
)

app = FastAPI(title="Lifeline AI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=CORS_ALLOW_METHODS,
    allow_headers=CORS_ALLOW_HEADERS,
    expose_headers=CORS_EXPOSE_HEADERS,
    max_age=CORS_MAX_AGE_SECONDS,
)

vlm_client = LifelineSDKClient()


@app.exception_handler(HTTPException)
async def handle_http_exception(request: Request, exc: HTTPException):
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "error": {
                "code": exc.status_code,
                "message": message,
            },
        },
    )


@app.exception_handler(Exception)
async def handle_unexpected_exception(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "error": {
                "code": 500,
                "message": "Internal server error",
            },
        },
    )


def _is_valid_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.post("/analyze-ecg", response_model=AnalyzeEcgResponse)
async def analyze_ecg(
    request: Request,
    image_file: Optional[UploadFile] = File(default=None),
    image_url_form: Optional[str] = Form(default=None, alias="image_url"),
) -> AnalyzeEcgResponse:
    if not vlm_client.can_analyze:
        raise HTTPException(
            status_code=500,
            detail="Lifeline SDK is not configured. Set LIFELINE_SDK_API_KEY.",
        )

    image_url = image_url_form

    if request.headers.get("content-type", "").startswith("application/json"):
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
        raw_image_url = payload.get("image_url")
        image_url = raw_image_url if isinstance(raw_image_url, str) else None

    if image_file is None and not image_url:
        raise HTTPException(
            status_code=400,
            detail="Provide either image_file or image_url",
        )

    if image_file is not None:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_IMAGE_SIZE_BYTES + 1024:
                    raise HTTPException(
                        status_code=413,
                        detail="Image file exceeds 5MB size limit",
                    )
            except ValueError:
                pass

        if image_file.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=415,
                detail="Unsupported image type. Use PNG, JPG, JPEG, or WEBP.",
            )

        image_bytes = await image_file.read(MAX_IMAGE_SIZE_BYTES + 1)
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Empty image file")
        if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Image file exceeds 5MB size limit",
            )

        try:
            result = vlm_client.analyze_from_file(
                image_bytes=image_bytes,
                mime_type=image_file.content_type,
            )
        except LifelineServiceUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except LifelineClientRequestError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return AnalyzeEcgResponse(**result)

    if image_url is None:
        raise HTTPException(
            status_code=400,
            detail="Provide either image_file or image_url",
        )

    if not _is_valid_http_url(image_url):
        raise HTTPException(
            status_code=400,
            detail="Invalid image_url. Use an absolute HTTP/HTTPS URL.",
        )

    try:
        result = vlm_client.analyze_from_url(image_url)
    except LifelineServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LifelineClientRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return AnalyzeEcgResponse(**result)


@app.post("/generate-api-key", response_model=GenerateApiKeyResponse)
def generate_api_key() -> GenerateApiKeyResponse:
    try:
        api_key = vlm_client.generate_api_key()
    except LifelineServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LifelineClientRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return GenerateApiKeyResponse(status="success", api_key=api_key)
