import re
import random

def verify_fssai_licence(fssai_number):
    """
    Mock sandbox for CrimeScan FSSAI Licence Verification.
    Validates format and returns mock verification data.
    """
    if not fssai_number or str(fssai_number).strip().lower() in ["not detected", "none", ""]:
        return {
            "status": "error", 
            "message": "No FSSAI number provided or detected."
        }
        
    # Clean the number (remove non-digits just in case, though FSSAI is strictly 14 digits)
    cleaned_number = re.sub(r'\D', '', str(fssai_number))
    
    if len(cleaned_number) != 14:
        return {
            "status": "invalid", 
            "message": "Invalid FSSAI format (must be 14 digits)",
            "licence_no": fssai_number
        }
        
    # Mocking sandbox behavior based on the number to give varied results
    # For sandbox, if it starts with '1', we mock as Active. If '2', we mock as Expired/Invalid
    is_active = cleaned_number.startswith("1")
    
    if is_active:
        return {
            "status": "valid",
            "licence_no": cleaned_number,
            "company_name": "NutriGuard Verified Brands Pvt Ltd",
            "state": "Maharashtra",
            "valid_upto": "2027-12-31",
            "licence_status": "Active"
        }
    else:
        return {
            "status": "invalid",
            "licence_no": cleaned_number,
            "company_name": "Unknown Entity",
            "state": "N/A",
            "valid_upto": "2022-01-01",
            "licence_status": "Expired/Suspended"
        }
