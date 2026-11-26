"use strict";
(() => {
 const el=id=>document.getElementById(id), symptom=el("cycle-symptom");if(!symptom)return;
 const status=el("cycle-status"), results=el("cycle-results");
 let seq=0;
 function add(parent,tag,value){const n=document.createElement(tag);n.textContent=value;parent.append(n);return n;}
 async function load(){
   const ticket=++seq;results.replaceChildren();status.textContent="Comparing recorded bleeding and symptoms…";
   const selected=symptom.value;
   try{
     const r=await fetch("/private-health-api/cycle-impact/"+el("cycle-days").value+"?symptom="+encodeURIComponent(selected),{credentials:"same-origin",cache:"no-store"});
     if(!r.ok)throw Error();const data=await r.json();if(ticket!==seq)return;
     symptom.replaceChildren();
     for(const name of data.symptoms){const o=add(symptom,"option",name);o.value=name;}symptom.value=selected;
     status.textContent=data.starts.length+" recorded or observed period starts in this window.";
     if(data.starts.length)add(results,"p","Start dates: "+data.starts.join(", "));
     for(const row of data.rows){
       const block=add(results,"div","");block.className="impact-result";add(block,"strong",row.label);
       add(block,"p",(row.mean===null?"No matching ratings":row.mean.toFixed(2)+" / 3")+" · "+row.n+" rated days out of "+row.days+" eligible days");
       if(row.mean!==null){const bar=document.createElement("progress");bar.max=3;bar.value=row.mean;bar.setAttribute("aria-label",row.label+": "+row.mean.toFixed(2));block.append(bar);}
       if(row.n<5)add(block,"p","Limited observations");
     }
     const eligible=data.rows.filter(r=>r.n>=5).sort((a,b)=>a.mean-b.mean);
     if(eligible.length>=2&&eligible[eligible.length-1].mean-eligible[0].mean>=.5)add(results,"p","Lower recorded severity: "+eligible[0].label+" compared with "+eligible[eligible.length-1].label+". This does not establish a hormonal cause.");
     else add(results,"p",eligible.length<2?"More ratings needed in at least two groups.":"No difference of 0.5 points or more among groups with at least five ratings.");
     add(results,"p","Multiple days from one period are not independent cycles. Look for repeated patterns over time.");
   }catch(_){if(ticket===seq)status.textContent="Could not load cycle comparisons. Try again.";}
 }
 el("cycle-load").addEventListener("click",load);
})();
