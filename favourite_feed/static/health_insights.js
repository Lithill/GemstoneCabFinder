"use strict";
(() => {
  const month = document.getElementById("insight-month");
  if (!month) return;
  const dayInput = document.getElementById("staging-day");
  const calendar = document.getElementById("insight-calendar");
  const symptom = document.getElementById("insight-symptom");
  const chart = document.getElementById("insight-chart");
  const status = document.getElementById("insight-status");
  const diaryTab = document.getElementById("diary-tab");
  const insightsTab = document.getElementById("insights-tab");
  const diaryPanel = document.getElementById("diary-panel");
  const insightsPanel = document.getElementById("insights-panel");
  // Switch between diary and insights, hide other panels and update accessible tab states.
  function selectView(insights) {
    document.getElementById("factors-panel").hidden = true;
    document.getElementById("factors-tab").setAttribute("aria-pressed", "false");
    document.getElementById("impact-panel").hidden = true;
    document.getElementById("impact-tab").setAttribute("aria-pressed","false");
    diaryPanel.hidden = insights;
    insightsPanel.hidden = !insights;
    diaryTab.setAttribute("aria-pressed", String(!insights));
    insightsTab.setAttribute("aria-pressed", String(insights));
    if (insights) load();
  }
  diaryTab.addEventListener("click", () => selectView(false));
  insightsTab.addEventListener("click", () => selectView(true));
  // Hold the loaded month in memory and use a sequence number to reject stale responses.
  let data = null, sequence = 0;
  month.value = dayInput.value.slice(0, 7);
  // Rebuild the calendar and timeline from the current month and selected symptom.
  function draw() {
    calendar.replaceChildren();
    chart.replaceChildren();
    document.getElementById("insight-context").replaceChildren();
    if (!data) return;
    const [year, m] = month.value.split("-").map(Number);
    // Calculate the number of days in the month and convert Sunday-first weekday numbering to Monday-first.
    const count = new Date(year, m, 0).getDate();
    const offset = (new Date(year, m - 1, 1).getDay() + 6) % 7;
    for (const name of ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]) {
      const label = document.createElement("span");
      label.textContent = name;
      calendar.append(label);
    }
    for (let i = 0; i < offset; i++) calendar.append(document.createElement("span"));
    // Create severity rows for explicit ratings; missing ratings leave cells blank.
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
    const context = data.timeline || {};
    // Convert recorded activity, bleeding and dated changes into compact timeline markers with descriptive labels.
    const contextRows = [
      ["Exercise", d => {
        const log = d.exercise;
        if (!log) return ["", "Exercise not recorded"];
        if (log.rest) return ["R", "Recorded rest day"];
        if (!log.sessions.length) return ["", "Exercise not recorded"];
        return [String(log.sessions.reduce((n,s)=>n+s.minutes,0)), log.sessions.map(s=>s.activity+" "+s.minutes+" min ("+s.intensity+")").join("; ")];
      }],
      ["Bleeding", d => [({None:"–",Period:"P",Spotting:"S",Unexpected:"U"})[d.period] || "", d.period===null?"Bleeding not recorded":d.period]],
      ["Changes", d => [d.changes.length?String(d.changes.length):"",d.changes.map(e=>e.name+" — "+e.status+" "+e.dose).join("; ")]]
    ];
    for (const [label, describe] of contextRows) {
      const row=table.insertRow();const th=document.createElement("th");th.scope="row";th.textContent=label;row.append(th);
      for(let i=1;i<=count;i++){
        const date=month.value+"-"+String(i).padStart(2,"0"),cell=row.insertCell();
        const d=context[date];if(!d)continue;
        const [mark,detail]=describe(d);
        cell.textContent=mark;cell.title=detail;cell.setAttribute("aria-label",date+": "+(detail||"No dated change"));
        if(mark)cell.className="insight-point";
      }
    }
    chart.append(table);
    const detailBox=document.getElementById("insight-context");
    detailBox.replaceChildren();
    function add(parent,tag,value){const node=document.createElement(tag);node.textContent=value;parent.append(node);return node;}
    // Display the effective ongoing factors at the start of the selected month.
    add(detailBox,"h3","Ongoing factors at start of month");
    if(!(data.baseline||[]).length)add(detailBox,"p","No ongoing factor recorded as of the first day.");
    for(const e of data.baseline||[])add(detailBox,"p",e.name+" — "+e.status+" "+e.dose+" (since "+e.day+")");
    add(detailBox,"h3","Recorded changes and activity");
    // Show expandable daily details in chronological order.
    for(const [date,d] of Object.entries(context).sort((a,b)=>a[0].localeCompare(b[0]))){
      const lines=[];
      if(d.exercise)lines.push(contextRows[0][1](d)[1]);
      if(d.period&&d.period!=="None")lines.push("Bleeding: "+d.period);
      for(const e of d.changes)lines.push(e.name+" — "+e.status+" "+e.dose);
      if(lines.length){const block=add(detailBox,"details","");add(block,"summary",date+" · "+lines.length+" recorded item(s)");for(const line of lines)add(block,"p",line);}
    }

    for (let i=1;i<=count;i++) {
      const date = month.value + "-" + String(i).padStart(2,"0");
      const entry = data.days[date];
      const button = document.createElement("button");
      button.type = "button"; button.textContent = String(i);
      button.className = entry ? "insight-recorded" : "";
      button.setAttribute("aria-label", date + (entry ? ", " + entry.count + " recorded answers" : ", no recorded answers"));
      // Open the selected day's diary through the existing date-change handler, preserving its unsaved-change safeguards.
      button.addEventListener("click", () => {
        if (dayInput.disabled) return;
        selectView(false);
        dayInput.value = date;
        dayInput.dispatchEvent(new Event("change"));
        dayInput.scrollIntoView({block:"center"});
      });
      calendar.append(button);
    }
    status.textContent = Object.keys(data.days).length + " days with saved answers. Blank chart columns mean no recorded severity.";
  }
  // Fetch private monthly data without caching and ignore responses superseded by a newer request.
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
      // Preserve the selected symptom when it is still available in the new month.
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
  // Refresh visible insights after a diary save or deletion.
  document.addEventListener("tracker:saved", () => { if (!insightsPanel.hidden) load(); });
})();
