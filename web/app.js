'use strict';
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const sections = ['catalog','reader','sign','receipt','admin'];
let active = 'catalog', training = null, page = 1, seen = 0, busy = false, objectURL = null, adminData = null;
let catalogFingerprint = '';
const notify = message => { $('#notice').textContent = message; $('#notice').hidden = !message; };
function show(id) {
  active = id;
  sections.forEach(s => $('#' + s).hidden = s !== id);
  notify('');
  window.scrollTo({top:0,behavior:'instant'});
}
async function api(url, body) {
  const response = await fetch(url, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw Error(data.error || '요청을 처리하지 못했습니다.');
  return data;
}
function handle(error) { notify(error.message || '서버에 연결하지 못했습니다. 서버 실행 상태를 확인해 주세요.'); }
async function catalog() {
  show('catalog');
  training = null;
  resetSignature();
  $('#sign-form').reset();
  $('#receipt-text').textContent = '';
  if (objectURL) { URL.revokeObjectURL(objectURL); objectURL = null; }
  $('#page-image').removeAttribute('src');
  catalogFingerprint = '';
  $('#courses').textContent = '연수 목록을 불러오는 중입니다…';
  await refreshCourses();
}
async function refreshCourses(quiet = false) {
  try {
    const courses = await api('/api/courses');
    if (active !== 'catalog') return;
    const fingerprint = JSON.stringify(courses);
    if (fingerprint === catalogFingerprint) return;
    catalogFingerprint = fingerprint;
    $('#course-count').textContent = courses.length;
    $('#courses').innerHTML = courses.length ? courses.map(c => `<article class="course-card"><span class="filetype">${c.source.endsWith('/') ? '자료 모음' : esc(c.source.split('.').pop().toUpperCase())}</span><h3>${esc(c.title)}</h3><p class="course-meta">${c.error ? esc(c.error) : `${c.pages}쪽 · 자료 열람 후 서명`}</p><button data-course="${c.id}" ${c.error ? 'disabled' : ''}>연수 참여하기 →</button></article>`).join('') : '<div class="empty">등록된 자료가 없습니다. 담당자는 프로그램의 [연수자료] 폴더에 PDF 또는 PNG를 넣어 주세요.</div>';
  } catch (e) { if (!quiet) { $('#courses').textContent = ''; handle(e); } }
}
setInterval(() => { if (active === 'catalog' && !document.hidden) refreshCourses(true); }, 4000);
$('#refresh').onclick = catalog;
document.querySelectorAll('.home').forEach(b => b.onclick = catalog);
$('#courses').onclick = async e => {
  const button = e.target.closest('[data-course]');
  if (!button) return;
  button.disabled = true;
  try {
    training = await api(`/api/courses/${button.dataset.course}/start`, {});
    seen = 0; page = 1;
    $('#reader-title').textContent = training.title;
    $('#sign-title').textContent = training.title;
    $('#pledge').textContent = training.pledge;
    show('reader');
    await displayPage(1);
  } catch(e) { handle(e); }
  finally { button.disabled = false; }
};
function navigation() {
  $('#previous').disabled = busy || page <= 1;
  $('#next').disabled = busy || page >= training.pages || page > seen;
  $('#page-number').textContent = `${page} / ${training.pages}쪽`;
  $('#read-count').textContent = `${seen}쪽 확인 완료`;
  $('#progress-bar').style.width = `${seen / training.pages * 100}%`;
  $('#go-sign').disabled = busy || seen !== training.pages;
  $('#reader-hint').textContent = seen === training.pages ? '모든 자료를 확인했습니다. 이제 서명을 제출해 주세요.' : '모든 쪽을 확인하면 서명할 수 있습니다.';
}
async function displayPage(number) {
  if (busy) return;
  busy = true; page = number; navigation();
  $('#loading').textContent = '자료를 불러오는 중입니다…';
  $('#loading').hidden = false; $('#page-image').hidden = true;
  $('#page-stage').setAttribute('aria-busy','true');
  notify('');
  try {
    const response = await fetch(`/api/pages/${training.token}/${number}`);
    if (!response.ok) throw Error((await response.json()).error);
    const blob = await response.blob();
    if (objectURL) URL.revokeObjectURL(objectURL);
    objectURL = URL.createObjectURL(blob);
    $('#page-image').src = objectURL;
    await $('#page-image').decode();
    $('#page-image').alt = `${training.title} ${number}쪽`;
    $('#page-image').hidden = false;
    $('#loading').hidden = true;
    await api(`/api/pages/${training.token}/${number}/read`, {});
    seen = Math.max(seen, number);
  } catch(e) { $('#loading').textContent = '자료를 열지 못했습니다. 연수 목록에서 다시 열어 주세요.'; handle(e); }
  finally { busy = false; navigation(); $('#page-stage').setAttribute('aria-busy','false'); }
}
$('#previous').onclick = () => displayPage(page - 1);
$('#next').onclick = () => displayPage(page + 1);
$('#go-sign').onclick = () => { if (seen !== training.pages || busy) return; show('sign'); resizeSignature(); };
$('#back-reader').onclick = () => { show('reader'); };

const canvas = $('#signature'), context = canvas.getContext('2d');
let strokes = [], currentStroke = null;
function resetSignature() { strokes = []; currentStroke = null; resizeSignature(); }
function draw(ctx, width, height) {
  ctx.lineWidth = 2.5; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.strokeStyle = '#1e2925';
  for (const stroke of strokes) {
    ctx.beginPath();
    stroke.forEach((p,i) => i ? ctx.lineTo(p[0]*width,p[1]*height) : ctx.moveTo(p[0]*width,p[1]*height));
    ctx.stroke();
  }
}
function resizeSignature() {
  const rect = canvas.getBoundingClientRect();
  if (!rect.width) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(rect.width*dpr); canvas.height = Math.round(rect.height*dpr);
  context.setTransform(dpr,0,0,dpr,0,0); draw(context,rect.width,rect.height);
}
function point(event) {
  const rect = canvas.getBoundingClientRect();
  return [Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width)),Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height))];
}
canvas.onpointerdown = e => {
  if (currentStroke || e.button !== 0) return;
  e.preventDefault(); canvas.setPointerCapture(e.pointerId);
  currentStroke = {id:e.pointerId, points:[point(e)]}; strokes.push(currentStroke.points);
};
canvas.onpointermove = e => {
  if (!currentStroke || currentStroke.id !== e.pointerId) return;
  currentStroke.points.push(point(e)); resizeSignature();
};
const stopStroke = e => { if (currentStroke?.id === e.pointerId) currentStroke = null; };
canvas.onpointerup = stopStroke; canvas.onpointercancel = stopStroke; canvas.onlostpointercapture = stopStroke;
$('#clear-signature').onclick = resetSignature;
new ResizeObserver(resizeSignature).observe(canvas);
function signatureData() {
  const result = document.createElement('canvas'); result.width = 600; result.height = 200;
  const ctx = result.getContext('2d'); ctx.fillStyle = '#fff'; ctx.fillRect(0,0,600,200); draw(ctx,600,200);
  return result.toDataURL('image/png');
}
function inkLength() {
  return strokes.reduce((sum, s) => sum + s.slice(1).reduce((n,p,i) => n+Math.hypot((p[0]-s[i][0])*600,(p[1]-s[i][1])*200),0),0);
}
$('#sign-form').onsubmit = async e => {
  e.preventDefault(); notify('');
  if (inkLength() < 40) return notify('서명란에 마우스나 손가락으로 서명해 주세요.');
  const name = $('#name').value.trim();
  if (!name) return notify('이름을 입력해 주세요.');
  const button = $('#submit'); button.disabled = true; button.textContent = '저장 중…';
  try {
    const out = await api('/api/submit', {token:training.token,name,signature:signatureData(),agreed:$('#agree').checked});
    show('receipt');
    $('#receipt-text').textContent = `${name} · ${training.title} · ${new Date(out.submittedAt).toLocaleString('ko-KR')}`;
    $('#sign-form').reset(); resetSignature();
  } catch(e) { handle(e); }
  finally { button.disabled = false; button.textContent = '서명 제출하고 완료하기'; }
};

