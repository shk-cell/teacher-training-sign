/**
 * 교사연수 서명 - 구글 시트 Apps Script
 *
 * 하는 일
 *  1. 웹 앱(doPost): GitHub Pages에서 보낸 제출 내용을 '제출' 시트에 한 줄씩 기록하고,
 *     서명 이미지는 내 구글 드라이브의 '교사연수서명_서명이미지' 폴더에 PNG로 저장합니다.
 *  2. 시트 메뉴 [교사연수 서명 → 서명부 만들기]: 제출 명단과 서명을 넣은 구글 문서를 만듭니다.
 *     이 문서를 PDF로 내려받아 내부결재 증빙으로 첨부하면 됩니다.
 *
 * 설치 방법은 저장소의 README.md를 보세요.
 */

const SHEET_NAME = "제출";
const FOLDER_NAME = "교사연수서명_서명이미지";
const HEADERS = ["제출일시", "연수ID", "연수명", "소속", "직위·직종", "성명", "이수확인", "서약", "서명파일ID"];
const MAX_SIG_CHARS = 300000;

/* ---------- 웹 앱 ---------- */

function doPost(e) {
  try {
    const d = JSON.parse(e.postData.contents);
    const org = clean_(d.org, 60), role = clean_(d.role, 20), name = clean_(d.name, 30);
    const course = clean_(d.course, 40), title = clean_(d.title, 100), viewed = clean_(d.viewed || d.quiz, 40);
    const sig = String(d.signature || "");
    if (!org || !role || !name || !course) return json_({ ok: false, error: "필수 항목이 비어 있습니다." });
    if (d.agreed !== true) return json_({ ok: false, error: "서약 동의가 없습니다." });
    if (!sig.startsWith("data:image/png;base64,") || sig.length > MAX_SIG_CHARS) return json_({ ok: false, error: "서명 이미지가 올바르지 않습니다." });

    const lock = LockService.getScriptLock();
    lock.waitLock(20000);
    try {
      const now = new Date();
      const blob = Utilities.newBlob(Utilities.base64Decode(sig.split(",")[1]), "image/png",
        `${course}_${org}_${name}_${Utilities.formatDate(now, "Asia/Seoul", "yyyyMMdd-HHmmss")}.png`);
      const file = folder_().createFile(blob);
      sheet_().appendRow([now, course, title, org, role, name, viewed, "동의", file.getId()]);
      return json_({ ok: true, submittedAt: now.getTime() });
    } finally {
      lock.releaseLock();
    }
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

function doGet() {
  return json_({ ok: true, message: "교사연수 서명 수집용 웹 앱입니다." });
}

/* ---------- 시트 메뉴 ---------- */

function onOpen() {
  SpreadsheetApp.getUi().createMenu("교사연수 서명")
    .addItem("서명부 만들기 (구글 문서)", "makeRoster")
    .addItem("처음 설정 (시트·폴더 만들기)", "setup")
    .addToUi();
}

function setup() {
  const url = spreadsheet_().getUrl();
  sheet_();
  folder_();
  const msg = "'제출' 시트와 드라이브의 '" + FOLDER_NAME + "' 폴더를 준비했습니다.\n제출이 기록될 시트: " + url;
  try { SpreadsheetApp.getUi().alert(msg); } catch (err) { Logger.log(msg); }
}

function makeRoster() {
  const ui = SpreadsheetApp.getUi();
  const rows = sheet_().getDataRange().getValues().slice(1).filter(r => r[1]);
  if (!rows.length) return ui.alert("아직 제출된 내용이 없습니다.");

  const latestCourse = rows[rows.length - 1][1];
  const c = ui.prompt("서명부 만들기", `연수ID를 입력하세요. (비워 두면 최근 연수: ${latestCourse})`, ui.ButtonSet.OK_CANCEL);
  if (c.getSelectedButton() !== ui.Button.OK) return;
  const course = c.getResponseText().trim() || latestCourse;

  const t = ui.prompt("서명부 만들기", "전체 대상 인원을 입력하세요. (이수율 계산용, 모르면 비워 두기)", ui.ButtonSet.OK_CANCEL);
  if (t.getSelectedButton() !== ui.Button.OK) return;
  const total = parseInt(t.getResponseText(), 10) || 0;

  const o = ui.prompt("서명부 만들기", "기관명을 입력하세요. (예: ○○초등학교, 비워 두면 생략)", ui.ButtonSet.OK_CANCEL);
  if (o.getSelectedButton() !== ui.Button.OK) return;
  const orgName = o.getResponseText().trim();

  // 같은 소속·성명이 여러 번 제출했으면 마지막 제출만 남깁니다.
  const byPerson = new Map();
  rows.filter(r => r[1] === course).forEach(r => byPerson.set(r[3] + "|" + r[5], r));
  const list = [...byPerson.values()].sort((a, b) => String(a[3]).localeCompare(String(b[3]), "ko") || String(a[5]).localeCompare(String(b[5]), "ko"));
  if (!list.length) return ui.alert(`연수ID '${course}'로 제출된 내용이 없습니다.`);

  const title = list[0][2] || course;
  const fmtDay = d => Utilities.formatDate(new Date(d), "Asia/Seoul", "yyyy. MM. dd.");
  const fmtTime = d => Utilities.formatDate(new Date(d), "Asia/Seoul", "yyyy. MM. dd. HH:mm");
  const times = list.map(r => new Date(r[0]).getTime());
  const period = `${fmtDay(Math.min(...times))} ~ ${fmtDay(Math.max(...times))}`;
  const rate = total ? Math.round(list.length / total * 1000) / 10 + "%" : "-";

  const doc = DocumentApp.create(`${title} 서명부 (${Utilities.formatDate(new Date(), "Asia/Seoul", "yyyyMMdd")})`);
  const body = doc.getBody();
  body.setMarginTop(42).setMarginBottom(42).setMarginLeft(42).setMarginRight(42);
  body.appendParagraph(`${title} 서명부`).setHeading(DocumentApp.ParagraphHeading.HEADING1).setAlignment(DocumentApp.HorizontalAlignment.CENTER);
  if (orgName) body.appendParagraph(orgName).setAlignment(DocumentApp.HorizontalAlignment.CENTER);

  const sum = body.appendTable([
    ["연수명", title],
    ["연수 방법", "온라인 연수 (교육자료 전체 열람 후 서약·서명)"],
    ["연수 기간", period],
    ["대상", total ? `전 교직원 ${total}명` : "전 교직원"],
    ["이수 인원", `${list.length}명 (이수율 ${rate})`],
  ]);
  for (let i = 0; i < sum.getNumRows(); i++) sum.getCell(i, 0).setBackgroundColor("#eeeeee").setWidth(90);
  body.appendParagraph("");

  const table = body.appendTable([["연번", "부서·교과", "직위·직종", "성명", "제출 일시", "서명"]]);
  const head = table.getRow(0);
  for (let i = 0; i < head.getNumCells(); i++) head.getCell(i).setBackgroundColor("#eeeeee");
  list.forEach((r, i) => {
    const row = table.appendTableRow();
    [String(i + 1), r[3], r[4], r[5], fmtTime(r[0])].forEach(v => row.appendTableCell(String(v)));
    const cell = row.appendTableCell("");
    try {
      const img = cell.getChild(0).asParagraph().appendInlineImage(DriveApp.getFileById(r[8]).getBlob());
      const w = 100, h = Math.round(img.getHeight() * w / img.getWidth());
      img.setWidth(w).setHeight(h);
    } catch (err) {
      cell.setText("(서명 파일 없음)");
    }
  });
  body.appendParagraph(`출력일 ${fmtTime(new Date())}`).setAlignment(DocumentApp.HorizontalAlignment.RIGHT);
  doc.saveAndClose();

  const html = HtmlService.createHtmlOutput(
    `<p style="font-family:sans-serif">서명부를 만들었습니다. (${list.length}명)</p>
     <p style="font-family:sans-serif"><a href="${doc.getUrl()}" target="_blank">서명부 문서 열기</a></p>
     <p style="font-family:sans-serif;color:#666;font-size:13px">문서에서 [파일 → 다운로드 → PDF]로 저장해 결재에 첨부하세요.</p>`
  ).setWidth(360).setHeight(160);
  ui.showModalDialog(html, "서명부 완료");
}

/* ---------- 내부 함수 ---------- */

function spreadsheet_() {
  // 웹 앱으로 실행될 때는 '현재 시트'가 없을 수 있어서, 시트 ID를 저장해 두고 그 ID로 엽니다.
  const props = PropertiesService.getScriptProperties();
  const active = SpreadsheetApp.getActiveSpreadsheet();
  if (active) {
    if (props.getProperty("SHEET_ID") !== active.getId()) props.setProperty("SHEET_ID", active.getId());
    return active;
  }
  const id = props.getProperty("SHEET_ID");
  if (id) {
    try { return SpreadsheetApp.openById(id); } catch (err) { /* 시트가 지워졌으면 새로 만듭니다 */ }
  }
  const ss = SpreadsheetApp.create("교사연수 서명 제출");
  props.setProperty("SHEET_ID", ss.getId());
  return ss;
}

function sheet_() {
  const ss = spreadsheet_();
  let sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) {
    sh = ss.insertSheet(SHEET_NAME);
    sh.appendRow(HEADERS);
    sh.setFrozenRows(1);
    sh.getRange(1, 1, 1, HEADERS.length).setFontWeight("bold").setBackground("#eeeeee");
  }
  return sh;
}

function folder_() {
  const props = PropertiesService.getScriptProperties();
  const id = props.getProperty("FOLDER_ID");
  if (id) {
    try { return DriveApp.getFolderById(id); } catch (err) { /* 폴더가 지워졌으면 새로 만듭니다 */ }
  }
  const f = DriveApp.createFolder(FOLDER_NAME);
  props.setProperty("FOLDER_ID", f.getId());
  return f;
}

function clean_(v, max) {
  const s = String(v == null ? "" : v).replace(/[\u0000-\u001f]/g, "").trim().slice(0, max);
  // =, +, -, @로 시작하면 시트가 수식으로 읽으므로 글자로 저장합니다.
  return /^[=+\-@]/.test(s) ? "'" + s : s;
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
