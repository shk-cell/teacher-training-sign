// 연수 내용 설정 파일
// 다른 연수에 쓰려면 이 파일과 교육자료 PDF만 바꾸면 됩니다.

window.TRAINING = {
  // 구글 Apps Script 웹 앱 배포 URL (README의 2단계 참고)
  SCRIPT_URL: "https://script.google.com/macros/s/AKfycbwHxFK4ImfnoanQet7Fwy5d6EDaVCne2u402gNCIa9Pa3m56VIMRz0xaBxccSO4wguz4w/exec",

  // 연수 회차 구분값. 다음 연수 때 바꾸면 "이미 제출함" 표시가 초기화되고, 서명부도 따로 만들어집니다.
  COURSE_ID: "2026-bupyeong-security",

  TITLE: "2026학년도 부평중학교 전교직원 대상 정보보안 교육",
  // 제목 위 작은 글씨와 제목 아래 안내 줄. 비워 두면 표시하지 않습니다.
  EYEBROW: "",
  META: [],

  // 교육자료 PDF (저장소에 함께 올린 파일). 모든 쪽을 넘겨 본 사람만 서명할 수 있습니다.
  PDF: "material.pdf",

  // 한 쪽에 최소 몇 초 머물러야 '읽음'으로 칠지. 0이면 넘기기만 해도 읽음 처리됩니다.
  MIN_SECONDS_PER_PAGE: 0,

  PLEDGE: "본인은 2026학년도 부평중학교 정보보안 교육자료를 끝까지 열람하였으며, 업무 중 알게 된 개인정보와 업무자료를 보호하고 인천광역시교육청 정보보안 기본지침을 성실히 지킬 것을 서약합니다.",
};
