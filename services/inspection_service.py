"""
services/inspection_service.py — Unified Inspection Workflow (Phase 3)
"""
from typing import Dict, Any
from services.barcode_service import detect_barcode
from services.product_service import get_product_by_barcode
from ai.gemini_scanner import analyze_with_gemini

def perform_unified_inspection(image_path: str, manual_barcode: str = "", mfg_date: str = "", exp_date: str = "") -> Dict[str, Any]:
    """
    Combines Barcode Detection + Open Food Facts + Gemini Visual Analysis.
    
    Returns a unified inspection result.
    """
    result = {
        "barcode": {
            "number": "Not Detected",
            "type": "",
            "detected": False
        },
        "product": {
            "name": "Unknown",
            "brand": "Unknown",
            "quantity": "",
            "category": "",
            "source": ""
        },
        "ai_analysis": {}
    }
    
    # 1. Barcode Detection
    if manual_barcode:
        result["barcode"]["detected"] = True
        result["barcode"]["number"] = manual_barcode
        result["barcode"]["type"] = "Manual Entry"
    elif image_path:
        barcode_data = detect_barcode(image_path)
        if barcode_data["detected"]:
            result["barcode"]["detected"] = True
            result["barcode"]["number"] = barcode_data["barcode"]
            result["barcode"]["type"] = barcode_data["type"]
        
    # 2. Open Food Facts Lookup
    if result["barcode"]["detected"]:
        off_data = get_product_by_barcode(result["barcode"]["number"])
        if off_data["success"] and off_data["product"]:
            p = off_data["product"]
            result["product"]["name"] = p.get("name", "Unknown")
            result["product"]["brand"] = p.get("brand", "Unknown")
            result["product"]["quantity"] = p.get("quantity", "")
            result["product"]["category"] = p.get("category", "")
            result["product"]["source"] = p.get("source", "open_food_facts")

    # 3. Gemini Visual Analysis
    if image_path:
        ai_data = analyze_with_gemini(image_path)
        result["ai_analysis"] = ai_data
    else:
        # Default empty AI analysis if no image was provided
        result["ai_analysis"] = {
            "expiry_date": "Not Scanned",
            "manufacturing_date": "Not Scanned",
            "batch_number": "Not Scanned",
            "mrp": "Not Scanned",
            "package_condition": "Not Scanned",
            "damage_percentage": "0%",
            "quality_score": "0",
            "status": "Not Scanned",
            "summary": "No image was uploaded, so visual inspection was skipped. Product identified purely via manual barcode.",
            "ocr_text": "",
            "ocr_confidence": "0",
            "damage_type": "Not Scanned",
            "damage_conf": "0",
            "recommendation": "Submit an image for visual damage assessment."
        }
        
    # 4. Override with manual dates if provided
    if mfg_date:
        result["ai_analysis"]["manufacturing_date"] = mfg_date
    if exp_date:
        result["ai_analysis"]["expiry_date"] = exp_date
    
    return result
