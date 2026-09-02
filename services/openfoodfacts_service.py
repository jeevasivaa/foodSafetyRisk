"""
services/openfoodfacts_service.py — Open Food Facts API Integration
"""
import requests
import json
from typing import Dict, Any, Optional

def fetch_product_info(barcode: str) -> Dict[str, Any]:
    """
    Fetch product information from the Open Food Facts API.
    
    Args:
        barcode: The product barcode string.
        
    Returns:
        dict: Product details or error message.
    """
    _default = {
        "success": False,
        "source": "open_food_facts",
        "cached": False,
        "product": None,
        "message": "Product not found in Open Food Facts."
    }
    
    if not barcode or not barcode.strip() or barcode == "Not Detected":
        return _default

    url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
    
    try:
        # Open Food Facts requires a User-Agent to prevent 403 errors
        headers = {
            "User-Agent": "FoodQualityAI/1.0 - Academic Project"
        }
        # 5-second timeout for the API call to prevent hanging the app
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code != 200:
            _default["message"] = f"API error: {response.status_code}"
            return _default
            
        data = response.json()
        
        if data.get("status") != 1:
            return _default
            
        p = data.get("product", {})
        
        # Extract structured data
        product_info = {
            "barcode": barcode,
            "name": p.get("product_name", "Unknown Product"),
            "brand": p.get("brands", "Unknown Brand"),
            "quantity": p.get("quantity", "Unknown"),
            "category": p.get("categories", "Unknown"),
            "ingredients": p.get("ingredients_text", ""),
            "allergens": p.get("allergens", ""),
            "nutrition_json": json.dumps(p.get("nutriments", {})),
            "image_url": p.get("image_url", ""),
            "source": "open_food_facts"
        }
        
        return {
            "success": True,
            "source": "open_food_facts",
            "cached": False,
            "product": product_info,
            "message": "Product found successfully."
        }
        
    except requests.exceptions.Timeout:
        _default["message"] = "Product database temporarily unavailable (timeout)."
        return _default
    except requests.exceptions.RequestException as e:
        _default["message"] = "Network error while reaching product database."
        return _default
    except Exception as e:
        print(f"[Open Food Facts Error] {e}")
        _default["message"] = "An unexpected error occurred during product lookup."
        return _default
