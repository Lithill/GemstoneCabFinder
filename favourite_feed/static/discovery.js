(() => {
const go=document.getElementById('continue-search'),pause=document.getElementById('pause-search'),status=document.getElementById('search-progress');
const search=document.getElementById('seller-search');
const cards=Array.from(document.querySelectorAll('.seller-card'));
const count=document.getElementById('seller-count');
if(search)search.addEventListener('input',()=>{
 const term=search.value.trim().toLowerCase();
 let shown=0;
 for(const card of cards){card.hidden=!card.dataset.search.toLowerCase().includes(term);if(!card.hidden)shown++;}
 count.textContent=shown+' of '+cards.length+' shops shown';
});
for(const button of document.querySelectorAll('.seller-reject')){
 button.addEventListener('click',event=>{if(!window.confirm('Reject this shop? It will no longer appear in your review list.'))event.preventDefault();});
}
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
 finally{busy=false;running=false;go.disabled=false;pause.disabled=false;}
};
pause.onclick=()=>{running=false;pause.disabled=true;status.textContent='Pausing after current request. Reload to see newly found shops.';};
})();