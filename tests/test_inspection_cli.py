"""End-to-end inspection CLI contracts, using isolated real files."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def legacy_atlas():
    return {
        "project": "Inspection fixture", "design_read": "Quiet editorial",
        "invariants": ["Serif", "Space", "Contrast"],
        "hierarchy": {"layout": "Reference A"},
        "items": [{"target": "Hero", "reference": "assets/hero.png",
                   "borrow": "Scale", "do_not_copy": "Identity",
                   "build_implication": "Grid", "mobile": "Stack",
                   "attribution": "Synthetic fixture"}],
    }


def v2_atlas():
    return {
        "schema_version": 2, "project": "V2 inspection", "design_read": "Clear",
        "invariants": ["Scale", "Space", "Contrast"],
        "sources": {"reference-a": {"title": "Fixture", "locator": "assets/hero.txt", "attribution": "Synthetic"}},
        "hierarchy": {},
        "items": [{"id": "hero", "target": "Hero", "build_implication": "Grid", "mobile": "Stack",
                   "references": [{"source": "reference-a", "borrow": "Scale", "do_not_copy": "Identity"}]}],
    }


class InspectionCliTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "atlas.json"
        self.output = self.root / "atlas.md"
        self.data = legacy_atlas()
        self.save()

    def save(self):
        self.source.write_text(json.dumps(self.data), encoding="utf-8")

    def run_cli(self, *args, decoder_recursion=False):
        command = [sys.executable, "-m", "reference_atlas.cli"]
        if decoder_recursion:
            # Leave source open/fstat and CLI error reporting real; only the
            # decoder raises, independently of interpreter nesting thresholds.
            script = (
                "from unittest.mock import patch\n"
                "from reference_atlas import cli\n"
                "with patch.object(cli.json, 'load', side_effect=RecursionError('decoder recursion guard')):\n"
                "    raise SystemExit(cli.main())\n"
            )
            command = [sys.executable, "-c", script]
        return subprocess.run(
            [*command, *map(str, args)],
            cwd=self.root, env=dict(os.environ, PYTHONPATH=str(ROOT / "src"),
                                   PYTHONDONTWRITEBYTECODE="1"),
            capture_output=True, encoding="utf-8", timeout=10,
        )

    def snapshot(self):
        return {p.name: p.read_bytes() for p in self.root.iterdir() if p.is_file()}

    def envelope(self, result, code):
        self.assertEqual(result.returncode, code, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(set(payload), {"valid", "ready", "diagnostics"})
        for diagnostic in payload["diagnostics"]:
            self.assertEqual(set(diagnostic), {"code", "severity", "path", "message"})
            self.assertIn(diagnostic["severity"], ("warning", "error"))
        return payload

    def test_check_text_without_output_writes_nothing(self):
        before = self.snapshot()
        result = self.run_cli(self.source, "--check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "valid\n")
        self.assertEqual(result.stderr, "")
        self.assertEqual(self.snapshot(), before)

    def test_check_json_clean_legacy(self):
        result = self.run_cli(self.source, "--check", "--diagnostics", "json")
        self.assertEqual(self.envelope(result, 0), {"valid": True, "ready": True, "diagnostics": []})
        self.assertEqual(result.stderr, "")

    def test_unknown_extras_warn_in_check_and_render(self):
        self.data["layout_plan"] = {"ignored": True}
        self.save()
        before = self.snapshot()
        result = self.run_cli(self.source, "--check", "--diagnostics", "json")
        payload = self.envelope(result, 0)
        self.assertTrue(payload["valid"])
        self.assertFalse(payload["ready"])
        self.assertTrue(any(d["path"] == "/layout_plan" and d["severity"] == "warning" for d in payload["diagnostics"]))
        self.assertEqual(self.snapshot(), before)
        result = self.run_cli(self.source, self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("warning", result.stderr.lower())
        self.assertIn("/layout_plan", result.stderr)
        self.assertEqual(result.stdout, str(self.output) + "\n")

    def test_strict_warning_preserves_forced_output(self):
        self.data["unused"] = "warning"
        self.save()
        self.output.write_bytes(b"keep")
        before = self.snapshot()
        result = self.run_cli(self.source, self.output, "--strict", "--force")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn("warning", result.stderr.lower())
        self.assertEqual(self.snapshot(), before)
        result = self.run_cli(self.source, "--check", "--strict", "--diagnostics", "json")
        payload = self.envelope(result, 2)
        self.assertTrue(payload["valid"])
        self.assertFalse(payload["ready"])
        self.assertEqual(self.snapshot(), before)

    def test_invalid_schema_json_never_writes(self):
        self.data = {"project": 12}
        self.save()
        before = self.snapshot()
        payload = self.envelope(self.run_cli(self.source, "--check", "--diagnostics", "json"), 2)
        self.assertFalse(payload["valid"])
        self.assertFalse(payload["ready"])
        self.assertTrue(payload["diagnostics"])
        self.assertEqual(self.snapshot(), before)

    def test_flag_constraints(self):
        cases = [(self.source,), ("--check",),
                 (self.source, "--check", "--force"),
                 (self.source, self.output, "--check"),
                 (self.source, self.output, "--diagnostics", "json"),
                 (self.source, "--check", "--diagnostics", "yaml")]
        before = self.snapshot()
        for args in cases:
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, 2)
                self.assertNotIn("Traceback", result.stderr)
                self.assertTrue(result.stderr)
                self.assertEqual(self.snapshot(), before)

    def test_duplicate_keys_rejected_at_every_depth(self):
        raw = json.dumps(self.data)
        cases = [raw[:-1] + ', "project": "overwritten"}',
                 raw.replace('"target": "Hero"', '"target": "Hero", "target": "Other"')]
        for raw in cases:
            for checking in (False, True):
                with self.subTest(raw=raw, checking=checking):
                    self.source.write_text(raw, encoding="utf-8")
                    self.output.write_bytes(b"keep")
                    before = self.snapshot()
                    flags = ("--check", "--diagnostics", "json") if checking else (self.output, "--force")
                    result = self.run_cli(self.source, *flags)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    if checking:
                        payload = self.envelope(result, 2)
                        self.assertFalse(payload["valid"])
                        self.assertEqual(payload["diagnostics"][0]["path"], "")
                        self.assertIn("duplicate", payload["diagnostics"][0]["message"].lower())
                    else:
                        self.assertIn("duplicate", result.stderr.lower())
                    self.assertEqual(self.snapshot(), before)

    def test_load_errors_have_json_envelope_and_location(self):
        cases = [(b'{\n "project":\n}', 2, "line 3"), (b'\xff', 2, "UTF-8"), (None, 3, str(self.source))]
        for raw, code, expected in cases:
            with self.subTest(raw=raw):
                if raw is None:
                    self.source.unlink()
                else:
                    self.source.write_bytes(raw)
                before = self.snapshot()
                result = self.run_cli(self.source, "--check", "--diagnostics", "json")
                payload = self.envelope(result, code)
                self.assertFalse(payload["valid"])
                self.assertFalse(payload["ready"])
                self.assertIn(expected, payload["diagnostics"][0]["message"])
                self.assertEqual(self.snapshot(), before)

    def test_v2_draft_warns_but_renders_unless_strict(self):
        self.data = v2_atlas()
        self.save()
        before = self.snapshot()
        payload = self.envelope(self.run_cli(self.source, "--check", "--diagnostics", "json"), 0)
        self.assertTrue(payload["valid"])
        self.assertFalse(payload["ready"])
        self.assertTrue({"missing_hierarchy", "missing_evidence", "missing_requirement", "unchecked_check"}
                        <= {d["code"] for d in payload["diagnostics"]})
        self.assertEqual(self.snapshot(), before)
        text = self.run_cli(self.source, "--check")
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertEqual(text.stdout, "valid\n")
        self.assertIn("warning", text.stderr)
        result = self.run_cli(self.source, self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("warning", result.stderr)
        self.assertIn("V2 inspection", self.output.read_text())
        before = self.snapshot()
        result = self.run_cli(self.source, self.output, "--force", "--strict")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_schema_versions_are_exact_integers(self):
        for version in (True, 1.0, 2.0, "2"):
            with self.subTest(version=version):
                self.data = v2_atlas()
                self.data["schema_version"] = version
                self.save()
                payload = self.envelope(self.run_cli(self.source, "--check", "--diagnostics", "json"), 2)
                self.assertFalse(payload["valid"])
                self.assertTrue(any(d["path"] == "/schema_version" for d in payload["diagnostics"]))

    def test_v2_duplicate_nested_key_is_a_decode_error(self):
        raw = json.dumps(v2_atlas()).replace('"source": "reference-a"', '"source": "reference-a", "source": "other"')
        self.source.write_text(raw)
        before = self.snapshot()
        for flags in (("--check", "--diagnostics", "json"), (self.output,)):
            result = self.run_cli(self.source, *flags)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("duplicate", result.stdout + result.stderr)
            self.assertEqual(self.snapshot(), before)

    def test_v2_asset_checks_are_opt_in_and_relative_to_atlas(self):
        self.data = v2_atlas()
        nested = self.root / "nested"
        nested.mkdir()
        self.source = nested / "atlas.json"
        self.save()
        flags = ("--check", "--diagnostics", "json")
        self.assertTrue(self.envelope(self.run_cli(self.source, *flags), 0)["valid"])
        payload = self.envelope(self.run_cli(self.source, *flags, "--check-assets"), 2)
        self.assertFalse(payload["valid"])
        (nested / "assets").mkdir()
        (nested / "assets" / "hero.txt").write_text("Fixture")
        payload = self.envelope(self.run_cli(self.source, *flags, "--check-assets"), 0)
        self.assertTrue(payload["valid"])
        result = self.run_cli(self.source, self.output, "--check-assets")
        self.assertEqual(result.returncode, 0, result.stderr)
        before = self.output.read_bytes()
        (nested / "assets" / "hero.txt").unlink()
        result = self.run_cli(self.source, self.output, "--check-assets", "--force")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(self.output.read_bytes(), before)

    def test_asset_checks_never_fetch_remote_urls(self):
        self.data = v2_atlas()
        self.data["sources"]["reference-a"]["locator"] = "https://example.invalid/never-fetch"
        self.save()
        (self.root / "assets").mkdir()
        script = (
            "import runpy, socket, urllib.request; from unittest.mock import patch; "
            "\nwith patch.object(socket, 'socket', side_effect=AssertionError('network forbidden')), "
            "patch.object(urllib.request, 'urlopen', side_effect=AssertionError('fetch forbidden')):"
            "\n runpy.run_module('reference_atlas.cli', run_name='__main__')"
        )
        result = subprocess.run(
            [sys.executable, "-c", script, str(self.source), "--check", "--check-assets", "--diagnostics", "json"],
            cwd=self.root, env=dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONDONTWRITEBYTECODE="1"),
            capture_output=True, encoding="utf-8", timeout=10,
        )
        payload = self.envelope(result, 0)
        self.assertTrue(payload["valid"])
        self.assertTrue(any(d["code"] == "remote_unchecked" for d in payload["diagnostics"]))

    def test_strict_clean_legacy_still_renders_and_checks(self):
        result = self.run_cli(self.source, "--check", "--strict")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "valid\n")
        result = self.run_cli(self.source, self.output, "--strict")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, str(self.output) + "\n")
        self.assertTrue(self.output.is_file())

    def test_check_does_not_call_publisher(self):
        from reference_atlas import cli
        with mock.patch.object(cli, "_publish", side_effect=AssertionError("publish called")):
            with mock.patch.object(sys, "argv", ["reference-atlas", str(self.source), "--check"]):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(cli.main(), 0)

    def test_check_rejects_lone_surrogates_without_writing(self):
        for surrogate in ("\ud800", "\udfff"):
            for diagnostic_format in ("text", "json"):
                with self.subTest(surrogate=repr(surrogate), format=diagnostic_format):
                    self.data["project"] = "Invalid " + surrogate
                    self.data["unused"] = "preserve this warning"
                    self.save()
                    before = self.snapshot()
                    result = self.run_cli(self.source, "--check", "--diagnostics", diagnostic_format)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertNotIn("Traceback", result.stdout + result.stderr)
                    self.assertEqual(self.snapshot(), before)
                    if diagnostic_format == "json":
                        payload = self.envelope(result, 2)
                        self.assertFalse(payload["valid"])
                        self.assertFalse(payload["ready"])
                        errors = [d for d in payload["diagnostics"] if d["severity"] == "error"]
                        self.assertEqual(len(errors), 1)
                        self.assertEqual(errors[0]["code"], "invalid_unicode")
                        self.assertEqual(errors[0]["path"], "")
                        self.assertIn("UTF-8", errors[0]["message"])
                        self.assertTrue(any(d["severity"] == "warning" for d in payload["diagnostics"]))
                        self.assertEqual(result.stderr, "")
                    else:
                        self.assertEqual(result.stdout, "")
                        self.assertIn("UTF-8", result.stderr)
                        self.assertIn("invalid_unicode", result.stderr)
                        self.assertIn("warning", result.stderr)

    def test_check_keeps_renderer_programmer_errors_observable(self):
        from reference_atlas import cli
        for diagnostic_format in ("text", "json"):
            with self.subTest(format=diagnostic_format):
                with mock.patch.object(cli, "render_markdown", side_effect=ValueError("renderer bug")):
                    with mock.patch.object(sys, "argv", ["reference-atlas", str(self.source), "--check", "--diagnostics", diagnostic_format]):
                        with self.assertRaisesRegex(ValueError, "renderer bug"):
                            cli.main()

    def test_check_does_not_render_structurally_invalid_data(self):
        from reference_atlas import cli
        self.data = {"project": 12}
        self.save()
        with mock.patch.object(cli, "render_markdown", side_effect=AssertionError("render called")):
            with mock.patch.object(sys, "argv", ["reference-atlas", str(self.source), "--check"]):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(cli.main(), 2)

    def test_decoder_resource_guards_have_json_envelopes(self):
        limit = getattr(sys, "get_int_max_str_digits", lambda: 0)()
        # Use valid input for fault injection, retaining real integer decoding.
        cases = [("recursion", self.source.read_bytes())]
        if limit:
            cases.append(("integer", b'{"number": ' + b'9' * max(5000, limit + 1) + b'}'))
        for kind, raw in cases:
            with self.subTest(kind=kind):
                self.source.write_bytes(raw)
                self.output.write_bytes(b"keep")
                before = self.snapshot()
                result = self.run_cli(self.source, "--check", "--diagnostics", "json",
                                      decoder_recursion=kind == "recursion")
                payload = self.envelope(result, 2)
                self.assertFalse(payload["valid"])
                self.assertFalse(payload["ready"])
                self.assertIn("invalid JSON", payload["diagnostics"][0]["message"])
                if kind == "recursion":
                    self.assertIn("decoder recursion guard", payload["diagnostics"][0]["message"])
                self.assertEqual(result.stderr, "")
                self.assertEqual(self.snapshot(), before)
                self.assertEqual({p.name for p in self.root.iterdir()}, set(before))

    def test_directory_input_has_json_io_error(self):
        payload = self.envelope(self.run_cli(self.root, "--check", "--diagnostics", "json"), 3)
        self.assertFalse(payload["valid"])
        self.assertIn(str(self.root), payload["diagnostics"][0]["message"])

    def test_asset_option_is_opt_in_and_uses_source_parent(self):
        from reference_atlas import cli
        for flags, enabled in [((), False), (("--check-assets",), True)]:
            with self.subTest(flags=flags):
                with mock.patch.object(cli, "inspect_atlas", create=True, return_value=[]) as inspect:
                    with mock.patch.object(sys, "argv", ["reference-atlas", str(self.source), "--check", *flags]):
                        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                            self.assertEqual(cli.main(), 0)
                    inspect.assert_called_once_with(self.data, base_dir=self.source.parent, check_assets=enabled)


if __name__ == "__main__":
    unittest.main()
