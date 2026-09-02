"""
services/barcode_service.py — Barcode detection using pyzbar
"""
import cv2
import numpy as np
from typing import Dict, Any

# Try to import pyzbar, but handle Windows DLL missing issues gracefully
try:
    from pyzbar.pyzbar import decode, ZBarSymbol
    PYZBAR_AVAILABLE = True
except Exception as e:
    print(f"[Warning] pyzbar not available (likely missing Windows DLLs): {e}")
    PYZBAR_AVAILABLE = False

def detect_barcode(image_path: str) -> Dict[str, Any]:
    """
    Detect barcodes in the given image using pyzbar.
    
    Args:
        image_path: Path to the image file.
        
    Returns:
        dict: Detection result containing 'detected', 'barcode', 'type', 'bbox', 'message'
    """
    _default = {
        "detected": False,
        "barcode": None,
        "type": None,
        "bbox": None,
        "message": "No barcode detected"
    }

    try:
        # Load image using OpenCV
        img = cv2.imread(image_path)
        if img is None:
            return {"detected": False, "barcode": None, "message": "Failed to load image."}

        # Convert to grayscale for better detection
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Decode barcodes in the image
        if PYZBAR_AVAILABLE:
            decoded_objects = decode(gray)
            
            if not decoded_objects:
                # Try increasing contrast/thresholding if the first pass fails
                _, thresh = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                decoded_objects = decode(thresh)
                
            if decoded_objects:
                primary_barcode = decoded_objects[0]
                barcode_data = primary_barcode.data.decode('utf-8')
                barcode_type = primary_barcode.type
                rect = primary_barcode.rect
                bbox = {"x": rect.left, "y": rect.top, "width": rect.width, "height": rect.height}
                
                return {
                    "detected": True,
                    "barcode": barcode_data,
                    "type": barcode_type,
                    "bbox": bbox,
                    "message": "Barcode detected successfully via pyzbar."
                }
                
        # Fallback to OpenCV BarcodeDetector
        try:
            barcode_detector = cv2.barcode.BarcodeDetector()
            result = barcode_detector.detectAndDecode(gray)
            
            # Handle different OpenCV versions returning 3 or 4 values
            ok = result[0]
            decoded_info = result[1] if len(result) > 1 else None
            decoded_type = result[2] if len(result) > 2 else None
            corners = result[3] if len(result) > 3 else None
            
            if ok and decoded_info and len(decoded_info) > 0 and decoded_info[0]:
                val = decoded_info[0] if isinstance(decoded_info, (list, tuple)) else decoded_info
                btype = decoded_type[0] if isinstance(decoded_type, (list, tuple)) else decoded_type
                
                if val and str(val).strip():
                    # Calculate bbox from corners
                    c = corners[0] if corners is not None else None
                    bbox = None
                    if c is not None and len(c) == 4:
                        xs = [p[0] for p in c]
                        ys = [p[1] for p in c]
                        bbox = {"x": min(xs), "y": min(ys), "width": max(xs)-min(xs), "height": max(ys)-min(ys)}
                        
                    return {
                        "detected": True,
                        "barcode": str(val).strip(),
                        "type": str(btype) if btype else "Barcode",
                        "bbox": bbox,
                        "message": "Barcode detected successfully via OpenCV fallback."
                    }
        except AttributeError:
            pass
            
        return _default

    except Exception as e:
        print(f"[Barcode Service Error] {e}")
        return {"detected": False, "barcode": None, "message": f"Detection error: {str(e)}"}
