"use strict";
(() => {
 const el = id => document.getElementById(id);
 const tab = el("factors-tab"); if (!tab) return;
 const day = el("factor-day"), status = el("factor-status"), name = el("factor-name"), value = el("factor-value"), category = el("factor-category");
 // Keep the selected day's editable factors, loaded date, dirty flag and request state in memory.
 let items = [], loaded = "", dirty = false, busy = false;
 // Rebuild the list and disable date and save controls during requests.
 function render() {
   const list = el("factor-items"); list.replaceChildren();
   items.forEach((item,i) => {
     const row = document.createElement("p");
     row.textContent = item.category + " — " + item.name + ": " + item.value + " ";
     const remove = document.createElement("button"); remove.type="button"; remove.textContent="Remove"; remove.disabled=busy;
     remove.onclick=()=>{items.splice(i,1);dirty=true;render();status.textContent="Unsaved changes";};
     row.append(remove);list.append(row);
   });
   day.disabled=busy; el("factor-add").disabled=busy || !loaded; el("factor-save").disabled=busy || !loaded;
 }
 // Send requests to the private API using same-origin credentials and no-store caching.
 async function api(path, options={}) {
   const r=await fetch("/private-health-api/"+path,{cache:"no-store",credentials:"same-origin",...options});
   if(!r.ok) throw Error(); return r.json();
 }
 // Confirm discarding unsaved entries or unfinished input before loading a different day.
 async function load() {
   if(busy) return;
   if((dirty || name.value || value.value) && !confirm("Discard unsaved lifestyle changes?")) {day.value=loaded;return;}
   busy=true;render();status.textContent="Loading…";
   try {const result=await api("factors/"+encodeURIComponent(day.value));items=result.items;loaded=day.value;dirty=false;name.value="";value.value="";status.textContent="Saved factors loaded";}
   catch (_) {day.value=loaded;status.textContent="Could not load factors. Select a date to retry.";}
   finally {busy=false;render();}
 }
 // Switch to the lifestyle panel and initially load factors for the diary date.
 tab.onclick=()=>{
   el("impact-panel").hidden=true;el("impact-tab").setAttribute("aria-pressed","false");
   el("diary-panel").hidden=true;el("insights-panel").hidden=true;el("factors-panel").hidden=false;
   for(const id of ["diary-tab","insights-tab","factors-tab"]) el(id).setAttribute("aria-pressed",String(id==="factors-tab"));
   if(!loaded && !busy){day.value=el("staging-day").value;load();}
 };
 day.onchange=load;
 // Validate required fields and the local twenty-entry limit, then add to the draft without saving yet.
 el("factor-add").onclick=()=>{
   if(!name.value.trim() || !value.value.trim() || items.length>=20){status.textContent="Enter a name and amount or change (maximum 20 entries per day).";return;}
   items.push({category:category.value,name:name.value.trim(),value:value.value.trim()});name.value="";value.value="";dirty=true;render();status.textContent="Unsaved changes";
 };
 // Reject unfinished input, obtain a CSRF token and save the entire day's factor list.
 el("factor-save").onclick=async()=>{
   if(name.value || value.value){status.textContent="Add your unfinished entry before saving.";return;}
   busy=true;render();status.textContent="Saving…";
   try {const session=await api("session");const result=await api("factors/"+encodeURIComponent(loaded),{method:"POST",headers:{"Content-Type":"application/json","X-Health-CSRF":session.csrf},body:JSON.stringify({items})});dirty=false;status.textContent=result.backup_ok===false?"Saved, but encrypted backup failed. Save again to retry.":"Factors saved";}
   catch(_){status.textContent="Could not save. Your entries are still on screen.";}
   finally{busy=false;render();}
 };
 // Warn before navigating away with unsaved factors or unfinished input.
 window.addEventListener("beforeunload",e=>{if(dirty || name.value || value.value){e.preventDefault();e.returnValue="";}});
 render();
})();
