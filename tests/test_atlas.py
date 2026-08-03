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
    def test_invalid_hierarchy_is_validation_error(self):
        data={"project":"x","design_read":"x","invariants":["a","b","c"],"hierarchy":"layout","items":[{"target":"x","reference":"x","borrow":"x","do_not_copy":"x","build_implication":"x","mobile":"x","attribution":"x"}]}
        self.assertIn("hierarchy must be an object", validate_atlas(data))
        with self.assertRaisesRegex(ValueError, "hierarchy must be an object"):
            render_markdown(data)
    def test_invalid_items_shape_is_validation_error(self):
        data={"project":"x","design_read":"x","invariants":["a","b","c"],"hierarchy":{"layout":"x"},"items":"target"}
        self.assertIn("items must be a list", validate_atlas(data))
        with self.assertRaisesRegex(ValueError, "items must be a list"):
            render_markdown(data)
    def test_scalar_item_is_validation_error(self):
        data={"project":"x","design_read":"x","invariants":["a","b","c"],"hierarchy":{"layout":"x"},"items":[42]}
        self.assertIn("item 0 must be an object", validate_atlas(data))
        with self.assertRaisesRegex(ValueError, "item 0 must be an object"):
            render_markdown(data)
    def test_invalid_item_field_type_is_validation_error(self):
        data={"project":"x","design_read":"x","invariants":["a","b","c"],"hierarchy":{"layout":"x"},"items":[{"target":123,"reference":"x","borrow":"x","do_not_copy":"x","build_implication":"x","mobile":"x","attribution":"x"}]}
        self.assertIn("item 0 field must be text: target", validate_atlas(data))
        with self.assertRaisesRegex(ValueError, "item 0 field must be text: target"):
            render_markdown(data)
if __name__ == "__main__": unittest.main()
