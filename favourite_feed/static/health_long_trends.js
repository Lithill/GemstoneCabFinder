"use strict";
(() => {
 const el=id=>document.getElementById(id), symptom=el("long-symptom");if(!symptom)return;
 const status=el("long-status"),results=el("long-results");let seq=0;
 function add(parent,tag,value){const n=document.createElement(tag);n.textContent=value;parent.append(n);return n;}
 for(const id of ["long-symptom","long-months"])el(id).addEventListener("change",()=>{seq++;results.replaceChildren();status.textContent="Select Show longer-term trends to update.";});
 el("long-load").addEventListener("click",async()=>{
   const ticket=++seq,selected=symptom.value;results.replaceChildren();status.textContent="Loading monthly trends…";
   try{
     const r=await fetch("/private-health-api/long-trends/"+el("long-months").value+"?symptom="+encodeURIComponent(selected),{credentials:"same-origin",cache:"no-store"});
     if(!r.ok)throw Error();const data=await r.json();if(ticket!==seq)return;
     symptom.replaceChildren();for(const name of data.symptoms){const o=add(symptom,"option",name);o.value=name;}symptom.value=selected;
     status.textContent=selected+" — monthly average severity (0–3)";
     for(const row of data.rows){
       const block=add(results,"div","");block.className="impact-result";
       add(block,"strong",row.month+(row.partial?" (in progress)":""));
       add(block,"p",(row.mean===null?"No recorded ratings":row.mean.toFixed(2)+" / 3")+" · "+row.n+"/"+row.days+" days rated");
       if(row.mean!==null){const bar=document.createElement("progress");bar.max=3;bar.value=row.mean;bar.setAttribute("aria-label",row.month+": "+row.mean.toFixed(2));block.append(bar);}
       add(block,"p",row.severe+" severe days · "+row.none+" explicitly symptom-free days"+(row.n<5?" · Limited observations":""));
     }
     const eligible=data.rows.filter(r=>!r.partial&&r.n>=5);
     if(eligible.length>=2){
       const first=eligible[0],last=eligible[eligible.length-1],delta=last.mean-first.mean;
       add(results,"p","First versus latest completed month with at least five ratings ("+first.month+" to "+last.month+"): "+(delta<=-.5?"Lower recorded severity":delta>=.5?"Higher recorded severity":"Difference below 0.5 points")+". This is not a statistical trend test.");
     }else add(results,"p","More completed months with at least five ratings are needed for a comparison.");
   }catch(_){if(ticket===seq)status.textContent="Could not load longer-term trends. Try again.";}
 });
})();
