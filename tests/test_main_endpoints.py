from fastapi.testclient import TestClient

import main as api_main
from app.services.analysis_history_store import AnalysisHistoryStore


class _StubVLMClient:
    can_analyze = True

    def health_status(self):
        return {
            "status": "ok",
            "service": "lifeline-api",
            "sdk_configured": True,
            "lifeline_upstream_reachable": True,
        }

    def analyze_from_file(self, image_bytes, mime_type):
        return {
            "status": "success",
            "analysis": {
                "diagnosis": "Normal sinus rhythm",
                "confidence": 0.95,
                "findings": ["No acute abnormalities"],
                "recommendation": "Routine follow-up",
            },
        }

    def analyze_from_url(self, image_url):
        return {
            "status": "success",
            "analysis": {
                "diagnosis": "Normal sinus rhythm",
                "confidence": 0.95,
                "findings": ["No acute abnormalities"],
                "recommendation": "Routine follow-up",
            },
        }

    def analyze_dynamic(self, **kwargs):
        return {"description": "Dynamic analysis response"}


def _fresh_client(monkeypatch):
    monkeypatch.setattr(api_main, "vlm_client", _StubVLMClient())
    monkeypatch.setattr(api_main, "analysis_history_store", AnalysisHistoryStore(max_records=100))
    return TestClient(api_main.app)



def test_health_returns_expected_payload(monkeypatch):
    client = _fresh_client(monkeypatch)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["sdk_configured"] is True



def test_analyze_ecg_requires_file_or_url(monkeypatch):
    client = _fresh_client(monkeypatch)

    response = client.post("/analyze-ecg")

    assert response.status_code == 400
    assert "either image_file or image_url" in response.json()["error"]["message"].lower()



def test_analyze_ecg_rejects_invalid_url(monkeypatch):
    client = _fresh_client(monkeypatch)

    response = client.post("/analyze-ecg", json={"image_url": "not-a-url"})

    assert response.status_code == 400
    assert "invalid image_url" in response.json()["error"]["message"].lower()



def test_analyze_ecg_accepts_valid_image_url(monkeypatch):
    client = _fresh_client(monkeypatch)

    response = client.post(
        "/analyze-ecg",
        json={"image_url": "https://example.com/ecg.png"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert "analysis" in response.json()
    assert response.json().get("analysis_id")


def test_analysis_history_delete_flow(monkeypatch):
    client = _fresh_client(monkeypatch)

    analyze_response = client.post(
        "/analyze-ecg",
        json={"image_url": "https://example.com/ecg.png"},
    )
    assert analyze_response.status_code == 200
    analysis_id = analyze_response.json()["analysis_id"]

    list_response = client.get("/analysis-history")
    assert list_response.status_code == 200
    records = list_response.json()["records"]
    assert any(record["analysis_id"] == analysis_id for record in records)

    delete_response = client.delete(f"/analysis-history/{analysis_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted_analysis_id"] == analysis_id

    missing_delete_response = client.delete(f"/analysis-history/{analysis_id}")
    assert missing_delete_response.status_code == 404
