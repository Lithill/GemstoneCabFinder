"use strict";
(() => {
 const el=id=>document.getElementById(id), tab=el("impact-tab");if(!tab)return;
 const status=el("personal-insights-status"), results=el("personal-insights-results");
 let sequence=0;
 function add(parent,tag,text){const n=document.createElement(tag);n.textContent=text;parent.append(n);return n;}
 // Fetch the server-selected exploratory patterns and ignore outdated responses.
 async function load(){
   const ticket=++sequence;results.replaceChildren();status.textContent="Looking for recorded patterns…";
   try{
     const r=await fetch("/private-health-api/personal-insights",{credentials:"same-origin",cache:"no-store"});
     if(!r.ok)throw Error();const data=await r.json();if(ticket!==sequence)return;
     status.textContent="Exploratory associations only. Symptoms can also influence whether you exercise.";
     // Separate lower and higher severity associations into two groups.
     for(const [key,title] of [["lower","Potential improvement"],["higher","Potential worsening"]]){
       add(results,"h4",title);
       if(!data[key].length)add(results,"p","No pattern meeting the display threshold yet.");
       for(const item of data[key]){
         const block=document.createElement("div");block.className="impact-result";
         add(block,"strong",item.symptom+" — "+item.factor);
         add(block,"p",item.before.toFixed(2)+" → "+item.after.toFixed(2)+" / 3 ("+item.before_n+" vs "+item.after_n+" recorded days)");
         // Label small samples as limited even when they meet the minimum display threshold.
         add(block,"p",Math.min(item.before_n,item.after_n)<10?"Limited observations":"More observations, still exploratory");
         // Flag overlapping ongoing changes as a limitation.
         if(item.overlap)add(block,"p","Other ongoing changes overlap this comparison.");
         results.append(block);
       }
     }
     // List comparisons still awaiting sufficient observations.
     add(results,"h4","Still gathering information");
     if(data.pending.length){const list=document.createElement("ul");for(const label of data.pending)add(list,"li",label);results.append(list);}
     else add(results,"p","No additional comparisons awaiting minimum observations.");
     add(results,"p","Showing up to five patterns in each direction, prioritised by observation counts. Minimum five ratings per group and a 0.5 point difference; not a statistical significance test.");
   }catch(_){if(ticket===sequence)status.textContent="Could not load personal insights. Try Refresh personal insights.";}
 }
 tab.addEventListener("click",load);el("personal-insights-refresh").addEventListener("click",load);
})();
