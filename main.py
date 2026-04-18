import time
from typing import Optional
from urllib.parse import urlparse
import logging

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.logging_config import configure_logging
from app.schemas import (
    AnalyzeEcgResponse,
    ChatEcgRequest,
    ChatEcgResponse,
    DynamicAnalyzeResponse,
    GenerateApiKeyRequest,
    GenerateApiKeyResponse,
    HealthCheckResponse,
)
from app.services.vlm_client import (
    DEFAULT_GENERATE_API_EMAIL,
    LifelineAuthenticationError,
    LifelineClientRequestError,
    LifelineSdkVersionError,
    LifelineSDKClient,
    LifelineServiceUnavailableError,
    LifelineValidationError,
)

MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}

configure_logging()
logger = logging.getLogger("lifeline.api")

CORS_ALLOW_ORIGINS = ["*"]
CORS_ALLOW_METHODS = ["*"]
CORS_ALLOW_HEADERS = ["*"]
CORS_EXPOSE_HEADERS: list[str] = []
CORS_MAX_AGE_SECONDS = 600
# With wildcard origins, credentials must be false.
CORS_ALLOW_CREDENTIALS = False

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


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started_at = time.perf_counter()
    client_host = request.client.host if request.client else "unknown"

    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        logger.exception(
            "request_failed method=%s path=%s client=%s duration_ms=%.2f",
            request.method,
            request.url.path,
            client_host,
            elapsed_ms,
        )
        raise

    elapsed_ms = (time.perf_counter() - started_at) * 1000
    logger.info(
        "request_completed method=%s path=%s status=%s client=%s duration_ms=%.2f",
        request.method,
        request.url.path,
        response.status_code,
        client_host,
        elapsed_ms,
    )
    return response


@app.exception_handler(HTTPException)
async def handle_http_exception(request: Request, exc: HTTPException):
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    logger.warning(
        "http_exception method=%s path=%s status=%s message=%s",
        request.method,
        request.url.path,
        exc.status_code,
        message,
    )
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
    logger.exception(
        "unexpected_exception method=%s path=%s",
        request.method,
        request.url.path,
    )
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


def _result_to_text(result: object) -> str:
    if isinstance(result, str):
        text = result.strip()
        return text if text else "Analysis completed."
    
    if isinstance(result, dict):
        # Check for Lifeline's response format
        for key in (
            "final_report",
            "response",
            "answer",
            "diagnosis",
            "summary",
            "description",
            "generated_description",
            "text",
            "message",
        ):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                text = value.strip()
                return text if text else "Analysis completed."
        return str(result)
    
    return str(result)


@app.get("/health", response_model=HealthCheckResponse)
def health_check() -> HealthCheckResponse:
    status_payload = vlm_client.health_status()
    logger.info(
        "health_check status=%s sdk_configured=%s lifeline_upstream_reachable=%s",
        status_payload["status"],
        status_payload["sdk_configured"],
        status_payload["lifeline_upstream_reachable"],
    )
    return HealthCheckResponse(**status_payload)


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
        except LifelineValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except LifelineAuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
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
    except LifelineValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LifelineAuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except LifelineClientRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return AnalyzeEcgResponse(**result)


@app.post("/generate-api-key", response_model=GenerateApiKeyResponse)
def generate_api_key(payload: Optional[GenerateApiKeyRequest] = None) -> GenerateApiKeyResponse:
    email = (payload.email if payload and payload.email else "").strip()
    if not email:
        email = DEFAULT_GENERATE_API_EMAIL

    try:
        api_key = vlm_client.generate_api_key(email=email)
    except LifelineServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LifelineValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LifelineAuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except LifelineClientRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return GenerateApiKeyResponse(status="success", api_key=api_key)


@app.post("/analyze-ecg-dynamic", response_model=DynamicAnalyzeResponse)
async def analyze_ecg_dynamic(
    request: Request,
    prompt_form: Optional[str] = Form(default=None, alias="prompt"),
    context_form: Optional[str] = Form(default=None, alias="context"),
    image_file: Optional[UploadFile] = File(default=None),
    image_url_form: Optional[str] = Form(default=None, alias="image_url"),
) -> DynamicAnalyzeResponse:
    prompt = prompt_form
    context = context_form
    image_url = image_url_form

    if request.headers.get("content-type", "").startswith("application/json"):
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
        raw_prompt = payload.get("prompt")
        raw_context = payload.get("context")
        raw_image_url = payload.get("image_url")
        prompt = raw_prompt if isinstance(raw_prompt, str) else None
        context = raw_context if isinstance(raw_context, str) else None
        image_url = raw_image_url if isinstance(raw_image_url, str) else None

    if not prompt or not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt is required")

    image_bytes = None
    mime_type = None

    if image_file is not None:
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
        mime_type = image_file.content_type

    if image_url and not _is_valid_http_url(image_url):
        raise HTTPException(
            status_code=400,
            detail="Invalid image_url. Use an absolute HTTP/HTTPS URL.",
        )

    try:
        raw_result = vlm_client.analyze_dynamic(
            prompt=prompt,
            context=context,
            image_bytes=image_bytes,
            mime_type=mime_type,
            image_url=image_url,
        )
    except LifelineSdkVersionError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except LifelineServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LifelineValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LifelineAuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except LifelineClientRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    description_text = _result_to_text(raw_result)
    logger.info(
        "analyze_dynamic_completed raw_result_type=%s description_length=%d",
        type(raw_result).__name__,
        len(description_text),
    )
    
    return DynamicAnalyzeResponse(
        status="success",
        description=description_text,
        raw_result=raw_result,
    )


@app.post("/chat-ecg", response_model=ChatEcgResponse)
def chat_ecg(payload: ChatEcgRequest) -> ChatEcgResponse:
    last_two_messages = payload.previous_messages[-2:]

    labelled_history = "\n".join(
        [
            f"PREVIOUS_MESSAGE_{index + 1}_{message.role.upper()}: {message.content}"
            for index, message in enumerate(last_two_messages)
        ]
    )
    if not labelled_history:
        labelled_history = "PREVIOUS_MESSAGE_1_NONE: No prior conversation context"

    labelled_prompt = (
        "You are continuing an ECG discussion. Use the provided context and answer clearly.\n\n"
        f"GENERATED_ECG_DESCRIPTION: {payload.description}\n"
        f"NEW_USER_PROMPT: {payload.prompt}\n"
        f"{labelled_history}"
    )

    try:
        raw_result = vlm_client.analyze_dynamic(prompt=labelled_prompt)
    except LifelineSdkVersionError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except LifelineServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LifelineValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LifelineAuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except LifelineClientRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ChatEcgResponse(status="success", answer=_result_to_text(raw_result))
