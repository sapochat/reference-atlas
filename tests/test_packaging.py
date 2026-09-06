"""Cheap resource/metadata regressions; never build from unittest discovery."""
import importlib.util
from importlib import metadata, resources
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_release_metadata(self):
        dist = metadata.distribution("reference-atlas")
        self.assertEqual(dist.version, "0.2.0")
        self.assertEqual(dist.requires or [], [])
        self.assertEqual(dist.metadata["License-Expression"], "MIT")
        self.assertIn("Repository, https://github.com/sapochat/reference-atlas", dist.metadata.get_all("Project-URL", []))
        self.assertIn("Documentation, https://github.com/sapochat/reference-atlas#readme", dist.metadata.get_all("Project-URL", []))

    def test_published_schema_matches_packaged_resource(self):
        packaged = resources.files("reference_atlas").joinpath("resources/atlas-v2.schema.json")
        self.assertEqual(packaged.read_bytes(), (ROOT / "schemas/atlas-v2.schema.json").read_bytes())

    def test_starter_is_valid_but_not_ready_without_assets(self):
        from reference_atlas.validation import inspect_atlas
        import jsonschema
        bundle = resources.files("reference_atlas").joinpath("resources")
        starter = json.loads(bundle.joinpath("starter.json").read_text(encoding="utf-8"))
        schema = json.loads(bundle.joinpath("atlas-v2.schema.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(starter)
        self.assertEqual(starter["schema_version"], 2)
        with tempfile.TemporaryDirectory() as tmp:
            diagnostics = inspect_atlas(starter, base_dir=tmp, check_assets=True)
            self.assertFalse(any(d["severity"] == "error" for d in diagnostics))
            self.assertTrue(any(d["severity"] == "warning" for d in diagnostics))
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_verifier_environment_removes_source_overrides(self):
        path = ROOT / "scripts/verify_distribution.py"
        self.assertTrue(path.is_file(), "distribution verifier must ship in sdist")
        spec = importlib.util.spec_from_file_location("verify_distribution", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        env = module.clean_environment({"PYTHONPATH": "/checkout/src", "PYTHONHOME": "/bad", "VIRTUAL_ENV": "/old", "PATH": "/bin"})
        self.assertNotIn("PYTHONPATH", env)
        self.assertNotIn("PYTHONHOME", env)
        self.assertNotIn("VIRTUAL_ENV", env)
        self.assertEqual(env["PYTHONNOUSERSITE"], "1")
        self.assertEqual(env["PATH"], "/bin")


if __name__ == "__main__":
    unittest.main()
