"""한글에서 편집 가능한 연수 서명부. 외부 프로그램이나 인터넷 없이 생성합니다."""
from datetime import datetime
import io
from zoneinfo import ZoneInfo

from PIL import Image
from hwpx import HwpxDocument


def make_signature_book(title: str, records) -> bytes:
    records = list(records)
    doc = HwpxDocument.new()
    doc.page.set_size(width=59528, height=84188)  # A4, 1 inch = 7200 HWPUNIT
    doc.page.set_margins(left=5669, right=5669, top=4252, bottom=4252, header=1800, footer=1800)
    doc.page.set_page_number(align="CENTER", prefix="- ", suffix=" -")
    title_style = doc.styles.ensure_run(font="맑은 고딕", size=20, bold=True, color="#182D26")
    subtitle_style = doc.styles.ensure_run(font="맑은 고딕", size=12, bold=True)
    body_style = doc.styles.ensure_run(font="맑은 고딕", size=10)
    small_style = doc.styles.ensure_run(font="맑은 고딕", size=9, color="#606A64")
    header_style = doc.styles.ensure_run(font="맑은 고딕", size=10, bold=True)
    center = doc.styles.ensure_paragraph_format(alignment="CENTER", line_spacing_percent=130,
                                               margins={"prev": 0, "next": 0})
    left = doc.styles.ensure_paragraph_format(alignment="LEFT", line_spacing_percent=150,
                                             margins={"prev": 0, "next": 500})
    # 첫 문단의 구역 설정은 보존하고 빈 줄만 제목으로 바꿉니다.
    first = doc.paragraphs[0]
    first.text = "연수 서명부"
    first.char_pr_id_ref = title_style
    first.para_pr_id_ref = center
    doc.add_paragraph(title, char_pr_id_ref=subtitle_style, para_pr_id_ref=center)
    now = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y.%m.%d. %H:%M")
    doc.add_paragraph(f"제출 서명 {len(records)}건  |  작성 일시 {now}", char_pr_id_ref=small_style, para_pr_id_ref=center)
    doc.add_paragraph("아래 명단은 연수자료 열람 후 제출한 이름과 서명을 제출 순서대로 정리한 것입니다.",
                      char_pr_id_ref=body_style, para_pr_id_ref=left)
    width = 48190
    table = doc.add_table(len(records) + 1, 4, width=width,
                          height=2600 + 5200 * len(records), char_pr_id_ref=body_style)
    table.set_column_widths([8, 21, 35, 36])
    table.element.set("repeatHeader", "1")
    table.element.set("pageBreak", "CELL")
    border = doc.styles.ensure_border_fill(border_color="#AEB8B0", border_width="0.12 mm")
    for row in range(len(records) + 1):
        for col in range(4):
            cell = table.cell(row, col)
            cell.set_size(height=2600 if row == 0 else 5200)
            cell.set_margins(left=360, right=360, top=300, bottom=300)
            cell.element.set("borderFillIDRef", border)
            paragraph = cell.paragraphs[0]
            paragraph.char_pr_id_ref = header_style if row == 0 else body_style
            paragraph.para_pr_id_ref = center
            if row == 0:
                cell.element.set("header", "1")
                table.set_cell_shading(row, col, "#EAF0EA")
    for col, heading in enumerate(["번호", "성명", "서명", "제출 일시"]):
        table.set_cell_text(0, col, heading)
    for row, rec in enumerate(records, 1):
        table.set_cell_text(row, 0, str(row))
        table.set_cell_text(row, 1, rec["name"])
        timestamp = datetime.fromisoformat(rec["submitted_at"]).astimezone(ZoneInfo("Asia/Seoul"))
        table.set_cell_text(row, 3, timestamp.strftime("%Y.%m.%d.\n%H:%M:%S"))
        image_data = bytes(rec["signature"])
        item = doc.media.add_image(image_data, "png")
        with Image.open(io.BytesIO(image_data)) as image:
            scale = min(14000 / image.width, 4200 / image.height)
            w, h = round(image.width * scale), round(image.height * scale)
        # 표 셀 안의 문단에 글자처럼 삽입해 이름과 그림이 다른 쪽으로 흩어지지 않게 합니다.
        table.cell(row, 2).paragraphs[0].add_picture(item.item_id, width=w, height=h,
                                                   treat_as_char=True, char_pr_id_ref=body_style)
    if not records:
        doc.add_paragraph("아직 제출된 서명이 없습니다.", char_pr_id_ref=body_style, para_pr_id_ref=left)
    pledges = list(dict.fromkeys(rec["pledge"] for rec in records))
    if pledges:
        doc.add_paragraph("제출 시 확인 내용", char_pr_id_ref=header_style, para_pr_id_ref=left)
        for pledge in pledges:
            doc.add_paragraph(pledge, char_pr_id_ref=small_style, para_pr_id_ref=left)
    table.mark_dirty()
    return doc.to_bytes()
