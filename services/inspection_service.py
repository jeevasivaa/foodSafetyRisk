"""
services/inspection_service.py — Unified Inspection Workflow (Phase 3)
"""
from typing import Dict, Any
from services.barcode_service import detect_barcode
from services.product_service import get_product_by_barcode
from ai.gemini_scanner import analyze_with_gemini

def perform_unified_inspection(image_path: str) -> Dict[str, Any]:
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
    barcode_data = detect_barcode(image_path)
    if barcode_data["detected"]:
        result["barcode"]["detected"] = True
        result["barcode"]["number"] = barcode_data["barcode"]
        result["barcode"]["type"] = barcode_data["type"]
        
        # 2. Open Food Facts Lookup
        off_data = get_product_by_barcode(barcode_data["barcode"])
        if off_data["success"] and off_data["product"]:
            p = off_data["product"]
            result["product"]["name"] = p.get("name", "Unknown")
            result["product"]["brand"] = p.get("brand", "Unknown")
            result["product"]["quantity"] = p.get("quantity", "")
            result["product"]["category"] = p.get("category", "")
            result["product"]["source"] = p.get("source", "open_food_facts")

    # 3. Gemini Visual Analysis
    ai_data = analyze_with_gemini(image_path)
    result["ai_analysis"] = ai_data
    
    return result
