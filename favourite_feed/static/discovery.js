(() => {
// Find the discovery controls and status display, which may be absent when no run is active.
const go=document.getElementById('continue-search'),pause=document.getElementById('pause-search'),status=document.getElementById('search-progress');
const search=document.getElementById('seller-search');
const cards=Array.from(document.querySelectorAll('.seller-card'));
const count=document.getElementById('seller-count');
// Filter existing review cards locally by shop name or country without making server requests.
if(search)search.addEventListener('input',()=>{
 const term=search.value.trim().toLowerCase();
 let shown=0;
 for(const card of cards){card.hidden=!card.dataset.search.toLowerCase().includes(term);if(!card.hidden)shown++;}
 count.textContent=shown+' of '+cards.length+' shops shown';
});
// Ask for confirmation before submitting a rejection.
for(const button of document.querySelectorAll('.seller-reject')){
 button.addEventListener('click',event=>{if(!window.confirm('Reject this shop? It will no longer appear in your review list.'))event.preventDefault();});
}
// Keep local filtering available even when there is no active discovery run.
if(!go)return;
let running=false,busy=false;
// Start a sequential request loop and prevent overlapping loops from this page.
go.onclick=async()=>{
 if(busy)return;
 running=true;busy=true;go.disabled=true;
 try{
 // Request one discovery step at a time, awaiting each result before continuing.
 while(running){
 const r=await fetch('/discover',{method:'POST',body:new URLSearchParams({operation:'step'}),cache:'no-store'});
 if(!r.ok)throw Error('Search paused; retry later.');
 const data=await r.json();
 status.textContent=data.message;
 // Reload the review list when the server reports completion or no active run.
 if(['Search complete','Not running'].includes(data.message)){location.reload();break;}
 }
 }catch(e){status.textContent=e.message;}
 // Reset browser controls whether the loop completes, pauses or encounters an error.
 finally{busy=false;running=false;go.disabled=false;pause.disabled=false;}
};
// Stop issuing new steps after the current request finishes; this pauses the browser loop, not the persisted server run.
pause.onclick=()=>{running=false;pause.disabled=true;status.textContent='Pausing after current request. Reload to see newly found shops.';};
})();