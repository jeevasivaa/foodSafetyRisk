# AI Food Quality Analysis System

## Phase 3 Features
- **Barcode Detection**: Uses `pyzbar` (falls back to OpenCV if DLLs are missing on Windows).
- **Open Food Facts Integration**: Retrieves comprehensive product data using standard global barcode registries.
- **Gemini AI Visual Inspection**: Independently evaluates the visible package condition without conflating with product identity.
- **Unified Result UI**: Clearly separates product data from visual inspection.

## Setup Instructions

### Windows Pre-requisites for pyzbar
If `pyzbar` fails to load with a `FileNotFoundError` for `libiconv.dll` or `libzbar-64.dll`:
1. You must install the Visual C++ Redistributable for Visual Studio 2013.
2. If issues persist, the backend gracefully falls back to `cv2.barcode.BarcodeDetector()`.

### Running the application
```bash
pip install -r requirements.txt
python app.py
```
