"""
services/product_service.py — Product Caching Layer
"""
from models.db import get_db
from services.openfoodfacts_service import fetch_product_info
from typing import Dict, Any

def get_product_by_barcode(barcode: str) -> Dict[str, Any]:
    """
    Lookup product by barcode.
    1. Check SQLite cache (cached_products).
    2. If not found, check Open Food Facts.
    3. Save to cache if found in OFF.
    """
    _default = {
        "success": False,
        "source": "none",
        "cached": False,
        "product": None,
        "message": "Product not found."
    }
    
    if not barcode or barcode == "Not Detected":
        return _default
        
    db = get_db()
    
    # 1. Check local cache
    cached = db.execute(
        "SELECT * FROM cached_products WHERE barcode = ?", (barcode,)
    ).fetchone()
    
    if cached:
        return {
            "success": True,
            "source": cached["source"],
            "cached": True,
            "product": {
                "barcode": cached["barcode"],
                "name": cached["product_name"],
                "brand": cached["brand"],
                "quantity": cached["quantity"],
                "category": cached["category"],
                "ingredients": cached["ingredients"],
                "allergens": cached["allergens"],
                "nutrition_json": cached["nutrition_json"],
                "image_url": cached["image_url"],
                "source": cached["source"]
            },
            "message": "Product loaded from cache."
        }
        
    # 2. Check Open Food Facts
    off_data = fetch_product_info(barcode)
    
    if off_data["success"] and off_data["product"]:
        p = off_data["product"]
        
        # 3. Save to cache
        try:
            db.execute(
                """INSERT INTO cached_products
                   (barcode, product_name, brand, category, quantity,
                    ingredients, allergens, nutrition_json, image_url, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    p["barcode"], p["name"], p["brand"], p["category"], p["quantity"],
                    p["ingredients"], p["allergens"], p["nutrition_json"],
                    p["image_url"], p["source"]
                )
            )
            db.commit()
        except Exception as e:
            print(f"[Cache Error] Failed to cache product: {e}")
            
    return off_data
