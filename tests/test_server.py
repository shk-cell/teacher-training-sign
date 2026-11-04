import base64
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw
from openpyxl import load_workbook
from docx import Document

from server import create_app


class TrainingTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[1] / 'data' / 'tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.root = Path(self.temp.name)
        self.materials = self.root / "연수자료"
        self.materials.mkdir()
        self.pdf(self.materials / "정보보안.pdf", 2)
        self.app = create_app(self.root, password="test-password")
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def pdf(self, path, count):
        with pymupdf.open() as doc:
            for i in range(count):
                doc.new_page().insert_text((40, 40), f"Training page {i + 1}")
            doc.save(path)

    def start(self):
        courses = self.client.get("/api/courses").get_json()
        cid = courses[0]["id"]
        out = self.client.post(f"/api/courses/{cid}/start", json={})
        self.assertEqual(out.status_code, 200)
        return cid, out.get_json()["token"]

    def signature(self, blank=False):
        image = Image.new("RGB", (600, 200), "white")
        if not blank:
            ImageDraw.Draw(image).line([(10, 90), (110, 20), (200, 140), (300, 80)], fill="black", width=4)
        stream = io.BytesIO()
        image.save(stream, format="PNG")
        return "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode()

    def read(self, token, count=2):
        for n in range(1, count + 1):
            image = self.client.get(f"/api/pages/{token}/{n}")
            self.assertEqual(image.status_code, 200)
            self.assertEqual(image.mimetype, "image/png")
            self.assertEqual(self.client.post(f"/api/pages/{token}/{n}/read", json={}).status_code, 200)

    def submit(self, token, **extra):
        return self.client.post("/api/submit", json={"token": token, "name": "홍길동", "signature": self.signature(), "agreed": True, **extra})

    def login(self):
        self.assertEqual(self.client.post("/api/admin/login", json={"password":"test-password"}).status_code, 200)

    def test_sequential_reading_and_idempotent_submission(self):
        _, token = self.start()
        self.assertEqual(self.submit(token).status_code, 400)
        self.assertEqual(self.client.post(f"/api/pages/{token}/2/read", json={}).status_code, 403)
        self.read(token)
        first = self.submit(token)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(self.submit(token).get_json()["id"], first.get_json()["id"])
        self.login()
        self.assertEqual(len(self.client.get('/api/admin/data').get_json()['records']), 1)

    def test_folder_changes_and_grouped_images(self):
        cid, _ = self.start()
        group = self.materials / "안전교육"
        group.mkdir()
        Image.new('RGB', (300, 200), 'white').save(group / '01.png')
        Image.new('RGB', (300, 200), 'green').save(group / '02.png')
        courses = self.client.get('/api/courses').get_json()
        grouped = next(c for c in courses if c['source'].endswith('/'))
        self.assertEqual(grouped['pages'], 2)
        token = self.client.post(f"/api/courses/{grouped['id']}/start", json={}).get_json()['token']
        self.read(token)
        (self.materials / '정보보안.pdf').unlink()
        self.assertEqual(len(self.client.get('/api/courses').get_json()), 1)
        self.assertEqual(self.client.post(f'/api/courses/{cid}/start', json={}).status_code, 404)

    def test_replacement_invalidates_old_reader(self):
        _, token = self.start()
        path = self.materials / '정보보안.pdf'
        path.unlink()
        self.pdf(path, 3)
        self.client.get('/api/courses')
        self.assertEqual(self.client.get(f'/api/pages/{token}/1').status_code, 409)

    def test_admin_is_local_and_private(self):
        cid, _ = self.start()
        self.assertEqual(self.client.get('/api/admin/data').status_code, 401)
        self.assertEqual(self.client.get(f'/api/admin/export/{cid}/xlsx').status_code, 401)
        self.assertEqual(self.client.get('/data/training.sqlite3').status_code, 404)
        remote = {'REMOTE_ADDR':'192.168.1.50'}
        self.assertEqual(self.client.post('/api/admin/login', json={'password':'test-password'}, environ_overrides=remote).status_code, 403)
        self.login()
        self.assertEqual(self.client.get('/api/admin/data', environ_overrides=remote).status_code, 403)
        self.assertEqual(self.client.post('/api/admin/logout', json={}, headers={'Origin':'https://other.example'}).status_code, 403)

    def test_exports_embed_signatures_and_preserve_deleted_material_records(self):
        cid, token = self.start()
        self.read(token)
        self.assertEqual(self.submit(token, name='=홍길동').status_code, 200)
        self.login()
        self.client.post(f'/api/admin/courses/{cid}', json={'title':'새 연수명','pledge':'새 문구'})
        (self.materials / '정보보안.pdf').unlink()
        self.client.get('/api/courses')
        data = self.client.get('/api/admin/data').get_json()
        self.assertEqual(data['courses'][0]['active'], 0)
        self.assertEqual(data['records'][0]['title'], '정보보안')
        self.assertEqual(self.client.get('/api/admin/signatures/1').mimetype, 'image/png')
        for kind in ['xlsx', 'docx']:
            response = self.client.get(f'/api/admin/export/{cid}/{kind}')
            self.assertEqual(response.status_code, 200)
            with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
                self.assertTrue(any('/media/' in name for name in archive.namelist()))
            if kind == 'xlsx':
                workbook = load_workbook(io.BytesIO(response.data))
                self.assertEqual(workbook.active['C2'].value, '=홍길동')
                self.assertEqual(workbook.active['C2'].data_type, 's')
                self.assertEqual(workbook.active['B2'].value, '정보보안')
                self.assertEqual(len(workbook.active._images), 1)
            else:
                document = Document(io.BytesIO(response.data))
                self.assertEqual(document.tables[0].cell(1, 1).text, '=홍길동')
                self.assertEqual(len(document.inline_shapes), 1)

    def test_blank_signature_rejected_and_same_name_does_not_overwrite(self):
        _, token = self.start()
        self.read(token)
        self.assertEqual(self.submit(token, signature=self.signature(blank=True)).status_code, 400)
        self.assertEqual(self.submit(token).status_code, 200)
        _, second = self.start()
        self.read(second)
        self.assertEqual(self.submit(second).status_code, 200)
        self.login()
        self.assertEqual(len(self.client.get('/api/admin/data').get_json()['records']), 2)

    def test_admin_text_edit_invalidates_reader(self):
        cid, token = self.start()
        self.login()
        self.assertEqual(self.client.post(f'/api/admin/courses/{cid}', json={'title':'제목 변경','pledge':'동의 내용 변경'}).status_code, 200)
        self.assertEqual(self.client.get(f'/api/pages/{token}/1').status_code, 403)

    def test_bad_pdf_is_visible_but_cannot_be_opened(self):
        (self.materials / '정보보안.pdf').write_bytes(b'broken pdf')
        courses = self.client.get('/api/courses').get_json()
        self.assertTrue(courses[0]['error'])
        self.assertEqual(self.client.post(f"/api/courses/{courses[0]['id']}/start", json={}).status_code, 409)


if __name__ == '__main__':
    unittest.main()
