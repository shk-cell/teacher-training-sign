import io
import unittest
import zipfile
from lxml import etree
from PIL import Image, ImageDraw
from hwpx import HwpxDocument

from signature_book import make_signature_book

NS = {"hp": "http://www.hancom.co.kr/hwpml/2011/paragraph"}


class SignatureBookTests(unittest.TestCase):
    def records(self, count):
        image = Image.new("RGB", (600, 200), "white")
        ImageDraw.Draw(image).line([(20, 100), (140, 30), (280, 150), (460, 60)], fill="black", width=5)
        stream = io.BytesIO()
        image.save(stream, format="PNG")
        return [{"name": f"교직원 {i+1}", "signature": stream.getvalue(), "submitted_at": "2026-11-05T09:30:00+09:00",
                 "pledge": "교육자료를 확인했습니다."} for i in range(count)]

    def test_all_names_and_images_are_in_their_table_cells(self):
        records = self.records(27)
        raw = make_signature_book("정보보안 <특별> 연수", records)
        with zipfile.ZipFile(io.BytesIO(raw)) as package:
            self.assertEqual(package.read("mimetype"), b"application/hwp+zip")
            xml = etree.fromstring(package.read("Contents/section0.xml"))
            rows = xml.findall(".//hp:tbl/hp:tr", NS)
            self.assertEqual(len(rows), 28)
            self.assertEqual(len(xml.findall(".//hp:pic", NS)), 27)
            self.assertEqual(xml.find(".//hp:tbl", NS).get("repeatHeader"), "1")
            for row, record in zip(rows[1:], records):
                cells = row.findall("hp:tc", NS)
                self.assertIn(record["name"], "".join(cells[1].itertext()))
                self.assertEqual(len(cells[2].findall(".//hp:pic", NS)), 1)
                self.assertEqual(cells[2].find(".//hp:pic/hp:pos", NS).get("treatAsChar"), "1")
        with HwpxDocument.open(io.BytesIO(raw)) as doc:
            self.assertEqual(doc.tables[0].row_count, 28)

    def test_empty_roster_is_a_valid_document(self):
        raw = make_signature_book("빈 연수", [])
        with zipfile.ZipFile(io.BytesIO(raw)) as package:
            text = package.read("Contents/section0.xml").decode()
            self.assertIn("아직 제출된 서명이 없습니다", text)
