(() => {
 const bar=document.getElementById("import-bar"), count=document.getElementById("import-count"), status=document.getElementById("import-status");
 const resume=document.getElementById("import-resume"), pause=document.getElementById("import-pause");
 let running=false,busy=false,done=resume.disabled;
 // Await each batch before requesting another; pausing never interrupts a database write.
 async function run(){
   if(busy||done)return;
   busy=running=true;resume.disabled=true;pause.disabled=false;
   try{
     while(running&&!done){
       status.textContent="Importing next batch…";
       const response=await fetch(location.pathname,{method:"POST",cache:"no-store"});
       const data=await response.json();
       if(!response.ok)throw Error(data.error||"Import paused. Resume to retry.");
       done=Boolean(data.done);
       if(done||Number.isFinite(data.total)&&data.total>0){
         bar.max=Math.max(data.total||0,data.processed,1);bar.value=done?bar.max:data.processed;
       }else bar.removeAttribute("value");
       count.textContent=data.processed+(data.total!=null?" of "+data.total:"")+" processed · "+data.imported+" imported · "+data.skipped+" skipped";
       status.textContent=done?"Import complete":running?"Batch saved":"Paused — progress saved";
     }
   }catch(e){status.textContent="Import paused. "+e.message;}
   finally{busy=running=false;resume.disabled=done;pause.disabled=true;}
 }
 resume.onclick=run;
 pause.onclick=()=>{running=false;pause.disabled=true;status.textContent="Pausing after current batch…";};
 if(!done)run();
})();