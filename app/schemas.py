from typing import Any, Literal

from pydantic import BaseModel, Field


class AnalyzeEcgAnalysis(BaseModel):
    diagnosis: str
    confidence: float = Field(..., ge=0, le=1)
    findings: list[str]
    recommendation: str


class AnalyzeEcgResponse(BaseModel):
    status: Literal["success"]
    analysis: AnalyzeEcgAnalysis
    analysis_id: str | None = None


class GenerateApiKeyResponse(BaseModel):
    status: Literal["success"]
    api_key: str


class GenerateApiKeyRequest(BaseModel):
    email: str


class HealthCheckResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    sdk_configured: bool
    lifeline_upstream_reachable: bool


class DynamicAnalyzeResponse(BaseModel):
    status: Literal["success"]
    description: str
    raw_result: Any
    analysis_id: str | None = None


class AnalysisHistoryEntry(BaseModel):
    analysis_id: str
    analysis_type: Literal["analyze-ecg", "analyze-ecg-dynamic"]
    source: Literal["file", "url", "text-only"]
    created_at: str


class AnalysisHistoryListResponse(BaseModel):
    status: Literal["success"]
    records: list[AnalysisHistoryEntry]


class AnalysisDeleteResponse(BaseModel):
    status: Literal["success"]
    deleted_analysis_id: str


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "ai"]
    content: str


class ChatEcgRequest(BaseModel):
    description: str
    prompt: str
    previous_messages: list[ChatHistoryMessage] = Field(default_factory=list)
    image: str | None = None
    mime_type: str | None = None


class ChatEcgResponse(BaseModel):
    status: Literal["success"]
    answer: str
