/* ── API ─────────────────────────────────────────────────────────────────── */
async function api(url, method='GET', body=null){
  const opts={method,headers:{'Content-Type':'application/json'}};
  if(body) opts.body=JSON.stringify(body);
  try{
    const r=await fetch(url,opts);
    return await r.json();
  }catch(e){
    console.error('API error',e);
    return {ok:false,msg:'Network error'};
  }
}

/* ── Toast ───────────────────────────────────────────────────────────────── */
function toast(msg,type='info'){
  const c=document.getElementById('toasts');
  const t=document.createElement('div');
  t.className=`toast ${type}`;
  t.textContent=msg;
  c.appendChild(t);
  setTimeout(()=>{
    t.style.animation='toastOut .3s ease forwards';
    setTimeout(()=>t.remove(),300);
  },3500);
}

/* ── Time helpers ────────────────────────────────────────────────────────── */
function fmtTime(iso){
  if(!iso)return'—';
  return new Date(iso).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'});
}
function fmtDT(iso){
  if(!iso)return'—';
  const d=new Date(iso);
  return d.toLocaleDateString([],{month:'short',day:'numeric'})+' '+
         d.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
}
function timeAgo(iso){
  if(!iso)return'—';
  const s=Math.floor((Date.now()-new Date(iso).getTime())/1000);
  if(s<60) return s+'s ago';
  if(s<3600) return Math.floor(s/60)+'m ago';
  return Math.floor(s/3600)+'h ago';
}

/* ── Priority helpers ────────────────────────────────────────────────────── */
function pLabel(p){
  return['VIP','P1·10 seats','P2·8 seats','P3·6 seats','P4·4 seats','P5·2 seats'][p]||'P'+p;
}
function pDotClass(p){return'pd-'+Math.min(p,5)}
function pBadgeClass(p){return'b-p'+Math.min(p,5)}

/* ── Empty state ─────────────────────────────────────────────────────────── */
function emptyHTML(icon,text){
  return`<div class="empty"><div class="empty-icon">${icon}</div><div class="empty-text">${text}</div></div>`;
}

/* ── Topbar clock ────────────────────────────────────────────────────────── */
function startClock(){
  const el=document.getElementById('topbar-time');
  if(!el)return;
  const tick=()=>{
    el.textContent=new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'});
  };
  tick(); setInterval(tick,1000);
}

/* ── Sidebar live stats ──────────────────────────────────────────────────── */
async function updateSidebarStats(){
  const st=await api('/api/stats');
  const r=document.getElementById('sb-ready');
  const o=document.getElementById('sb-occ');
  if(r) r.textContent=st.ready??'—';
  if(o) o.textContent=st.occupied??'—';
}

/* ── Init ────────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded',()=>{
  startClock();
  updateSidebarStats();
  setInterval(updateSidebarStats,10000);
});
