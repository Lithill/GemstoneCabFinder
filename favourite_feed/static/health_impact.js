"use strict";
(() => {
 const el=id=>document.getElementById(id), tab=el("impact-tab");if(!tab)return;
 const event=el("impact-event"), windowSize=el("impact-window"), status=el("impact-status"), results=el("impact-results");
 let sequence=0;
 async function api(path){const r=await fetch("/private-health-api/"+path,{cache:"no-store",credentials:"same-origin"});if(!r.ok)throw Error();return r.json();}
 function add(parent,tag,value){const n=document.createElement(tag);n.textContent=value;parent.append(n);return n;}
 async function compare(){
   const ticket=++sequence;results.replaceChildren();
   if(!event.value){status.textContent="Record an ongoing factor or dated change first.";return;}
   status.textContent="Comparing saved ratings…";
   try{
     const data=await api("impact/"+encodeURIComponent(event.value)+"/"+windowSize.value);
     if(ticket!==sequence)return;
     status.textContent=data.rows.length?"Comparison of saved ratings":"No symptom severity ratings in this window yet.";
     if(data.events.length>1)add(results,"p","Several recorded changes overlap this window. Their individual effects cannot be separated.");
     if(data.events.length){const details=document.createElement("details");add(details,"summary","Changes in this window");for(const e of data.events)add(details,"p",e.day+" — "+e.name+" · "+e.status+" "+e.dose);results.append(details);}
     const labels={lower:"Lower recorded severity",higher:"Higher recorded severity",similar:"Little recorded difference",insufficient:"Not enough observations"};
     const order={lower:0,higher:1,similar:2,insufficient:3};
     data.rows.sort((a,b)=>order[a.direction]-order[b.direction]||a.name.localeCompare(b.name));
     for(const row of data.rows){
       const block=document.createElement("div");block.className="impact-result";
       add(block,"strong",row.name);add(block,"p",labels[row.direction]);
       for(const side of ["before","after"]){
         const value=row[side], n=row[side+"_n"];
         const label=(side==="before"?"Before":"After")+": "+(value===null?"No ratings":value.toFixed(2)+" / 3")+" ("+n+" days)";
         add(block,"div",label);
         if(value!==null){const bar=document.createElement("progress");bar.max=3;bar.value=value;bar.setAttribute("aria-label",label);block.append(bar);}
       }
       results.append(block);
     }
   }catch(_){if(ticket===sequence)status.textContent="Could not load comparison. Reopen this tab to retry.";}
 }
 async function open(){
   const ticket=++sequence;
   for(const id of ["diary","insights","factors","impact"]){el(id+"-panel").hidden=id!=="impact";el(id+"-tab").setAttribute("aria-pressed",String(id==="impact"));}
   results.replaceChildren();status.textContent="Loading recorded changes…";event.disabled=true;
   try{
     const data=await api("ongoing");if(ticket!==sequence)return;
     const previous=event.value;event.replaceChildren();
     const events=data.items.flatMap(i=>i.history.map(e=>({...e,name:i.name}))).sort((a,b)=>b.day.localeCompare(a.day));
     for(const e of events){const option=document.createElement("option");option.value=e.day;option.textContent=e.day+" — "+e.name+" · "+e.status+" "+e.dose;event.append(option);}
     if(events.some(e=>e.day===previous))event.value=previous;
     event.disabled=false;compare();
   }catch(_){if(ticket===sequence)status.textContent="Could not load changes. Reopen this tab to retry.";}
 }
 tab.addEventListener("click",open);event.addEventListener("change",compare);windowSize.addEventListener("change",()=>{if(!event.disabled)compare();});
})();
