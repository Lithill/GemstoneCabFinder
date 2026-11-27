"use strict";
(() => {
 const el=id=>document.getElementById(id), day=el("exercise-day");if(!day)return;
 const status=el("exercise-status"), list=el("exercise-list");
 // Track the loaded exercise record, request state, loaded date and comparison request sequence.
 let log=null,busy=false,loaded="",seq=0;
 const buttons=["exercise-add","exercise-rest","exercise-clear"];
 async function api(path,options={}){const r=await fetch("/private-health-api/"+path,{cache:"no-store",credentials:"same-origin",...options});if(!r.ok)throw Error();return r.json();}
 // Distinguish an explicit rest day from no exercise record and display removable sessions.
 function render(){
   day.disabled=busy;for(const id of buttons)el(id).disabled=busy||!log;
   list.replaceChildren();if(!log)return;
   if(log.rest)list.textContent="Rest day recorded";
   else if(!log.sessions.length)list.textContent="No exercise record";
   log.sessions.forEach((s,i)=>{
     const p=document.createElement("p");p.textContent=s.activity+" · "+s.minutes+" min · "+s.intensity+" ";
     const b=document.createElement("button");b.type="button";b.textContent="Remove";b.disabled=busy;
     b.onclick=()=>save({rest:false,sessions:log.sessions.filter((_,j)=>j!==i)});p.append(b);list.append(p);
   });
 }
 // Load the selected day's exercise record before enabling editing.
 async function load(){
   if(busy||!day.value)return;busy=true;log=null;render();status.textContent="Loading exercise…";
   try{log=await api("exercise/"+encodeURIComponent(day.value));loaded=day.value;status.textContent="Exercise record loaded";}
   catch(_){status.textContent="Could not load exercise. Reopen the tab to retry.";}
   finally{busy=false;render();}
 }
 // Save a proposed record only for the currently loaded date, using a session CSRF token.
 async function save(next){
   if(busy||!log||day.value!==loaded)return;
   busy=true;render();status.textContent="Saving…";
   try{const token=await api("session");const r=await api("exercise/"+encodeURIComponent(loaded),{method:"POST",headers:{"Content-Type":"application/json","X-Health-CSRF":token.csrf},body:JSON.stringify(next)});log=next;status.textContent=r.backup_ok===false?"Saved, but encrypted backup failed.":"Exercise record saved";}
   catch(_){status.textContent="Could not save exercise. Try again.";}
   finally{busy=false;render();}
 }
 el("factors-tab").addEventListener("click",()=>{if(!day.value)day.value=el("staging-day").value;load();});
 day.addEventListener("change",load);
 // Validate duration and session count, and confirm replacing an explicit rest day.
 el("exercise-add").onclick=()=>{
   const minutes=Number(el("exercise-minutes").value);
   if(!Number.isInteger(minutes)||minutes<1||minutes>1440||log.sessions.length>=20){status.textContent="Enter valid minutes (1–1440), maximum 20 sessions.";return;}
   if(log.rest&&!confirm("Replace the rest day with exercise?"))return;
   save({rest:false,sessions:[...log.sessions,{activity:el("exercise-type").value,minutes,intensity:el("exercise-intensity").value}]});
 };
 // Record rest explicitly, confirming before replacing existing sessions.
 el("exercise-rest").onclick=()=>{if(!log.sessions.length||confirm("Replace all exercise sessions with a rest day?"))save({rest:true,sessions:[]});};
 // Clear the record rather than recording rest; these have different meanings in analysis.
 el("exercise-clear").onclick=()=>{if(confirm("Remove this day's exercise record?"))save({rest:false,sessions:[]});};
 const result=el("exercise-impact-results"), message=el("exercise-impact-status");
 // Request exercise-versus-rest symptom comparisons for the selected window and lag; ignore stale responses.
 async function compare(){
   const ticket=++seq;result.replaceChildren();message.textContent="Comparing exercise and rest days…";
   try{
     const data=await api("exercise-impact/"+el("exercise-range").value+"/"+el("exercise-lag").value);
     if(ticket!==seq)return;
     message.textContent=data.counts.active+" exercise days · "+data.counts.rest+" rest days recorded. "+(data.rows.length?"":"No matching symptom ratings yet.");
     // Translate server-calculated descriptive directions into readable labels and group the results.
     const labels={lower:"Lower severity associated with exercise",higher:"Higher severity associated with exercise",similar:"Little recorded difference",insufficient:"Not enough observations"};
     const order={lower:0,higher:1,similar:2,insufficient:3};
     data.rows.sort((a,b)=>order[a.direction]-order[b.direction]||a.name.localeCompare(b.name));
     for(const row of data.rows){
       const block=document.createElement("div");block.className="impact-result";
       const title=document.createElement("strong");title.textContent=row.name;block.append(title);
       const p=document.createElement("p");p.textContent=labels[row.direction];block.append(p);
       // Display each group's mean and sample size, omitting the bar when no ratings exist.
       for(const side of ["rest","active"]){
         const label=document.createElement("div");label.textContent=(side==="rest"?"Rest":"Exercise")+": "+(row[side]===null?"No ratings":row[side].toFixed(2)+" / 3")+" ("+row[side+"_n"]+" days)";block.append(label);
         if(row[side]!==null){const bar=document.createElement("progress");bar.max=3;bar.value=row[side];bar.setAttribute("aria-label",label.textContent);block.append(bar);}
       }
       result.append(block);
     }
   }catch(_){if(ticket===seq)message.textContent="Could not load exercise comparison. Reopen the tab to retry.";}
 }
 el("impact-tab").addEventListener("click",compare);
 el("exercise-range").addEventListener("change",compare);el("exercise-lag").addEventListener("change",compare);
 render();
})();
