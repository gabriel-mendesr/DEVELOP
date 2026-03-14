/* =============================================================
   escala.js — Hotel 24/7 · v3
   Lê configurações do localStorage (salvas em config.html)
   ============================================================= */
'use strict';

const STORAGE_KEY = 'hotel_escala_config';

// ── DEFAULTS ──────────────────────────────────────────────────
const CFG_DEFAULTS = {
  morningStart:7, afternoonStart:15, nightStart:19,
  salaries:{ giovanna:1700, anderson:2100, gabriel:1800, folguista:1500,
    freelancer:250, intermitente:220, fdsDay:491, fdsNight:982 },
  charges:{ inss:20, rat:2, terceiros:5.8, fgts:8,
    ferias:11.11, decimo:8.33, fgtsProv:1.92, noturno:20 }
};

let _cfg = JSON.parse(JSON.stringify(CFG_DEFAULTS));

function loadStoredConfig() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) _cfg = JSON.parse(raw);
  } catch(e) { /* keep defaults */ }
}

// ── UTILS ─────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const pad = h => { h=((h%24)+24)%24; return h<10?'0'+h:''+h; };
const fmt = v => 'R$\u00a0'+Math.round(v).toLocaleString('pt-BR');
const setEl  = (id,v) => { const e=$(id); if(e) e.textContent=v; };
const setFmt = (id,v) => setEl(id,fmt(v));
const setVal = (id,v) => { const e=$(id); if(e) e.value=v; };

// ── CONFIG ────────────────────────────────────────────────────
function getCfg() {
  const ms = _cfg.morningStart   ?? 7;
  const as_ = _cfg.afternoonStart ?? 15;
  const ns = _cfg.nightStart     ?? 19;
  return {
    ms, as:as_, ns,
    morningEnd: as_, afternoonEnd: ns,
    mDur: as_-ms, aDur: ns-as_, nDur: (ms+24)-ns,
    lMorn:  `${pad(ms)}h–${pad(as_)}h`,
    lAft:   `${pad(as_)}h–${pad(ns)}h`,
    lNight: `${pad(ns)}h–${pad(ms)}h(+1)`,
    lDay:   `${pad(ms)}h–${pad(ns)}h (${ns-ms}h)`,
  };
}

function getSal() {
  const s = _cfg.salaries || {};
  const lv = id => { const e=$(id); return e ? +e.value||0 : 0; };
  return {
    gio:  lv('s-gio')  || s.giovanna     || 1700,
    and:  lv('s-and')  || s.anderson     || 2100,
    gab:  lv('s-gab')  || s.gabriel      || 1800,
    free: lv('s-free') || s.freelancer   || 250,
    int:  lv('s-int')  || s.intermitente || 220,
    fds:  lv('s-fds')  || s.fdsDay       || 491,
    fds2: lv('s-fds2') || s.fdsNight     || 982,
    folg: lv('s-folg') || s.folguista    || 1500,
  };
}

function getEnc() {
  const c = _cfg.charges || {};
  const lv = id => { const e=$(id); return e ? parseFloat(e.value)||0 : 0; };
  const inss=lv('enc-inss')||c.inss||20, rat=lv('enc-rat')||c.rat||2,
        terc=lv('enc-terc')||c.terceiros||5.8, fgts=lv('enc-fgts')||c.fgts||8,
        fer=lv('enc-fer')||c.ferias||11.11, e13=lv('enc-13')||c.decimo||8.33,
        fp=lv('enc-fp')||c.fgtsProv||1.92, not=lv('enc-not')||c.noturno||20;
  return {inss,rat,terc,fgts,fer,e13,fp,not,
    emp:inss+rat+terc+fgts, prov:fer+e13+fp, total:inss+rat+terc+fgts+fer+e13+fp};
}

function syncConfigBar() {
  const s=_cfg.salaries||{}, c=_cfg.charges||{};
  setVal('s-gio',  s.giovanna||1700);   setVal('s-and',  s.anderson||2100);
  setVal('s-gab',  s.gabriel||1800);    setVal('s-free', s.freelancer||250);
  setVal('s-int',  s.intermitente||220);setVal('s-fds',  s.fdsDay||491);
  setVal('s-fds2', s.fdsNight||982);    setVal('s-folg', s.folguista||1500);
  setVal('enc-inss',c.inss||20);        setVal('enc-rat', c.rat||2);
  setVal('enc-terc',c.terceiros||5.8);  setVal('enc-fgts',c.fgts||8);
  setVal('enc-fer', c.ferias||11.11);   setVal('enc-13',  c.decimo||8.33);
  setVal('enc-fp',  c.fgtsProv||1.92);  setVal('enc-not', c.noturno||20);
  const cfg=getCfg();
  setEl('active-shift-label', `${pad(cfg.ms)}h / ${pad(cfg.ns)}h`);
}

