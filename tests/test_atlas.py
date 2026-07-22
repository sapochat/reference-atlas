import json,unittest
from pathlib import Path
from reference_atlas.atlas import render_markdown, validate_atlas
class AtlasTests(unittest.TestCase):
    def test_example(self):
        data=json.loads((Path(__file__).parents[1]/"examples/atlas.json").read_text())
        self.assertEqual(validate_atlas(data),[]); self.assertIn("| Hero |",render_markdown(data))
    def test_missing_attribution(self):
        data={"project":"x","design_read":"x","invariants":["a","b","c"],"hierarchy":{"layout":"x"},"items":[{"target":"x"}]}
        self.assertTrue(any("attribution" in e for e in validate_atlas(data)))
if __name__ == "__main__": unittest.main()
