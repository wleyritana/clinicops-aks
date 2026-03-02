// ============================================================
// Matrix Voice Assistant - embed.js
// - Embeds the assistant iframe into any host page
// - Grants microphone + autoplay permissions
// ============================================================

(() => {
  // Change this to your deployed assistant URL if needed
  const assistantURL = "https://YOUR-RAILWAY-APP-URL/"; // make sure it ends with /

  function injectAssistant() {
    // Avoid injecting multiple times
    if (document.getElementById("matrix-frame")) return;

    const iframe = document.createElement("iframe");
    iframe.id = "matrix-frame";
    iframe.src = assistantURL;

    // Important: allow microphone + autoplay inside iframe
    iframe.allow = "microphone *; autoplay *";

    iframe.style.border = "1px solid #00ff88";
    iframe.style.width = "100%";
    iframe.style.height = "100%";
    iframe.style.borderRadius = "8px";

    document.body.appendChild(iframe);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", injectAssistant);
  } else {
    injectAssistant();
  }
})();
