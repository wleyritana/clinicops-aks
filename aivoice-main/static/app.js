// ============================================================
// Matrix Voice Assistant - app.js
// ============================================================

(() => {
  console.log("[MatrixVA] app.js loaded");

  // ---------- Device type ----------
  const IS_MOBILE =
    /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
      navigator.userAgent
    );

  // ---------- Global TTS audio element ----------
  const ttsAudio = new Audio();
  let audioUnlocked = false;

  const SILENT_WAV =
    "data:audio/wav;base64,UklGRiYAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQIAAAAAAA==";

  async function unlockAudio() {
    if (audioUnlocked) return;

    try {
      if (!ttsAudio.src) ttsAudio.src = SILENT_WAV;

      ttsAudio.muted = true;

      const playPromise = ttsAudio.play();
      if (playPromise && playPromise.then) await playPromise;

      ttsAudio.pause();
      ttsAudio.currentTime = 0;
      ttsAudio.muted = false;

      audioUnlocked = true;
      console.log("[TTS] Audio unlocked for mobile");
    } catch (err) {
      console.warn("[TTS] Unlock failed:", err);
    }
  }

  // -------------------- DEVICE ID --------------------
  function getOrCreateDeviceId() {
    const key = "matrix_device_id";
    try {
      let id = localStorage.getItem(key);
      if (!id) {
        id =
          "device-" +
          (crypto.randomUUID
            ? crypto.randomUUID()
            : Math.random().toString(36).slice(2));
        localStorage.setItem(key, id);
      }
      return id;
    } catch (e) {
      return "device-anon-" + Math.random().toString(36).slice(2);
    }
  }
  const DEVICE_ID = getOrCreateDeviceId();
  const SESSION_ID =
    "sess-" +
    (crypto.randomUUID
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2));

  const deviceEl = document.getElementById("deviceIdLabel");
  const sessionEl = document.getElementById("sessionIdLabel");
  if (deviceEl) deviceEl.textContent = DEVICE_ID;
  if (sessionEl) sessionEl.textContent = SESSION_ID;

  const micButton = document.getElementById("micButton");
  const micLabel = document.getElementById("micLabel");
  const statusDot = document.getElementById("statusDot");
  const statusText = document.getElementById("statusText");
  const chat = document.getElementById("chat");
  const flowWarningEl = document.getElementById("flowWarning");

  if (!micButton || !micLabel || !statusDot || !statusText || !chat) {
    console.error("[MatrixVA] Missing DOM elements");
    return;
  }

  let mediaRecorder = null;
  let activeStream = null;
  let chunks = [];
  let inOrderFlow = false;

  // ---------- UI ----------
  function setStatus(text, dotClass) {
    statusText.textContent = text;
    statusDot.className = "va-dot " + dotClass;
  }

  function appendChat(role, text) {
    if (!text) return;
    const div = document.createElement("div");
    div.className = "va-msg va-" + role;
    div.textContent = text;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
  }

  function clearChat() {
    chat.innerHTML = "";
  }

  function showToast(message) {
    const toast = document.createElement("div");
    toast.className = "va-toast";
    toast.textContent = message;
    document.body.appendChild(toast);

    requestAnimationFrame(() => {
      toast.classList.add("show");
    });

    setTimeout(() => toast.classList.remove("show"), 2500);
    setTimeout(() => toast.remove(), 3000);
  }

  // ---------- MOBILE: Tap-to-play reply ----------
  function showPlayReplyButton(src, mime) {
    const oldBtn = document.getElementById("playReplyBtn");
    if (oldBtn) oldBtn.remove();

    const oldAudio = document.getElementById("replyAudioPlayer");
    if (oldAudio) oldAudio.remove();

    const audioEl = document.createElement("audio");
    audioEl.id = "replyAudioPlayer";
    audioEl.controls = true;
    audioEl.src = src;

    audioEl.addEventListener("error", () => {
      console.error("[TTS] mobile audio error:", audioEl.error);
    });

    const btn = document.createElement("button");
    btn.id = "playReplyBtn";
    btn.textContent = "Tap to hear reply";
    btn.className = "va-play-reply-btn";

    btn.addEventListener("click", () => {
      audioEl
        .play()
        .then(() => {
          console.log("[TTS] Played via tap");
          btn.remove();
        })
        .catch((err) => console.error("[TTS] Mobile play failed:", err));
    });

    chat.appendChild(audioEl);
    chat.appendChild(btn);
    chat.scrollTop = chat.scrollHeight;
  }

  // ---------- FLOW GUARD ----------
  function updateFlowGuard(debug, replyText) {
    const flow = debug && debug.flow;
    const step = debug && debug.step;

    const nowInFlow = flow === "food_order" && step != null;
    const wasInFlow = inOrderFlow;
    inOrderFlow = nowInFlow;

    if (flowWarningEl) {
      if (inOrderFlow) {
        flowWarningEl.style.display = "block";
        window.onbeforeunload = () => "Your food order is in progress.";
      } else {
        flowWarningEl.style.display = "none";
        window.onbeforeunload = null;
      }
    }

    if (wasInFlow && !inOrderFlow && replyText) {
      const msg = replyText.toLowerCase();
      if (msg.includes("order has been placed")) {
        clearChat();
        showToast("Order complete. Starting fresh.");
      } else if (msg.includes("canceled") || msg.includes("cancelled")) {
        clearChat();
        showToast("Order cancelled. Starting fresh.");
      }
    }
  }

  // ============================================================
  // RECORDING (patched for mobile)
  // ============================================================

  async function startRecording() {
    chunks = [];

    try {
      activeStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(activeStream);

      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunks.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        console.log("[DEBUG] MediaRecorder stopped. chunks:", chunks.length);

        // Always kill mic stream
        if (activeStream) {
          activeStream.getTracks().forEach((t) => t.stop());
          activeStream = null;
        }

        micButton.classList.remove("recording");
        micLabel.textContent = "Open Voice Link";

        if (chunks.length === 0) {
          console.warn("[WARN] Empty recording — mobile interrupted");
          setStatus("Ready", "va-dot-idle");
          return;
        }

        setStatus("Uploading...", "va-dot-busy");

        const blob = new Blob(chunks, { type: "audio/webm" });
        const formData = new FormData();
        formData.append("audio", blob, "recording.webm");
        formData.append("device_id", DEVICE_ID);
        formData.append("session_id", SESSION_ID);

        try {
          const res = await fetch("/api/voice", {
            method: "POST",
            body: formData,
          });

          console.log("[DEBUG] Server status:", res.status);

          // Non-2xx status from server
          if (!res.ok) {
            const errorText = await res.text();
            console.error("[SERVER ERROR]", res.status, errorText);
            setStatus("Server error", "va-dot-error");
            return;
          }

          // Clone so we can inspect text if JSON parsing fails
          const resClone = res.clone();
          let data;

          try {
            data = await res.json();
          } catch (jsonErr) {
            const rawText = await resClone.text();
            console.error(
              "[PARSE ERROR] Could not parse JSON:",
              jsonErr,
              "Raw response:",
              rawText
            );
            setStatus("Bad response", "va-dot-error");
            return;
          }

          console.log("[MatrixVA] /api/voice:", data);

          appendChat("user", data.user_text);
          appendChat("bot", data.reply_text);
          updateFlowGuard(data.debug, data.reply_text);

          // TTS playback
          if (data.audio_base64 && data.audio_mime) {
            const src = `data:${data.audio_mime};base64,${data.audio_base64}`;
            console.log("[TTS] MIME:", data.audio_mime);

            ttsAudio.src = src;
            ttsAudio.load();

            if (!IS_MOBILE) {
              ttsAudio
                .play()
                .then(() => console.log("[TTS] Played (desktop)"))
                .catch((err) =>
                  console.error("[TTS] Desktop autoplay failed:", err)
                );
            } else {
              showPlayReplyButton(src, data.audio_mime);
            }
          } else {
            console.warn("[TTS] No audio returned.");
          }

          setStatus("Ready", "va-dot-idle");
        } catch (err) {
          // Real network-level error (request failed, offline, etc.)
          console.error("[NETWORK ERROR] fetch failed:", err);
          setStatus("Network error", "va-dot-error");
        }
      };

      mediaRecorder.start();

      micButton.classList.add("recording");
      micLabel.textContent = "Stop";
      setStatus("Recording...", "va-dot-live");
    } catch (err) {
      console.error("Mic error:", err);
      setStatus("Mic blocked", "va-dot-error");
      micButton.classList.remove("recording");
      micLabel.textContent = "Open Voice Link";
    }
  }

  function stopRecording() {
    try {
      if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
      }
    } catch (e) {
      console.error("Stop error:", e);
    }
  }

  // ---------- Mic button ----------
  micButton.addEventListener("click", () => {
    unlockAudio();

    if (!mediaRecorder || mediaRecorder.state === "inactive") {
      startRecording();
    } else {
      stopRecording();
    }
  });

  setStatus("Ready", "va-dot-idle");
})();
