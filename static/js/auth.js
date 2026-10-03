const $ = (id) => document.getElementById(id);

function showRegister() {
  $("login").classList.add("hidden-left");
  $("register").classList.add("visible");
}
function showLogin() {
  $("login").classList.remove("hidden-left");
  $("register").classList.remove("visible");
}

$("showRegister").addEventListener("click", (e) => { e.preventDefault(); showRegister(); });
$("showLogin").addEventListener("click", (e) => { e.preventDefault(); showLogin(); });

$("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = await api("/api/login", {
    method: "POST",
    body: JSON.stringify({
      email: $("login-email").value.trim(),
      password: $("login-password").value,
    }),
  });
  if (data.ok) {
    window.location.href = data.redirect || "/dashboard";
  } else {
    showMsg($("loginMsg"), data.message || "Login failed.", false);
  }
});

$("registerForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = await api("/api/register", {
    method: "POST",
    body: JSON.stringify({
      firstname: $("firstName").value.trim(),
      lastname: $("lastName").value.trim(),
      email: $("register-email").value.trim(),
      password: $("register-password").value,
      role: $("role").value,
    }),
  });
  if (data.ok) {
    $("registerForm").reset();
    showLogin();
    showMsg($("loginMsg"), data.message, true);
  } else {
    showMsg($("registerMsg"), data.message || "Registration failed.", false);
  }
});

/* ---- extras from the original login folder ---- */
// open the Sign Up card directly from the navbar (/sign-in#signup)
if (location.hash === "#signup") showRegister();

// Remember me: keep the email in this browser only (never the password)
try {
  const saved = localStorage.getItem("learnly_email");
  if (saved) { $("login-email").value = saved; $("login-check").checked = true; }
} catch (_) {}
$("loginForm").addEventListener("submit", () => {
  try {
    if ($("login-check").checked) localStorage.setItem("learnly_email", $("login-email").value.trim());
    else localStorage.removeItem("learnly_email");
  } catch (_) {}
});

$("forgotLink").addEventListener("click", (e) => {
  e.preventDefault();
  showMsg($("loginMsg"), "Password reset is not available yet. Ask your teacher or administrator.", false);
});
$("termsLink").addEventListener("click", (e) => {
  e.preventDefault();
  alert("Learnly stores your name, email and the notes teachers send. Your data is only visible to the people linked to you.");
});
