"""
report.py — 生成最终 HTML 报告（双栏对比 + 热力图版）
"""

import json as _json
import os
from datetime import datetime
from typing import Optional


# ── CSS ──────────────────────────────────────────────────────────────────────

_CSS = """
/* ── Design Tokens ─────────────────────────────────── */
:root {
  /* Colors: OKLCH for perceptual uniformity */
  --pg:        oklch(93.5% 0.022 55);    /* warm sand page bg */
  --surface:   oklch(98.5% 0.008 52);    /* card surface */
  --surface-2: oklch(96%   0.018 54);    /* secondary fills */

  --br-900: oklch(32%  0.085 48);   /* darkest brown */
  --br-700: oklch(44%  0.095 49);   /* primary accent */
  --br-500: oklch(58%  0.105 51);   /* medium brown */
  --br-300: oklch(74%  0.085 53);   /* light brown */
  --br-100: oklch(91%  0.042 55);   /* pale border */
  --br-050: oklch(96%  0.022 55);   /* near-white warm */

  --tl-800: oklch(40%  0.075 174);  /* dark teal */
  --tl-500: oklch(58%  0.085 175);  /* medium teal */
  --tl-200: oklch(83%  0.055 175);  /* pale teal */
  --tl-050: oklch(95%  0.028 175);  /* teal near-white */

  --tx-900: oklch(22%  0.025 48);   /* near-black, warm */
  --tx-600: oklch(46%  0.030 48);   /* mid text */
  --tx-400: oklch(63%  0.022 50);   /* subtle text */

  --sh-sm: 0 1px 4px oklch(32% 0.085 48 / .07);
  --sh-md: 0 4px 18px oklch(32% 0.085 48 / .10);

  --r-sm: 8px;  --r-md: 14px;  --r-lg: 20px;  --r-xl: 28px;
  --ease-expo: cubic-bezier(0.16, 1, 0.3, 1);

  --ff-display: 'Songti SC', 'STSong', 'SimSun', Georgia, 'Times New Roman', serif;
  --ff-body:    'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', system-ui, sans-serif;
}

/* ── Animations ────────────────────────────────────── */
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(18px); }
}
@keyframes growX {
  from { transform: scaleX(0); }
}

.header, .stats, .section {
  animation: fadeUp 560ms var(--ease-expo) both;
  animation-delay: calc(var(--i, 0) * 65ms);
}
.bar-fill, .bf-fill-self, .bf-fill-partner {
  animation: growX 750ms var(--ease-expo) both;
  animation-delay: calc(300ms + var(--bi, 0) * 40ms);
}
.bf-fill-self    { transform-origin: right center; }
.bf-fill-partner { transform-origin: left center; }
.bar-fill        { transform-origin: left center; }

@media (prefers-reduced-motion: reduce) {
  .header, .stats, .section,
  .bar-fill, .bf-fill-self, .bf-fill-partner {
    animation: none;
  }
}

/* ── Reset & Base ──────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
blockquote { quotes: none; }
img        { max-width: 100%; }

body {
  font-family: var(--ff-body);
  background: var(--pg);
  color: var(--tx-900);
  line-height: 1.6;
  font-kerning: normal;
  padding: clamp(14px, 3vw, 32px) clamp(10px, 2.5vw, 20px);
  min-height: 100vh;
}
.container {
  max-width: 960px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* ── Header ────────────────────────────────────────── */
.header {
  background: var(--br-900);
  border-radius: var(--r-xl);
  padding: clamp(28px, 5vw, 52px) clamp(22px, 4vw, 48px);
  color: #fff;
  text-align: center;
  position: relative;
  overflow: hidden;
}
.header::before {
  content: ''; position: absolute; inset: 0;
  background: repeating-linear-gradient(
    -45deg,
    transparent, transparent 32px,
    oklch(100% 0 0 / .022) 32px,
    oklch(100% 0 0 / .022) 33px
  );
  pointer-events: none;
}
.header::after {
  content: ''; position: absolute;
  bottom: 0; left: 0; right: 0; height: 55%;
  background: linear-gradient(to bottom, transparent, oklch(28% 0.07 48 / .2));
  pointer-events: none;
}
.header h1 {
  font-family: var(--ff-display);
  font-size: clamp(1.45rem, 4.5vw, 2.1rem);
  font-weight: 700; letter-spacing: .04em;
  margin-bottom: 7px;
  position: relative; z-index: 1;
}
.header-meta {
  opacity: .58; font-size: .84em; letter-spacing: .03em;
  position: relative; z-index: 1;
}
.header-vs {
  display: flex; align-items: center; justify-content: center;
  gap: 14px; margin-top: 20px;
  position: relative; z-index: 1;
}
.vs-divider { font-size: .9em; opacity: .38; font-weight: 200; letter-spacing: .2em; }
.person-pill {
  display: inline-flex; align-items: center; gap: 8px;
  background: oklch(100% 0 0 / .11);
  border: 1px solid oklch(100% 0 0 / .18);
  border-radius: 50px;
  padding: 5px 15px 5px 5px;
}
.av {
  width: 38px; height: 38px; border-radius: 50%;
  overflow: hidden; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; font-weight: 700;
  border: 2px solid oklch(100% 0 0 / .3);
}
.av img { width: 100%; height: 100%; object-fit: cover; display: block; }
.av-self    { background: linear-gradient(135deg, var(--br-700), var(--br-300)); color: #fff; }
.av-partner { background: linear-gradient(135deg, var(--tl-800), var(--tl-500)); color: #fff; }
.pill-name  { font-size: .88em; font-weight: 600; color: #fff; }

/* ── Stats ─────────────────────────────────────────── */
.stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.stat {
  background: var(--surface);
  border-radius: var(--r-md);
  padding: 22px 14px 20px;
  text-align: center;
  box-shadow: var(--sh-sm);
  position: relative;
}
.stat::after {
  content: '';
  position: absolute; bottom: 0; left: 50%;
  transform: translateX(-50%);
  width: 40px; height: 3px;
  background: linear-gradient(90deg, var(--br-500), var(--br-300));
  border-radius: 2px 2px 0 0;
}
.stat-num {
  font-family: var(--ff-display);
  font-size: clamp(1.5rem, 3.5vw, 2.1rem);
  font-weight: 700;
  color: var(--br-700);
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.stat-lbl { color: var(--tx-400); font-size: .78em; margin-top: 7px; }

/* ── Section ───────────────────────────────────────── */
.section {
  background: var(--surface);
  border-radius: var(--r-lg);
  padding: clamp(18px, 3.5vw, 28px);
  box-shadow: var(--sh-sm);
}
.section-title {
  font-family: var(--ff-display);
  font-size: 1.02em; font-weight: 700;
  color: var(--br-900); letter-spacing: .04em;
  display: flex; align-items: center; gap: 9px;
  padding-bottom: 14px; margin-bottom: 18px;
  border-bottom: 1.5px solid var(--br-100);
}

/* ── Charts ────────────────────────────────────────── */
.chart-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.chart-grid img {
  width: 100%; border-radius: var(--r-sm); display: block;
  transition: transform 200ms var(--ease-expo), box-shadow 200ms;
}
.chart-grid img:hover { transform: translateY(-2px); box-shadow: var(--sh-md); }
.chart-full { width: 100%; border-radius: var(--r-sm); display: block; }

/* ── Tags ──────────────────────────────────────────── */
.tag-self, .tag-partner {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 3px 10px 3px 4px;
  border-radius: 20px; font-size: .79em; font-weight: 600;
  white-space: nowrap; color: #fff;
}
.tag-self    { background: var(--br-700); }
.tag-partner { background: var(--tl-800); }
.tag-av {
  width: 20px; height: 20px; border-radius: 50%; overflow: hidden;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 10px; font-weight: 700; flex-shrink: 0;
  background: oklch(100% 0 0 / .22); color: #fff;
}
.tag-av img { width: 100%; height: 100%; object-fit: cover; }

/* ── Big5 Butterfly ────────────────────────────────── */
.butterfly-header {
  display: grid; grid-template-columns: 1fr 120px 1fr;
  gap: 8px; margin-bottom: 8px;
  font-size: .79em; font-weight: 600; color: var(--tx-400);
}
.bf-head-left  { text-align: right; }
.bf-head-right { text-align: left; }

.butterfly-row {
  display: grid; grid-template-columns: 1fr 120px 1fr;
  gap: 8px; align-items: center; margin: 6px 0;
}
.bf-left  { display: flex; align-items: center; justify-content: flex-end; gap: 8px; }
.bf-right { display: flex; align-items: center; gap: 8px; }

.bf-track-left {
  width: 110px; height: 17px;
  background: var(--br-100); border-radius: 8px 0 0 8px;
  overflow: hidden; direction: rtl; flex-shrink: 0;
}
.bf-track-right {
  width: 110px; height: 17px;
  background: var(--tl-200); border-radius: 0 8px 8px 0;
  overflow: hidden; flex-shrink: 0;
}
.bf-fill-self {
  height: 100%;
  background: linear-gradient(to left, var(--br-900), var(--br-500));
  border-radius: 8px 0 0 8px;
}
.bf-fill-partner {
  height: 100%;
  background: linear-gradient(90deg, var(--tl-500), var(--tl-800));
  border-radius: 0 8px 8px 0;
}
.bf-score-left  {
  font-size: .79em; font-weight: 700; color: var(--br-700);
  text-align: right; white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.bf-score-right {
  font-size: .79em; font-weight: 700; color: var(--tl-800);
  white-space: nowrap; font-variant-numeric: tabular-nums;
}
.bf-level { font-weight: 400; color: var(--tx-400); }
.bf-center {
  text-align: center; font-size: .84em; font-weight: 600;
  color: var(--tx-900); line-height: 1.3;
}
.bf-center small { font-weight: 400; color: var(--tx-400); font-size: .78em; }

/* Big5 dual notes */
.dual-notes {
  display: grid; grid-template-columns: 1fr 1fr; gap: 18px;
  margin-top: 22px; padding-top: 18px;
  border-top: 1.5px solid var(--br-100);
}
.note-col-header {
  font-size: .79em; font-weight: 600; color: var(--br-900);
  margin-bottom: 9px; display: flex; align-items: center; gap: 7px;
}
.note-item {
  margin-bottom: 9px; padding: 9px 11px;
  background: var(--br-050); border-radius: var(--r-sm);
  border-left: 3px solid var(--br-300);
}
.partner-note .note-item { background: var(--tl-050); border-left-color: var(--tl-500); }
.note-dim {
  display: inline-block; font-size: .73em; font-weight: 700;
  color: var(--br-700); background: oklch(100% 0 0 / .7);
  padding: 1px 7px; border-radius: 10px; margin-bottom: 3px;
}
.partner-note .note-dim { color: var(--tl-800); }
.note-text     { font-size: .82em; color: var(--tx-900); display: block; margin-top: 3px; line-height: 1.6; }
.note-evidence { font-size: .76em; color: var(--tx-400); font-style: italic; margin-top: 4px; }

/* ── Single Big5 ───────────────────────────────────── */
.trait-row {
  display: flex; gap: 14px; margin: 13px 0; align-items: flex-start;
}
.trait-label {
  width: 68px; font-weight: 600; font-size: .84em;
  color: var(--tx-900); flex-shrink: 0; line-height: 1.3; padding-top: 2px;
}
.trait-label small { font-weight: 400; color: var(--tx-400); display: block; }
.trait-body { flex: 1; }
.bar-wrap { display: flex; align-items: center; gap: 10px; }
.bar-track {
  flex: 1; height: 17px;
  background: var(--br-100); border-radius: 8px; overflow: hidden;
}
.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--br-300), var(--br-900));
  border-radius: 8px;
}
.bar-score {
  font-size: .79em; color: var(--br-700); font-weight: 700;
  white-space: nowrap; font-variant-numeric: tabular-nums;
}
.trait-note     { font-size: .82em; color: var(--tx-600); margin-top: 6px; line-height: 1.65; }
.trait-evidence { font-size: .76em; color: var(--tx-400); font-style: italic; margin-top: 3px; }

/* ── MBTI ──────────────────────────────────────────── */
.dual-col { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.person-panel {
  border-radius: var(--r-md); padding: 18px;
  background: var(--br-050);
}
.person-panel.panel-partner { background: var(--tl-050); }
.panel-header { margin-bottom: 10px; }
.mbti-type-badge {
  font-family: var(--ff-display);
  font-size: clamp(1.8rem, 4vw, 2.7rem);
  font-weight: 700; letter-spacing: 5px;
  color: var(--br-700); line-height: 1; margin: 8px 0 4px;
}
.mbti-type-badge.panel-partner { color: var(--tl-800); }
.mbti-conf  { font-size: .77em; color: var(--tx-400); margin-top: 2px; }
.mbti-note  { font-size: .81em; color: var(--tx-600); margin: 8px 0 10px; font-style: italic; line-height: 1.55; }
.dims-list  {}
.dim-row {
  display: grid; grid-template-columns: 74px 26px 48px 1fr;
  gap: 6px; padding: 6px 0;
  border-bottom: 1px solid oklch(100% 0 0 / .55);
  align-items: baseline; font-size: .81em;
}
.panel-partner .dim-row { border-bottom-color: oklch(100% 0 0 / .45); }
.dim-axis     { color: var(--tx-900); font-weight: 600; }
.dim-lean     { font-weight: 800; color: var(--br-500); }
.dim-lean.panel-partner { color: var(--tl-800); }
.dim-strength { color: var(--tx-400); font-size: .84em; }
.dim-reason   { color: var(--tx-600); line-height: 1.45; }

/* ── Style Summary ─────────────────────────────────── */
.one-line {
  background: var(--surface-2);
  border-left: 4px solid var(--br-500);
  padding: 13px 18px; border-radius: 0 var(--r-sm) var(--r-sm) 0;
  font-size: .94em; font-style: italic; color: var(--tx-900);
  margin-bottom: 15px; line-height: 1.7;
}
.one-line.partner { border-left-color: var(--tl-500); background: var(--tl-050); }
.summary-text { font-size: .89em; color: var(--tx-600); line-height: 1.8; margin-bottom: 13px; }
.strengths    { padding-left: 18px; margin-bottom: 13px; }
.strengths li { font-size: .87em; color: var(--tx-600); margin: 6px 0; line-height: 1.6; }
.fun-facts-label { font-size: .82em; font-weight: 700; color: var(--br-500); margin: 13px 0 7px; }
.partner-col .fun-facts-label { color: var(--tl-800); }
.fun-fact {
  background: var(--surface-2);
  border-left: 3px solid var(--br-300);
  padding: 10px 14px; border-radius: 0 var(--r-sm) var(--r-sm) 0;
  font-size: .84em; margin: 7px 0; color: var(--tx-600); line-height: 1.65;
}
.partner-col .fun-fact { border-left-color: var(--tl-500); }

/* ── Heatmap ───────────────────────────────────────── */
.hm-controls { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
.hm-label-sm { font-size: .79em; color: var(--tx-400); }
.hm-yr-btns  { display: flex; gap: 5px; flex-wrap: wrap; }
.hm-yr-btn {
  padding: 4px 13px; border-radius: 20px;
  border: 1.5px solid var(--br-300);
  background: transparent; color: var(--br-700);
  cursor: pointer; font-size: .79em; font-family: inherit;
  transition: background 150ms, color 150ms, border-color 150ms;
}
.hm-yr-btn.hm-active { background: var(--br-700); color: #fff; border-color: var(--br-700); }
.hm-yr-btn:hover:not(.hm-active) { background: var(--br-100); }

.hm-person-block { margin-bottom: 18px; }
.hm-person-label { margin-bottom: 9px; }
.hm-flex         { display: flex; gap: 4px; }
.hm-daycol       { display: flex; flex-direction: column; flex-shrink: 0; }
.hm-month-sp     { height: 18px; }
.hm-daylbl {
  height: 14px; width: 18px; font-size: 9px;
  color: var(--tx-400); line-height: 14px; margin-bottom: 2px; text-align: right;
}
.hm-scroll {
  display: flex; gap: 2px; overflow-x: auto; padding-bottom: 6px;
  scrollbar-width: thin;
  scrollbar-color: var(--br-300) var(--br-100);
}
.hm-scroll::-webkit-scrollbar       { height: 5px; }
.hm-scroll::-webkit-scrollbar-track { background: var(--br-100); border-radius: 3px; }
.hm-scroll::-webkit-scrollbar-thumb { background: var(--br-300); border-radius: 3px; }
.hm-col     { display: flex; flex-direction: column; }
.hm-monlbl  { height: 18px; font-size: 9px; color: var(--tx-400); white-space: nowrap; }
.hm-weekcol { display: flex; flex-direction: column; gap: 2px; }
.hm-cell {
  width: 13px; height: 13px; border-radius: 2px;
  flex-shrink: 0; transition: opacity 100ms;
  cursor: default;
}
.hm-cell:hover { opacity: .62; }
.hm-out        { background: transparent !important; }
.hm-sep        { border: none; border-top: 1.5px solid var(--br-100); margin: 14px 0; }
.hm-legend     { display: flex; align-items: center; gap: 10px; margin-top: 10px; flex-wrap: wrap; font-size: .75em; color: var(--tx-400); }
.hm-leg-row    { display: flex; align-items: center; gap: 5px; }
.hm-leg-cells  { display: flex; gap: 2px; }
.hm-leg-cell   { width: 11px; height: 11px; border-radius: 2px; }
.hm-tip {
  position: fixed;
  background: var(--tx-900); color: oklch(96% 0.022 55);
  padding: 6px 12px; border-radius: var(--r-sm);
  font-size: 11px; pointer-events: none; z-index: 9999;
  display: none; white-space: nowrap; line-height: 1.5;
  box-shadow: 0 4px 14px oklch(22% 0.025 48 / .28);
}

/* ── Disclaimer ────────────────────────────────────── */
.disclaimer {
  text-align: center; font-size: .74em; color: var(--tx-400);
  padding: 26px 22px; border-top: 1.5px solid var(--br-100);
  line-height: 2;
}
.brand {
  font-family: var(--ff-display);
  font-weight: 700; color: var(--br-500);
  margin-top: 12px; font-size: 1em; letter-spacing: .08em;
}

/* ── Responsive ────────────────────────────────────── */
@media (max-width: 600px) {
  .chart-grid       { grid-template-columns: 1fr; }
  .dual-col         { grid-template-columns: 1fr; }
  .dual-notes       { grid-template-columns: 1fr; }
  .stats            { gap: 7px; }
  .stat-num         { font-size: 1.4rem; }
  .butterfly-row,
  .butterfly-header { grid-template-columns: 1fr 80px 1fr; }
  .bf-track-left,
  .bf-track-right   { width: 72px; }
  .mbti-type-badge  { font-size: 1.75rem; letter-spacing: 3px; }
}
"""

