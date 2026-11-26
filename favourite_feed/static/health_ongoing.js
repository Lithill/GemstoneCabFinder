"use strict";
(() => {
 const el=id=>document.getElementById(id), tab=el("factors-tab"); if(!tab)return;
 const name=el("ongoing-name"), category=el("ongoing-category"), day=el("ongoing-day"), state=el("ongoing-state"), dose=el("ongoing-dose"), save=el("ongoing-save"), status=el("ongoing-status");
 let items=[], ready=false, busy=false;
 const today=()=>{const d=new Date();return [d.getFullYear(),String(d.getMonth()+1).padStart(2,"0"),String(d.getDate()).padStart(2,"0")].join("-");};
 day.value=today();
 async function api(path,options={}){const r=await fetch("/private-health-api/"+path,{cache:"no-store",credentials:"same-origin",...options});if(!r.ok)throw Error();return r.json();}
 function render(){
   const list=el("ongoing-list");list.replaceChildren();
   for(const item of items){
     const block=document.createElement("div"), title=document.createElement("strong");
     const history=[...item.history].sort((a,b)=>b.day.localeCompare(a.day));
     const current=history.find(e=>e.day<=today());
     title.textContent=item.name+" — "+(current?current.status+(current.dose?" · "+current.dose:""):"Not started");block.append(title);
     const update=document.createElement("button");update.type="button";update.textContent="Update";update.disabled=busy;
     update.onclick=()=>{name.value=item.name;category.value=item.category;day.value=today();state.value=current?.status||"Ongoing";dose.value=current?.dose||"";name.focus();};block.append(update);
     const details=document.createElement("details"), summary=document.createElement("summary");summary.textContent="History";details.append(summary);
     for(const event of history){const p=document.createElement("p");p.textContent=event.day+" — "+event.status+" "+event.dose+" ";const edit=document.createElement("button");edit.type="button";edit.textContent="Correct";edit.disabled=busy;edit.onclick=()=>{name.value=item.name;category.value=item.category;day.value=event.day;state.value=event.status;dose.value=event.dose;name.focus();};p.append(edit);details.append(p);}
     block.append(details);list.append(block);
   }
   save.disabled=!ready||busy;
 }
 async function load(){if(busy||ready)return;busy=true;render();try{items=(await api("ongoing")).items;ready=true;status.textContent="Ongoing factors loaded";}catch(_){status.textContent="Could not load. Reopen this tab to retry.";}finally{busy=false;render();}}
 tab.addEventListener("click",load);
 save.onclick=async()=>{
   if(!ready||busy||!name.value.trim()||!day.value){status.textContent="Enter a name and effective date.";return;}
   const next=JSON.parse(JSON.stringify(items));
   let item=next.find(i=>i.name.toLowerCase()===name.value.trim().toLowerCase());
   if(!item){item={name:name.value.trim(),category:category.value,history:[]};next.push(item);}
   const event={day:day.value,status:state.value,dose:state.value==="Stopped"?"":dose.value.trim()};
   if(item.history.some(e=>e.day===event.day)&&!confirm("Replace the recorded change on this date?"))return;
   item.history=item.history.filter(e=>e.day!==event.day);item.history.push(event);
   busy=true;render();for(const field of [name,category,day,state,dose])field.disabled=true;
   try{const session=await api("session");const result=await api("ongoing",{method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":session.csrf},body:JSON.stringify({items:next})});items=next;name.value="";dose.value="";day.value=today();status.textContent=result.backup_ok===false?"Saved, but backup failed. Repeat save to retry.":"Dated change saved";}
   catch(_){status.textContent="Could not save. Your input remains available.";}
   finally{busy=false;for(const field of [name,category,day,state,dose])field.disabled=false;render();}
 };
})();
