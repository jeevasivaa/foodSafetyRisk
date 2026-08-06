/**
 * camera.js — Live Camera Scanning
 * ---------------------------------
 * Handles:
 *   - Camera permission & stream via MediaDevices API
 *   - Front / rear camera toggle (facingMode)
 *   - Frame capture to canvas → JPEG base64
 *   - AJAX POST to /scan/camera
 *   - Loading state & error handling
 */

/* ── State ─────────────────────────────────────────────────────────────────── */
let _stream       = null;
let _facingMode   = "environment";  // "environment" = rear, "user" = front
let _capturedBlob = null;

/* ── DOM refs (populated after DOMContentLoaded) ─────────────────────────── */
let _video, _canvas, _ctx, _previewImg;
let _startBtn, _captureBtn, _retakeBtn, _analyzeBtn, _switchBtn;
let _statusEl, _errorEl;

document.addEventListener("DOMContentLoaded", () => {
  _video      = document.getElementById("cameraVideo");
  _canvas     = document.getElementById("cameraCanvas");
  _previewImg = document.getElementById("capturedPreview");
  _startBtn   = document.getElementById("startCameraBtn");
  _captureBtn = document.getElementById("captureBtn");
  _retakeBtn  = document.getElementById("retakeBtn");
  _analyzeBtn = document.getElementById("analyzeBtn");
  _switchBtn  = document.getElementById("switchCameraBtn");
  _statusEl   = document.getElementById("cameraStatus");
  _errorEl    = document.getElementById("cameraError");

  if (_canvas) _ctx = _canvas.getContext("2d");

  // Bind buttons
  if (_startBtn)   _startBtn.addEventListener("click",   startCamera);
  if (_captureBtn) _captureBtn.addEventListener("click",  captureFrame);
  if (_retakeBtn)  _retakeBtn.addEventListener("click",   retake);
  if (_analyzeBtn) _analyzeBtn.addEventListener("click",  submitCapture);
  if (_switchBtn)  _switchBtn.addEventListener("click",   switchCamera);
});


/* ── Start camera ────────────────────────────────────────────────────────── */
async function startCamera() {
  _clearError();
  _setStatus("Requesting camera permission...");

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    _showError("Your browser does not support camera access. Please use Chrome, Edge, or Firefox.");
    return;
  }

  try {
    // Stop any existing stream
    _stopStream();

    _stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: _facingMode,
        width:  { ideal: 1280 },
        height: { ideal: 720  },
      },
      audio: false,
    });

    _video.srcObject = _stream;
    await _video.play();

    // Show camera UI
    _video.classList.remove("d-none");
    _startBtn.classList.add("d-none");
    _captureBtn.classList.remove("d-none");
    _switchBtn.classList.remove("d-none");

    _setStatus("Camera active — aim at the package and click Capture.");
  } catch (err) {
    console.error("Camera error:", err);
    if (err.name === "NotAllowedError") {
      _showError("Camera permission denied. Please allow camera access and try again.");
    } else if (err.name === "NotFoundError") {
      _showError("No camera found on this device.");
    } else {
      _showError("Could not access camera: " + err.message);
    }
  }
}


/* ── Capture frame ───────────────────────────────────────────────────────── */
function captureFrame() {
  if (!_stream || !_video) return;

  // Draw current video frame onto canvas
  _canvas.width  = _video.videoWidth  || 640;
  _canvas.height = _video.videoHeight || 480;
  _ctx.drawImage(_video, 0, 0, _canvas.width, _canvas.height);

  // Show preview image
  const dataUrl = _canvas.toDataURL("image/jpeg", 0.92);
  _previewImg.src = dataUrl;
  _previewImg.classList.remove("d-none");

  // Store captured data
  _capturedBlob = dataUrl;

  // Switch to post-capture UI
  _video.classList.add("d-none");
  _captureBtn.classList.add("d-none");
  _switchBtn.classList.add("d-none");
  _retakeBtn.classList.remove("d-none");
  _analyzeBtn.classList.remove("d-none");

  _stopStream();
  _setStatus("Image captured. Click Analyze to run AI analysis.");
}


/* ── Retake ──────────────────────────────────────────────────────────────── */
function retake() {
  _capturedBlob = null;
  _previewImg.classList.add("d-none");
  _previewImg.src = "";
  _retakeBtn.classList.add("d-none");
  _analyzeBtn.classList.add("d-none");
  _startBtn.classList.remove("d-none");
  _setStatus("Ready to scan.");
}


/* ── Switch camera (front ↔ rear) ────────────────────────────────────────── */
function switchCamera() {
  _facingMode = (_facingMode === "environment") ? "user" : "environment";
  startCamera();
}


/* ── Submit captured image for AI analysis ───────────────────────────────── */
async function submitCapture() {
  if (!_capturedBlob) {
    _showError("No image captured. Please capture an image first.");
    return;
  }

  _clearError();
  _setStatus("Analyzing package...");
  _analyzeBtn.disabled = true;
  _retakeBtn.disabled  = true;
  showLoading("Analyzing package with AI...");

  // Collect optional form metadata
  const productName = document.getElementById("cam_product_name")?.value || "Camera Capture";
  const brand       = document.getElementById("cam_brand")?.value        || "Unknown";
  const category    = document.getElementById("cam_category")?.value     || "Other";

  try {
    const response = await fetch("/scan/camera", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        image:        _capturedBlob,
        product_name: productName,
        brand:        brand,
        category:     category,
      }),
    });

    const data = await response.json();
    hideLoading();

    if (data.success && data.redirect_url) {
      window.location.href = data.redirect_url;
    } else {
      _analyzeBtn.disabled = false;
      _retakeBtn.disabled  = false;
      _showError(data.error || "Analysis failed. Please try again.");
    }
  } catch (err) {
    hideLoading();
    _analyzeBtn.disabled = false;
    _retakeBtn.disabled  = false;
    _showError("Network error. Please check your connection and try again.");
    console.error("Submit error:", err);
  }
}


/* ── Helpers ─────────────────────────────────────────────────────────────── */
function _stopStream() {
  if (_stream) {
    _stream.getTracks().forEach(t => t.stop());
    _stream = null;
  }
}

function _setStatus(msg) {
  if (_statusEl) _statusEl.textContent = msg;
}

function _showError(msg) {
  if (_errorEl) {
    _errorEl.textContent = msg;
    _errorEl.classList.remove("d-none");
  }
  _setStatus("");
}

function _clearError() {
  if (_errorEl) {
    _errorEl.textContent = "";
    _errorEl.classList.add("d-none");
  }
}

// Cleanup stream when user navigates away
window.addEventListener("beforeunload", _stopStream);
