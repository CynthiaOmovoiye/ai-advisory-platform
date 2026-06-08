"""Tests for file-upload validation + the malware-scan gate (security-review §5)."""

import unittest

from app.domain.access import Principal, Role
from app.domain.uploads import InvalidUpload, validate_upload
from app.errors import Conflict, NotFound
from app.infra.db import Base, make_engine, make_session_factory
from app.infra.storage import InMemoryStorage
from app.repositories.orm import Assessment, Organization
from app.repositories.sql import (
    SqlAssessmentRepository,
    SqlAuditSink,
    SqlDocumentRepository,
)
from app.services.document_service import DocumentService, UnprocessableUpload

PDF = b"%PDF-1.4\n...content..."
DOCX = b"PK\x03\x04" + b"\x00" * 40
ORG = "org-a"
consultant = Principal(user_id="c1", global_roles=frozenset({Role.CONSULTANT}))


class TestValidation(unittest.TestCase):
    def test_valid_pdf(self):
        v = validate_upload(
            filename="a.pdf", content_type="application/pdf", data=PDF, max_bytes=1000
        )
        self.assertEqual(v.extension, ".pdf")
        self.assertTrue(v.sha256)

    def test_valid_docx_zip_magic(self):
        v = validate_upload(
            filename="a.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            data=DOCX,
            max_bytes=1000,
        )
        self.assertEqual(v.extension, ".docx")

    def test_disallowed_extension(self):
        with self.assertRaises(InvalidUpload):
            validate_upload(
                filename="a.exe", content_type="application/pdf", data=PDF, max_bytes=1000
            )

    def test_mime_mismatch(self):
        with self.assertRaises(InvalidUpload):
            validate_upload(filename="a.pdf", content_type="text/html", data=PDF, max_bytes=1000)

    def test_magic_byte_spoof_rejected(self):
        # A .pdf-named file whose bytes are NOT a PDF (renamed/spoofed) is rejected.
        with self.assertRaises(InvalidUpload):
            validate_upload(
                filename="evil.pdf",
                content_type="application/pdf",
                data=b"<html>not a pdf</html>",
                max_bytes=1000,
            )

    def test_too_large(self):
        with self.assertRaises(InvalidUpload):
            validate_upload(filename="a.pdf", content_type="application/pdf", data=PDF, max_bytes=5)


class TestScanGate(unittest.TestCase):
    def setUp(self):
        engine = make_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.session = make_session_factory(engine)()
        self.session.add(Organization(id=ORG, name="A", slug="a"))
        self.session.add(
            Assessment(
                id="a1",
                organization_id=ORG,
                template_name="t",
                ruleset_name="baseline",
                ruleset_version=1,
            )
        )
        self.session.commit()
        self.storage = InMemoryStorage()
        self.svc = DocumentService(
            documents=SqlDocumentRepository(self.session),
            assessments=SqlAssessmentRepository(self.session),
            storage=self.storage,
            audit=SqlAuditSink(self.session),
        )

    def tearDown(self):
        self.session.close()

    def test_upload_is_pending_and_stored_under_opaque_key(self):
        doc = self.svc.upload(
            consultant, ORG, "a1", filename="r.pdf", content_type="application/pdf", data=PDF
        )
        self.assertEqual(doc.scan_status, "pending")
        self.assertTrue(doc.storage_key.startswith(f"documents/{ORG}/"))
        self.assertNotIn("r.pdf", doc.storage_key)  # opaque, not the user's filename
        self.assertIn(doc.storage_key, self.storage.objects)

    def test_download_blocked_until_scanned_clean(self):
        doc = self.svc.upload(
            consultant, ORG, "a1", filename="r.pdf", content_type="application/pdf", data=PDF
        )
        # THE GATE: pending document is not downloadable
        with self.assertRaises(Conflict):
            self.svc.download_url(consultant, ORG, doc.id)
        # worker scans -> clean -> now downloadable
        self.svc.scan(ORG, doc.id, "worker")
        url = self.svc.download_url(consultant, ORG, doc.id)
        self.assertTrue(url)

    def test_invalid_upload_rejected(self):
        with self.assertRaises(UnprocessableUpload):
            self.svc.upload(
                consultant, ORG, "a1", filename="x.exe", content_type="application/pdf", data=PDF
            )

    def test_cross_tenant_document_not_found(self):
        doc = self.svc.upload(
            consultant, ORG, "a1", filename="r.pdf", content_type="application/pdf", data=PDF
        )
        other = Principal(user_id="x", org_roles={"org-b": frozenset({Role.CONSULTANT})})
        with self.assertRaises(NotFound):
            self.svc.download_url(other, "org-b", doc.id)


if __name__ == "__main__":
    unittest.main()
