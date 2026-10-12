import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import render as render_module  # noqa: E402
from render import PAGE, load_data, load_pinned_schemas, render, validate  # noqa: E402


class CrosswalkTests(unittest.TestCase):
    def setUp(self):
        self.data = load_data()

    def test_real_data_and_generated_page(self):
        validate(self.data)
        self.assertEqual(render(self.data), PAGE.read_text(encoding="utf-8"))

    def test_review_date_has_valid_quoted_datetime_attribute(self):
        page = render(self.data)
        self.assertIn('<time datetime="2026-10-12">2026-10-12</time>', page)

    def test_human_titles_preserve_standard_acronyms(self):
        page = render(self.data)
        self.assertIn('>AI level classification</h3>', page)
        self.assertIn('>FAA learning system</h3>', page)
        self.assertIn('>U.S. maintenance record separation</h3>', page)

    def test_duplicate_row_rejected(self):
        bad = copy.deepcopy(self.data)
        bad["rows"].append(copy.deepcopy(bad["rows"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            validate(bad)

    def test_unknown_field_path_rejected(self):
        bad = copy.deepcopy(self.data)
        bad["rows"][0]["field_paths"] = ["unverified_certification.approved"]
        with self.assertRaisesRegex(ValueError, "field path"):
            validate(bad)

    def test_renamed_upstream_field_rejected(self):
        schemas = load_pinned_schemas()
        fields = schemas["Aviation ML Assurance Card"]["properties"]["odd"]["properties"]
        fields["coverage_artifact_refs"] = fields.pop("coverage_evidence_refs")
        with self.assertRaisesRegex(ValueError, "odd.coverage_evidence_refs"):
            validate(self.data, schemas=schemas)

    def test_deleted_mro_field_rejected(self):
        schemas = load_pinned_schemas()
        del schemas["MRO AI Sign-off Card"]["properties"]["human_review"]["properties"]["authority_ref"]
        with self.assertRaisesRegex(ValueError, "human_review.authority_ref"):
            validate(self.data, schemas=schemas)

    def test_changed_pinned_schema_bytes_rejected(self):
        pins = copy.deepcopy(render_module.SCHEMA_PINS)
        pins[0]["sha256"] = "0" * 64
        with patch.object(render_module, "SCHEMA_PINS", pins):
            with self.assertRaisesRegex(ValueError, "Pinned schema hash mismatch"):
                validate(self.data)

    def test_unknown_source_rejected(self):
        bad = copy.deepcopy(self.data)
        bad["rows"][0]["source_id"] = "invented-authority"
        with self.assertRaisesRegex(ValueError, "Unknown source"):
            validate(bad)

    def test_insecure_source_url_rejected(self):
        bad = copy.deepcopy(self.data)
        bad["sources"][0]["url"] = "http://example.invalid/source"
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            validate(bad)

    def test_html_escapes_source_content(self):
        bad = copy.deepcopy(self.data)
        bad["rows"][0]["connection"] = "<script>alert('unsafe')</script>"
        page = render(bad)
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)


if __name__ == "__main__":
    unittest.main()
