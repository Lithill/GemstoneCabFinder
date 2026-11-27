"use strict";
(() => {
 const el=id=>document.getElementById(id), symptom=el("combined-symptom");if(!symptom)return;
 const status=el("combined-status"),results=el("combined-results");let seq=0;
 function add(parent,tag,value){const n=document.createElement(tag);n.textContent=value;parent.append(n);return n;}
 // Invalidate pending results when controls change; wait for an explicit comparison request.
 for(const id of ["combined-symptom","combined-days","combined-lag"])el(id).addEventListener("change",()=>{seq++;results.replaceChildren();status.textContent="Select Compare influencing factors to update.";});
 // Fetch the selected symptom, window and lag only when the comparison button is pressed.
 el("combined-load").addEventListener("click",async()=>{
   const ticket=++seq, selected=symptom.value;results.replaceChildren();status.textContent="Comparing similar recorded contexts…";
   try{
     const r=await fetch("/private-health-api/combined/"+el("combined-days").value+"/"+el("combined-lag").value+"?symptom="+encodeURIComponent(selected),{credentials:"same-origin",cache:"no-store"});
     if(!r.ok)throw Error();const data=await r.json();if(ticket!==seq)return;
     symptom.replaceChildren();for(const name of data.symptoms){const o=add(symptom,"option",name);o.value=name;}symptom.value=selected;
     status.textContent="Average severity (0–3) for exercise versus recorded rest days.";
     // Display each bleeding context split by proximity to a recorded medication or supplement change.
     for(const row of data.rows){
       const block=add(results,"div","");block.className="impact-result";
       add(block,"strong",row.context+" — "+(row.recent?"Near recorded change":"No recent recorded change"));
       // Compare recorded rest and exercise means within the same context, retaining sample sizes and missing values.
       for(const [key,label] of [["rest","Rest"],["active","Exercise"]]){
         const value=row[key];add(block,"p",label+": "+(value===null?"No ratings":value.toFixed(2)+" / 3")+" ("+row[key+"_n"]+" days)");
         if(value!==null){const bar=document.createElement("progress");bar.max=3;bar.value=value;bar.setAttribute("aria-label",label+": "+value.toFixed(2));block.append(bar);}
       }
       add(block,"p",({lower:"Lower recorded severity after exercise",higher:"Higher recorded severity after exercise",similar:"Little recorded difference",insufficient:"Not enough observations"})[row.direction]);
     }
     // Explain exclusions using the first missing item counted by the server.
     add(results,"p","Excluded days: "+data.excluded.activity+" missing activity, "+data.excluded.bleeding+" missing bleeding, "+data.excluded.symptom+" missing symptom rating (first missing item counted).");
     add(results,"p","At least five ratings per group and a difference of 0.5 points are needed to highlight an association. These comparisons do not establish causes.");
   }catch(_){if(ticket===seq)status.textContent="Could not load combined comparisons. Try again.";}
 });
})();
