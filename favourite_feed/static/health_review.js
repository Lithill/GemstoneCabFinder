"use strict";
(() => {
 const el=id=>document.getElementById(id), days=el("review-days");if(!days)return;
 const status=el("review-status"), results=el("review-results");
 let seq=0;
 function add(parent,tag,value){const n=document.createElement(tag);n.textContent=value;parent.append(n);return n;}
 async function load(){
   const ticket=++seq;results.replaceChildren();status.textContent="Preparing diary review…";
   try{
     const r=await fetch("/private-health-api/review/"+days.value,{credentials:"same-origin",cache:"no-store"});
     if(!r.ok)throw Error();const data=await r.json();if(ticket!==seq)return;
     const a=data.previous,b=data.current,n=Number(days.value);
     status.textContent=b.start+" to "+b.end+" compared with "+a.start+" to "+a.end;
     const table=add(results,"table","");table.className="impact-result";
     const head=table.insertRow();for(const label of ["Recorded activity","Previous","Latest"]){const th=add(head,"th",label);th.scope="col";}
     const metrics=[["Diary days","diary_days"],["Exercise days","active"],["Rest days","rest"],["Exercise minutes","minutes"],["Period days","period"],["Spotting days","spotting"],["Unexpected bleeding days","unexpected"],["No-bleeding days","no_bleeding"]];
     for(const [label,key] of metrics){const row=table.insertRow();const th=add(row,"th",label);th.scope="row";add(row,"td",String(a.counts[key]));add(row,"td",String(b.counts[key]));}
     add(results,"p","Latest period: "+b.counts.diary_days+"/"+n+" diary days; "+(n-b.counts.active-b.counts.rest)+" days without exercise records; "+(n-b.counts.period-b.counts.spotting-b.counts.unexpected-b.counts.no_bleeding)+" days without bleeding records.");
     for(const [key,label] of [["lower","Improving ratings"],["higher","Worsening ratings"],["similar","Little recorded difference"],["insufficient","Not enough ratings"]]){
       const rows=data.rows.filter(x=>x.direction===key).sort((x,y)=>Math.abs((y.after??0)-(y.before??0))-Math.abs((x.after??0)-(x.before??0)));
       const group=add(results,"details","");group.open=key==="lower"||key==="higher";add(group,"summary",label+" ("+rows.length+")");
       if(!rows.length)add(group,"p","No matching symptoms.");
       for(const row of rows){const block=add(group,"div","");block.className="impact-result";add(block,"strong",row.name);
         add(block,"p","Previous: "+(row.before===null?"Not recorded":row.before.toFixed(2)+" / 3")+" ("+row.before_n+" days) · Latest: "+(row.after===null?"Not recorded":row.after.toFixed(2)+" / 3")+" ("+row.after_n+" days)");}
     }
     add(results,"p","Minimum "+data.minimum+" ratings in each period and a difference of at least 0.5 points to highlight a change.");
     for(const [p,label] of [[b,"Latest ongoing changes"],[a,"Previous ongoing changes"]]){
       const group=add(results,"details","");group.open=p===b;add(group,"summary",label+" ("+p.changes.length+")");
       for(const e of p.changes)add(group,"p",e.day+" — "+e.name+" · "+e.status+" "+e.dose);
       if(!p.changes.length)add(group,"p","No dated changes recorded.");
     }
   }catch(_){if(ticket===seq)status.textContent="Could not load review. Try Refresh review.";}
 }
 el("impact-tab").addEventListener("click",load);days.addEventListener("change",load);el("review-refresh").addEventListener("click",load);
})();
