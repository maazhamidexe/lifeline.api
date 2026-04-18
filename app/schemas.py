from typing import Literal

from pydantic import BaseModel, Field


class AnalyzeEcgAnalysis(BaseModel):
    diagnosis: str
    confidence: float = Field(..., ge=0, le=1)
    findings: list[str]
    recommendation: str


class AnalyzeEcgResponse(BaseModel):
    status: Literal["success"]
    analysis: AnalyzeEcgAnalysis


class GenerateApiKeyResponse(BaseModel):
    status: Literal["success"]
    api_key: str
