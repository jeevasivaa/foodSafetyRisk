/**
 * main.js — FoodQuality AI Frontend Utilities
 * Handles: image preview, password toggle, sidebar,
 *          loading spinner, toast auto-dismiss, form validation
 */

// ── Auto-initialize all Bootstrap Toasts ────────────────────────────────────
document.addEventListener("DOMContentLoaded", function () {
  const toastEls = document.querySelectorAll(".toast");
  toastEls.forEach(function (toastEl) {
    const bsToast = new bootstrap.Toast(toastEl, { delay: 4500 });
    bsToast.show();
  });

  // Add sidebar overlay element
  if (!document.getElementById("sidebarOverlay")) {
    const overlay = document.createElement("div");
    overlay.className = "sidebar-overlay";
    overlay.id = "sidebarOverlay";
    overlay.onclick = closeSidebar;
    document.body.appendChild(overlay);
  }
});


// ── Sidebar Toggle ────────────────────────────────────────────────────────────
/**
 * On desktop (>992px): toggles .sidebar-collapsed on sidebar + .sidebar-collapsed
 *   on mainWrapper so the layout shifts accordingly.
 * On mobile (<=992px): slides the sidebar in/out with .sidebar-open + overlay.
 */
function toggleSidebar() {
  const sidebar = document.getElementById("sidebar");
  const wrapper = document.getElementById("mainWrapper");
  const overlay = document.getElementById("sidebarOverlay");

  if (!sidebar) return;

  if (window.innerWidth > 992) {
    // Desktop: collapse/expand
    sidebar.classList.toggle("sidebar-collapsed");
    if (wrapper) wrapper.classList.toggle("sidebar-collapsed");
  } else {
    // Mobile: slide in/out with overlay
    sidebar.classList.toggle("sidebar-open");
    if (overlay) overlay.classList.toggle("show");
  }
}

function closeSidebar() {
  const sidebar = document.getElementById("sidebar");
  const wrapper = document.getElementById("mainWrapper");
  const overlay = document.getElementById("sidebarOverlay");
  if (sidebar) {
    sidebar.classList.remove("sidebar-open");
    // Do NOT remove sidebar-collapsed on mobile close — that's desktop state
  }
  if (overlay) overlay.classList.remove("show");
}

// Re-evaluate sidebar state on window resize to prevent stuck states
window.addEventListener("resize", function () {
  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("sidebarOverlay");
  if (!sidebar) return;
  if (window.innerWidth > 992) {
    // Switch to desktop mode — remove mobile-only classes
    sidebar.classList.remove("sidebar-open");
    if (overlay) overlay.classList.remove("show");
  } else {
    // Switch to mobile mode — remove desktop-only classes
    // (keep sidebar-collapsed state if user explicitly set it)
  }
});


// ── Image Preview ─────────────────────────────────────────────────────────────
/**
 * Preview a selected image file.
 * @param {HTMLInputElement} input     - The file input element
 * @param {string|null}      dropzoneId - ID of the dropzone inner div to update text
 * @param {string}           previewId  - ID of the <img> preview element
 */
function previewImage(input, dropzoneId, previewId) {
  if (!input.files || !input.files[0]) return;

  const file    = input.files[0];
  const allowed = ["image/jpeg", "image/jpg", "image/png"];

  if (!allowed.includes(file.type)) {
    showToast("Only JPG, JPEG, and PNG images are allowed.", "danger");
    input.value = "";
    return;
  }

  const reader = new FileReader();
  reader.onload = function (e) {
    // Update dropzone inner text
    if (dropzoneId) {
      const dzInner = document.getElementById(dropzoneId);
      if (dzInner) {
        dzInner.innerHTML = `
          <i class="bi bi-check-circle-fill text-success fs-3 mb-2"></i>
          <p class="fw-semibold mb-0 text-success">${file.name}</p>
          <small class="text-muted">${(file.size / 1024).toFixed(1)} KB — click to change</small>
        `;
      }
    }

    // Show preview image
    const preview = document.getElementById(previewId);
    if (preview) {
      preview.src = e.target.result;
      preview.classList.remove("d-none");
    }
  };
  reader.readAsDataURL(file);
}


// ── Password Visibility Toggle ────────────────────────────────────────────────
/**
 * Toggle password field between text and password type.
 * @param {string} fieldId  - ID of the password input
 * @param {Element} btn     - The toggle button element
 */
function togglePassword(fieldId, btn) {
  const field = document.getElementById(fieldId);
  if (!field) return;

  if (field.type === "password") {
    field.type = "text";
    btn.querySelector("i").className = "bi bi-eye-slash";
  } else {
    field.type = "password";
    btn.querySelector("i").className = "bi bi-eye";
  }
}


// ── AI Analysis Progress Loader ────────────────────────────────────────────────

/**
 * Pipeline stages: each entry is
 *   [targetPercent, durationMs, stepLabel]
 *
 * Timings are weighted to match the real AI pipeline durations.
 * The bar intentionally slows near 95% and never reaches 100%
 * (the page redirect completes it naturally).
 */
const _LOADING_STAGES = [
  [  8,  400, "Uploading image to server..."       ],
  [ 15,  700, "Preprocessing & enhancing image..."  ],
  [ 25, 1000, "Detecting barcode & QR codes..."     ],
  [ 60, 9000, "Running OCR text extraction..."      ],  // EasyOCR is slowest
  [ 80, 4000, "Analyzing package for damage..."     ],
  [ 90, 1500, "Calculating quality score..."         ],
  [ 95, 1000, "Generating recommendations..."       ],
  [ 99, 5000, "Finalizing results..."               ],  // holds here until redirect
];

