"""V2 structural conformance and runtime-only semantic/safety regressions."""
import copy
import importlib
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def draft():
    return {"schema_version": 2, "project": "Example", "design_read": "Clear",
            "invariants": ["One", "Two", "Three"],
            "sources": {"example": {"title": "Example", "locator": "assets/reference.txt", "attribution": "Author"}},
            "hierarchy": {}, "items": [{"id": "hero", "target": "Hero", "build_implication": "Build",
            "mobile": "Stack", "references": [{"source": "example", "borrow": "Spacing", "do_not_copy": "Brand"}]}]}


def legacy():
    return {"project": "Example", "design_read": "Clear", "invariants": ["A", "B", "C"],
            "hierarchy": {"type": "Original"}, "items": [{k: "text" for k in
            ("target", "reference", "borrow", "do_not_copy", "build_implication", "mobile", "attribution")} ]}


def changed(path, value, remove=False):
    data = draft()
    node = data
    for key in path[:-1]:
        node = node[key]
    if remove:
        del node[path[-1]]
    else:
        node[path[-1]] = value
    return data


class ValidationTests(unittest.TestCase):
    def setUp(self):
        module = importlib.import_module("reference_atlas.validation")
        self.inspect = module.inspect_atlas
        self.validate = module.validate_atlas

    def test_legacy_errors_and_warnings(self):
        self.assertEqual(self.validate(None), ["atlas must be an object"])
        self.assertEqual(self.validate({}), ["root field must be non-empty text: project", "root field must be non-empty text: design_read", "invariants must contain at least three items", "hierarchy must be a non-empty object", "items must be a non-empty list"])
        data = legacy()
        self.assertEqual(self.inspect(data), [])
        data["schema_version"] = 1
        self.assertEqual(self.inspect(data), [])
        data["a~/b"] = 0
        data["items"][0]["unused"] = True
        diagnostics = self.inspect(data)
        self.assertEqual([d["path"] for d in diagnostics], ["/a~0~1b", "/items/0/unused"])
        self.assertTrue(all(d["severity"] == "warning" and "not rendered" in d["message"] for d in diagnostics))
        data["items"] = [3, {}]
        self.assertEqual(self.validate(data)[0], "item 0 must be an object")
        self.assertIn("item 1 field must be non-empty text: target", self.validate(data))

    def test_exact_version_dispatch(self):
        for version in (True, False, 1.0, 2.0, "2", None, 0, 3, [], {}):
            with self.subTest(version=version):
                self.assertTrue(self.validate(changed(["schema_version"], version)))
        self.assertEqual(self.validate(legacy()), [])
        self.assertEqual(self.validate(draft()), [])

    def test_structural_contract(self):
        bad = []
        for key in draft():
            bad.append(changed([key], None, remove=True))
        for path in (["project"], ["design_read"], ["items", 0, "target"], ["items", 0, "mobile"], ["items", 0, "build_implication"], ["sources", "example", "title"], ["sources", "example", "attribution"]):
            for value in (None, "", "  ", 3, []):
                bad.append(changed(path, value))
        for path in (["extra"], ["items", 0, "extra"], ["sources", "example", "extra"], ["items", 0, "references", 0, "extra"]):
            bad.append(changed(path, "extra"))
        bad += [changed(["invariants"], ["one", "two"]), changed(["invariants"], ["one", "two", " "]), changed(["items"], []), changed(["items"], [None]), changed(["sources"], []), changed(["hierarchy"], []), changed(["items", 0, "id"], "Bad_ID"), changed(["sources"], {"Bad_ID": draft()["sources"]["example"]}), changed(["items", 0, "references"], []), changed(["items", 0, "references"], [None]), changed(["items", 0, "original_design"], "Original"), changed(["items", 0, "requirements"], {"unknown": "text"}), changed(["items", 0, "requirements"], {"accessibility": " "}), changed(["items", 0, "checks"], {})]
        for data in bad:
            with self.subTest(data=data):
                self.assertTrue(self.validate(data))
        original = draft()
        original["sources"] = {}
        original["items"][0].pop("references")
        original["items"][0]["original_design"] = "Original arrangement"
        self.assertEqual(self.validate(original), [])
        self.assertFalse(any("evidence" in d["code"] or "reference" in d["code"] for d in self.inspect(original)))

    def test_hierarchy_contract(self):
        for entry in ({}, {"reason": "Why"}, {"reason": "Why", "source": "example", "decision": "original"}, {"reason": "Why", "decision": "other"}, {"reason": " ", "decision": "original"}, {"reason": "Why", "decision": "original", "extra": True}, None):
            self.assertTrue(self.validate(changed(["hierarchy"], {"typography": entry})))
        for entry in ({"reason": "Why", "source": "example"}, {"reason": "Why", "decision": "original"}, {"reason": "Why", "decision": "not_applicable"}):
            self.assertEqual(self.validate(changed(["hierarchy"], {"typography": entry})), [])
        self.assertTrue(self.validate(changed(["hierarchy"], {"unknown": {"reason": "Why", "decision": "original"}})))

    def test_check_contract(self):
        for status in ("not_checked", "pass", "fail", "not_applicable"):
            check = {"criterion": "mobile", "status": status}
            if status in ("pass", "fail"):
                check.update(method="Browser test", evidence="test.txt")
            if status == "not_applicable":
                check["reason"] = "No motion"
            self.assertEqual(self.validate(changed(["items", 0, "checks"], [check])), [])
        for check in ({}, None, {"criterion": "other", "status": "not_checked"}, {"criterion": "mobile", "status": "done"}, {"criterion": "mobile", "status": "pass"}, {"criterion": "mobile", "status": "fail", "method": "test"}, {"criterion": "mobile", "status": "not_applicable"}, {"criterion": "mobile", "status": "not_checked", "note": " "}, {"criterion": "mobile", "status": "not_checked", "extra": 1}):
            self.assertTrue(self.validate(changed(["items", 0, "checks"], [check])))

    def test_locators(self):
        paths = (["sources", "example", "locator"], ["items", 0, "references", 0, "evidence"])
        for path in paths:
            for value in ("https://example.org/a", "http://example.org", "folder/reference.txt"):
                self.assertEqual(self.validate(changed(path, value)), [])
            for value in ("file:///tmp/a", "javascript:alert(1)", "ftp://example.org/a", "/tmp/a", "../a", "dir/../a", "C:\\a", "//example.org/a", "https://user:pass@example.org/a", "https:///a", "https://", " ", "a\\..\\b"):
                self.assertTrue(self.validate(changed(path, value)), value)
        for value in ("relative.txt", "https://user@example.org", "ftp://example.org"):
            self.assertTrue(self.validate(changed(["sources", "example", "url"], value)))
        self.assertEqual(self.validate(changed(["sources", "example", "url"], "https://example.org")), [])
        for value in ("../assets", "/assets", "https://example.org", " "):
            self.assertTrue(self.validate(changed(["asset_root"], value)))

    def test_semantics_and_diagnostics(self):
        data = draft()
        codes = {d["code"] for d in self.inspect(data)}
        self.assertTrue({"missing_hierarchy", "missing_evidence", "missing_requirement", "unchecked_check"} <= codes)
        data["items"].append(copy.deepcopy(data["items"][0]))
        self.assertTrue(any(d["code"] == "duplicate_id" for d in self.inspect(data)))
        data = changed(["items", 0, "references", 0, "source"], "missing")
        self.assertTrue(any(d["code"] == "unknown_source" and d["path"] == "/items/0/references/0/source" for d in self.inspect(data)))
        data = changed(["hierarchy"], {"typography": {"source": "missing", "reason": "Why"}})
        self.assertTrue(any(d["code"] == "unknown_source" for d in self.inspect(data)))
        data = changed(["items", 0, "checks"], [{"criterion": "mobile", "status": "not_checked"}] * 2)
        self.assertTrue(any(d["code"] == "duplicate_criterion" for d in self.inspect(data)))
        data = changed(["invariants"], ["One", "One", "Three"])
        self.assertTrue(any(d["code"] == "duplicate_invariant" and d["severity"] == "warning" for d in self.inspect(data)))
        data = changed(["items", 0, "checks"], [{"criterion": "mobile", "status": "fail", "method": "Test", "evidence": "test.txt"}])
        self.assertTrue(any(d["code"] == "failed_check" and d["severity"] == "warning" for d in self.inspect(data)))
        for d in self.inspect(data):
            self.assertEqual(set(d), {"code", "severity", "path", "message"})
        self.assertEqual(self.inspect(data), self.inspect(data))

    def test_malformed_never_crashes(self):
        values = (None, True, 5, 2.0, "x", [], {}, [None], {"bad": []})
        for value in values:
            self.inspect(value)
            for path in (["sources"], ["hierarchy"], ["items"], ["invariants"], ["items", 0, "requirements"], ["items", 0, "checks"], ["items", 0, "references"], ["items", 0, "references", 0, "source"]):
                self.inspect(changed(path, value))

    def test_legacy_assets_explicitly_unsupported(self):
        diagnostics = self.inspect(legacy(), base_dir=ROOT, check_assets=True)
        self.assertTrue(any(d["severity"] == "warning" and d["code"] == "legacy_assets_unchecked" for d in diagnostics))
        self.assertEqual(self.inspect(legacy()), [])

    def test_malformed_url_authority_and_port(self):
        for locator in ("https://example.org:99999/a", "https://[:::]/a", "http://[abc]/a"):
            with self.subTest(locator=locator):
                self.assertTrue(self.validate(changed(["sources", "example", "locator"], locator)))

    def test_original_and_remote_only_need_no_asset_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = draft()
            data["sources"] = {}
            data["items"][0].pop("references")
            data["items"][0]["original_design"] = "Original layout"
            self.assertFalse(any(d["severity"] == "error" for d in self.inspect(data, base_dir=tmp, check_assets=True)))
            data = changed(["sources", "example", "locator"], "https://example.invalid/no-fetch")
            diagnostics = self.inspect(data, base_dir=tmp, check_assets=True)
            self.assertFalse(any(d["severity"] == "error" for d in diagnostics))
            self.assertTrue(any(d["code"] == "remote_unchecked" for d in diagnostics))

    def test_asset_check_opt_in_and_containment(self):
        data = draft()
        self.assertFalse(any(d["code"].startswith("asset_") for d in self.inspect(data)))
        self.assertTrue(any(d["severity"] == "error" for d in self.inspect(data, check_assets=True)))
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "assets").mkdir()
            (base / "assets/reference.txt").write_text("not fidelity proof")
            self.assertFalse(any(d["severity"] == "error" for d in self.inspect(data, base_dir=base, check_assets=True)))
            data["items"][0]["references"][0]["evidence"] = "assets/missing.txt"
            errors = [d for d in self.inspect(data, base_dir=base, check_assets=True) if d["severity"] == "error"]
            self.assertTrue(any(d["path"] == "/items/0/references/0/evidence" for d in errors))
            data["items"][0]["references"][0]["evidence"] = "https://example.invalid/no-request"
            self.assertTrue(any(d["code"] == "remote_unchecked" for d in self.inspect(data, base_dir=base, check_assets=True)))
            self.assertFalse(any(d["code"] == "remote_unchecked" for d in self.inspect(data)))
            (base / "outside.txt").write_text("outside")
            (base / "assets/escape.txt").symlink_to(base / "outside.txt")
            data["sources"]["example"]["locator"] = "assets/escape.txt"
            self.assertTrue(any(d["code"] == "asset_escape" for d in self.inspect(data, base_dir=base, check_assets=True)))
            data["sources"]["example"]["locator"] = "assets/directory"
            (base / "assets/directory").mkdir()
            self.assertTrue(any(d["code"] == "asset_missing" for d in self.inspect(data, base_dir=base, check_assets=True)))
            (base / "root-link").symlink_to(base.parent, target_is_directory=True)
            data["asset_root"] = "root-link"
            self.assertTrue(any(d["code"] == "asset_escape" and d["path"] == "/asset_root" for d in self.inspect(data, base_dir=base, check_assets=True)))


