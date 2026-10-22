// 全站共用：資料日期過期提醒、名詞提示。由 build_site.py 嵌入每一頁，GL 是入門教室的名詞表。
(()=>{
  // 資料日期：超過 3 個交易日（只算週一到週五）沒更新就變橘色
  const b=document.querySelector(".sitenav .asofb[data-asof]");
  if(b){
    const d=new Date(b.dataset.asof+"T00:00:00"),now=new Date();let n=0;
    for(const x=new Date(d);x<now;x.setDate(x.getDate()+1)){const w=x.getDay();if(x>d&&w&&w<6)n++}
    if(n>3){b.classList.add("stale");b.textContent+="・資料可能過期"}
  }

  // 手機上導覽列可橫滑：把目前這一頁捲到看得見的位置
  const nv=document.querySelector(".sitenav"),cur=nv&&nv.querySelector("[aria-current]");
  if(cur&&nv.scrollWidth>nv.clientWidth)nv.scrollLeft=cur.offsetLeft-nv.clientWidth/2+cur.offsetWidth/2;

  // 名詞提示：表頭、統計卡標題與 data-gl 元素裡出現的名詞加底線，點一下看白話解釋
  const GL=window.__GL__||{terms:[],url:""};
  const SKIP=new Set(["股票","ETF","債券","定存","波動","通膨"]);
  const T=[];
  for(const t of GL.terms){
    if(SKIP.has(t.k))continue;
    const names=[t.k.replace(/\s*\(.*\)$/,"")];
    t.k.split("／").forEach(x=>names.push(x));
    if(/淨值比/.test(t.k))names.push("淨值比");
    for(const n of new Set(names))if(n.length>=2)T.push([n,t]);
  }
  T.sort((a,b)=>b[0].length-a[0].length);
  const SEL="th,.stats small,.kv small,.fact>span,.eyebrow,[data-gl]";
  function wrap(el){
    if(el.dataset.gld)return;el.dataset.gld=1;
    const walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);const nodes=[];
    while(walker.nextNode())nodes.push(walker.currentNode);
    for(const node of nodes){
      if(node.parentElement.closest("button,a,.gl-term,input,select,option"))continue;
      const s=node.nodeValue;let hit=null;
      for(const [n,t] of T){const i=s.indexOf(n);if(i>=0){hit=[i,n,t];break}}
      if(!hit)continue;
      const [i,n,t]=hit,span=document.createElement("span");
      span.className="gl-term";span.tabIndex=0;span.setAttribute("role","button");span.dataset.k=t.k;span.textContent=n;
      const after=node.splitText(i);after.nodeValue=after.nodeValue.slice(n.length);node.parentNode.insertBefore(span,after);
    }
  }
  const scan=()=>document.querySelectorAll(SEL).forEach(wrap);
  let pend=0;new MutationObserver(()=>{if(!pend){pend=1;requestAnimationFrame(()=>{pend=0;scan()})}}).observe(document.body,{childList:true,subtree:true});
  scan();

  let pop=null;
  const close=()=>{if(pop){pop.remove();pop=null}};
  function open(el){
    close();const t=GL.terms.find(x=>x.k===el.dataset.k);if(!t)return;
    pop=document.createElement("div");pop.className="gl-pop";pop.setAttribute("role","dialog");
    const b=document.createElement("b");b.textContent=t.k;const p=document.createElement("div");p.textContent=t.d;pop.append(b,p);
    if(GL.url){const a=document.createElement("a");a.href=GL.url+"#t-"+encodeURIComponent(t.k);a.target="_blank";a.rel="noopener";a.textContent="在入門教室看更多 →";pop.append(a)}
    document.body.append(pop);
    const r=el.getBoundingClientRect(),w=pop.offsetWidth;
    pop.style.left=Math.max(16,Math.min(scrollX+r.left,scrollX+innerWidth-w-16))+"px";pop.style.top=(scrollY+r.bottom+6)+"px";
  }
  document.addEventListener("click",e=>{const el=e.target.closest(".gl-term");if(el){e.stopPropagation();e.preventDefault();open(el)}else if(!e.target.closest(".gl-pop"))close()},true);
  document.addEventListener("keydown",e=>{if(e.key==="Escape")close();const el=e.target.closest&&e.target.closest(".gl-term");if(el&&(e.key==="Enter"||e.key===" ")){e.preventDefault();open(el)}});
})();
