// Small fetch helper: always returns parsed JSON ({ok:false,...} on failure).
async function api(path, options = {}) {
  try {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      ...options,
    });
    let data = {};
    try { data = await res.json(); } catch (_) { /* non-JSON response */ }
    if (!res.ok && data.ok === undefined) data.ok = false;
    if (res.status === 401 && !path.startsWith("/api/login")) {
      window.location.href = "/sign-in";
    }
    return data;
  } catch (err) {
    console.error("API error:", err);
    return { ok: false, message: "Could not reach the server." };
  }
}

function showMsg(el, text, ok) {
  if (!el) return;
  el.textContent = text || "";
  el.className = "form-msg " + (ok ? "ok" : "err");
}
