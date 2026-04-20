# Lifeline API

FastAPI backend for Lifeline AI ECG workflows.

This service handles:

- ECG analysis from uploaded files or image URLs
- Dynamic prompt-based ECG analysis
- Context-aware ECG follow-up chat
- API key generation via Lifeline SDK
- Health checks and unified error responses

## Tech Stack

- Python 3.11
- FastAPI
- Uvicorn
- Pydantic v2
- lifelinecg-sdk

## Endpoints

- `GET /health`
- `POST /analyze-ecg`
- `POST /analyze-ecg-dynamic`
- `POST /chat-ecg`
- `POST /generate-api-key`
- `GET /analysis-history`
- `DELETE /analysis-history/{analysis_id}`

## Request and Response Summary

### `POST /analyze-ecg`

Accepted input:

- `multipart/form-data` with `image_file`
- `application/json` with `image_url`

Validation:

- File types: `image/png`, `image/jpeg`, `image/jpg`, `image/webp`
- Max file size: 5 MB

Success shape:

```json
{
  "status": "success",
  "analysis": {
    "diagnosis": "...",
    "confidence": 0.85,
    "findings": ["..."],
    "recommendation": "..."
  }
}
```

### `POST /analyze-ecg-dynamic`

Request requirements:

- Required: `prompt`
- Optional: `context`
- Optional: `image_file` or `image_url`

Success shape:

```json
{
  "status": "success",
  "description": "...",
  "raw_result": {}
}
```

### `POST /chat-ecg`

Request shape:

```json
{
  "description": "Generated ECG description",
  "prompt": "Follow-up question",
  "previous_messages": [
    { "role": "user", "content": "..." },
    { "role": "ai", "content": "..." }
  ]
}
```

Success shape:

```json
{
  "status": "success",
  "answer": "..."
}
```

### `POST /generate-api-key`

- Accepts optional JSON body with `email`
- Uses the Lifeline SDK key generation flow

Success shape:

```json
{
  "status": "success",
  "api_key": "lfai_xxx"
}
```

Standard error shape for handled failures:

```json
{
  "status": "error",
  "error": {
    "code": 400,
    "message": "Validation error message"
  }
}
```

### `GET /analysis-history`

- Returns recent analysis records (newest first)
- Optional query param: `limit` (1 to 200, default 50)

Success shape:

```json
{
  "status": "success",
  "records": [
    {
      "analysis_id": "uuid",
      "analysis_type": "analyze-ecg",
      "source": "url",
      "created_at": "2026-04-21T10:00:00+00:00"
    }
  ]
}
```

### `DELETE /analysis-history/{analysis_id}`

- Deletes a specific analysis history record by id

Success shape:

```json
{
  "status": "success",
  "deleted_analysis_id": "uuid"
}
```

## Local Development

From repository root:

```bash
cd lifeline.api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API URL:

- `http://localhost:8000`

## Testing

Install test dependencies:

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

Run tests:

```bash
pytest -q --maxfail=1 --disable-warnings
```

## Health Check

`GET /health` includes:

- `status`: `ok` or `degraded`
- `service`: `lifeline-api`
- `sdk_configured`: whether SDK client is initialized
- `lifeline_upstream_reachable`: upstream availability check result

## Notes

- CORS is currently configured as allow-all in `main.py`.
- Lifeline SDK integration and normalization logic is in `app/services/vlm_client.py`.
- API schemas are defined in `app/schemas.py`.
