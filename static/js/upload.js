// QR Docs Document Upload JavaScript

document.addEventListener("DOMContentLoaded", () => {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file");
  const filePreview = document.getElementById("filePreview");
  const previewImg = document.getElementById("previewImg");
  const previewIcon = document.getElementById("previewIcon");
  const previewName = document.getElementById("previewName");
  const previewSize = document.getElementById("previewSize");
  const titleInput = document.getElementById("title");
  const uploadForm = document.getElementById("uploadForm");
  const progressBar = document.getElementById("uploadProgressBar");
  const progressContainer = document.getElementById("progressContainer");

  const MAX_SIZE_BYTES = 10 * 1024 * 1024; // 10MB
  const ALLOWED_EXTS = ["pdf", "png", "jpg", "jpeg"];

  if (!dropzone || !fileInput) return;

  // Dropzone click triggers input
  dropzone.addEventListener("click", () => fileInput.click());

  // Drag and drop events
  ["dragenter", "dragover"].forEach(evt => {
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach(evt => {
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone.addEventListener("drop", (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      fileInput.files = files;
      handleFileSelected(files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (fileInput.files.length > 0) {
      handleFileSelected(fileInput.files[0]);
    }
  });

  function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(2) + " MB";
  }

  function handleFileSelected(file) {
    const ext = file.name.split(".").pop().toLowerCase();

    // Validation
    if (!ALLOWED_EXTS.includes(ext)) {
      alert(`Invalid file format '.${ext}'. Only PDF, PNG, and JPG/JPEG files are accepted.`);
      fileInput.value = "";
      filePreview.style.display = "none";
      return;
    }

    if (file.size > MAX_SIZE_BYTES) {
      alert(`File size (${formatFileSize(file.size)}) exceeds the 10 MB limit.`);
      fileInput.value = "";
      filePreview.style.display = "none";
      return;
    }

    // Auto-fill title if empty
    if (titleInput && (!titleInput.value || titleInput.value.trim() === "")) {
      const baseName = file.name.substring(0, file.name.lastIndexOf(".")) || file.name;
      // Convert underscores / hyphens to clean title
      titleInput.value = baseName.replace(/[_-]+/g, " ").trim();
    }

    // Display Preview
    previewName.textContent = file.name;
    previewSize.textContent = formatFileSize(file.size);
    filePreview.style.display = "flex";

    if (["png", "jpg", "jpeg"].includes(ext)) {
      const reader = new FileReader();
      reader.onload = (e) => {
        previewImg.src = e.target.result;
        previewImg.style.display = "block";
        previewIcon.style.display = "none";
      };
      reader.readAsDataURL(file);
    } else {
      previewImg.style.display = "none";
      previewIcon.style.display = "block";
    }
  }

  // Submit Progress Indicator
  if (uploadForm && progressContainer && progressBar) {
    uploadForm.addEventListener("submit", (e) => {
      if (fileInput.files.length === 0) {
        alert("Please select a file to upload.");
        e.preventDefault();
        return;
      }
      progressContainer.style.display = "block";
      let progress = 15;
      progressBar.style.width = progress + "%";
      const interval = setInterval(() => {
        if (progress < 90) {
          progress += Math.floor(Math.random() * 15) + 5;
          if (progress > 90) progress = 90;
          progressBar.style.width = progress + "%";
        } else {
          clearInterval(interval);
        }
      }, 200);
    });
  }
});

