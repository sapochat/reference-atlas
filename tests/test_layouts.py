"""Layout contracts, lossless details, and raw-HTML-enabled parsing."""
import copy
import json
from pathlib import Path
import unittest

from reference_atlas.atlas import REQUIRED_ITEM, render_markdown
from test_rendering import RenderedDocument
import test_rendering
from test_v2_rendering import Document, atlas, strings


ROOT = Path(__file__).parents[1]


class LayoutTests(unittest.TestCase):
    def test_defaults_and_explicit_default_layouts_are_byte_identical(self):
        for name, layout in (("atlas", "table"), ("atlas-v2", "sections")):
            data = json.loads((ROOT / f"examples/{name}.json").read_text())
            expected = (ROOT / f"docs/example-{name}.md").read_bytes()
            with self.subTest(name=name):
                self.assertEqual(render_markdown(data).encode(), expected)
                self.assertEqual(render_markdown(data, layout=None).encode(), expected)
                self.assertEqual(render_markdown(data, layout=layout).encode(), expected)

    def test_invalid_layout_values_raise_value_error(self):
        for layout in ("", "grid", "TABLE", False, 1, [], {}):
            with self.subTest(layout=layout), self.assertRaisesRegex(ValueError, "layout"):
                render_markdown(atlas(), layout=layout)

    def test_layout_is_keyword_only(self):
        with self.assertRaises(TypeError):
            render_markdown(atlas(), "table")

    def test_legacy_sections_keep_all_fields_and_root_metadata(self):
        data = test_rendering.RenderingTests.atlas()
        data["schema_version"] = 1
        data["items"] = [{key: f"first {key}" for key in REQUIRED_ITEM},
                         {key: f"second {key}" for key in REQUIRED_ITEM}]
        output = render_markdown(data, layout="sections")
        doc = Document(output)
        for value in strings(data):
            self.assertIn(value, doc.text)
        self.assertIn("Schema version: 1", doc.text)
        self.assertNotIn("table", [tag for tag, _ in doc.tags])
        self.assertEqual(len(RenderedDocument(output).texts("h3")), 2)
        for key in REQUIRED_ITEM:
            self.assertIn(key.replace("_", " ").capitalize() + ":", doc.text)

    def test_v2_table_is_seven_columns_with_lossless_full_details(self):
        data = atlas()
        data["asset_root"] = "custom-assets"
        data["sources"]["source-two"] = dict(data["sources"]["source-one"], title="Second source")
        data["items"][0]["references"].append({"source": "source-two", "borrow": "Second borrow", "do_not_copy": "Second avoid", "evidence": "second.png"})
        output = render_markdown(data, layout="table")
        doc = Document(output)
        for value in strings(data):
            self.assertIn(value, doc.text)
        for value in ("source-one", "source-two", "Schema version: 2", "Asset root: custom-assets"):
            self.assertIn(value, doc.text)
        self.assertIn("## Table overview", output)
        self.assertIn("## Full details", output)
        # The preexisting full renderer body must survive unchanged.
        self.assertTrue(output.endswith(render_markdown(data).split("\n", 2)[2]))
        parsed = RenderedDocument(output)
        self.assertEqual(len(parsed.texts("th")), 7)
        self.assertEqual(len(parsed.texts("td")), 7 * len(data["items"]))
        self.assertEqual(len(parsed.texts("tr")), len(data["items"]) + 1)

    def test_original_only_table_and_empty_checks_remain_explicit(self):
        data = atlas()
        data["sources"] = {}
        data["hierarchy"] = {}
        data["items"] = data["items"][1:]
        data["items"][0]["checks"] = []
        doc = Document(render_markdown(data, layout="table"))
        for value in ("No sources", "No checks reported", "Original design value", "Asset root: assets"):
            self.assertIn(value, doc.text)

    def test_new_layouts_are_literal_and_have_no_injected_columns(self):
        payload = '  **bold** [link](https://example.com) ![img](x) <script>x</script> &copy; \\\\|\r\n# heading\n| fake | row |  '
        legacy = test_rendering.RenderingTests.atlas(payload)
        v2 = atlas()
        # Replace every unrestricted prose field while keeping IDs/enums/locators valid.
        def poison(value, key=None):
            if isinstance(value, dict):
                return {k: poison(v, k) for k, v in value.items()}
            if isinstance(value, list):
                return [poison(v, key) for v in value]
            if isinstance(value, str) and key not in {"id", "source", "decision", "status", "criterion", "locator", "url", "evidence"}:
                return payload
            return value
        v2 = poison(v2)
        for data, layout in ((legacy, "sections"), (v2, "table")):
            with self.subTest(layout=layout):
                before = copy.deepcopy(data)
                output = render_markdown(data, layout=layout)
                self.assertEqual(data, before)
                self.assertEqual(output, render_markdown(data, layout=layout))
                doc = Document(output)
                self.assertIn(payload.replace("\r\n", "\n"), doc.text)
                allowed = {"h1", "h2", "h3", "h4", "p", "strong", "ul", "li", "br", "table", "thead", "tbody", "tr", "th", "td"}
                for tag, attrs in doc.tags:
                    self.assertIn(tag, allowed)
                    self.assertEqual(attrs, [])
                if layout == "table":
                    parsed = RenderedDocument(output)
                    self.assertEqual(len(parsed.texts("th")), 7)
                    self.assertEqual(len(parsed.texts("td")), 14)
                    for cell in parsed.texts("td"):
                        self.assertNotIn("<br>", cell)

    def test_new_layout_goldens_match_current_examples(self):
        for name, layout, golden in (("atlas", "sections", "example-atlas-sections.md"),
                                     ("atlas-v2", "table", "example-atlas-v2-table.md")):
            with self.subTest(layout=layout):
                data = json.loads((ROOT / f"examples/{name}.json").read_text())
                output = render_markdown(data, layout=layout)
                self.assertEqual(output.encode(), (ROOT / "docs" / golden).read_bytes())
                self.assertEqual(output, render_markdown(data, layout=layout))


if __name__ == "__main__":
    unittest.main()
