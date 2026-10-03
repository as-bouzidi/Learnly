(() => {
  const $ = (id) => document.getElementById(id);
  const MAX_SCORE = 20;

  const form = $("noteForm"), sendBtn = $("sendBtn");
  const studentSelect = $("studentSelect"), section = $("section");
  const absences = $("absences"), homework = $("homework"), examScore = $("examScore");
  const content = $("content"), count = $("count");
  const list = $("notesList"), reportCount = $("reportCount"), search = $("search");
  const scoreFill = $("scoreFill"), toastEl = $("toast");

  let reports = [];

  /* ---------------------------------------------------------- helpers */
  async function api(path, options = {}) {
    try {
      const res = await fetch(path, {
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        ...options,
      });
      if (res.status === 401) { window.location.href = "/sign-in"; return { ok: false }; }
      let data = {};
      try { data = await res.json(); } catch (_) {}
      if (data.ok === undefined) data.ok = res.ok;
      return data;
    } catch (_) {
      return { ok: false, message: "Could not reach the server." };
    }
  }

  let toastTimer;
  function toast(text, type = "success") {
    toastEl.textContent = text;
    toastEl.className = "toast show " + type;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (toastEl.className = "toast"), 3000);
  }

  const scoreClass = (v) => (v === null || v === undefined ? "" : v >= MAX_SCORE * 0.7 ? "good" : v >= MAX_SCORE * 0.5 ? "mid" : "bad");
  const fmt = (n) => String(Number(n));
  function localDate(s) {                       // server stores UTC
    const d = new Date(String(s).replace(" ", "T") + "Z");
    return isNaN(d) ? String(s).slice(0, 16) : d.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
  }
  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  /* ------------------------------------------------------------ steppers */
  document.querySelectorAll(".stepper button").forEach((btn) => {
    btn.addEventListener("click", () => {
      const input = $(btn.dataset.target);
      const next = (parseInt(input.value, 10) || 0) + Number(btn.dataset.step);
      input.value = Math.min(Math.max(next, 0), 365);
    });
  });

  /* ------------------------------------------------------------ exam meter */
  examScore.addEventListener("input", () => {
    const v = parseFloat(examScore.value.replace(",", "."));
    if (isNaN(v)) { scoreFill.style.width = "0"; return; }
    const pct = Math.min(Math.max(v / MAX_SCORE, 0), 1) * 100;
    scoreFill.style.width = pct + "%";
    scoreFill.style.background = pct >= 70 ? "var(--green)" : pct >= 50 ? "var(--amber)" : "var(--red)";
  });

  /* ------------------------------------------------- quick notes + counter */
  const updateCount = () => (count.textContent = content.value.length);
  content.addEventListener("input", updateCount);
  document.querySelectorAll(".quick button").forEach((b) => {
    b.addEventListener("click", () => {
      const sep = content.value && !content.value.endsWith(" ") ? " " : "";
      const next = content.value + sep + b.dataset.text;
      if (next.length <= content.maxLength) content.value = next;
      updateCount();
      content.focus();
    });
  });

  /* --------------------------------------------------------------- students */
  async function loadStudents() {
    const data = await api("/api/students");
    studentSelect.replaceChildren();
    const students = data.students || [];
    const first = new Option(students.length ? "Select a student" : "No students registered yet", "", true, true);
    first.disabled = true;
    studentSelect.add(first);
    students.forEach((s) => {
      const o = new Option(`${s.firstname} ${s.lastname}${s.section ? " · " + s.section : ""}`, s.id);
      o.dataset.section = s.section || "";
      studentSelect.add(o);
    });
  }
  studentSelect.addEventListener("change", () => {
    const sec = studentSelect.selectedOptions[0].dataset.section;
    if (sec && !section.value.trim()) section.value = sec;
    clearError(studentSelect);
  });

  /* ------------------------------------------------------------- validation */
  function setError(input, msg) {
    const field = input.closest(".field");
    field.classList.add("invalid");
    let e = field.querySelector(".field-error");
    if (!e) { e = el("div", "field-error"); field.append(e); }
    e.textContent = msg;
  }
  function clearError(input) {
    const field = input.closest(".field");
    field.classList.remove("invalid");
    const e = field.querySelector(".field-error");
    if (e) e.remove();
  }
  [section, examScore, content].forEach((i) => i.addEventListener("input", () => clearError(i)));

  function validate() {
    let ok = true;
    if (!studentSelect.value) { setError(studentSelect, "Choose a student."); ok = false; }
    if (!section.value.trim()) { setError(section, "Write the section."); ok = false; }
    const sc = examScore.value.trim();
    if (sc !== "") {
      const v = parseFloat(sc.replace(",", "."));
      if (isNaN(v) || v < 0 || v > MAX_SCORE) { setError(examScore, `Score must be between 0 and ${MAX_SCORE}.`); ok = false; }
    }
    if (ok && !content.value.trim() && !(parseInt(absences.value, 10) > 0) &&
        !(parseInt(homework.value, 10) > 0) && sc === "") {
      setError(content, "Add a note, an absence, homework or an exam score.");
      ok = false;
    }
    return ok;
  }

  /* --------------------------------------------------------------- reports */
  function reportCard(r) {
    const card = el("div", "report");
    card.append(el("div", "avatar", (r.student[0] || "?").toUpperCase()));

    const body = el("div", "report-body");
    const top = el("div", "report-top");
    top.append(el("b", "", r.student), el("span", "tag", r.section), el("span", "date", localDate(r.created_at)));
    body.append(top);

    const chips = el("div", "chips");
    if (r.absences) chips.append(el("span", "chip red", `${r.absences} absence${r.absences === 1 ? "" : "s"}`));
    if (r.homework) chips.append(el("span", "chip amber", `${r.homework} unfinished homework`));
    if (r.exam_score !== null && r.exam_score !== undefined)
      chips.append(el("span", "chip " + scoreClass(r.exam_score), `Exam ${fmt(r.exam_score)} / ${MAX_SCORE}`));
    if (chips.children.length) body.append(chips);

    if (r.content) body.append(el("p", "report-text", r.content));
    card.append(body);

    const del = el("button", "del", "🗑");
    del.type = "button";
    del.title = "Delete this report";
    del.setAttribute("aria-label", "Delete this report");
    del.addEventListener("click", () => removeReport(r, del));
    card.append(del);
    return card;
  }

  function renderReports() {
    const q = search.value.trim().toLowerCase();
    const shown = reports.filter((r) =>
      !q || [r.student, r.section, r.content].some((t) => (t || "").toLowerCase().includes(q)));
    reportCount.textContent = reports.length;
    list.replaceChildren();
    if (!shown.length) {
      list.append(el("div", "empty", reports.length ? "No report matches your search." : "You haven't sent any report yet."));
      return;
    }
    shown.forEach((r) => list.append(reportCard(r)));
  }
  search.addEventListener("input", renderReports);

  async function loadReports() {
    list.replaceChildren(el("div", "empty", "Loading…"));
    const data = await api("/api/reports");
    if (!data.ok) { list.replaceChildren(el("div", "empty", data.message || "Could not load reports.")); return; }
    reports = data.reports;
    renderReports();
  }

  async function removeReport(r, btn) {
    if (!confirm(`Delete the report for ${r.student}?`)) return;
    btn.disabled = true;
    const data = await api("/api/reports/" + r.id, { method: "DELETE" });
    if (data.ok) {
      reports = reports.filter((x) => x.id !== r.id);
      renderReports();
      toast("Report deleted.");
    } else {
      btn.disabled = false;
      toast(data.message || "Could not delete.", "error");
    }
  }

  /* ----------------------------------------------------------------- submit */
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!validate()) return;

    sendBtn.disabled = true;
    const label = sendBtn.textContent;
    sendBtn.textContent = "Sending…";

    const data = await api("/api/reports", {
      method: "POST",
      body: JSON.stringify({
        student_id: Number(studentSelect.value),
        section: section.value.trim(),
        absences: parseInt(absences.value, 10) || 0,
        homework: parseInt(homework.value, 10) || 0,
        exam_score: examScore.value.trim(),
        content: content.value.trim(),
      }),
    });

    sendBtn.disabled = false;
    sendBtn.textContent = label;

    if (data.ok) {
      reports.unshift(data.report);
      renderReports();
      form.reset();
      studentSelect.selectedIndex = 0;
      scoreFill.style.width = "0";
      updateCount();
      loadStudents();                       // refresh the section shown next to each student
      toast("Report sent to the parent and the student.");
    } else {
      toast(data.message || "Could not send the report.", "error");
    }
  });

  loadStudents();
  loadReports();
})();
