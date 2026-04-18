#!/usr/bin/env python
"""
Diagnostic script to test what the Lifeline SDK actually receives
and why it's returning 'No diagnosis provided'
"""
import os
import sys
import tempfile
from lifelinecg_sdk import LifelineClient

BASE_URL = "https://asad999-lifelineopenapi.hf.space"
API_KEY = "dasa_20550346891082275954"

print("=" * 80)
print("LIFELINE SDK - ECG ANALYSIS DIAGNOSTIC")
print("=" * 80)

client = LifelineClient(api_key=API_KEY, base_url=BASE_URL)

# TEST 1: Analyze without image (text-only)
print("\n[TEST 1] Analyze WITHOUT image (text-only mode)")
print("-" * 80)
try:
    result = client.analyze_dynamic(prompt="Provide ECG diagnosis for a normal rhythm")
    print("[OK] Success")
    print(f"  Response has 'final_report': {'final_report' in result}")
    if isinstance(result, dict) and 'final_report' in result:
        report_length = len(result['final_report'])
        print(f"  Report length: {report_length} chars")
        print(f"  Is placeholder?: {'No clinical findings' in result['final_report'] or 'No diagnostic' in result['final_report']}")
except Exception as e:
    print(f"[FAILED] {e}")

# TEST 2: Regular analyze() without image
print("\n[TEST 2] Regular analyze() WITHOUT image")
print("-" * 80)
try:
    # Create empty/dummy image
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(b"NOT_A_REAL_IMAGE")
        temp_path = f.name
    
    try:
        result = client.analyze(image_path=temp_path)
        print("[OK] Response received")
        print(f"  Type: {type(result)}")
        print(f"  Content (first 200 chars): {str(result)[:200]}")
        
        if isinstance(result, dict):
            diagnosis = result.get('diagnosis') or result.get('summary') or result.get('text') or 'N/A'
            print(f"  Diagnosis field: {diagnosis[:100]}")
            print(f"  Is 'No diagnosis'?: {'No diagnosis' in str(diagnosis)}")
    finally:
        os.remove(temp_path)
except Exception as e:
    print(f"[FAILED] {e}")

# TEST 3: What the normalize function sees
print("\n[TEST 3] What your backend's normalization sees")
print("-" * 80)

# Import the normalization function
sys.path.insert(0, 'c:\\Users\\pc\\fyp-lifeline\\lifeline.api')
from app.services.vlm_client import _normalize_sdk_result, _is_placeholder_diagnosis

# Simulate what the SDK returns
dummy_response = {
    "diagnosis": "No diagnosis provided",
    "confidence": 0,
    "findings": ["No major findings detected."],
}

print("SDK returns:")
print(f"  {dummy_response}")
print("\nNormalization function converts to:")
normalized = _normalize_sdk_result(dummy_response)
print(f"  {normalized}")
print("\nIs 'No diagnosis provided' treated as placeholder?")
print(f"  {_is_placeholder_diagnosis('No diagnosis provided')}")

# TEST 4: Check if analyze() method exists and works
print("\n[TEST 4] Testing with REAL-ISH ECG data (PNG header)")
print("-" * 80)
try:
    # Create a minimal valid PNG file
    png_header = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
    
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(png_header)
        temp_path = f.name
    
    try:
        result = client.analyze(image_path=temp_path)
        print("[OK] Response received")
        print(f"  Diagnosis: {result.get('diagnosis') if isinstance(result, dict) else result}")
        is_placeholder = _is_placeholder_diagnosis(str(result.get('diagnosis') or result))
        print(f"  Is placeholder?: {is_placeholder}")
    finally:
        os.remove(temp_path)
except Exception as e:
    print(f"[FAILED] {e}")

print("\n" + "=" * 80)
print("DIAGNOSTIC COMPLETE")
print("=" * 80)
print("\nSUMMARY:")
print("-" * 80)
print("If tests show 'No diagnosis provided' responses:")
print("  → The Lifeline SDK is returning placeholders for your images")
print("  → This could mean:")
print("    1. Your ECG images aren't in the right format")
print("    2. Your API key is invalid/expired")
print("    3. The Lifeline service is having issues")
print("    4. The images aren't being uploaded properly")
print("\nNEXT STEPS:")
print("  1. Try uploading different ECG images")
print("  2. Generate a NEW API key using /generate-api-key")
print("  3. Check if the image file is actually being received by the API")
print("  4. Add logging to see what bytes are being received")
print("=" * 80)
