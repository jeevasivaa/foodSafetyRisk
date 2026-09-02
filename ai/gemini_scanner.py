import os
import json
import base64
import requests

API_KEY = "AQ.Ab8RN6JTXXvJrR5wDhLXKQAEmcbx5C-hjDmaTS_GAIrmZcZJaQ"
# Use Gemini 3.6 Flash which is the latest stable version available in this environment
MODEL_NAME = "gemini-3.6-flash"

SYSTEM_PROMPT = """
You are an expert AI for Food Packaging Visual Inspection.
Your task is to analyze an image of a food product package and return a strictly formatted JSON object with your physical observation.
Do NOT try to identify the product name, brand, or ingredients—this is handled by another system. Your job is ONLY to inspect the "Visible Package Condition" and "AI-Assisted Visual Inspection".

Please extract the following information from the image:
- "expiry_date": Expiry date if visible, or 'Not Detected'
- "manufacturing_date": Manufacturing date if visible, or 'Not Detected'
- "batch_number": Batch number if visible, or 'Not Detected'
- "mrp": MRP (price) if visible, or 'Not Detected'
- "ocr_text": A string containing the most important readable text.
- "ocr_confidence": Your confidence in the text reading as a percentage string (e.g., "95").

Then, analyze the physical condition of the packaging:
- "damage_type": E.g., 'Torn Package', 'Broken Seal', 'Leakage', 'Swollen Package', 'Damaged Label', or 'Package Appears Normal'.
- "package_condition": A general assessment strictly one of: 'Good', 'Fair', or 'Poor'.
- "damage_percentage": Estimated percentage of the package damaged (e.g., "0%", "20%").

Finally, provide a safety analysis based purely on visual evidence:
- "quality_score": A score from "0" to "100" based on the package condition (100 is perfect).
- "status": Overall status, strictly one of: 'Safe', 'Warning', 'Unsafe'.
- "summary": A brief 1-2 sentence paragraph describing the physical package condition (e.g., "The package is intact with no visible defects. The expiry date is clearly visible.").
- "recommendation": A short, actionable recommendation (e.g., "Safe to consume", "Do not consume, package is swollen").

Return ONLY valid JSON. Do not include markdown formatting like ```json or any other text.
"""

def analyze_with_gemini(image_path: str) -> dict:
    """
    Analyze the product image using the Gemini REST API.
    """
    _default = {
        "expiry_date":        "Not Detected",
        "manufacturing_date": "Not Detected",
        "package_condition":  "Fair",
        "damage_percentage":  "0%",
        "barcode":            "Not Detected",
        "quality_score":      "50",
        "status":             "Warning",
        "summary":            "Unable to generate summary.",
        "barcode_number":     "Not Detected",
        "barcode_type":       "",
        "batch_number":       "Not Detected",
        "mrp":                "Not Detected",
        "net_weight":         "Not Detected",
        "ocr_text":           "",
        "ocr_confidence":     "0",
        "damage_type":        "Package Appears Normal",
        "damage_conf":        "0",
        "annotated_image":    "",
        "recommendation":     "Unable to complete analysis using Gemini. Please try again.",
    }

    try:
        # Load image as base64
        with open(image_path, "rb") as f:
            image_data = f.read()
        b64_img = base64.b64encode(image_data).decode("utf-8")
        
        import mimetypes
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type:
            mime_type = "image/jpeg"

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={API_KEY}"
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": SYSTEM_PROMPT},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": b64_img
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json"
            }
        }

        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code != 200:
            print(f"[Gemini API Error] {response.status_code}: {response.text}")
            return _default
            
        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        
        result_data = json.loads(text)
        
        # Merge with default to ensure all keys exist
        for key in _default:
            if key not in result_data:
                result_data[key] = _default[key]
                
        # Backward compatibility for Phase 1
        result_data["barcode"] = result_data.get("barcode_number", "Not Detected")
        
        # Gemini won't create an annotated image, so we leave it empty
        result_data["annotated_image"] = ""
        
        return result_data

    except Exception as e:
        print(f"[Gemini Exception] Error analyzing image: {e}")
        return _default
