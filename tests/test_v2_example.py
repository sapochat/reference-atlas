"""The committed v2 draft must be useful without inventing verification."""
import json
from pathlib import Path
import unittest

from reference_atlas import render_markdown, validate_atlas

ROOT = Path(__file__).resolve().parents[1]


class V2ExampleTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "examples/atlas-v2.json").read_text(encoding="utf-8"))

    def test_v2_example_is_structurally_valid(self):
        self.assertEqual(validate_atlas(self.data), [])

    def test_committed_render_has_not_drifted(self):
        self.assertEqual(
            render_markdown(self.data).encode("utf-8"),
            (ROOT / "docs/example-atlas-v2.md").read_bytes(),
        )

    def test_example_contains_real_synthetic_evidence(self):
        base = ROOT / "examples"
        asset_root = (base / self.data["asset_root"]).resolve()
        for source in self.data["sources"].values():
            asset = (base / source["locator"]).resolve()
            self.assertTrue(asset.is_relative_to(asset_root))
            self.assertTrue(asset.is_file())
        self.assertEqual(
            (asset_root / "reference-atlas-example.svg").read_bytes(),
            (ROOT / "docs/reference-atlas-example.svg").read_bytes(),
        )

    def test_example_does_not_fabricate_passed_checks(self):
        for item in self.data["items"]:
            for check in item["checks"]:
                self.assertEqual(check["status"], "not_checked")
        self.assertTrue(any("original_design" in item for item in self.data["items"]))
        rendered = render_markdown(self.data)
        self.assertIn("Original synthetic diagram", rendered)
        self.assertIn("Attribution footer", rendered)
        self.assertIn("No implementation has been built", rendered)


if __name__ == "__main__":
    unittest.main()
