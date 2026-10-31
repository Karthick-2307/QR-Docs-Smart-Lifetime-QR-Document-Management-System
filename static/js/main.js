// QR Docs Main JavaScript

document.addEventListener("DOMContentLoaded", () => {
  // Theme Management
  const themeToggleButtons = document.querySelectorAll(".theme-toggle");
  const storedTheme = localStorage.getItem("qrdocs_theme") || "light";
  document.documentElement.setAttribute("data-theme", storedTheme);

  themeToggleButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      const current = document.documentElement.getAttribute("data-theme") || "light";
      const next = current === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("qrdocs_theme", next);
    });
  });

  // Mobile Sidebar Drawer
  const menuToggle = document.querySelector(".menu-toggle");
  const sidebar = document.querySelector(".sidebar");
  if (menuToggle && sidebar) {
    menuToggle.addEventListener("click", () => {
      sidebar.classList.toggle("open");
    });

    document.addEventListener("click", (e) => {
      if (sidebar.classList.contains("open") && !sidebar.contains(e.target) && !menuToggle.contains(e.target)) {
        sidebar.classList.remove("open");
      }
    });
  }

  // Dismiss Flash Alerts
  document.querySelectorAll(".alert-close").forEach(closeBtn => {
    closeBtn.addEventListener("click", (e) => {
      const alert = e.target.closest(".alert");
      if (alert) {
        alert.style.opacity = "0";
        setTimeout(() => alert.remove(), 200);
      }
    });
  });

  // Copy to Clipboard
  document.querySelectorAll("[data-copy]").forEach(copyBtn => {
    copyBtn.addEventListener("click", async () => {
      const textToCopy = copyBtn.getAttribute("data-copy");
      if (!textToCopy) return;

      try {
        await navigator.clipboard.writeText(textToCopy);
        const originalText = copyBtn.innerHTML;
        copyBtn.innerHTML = `<span>Copied!</span>`;
        copyBtn.classList.add("btn-success");
        setTimeout(() => {
          copyBtn.innerHTML = originalText;
          copyBtn.classList.remove("btn-success");
        }, 2000);
      } catch (err) {
        prompt("Copy URL manually:", textToCopy);
      }
    });
  });

  // Modal Handling
  document.querySelectorAll("[data-modal-target]").forEach(trigger => {
    trigger.addEventListener("click", (e) => {
      e.preventDefault();
      const targetId = trigger.getAttribute("data-modal-target");
      const modal = document.getElementById(targetId);
      if (modal) {
        modal.classList.add("active");
      }
    });
  });

  document.querySelectorAll(".modal-close, [data-modal-close]").forEach(closeBtn => {
    closeBtn.addEventListener("click", (e) => {
      const backdrop = e.target.closest(".modal-backdrop");
      if (backdrop) {
        backdrop.classList.remove("active");
      }
    });
  });

  // Close modal when clicking on backdrop
  document.querySelectorAll(".modal-backdrop").forEach(backdrop => {
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) {
        backdrop.classList.remove("active");
      }
    });
  });
});

