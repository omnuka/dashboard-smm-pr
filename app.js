
const state = {
  competitors: [], sources: [], servicesBase: [], findings: [], demoMode: false,
  filters: { period: 'all', type: 'all', service: 'all', search: '' }
};

const $ = (id) => document.getElementById(id);
const fmt = (v) => (v === null || v === undefined || v === '' ? '—' : v);
const num = (v) => Number(v || 0);
const byDateDesc = (a,b) => String(b.date || '').localeCompare(String(a.date || ''));

async function getJson(path, fallback){
  try{ const r = await fetch(path); if(!r.ok) throw new Error(path); return await r.json(); }
  catch(e){ return fallback; }
}

function unique(arr){ return [...new Set(arr.filter(Boolean))]; }

function withinPeriod(item){
  if(state.filters.period === 'all' || !item.date) return true;
  const days = Number(state.filters.period);
  const d = new Date(item.date + 'T00:00:00');
  const now = new Date();
  const diff = (now - d) / (1000*60*60*24);
  return diff <= days;
}

function filteredFindings(){
  const q = state.filters.search.trim().toLowerCase();
  return state.findings.filter(f => {
    if(!withinPeriod(f)) return false;
    if(state.filters.type !== 'all' && f.source_type !== state.filters.type) return false;
    if(state.filters.service !== 'all' && f.service !== state.filters.service) return false;
    if(q){
      const blob = [f.theme,f.service,f.title,f.summary,f.competitor,f.channel,f.seo_keyword].join(' ').toLowerCase();
      if(!blob.includes(q)) return false;
    }
    return true;
  }).sort(byDateDesc);
}

function countBy(items, key){
  const map = new Map();
  items.forEach(i => {
    const k = i[key] || 'Без категории';
    map.set(k, (map.get(k) || 0) + 1);
  });
  return [...map.entries()].sort((a,b) => b[1]-a[1]);
}

function renderBars(el, pairs, emptyText='Данных пока нет'){
  if(!pairs.length){ el.innerHTML = `<div class="empty-bars">${emptyText}</div>`; return; }
  const max = Math.max(...pairs.map(p => p[1]), 1);
  el.innerHTML = pairs.slice(0,10).map(([label,value]) => `
    <div class="bar-row">
      <div class="bar-label" title="${label}">${label}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${Math.max(6,value/max*100)}%"></div></div>
      <div class="bar-value">${value}</div>
    </div>
  `).join('');
}

function link(url, text='открыть'){
  if(!url) return '<span class="muted">—</span>';
  return `<a class="link" href="${url}" target="_blank" rel="noreferrer">${text}</a>`;
}

function reactionText(f){
  const parts = [];
  if(f.views) parts.push(`${f.views} просмотров`);
  if(f.reactions) parts.push(`${f.reactions} реакций`);
  if(f.comments) parts.push(`${f.comments} комм.`);
  return parts.length ? parts.join('<br>') : '—';
}

function renderTable(tbody, rows, cols, empty){
  if(!rows.length){ tbody.innerHTML = `<tr><td colspan="${cols.length}" class="muted">${empty}</td></tr>`; return; }
  tbody.innerHTML = rows.map(r => `<tr>${cols.map(c => `<td>${c(r)}</td>`).join('')}</tr>`).join('');
}

function renderAll(){
  const data = filteredFindings();
  $('emptyState').classList.toggle('hidden', state.findings.length > 0);

  $('kpiCases').textContent = data.filter(f => f.source_type === 'Кейс').length;
  $('kpiPosts').textContent = data.filter(f => f.source_type === 'Пост' || f.source_type === 'Видео').length;
  $('kpiMedia').textContent = data.filter(f => f.source_type === 'СМИ').length;
  $('kpiSeo').textContent = data.filter(f => f.source_type === 'SEO' || f.seo_keyword).length;

  renderBars($('themeBars'), countBy(data, 'theme'));
  renderBars($('serviceBars'), countBy(data, 'service'));
  renderBars($('seoBars'), countBy(data.filter(f => f.seo_keyword), 'seo_keyword'), 'SEO-импорт пока не подключен');

  const latestCols = [
    f => `<span class="nowrap">${fmt(f.date)}</span>`,
    f => `<span class="tag">${fmt(f.theme)}</span>`,
    f => fmt(f.service),
    f => fmt(f.source_type),
    f => fmt(f.competitor),
    f => `${fmt(f.title)}<div class="muted">${fmt(f.summary)}</div>${link(f.url)}`,
    f => `<span class="metric">${reactionText(f)}</span>`,
    f => fmt(f.serenity_pr_smm_use)
  ];
  renderTable($('latestRows'), data.slice(0,12), latestCols, 'Находок по выбранным фильтрам нет');

  const themeCols = [
    f => `<strong>${fmt(f.theme)}</strong>`, f => fmt(f.service), f => fmt(f.source_type), f => fmt(f.channel), f => fmt(f.competitor),
    f => `${fmt(f.title)}<div class="muted">${fmt(f.summary)}</div>`, f => fmt(f.date), f => reactionText(f), f => link(f.url)
  ];
  renderTable($('themeRows'), data, themeCols, 'Тематики появятся после сбора или импорта находок');

  const social = data.filter(f => ['Пост','Видео'].includes(f.source_type) || ['Telegram','VK','YouTube','Instagram'].includes(f.channel));
  const socialCols = [f=>fmt(f.date), f=>fmt(f.channel), f=>fmt(f.competitor), f=>fmt(f.theme), f=>`${fmt(f.title)}${link(f.url)}`, f=>fmt(f.views), f=>fmt(f.reactions), f=>fmt(f.comments), f=>fmt(f.serenity_pr_smm_use)];
  renderTable($('socialRows'), social, socialCols, 'Соцданные пока не собраны');

  const media = data.filter(f => f.source_type === 'СМИ' || f.channel === 'СМИ');
  const mediaCols = [f=>fmt(f.date), f=>fmt(f.theme), f=>fmt(f.competitor), f=>`${fmt(f.title)}${link(f.url)}`, f=>fmt(f.summary), f=>fmt(f.sentiment), f=>fmt(f.serenity_pr_smm_use)];
  renderTable($('mediaRows'), media, mediaCols, 'СМИ-упоминания пока не собраны');

  const seo = data.filter(f => f.source_type === 'SEO' || f.seo_keyword);
  const seoCols = [f=>fmt(f.seo_keyword), f=>fmt(f.seo_position), f=>fmt(f.competitor), f=>link(f.url), f=>fmt(f.service), f=>fmt(f.theme), f=>fmt(f.date)];
  renderTable($('seoRows'), seo, seoCols, 'SEO-данные нужно импортировать отдельным файлом');

  renderServiceSummary(data);
  renderSources();
}

