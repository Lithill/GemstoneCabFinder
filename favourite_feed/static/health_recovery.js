"use strict";
(() => {
 const el=id=>document.getElementById(id), symptom=el("recovery-symptom");if(!symptom)return;
 const status=el("recovery-status"), results=el("recovery-results");
 let sequence=0;
 function add(parent,tag,text){const n=document.createElement(tag);n.textContent=text;parent.append(n);return n;}
 // Request the chosen symptom, activity grouping, lookback window and symptom lag.
 async function load(){
   const ticket=++sequence;results.replaceChildren();status.textContent="Comparing recorded activity…";
   const selected=symptom.value;
   try{
     const path=[el("recovery-days").value,el("recovery-lag").value,el("recovery-mode").value].join("/");
     const r=await fetch("/private-health-api/exercise-recovery/"+path+"?symptom="+encodeURIComponent(selected),{credentials:"same-origin",cache:"no-store"});
     if(!r.ok)throw Error();const data=await r.json();if(ticket!==sequence)return;
     symptom.replaceChildren();
     // Keep two default symptom choices first, then append other available symptoms without duplicates.
     const names=["Fibromyalgia pain","Fatigue / lacking in energy",...data.symptoms.filter(s=>!["Fibromyalgia pain","Fatigue / lacking in energy"].includes(s))];
     for(const name of names){const o=add(symptom,"option",name);o.value=name;}symptom.value=selected;
     status.textContent="Average recorded severity (0–3). Lower means fewer or milder symptoms.";
     // Display mean severity, rated days and eligible days for each activity group.
     for(const row of data.rows){
       const block=document.createElement("div");block.className="impact-result";add(block,"strong",row.label);
       add(block,"p",(row.mean===null?"No matching ratings":row.mean.toFixed(2)+" / 3")+" · "+row.n+" rated days out of "+row.days+" eligible days");
       if(row.mean!==null){const bar=document.createElement("progress");bar.max=3;bar.value=row.mean;bar.setAttribute("aria-label",row.label+": "+row.mean.toFixed(2));block.append(bar);}
       if(row.n<5)add(block,"p","Not enough observations for a comparison");
       results.append(block);
     }
     // Only compare groups with at least five ratings; sort by mean to find the extremes.
     const eligible=data.rows.filter(r=>r.n>=5).sort((a,b)=>a.mean-b.mean);
     // Highlight an exploratory difference only when the extreme means differ by at least half a point.
     if(eligible.length>=2&&eligible[eligible.length-1].mean-eligible[0].mean>=.5){
       add(results,"p","Lower recorded severity: "+eligible[0].label+" compared with "+eligible[eligible.length-1].label+". Exploratory association, not proof of an effect.");
     }else add(results,"p",eligible.length<2?"More observations needed in at least two groups.":"No difference of 0.5 points or more among groups with at least five ratings.");
   }catch(_){if(ticket===sequence)status.textContent="Could not load recovery comparisons. Reopen Impact analysis to retry.";}
 }
 el("impact-tab").addEventListener("click",load);
 for(const id of ["recovery-symptom","recovery-mode","recovery-days","recovery-lag"])el(id).addEventListener("change",load);
})();
