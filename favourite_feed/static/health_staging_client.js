"use strict";
// This client is loaded ONLY in the double-opt-in private staging tracker.
// The private storage client also supports the personal diary when storage is enabled; the preview alone does not load this script.
(() => {
  const dateInput = document.getElementById("staging-day");
  if (!dateInput) return;
  const status = document.getElementById("staging-status");
  const indicator = document.getElementById("staging-save-state");
  const saveButton = document.getElementById("staging-save");
  const loadButton = document.getElementById("staging-load");
  const modeButtons = [document.getElementById("guided-start"), document.getElementById("quick-start")];
  const modeSections = [document.getElementById("guided"), document.getElementById("quick")];
  // Disable editing while a date is unloaded or an asynchronous operation is underway.
  function lockEditing(locked) {
    modeButtons.forEach(button => { button.disabled = locked; });
    modeSections.forEach(section => { section.inert = locked || busy; if (locked && !busy) section.hidden = true; });
    document.getElementById("diary-items").inert = locked || busy;
    document.getElementById("clear-diary").disabled = locked;
    saveButton.disabled = locked || busy;
  }
  // Use the browser's local calendar date rather than a UTC date string.
  const today = new Date();
  dateInput.value = [today.getFullYear(), String(today.getMonth()+1).padStart(2,"0"), String(today.getDate()).padStart(2,"0")].join("-");
  // Keep session token, request state, loaded date and saved snapshot in this page's memory.
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
  // Track backup success separately from successful diary writes.
  const updateBackup = result => {
    if (typeof result.backup_ok === "boolean") backupFailed = !result.backup_ok;
  };
  // Exclude free-text notes from the transmitted entries; sort snapshots by name for stable dirty-state comparisons.
  const entriesForSave = () => diary.map(({name, answer, extras}) => ({name, answer, extras, notes:""}));
  const snapshot = () => JSON.stringify(entriesForSave().slice().sort((a,b) => a.name.localeCompare(b.name)));
  const setDirty = value => {
    dirty = value;
    indicator.textContent = dirty ? "Unsaved changes" : (loadedDay === dateInput.value ? "All changes saved or loaded" : "Date not loaded");
    indicator.dataset.state = dirty ? "unsaved" : "saved";
  };
  // Compare the current draft against the last loaded or saved snapshot.
  const refreshDirty = () => {
    if (!suppressChanges) setDirty(savedSnapshot === null ? diary.length > 0 : snapshot() !== savedSnapshot);
  };
  document.addEventListener("tracker:diary-changed", refreshDirty);
  // Confirm discarding changes before switching dates and load the selected day's saved answers.
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
  // Obtain the session's CSRF token for protected write requests and reuse it in memory.
  async function sessionToken() {
    if (csrf) return csrf;
    const response = await fetch("/private-health-api/session", {credentials:"same-origin", cache:"no-store"});
    if (!response.ok) throw new Error("Your private session has expired. Keep this tab open and sign in again in a separate tab, then retry.");
    csrf = (await response.json()).csrf;
    return csrf;
  }
  // Use same-origin credentials and no-store requests; attach JSON and CSRF headers for writes.
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
    // Discard the cached token on authentication or security failure while retaining the local draft.
    if (response.status === 401 || response.status === 403) {
      csrf = null;
      throw new Error("Session expired or security check failed. Keep this tab open, sign in again in a separate tab, then retry. Your entries remain here.");
    }
    if (!response.ok) throw new Error("The check-in could not be processed (" + response.status + ").");
    return response.json();
  }
  // Serialise diary operations, lock controls during requests and restore the previously loaded date on failure.
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
  // Replace the shared array in place without treating server-loaded answers as user edits.
  function replaceDiary(entries) {
    suppressChanges = true;
    try {
      diary.splice(0, diary.length, ...entries);
      renderDiary();
    } finally { suppressChanges = false; }
  }
  // Prevent writing answers to a date other than the one currently loaded.
  function requireLoaded(day) {
    if (loadedDay !== day) throw new Error("Load this date first to avoid mixing entries from different days.");
  }
  // Require a clean draft and explicit confirmation before deleting a saved answer.
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
  // Save the current draft explicitly; omitted answers remain stored rather than being deleted.
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
  // Read the selected date and establish a new clean snapshot after successful loading.
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
  // Request a browser navigation warning when the draft contains unsaved changes.
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