async function loadAdmin() {
  try {
    adminData = await api('/api/admin/data');
    $('#login-form').hidden = true; $('#admin-content').hidden = false;
    $('#admin-courses').innerHTML = adminData.courses.map(c => `<form class="card admin-card" data-id="${c.id}"><div class="source">${c.active ? '진행 중' : '자료 삭제됨 · 기록 보존'} · ${esc(c.source)} · 서명 ${c.count}건</div>${c.error ? `<p>${esc(c.error)}</p>` : ''}<label for="title-${c.id}">연수명</label><input id="title-${c.id}" name="title" value="${esc(c.title)}" maxlength="200" required><label for="pledge-${c.id}">확인 문구</label><textarea id="pledge-${c.id}" name="pledge" maxlength="4000" required>${esc(c.pledge)}</textarea><div class="actions"><button type="submit">내용 저장</button><a href="/api/admin/export/${c.id}/xlsx">엑셀 내려받기</a><a href="/api/admin/export/${c.id}/docx">워드 내려받기</a></div><small>저장하면 열람 중인 참여자는 자료를 다시 열어야 합니다.</small></form>`).join('') || '<div class="empty">[연수자료] 폴더에 PDF나 PNG를 넣어 주세요.</div>';
    const filter = $('#record-filter').value;
    $('#record-filter').innerHTML = '<option value="">전체 연수</option>' + adminData.courses.map(c => `<option value="${c.id}">${esc(c.title)}${c.active ? '' : ' (삭제된 자료)'}</option>`).join('');
    $('#record-filter').value = filter;
    renderRecords(); notify('');
  } catch(e) {
    $('#login-form').hidden = false; $('#admin-content').hidden = true;
    handle(e);
  }
}
function renderRecords() {
  const records = adminData.records.filter(r => !$('#record-filter').value || r.course === $('#record-filter').value);
  $('#record-count').textContent = `${records.length}건`;
  $('#records').innerHTML = records.map(r => `<tr><td>${r.id}</td><td>${esc(r.title)}<br><small>자료 ${esc(r.revision.slice(0,12))} · ${r.pages}쪽</small></td><td>${esc(r.name)}</td><td><img loading="lazy" src="/api/admin/signatures/${r.id}" alt="${esc(r.name)} 서명"></td><td>${esc(new Date(r.submitted_at).toLocaleString('ko-KR'))}</td></tr>`).join('') || '<tr><td colspan="5">아직 제출한 서명이 없습니다.</td></tr>';
}
$('#record-filter').onchange = renderRecords;
$('#login-form').onsubmit = async e => {
  e.preventDefault();
  try { await api('/api/admin/login',{password:$('#password').value}); $('#password').value = ''; await loadAdmin(); }
  catch(e) { handle(e); }
};
$('#admin-refresh').onclick = loadAdmin;
$('#logout').onclick = async () => {
  try { await api('/api/admin/logout',{}); $('#admin-content').hidden = true; $('#login-form').hidden = false; $('#records').replaceChildren(); adminData = null; notify(''); }
  catch(e) { handle(e); }
};
$('#admin-courses').onsubmit = async e => {
  e.preventDefault();
  const form = e.target, button = form.querySelector('button'); button.disabled = true;
  try { await api(`/api/admin/courses/${form.dataset.id}`,{title:form.elements.title.value,pledge:form.elements.pledge.value}); notify('연수명과 확인 문구를 저장했습니다.'); }
  catch(e) { handle(e); }
  finally { button.disabled = false; }
};
if (location.pathname === '/admin') { show('admin'); loadAdmin(); } else { catalog(); }
