#!/usr/bin/env python3
"""
대시보드 빌더
data/games.json + data/snapshots/*.json 을 읽어 완전 독립 dashboard.html 생성.
인터넷·서버 불필요 — 더블클릭으로 열림.

사용:
  python build_dashboard.py
  → dashboard.html 생성
"""

import glob
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
GAMES_JSON = os.path.join(ROOT, "data", "games.json")
SNAP_DIR = os.path.join(ROOT, "data", "snapshots")
WATCH_DATA = os.path.join(ROOT, "data", "watchlist_data.json")
OUT_HTML = os.path.join(ROOT, "dashboard.html")

TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Steam 시장 분석 — 개인 콕핏</title>
<style>
:root{
  --bg:#0E141B; --panel:#161F29; --panel-2:#1B2632; --line:#24303C;
  --txt:#C8D2DC; --dim:#7A8B99; --faint:#4A5866;
  --owners:#E8A33D; --review:#4FC3D9; --indie:#7BC96F; --price:#A78BDB; --neg:#D9705B;
  --radius:10px;
}
*{margin:0;padding:0;box-sizing:border-box}
html{font-size:15px}
body{
  background:var(--bg); color:var(--txt); min-height:100vh;
  font-family:'Segoe UI','Malgun Gothic','Apple SD Gothic Neo',system-ui,sans-serif;
  padding:28px clamp(16px,4vw,48px) 80px;
}
.num{font-family:ui-monospace,'Cascadia Mono',Consolas,monospace; font-variant-numeric:tabular-nums}
a{color:var(--review)}

/* ---- 헤더 ---- */
header{display:flex; align-items:baseline; gap:16px; flex-wrap:wrap; margin-bottom:6px}
h1{font-size:1.5rem; font-weight:700; letter-spacing:-.02em}
h1 em{font-style:normal; color:var(--owners)}
.meta{color:var(--dim); font-size:.8rem}
.tabs{display:flex; gap:4px; margin:18px 0 14px}
.tab{
  background:none; border:1px solid var(--line); color:var(--dim); cursor:pointer;
  padding:7px 18px; border-radius:8px 8px 0 0; border-bottom:none; font-size:.9rem;
}
.tab.on{background:var(--panel); color:var(--txt); font-weight:600}
.tab:focus-visible{outline:2px solid var(--review)}

/* ---- 분기 스펙트럼 (시그니처) ---- */
.spectrum-wrap{background:var(--panel); border:1px solid var(--line); border-radius:var(--radius); padding:14px 16px 10px; margin-bottom:16px}

