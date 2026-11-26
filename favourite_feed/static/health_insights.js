"use strict";
(() => {
  const month = document.getElementById("insight-month");
  if (!month) return;
  const dayInput = document.getElementById("staging-day");
  const calendar = document.getElementById("insight-calendar");
  const symptom = document.getElementById("insight-symptom");
  const chart = document.getElementById("insight-chart");
  const status = document.getElementById("insight-status");
  let data = null, sequence = 0;
  month.value = dayInput.value.slice(0, 7);
  function draw() {
    calendar.replaceChildren();
    chart.replaceChildren();
    if (!data) return;
    const [year, m] = month.value.split("-").map(Number);
    const count = new Date(year, m, 0).getDate();
    const offset = (new Date(year, m - 1, 1).getDay() + 6) % 7;
    for (const name of ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]) {
      const label = document.createElement("span");
      label.textContent = name;
      calendar.append(label);
    }
    for (let i = 0; i < offset; i++) calendar.append(document.createElement("span"));
    const levels = ["None", "Mild", "Moderate", "Severe"];
    const table = document.createElement("table");
    table.className = "insight-plot";
    const header = table.insertRow();
    for (const label of ["Severity", ...Array.from({length:count}, (_,i)=>String(i+1))]) {
      const th = document.createElement("th"); th.scope = "col"; th.textContent = label; header.append(th);
    }
    for (const level of [...levels].reverse()) {
      const row = table.insertRow();
      const th = document.createElement("th"); th.scope = "row"; th.textContent = level; row.append(th);
      for (let i=1;i<=count;i++) {
        const date = month.value + "-" + String(i).padStart(2,"0");
        const cell = row.insertCell();
        if (data.days[date]?.severity[symptom.value] === level) {
          cell.textContent = "●"; cell.className = "insight-point";
          cell.setAttribute("aria-label", date + ": " + level);
        }
      }
    }
    chart.append(table);
    for (let i=1;i<=count;i++) {
      const date = month.value + "-" + String(i).padStart(2,"0");
      const entry = data.days[date];
      const button = document.createElement("button");
      button.type = "button"; button.textContent = String(i);
      button.className = entry ? "insight-recorded" : "";
      button.setAttribute("aria-label", date + (entry ? ", " + entry.count + " recorded answers" : ", no recorded answers"));
      button.addEventListener("click", () => {
        if (dayInput.disabled) return;
        dayInput.value = date;
        dayInput.dispatchEvent(new Event("change"));
        dayInput.scrollIntoView({block:"center"});
      });
      calendar.append(button);
    }
    status.textContent = Object.keys(data.days).length + " days with saved answers. Blank chart columns mean no recorded severity.";
  }
  async function load() {
    const ticket = ++sequence;
    data = null; draw();
    status.textContent = "Loading month…";
    try {
      const response = await fetch("/private-health-api/month/" + encodeURIComponent(month.value), {credentials:"same-origin",cache:"no-store"});
      if (!response.ok) throw new Error();
      const result = await response.json();
      if (ticket !== sequence) return;
      data = result;
      const previous = symptom.value;
      symptom.replaceChildren();
      for (const name of data.symptoms) {
        const option = document.createElement("option"); option.value = name; option.textContent = name; symptom.append(option);
      }
      if (data.symptoms.includes(previous)) symptom.value = previous;
      draw();
    } catch (_) {
      if (ticket === sequence) status.textContent = "Could not load this month. Try Refresh insights.";
    }
  }
  month.addEventListener("change", load);
  symptom.addEventListener("change", draw);
  document.getElementById("insight-refresh").addEventListener("click", load);
  document.addEventListener("tracker:saved", load);
  load();
})();
