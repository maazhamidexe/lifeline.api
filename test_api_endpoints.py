#!/usr/bin/env python
"""
Manual test script for the FastAPI Lifeline integration.
Run this after starting the FastAPI server.
"""
import requests
import json
import sys

# Configuration
API_BASE_URL = "http://localhost:8000"

def test_health():
    """Test the health check endpoint."""
    print("\n" + "=" * 70)
    print("TEST 1: Health Check")
    print("=" * 70)
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        response.raise_for_status()
        data = response.json()
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2)}")
        return data.get("lifeline_upstream_reachable", False)
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_dynamic_text_only():
    """Test dynamic analysis with text only (no image)."""
    print("\n" + "=" * 70)
    print("TEST 2: Dynamic Analysis (Text Only)")
    print("=" * 70)
    try:
        payload = {
            "prompt": "What are the standard protocols for treating Bradycardia?",
        }
        response = requests.post(
            f"{API_BASE_URL}/analyze-ecg-dynamic",
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        print(f"Status: {response.status_code}")
        print(f"Description (first 200 chars):")
        print(f"  {data.get('description', '')[:200]}...")
        print(f"\nFull Response:")
        print(json.dumps(data, indent=2, default=str)[:500])
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_dynamic_with_image():
    """Test dynamic analysis with image and prompt."""
    print("\n" + "=" * 70)
    print("TEST 3: Dynamic Analysis (Image + Text)")
    print("=" * 70)
    
    # Check if test image exists
    import os
    if not os.path.exists("download.jpeg"):
        print("Test image 'download.jpeg' not found. Skipping this test.")
        print("To test with image: Place an ECG image file named 'download.jpeg' in lifeline.api/")
        return None
    
    try:
        with open("download.jpeg", "rb") as f:
            files = {"image_file": f}
            data = {"prompt": "Analyze this ECG image. What does it show?"}
            response = requests.post(
                f"{API_BASE_URL}/analyze-ecg-dynamic",
                files=files,
                data=data,
                timeout=30
            )
        response.raise_for_status()
        data = response.json()
        print(f"Status: {response.status_code}")
        print(f"Description (first 200 chars):")
        print(f"  {data.get('description', '')[:200]}...")
        return True
    except FileNotFoundError:
        print("Test image not found")
        return None
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_generate_api_key():
    """Test API key generation."""
    print("\n" + "=" * 70)
    print("TEST 4: Generate API Key")
    print("=" * 70)
    try:
        response = requests.post(
            f"{API_BASE_URL}/generate-api-key",
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        print(f"Status: {response.status_code}")
        api_key = data.get("api_key", "")
        if api_key:
            print(f"Generated API Key (last 8 chars): ...{api_key[-8:]}")
            print(f"Full Response: {json.dumps(data, indent=2)}")
        else:
            print("No API key returned")
        return bool(api_key)
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def main():
    print("=" * 70)
    print("LIFELINE API INTEGRATION TESTS")
    print("=" * 70)
    print(f"API Base URL: {API_BASE_URL}")
    
    # Check if server is running
    try:
        requests.get(f"{API_BASE_URL}/health", timeout=2)
    except requests.exceptions.ConnectionError:
        print(f"\nERROR: Cannot connect to FastAPI server at {API_BASE_URL}")
        print("Make sure to start the server first:")
        print("  cd lifeline.api")
        print("  uvicorn main:app --reload --host 0.0.0.0 --port 8000")
        sys.exit(1)
    
    # Run tests
    results = {
        "health": test_health(),
        "dynamic_text_only": test_dynamic_text_only(),
        "dynamic_with_image": test_dynamic_with_image(),
        "generate_api_key": test_generate_api_key(),
    }
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    for test_name, result in results.items():
        if result is None:
            status = "SKIPPED"
        elif result:
            status = "PASSED"
        else:
            status = "FAILED"
        print(f"{test_name.upper()}: {status}")
    
    all_passed = all(v for v in results.values() if v is not None)
    print("\n" + ("=" * 70))
    if all_passed:
        print("All tests PASSED!")
    else:
        print("Some tests FAILED. Check the output above.")
    print("=" * 70)

if __name__ == "__main__":
    main()
