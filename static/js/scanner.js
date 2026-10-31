// QR Docs Scanner Controller

document.addEventListener("DOMContentLoaded", () => {
  const qrReaderContainer = document.getElementById("qr-reader");
  const startBtn = document.getElementById("startScanBtn");
  const stopBtn = document.getElementById("stopScanBtn");
  const cameraSelect = document.getElementById("cameraSelect");
  const statusBanner = document.getElementById("scannerStatus");
  const fileInput = document.getElementById("qrFileInput");
  const fileScanBtn = document.getElementById("scanFileBtn");
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute("content");

  if (!qrReaderContainer) return;

  let html5QrCode = null;
  let isProcessingScan = false;

  function showStatus(message, type = "info") {
    if (!statusBanner) return;
    statusBanner.className = `alert alert-${type}`;
    statusBanner.textContent = message;
    statusBanner.style.display = "block";
  }

  function hideStatus() {
    if (statusBanner) statusBanner.style.display = "none";
  }

  try {
    html5QrCode = new Html5Qrcode("qr-reader");
  } catch (e) {
    showStatus("Could not initialize QR scanner: " + e.message, "danger");
    return;
  }

  // Populate camera choices
  if (Html5Qrcode.getCameras) {
    Html5Qrcode.getCameras()
      .then(cameras => {
        if (cameras && cameras.length > 0) {
          cameraSelect.innerHTML = "";
          cameras.forEach((camera, index) => {
            const option = document.createElement("option");
            option.value = camera.id;
            // Prefer rear camera on mobile
            const labelLower = camera.label.toLowerCase();
            if (labelLower.includes("back") || labelLower.includes("rear") || labelLower.includes("environment")) {
              option.selected = true;
            }
            option.text = camera.label || `Camera ${index + 1}`;
            cameraSelect.appendChild(option);
          });
          cameraSelect.style.display = "inline-block";
        }
      })
      .catch(() => {
        // Cameras cannot be enumerated without permission or on HTTP
      });
  }

  // Start scanning
  startBtn?.addEventListener("click", async () => {
    hideStatus();
    isProcessingScan = false;
    showStatus("Accessing camera...", "info");

    const selectedCameraId = cameraSelect?.value;
    const cameraConfig = selectedCameraId
      ? { deviceId: { exact: selectedCameraId } }
      : { facingMode: "environment" };

    try {
      await html5QrCode.start(
        cameraConfig,
        { fps: 10, qrbox: { width: 250, height: 250 } },
        onScanSuccess,
        onScanFailure
      );

      startBtn.style.display = "none";
      stopBtn.style.display = "inline-flex";
      showStatus("Point your camera at a QR code", "info");
    } catch (err) {
      showStatus("Camera error: " + (err.message || err) + ". In production, camera access requires HTTPS.", "danger");
    }
  });

  // Stop scanning
  stopBtn?.addEventListener("click", async () => {
    try {
      await html5QrCode.stop();
      startBtn.style.display = "inline-flex";
      stopBtn.style.display = "none";
      showStatus("Scanning paused.", "info");
    } catch (err) {
      showStatus("Error stopping camera: " + err, "danger");
    }
  });

  // Handle detected QR text
  async function onScanSuccess(decodedText) {
    if (isProcessingScan) return; // Prevent duplicate rapid scans
    isProcessingScan = true;

    showStatus("Verifying scanned QR code...", "info");

    try {
      // Validate with backend security check
      const response = await fetch("/scanner/validate-url", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken || "",
        },
        body: JSON.stringify({ url: decodedText }),
      });

      const data = await response.json();

      if (response.ok && data.valid && data.redirect_url) {
        showStatus("Valid document found! Opening...", "success");
        try { await html5QrCode.stop(); } catch(e) {}
        window.location.href = data.redirect_url;
      } else {
        showStatus(data.error || "Invalid QR code. This is not a recognized document link.", "danger");
        setTimeout(() => { isProcessingScan = false; }, 2500);
      }
    } catch (err) {
      showStatus("Verification failed: " + err.message, "danger");
      setTimeout(() => { isProcessingScan = false; }, 2500);
    }
  }

  function onScanFailure(error) {
    // Continuous background frame scan error, ignorable
  }

  // File upload scanner fallback
  fileScanBtn?.addEventListener("click", () => fileInput.click());

  fileInput?.addEventListener("change", async (e) => {
    if (e.target.files.length === 0) return;
    const file = e.target.files[0];
    showStatus("Analyzing uploaded image...", "info");

    try {
      const decodedText = await html5QrCode.scanFile(file, true);
      onScanSuccess(decodedText);
    } catch (err) {
      showStatus("Could not find a valid QR code in the uploaded image: " + err.message, "danger");
    }
  });
});

