"use strict";
// Prototype only. Entries are held in JavaScript memory and never transmitted or persisted.
const groups = [
  {name:"Daily questions",items:[
    ["Hot flushes","yesno"],["Night sweats","yesno"]
  ]},
  {name:"Periods and bleeding",items:[
    ["Period / bleeding today","period"],["Period start or end date","date"],["Cycle changes or irregular periods","severity"],["Heavy bleeding or flooding","severity"]
  ]},
  {name:"Mood and emotions",items:[
    ["Anhedonia (loss of enjoyment)","severity"],["Anxiety / feeling tense or nervous","severity"],["Change to your mood / mood swings","severity"],["Crying spells","severity"],["Depression / low mood","severity"],["Irritability","severity"],["Lack of motivation","severity"],["Shutdowns","severity"],["Meltdowns","severity"],["Panic attacks","severity"],["Anger or angry outbursts","severity"]
  ]},
  {name:"Thinking, energy and sleep",items:[
    ["Brain fog","severity"],["Difficulty concentrating / loss of concentration","severity"],["Fatigue / lacking in energy","severity"],["Difficulty sleeping / insomnia","sleep"]
  ]},
  {name:"Physical symptoms",items:[
    ["Bloating","severity"],["Breathing difficulties","severity"],["Digestive problems","severity"],["Feeling dizzy or faint","severity"],["Headaches","severity"],["Heartburn","severity"],["Heart palpitations","severity"],["Migraines","severity"],["Nausea","severity"],["Pins and needles / tingling hands or feet","severity"],["Sore breasts","severity"],["Tinnitus","severity"]
  ]},
  {name:"Urinary and sexual health",items:[
    ["UTI episode / recurrent UTIs","uti"],["Sex drive / low libido / fluctuations","libido"]
  ]},
  {name:"Weight",items:[
    ["Weight measurement","weight"]
  ]}
];
const questions=groups.flatMap(g=>g.items.map(([name,type])=>({name,type,category:g.name})));
const $=id=>document.getElementById(id);
const diary=[];
let step=0, current=null;
function el(tag,attrs={},parent){
  const node=document.createElement(tag);
  Object.entries(attrs).forEach(([k,v])=>{if(k==="text")node.textContent=v;else if(k==="className")node.className=v;else node.setAttribute(k,v);});
  if(parent)parent.appendChild(node);
  return node;
}
function field(parent,label,type,options){
  const wrap=el("div",{className:"tracker-field"},parent);
  const id="field-"+parent.id+"-"+parent.children.length;
  if(options){
    const group=el("fieldset",{className:"tracker-radio-group"},wrap);
    el("legend",{text:label},group);
    const inputs=options.map(([value,text],i)=>{
      const item=el("label",{className:"tracker-radio-option"},group);
      const radio=el("input",{type:"radio",name:id,value},item);
      if(i===0)radio.checked=true;
      el("span",{text},item);
      return radio;
    });
    return {get value(){return (inputs.find(r=>r.checked)||inputs[0]).value;}};
  }
  el("label",{for:id,text:label},wrap);
  const input=el("input",{id,type:type||"text"},wrap);
  if(type==="number"){input.min="0";input.step="any";}
  return input;
}
function fields(parent,q){
  parent.replaceChildren();
  const inputs={};
  if(q.type==="yesno") inputs.answer=field(parent,"Today",null,[["","Not answered"],["Yes","Yes"],["No","No"]]);
  else if(q.type==="period"){
    inputs.answer=field(parent,"Bleeding today",null,[["","Not recorded"],["None","None"],["Period","Period"],["Spotting","Spotting"],["Unexpected","Unexpected bleeding"]]);
    inputs.flow=field(parent,"Flow",null,[["","Not recorded"],["Light","Light"],["Medium","Medium"],["Heavy","Heavy"],["Flooding","Flooding"]]);
  }else if(q.type==="date"){
    inputs.answer=field(parent,"Date","date");
    inputs.detail=field(parent,"Event",null,[["Start","Period started"],["End","Period ended"]]);
  }else if(q.type==="weight"){
    inputs.answer=field(parent,"Weight","number");
    inputs.unit=field(parent,"Unit",null,[["kg","kg"],["lb","pounds"],["st","stones (decimal)"]]);
  }else if(q.type==="libido"){
    inputs.answer=field(parent,"Sex drive",null,[["","Not recorded"],["Low","Low / absent"],["Usual","Usual for me"],["Higher","Higher than usual"],["Fluctuating","Fluctuating"]]);
  }else if(q.type==="uti"){
    inputs.answer=field(parent,"UTI status",null,[["","Not recorded"],["Suspected","Suspected"],["Confirmed","Confirmed"],["Symptoms","Urinary symptoms"],["Resolved","Resolved"]]);
    inputs.detail=field(parent,"Treatment or symptoms (optional)","text");
  }else if(q.type==="sleep"){
    inputs.answer=field(parent,"Difficulty",null,[["","Not recorded"],["Mild","Mild"],["Moderate","Moderate"],["Severe","Severe"]]);
    inputs.hours=field(parent,"Hours slept (optional)","number");
  }else{
    inputs.answer=field(parent,"Severity",null,[["","Not recorded"],["Mild","Mild"],["Moderate","Moderate"],["Severe","Severe"]]);
  }
  if(q.type!=="yesno"&&q.type!=="date"&&q.type!=="weight"){
    inputs.time=field(parent,"Time of day",null,[["","Any time"],["Morning","Morning"],["Afternoon","Afternoon"],["Evening","Evening"],["Night","Night"]]);
  }
  inputs.notes=field(parent,"Optional notes (not saved)","text");
  return inputs;
}
function collect(q,inputs){
  const answer=inputs.answer.value.trim();
  if(!answer)return null;
  const extras=Object.entries(inputs).filter(([key])=>key!=="answer"&&key!=="notes").map(([key,input])=>input.value.trim()?key+": "+input.value.trim():"").filter(Boolean);
  return {name:q.name,answer,extras,notes:inputs.notes.value.trim()};
}
function add(entry){
  if(!entry)return false;
  diary.push(entry);renderDiary();return true;
}
function renderDiary(){
  $("entry-count").textContent=diary.length+" entries";
  $("empty-diary").hidden=diary.length>0;
  $("diary-items").replaceChildren();
  diary.forEach((item,i)=>{
    const row=el("div",{className:"tracker-diary-item"},$("diary-items"));
    const info=el("div",{},row);
    el("strong",{text:item.name},info);
    el("p",{text:[item.answer,...item.extras].join(" · ")},info);
    if(item.notes)el("p",{text:item.notes},info);
    const remove=el("button",{type:"button",text:"Remove", "aria-label":"Remove "+item.name},row);
    remove.addEventListener("click",()=>{diary.splice(i,1);renderDiary();});
  });
}
function showMode(mode){
  $("guided").hidden=mode!=="guided";
  $("quick").hidden=mode!=="quick";
  if(mode==="guided")showStep();
  if(mode==="quick")quickFields();
}
function guidedAdvance(){
  if(step>=questions.length)return;
  add(collect(questions[step],current));
  step++;
  showStep();
}
function guidedAutoAdvance(q){
  // Multi-part questions need a deliberate Next tap so other fields aren't skipped.
  if(!["yesno","severity"].includes(q.type))return;
  const answerGroup=$("guided-fields").querySelector(".tracker-radio-group");
  if(!answerGroup)return;
  answerGroup.addEventListener("change",event=>{
    if(!event.target.matches('input[type="radio"]'))return;
    if(!event.target.value)return;
    // If the user has chosen to add a note, let them finish before proceeding.
    if($("guided-notes-toggle")?.checked)return;
    guidedAdvance();
  });
}
function showStep(){
  if(step>=questions.length){
    $("guided-question").textContent="Guided check-in complete";
    $("guided-help").textContent="Review your temporary entries below, or go back to edit more questions.";
    $("guided-fields").replaceChildren();
    $("guided-progress").textContent="Complete";
    $("guided-bar").value=questions.length;
    $("guided-next").hidden=true;$("guided-skip").hidden=true;
    $("guided-back").disabled=false;
    return;
  }
  const q=questions[step];
  $("guided-question").textContent=q.name;
  $("guided-help").textContent=q.category+" · Leave unanswered to skip. No entries are saved.";
  $("guided-progress").textContent=(step+1)+" of "+questions.length;
  $("guided-bar").max=questions.length;$("guided-bar").value=step+1;
  current=fields($("guided-fields"),q);
  if(["yesno","severity"].includes(q.type)){
    const notesField=current.notes.closest(".tracker-field");
    notesField.hidden=true;
    const toggleLabel=el("label",{className:"tracker-notes-toggle"},$("guided-fields"));
    const toggle=el("input",{type:"checkbox",id:"guided-notes-toggle"},toggleLabel);
    el("span",{text:"Add a note before continuing"},toggleLabel);
    toggle.addEventListener("change",()=>{notesField.hidden=!toggle.checked;if(toggle.checked)current.notes.focus();});
    guidedAutoAdvance(q);
  }
  $("guided-next").hidden=false;$("guided-skip").hidden=false;
  $("guided-back").disabled=step===0;
}
$("guided-start").addEventListener("click",()=>{step=0;showMode("guided");});
$("quick-start").addEventListener("click",()=>showMode("quick"));
$("guided-exit").addEventListener("click",()=>showMode(null));
$("quick-exit").addEventListener("click",()=>showMode(null));
$("guided-back").addEventListener("click",()=>{if(step>0){step--;showStep();}});
$("guided-skip").addEventListener("click",()=>{step++;showStep();});
$("guided-next").addEventListener("click",()=>{
  guidedAdvance();
});
let quickCategory=0,quickSymptom=0;
function radioChoices(container,title,items,selected,onSelect){
  container.replaceChildren();
  const fieldset=el("fieldset",{className:"tracker-radio-group"},container);
  el("legend",{text:title},fieldset);
  items.forEach((label,i)=>{
    const row=el("label",{className:"tracker-radio-option"},fieldset);
    const radio=el("input",{type:"radio",name:container.id,value:String(i)},row);
    radio.checked=i===selected;
    radio.addEventListener("change",()=>{if(radio.checked)onSelect(i);});
    el("span",{text:label},row);
  });
}
function quickOptions(){
  radioChoices($("quick-category"),"Category",groups.map(g=>g.name),quickCategory,i=>{
    quickCategory=i;quickSymptom=0;quickOptions();
  });
  radioChoices($("quick-symptom"),"Symptom or measurement",groups[quickCategory].items.map(item=>item[0]),quickSymptom,i=>{
    quickSymptom=i;quickFields();
  });
  quickFields();
}
function quickFields(){
  const [name,type]=groups[quickCategory].items[quickSymptom];
  current=fields($("quick-fields"),{name,type});
}
$("quick-add").addEventListener("click",()=>{
  const [name,type]=groups[quickCategory].items[quickSymptom];
  if(!add(collect({name,type},current))){alert("Choose a value before adding this entry.");return;}
  quickFields();
});
$("clear-diary").addEventListener("click",()=>{diary.length=0;renderDiary();});
quickOptions();renderDiary();