class PublishedSchemaTests(unittest.TestCase):
    def test_nested_shape_mutation_conformance(self):
        import jsonschema
        from reference_atlas.validation import inspect_atlas
        schema = json.loads((ROOT / "schemas/atlas-v2.schema.json").read_text())
        validator = jsonschema.Draft202012Validator(schema)
        rich = draft()
        rich["asset_root"] = "assets"
        rich["sources"]["example"].update(url="https://example.org", rights_notes="Original")
        rich["hierarchy"]["typography"] = {"source": "example", "reason": "Why"}
        rich["items"][0]["requirements"] = {key: "Required" for key in ("accessibility", "reduced_motion", "performance")}
        rich["items"][0]["checks"] = [{"criterion": "mobile", "status": "pass", "method": "Test", "evidence": "assets/reference.txt", "note": "Reported", "reason": "Test"}]
        rich["items"][0]["references"][0]["evidence"] = "assets/reference.txt"
        paths = []
        def visit(value, path=()):
            paths.append(path)
            if isinstance(value, dict):
                for key, child in value.items():
                    visit(child, path + (key,))
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    visit(child, path + (index,))
        visit(rich)
        corpus = []
        for path in paths:
            if not path or path == ("schema_version",):
                continue
            for replacement in (None, True, 7, 2.5, "", " ", [], {}, [None]):
                data = copy.deepcopy(rich)
                node = data
                for key in path[:-1]:
                    node = node[key]
                node[path[-1]] = replacement
                corpus.append((path, data))
            if isinstance(path[-1], str):
                data = copy.deepcopy(rich)
                node = data
                for key in path[:-1]:
                    node = node[key]
                del node[path[-1]]
                corpus.append((path, data))
        semantic_codes = {"unknown_source", "duplicate_id", "duplicate_criterion"}
        for path, data in corpus:
            with self.subTest(path=path, data=data):
                structural_errors = [d for d in inspect_atlas(data) if d["severity"] == "error" and d["code"] not in semantic_codes]
                self.assertEqual(validator.is_valid(data), not structural_errors)
        self.assertGreater(len(corpus), 300)

    def test_schema_exists_and_conformance(self):
        path = ROOT / "schemas/atlas-v2.schema.json"
        self.assertTrue(path.is_file(), "Published v2 schema is missing")
        import jsonschema
        from reference_atlas.validation import validate_atlas
        schema = json.loads(path.read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        validator = jsonschema.Draft202012Validator(schema)
        corpus = [draft()]
        for key in draft():
            corpus.append(changed([key], None, remove=True))
        corpus += [changed(["project"], " "), changed(["items"], []), changed(["sources"], []), changed(["schema_version"], True), changed(["schema_version"], "2"), changed(["items", 0, "extra"], 1), changed(["items", 0, "original_design"], "Original"), changed(["items", 0, "checks"], [{"criterion": "mobile", "status": "pass"}]), changed(["hierarchy"], {"motion": {"reason": "why", "decision": "original"}}), changed(["sources", "example", "locator"], "../escape"), changed(["sources", "example", "url"], "https://user@example.org"), changed(["items", 0, "requirements"], {"other": "text"})]
        corpus += [changed(["items", 0, "id"], "hero\n"), changed(["sources"], {"example\n": draft()["sources"]["example"]}), changed(["sources", "example", "locator"], "assets/reference.txt\n"), changed(["sources", "example", "locator"], "https://example.org/a\n"), changed(["items", 0, "references", 0, "evidence"], "assets/reference.txt\n")]
        for data in corpus:
            with self.subTest(data=data):
                self.assertEqual(validator.is_valid(data), not validate_atlas(data))
        # Cross-record constraints deliberately remain runtime semantics.
        data = changed(["items", 0, "references", 0, "source"], "unregistered")
        self.assertTrue(validator.is_valid(data))
        self.assertTrue(validate_atlas(data))
        # JSON Schema integers are mathematical: 2.0 passes the published shape,
        # while exact runtime dispatch intentionally rejects Python floats.
        numeric_float = changed(["schema_version"], 2.0)
        self.assertTrue(validator.is_valid(numeric_float))
        self.assertTrue(validate_atlas(numeric_float))
        self.assertIn("2.0", schema["description"])
        # Port range and bracketed IP validity require URL parser semantics.
        malformed_port = changed(["sources", "example", "locator"], "https://example.org:99999/a")
        self.assertTrue(validator.is_valid(malformed_port))
        self.assertTrue(validate_atlas(malformed_port))
        self.assertIn("URL parser", schema["description"])


if __name__ == "__main__":
    unittest.main()
