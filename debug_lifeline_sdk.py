#!/usr/bin/env python
"""
Debug script to diagnose Lifeline SDK issues.
Run this to see exactly what the SDK is returning.
"""
import os
import sys
import json
from lifelinecg_sdk import LifelineClient

# Configuration
BASE_URL = os.getenv("LIFELINE_SDK_BASE_URL", "https://asad999-lifelineopenapi.hf.space")
API_KEY = os.getenv("LIFELINE_SDK_API_KEY", "dasa_20550346891082275954")
ADMIN_SECRET = os.getenv("LIFELINE_ADMIN_SECRET", "lifelineasad9009")
TEST_EMAIL = "asadirfan7533@gmail.com"
TEST_IMAGE = os.getenv("LIFELINE_TEST_IMAGE", "download.jpeg")

print("=" * 70)
print("LIFELINE SDK DEBUG SCRIPT")
print("=" * 70)

# Step 1: Health Check
print("\n[1/4] Checking upstream connectivity...")
try:
    from urllib.request import urlopen
    with urlopen(BASE_URL, timeout=5) as response:
        print(f"[OK] Upstream is reachable: {BASE_URL}")
        print(f"  Status: {response.status}")
except Exception as e:
    print(f"[FAILED] Failed to reach upstream: {e}")
    sys.exit(1)

# Step 2: Initialize client
print("\n[2/4] Initializing Lifeline SDK client...")
try:
    client = LifelineClient(api_key=API_KEY, base_url=BASE_URL)
    print(f"[OK] Client initialized with API key (last 8 chars): ...{API_KEY[-8:]}")
except Exception as e:
    print(f"[FAILED] Failed to initialize client: {e}")
    sys.exit(1)

# Step 3: Test analyze_dynamic with text only
print("\n[3/4] Testing analyze_dynamic (text-only)...")
try:
    result = client.analyze_dynamic(
        prompt="What are the standard protocols for treating Bradycardia?"
    )
    print(f"[OK] Text-only analysis completed")
    print(f"  Response type: {type(result).__name__}")
    print(f"  Response (first 200 chars): {str(result)[:200]}")
    print(f"  Full response:")
    if isinstance(result, dict):
        print(json.dumps(result, indent=2, default=str))
    else:
        print(repr(result))
except Exception as e:
    print(f"[FAILED] Text-only analysis failed: {e}")
    import traceback
    traceback.print_exc()

# Step 4: Test with image if available
if os.path.exists(TEST_IMAGE):
    print(f"\n[4/4] Testing analyze_dynamic with image ({TEST_IMAGE})...")
    try:
        result = client.analyze_dynamic(
            prompt="Analyze this ECG. What does it show?",
            image_path=TEST_IMAGE,
        )
        print(f"[OK] Image analysis completed")
        print(f"  Response type: {type(result).__name__}")
        print(f"  Response (first 200 chars): {str(result)[:200]}")
        print(f"  Full response:")
        if isinstance(result, dict):
            print(json.dumps(result, indent=2, default=str))
        else:
            print(repr(result))
    except Exception as e:
        print(f"[FAILED] Image analysis failed: {e}")
        import traceback
        traceback.print_exc()
else:
    print(f"\n[4/4] Test image not found: {TEST_IMAGE}")

print("\n" + "=" * 70)
print("DEBUG COMPLETE")
print("=" * 70)
print("\nIf you see 'dummy text' or placeholder responses above,")
print("the issue is with the Lifeline SDK/API, not your integration.")
print("\nTroubleshooting steps:")
print("1. Verify LIFELINE_SDK_API_KEY is valid and hasn't expired")
print("2. Check if the Hugging Face Space is running")
print("3. Try generating a new API key using the generate_api_key endpoint")
print("4. Check the Lifeline service status/logs")
