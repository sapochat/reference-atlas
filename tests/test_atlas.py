import json,unittest
from pathlib import Path
from reference_atlas.atlas import render_markdown, validate_atlas
class AtlasTests(unittest.TestCase):
    @staticmethod
    def example():
        return {
            "project":"x",
            "design_read":"x",
            "invariants":["a","b","c"],
            "hierarchy":{"layout":"x"},
            "items":[{
                "target":"x", "reference":"x", "borrow":"x",
                "do_not_copy":"x", "build_implication":"x",
                "mobile":"x", "attribution":"x",
            }],
        }

    def test_non_object_atlas_is_validation_error(self):
        for data in (None, [], "atlas"):
            with self.subTest(data=data):
                self.assertEqual(validate_atlas(data), ["atlas must be an object"])
                with self.assertRaisesRegex(ValueError, "atlas must be an object"):
                    render_markdown(data)

    def test_example(self):
        data=json.loads((Path(__file__).parents[1]/"examples/atlas.json").read_text())
        self.assertEqual(validate_atlas(data),[]); self.assertIn("| Hero |",render_markdown(data))
    def test_missing_attribution(self):
        data={"project":"x","design_read":"x","invariants":["a","b","c"],"hierarchy":{"layout":"x"},"items":[{"target":"x"}]}
        self.assertTrue(any("attribution" in e for e in validate_atlas(data)))
    def test_invalid_hierarchy_is_validation_error(self):
        data={"project":"x","design_read":"x","invariants":["a","b","c"],"hierarchy":"layout","items":[{"target":"x","reference":"x","borrow":"x","do_not_copy":"x","build_implication":"x","mobile":"x","attribution":"x"}]}
        self.assertIn("hierarchy must be a non-empty object", validate_atlas(data))
        with self.assertRaisesRegex(ValueError, "hierarchy must be a non-empty object"):
            render_markdown(data)
    def test_invalid_items_shape_is_validation_error(self):
        data=self.example(); data["items"]="not-a-list"
        self.assertIn("items must be a non-empty list", validate_atlas(data))
        with self.assertRaisesRegex(ValueError, "items must be a non-empty list"):
            render_markdown(data)

        for value in (None, 0, False):
            with self.subTest(value=value):
                data=self.example(); data["items"]=value
                self.assertIn("items must be a non-empty list", validate_atlas(data))
                with self.assertRaisesRegex(ValueError, "items must be a non-empty list"):
                    render_markdown(data)
    def test_scalar_item_is_validation_error(self):
        data={"project":"x","design_read":"x","invariants":["a","b","c"],"hierarchy":{"layout":"x"},"items":[42]}
        self.assertIn("item 0 must be an object", validate_atlas(data))
        with self.assertRaisesRegex(ValueError, "item 0 must be an object"):
            render_markdown(data)
    def test_invalid_item_field_type_is_validation_error(self):
        data={"project":"x","design_read":"x","invariants":["a","b","c"],"hierarchy":{"layout":"x"},"items":[{"target":123,"reference":"x","borrow":"x","do_not_copy":"x","build_implication":"x","mobile":"x","attribution":"x"}]}
        self.assertIn("item 0 field must be non-empty text: target", validate_atlas(data))
        with self.assertRaisesRegex(ValueError, "item 0 field must be non-empty text: target"):
            render_markdown(data)

    def test_render_consumed_text_shapes_are_validated(self):
        cases = [
            ("project", 42, "root field must be non-empty text: project"),
            ("design_read", {}, "root field must be non-empty text: design_read"),
            ("invariants", ["a", "b", 3], "invariants must contain only non-empty text"),
            ("hierarchy", {"layout": []}, "hierarchy keys and values must be non-empty text"),
        ]
        for field, value, message in cases:
            with self.subTest(field=field, value=value):
                data=self.example(); data[field]=value
                self.assertIn(message, validate_atlas(data))
                with self.assertRaisesRegex(ValueError, message):
                    render_markdown(data)
if __name__ == "__main__": unittest.main()
