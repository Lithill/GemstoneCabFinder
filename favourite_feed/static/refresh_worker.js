/* Any open page on this site can continue a manually started refresh.
   A locked phone or closed browser may pause requests; progress persists. */
(function(){
 // Prevent overlapping requests from this page and stop processing when the page is left.
 let busy=false, stopped=false;
 async function call(path){
   const r=await fetch(path,{method:'POST',cache:'no-store'});
   if(!r.ok)throw new Error('HTTP '+r.status);
   return r.json();
 }
 // Check persisted status only while this page is visible and no request is in progress.
 async function tick(){
   if(busy||stopped||document.hidden)return;
   busy=true;
   try{
     const response=await fetch('/refresh/status',{cache:'no-store'});
     if(!response.ok)return;
     const state=await response.json();
     // Request one server-side processing step only for an already running refresh.
     if(state.status==='running'){
       await call('/refresh/step');
     }
   }catch(e){console.warn('Refresh temporarily interrupted',e);}
   finally{busy=false;}
 }
 // Resume checking when the page becomes visible; the timer otherwise checks every five seconds.
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)tick();});
 window.addEventListener('pagehide',()=>{stopped=true;});
 setInterval(tick,5000);
 tick();
})();