function renderServiceSummary(data){
  const pairs = countBy(data, 'service');
  $('serviceSummary').innerHTML = pairs.length ? pairs.map(([service,count]) => `<div class="service-item"><div><strong>${service}</strong><span>по свежим находкам</span></div><div class="service-count">${count}</div></div>`).join('') : '<div class="empty-bars">После сбора здесь будет видно, какие услуги чаще продвигают конкуренты.</div>';
  $('baseServiceSummary').innerHTML = state.servicesBase.map(s => `<div class="service-item"><div><strong>${s.service}</strong><span>${s.competitors.slice(0,5).join(', ')}${s.competitors.length>5?'…':''}</span></div><div class="service-count">${s.competitors_count}</div></div>`).join('');
}

function renderSources(){
  $('baseCount').textContent = `${state.competitors.length} агентств`;
  $('sourceCount').textContent = `${state.sources.length} источников`;
  $('competitorCards').innerHTML = state.competitors.map(c => {
    const links = [
      ['сайт', c.site], ['кейсы', c.cases_url], ['блог', c.blog_url], ['TG', c.telegram], ['VK', c.vk], ['YT', c.youtube]
    ].filter(x => x[1] && !String(x[1]).includes('не найдено')).map(([t,u]) => `<a href="${u}" target="_blank" rel="noreferrer">${t}</a>`).join('');
    return `<article class="competitor"><h3>${c.rank}. ${c.name}</h3><p>${fmt(c.services)}</p><p class="muted">${fmt(c.monitor_focus)}</p><div class="competitor-links">${links}</div></article>`;
  }).join('');
  renderTable($('sourceRows'), state.sources, [s=>fmt(s.competitor), s=>fmt(s.source_type), s=>fmt(s.check), s=>fmt(s.url_or_query)], 'Источников нет');
}

async function loadDemo(){
  state.findings = await getJson('data/weekly_findings.demo.json', []);
  state.demoMode = true;
  renderAll();
}

function fillServiceFilter(){
  const services = unique([...state.servicesBase.map(s => s.service), ...state.findings.map(f => f.service)]).sort();
  $('serviceFilter').innerHTML = '<option value="all">Все услуги</option>' + services.map(s => `<option value="${s}">${s}</option>`).join('');
}

function download(filename, data){
  const blob = new Blob([data], {type:'application/json;charset=utf-8'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click(); URL.revokeObjectURL(url);
}

async function init(){
  state.competitors = await getJson('data/competitors.json', []);
  state.sources = await getJson('data/sources.json', []);
  state.servicesBase = await getJson('data/service-summary.json', []);
  state.findings = await getJson('data/weekly_findings.json', []);
  fillServiceFilter();
  renderAll();

  document.querySelectorAll('.nav').forEach(btn => btn.addEventListener('click', () => {
    document.querySelectorAll('.nav').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    btn.classList.add('active');
    $(`view-${btn.dataset.view}`).classList.add('active');
  }));
  $('periodFilter').addEventListener('change', e => {state.filters.period=e.target.value; renderAll();});
  $('typeFilter').addEventListener('change', e => {state.filters.type=e.target.value; renderAll();});
  $('serviceFilter').addEventListener('change', e => {state.filters.service=e.target.value; renderAll();});
  $('searchInput').addEventListener('input', e => {state.filters.search=e.target.value; renderAll();});
  $('loadDemoBtn').addEventListener('click', loadDemo);
  $('exportBtn').addEventListener('click', () => download('weekly_findings_export.json', JSON.stringify(filteredFindings(), null, 2)));
}
init();
