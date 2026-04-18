#!/usr/bin/env python
"""
Test the FastAPI integration with Lifeline SDK.
"""
import json
from app.services.vlm_client import _dynamic_result_to_text, _is_placeholder_diagnosis

# Inline the _result_to_text function for testing
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

# Test case 1: Text-only response from SDK
sdk_response_text_only = {
    "status": "success",
    "modality_used": "Text Only",
    "final_report": "**Primary Summary**\nNo specific findings or diagnostic information were identified from the available data."
}

print("=" * 70)
print("TEST 1: Text-only SDK Response")
print("=" * 70)
print(f"Input: {json.dumps(sdk_response_text_only, indent=2)}")
result = _dynamic_result_to_text(sdk_response_text_only)
print(f"\nExtracted text:\n{result}")
print()

# Test case 2: Image with ECG analysis
sdk_response_with_image = {
    "status": "success",
    "modality_used": "Image+Text",
    "final_report": "ECG findings suggest normal sinus rhythm with no acute changes."
}

print("=" * 70)
print("TEST 2: Image+Text SDK Response")
print("=" * 70)
print(f"Input: {json.dumps(sdk_response_with_image, indent=2)}")
result = _dynamic_result_to_text(sdk_response_with_image)
print(f"\nExtracted text:\n{result}")
print()

# Test case 3: Old format (diagnosis key)
old_format = {
    "diagnosis": "Normal sinus rhythm",
    "confidence": 0.95,
}

print("=" * 70)
print("TEST 3: Old Format Response (diagnosis key)")
print("=" * 70)
print(f"Input: {json.dumps(old_format, indent=2)}")
result = _result_to_text(old_format)
print(f"\nExtracted text:\n{result}")
print()

# Test case 4: String response
string_response = "Patient shows signs of atrial fibrillation. Recommend immediate consultation."

print("=" * 70)
print("TEST 4: String Response")
print("=" * 70)
print(f"Input: {repr(string_response)}")
result = _dynamic_result_to_text(string_response)
print(f"\nExtracted text:\n{result}")
print()

print("=" * 70)
print("ALL TESTS COMPLETE")
print("=" * 70)
