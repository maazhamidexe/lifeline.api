from fastapi.testclient import TestClient

import main as api_main


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



def test_health_returns_expected_payload(monkeypatch):
    monkeypatch.setattr(api_main, "vlm_client", _StubVLMClient())
    client = TestClient(api_main.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["sdk_configured"] is True



def test_analyze_ecg_requires_file_or_url(monkeypatch):
    monkeypatch.setattr(api_main, "vlm_client", _StubVLMClient())
    client = TestClient(api_main.app)

    response = client.post("/analyze-ecg")

    assert response.status_code == 400
    assert "either image_file or image_url" in response.json()["error"]["message"].lower()



def test_analyze_ecg_rejects_invalid_url(monkeypatch):
    monkeypatch.setattr(api_main, "vlm_client", _StubVLMClient())
    client = TestClient(api_main.app)

    response = client.post("/analyze-ecg", json={"image_url": "not-a-url"})

    assert response.status_code == 400
    assert "invalid image_url" in response.json()["error"]["message"].lower()



def test_analyze_ecg_accepts_valid_image_url(monkeypatch):
    monkeypatch.setattr(api_main, "vlm_client", _StubVLMClient())
    client = TestClient(api_main.app)

    response = client.post(
        "/analyze-ecg",
        json={"image_url": "https://example.com/ecg.png"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert "analysis" in response.json()