// ── EMP COST ──────────────────────────────────────────────────
function empCost(sal, opts={}) {
  const enc=getEnc(), {hePct=0,noturno=false}=opts;
  const adicHE=sal*(hePct/100), adicNot=noturno?sal*(enc.not/100):0;
  const gross=sal+adicHE+adicNot, encV=gross*(enc.emp/100), provV=gross*(enc.prov/100);
  return {base:sal,adicHE,adicNot,gross,encV,provV,total:gross+encV+provV};
}

// ── GANTT BUILDER ─────────────────────────────────────────────
const DAY_HDR = ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb'];

function buildGantt(tableId, legendId, sched, opts={}) {
  const table=$(tableId), legEl=$(legendId);
  if (!table||!sched) return;
  const cfg=getCfg();
  if (legEl) legEl.innerHTML=(opts.legend||[]).map(l=>
    `<div class="leg"><div class="leg-box" style="background:${l.color}"></div>${l.name}</div>`).join('');
  table.innerHTML=''; table.className='sched';
  const SHIFTS=[
    {key:'morning',  label:'☀️ Manhã', hours:cfg.lMorn },
    {key:'afternoon',label:'🌆 Tarde', hours:cfg.lAft  },
    {key:'night',    label:'🌙 Noite', hours:cfg.lNight},
  ];
  const thead=document.createElement('thead'), hrow=document.createElement('tr');
  const th0=document.createElement('th');
  th0.className='shift-lbl'; th0.style.cssText='border:1px solid var(--border)';
  hrow.appendChild(th0);
  DAY_HDR.forEach((d,i)=>{
    const th=document.createElement('th');
    th.className='day-h'+(i===0?' sun':''); th.textContent=d; hrow.appendChild(th);
  });
  thead.appendChild(hrow); table.appendChild(thead);
  const afternoonSkip=new Array(7).fill(false), tbody=document.createElement('tbody');
  SHIFTS.forEach((shift,si)=>{
    const tr=document.createElement('tr'), lbl=document.createElement('td');
    lbl.className='shift-lbl';
    lbl.innerHTML=`<span class="sl-name">${shift.label}</span><span class="sl-hours">${shift.hours}</span>`;
    tr.appendChild(lbl);
    for(let col=0;col<7;col++){
      if(si===1&&afternoonSkip[col]) continue;
      const cell=(sched[shift.key]||[])[col]??null, td=document.createElement('td');
      if(!cell){
        td.className='sc sc-empty';
        td.innerHTML='<div class="sc-inner"><span class="sc-empty-lbl">Vago</span></div>';
      } else if(cell.fullDay&&si===0){
        td.className='sc sc-tall'+(cell.warn?' sc-warn':'');
        td.setAttribute('rowspan','2'); td.style.background=cell.color;
        if(cell.faded) td.style.opacity='0.45';
        td.innerHTML=`<div class="sc-inner">
          <span class="sc-name">${cell.name}</span>
          <span class="sc-sub">${cfg.lDay}</span>
          ${cell.badge?`<span class="sc-badge${cell.warn?' warn':''}">${cell.badge}</span>`:''}
        </div>`;
        afternoonSkip[col]=true;
      } else {
        td.className='sc'+(cell.warn?' sc-warn':'');
        td.style.background=cell.color;
        if(cell.faded) td.style.opacity='0.45';
        td.innerHTML=`<div class="sc-inner">
          <span class="sc-name">${cell.warn?'⚠ ':''}${cell.name}</span>
          ${cell.badge?`<span class="sc-badge${cell.warn?' warn':''}">${cell.badge}</span>`:''}
        </div>`;
      }
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
}

// ── CELL FACTORIES ────────────────────────────────────────────
const C_GIO='rgba(224,122,122,.82)',C_AND='rgba(80,144,224,.82)',C_GAB='rgba(78,200,148,.82)';
const C_FREE='rgba(212,168,75,.75)',C_NEW='rgba(144,96,208,.82)',C_FOLG='rgba(212,168,75,.92)';
const C_WARN='rgba(224,80,80,.85)', C_X='rgba(110,110,140,.65)';
const mk=(name,color,badge,warn,faded,fullDay)=>({name,color,badge:badge||null,warn:!!warn,faded:!!faded,fullDay:!!fullDay});
const GIO=(b,w)=>mk('Giovanna',  C_GIO,  b,w);
const AND=(b,w)=>mk('Anderson',  C_AND,  b,w);
const GAB=(b,w)=>mk('Gabriel',   w?C_WARN:C_GAB,b,w);
const FREE=b   =>mk('Freelancer',C_FREE, b);
const NEW=b    =>mk('T.Parcial', C_NEW,  b);
const FOLG=b   =>mk('Folguista', C_FOLG, b);
const GGIO=b   =>mk('Giovanna',  C_GIO,  b,false,false,true);
const GAND=b   =>mk('Anderson',  C_AND,  b,false,false,true);
const GNEW=b   =>mk('Novo 12×36',C_NEW,  b,false,false,true);
const GFDS_D=b =>mk('FDS Diurno',C_NEW,  b,false,false,true);
const FDS_N=b  =>mk('FDS Noturno',C_NEW, b);
const X_EMP=() =>mk('Func.X',   C_X,'saindo',false,true);
const NULL_C=null;
const GAB_A=[true,false,true,false,true,false,true]; // Dom,Ter,Qui,Sáb

// ── SCENARIOS ─────────────────────────────────────────────────
function getScenarios() {
  const atual={
    morning:  [NULL_C,GIO(),GIO(),GIO(),GIO(),GIO(),GIO()],
    afternoon:[NULL_C,AND(),AND(),AND(),AND(),AND(),AND()],
    night:    GAB_A.map(g=>g?GAB('12×36'):X_EMP()),
  };
  const s1={
    morning:  [FREE('FDS'),GIO(),GIO(),GIO(),GIO(),GIO(),FREE('FDS')],
    afternoon:[FREE('FDS'),AND(),AND(),AND(),AND(),AND(),FREE('FDS')],
    night:    GAB_A.map(g=>g?GAB('12×36'):FREE('gap')),
  };
  const s2={
    morning:  [GGIO('12×36'),GAND('12×36'),GGIO('12×36'),GAND('12×36'),GGIO('12×36'),GAND('12×36'),GAND('12×36')],
    afternoon:[NULL_C,NULL_C,NULL_C,NULL_C,NULL_C,NULL_C,NULL_C],
    night:    GAB_A.map(g=>g?GAB('12×36'):GNEW('12×36')),
  };
  const s3={
    morning:  [NULL_C,GIO(),GIO(),GIO(),GIO(),GIO(),GIO()],
    afternoon:[AND('rev'),AND(),AND(),AND(),AND(),AND(),NULL_C],
    night:    GAB_A.map(g=>g?GAB('12×36'):FREE('gap')),
  };
  const s4={
    morning:  [FREE('FDS'),GIO(),GIO(),GIO(),GIO(),GIO(),FREE('FDS')],
    afternoon:[FREE('FDS'),AND(),AND(),AND(),AND(),AND(),FREE('FDS')],
    night:[FREE('FDS'),GAB('⚠60h',true),GAB('⚠ilegal',true),GAB('⚠ilegal',true),GAB('⚠ilegal',true),GAB('⚠ilegal',true),FREE('FDS')],
  };
  const s5={
    morning:  [FREE('Dom'),GIO(),GIO(),GIO(),GIO(),GIO(),AND('banco h.')],
    afternoon:[FREE('Dom'),AND(),AND(),AND(),AND(),AND(),AND()],
    night:    GAB_A.map(g=>g?GAB('12×36'):FREE('gap')),
  };
  // F: FDS Diurno (Sáb 12h fullDay) + FDS Noturno (Sáb+Dom noite 12h each)
  const s6={
    morning:  [NULL_C,      GIO(),GIO(),GIO(),GIO(),GIO(), GFDS_D('Sáb·12h')],
    afternoon:[NULL_C,      AND(),AND(),AND(),AND(),AND(), NULL_C],// Sáb spanned by GFDS_D
    night:    GAB_A.map((g,i)=>{
      if(i===0) return FDS_N('Dom·12h'); // Dom noite
      if(i===6) return FDS_N('Sáb·12h'); // Sáb noite
      return g?GAB('12×36'):FREE('gap');
    }),
  };
  const sg={
    morning:  [NULL_C,    GIO(),GIO(),GIO(),GIO(),GIO(),FOLG('FDS')],
    afternoon:[FOLG('FDS'),AND(),AND(),AND(),AND(),AND(),AND()],
    night:    GAB_A.map(g=>g?GAB('12×36'):FREE('gap')),
  };

  const LEG_BASE=[
    {name:'Giovanna',color:C_GIO},{name:'Anderson',color:C_AND},
    {name:'Gabriel 12×36 (sem.A)',color:C_GAB},{name:'Freelancer',color:C_FREE},
  ];
  return {
    atual,s1,s2,s3,s4,s5,s6,sg, LEG_BASE,
    LEG_ATUAL:[...LEG_BASE,{name:'Func.X (saindo)',color:C_X}],
    LEG_S2:[{name:'Giovanna 12×36',color:C_GIO},{name:'Anderson 12×36',color:C_AND},{name:'Gabriel 12×36',color:C_GAB},{name:'Novo Noturno',color:C_NEW}],
    LEG_S4:[{name:'Giovanna',color:C_GIO},{name:'Anderson',color:C_AND},{name:'Gabriel ⚠ ILEGAL',color:C_WARN},{name:'Freelancer',color:C_FREE}],
    LEG_S6:[{name:'Giovanna 5×2',color:C_GIO},{name:'Anderson 5×2',color:C_AND},{name:'Gabriel 12×36',color:C_GAB},{name:'FDS Diurno (Sáb 12h)',color:C_NEW},{name:'FDS Noturno (Sáb+Dom 12h)',color:C_NEW},{name:'Freelancer gap',color:C_FREE}],
    LEG_SG:[{name:'Giovanna 5×2',color:C_GIO},{name:'Anderson 5×2',color:C_AND},{name:'Gabriel 12×36',color:C_GAB},{name:'Folguista',color:C_FOLG},{name:'Freelancer noite',color:C_FREE}],
  };
}

function renderGantts() {
  const sc=getScenarios();
  buildGantt('gantt-atual','leg-atual',sc.atual,{legend:sc.LEG_ATUAL});
  buildGantt('gantt-s1',  'leg-s1',   sc.s1,   {legend:sc.LEG_BASE});
  buildGantt('gantt-s2',  'leg-s2',   sc.s2,   {legend:sc.LEG_S2});
  buildGantt('gantt-s3',  'leg-s3',   sc.s3,   {legend:sc.LEG_BASE});
  buildGantt('gantt-s4',  'leg-s4',   sc.s4,   {legend:sc.LEG_S4});
  buildGantt('gantt-s5',  'leg-s5',   sc.s5,   {legend:sc.LEG_BASE});
  buildGantt('gantt-s6',  'leg-s6',   sc.s6,   {legend:sc.LEG_S6});
  buildGantt('gantt-sg',  'leg-sg',   sc.sg,   {legend:sc.LEG_SG});
}

function updateLabels() {
  const c=getCfg();
  setEl('lbl-gio-a',c.lMorn); setEl('lbl-and-a',c.lAft); setEl('lbl-gab-a',c.lNight);
  [['la-gio-s1',c.lMorn],['la-and-s1',c.lAft],['la-gab-s1',c.lNight],
   ['la-gio-s2',c.lDay], ['la-and-s2',c.lDay], ['la-gab-s2',c.lNight],['la-new-s2',c.lNight],
   ['la-gio-s3',c.lMorn],['la-and-s3',c.lAft], ['la-gab-s3',c.lNight],
   ['la-gio-s5',c.lMorn],['la-and-s5',c.lAft], ['la-gab-s5',c.lNight],
   ['la-gio-s6',c.lMorn],['la-and-s6',c.lAft], ['la-gab-s6',c.lNight],
   ['la-gio-sg',c.lMorn],['la-and-sg',c.lAft], ['la-gab-sg',c.lNight],
  ].forEach(([id,v])=>setEl(id,v));
}

function showTab(id) {
  document.querySelectorAll('.panel[id^="panel-s"]').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab-btn[id^="t-"]').forEach(b=>b.classList.remove('active'));
  $('panel-'+id)?.classList.add('active');
  $('t-'+id)?.classList.add('active');
}

// ── SALARY CARDS ──────────────────────────────────────────────
function buildSalaryCards(sal,enc) {
  const emps=[
    {name:'Giovanna',color:'var(--gio)',sal:sal.gio,regime:'6×1 CLT',      hePct:11.8,noturno:false},
    {name:'Anderson',color:'var(--and)',sal:sal.and,regime:'6×1 CLT',      hePct:11.8,noturno:false},
    {name:'Gabriel', color:'var(--gab)',sal:sal.gab,regime:'12×36 Noturno',hePct:0,   noturno:true },
  ];
  let cards='',rows='';
  emps.forEach(emp=>{
    const c=empCost(emp.sal,{hePct:emp.hePct,noturno:emp.noturno});
    cards+=`<div class="emp-card">
      <div class="emp-card-head"><div class="dot" style="background:${emp.color}"></div>
        <div><div style="font-weight:600;font-size:.88rem">${emp.name}</div>
        <div style="font-size:.72rem;color:var(--muted2)">${emp.regime}</div></div>
      </div>
      <div class="emp-card-body">
        <div class="calc-row"><span class="lbl">Salário base</span><span class="val">${fmt(c.base)}</span></div>
        ${c.adicHE>0?`<div class="calc-row"><span class="lbl">H. extras (~${emp.hePct}%)</span><span class="val">${fmt(c.adicHE)}</span></div>`:''}
        ${c.adicNot>0?`<div class="calc-row"><span class="lbl">Adic. noturno (${enc.not}%)</span><span class="val" style="color:var(--orange)">${fmt(c.adicNot)}</span></div>`:''}
        <div class="calc-row total"><span class="lbl">Salário bruto</span><span class="val">${fmt(c.gross)}</span></div>
        <div class="calc-row emp-cost"><span class="lbl">+ Encargos (${enc.emp.toFixed(1)}%)</span><span class="val">${fmt(c.encV)}</span></div>
        <div class="calc-row emp-cost"><span class="lbl">+ Provisões (${enc.prov.toFixed(2)}%)</span><span class="val">${fmt(c.provV)}</span></div>
        <div class="calc-row total"><span class="lbl">CUSTO TOTAL EMPREGADOR</span><span class="val">${fmt(c.total)}</span></div>
      </div></div>`;
    rows+=`<tr><td style="color:${emp.color};font-weight:600">${emp.name}</td><td>${emp.regime}</td>
      <td class="mono">${fmt(c.base)}</td><td class="mono" style="color:var(--orange)">${fmt(c.adicHE+c.adicNot)}</td>
      <td class="mono">${fmt(c.encV)}</td><td class="mono">${fmt(c.provV)}</td>
      <td class="mono" style="color:var(--gold2);font-weight:600">${fmt(c.total)}</td></tr>`;
  });
  const ce=$('emp-cards'), se=$('sal-summary');
  if(ce) ce.innerHTML=cards; if(se) se.innerHTML=rows;
}

// ── COMPARISON TABLE ──────────────────────────────────────────
function buildCmpTable(costs) {
  const rows=[
    {n:'0 · Atual',               fix:4,extra:'—',          dom:'❌',he:'Gio+And HE', c:costs.atual,clt:'⚠ HE',      risk:'Médio'},
    {n:'A · 5×2 + Freelancer',    fix:3,extra:'~32 diárias',dom:'✅',he:'Nenhuma',    c:costs.s1,   clt:'✅ (PJ⚠)', risk:'Baixo'},
    {n:'B · 12×36 Universal',     fix:4,extra:'—',          dom:'✅',he:'Nenhuma',    c:costs.s2,   clt:'✅ Perfeito',risk:'Mínimo'},
    {n:'C · Revezamento 6×1',     fix:3,extra:'~15 noites', dom:'✅',he:'BH Gio+And', c:costs.s3,   clt:'⚠ BH',    risk:'Baixo'},
    {n:'D · Gabriel Seg–Sex ⚠',   fix:3,extra:'~24 diárias',dom:'✅',he:'ILEGAL',     c:costs.s4,   clt:'🚨 ILEGAL',risk:'ALTO',worst:true},
    {n:'E · Misto ⭐',             fix:3,extra:'~21 diárias',dom:'✅',he:'And (BH)',   c:costs.s5,   clt:'✅ (BH⚠)',risk:'Baixo',rec:true},
    {n:'F · Intermediários 12h ⭐',fix:5,extra:'2 intermediários',dom:'✅',he:'Nenhuma',c:costs.s6,  clt:'✅ Perfeito',risk:'Mínimo',rec:true},
    {n:'G · Folguista ⭐',         fix:4,extra:'~12 noites', dom:'✅',he:'Folg. (BH)', c:costs.sg,   clt:'✅ (BH)',  risk:'Mínimo',rec:true},
  ];
  const totals=rows.map(r=>(r.c?.fix||0)+(r.c?.free||0));
  const minT=Math.min(...totals.filter((_,i)=>!rows[i].worst));
  const tbody=$('cmp-body'); if(!tbody) return;
  tbody.innerHTML=rows.map(r=>{
    const tot=(r.c?.fix||0)+(r.c?.free||0);
    return `<tr class="${r.rec?'rec':''}"><td><strong>${r.n}</strong></td>
      <td class="center mono">${r.fix}</td><td style="font-size:.78rem">${r.extra}</td>
      <td class="center">${r.dom}</td><td style="font-size:.78rem">${r.he}</td>
      <td class="mono">${fmt(r.c?.fix||0)}</td><td class="mono">${r.c?.free>0?fmt(r.c.free):'—'}</td>
      <td class="mono${tot===minT&&!r.worst?' best':''}${r.worst?' worst':''}">${fmt(tot)}</td>
      <td style="font-size:.78rem;text-align:center">${r.clt}</td>
      <td style="font-size:.78rem;text-align:center">${r.risk}</td></tr>`;
  }).join('');
}

// ── CONTRACTS TABLE ───────────────────────────────────────────
function buildContractsTable() {
  const sal=getSal(), enc=getEnc(), cfg=getCfg();
  const OVERHEAD=1+enc.total/100, notMult=1+enc.not/100, wDays=4.33*2;
  const dayDur=cfg.ns-cfg.ms;
  const fdsD=sal.fds*OVERHEAD, fdsN=sal.fds2*OVERHEAD*notMult;
  const rows=[
    {mod:`T.Parcial FDS Diurno — Sáb ${pad(cfg.ms)}–${pad(cfg.ns)}h`,art:'58-A+59-A',ok:'✅ Sim',custo:`${fmt(fdsD)}/mês · ${dayDur}h/sem`,fgts:'✅',res:'CLT prop.',risk:'low',rl:'BAIXO'},
    {mod:`T.Parcial FDS Noturno — Sáb+Dom ${pad(cfg.ns)}–${pad(cfg.ms)}h`,art:'58-A+59-A',ok:'✅ Sim',custo:`${fmt(fdsN)}/mês · ${cfg.nDur*2}h/sem`,fgts:'✅',res:'CLT + Adic.Not.',risk:'low',rl:'BAIXO'},
    {mod:'Intermitente (Art.452-A)',art:'Art.452-A',ok:'⚠ Pool≥3',custo:`${fmt(wDays*2*sal.int)}/mês est.`,fgts:'✅',res:'Por convocação',risk:'med',rl:'MÉDIO'},
    {mod:'Trabalho Temporário (Lei 6.019)',art:'Lei 6.019',ok:'✅ Sim',custo:`${fmt(wDays*2*sal.free*1.15)}/mês est.`,fgts:'✅',res:'Verbas rescisórias',risk:'low',rl:'BAIXO (270d)'},
    {mod:'Freelancer PJ/MEI',art:'—',ok:'⚠ Risco',custo:`${fmt(wDays*2*sal.free)}/mês est.`,fgts:'❌',res:'Sem verbas',risk:'high',rl:'ALTO (vínculo)'},
  ];
  const tbody=$('contracts-table'); if(!tbody) return;
  tbody.innerHTML=rows.map(r=>`<tr><td>${r.mod}</td><td class="mono" style="color:var(--blue2)">${r.art}</td>
    <td class="center">${r.ok}</td><td class="mono">${r.custo}</td>
    <td class="center">${r.fgts}</td><td>${r.res}</td>
    <td><span class="risk-pill risk-${r.risk}">${r.rl}</span></td></tr>`).join('');
}

// ── COVERAGE TABLE ────────────────────────────────────────────
function buildCoverageTable() {
  const sal=getSal(), freeN=sal.free*1.4;
  const rows=[
    {n:'0 · Atual',          gap_d:16,gap_n:42,note:'Dom descoberto'},
    {n:'A · 5×2+Freelancer', gap_d:0, gap_n:0, note:'Coberto c/ free.'},
    {n:'B · 12×36 Universal',gap_d:0, gap_n:0, note:'100% coberto'},
    {n:'C · Revezamento',    gap_d:0, gap_n:0, note:'Coberto c/ free.'},
    {n:'E · Misto ⭐',        gap_d:0, gap_n:0, note:'Dom: free.'},
    {n:'F · Interm. 12h ⭐',  gap_d:0, gap_n:0, note:'Coberto'},
    {n:'G · Folguista ⭐',    gap_d:0, gap_n:0, note:'Falta coberta'},
  ];
  const tbody=$('coverage-body'); if(!tbody) return;
  tbody.innerHTML=rows.map(r=>{
    const gapH=r.gap_d+r.gap_n, pct=Math.round((1-gapH/168)*100);
    const color=pct===100?'var(--green)':pct>80?'var(--gold2)':'var(--red)';
    const gapCost=r.gap_n*freeN;
    return `<tr><td>${r.n}</td>
      <td style="font-size:.78rem">${r.gap_d>0?r.gap_d+'h gap':'✅'}</td>
      <td style="font-size:.78rem">${r.gap_n>0?'~'+r.gap_n+'h gap':'✅'}</td>
      <td style="font-weight:600;color:${color}">${pct}% (${168-gapH}h)</td>
      <td class="mono${gapH>0?'" style="color:var(--red)':''">${gapH>0?gapH+'h':'—'}</td>
      <td class="mono${gapH>0?'" style="color:var(--red)':''">${gapH>0?Math.round(gapH*4.33)+'h':'—'}</td>
      <td class="mono${gapCost>0?'" style="color:var(--orange)':''">${gapCost>0?fmt(gapCost)+'/mês':r.note}</td></tr>`;
  }).join('');
}

// ── MAIN RECALC ───────────────────────────────────────────────
function recalcAll() {
  const sal=getSal(), enc=getEnc(), cfg=getCfg();
  const OVERHEAD=1+enc.total/100, NOT_MULT=1+enc.not/100, HE_PCT=11.8;
  setEl('enc-total-pct',enc.total.toFixed(1)+'%');

  const gioCost6x1=sal.gio*OVERHEAD*(1+HE_PCT/100), andCost6x1=sal.and*OVERHEAD*(1+HE_PCT/100);
  const gioCost5x2=sal.gio*OVERHEAD, andCost5x2=sal.and*OVERHEAD;
  const gabCost=sal.gab*OVERHEAD*NOT_MULT, newCost=sal.gab*OVERHEAD*NOT_MULT;
  const fDay=sal.free, fNight=sal.free*1.4;
  const folgCost=sal.folg*OVERHEAD*(1+HE_PCT/100);
  const fdsD=sal.fds*OVERHEAD, fdsN=sal.fds2*OVERHEAD*NOT_MULT;

  const s1Free=4.33*4*fDay+15*fNight, s3Free=15*fNight;
  const gabHE=sal.gab*OVERHEAD*NOT_MULT*1.36;
  const s4Free=4.33*4*fDay+8*fNight, s5Free=4.33*2*fDay+12*fNight;
  const s6GabGaps=8*fNight, sgFree=12*fNight;

  const set=(id,v)=>{const e=$(id);if(e)e.textContent=fmt(v);};

  set('c0-gio',gioCost6x1); set('c0-and',andCost6x1);
  set('c0-gab',gabCost);    set('c0-x',gabCost);
  set('c0-tot',gioCost6x1+andCost6x1+gabCost*2);

  set('c1-gio',gioCost5x2); set('c1-and',andCost5x2);
  set('c1-gab',gabCost);    set('c1-free',s1Free);
  set('c1-tot',gioCost5x2+andCost5x2+gabCost+s1Free);

  set('c2-gio',gioCost5x2); set('c2-and',andCost5x2);
  set('c2-gab',gabCost);    set('c2-new',newCost);
  set('c2-tot',gioCost5x2+andCost5x2+gabCost+newCost);
  setEl('s2-gab-noturno',fmt(sal.gab*(enc.not/100)));

  set('c3-gio',gioCost6x1); set('c3-and',andCost6x1);
  set('c3-gab',gabCost);    set('c3-free',s3Free);
  set('c3-tot',gioCost6x1+andCost6x1+gabCost+s3Free);

  set('c4-gio',gioCost5x2); set('c4-and',andCost5x2);
  set('c4-gab',gabHE);      set('c4-free',s4Free);
  set('c4-tot',gioCost5x2+andCost5x2+gabHE+s4Free);
  setEl('s4-he-cost',fmt(sal.gab*(enc.not/100+0.36)*OVERHEAD));

  set('c5-gio',gioCost5x2); set('c5-and',andCost6x1);
  set('c5-gab',gabCost);    set('c5-free',s5Free);
  set('c5-tot',gioCost5x2+andCost6x1+gabCost+s5Free);

  // S6 — Intermediários 12h FDS
  set('c6-gio',gioCost5x2);  set('c6-and',andCost5x2);
  set('c6-gab',gabCost);     set('c6-fds',fdsD+fdsN);
  set('c6-free',s6GabGaps);  set('c6-tot',gioCost5x2+andCost5x2+gabCost+fdsD+fdsN+s6GabGaps);

  // SG — Folguista
  const sgTotal=gioCost5x2+andCost5x2+gabCost+folgCost+sgFree;
  ['cg-gio','cg2-gio'].forEach(id=>set(id,gioCost5x2));
  ['cg-and','cg2-and'].forEach(id=>set(id,andCost5x2));
  ['cg-gab','cg2-gab'].forEach(id=>set(id,gabCost));
  ['cg-folg','cg2-folg'].forEach(id=>set(id,folgCost));
  ['cg-free','cg2-free'].forEach(id=>set(id,sgFree));
  ['cg-tot','cg2-tot'].forEach(id=>set(id,sgTotal));
  setEl('cmp-no-folg',fmt(sal.free*1.5)+'/evento');
  setFmt('cmp-atual',gioCost6x1+andCost6x1+gabCost*2);
  setFmt('cmp-e',    gioCost5x2+andCost6x1+gabCost+s5Free);

  // S6 CLT dynamic analysis
  const interj=cfg.ns-cfg.ms, nightNoctH=Math.max(0,Math.min(cfg.ms+24,29)-Math.max(cfg.ns,22));
  const intEl=$('s6-clt-analysis');
  if(intEl){
    const okI=interj>=11, okD=(cfg.ns-cfg.ms)<=30;
    intEl.innerHTML=`<div class="alert alert-${okI&&okD?'green':'warn'}" style="margin:0">
      <span>${okI&&okD?'✅':'⚠️'}</span>
      <div><strong>Análise para turnos ${pad(cfg.ms)}h/${pad(cfg.ns)}h:</strong><br>
      FDS Diurno: ${cfg.ns-cfg.ms}h/sem ≤ 30h — <strong>${okD?'✅ LEGAL':'⚠ REVISAR'}</strong> (Art.58-A+59-A)<br>
      FDS Noturno: ${cfg.nDur*2}h/sem ≤ 30h — <strong>✅ LEGAL</strong> (Art.58-A+59-A)<br>
      Interjornada Sáb→Dom noite: ${interj}h ${okI?'≥ 11h ✅':'— < 11h ⚠ ILEGAL · ajuste na configuração'} (Art.66)<br>
      Adic. noturno: ~${nightNoctH}h/turno × 20% obrigatório (Art.73) · Contrato escrito obrigatório.
      </div></div>`;
  }
  setEl('int-tp-sal',fmt(sal.fds));
  buildSalaryCards(sal,enc);
  buildCmpTable({
    atual:{fix:gioCost6x1+andCost6x1+gabCost*2,            free:0},
    s1:  {fix:gioCost5x2+andCost5x2+gabCost,               free:s1Free},
    s2:  {fix:gioCost5x2+andCost5x2+gabCost+newCost,       free:0},
    s3:  {fix:gioCost6x1+andCost6x1+gabCost,               free:s3Free},
    s4:  {fix:gioCost5x2+andCost5x2+gabHE,                 free:s4Free},
    s5:  {fix:gioCost5x2+andCost6x1+gabCost,               free:s5Free},
    s6:  {fix:gioCost5x2+andCost5x2+gabCost+fdsD+fdsN,     free:s6GabGaps},
    sg:  {fix:gioCost5x2+andCost5x2+gabCost+folgCost,      free:sgFree},
  });
  buildContractsTable();
  buildCoverageTable();
  updateLabels();
}

// ── INIT ──────────────────────────────────────────────────────
function init() {
  loadStoredConfig();
  syncConfigBar();
  setEl('gen-date',   new Date().toLocaleDateString('pt-BR'));
  setEl('footer-date',new Date().toLocaleDateString('pt-BR'));
  renderGantts();
  recalcAll();
}

document.addEventListener('DOMContentLoaded', init);
