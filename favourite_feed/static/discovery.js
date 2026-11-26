(() => {
const go=document.getElementById('continue-search'),pause=document.getElementById('pause-search'),status=document.getElementById('search-progress');
if(!go)return;
let running=false,busy=false;
go.onclick=async()=>{
 if(busy)return;
 running=true;busy=true;go.disabled=true;
 try{
 while(running){
 const r=await fetch('/discover',{method:'POST',body:new URLSearchParams({operation:'step'}),cache:'no-store'});
 if(!r.ok)throw Error('Search paused; retry later.');
 const data=await r.json();
 status.textContent=data.message;
 if(['Search complete','Not running'].includes(data.message)){location.reload();break;}
 }
 }catch(e){status.textContent=e.message;}
 finally{busy=false;running=false;go.disabled=false;}
};
pause.onclick=()=>{running=false;status.textContent='Pausing after current request. Reload to see newly found shops.';};
})();