# ── Heatmap JavaScript ────────────────────────────────────────────────────────

_HEATMAP_JS = r"""
function initHeatmap(selfData, partnerData, hasPartner) {
  var SELF_PAL    = ['#EDE5DC','#D4A882','#B87040','#8B5E3C','#5A3020'];
  var PARTNER_PAL = ['#D8EDEA','#8ABFB8','#5A9B93','#4A7B6F','#2E5048'];
  var MON = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];

  // Collect years from both datasets
  var allKeys = Object.keys(selfData).concat(hasPartner ? Object.keys(partnerData) : []);
  var yearSet = {};
  allKeys.forEach(function(k) { yearSet[k.slice(0, 4)] = true; });
  var years = Object.keys(yearSet).sort();
  if (!years.length) return;

  var curYear = years[years.length - 1];

  // Year toggle buttons
  var btnBox = document.getElementById('hm-year-btns');
  years.forEach(function(y) {
    var btn = document.createElement('button');
    btn.className = 'hm-yr-btn' + (y === curYear ? ' hm-active' : '');
    btn.textContent = y;
    btn.onclick = function() {
      document.querySelectorAll('.hm-yr-btn').forEach(function(b) { b.classList.remove('hm-active'); });
      btn.classList.add('hm-active');
      curYear = y;
      renderGrid('hm-self-grid', selfData, SELF_PAL);
      if (hasPartner) renderGrid('hm-partner-grid', partnerData, PARTNER_PAL);
    };
    btnBox.appendChild(btn);
  });

  function getColor(n, mx, pal) {
    if (!n || mx === 0) return pal[0];
    var r = n / mx;
    return r < 0.15 ? pal[1] : r < 0.40 ? pal[2] : r < 0.72 ? pal[3] : pal[4];
  }

  function ymd(d) {
    return d.getFullYear() + '-' +
      String(d.getMonth() + 1).padStart(2, '0') + '-' +
      String(d.getDate()).padStart(2, '0');
  }

  function renderGrid(elId, data, pal) {
    var el = document.getElementById(elId);
    if (!el) return;
    el.innerHTML = '';

    var yr = parseInt(curYear, 10);
    var yrVals = [];
    Object.keys(data).forEach(function(k) {
      if (k.startsWith(curYear)) yrVals.push(+data[k]);
    });
    var mx = yrVals.length ? Math.max.apply(null, yrVals) : 1;

    // Outer flex container (day labels + scrollable weeks)
    var wrap = document.createElement('div');
    wrap.className = 'hm-flex';

    // Day-of-week labels (left column)
    var dayCol = document.createElement('div');
    dayCol.className = 'hm-daycol';
    var sp = document.createElement('div');
    sp.className = 'hm-month-sp';
    dayCol.appendChild(sp);
    ['一','二','三','四','五','六','日'].forEach(function(lbl, i) {
      var d = document.createElement('div');
      d.className = 'hm-daylbl';
      d.textContent = (i % 2 === 0) ? lbl : '';
      dayCol.appendChild(d);
    });
    wrap.appendChild(dayCol);

    // Scrollable weeks
    var scroll = document.createElement('div');
    scroll.className = 'hm-scroll';

    // Start: Monday on or before Jan 1
    var jan1 = new Date(yr, 0, 1);
    var dow0 = (jan1.getDay() + 6) % 7;
    var startD = new Date(jan1);
    startD.setDate(startD.getDate() - dow0);

    // End: Sunday on or after Dec 31
    var dec31 = new Date(yr, 11, 31);
    var dow31 = (dec31.getDay() + 6) % 7;
    var endD = new Date(dec31);
    endD.setDate(endD.getDate() + (6 - dow31));

    var cur = new Date(startD);
    var seenMon = {};

    while (cur <= endD) {
      var col = document.createElement('div');
      col.className = 'hm-col';

      var monLbl = document.createElement('div');
      monLbl.className = 'hm-monlbl';

      var weekEl = document.createElement('div');
      weekEl.className = 'hm-weekcol';

      for (var i = 0; i < 7; i++) {
        var inYr = cur.getFullYear() === yr;

        if (inYr && cur.getDate() === 1 && !seenMon[cur.getMonth()]) {
          monLbl.textContent = MON[cur.getMonth()];
          seenMon[cur.getMonth()] = true;
        }

        var cell = document.createElement('div');
        if (inYr) {
          var ds = ymd(cur);
          var n = +(data[ds] || 0);
          cell.className = 'hm-cell';
          cell.style.backgroundColor = getColor(n, mx, pal);
          cell.dataset.d = ds;
          cell.dataset.n = n;
        } else {
          cell.className = 'hm-cell hm-out';
        }
        weekEl.appendChild(cell);
        cur.setDate(cur.getDate() + 1);
      }

      col.appendChild(monLbl);
      col.appendChild(weekEl);
      scroll.appendChild(col);
    }

    wrap.appendChild(scroll);
    el.appendChild(wrap);
  }

  renderGrid('hm-self-grid', selfData, SELF_PAL);
  if (hasPartner) renderGrid('hm-partner-grid', partnerData, PARTNER_PAL);

  // Tooltip
  var tip = document.createElement('div');
  tip.className = 'hm-tip';
  document.body.appendChild(tip);

  document.addEventListener('mouseover', function(e) {
    var t = e.target;
    if (t.classList && t.classList.contains('hm-cell') && t.dataset && t.dataset.d) {
      var n = +t.dataset.n;
      tip.textContent = t.dataset.d + (n > 0 ? '  ·  ' + n + ' 条' : '  ·  无消息');
      tip.style.display = 'block';
    }
  });
  document.addEventListener('mouseout', function(e) {
    if (e.target.classList && e.target.classList.contains('hm-cell')) {
      tip.style.display = 'none';
    }
  });
  document.addEventListener('mousemove', function(e) {
    tip.style.left = (e.clientX + 14) + 'px';
    tip.style.top  = (e.clientY - 38) + 'px';
  });
}
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _av(name: str, data: Optional[str], size: int = 38, cls: str = 'av-self') -> str:
    initial = name[:1] if name else '?'
    inner = (f'<img src="{data}" alt="{initial}" onerror="this.style.display=\'none\';'
             f'this.parentNode.textContent=\'{initial}\'">' if data else initial)
    return (f'<div class="av {cls}" '
            f'style="width:{size}px;height:{size}px;font-size:{size//2}px">{inner}</div>')


def _pill(name: str, data: Optional[str], partner: bool = False) -> str:
    av = _av(name, data, size=38, cls='av-partner' if partner else 'av-self')
    return f'<div class="person-pill">{av}<span class="pill-name">{name}</span></div>'


def _tag(name: str, data: Optional[str], partner: bool = False) -> str:
    cls = 'tag-partner' if partner else 'tag-self'
    initial = name[:1] if name else '?'
    inner = (f'<img src="{data}" alt="{initial}" onerror="this.style.display=\'none\';'
             f'this.parentNode.textContent=\'{initial}\'">' if data else initial)
    av = f'<span class="tag-av">{inner}</span>'
    return f'<span class="{cls}">{av}{name}</span>'


# ── Section builders ──────────────────────────────────────────────────────────

def _butterfly_big5(b5s: dict, b5p: dict,
                    sn: str, pn: str, sa: Optional[str], pa: Optional[str]) -> str:
    labels = [
        ('openness',          '开放性', 'Openness'),
        ('conscientiousness', '尽责性', 'Conscientiousness'),
        ('extraversion',      '外倾性', 'Extraversion'),
        ('agreeableness',     '宜人性', 'Agreeableness'),
        ('neuroticism',       '神经质', 'Neuroticism'),
    ]
    hdr = f'''
    <div class="butterfly-header">
      <div class="bf-head-left">{_tag(sn, sa)}</div>
      <div style="text-align:center;color:var(--tx-400,#9A8070);font-size:.82em">维度</div>
      <div class="bf-head-right">{_tag(pn, pa, partner=True)}</div>
    </div>'''
    rows = ''
    left_notes = right_notes = ''
    for idx, (key, zh, en) in enumerate(labels):
        si, pi = b5s.get(key, {}), b5p.get(key, {})
        ss, ps = si.get('score', 0), pi.get('score', 0)
        sl, pl = si.get('level', ''), pi.get('level', '')
        rows += f'''
      <div class="butterfly-row">
        <div class="bf-left">
          <span class="bf-score-left">{ss}<span class="bf-level"> {sl}</span></span>
          <div class="bf-track-left"><div class="bf-fill-self" style="width:{ss}%;--bi:{idx}"></div></div>
        </div>
        <div class="bf-center">{zh}<br><small>{en}</small></div>
        <div class="bf-right">
          <div class="bf-track-right"><div class="bf-fill-partner" style="width:{ps}%;--bi:{idx}"></div></div>
          <span class="bf-score-right">{ps}<span class="bf-level"> {pl}</span></span>
        </div>
      </div>'''
        if si.get('note') or si.get('evidence'):
            ev = f'<div class="note-evidence">💬 "{si["evidence"]}"</div>' if si.get('evidence') else ''
            left_notes += f'<div class="note-item"><span class="note-dim">{zh}</span><span class="note-text">{si.get("note","")}</span>{ev}</div>'
        if pi.get('note') or pi.get('evidence'):
            ev = f'<div class="note-evidence">💬 "{pi["evidence"]}"</div>' if pi.get('evidence') else ''
            right_notes += f'<div class="note-item"><span class="note-dim">{zh}</span><span class="note-text">{pi.get("note","")}</span>{ev}</div>'
    notes = f'''
    <div class="dual-notes">
      <div class="note-col self-note">
        <div class="note-col-header">{_tag(sn, sa)} 解读</div>{left_notes}
      </div>
      <div class="note-col partner-note">
        <div class="note-col-header">{_tag(pn, pa, partner=True)} 解读</div>{right_notes}
      </div>
    </div>'''
    return hdr + rows + notes


def _single_big5(big5: dict) -> str:
    labels = [
        ('openness','开放性','Openness'), ('conscientiousness','尽责性','Conscientiousness'),
        ('extraversion','外倾性','Extraversion'), ('agreeableness','宜人性','Agreeableness'),
        ('neuroticism','神经质','Neuroticism'),
    ]
    html = ''
    for idx, (key, zh, en) in enumerate(labels):
        item = big5.get(key, {})
        score, level = item.get('score', 50), item.get('level', '')
        note, ev = item.get('note', ''), item.get('evidence', '')
        html += f'''
      <div class="trait-row">
        <div class="trait-label">{zh}<small>{en}</small></div>
        <div class="trait-body">
          <div class="bar-wrap">
            <div class="bar-track"><div class="bar-fill" style="width:{score}%;--bi:{idx}"></div></div>
            <span class="bar-score">{score} · {level}</span>
          </div>
          <div class="trait-note">{note}</div>
          <div class="trait-evidence">💬 "{ev}"</div>
        </div>
      </div>'''
    return html


def _mbti_panel(mbti: dict, partner: bool = False,
                name: str = '?', av: Optional[str] = None) -> str:
    mtype = mbti.get('type', '??')
    conf, note = mbti.get('confidence', '低'), mbti.get('note', '')
    dims = mbti.get('dims', {})
    pcls = 'panel-partner' if partner else ''
    dim_labels = [('EI','内/外向'), ('SN','感知/直觉'), ('TF','思考/情感'), ('JP','判断/感知')]
    dims_html = ''
    for dim, lbl in dim_labels:
        d = dims.get(dim, {})
        dims_html += f'''
          <div class="dim-row">
            <span class="dim-axis">{lbl}</span>
            <span class="dim-lean {pcls}">{d.get("lean","?")}</span>
            <span class="dim-strength">{d.get("strength","")}</span>
            <div class="dim-reason">{d.get("reason","")}</div>
          </div>'''
    return f'''
    <div class="person-panel {pcls}">
      <div class="panel-header">{_tag(name, av, partner=partner)}</div>
      <div class="mbti-type-badge {pcls}">{mtype}</div>
      <div class="mbti-conf">置信度：{conf}</div>
      <div class="mbti-note">{note}</div>
      <div class="dims-list">{dims_html}</div>
    </div>'''


def _style_panel(style: dict, partner: bool = False,
                 name: str = '?', av: Optional[str] = None) -> str:
    one_line  = style.get('one_line', '')
    summary   = style.get('summary', '')
    strengths = style.get('strengths', [])
    fun_facts = style.get('fun_facts', [])
    col_cls   = 'partner-col' if partner else ''
    ql_cls    = 'partner' if partner else ''
    s_items   = ''.join(f'<li>{s}</li>' for s in strengths)
    f_items   = ''.join(f'<div class="fun-fact">{f}</div>' for f in fun_facts)
    fun_sec   = f'<div class="fun-facts-label">意外发现</div>{f_items}' if fun_facts else ''
    return f'''
    <div class="{col_cls}">
      <div class="panel-header" style="margin-bottom:12px">{_tag(name, av, partner=partner)}</div>
      <blockquote class="one-line {ql_cls}">"{one_line}"</blockquote>
      <p class="summary-text">{summary}</p>
      <ul class="strengths">{s_items}</ul>
      {fun_sec}
    </div>'''


def _heatmap_html(stats_self: dict, stats_partner: Optional[dict],
                  sn: str, pn: str, sa: Optional[str], pa: Optional[str]) -> str:
    """生成热力图 HTML + 内嵌 JS"""
    daily_self = {str(k): int(v) for k, v in stats_self['daily'].items()}

    has_partner = stats_partner is not None
    daily_partner = {}
    if has_partner:
        daily_partner = {str(k): int(v) for k, v in stats_partner['daily'].items()}

    partner_block = ''
    if has_partner:
        partner_block = f'''
      <hr class="hm-sep">
      <div class="hm-person-block">
        <div class="hm-person-label">{_tag(pn, pa, partner=True)}</div>
        <div id="hm-partner-grid"></div>
      </div>'''

    # Legend
    self_pal    = ['#EDE5DC', '#D4A882', '#B87040', '#8B5E3C', '#5A3020']
    partner_pal = ['#D8EDEA', '#8ABFB8', '#5A9B93', '#4A7B6F', '#2E5048']
    s_leg = ''.join(f'<div class="hm-leg-cell" style="background:{c}"></div>' for c in self_pal)
    p_leg = ''.join(f'<div class="hm-leg-cell" style="background:{c}"></div>' for c in partner_pal)

    legend = f'''
    <div class="hm-legend">
      <div class="hm-leg-row">{_tag(sn, sa)} &nbsp;少 <div class="hm-leg-cells">{s_leg}</div> 多</div>
      {"&nbsp;&nbsp;" if has_partner else ""}
      {"<div class='hm-leg-row'>" + _tag(pn, pa, partner=True) + " &nbsp;少 <div class='hm-leg-cells'>" + p_leg + "</div> 多</div>" if has_partner else ""}
    </div>'''

    return f'''
  <div class="section" style="--i:3">
    <div class="section-title">📅 聊天频率热力图</div>
    <div class="hm-controls">
      <span class="hm-label-sm">年份</span>
      <div class="hm-yr-btns" id="hm-year-btns"></div>
    </div>
    <div class="hm-person-block">
      <div class="hm-person-label">{_tag(sn, sa)}</div>
      <div id="hm-self-grid"></div>
    </div>
    {partner_block}
    {legend}
  </div>
  <script>
  (function() {{
    var SELF_DATA    = {_json.dumps(daily_self, ensure_ascii=False)};
    var PARTNER_DATA = {_json.dumps(daily_partner, ensure_ascii=False)};
    var HAS_PARTNER  = {'true' if has_partner else 'false'};
    {_HEATMAP_JS}
    initHeatmap(SELF_DATA, PARTNER_DATA, HAS_PARTNER);
  }})();
  </script>'''


# ── Main generator ────────────────────────────────────────────────────────────

def generate(stats: dict, personality: dict, output_dir: str,
             partner_stats: dict = None,
             partner_personality: dict = None,
             self_name: str = '我',
             partner_name: str = '对方',
             self_avatar_data: Optional[str] = None,
             partner_avatar_data: Optional[str] = None,
             has_pair_wordcloud: bool = False) -> str:

    dr = stats['date_range']
    days = max(1, (dr[1] - dr[0]).days)
    yrs, rem = divmod(days, 365)
    mos = rem // 30
    span_str = (f'{yrs}年{mos}个月' if yrs > 0 else (f'{mos}个月' if mos > 0 else '不足1个月'))

    has_partner = bool(partner_personality and partner_personality.get('big5'))
    big5  = personality.get('big5', {})
    mbti  = personality.get('mbti', {})
    style = personality.get('style', {})

    # ── Header ────────────────────────────────────────────────────────────────
    if has_partner:
        header_vs = f'''
        <div class="header-vs">
          {_pill(self_name, self_avatar_data)}
          <span class="vs-divider">VS</span>
          {_pill(partner_name, partner_avatar_data, partner=True)}
        </div>'''
    else:
        header_vs = f'<div class="header-vs">{_pill(self_name, self_avatar_data)}</div>'

    # ── Charts ────────────────────────────────────────────────────────────────
    wc_img = ('charts/word_cloud_pair.png' if has_pair_wordcloud else 'charts/word_cloud.png')
    wc_title = '高频词对比' if has_pair_wordcloud else '你最常聊的话题'

    # ── Radar ─────────────────────────────────────────────────────────────────
    radar_img = ''
    if big5 and not has_partner:
        radar_img = '<img src="charts/radar.png" class="chart-full" alt="radar" style="margin-top:16px">'

    # ── Big5 ──────────────────────────────────────────────────────────────────
    if has_partner:
        big5_html = _butterfly_big5(
            big5, partner_personality.get('big5', {}),
            self_name, partner_name, self_avatar_data, partner_avatar_data
        )
    elif big5:
        big5_html = _single_big5(big5) + radar_img
    else:
        big5_html = '<p style="color:#9A8070;font-size:.9em">人格分析结果未加载</p>'

    # ── MBTI ──────────────────────────────────────────────────────────────────
    if has_partner:
        mbti_html = f'''
        <div class="dual-col">
          {_mbti_panel(mbti, partner=False, name=self_name, av=self_avatar_data)}
          {_mbti_panel(partner_personality.get("mbti", {}), partner=True, name=partner_name, av=partner_avatar_data)}
        </div>'''
    elif mbti:
        mbti_html = f'<div style="max-width:560px">{_mbti_panel(mbti, name=self_name, av=self_avatar_data)}</div>'
    else:
        mbti_html = '<p style="color:#9A8070;font-size:.9em">MBTI 分析未加载</p>'

    # ── Style ─────────────────────────────────────────────────────────────────
    if has_partner:
        style_html = f'''
        <div class="dual-col">
          {_style_panel(style, partner=False, name=self_name, av=self_avatar_data)}
          {_style_panel(partner_personality.get("style", {}), partner=True, name=partner_name, av=partner_avatar_data)}
        </div>'''
    elif style:
        style_html = _style_panel(style, name=self_name, av=self_avatar_data)
    else:
        style_html = ''

    # ── Heatmap ───────────────────────────────────────────────────────────────
    hm_section = _heatmap_html(
        stats, partner_stats,
        self_name, partner_name, self_avatar_data, partner_avatar_data
    )

    # Write external CSS file
    css_path = os.path.join(output_dir, 'report.css')
    with open(css_path, 'w', encoding='utf-8') as f:
        f.write(_CSS)

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>微信聊天人格分析 · 姜饼探AI</title>
<link rel="stylesheet" href="report.css">
</head>
<body>
<div class="container">

<div class="header" style="--i:0">
  <h1>🍪 微信聊天人格分析报告</h1>
  <div class="header-meta">{datetime.now().strftime('%Y年%m月%d日')}</div>
  {header_vs}
</div>

<div class="stats" style="--i:1">
  <div class="stat">
    <div class="stat-num">{stats['total_messages']:,}</div>
    <div class="stat-lbl">{self_name} 发出的消息</div>
  </div>
  <div class="stat">
    <div class="stat-num">{stats['avg_length']}</div>
    <div class="stat-lbl">平均消息字数</div>
  </div>
  <div class="stat">
    <div class="stat-num">{span_str}</div>
    <div class="stat-lbl">数据覆盖时长</div>
  </div>
</div>

<div class="section" style="--i:2">
  <div class="section-title">📊 消息行为分析</div>
  <div class="chart-grid">
    <img src="charts/hourly.png" alt="活跃时段">
    <img src="charts/monthly_trend.png" alt="月度趋势">
    <img src="charts/weekday_bar.png" alt="星期分布">
    <img src="charts/length_dist.png" alt="消息长度">
  </div>
</div>

{hm_section}

<div class="section" style="--i:4">
  <div class="section-title">💬 {wc_title}</div>
  <img src="{wc_img}" class="chart-full" alt="词云">
</div>

<div class="section" style="--i:5">
  <div class="section-title">🧠 大五人格分析 (Big Five)</div>
  {big5_html}
</div>

<div class="section" style="--i:6">
  <div class="section-title">🔮 MBTI 推断</div>
  {mbti_html}
</div>

<div class="section" style="--i:7">
  <div class="section-title">✨ AI 对你{"们" if has_partner else ""}的总结</div>
  {style_html}
</div>

<div class="disclaimer">
  ⚠️ 本报告基于语言模式的统计推断，仅供娱乐与自我探索，不构成心理学诊断或专业评估。<br>
  MBTI 信效度存在学术争议；Big Five 具有更强的研究支撑，但仍需结合充足样本谨慎解读。<br>
  人格判断以对话中的认知风格和语言习惯为依据，受数据量、话题覆盖范围及时间跨度影响，仅作参考。
  <div class="brand">🍪 姜饼探AI · WeChat Analyzer v1.3</div>
</div>

</div><!-- .container -->
</body>
</html>"""

    path = os.path.join(output_dir, 'report.html')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    return path
