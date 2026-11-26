"use strict";
// This client is loaded ONLY in the double-opt-in private staging tracker.
(() => {
  const dateInput = document.getElementById("staging-day");
  if (!dateInput) return;
  const status = document.getElementById("staging-status");
  const indicator = document.getElementById("staging-save-state");
  const saveButton = document.getElementById("staging-save");
  const loadButton = document.getElementById("staging-load");
  const modeButtons = [document.getElementById("guided-start"), document.getElementById("quick-start")];
  const modeSections = [document.getElementById("guided"), document.getElementById("quick")];
  function lockEditing(locked) {
    modeButtons.forEach(button => { button.disabled = locked; });
    modeSections.forEach(section => { section.inert = locked || busy; if (locked && !busy) section.hidden = true; });
    document.getElementById("diary-items").inert = locked || busy;
    document.getElementById("clear-diary").disabled = locked;
    saveButton.disabled = locked || busy;
  }
  const today = new Date();
  dateInput.value = [today.getFullYear(), String(today.getMonth()+1).padStart(2,"0"), String(today.getDate()).padStart(2,"0")].join("-");
  let csrf = null;
  let busy = false;
  let dirty = false;
  let loadedDay = null;
  let savedSnapshot = null;
  let suppressChanges = false;
  let backupFailed = false;
  const show = message => {
    status.textContent = message + (backupFailed ? " Warning: your diary is saved, but the encrypted backup failed. Save again to retry." : "");
  };
  const updateBackup = result => {
    if (typeof result.backup_ok === "boolean") backupFailed = !result.backup_ok;
  };
  const entriesForSave = () => diary.map(({name, answer, extras}) => ({name, answer, extras, notes:""}));
  const snapshot = () => JSON.stringify(entriesForSave().slice().sort((a,b) => a.name.localeCompare(b.name)));
  const setDirty = value => {
    dirty = value;
    indicator.textContent = dirty ? "Unsaved changes" : (loadedDay === dateInput.value ? "All changes saved or loaded" : "Date not loaded");
    indicator.dataset.state = dirty ? "unsaved" : "saved";
  };
  const refreshDirty = () => {
    if (!suppressChanges) setDirty(savedSnapshot === null ? diary.length > 0 : snapshot() !== savedSnapshot);
  };
  document.addEventListener("tracker:diary-changed", refreshDirty);
  dateInput.addEventListener("change", () => {
    if (busy) return;
    if (dirty && loadedDay !== dateInput.value && !confirm("Discard unsaved changes and switch dates?")) {
      dateInput.value = loadedDay;
      return;
    }
    if (loadedDay !== dateInput.value) {
      lockEditing(true);
      show("Loading selected day…");
      loadDay(true);
    } else {
      lockEditing(false);
      setDirty(dirty);
    }
  });
  async function sessionToken() {
    if (csrf) return csrf;
    const response = await fetch("/private-health-api/session", {credentials:"same-origin", cache:"no-store"});
    if (!response.ok) throw new Error("Your private session has expired. Keep this tab open and sign in again in a separate tab, then retry.");
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
      throw new Error("Session expired or security check failed. Keep this tab open, sign in again in a separate tab, then retry. Your entries remain here.");
    }
    if (!response.ok) throw new Error("The check-in could not be processed (" + response.status + ").");
    return response.json();
  }
  async function run(task) {
    if (busy) return;
    busy = true;
    lockEditing(true);
    saveButton.disabled = true;
    loadButton.disabled = true;
    dateInput.disabled = true;
    try {
      if (!dateInput.value) throw new Error("Choose a date first.");
      await task(dateInput.value);
    } catch (error) {
      if (loadedDay && loadedDay !== dateInput.value) dateInput.value = loadedDay;
      show(error.message || "The operation failed.");
    } finally {
      busy = false;
      lockEditing(loadedDay !== dateInput.value);
      loadButton.disabled = false;
      dateInput.disabled = false;
    }
  }
  function replaceDiary(entries) {
    suppressChanges = true;
    try {
      diary.splice(0, diary.length, ...entries);
      renderDiary();
    } finally { suppressChanges = false; }
  }
  function requireLoaded(day) {
    if (loadedDay !== day) throw new Error("Load this date first to avoid mixing entries from different days.");
  }
  window.stagingDeleteEntry = question => run(async day => {
    requireLoaded(day);
    if (dirty) throw new Error("Save or discard your unsaved changes before deleting a saved answer.");
    if (!confirm("Delete the saved answer for " + question + " on " + day + "? Older backups may still contain it.")) return;
    const result = await api("delete/" + encodeURIComponent(day), "POST", {question});
    document.dispatchEvent(new Event("tracker:saved"));
    updateBackup(result);
    if (result.deleted) {
      replaceDiary(diary.filter(entry => entry.name !== question));
      savedSnapshot = snapshot();
      setDirty(false);
    }
    show(result.deleted ? "Deleted saved answer for " + question + "." : "No saved answer found for that date.");
  });
  saveButton.addEventListener("click", () => run(async day => {
    requireLoaded(day);
    const entries = entriesForSave();
    if (!entries.length) {
      show("No answers to save. Use Delete saved entry to remove answers already stored.");
      return;
    }
    const result = await api("checkin/" + encodeURIComponent(day), "POST", {entries});
    document.dispatchEvent(new Event("tracker:saved"));
    updateBackup(result);
    savedSnapshot = snapshot();
    setDirty(false);
    show("Saved " + result.saved + " answers for " + day + ". Existing answers not shown here remain saved.");
  }));
  function loadDay(confirmed = false) { return run(async day => {
    if (dirty && !confirmed && !confirm("Discard your unsaved changes and load the saved answers for this date?")) return;
    const result = await api("checkin/" + encodeURIComponent(day), "GET");
    replaceDiary(result.entries);
    loadedDay = day;
    savedSnapshot = snapshot();
    setDirty(false);
    lockEditing(false);
    show("Loaded " + result.entries.length + " answers for " + day + ". You can now edit and save.");
  }); }
  loadButton.addEventListener("click", () => loadDay());
  window.addEventListener("beforeunload", event => {
    if (!dirty) return;
    event.preventDefault();
    event.returnValue = "";
  });
  lockEditing(true);
  show("Loading today’s diary…");
  setDirty(false);
  loadDay();
})();
