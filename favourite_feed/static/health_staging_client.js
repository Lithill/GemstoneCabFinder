"use strict";
// Loaded ONLY on the double-opt-in private staging page.
// The public prototype has no network calls and remains memory-only.
(() => {
  const dateInput = document.getElementById("staging-day");
  if (!dateInput) return;
  const status = document.getElementById("staging-status");
  dateInput.value = new Date().toLocaleDateString("en-CA");
  let csrf = null;
  let busy = false;
  const show = message => { status.textContent = message; };
  async function sessionToken() {
    if (csrf) return csrf;
    const response = await fetch("/private-health-api/session", {credentials:"same-origin", cache:"no-store"});
    if (!response.ok) throw new Error("Your private session has expired. Please sign in again.");
    csrf = (await response.json()).csrf;
    return csrf;
  }
  async function api(path, method, body) {
    const headers = {};
    if (method !== "GET") {
      headers["Content-Type"] = "application/json";
      headers["X-Health-CSRF"] = await sessionToken();
    }
    const response = await fetch("/private-health-api/" + path, {
      method, headers, credentials:"same-origin", cache:"no-store",
      ...(body === undefined ? {} : {body:JSON.stringify(body)})
    });
    if (response.status === 401 || response.status === 403) {
      csrf = null;
      throw new Error("Session expired or security check failed. Please sign in again.");
    }
    if (!response.ok) throw new Error("The check-in could not be processed (" + response.status + ").");
    return response.json();
  }
  async function run(task) {
    if (busy) return;
    busy = true;
    document.getElementById("staging-save").disabled = true;
    document.getElementById("staging-load").disabled = true;
    try {
      if (!dateInput.value) throw new Error("Choose a date first.");
      await task(dateInput.value);
    } catch (error) {
      show(error.message || "The operation failed.");
    } finally {
      busy = false;
      document.getElementById("staging-save").disabled = false;
      document.getElementById("staging-load").disabled = false;
    }
  }
  document.getElementById("staging-save").addEventListener("click", () => run(async day => {
    // Notes never leave the browser; only canonical diary fields are transmitted.
    const entries = diary.map(({name, answer, extras}) => ({name, answer, extras, notes:""}));
    const result = await api("checkin/" + encodeURIComponent(day), "POST", {entries});
    show("Saved " + result.saved + " entries for " + day + ". Other saved answers for this day are unchanged.");
  }));
  document.getElementById("staging-load").addEventListener("click", () => run(async day => {
    if (diary.length && !confirm("Replace your current unsaved diary with the saved entries for this date?")) return;
    const result = await api("checkin/" + encodeURIComponent(day), "GET");
    diary.splice(0, diary.length, ...result.entries);
    renderDiary();
    show("Loaded " + result.entries.length + " entries for " + day + ".");
  }));
})();