/* ---- 태그 필터 ---- */
.tagfilter{background:var(--panel); border:1px solid var(--line); border-radius:var(--radius); padding:12px 16px; margin-bottom:16px; display:flex; align-items:center; gap:12px; flex-wrap:wrap}
.tagfilter label{font-size:.78rem; color:var(--dim); white-space:nowrap}
.tagfilter input{
  background:var(--panel-2); border:1px solid var(--line); color:var(--txt);
  border-radius:7px; padding:7px 12px; font-size:.85rem; width:240px; outline:none;
}
.tagfilter input:focus{border-color:var(--review)}
.chips{display:flex; gap:6px; flex-wrap:wrap}
.chip{
  background:var(--panel-2); border:1px solid var(--line); color:var(--dim);
  border-radius:99px; padding:4px 12px; font-size:.76rem; cursor:pointer;
}
.chip:hover{color:var(--txt)}
.chip.on{background:var(--review); color:#0E141B; border-color:var(--review); font-weight:600}
.tag-hits{font-size:.76rem; color:var(--review); margin-left:auto}
.spectrum-head{display:flex; justify-content:space-between; align-items:baseline; margin-bottom:8px}
.spectrum-head .lbl{font-size:.78rem; color:var(--dim)}
.spectrum-head .sel{font-size:.85rem; color:var(--owners); font-weight:600}
.spectrum{display:flex; gap:2px; align-items:flex-end; height:56px; overflow-x:auto; padding-bottom:4px}
.qcell{
  flex:1 0 9px; min-width:9px; border-radius:2px 2px 0 0; cursor:pointer; position:relative;
  background:var(--faint); transition:filter .1s;
}
.qcell:hover{filter:brightness(1.5)}
.qcell.sel{outline:2px solid var(--owners)}
.qcell:focus-visible{outline:2px solid var(--review)}
.spectrum-axis{display:flex; justify-content:space-between; color:var(--faint); font-size:.68rem; margin-top:4px}
.clear-btn{background:none;border:1px solid var(--line);color:var(--dim);border-radius:6px;padding:2px 10px;font-size:.75rem;cursor:pointer}
.clear-btn:hover{color:var(--txt)}

/* ---- KPI ---- */
.kpis{display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:10px; margin-bottom:16px}
.kpi{background:var(--panel); border:1px solid var(--line); border-radius:var(--radius); padding:14px 16px}
.kpi .v{font-size:1.45rem; font-weight:700}
.kpi .k{font-size:.75rem; color:var(--dim); margin-top:2px}
.kpi.owners .v{color:var(--owners)} .kpi.review .v{color:var(--review)}
.kpi.indie .v{color:var(--indie)} .kpi.price .v{color:var(--price)}

/* ---- 패널 그리드 ---- */
.grid{display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-bottom:14px}
@media(max-width:900px){.grid{grid-template-columns:1fr}}
.panel{background:var(--panel); border:1px solid var(--line); border-radius:var(--radius); padding:16px 18px}
.panel h2{font-size:.95rem; font-weight:600; margin-bottom:2px}
.panel .sub{font-size:.74rem; color:var(--dim); margin-bottom:12px}

/* ---- 바 차트 ---- */
.bar-row{display:grid; grid-template-columns:130px 1fr 74px; gap:10px; align-items:center; padding:3.5px 0; font-size:.83rem}
.bar-row .name{white-space:nowrap; overflow:hidden; text-overflow:ellipsis; color:var(--txt)}
.bar-track{background:var(--panel-2); border-radius:4px; height:14px; overflow:hidden}
.bar-fill{height:100%; border-radius:4px}
.bar-row .val{text-align:right; color:var(--dim); font-size:.78rem}

/* ---- 분할 바 (인디 vs 대형) ---- */
.split{display:flex; height:26px; border-radius:6px; overflow:hidden; margin:8px 0 6px}
.split div{display:flex;align-items:center;justify-content:center;font-size:.75rem;font-weight:600;color:#0E141B}
.legend{display:flex; gap:16px; font-size:.76rem; color:var(--dim); flex-wrap:wrap}
.dot{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;vertical-align:baseline}

/* ---- 테이블 ---- */
table{width:100%; border-collapse:collapse; font-size:.82rem}
th,td{padding:7px 10px; text-align:right; border-bottom:1px solid var(--line)}
th{color:var(--dim); font-weight:600; cursor:pointer; user-select:none; white-space:nowrap; position:sticky; top:0; background:var(--panel)}
th:hover{color:var(--txt)}
th.sorted{color:var(--owners)}
td:first-child,th:first-child{text-align:left}
td.name{max-width:260px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap}
td .tag{color:var(--faint); font-size:.72rem}
tr:hover td{background:var(--panel-2)}
.pos{color:var(--indie)} .mid{color:var(--owners)} .low{color:var(--neg)}
.table-wrap{max-height:520px; overflow:auto; border-radius:6px}
.count-note{font-size:.75rem;color:var(--dim);margin-top:8px}

/* ---- 스냅샷 빈 상태 ---- */
.empty{border:1px dashed var(--line); border-radius:var(--radius); padding:34px; text-align:center; color:var(--dim); line-height:1.9}
.empty code{background:var(--panel-2); padding:2px 8px; border-radius:5px; color:var(--review); font-size:.85em}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
</head>
<body>
<header>
  <h1>Steam 시장 분석 <em>· 개인 콕핏</em></h1>
  <span class="meta" id="meta"></span>
</header>

<div class="tabs" role="tablist">
  <button class="tab on" id="tab-retro" role="tab" onclick="showTab('retro')">출시 분기 회고</button>
  <button class="tab" id="tab-snap" role="tab" onclick="showTab('snap')">분기 스냅샷 트렌드</button>
</div>

<!-- ============ 회고 탭 ============ -->
<div id="view-retro">
  <div class="tagfilter">
    <label for="tag-input">태그 필터</label>
    <input id="tag-input" type="text" placeholder="예: Horror, Hide &amp; Seek" oninput="setTagQuery(this.value)">
    <div class="chips" id="tag-chips"></div>
    <span class="tag-hits" id="tag-hits"></span>
  </div>

  <div class="spectrum-wrap">
    <div class="spectrum-head">
      <span class="lbl">출시 분기 스펙트럼 — 셀 높이·색 = 해당 분기 출시작 수 (클릭 필터)</span>
      <span><span class="sel" id="sel-q">전체 분기</span> <button class="clear-btn" id="clear-q" style="display:none" onclick="selectQuarter(null)">해제</button></span>
    </div>
    <div class="spectrum" id="spectrum"></div>
    <div class="spectrum-axis" id="spectrum-axis"></div>
  </div>

  <div class="kpis" id="kpis"></div>

  <div class="grid">
    <div class="panel">
      <h2>장르별 소유자 규모</h2>
      <div class="sub">Steam 스토어 장르 × 소유자 추정 중간값 합 — 시장 크기 감각</div>
      <div id="genre-bars"></div>
    </div>
    <div class="panel">
      <h2>태그 Top 15 (투표 가중)</h2>
      <div class="sub">각 게임 상위 3개 태그 × 소유자 가중 — 실제 수요 어휘</div>
      <div id="tag-bars"></div>
    </div>
  </div>

  <div class="grid">
    <div class="panel">
      <h2>인디 vs 대형</h2>
      <div class="sub">판정: 장르에 Indie 포함 또는 개발=퍼블리셔 소규모</div>
      <div id="indie-split"></div>
    </div>
    <div class="panel">
      <h2>가격대 분포</h2>
      <div class="sub">현재가 기준 게임 수</div>
      <div id="price-bars"></div>
    </div>
  </div>

  <div class="panel" id="watch-panel" style="margin-bottom:14px">
    <h2>워치리스트 <span style="color:var(--dim);font-weight:400;font-size:.78rem">— Steam 공식 API 직접 조회 (SteamSpy 사각지대 우회)</span></h2>
    <div class="sub" id="watch-sub"></div>
    <div class="table-wrap"><table id="watch-table"></table></div>
    <div class="count-note">추가/제거: <code style="color:var(--review)">python watch.py --add [appid]</code> 후 <code style="color:var(--review)">python build_dashboard.py</code></div>
  </div>

  <div class="panel">
    <h2>게임 목록</h2>
    <div class="sub">헤더 클릭으로 정렬 — 긍정률 = positive / (positive+negative)</div>
    <div class="table-wrap"><table id="game-table"></table></div>
    <div class="count-note" id="table-note"></div>
  </div>
</div>

<!-- ============ 스냅샷 탭 ============ -->
<div id="view-snap" style="display:none">
  <div id="snap-content"></div>
</div>

<script>
const DATA = /*__GAMES__*/;
const SNAPSHOTS = /*__SNAPSHOTS__*/;
const WATCH = /*__WATCH__*/;

/* ---------- 유틸 ---------- */
const fmt = n => n>=1e8 ? (n/1e8).toFixed(1)+'억' : n>=1e4 ? (n/1e4).toFixed(1)+'만' : n.toLocaleString();
const esc = s => String(s??'').replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const posRate = g => { const t=g.positive+g.negative; return t? g.positive/t : 0; };
const isIndie = g => (g.genre||'').includes('Indie') ||
  (g.developer && g.developer===g.publisher && g.owners_mid < 20_000_000);

let selectedQ = null;
let tagQuery = '';
let sortKey = 'owners_mid', sortDesc = true;

const games = DATA.games.filter(g => g.type !== 'dlc');
const PRESETS = ['Horror','Survival Horror','Hide & Seek','Stealth','Multiplayer','Co-op','Roguelike'];

function matchTag(g){
  if(!tagQuery) return true;
  const q = tagQuery.toLowerCase();
  return Object.keys(g.tags||{}).some(t => t.toLowerCase().includes(q));
}
const view = () => games.filter(g =>
  (!selectedQ || g.release_quarter===selectedQ) && matchTag(g));

function setTagQuery(q){
  tagQuery = (q||'').trim();
  document.getElementById('tag-input').value = tagQuery;
  renderChips(); renderHits(); buildSpectrum(); renderAll();
}
function toggleChip(p){ setTagQuery(p.toLowerCase()===tagQuery.toLowerCase() ? '' : p); }
function renderChips(){
  document.getElementById('tag-chips').innerHTML = PRESETS.map(p=>
    `<button class="chip${p.toLowerCase()===tagQuery.toLowerCase()?' on':''}"
      onclick="toggleChip('${p.replace(/'/g,"\\'")}')">${p}</button>`).join('');
}
function renderHits(){
  const el = document.getElementById('tag-hits');
  if(!tagQuery){ el.textContent=''; return; }
  const n = games.filter(matchTag).length;
  el.textContent = `"${tagQuery}" 태그 보유: ${n}개 / ${games.length}`;
}

/* ---------- 분기 스펙트럼 ---------- */
function buildSpectrum(){
  const counts = {};
  games.filter(matchTag).forEach(g => { if(g.release_quarter) counts[g.release_quarter]=(counts[g.release_quarter]||0)+1; });
  const qs = Object.keys(counts).sort();
  if(!qs.length){
    document.getElementById('spectrum').innerHTML =
      '<span style="color:var(--faint);font-size:.78rem;align-self:center">매칭 게임 없음</span>';
    document.getElementById('spectrum-axis').innerHTML = '';
    return;
  }
  const [y0] = qs[0].split('-'), [y1] = qs[qs.length-1].split('-');
  // 첫~마지막 분기 사이 전체 연속 분기 생성
  const all = [];
  for(let y=+y0; y<=+y1; y++) for(let q=1;q<=4;q++){
    const key = `${y}-Q${q}`;
    if(key>=qs[0] && key<=qs[qs.length-1]) all.push(key);
  }
  const max = Math.max(...Object.values(counts));
  const el = document.getElementById('spectrum');
  el.innerHTML = all.map(q=>{
    const c = counts[q]||0;
    const h = c? Math.max(14, c/max*100) : 6;
    const alpha = c? .35 + .65*(c/max) : .12;
    return `<div class="qcell${q===selectedQ?' sel':''}" tabindex="0" role="button"
      style="height:${h}%;background:rgba(232,163,61,${alpha})"
      title="${q} · ${c}개 출시" onclick="selectQuarter('${q}')"
      onkeydown="if(event.key==='Enter')selectQuarter('${q}')"></div>`;
  }).join('');
  document.getElementById('spectrum-axis').innerHTML =
    `<span>${qs[0]}</span><span>${qs[qs.length-1]}</span>`;
}
function selectQuarter(q){
  selectedQ = (q===selectedQ)? null : q;
  document.getElementById('sel-q').textContent = selectedQ || '전체 분기';
  document.getElementById('clear-q').style.display = selectedQ? '' : 'none';
  buildSpectrum(); renderAll();
}

/* ---------- KPI ---------- */
function renderKPIs(){
  const v = view();
  const totOwners = v.reduce((s,g)=>s+g.owners_mid,0);
  const avgPos = v.length? v.reduce((s,g)=>s+posRate(g),0)/v.length : 0;
  const indieN = v.filter(isIndie).length;
  const paid = v.filter(g=>!g.is_free && g.price_cents>0);
  const medPrice = paid.length? paid.map(g=>g.price_cents).sort((a,b)=>a-b)[Math.floor(paid.length/2)]/100 : 0;
  document.getElementById('kpis').innerHTML = `
    <div class="kpi"><div class="v num">${v.length}</div><div class="k">게임 수 ${selectedQ? '('+selectedQ+' 출시)':''}</div></div>
    <div class="kpi owners"><div class="v num">${fmt(totOwners)}</div><div class="k">소유자 추정 합 (중간값)</div></div>
    <div class="kpi review"><div class="v num">${(avgPos*100).toFixed(1)}%</div><div class="k">평균 긍정 리뷰율</div></div>
    <div class="kpi indie"><div class="v num">${indieN} <span style="font-size:.8rem;color:var(--dim)">/ ${v.length}</span></div><div class="k">인디 판정 게임</div></div>
    <div class="kpi price"><div class="v num">$${medPrice.toFixed(2)}</div><div class="k">유료 게임 중위가</div></div>`;
}

/* ---------- 바 차트 공용 ---------- */
function bars(el, rows, color, valFmt){
  const max = Math.max(...rows.map(r=>r[1]), 1);
  document.getElementById(el).innerHTML = rows.map(([name,val])=>`
    <div class="bar-row">
      <span class="name" title="${esc(name)}">${esc(name)}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${val/max*100}%;background:${color}"></div></div>
      <span class="val num">${valFmt(val)}</span>
    </div>`).join('');
}

function renderGenres(){
  const acc = {};
  view().forEach(g => (g.genre||'').split(',').map(s=>s.trim()).filter(Boolean)
    .forEach(gen => acc[gen]=(acc[gen]||0)+g.owners_mid));
  const rows = Object.entries(acc).sort((a,b)=>b[1]-a[1]).slice(0,12);
  bars('genre-bars', rows, 'var(--owners)', fmt);
}
function renderTags(){
  const acc = {};
  view().forEach(g=>{
    const t = g.tags||{}; 
    Object.keys(t).sort((a,b)=>t[b]-t[a]).slice(0,3)
      .forEach(tag => acc[tag]=(acc[tag]||0)+g.owners_mid);
  });
  const rows = Object.entries(acc).sort((a,b)=>b[1]-a[1]).slice(0,15);
  bars('tag-bars', rows, 'var(--review)', fmt);
}
function renderIndie(){
  const v = view();
  const ind = v.filter(isIndie), maj = v.filter(g=>!isIndie(g));
  const iOwn = ind.reduce((s,g)=>s+g.owners_mid,0), mOwn = maj.reduce((s,g)=>s+g.owners_mid,0);
  const tot = iOwn+mOwn || 1;
  const iPos = ind.length? ind.reduce((s,g)=>s+posRate(g),0)/ind.length : 0;
  const mPos = maj.length? maj.reduce((s,g)=>s+posRate(g),0)/maj.length : 0;
  document.getElementById('indie-split').innerHTML = `
    <div class="split">
      <div style="width:${iOwn/tot*100}%;background:var(--indie)">${(iOwn/tot*100).toFixed(0)}%</div>
      <div style="width:${mOwn/tot*100}%;background:var(--price)">${(mOwn/tot*100).toFixed(0)}%</div>
    </div>
    <div class="legend">
      <span><span class="dot" style="background:var(--indie)"></span>인디 ${ind.length}개 · 소유자 ${fmt(iOwn)} · 긍정률 ${(iPos*100).toFixed(1)}%</span>
      <span><span class="dot" style="background:var(--price)"></span>대형 ${maj.length}개 · 소유자 ${fmt(mOwn)} · 긍정률 ${(mPos*100).toFixed(1)}%</span>
    </div>`;
}
function renderPrices(){
  const buckets = [['무료',0,0],['~$5',1,500],['$5~15',501,1500],['$15~30',1501,3000],['$30~60',3001,6000],['$60+',6001,1e9]];
  const acc = buckets.map(([lbl,lo,hi]) =>
    [lbl, view().filter(g => g.is_free||g.price_cents===0 ? lo===0 : g.price_cents>=lo && g.price_cents<=hi).length]);
  bars('price-bars', acc, 'var(--price)', n=>n+'개');
}

/* ---------- 테이블 ---------- */
const COLS = [
  ['name','게임',g=>`<td class="name" title="${esc(g.name)}">${esc(g.name)}<br><span class="tag">${esc(g.top_tag||'')}</span></td>`],
  ['release_quarter','출시',g=>`<td class="num">${g.release_quarter||'-'}</td>`],
  ['owners_mid','소유자',g=>`<td class="num">${fmt(g.owners_mid)}</td>`],
  ['ccu','CCU',g=>`<td class="num">${fmt(g.ccu)}</td>`],
  ['posrate','긍정률',g=>{const r=posRate(g);const c=r>=.85?'pos':r>=.7?'mid':'low';return `<td class="num ${c}">${(r*100).toFixed(1)}%</td>`}],
  ['price_cents','가격',g=>`<td class="num">${g.is_free||!g.price_cents?'무료':'$'+(g.price_cents/100).toFixed(2)}</td>`],
  ['indie','구분',g=>`<td>${isIndie(g)?'<span class="pos">인디</span>':'<span style="color:var(--dim)">대형</span>'}</td>`],
];
function sortVal(g,k){ return k==='posrate'? posRate(g) : k==='indie'? +isIndie(g) : k==='name'? g.name : k==='release_quarter'? (g.release_quarter||'') : (g[k]||0); }
function renderTable(){
  const rows = [...view()].sort((a,b)=>{
    const x=sortVal(a,sortKey), y=sortVal(b,sortKey);
    return (x<y?-1:x>y?1:0) * (sortDesc?-1:1);
  });
  const head = '<tr>'+COLS.map(([k,lbl])=>
    `<th class="${k===sortKey?'sorted':''}" onclick="setSort('${k}')">${lbl}${k===sortKey?(sortDesc?' ▾':' ▴'):''}</th>`).join('')+'</tr>';
  document.getElementById('game-table').innerHTML =
    head + rows.map(g=>'<tr>'+COLS.map(([,,fn])=>fn(g)).join('')+'</tr>').join('');
  document.getElementById('table-note').textContent = `${rows.length}개 표시${selectedQ? ' · '+selectedQ+' 출시작만' : ''}`;
}
function setSort(k){ if(k===sortKey) sortDesc=!sortDesc; else {sortKey=k; sortDesc=true;} renderTable(); }

/* ---------- 스냅샷 탭 ---------- */
function renderSnapshots(){
  const el = document.getElementById('snap-content');
  const snaps = SNAPSHOTS.slice().sort((a,b)=>a.quarter<b.quarter?-1:1);
  if(snaps.length < 2){
    el.innerHTML = `<div class="empty">
      스냅샷이 ${snaps.length}개 있습니다. 트렌드 비교에는 최소 2개 분기가 필요합니다.<br>
      분기마다 <code>python collect.py</code> 후 <code>python snapshot.py</code> 실행<br>
      → <code>python build_dashboard.py</code> 로 이 파일을 다시 생성하면 여기에 시계열이 쌓입니다.</div>`;
    return;
  }
  // 태그별 소유자 변화: 최신 vs 직전
  const prev = snaps[snaps.length-2], cur = snaps[snaps.length-1];
  const keys = new Set([...Object.keys(cur.tag_owners||{}), ...Object.keys(prev.tag_owners||{})]);
  const deltas = [...keys].map(k=>{
    const a = (prev.tag_owners||{})[k]||0, b = (cur.tag_owners||{})[k]||0;
    return [k, b-a, b];
  }).filter(d=>d[2]>0).sort((x,y)=>y[1]-x[1]);
  const up = deltas.slice(0,10), down = deltas.slice(-10).reverse();
  const row = ([k,d]) => `
    <div class="bar-row"><span class="name" title="${esc(k)}">${esc(k)}</span>
    <div class="bar-track"><div class="bar-fill" style="width:${Math.min(100,Math.abs(d)/Math.max(1,Math.abs(deltas[0][1]))*100)}%;background:${d>=0?'var(--indie)':'var(--neg)'}"></div></div>
    <span class="val num">${d>=0?'+':''}${fmt(Math.abs(d))}</span></div>`;
  el.innerHTML = `
    <div class="grid">
      <div class="panel"><h2>상승 태그</h2><div class="sub">${prev.quarter} → ${cur.quarter} 소유자 증가</div>${up.map(row).join('')}</div>
      <div class="panel"><h2>하락 태그</h2><div class="sub">${prev.quarter} → ${cur.quarter} 소유자 감소</div>${down.map(row).join('')}</div>
    </div>
    <div class="count-note">축적된 스냅샷: ${snaps.map(s=>s.quarter).join(' · ')}</div>`;
}

/* ---------- 워치리스트 ---------- */
function renderWatch(){
  const panel = document.getElementById('watch-panel');
  const ents = (WATCH.entries||[]);
  if(!ents.length){ panel.style.display='none'; return; }
  document.getElementById('watch-sub').textContent =
    `갱신 ${new Date(WATCH.updated_at).toLocaleString('ko-KR')} — 리뷰수 x30~50 = 판매량 대략 추정(업계 관례)`;
  const head = '<tr><th>게임</th><th>출시</th><th>가격</th><th>CCU(실시간)</th><th>리뷰</th><th>긍정률</th><th>판매 추정</th><th>리뷰 증가</th></tr>';
  const rows = ents.map(e=>{
    const tot = e.total_reviews||0, pos = e.positive||0;
    const rate = tot? pos/tot : 0;
    const rc = rate>=.85?'pos':rate>=.7?'mid':'low';
    const est = tot? fmt(tot*30)+'~'+fmt(tot*50) : '-';
    // 이력 마지막 2개로 리뷰 증가량
    let delta = '-';
    const h = e.history||[];
    if(h.length>=2){
      const d = h[h.length-1].total_reviews - h[h.length-2].total_reviews;
      delta = (d>=0?'+':'')+fmt(Math.abs(d));
    }
    return `<tr>
      <td class="name" title="${esc(e.name)}">${esc(e.name)}<br><span class="tag">${esc((e.genres||[]).join(', '))}</span></td>
      <td class="num">${e.release_quarter||'-'}</td>
      <td class="num">${e.is_free?'무료':(e.price_cents?'$'+(e.price_cents/100).toFixed(2):'-')}</td>
      <td class="num">${fmt(e.ccu||0)}</td>
      <td class="num">${fmt(tot)}</td>
      <td class="num ${rc}">${(rate*100).toFixed(1)}%</td>
      <td class="num">${est}</td>
      <td class="num">${delta}</td></tr>`;
  }).join('');
  document.getElementById('watch-table').innerHTML = head + rows;
}

/* ---------- 탭 ---------- */
function showTab(t){
  document.getElementById('view-retro').style.display = t==='retro'?'':'none';
  document.getElementById('view-snap').style.display  = t==='snap'?'':'none';
  document.getElementById('tab-retro').classList.toggle('on', t==='retro');
  document.getElementById('tab-snap').classList.toggle('on', t==='snap');
}

/* ---------- 초기화 ---------- */
function renderAll(){ renderKPIs(); renderGenres(); renderTags(); renderIndie(); renderPrices(); renderTable(); }
document.getElementById('meta').textContent =
  `수집 ${new Date(DATA.collected_at).toLocaleString('ko-KR')} · ${DATA.count}개 · ${DATA.source}`;
renderChips(); buildSpectrum(); renderAll(); renderSnapshots(); renderWatch();
</script>
</body>
</html>
"""


def main():
    if not os.path.exists(GAMES_JSON):
        print("games.json 없음 → 먼저 collect.py 실행")
        return
    with open(GAMES_JSON, "r", encoding="utf-8") as f:
        games = f.read()

    snaps = []
    for p in sorted(glob.glob(os.path.join(SNAP_DIR, "*.json"))):
        with open(p, "r", encoding="utf-8") as f:
            snaps.append(json.load(f))

    watch = {"entries": []}
    if os.path.exists(WATCH_DATA):
        with open(WATCH_DATA, "r", encoding="utf-8") as f:
            watch = json.load(f)

    html = (TEMPLATE.replace("/*__GAMES__*/", games)
        .replace("/*__SNAPSHOTS__*/", json.dumps(snaps, ensure_ascii=False))
        .replace("/*__WATCH__*/", json.dumps(watch, ensure_ascii=False)))
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"생성 → {OUT_HTML} ({len(html)//1024}KB, 스냅샷 {len(snaps)}개 포함)")


if __name__ == "__main__":
    main()
