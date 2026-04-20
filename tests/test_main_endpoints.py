from fastapi.testclient import TestClient

import main as api_main
from app.services.analysis_history_store import AnalysisHistoryStore


class _StubVLMClient:
    can_analyze = True

    def __init__(self):
        self.last_dynamic_kwargs = None

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
        self.last_dynamic_kwargs = kwargs
        return {"description": "Dynamic analysis response"}


def _fresh_client(monkeypatch):
    stub_vlm_client = _StubVLMClient()
    monkeypatch.setattr(api_main, "vlm_client", stub_vlm_client)
    monkeypatch.setattr(api_main, "analysis_history_store", AnalysisHistoryStore(max_records=100))
    return TestClient(api_main.app), stub_vlm_client



def test_health_returns_expected_payload(monkeypatch):
    client, _ = _fresh_client(monkeypatch)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["sdk_configured"] is True



def test_analyze_ecg_requires_file_or_url(monkeypatch):
    client, _ = _fresh_client(monkeypatch)

    response = client.post("/analyze-ecg")

    assert response.status_code == 400
    assert "either image_file or image_url" in response.json()["error"]["message"].lower()



def test_analyze_ecg_rejects_invalid_url(monkeypatch):
    client, _ = _fresh_client(monkeypatch)

    response = client.post("/analyze-ecg", json={"image_url": "not-a-url"})

    assert response.status_code == 400
    assert "invalid image_url" in response.json()["error"]["message"].lower()



def test_analyze_ecg_accepts_valid_image_url(monkeypatch):
    client, _ = _fresh_client(monkeypatch)

    response = client.post(
        "/analyze-ecg",
        json={"image_url": "https://example.com/ecg.png"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert "analysis" in response.json()
    assert response.json().get("analysis_id")


def test_analysis_history_delete_flow(monkeypatch):
    client, _ = _fresh_client(monkeypatch)

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


def test_chat_ecg_maps_prompt_context_and_image_url(monkeypatch):
    client, stub_vlm_client = _fresh_client(monkeypatch)

    response = client.post(
        "/chat-ecg",
        json={
            "description": "ECG suggests sinus rhythm with mild ST changes.",
            "prompt": "Is this concerning for acute MI?",
            "image": "https://example.com/uploaded-ecg.png",
            "previous_messages": [
                {"role": "user", "content": "Please review this ECG."},
                {"role": "ai", "content": "I can help with that."},
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["answer"] == "Dynamic analysis response"

    assert stub_vlm_client.last_dynamic_kwargs is not None
    assert stub_vlm_client.last_dynamic_kwargs["prompt"] == "Is this concerning for acute MI?"
    assert stub_vlm_client.last_dynamic_kwargs["image_url"] == "https://example.com/uploaded-ecg.png"
    assert stub_vlm_client.last_dynamic_kwargs["image_bytes"] is None
    assert stub_vlm_client.last_dynamic_kwargs["mime_type"] is None
    assert "GENERATED_ECG_DESCRIPTION: ECG suggests sinus rhythm with mild ST changes." in stub_vlm_client.last_dynamic_kwargs["context"]
    assert "PREVIOUS_MESSAGE_1_USER: Please review this ECG." in stub_vlm_client.last_dynamic_kwargs["context"]
    assert "PREVIOUS_MESSAGE_2_AI: I can help with that." in stub_vlm_client.last_dynamic_kwargs["context"]