let _loadingTimer    = null;   // setInterval handle
let _loadingStageIdx = 0;
let _loadingPct      = 0;      // current displayed percentage

// Circumference of circle with r=50
const _RING_CIRC = 2 * Math.PI * 50;  // ≈ 314.16

/**
 * Show the loading overlay and start the progress animation.
 * @param {string} message - Optional headline override
 */
function showLoading(message) {
  const overlay = document.getElementById("loadingOverlay");
  if (!overlay) return;
  overlay.style.display = "flex";

  // Update headline
  if (message) {
    const msgEl = document.getElementById("loadingMsg");
    if (msgEl) msgEl.textContent = message;
  }

  // Reset state
  _loadingPct      = 0;
  _loadingStageIdx = 0;
  _setLoadingProgress(0, "Initializing...");

  // Clear any previous timer
  if (_loadingTimer) clearInterval(_loadingTimer);

  // Kick off the first stage immediately
  _advanceLoadingStage();
}

/** Advance through the pipeline stages one tick at a time. */
function _advanceLoadingStage() {
  if (_loadingStageIdx >= _LOADING_STAGES.length) return;

  const [targetPct, durationMs, label] = _LOADING_STAGES[_loadingStageIdx];
  const startPct  = _loadingPct;
  const range     = targetPct - startPct;
  const tickMs    = 80;                       // update every 80 ms
  const ticks     = Math.max(1, Math.round(durationMs / tickMs));
  let   tick      = 0;

  // Update step label immediately when entering stage
  const stepEl = document.getElementById("loadingStep");
  if (stepEl) stepEl.textContent = label;

  if (_loadingTimer) clearInterval(_loadingTimer);

  _loadingTimer = setInterval(() => {
    tick++;
    // Ease-out curve: fast at start, slows toward end of stage
    const progress = 1 - Math.pow(1 - tick / ticks, 2);
    const newPct   = Math.round(startPct + range * progress);
    _loadingPct    = newPct;
    _setLoadingProgress(newPct, label);

    if (tick >= ticks) {
      clearInterval(_loadingTimer);
      _loadingStageIdx++;
      // Short gap before next stage
      setTimeout(_advanceLoadingStage, 120);
    }
  }, tickMs);
}

/** Update the ring, bar, and percentage label. */
function _setLoadingProgress(pct, _label) {
  pct = Math.min(99, Math.max(0, pct));

  // Ring (stroke-dashoffset: 0 = full, 314.16 = empty)
  const ringFill = document.getElementById("loadingRingFill");
  if (ringFill) {
    ringFill.style.strokeDashoffset = _RING_CIRC * (1 - pct / 100);
  }

  // Percentage text inside ring
  const pctEl = document.getElementById("loadingPct");
  if (pctEl) pctEl.textContent = pct + "%";

  // Linear bar + bar label
  const barFill  = document.getElementById("loadingBarFill");
  const barLabel = document.getElementById("loadingBarPct");
  if (barFill)  barFill.style.width  = pct + "%";
  if (barLabel) barLabel.textContent = pct + "%";
}

/** Hide the loading overlay and reset all progress elements. */
function hideLoading() {
  if (_loadingTimer) { clearInterval(_loadingTimer); _loadingTimer = null; }
  const overlay = document.getElementById("loadingOverlay");
  if (overlay) overlay.style.display = "none";
  // Reset for next use
  _loadingPct      = 0;
  _loadingStageIdx = 0;
  _setLoadingProgress(0, "");
  const stepEl = document.getElementById("loadingStep");
  if (stepEl) stepEl.textContent = "Please wait";
  const msgEl = document.getElementById("loadingMsg");
  if (msgEl) msgEl.textContent = "Initializing analysis...";
}


// ── Programmatic Toast ─────────────────────────────────────────────────────────
/**
 * Show a Bootstrap toast notification programmatically.
 * @param {string} message  - Toast message text
 * @param {string} type     - Bootstrap color variant: success | danger | warning | info
 */
function showToast(message, type = "info") {
  const iconMap = {
    success: "check-circle",
    danger:  "x-circle",
    warning: "exclamation-triangle",
    info:    "info-circle",
  };

  const container = document.querySelector(".toast-container") || createToastContainer();

  const toastEl = document.createElement("div");
  toastEl.className = `toast align-items-center text-bg-${type} border-0`;
  toastEl.setAttribute("role", "alert");
  toastEl.setAttribute("aria-live", "assertive");
  toastEl.setAttribute("aria-atomic", "true");

  toastEl.innerHTML = `
    <div class="d-flex">
      <div class="toast-body fw-semibold">
        <i class="bi bi-${iconMap[type] || "info-circle"} me-2"></i>${message}
      </div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto"
              data-bs-dismiss="toast"></button>
    </div>
  `;

  container.appendChild(toastEl);
  const bsToast = new bootstrap.Toast(toastEl, { delay: 4000 });
  bsToast.show();

  toastEl.addEventListener("hidden.bs.toast", () => toastEl.remove());
}

function createToastContainer() {
  const container = document.createElement("div");
  container.className = "toast-container position-fixed top-0 end-0 p-3";
  container.style.zIndex = "9999";
  document.body.appendChild(container);
  return container;
}


// ── Form Validation Helpers ────────────────────────────────────────────────────
/**
 * Basic client-side form validator.
 * Adds Bootstrap was-validated class for visual feedback.
 */
document.addEventListener("DOMContentLoaded", function () {
  const forms = document.querySelectorAll("form[novalidate]");
  forms.forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
      }
      form.classList.add("was-validated");
    });
  });
});


// ── Confirm Delete Shortcut ────────────────────────────────────────────────────
function confirmDelete(message) {
  return confirm(message || "Are you sure you want to delete this item?");
}
