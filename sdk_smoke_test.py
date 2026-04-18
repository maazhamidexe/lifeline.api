import os

from lifelinecg_sdk import LifelineClient

# Initialize the client pointing to your live Hugging Face Space
BASE_URL = os.getenv("LIFELINE_SDK_BASE_URL", "https://asad999-lifelineopenapi.hf.space")
TEST_IMAGE = os.getenv("LIFELINE_TEST_IMAGE", "download.jpeg")
client = LifelineClient(base_url=BASE_URL)

# =========================================================
# TEST 1: Key Generation
# =========================================================
print("TEST 1: Generating API Key...")
try:
    key_response = client.generate_api_key(
        email=os.getenv("LIFELINE_GENERATE_API_EMAIL", "doctor@lifelinetest.com"),
        admin_secret=os.getenv("LIFELINE_ADMIN_SECRET", "super_secret_dev_key"),
    )
    my_api_key = key_response["api_key"]
    print(f"Success! New Key: {my_api_key}")

    # Assign the new key to our client so we can use it for the next tests
    client.api_key = my_api_key
except Exception as e:
    print(f"Key Generation Failed: {e}")
    raise SystemExit(1)

print("-" * 50)

# =========================================================
# TEST 2: Original Pipeline (Image Only)
# =========================================================
print(f"TEST 2: Original Pipeline using {TEST_IMAGE}...")
try:
    original_report = client.analyze(image_path=TEST_IMAGE)
    print("Original Report Received!")
    print(original_report)
except Exception as e:
    print(f"Original Pipeline Failed: {e}")

print("-" * 50)

# =========================================================
# TEST 3: Dynamic Pipeline (Prompt + Image + Context)
# =========================================================
print("TEST 3: Dynamic Pipeline (Prompt + Image + Context)...")
try:
    dynamic_report = client.analyze_dynamic(
        prompt="Analyze this ECG. Are there any signs of myocardial infarction?",
        image_path=TEST_IMAGE,
        context="Patient is a 55-year-old male presenting with severe chest pain.",
    )
    print("Dynamic Report Received!")
    print(dynamic_report)
except Exception as e:
    print(f"Dynamic Pipeline Failed: {e}")

print("-" * 50)

# =========================================================
# BONUS TEST: Dynamic Pipeline (Text-Only)
# =========================================================
print("BONUS TEST: Dynamic Pipeline (Text Only)...")
try:
    text_only_report = client.analyze_dynamic(
        prompt="What are the standard protocols for treating Bradycardia?"
    )
    print("Text-Only Report Received!")
    print(text_only_report)
except Exception as e:
    print(f"Text-Only Pipeline Failed: {e}")
