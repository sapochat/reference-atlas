import contextlib
from importlib import resources
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from reference_atlas import cli, inspect_atlas, validate_atlas


ROOT = Path(__file__).resolve().parents[1]


class InitializerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.output = self.root / "draft.json"

    def invoke(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", ["reference-atlas", *map(str, args)]), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                code = cli.main()
            except SystemExit as error:
                code = error.code
        return code, stdout.getvalue(), stderr.getvalue()

    def assert_failure(self, result, code=3):
        self.assertEqual(result[0], code, result[2])
        self.assertEqual(result[1], "")
        self.assertTrue(result[2])
        self.assertNotIn("Traceback", result[2])

    def test_init_publishes_only_valid_original_draft(self):
        code, stdout, stderr = self.invoke("--init", self.output)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(stdout, str(self.output) + "\n")
        self.assertEqual(stderr, "")
        self.assertEqual(list(self.root.iterdir()), [self.output])
        text = self.output.read_text(encoding="utf-8")
        self.assertEqual(text, resources.files("reference_atlas.resources").joinpath("starter.json").read_text(encoding="utf-8"))
        data = json.loads(text)
        self.assertEqual(validate_atlas(data), [])
        self.assertEqual(data["schema_version"], 2)
        self.assertEqual(data["sources"], {})
        self.assertEqual(len(data["invariants"]), 3)
        self.assertEqual(len(set(data["invariants"])), 3)
        self.assertEqual(set(data["hierarchy"]), {"typography", "layout", "motion", "imagery"})
        for entry in data["hierarchy"].values():
            self.assertIn(entry["decision"], {"original", "not_applicable"})
            self.assertIn("TBD", entry["reason"])
        self.assertEqual(len(data["items"]), 1)
        item = data["items"][0]
        self.assertNotIn("references", item)
        for field in ("target", "original_design", "build_implication", "mobile"):
            self.assertIn("TBD", item[field])
        self.assertEqual(set(item["requirements"]), {"accessibility", "reduced_motion", "performance"})
        self.assertEqual({check["criterion"] for check in item["checks"]}, {"mobile", "accessibility", "reduced_motion", "performance"})
        self.assertTrue(all(check["status"] == "not_checked" and "evidence" not in check for check in item["checks"]))
        issues = inspect_atlas(data, base_dir=self.root, check_assets=True)
        self.assertTrue(any(issue["severity"] == "warning" for issue in issues))
        self.assertFalse(any(issue["severity"] == "error" for issue in issues))
        result = self.invoke(self.output, "--check", "--diagnostics", "json")
        self.assertEqual(result[0], 0, result[2])
        report = json.loads(result[1])
        self.assertTrue(report["valid"])
        self.assertFalse(report["ready"])
        self.assert_failure(self.invoke(self.output, "--check", "--strict"), 2)

    def test_existing_output_preserved_without_force(self):
        self.output.write_bytes(b"keep")
        self.assert_failure(self.invoke("--init", self.output))
        self.assertEqual(self.output.read_bytes(), b"keep")
        self.assertEqual(list(self.root.iterdir()), [self.output])

    def test_force_replaces_only_regular_file(self):
        self.output.write_bytes(b"keep")
        result = self.invoke("--init", self.output, "--force")
        self.assertEqual(result[0], 0, result[2])
        self.assertEqual(validate_atlas(json.loads(self.output.read_text(encoding="utf-8"))), [])
        self.assertEqual(list(self.root.iterdir()), [self.output])

    def test_directories_and_symlinks_rejected(self):
        target = self.root / "target"
        target.write_bytes(b"keep")
        for kind in ("directory", "symlink", "dangling"):
            if kind == "directory":
                self.output.mkdir()
            else:
                self.output.symlink_to(target if kind == "symlink" else self.root / "absent")
            try:
                for flags in ((), ("--force",)):
                    with self.subTest(kind=kind, flags=flags):
                        self.assert_failure(self.invoke("--init", self.output, *flags))
                        self.assertEqual(target.read_bytes(), b"keep")
                        self.assertEqual(set(self.root.iterdir()), {self.output, target})
            finally:
                if kind == "directory":
                    self.output.rmdir()
                else:
                    self.output.unlink()

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires FIFO support")
    def test_special_file_rejected(self):
        os.mkfifo(self.output)
        for flags in ((), ("--force",)):
            self.assert_failure(self.invoke("--init", self.output, *flags))
        self.assertEqual(list(self.root.iterdir()), [self.output])

    def test_missing_parent_not_created(self):
        self.assert_failure(self.invoke("--init", self.root / "missing" / "draft.json"))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_incompatible_flags_and_positionals_rejected(self):
        for flags in (("--check",), ("--strict",), ("--diagnostics", "text"), ("--diagnostics", "json"), ("--check-assets",), ("--layout", "table"), ("--layout", "sections"), ("input.json",), ("input.json", "out.md")):
            with self.subTest(flags=flags):
                self.assert_failure(self.invoke("--init", self.output, *flags), 2)
                self.assertEqual(list(self.root.iterdir()), [])
        self.assert_failure(self.invoke("--init"), 2)

    def test_publication_failure_cleans_temporary_file(self):
        with mock.patch("os.link", side_effect=PermissionError("injected publication failure")):
            self.assert_failure(self.invoke("--init", self.output))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_replace_failure_preserves_output_and_cleans_temp(self):
        self.output.write_bytes(b"keep")
        with mock.patch("os.replace", side_effect=PermissionError("injected replace failure")):
            self.assert_failure(self.invoke("--init", self.output, "--force"))
        self.assertEqual(self.output.read_bytes(), b"keep")
        self.assertEqual(list(self.root.iterdir()), [self.output])

    def test_partial_write_failure_preserves_output_and_cleans_temp(self):
        self.output.write_bytes(b"keep")
        real_fdopen = os.fdopen
        def failing_fdopen(*args, **kwargs):
            stream = real_fdopen(*args, **kwargs)
            real_write = stream.write
            def fail(text):
                real_write(text[:10])
                raise OSError("injected disk full")
            stream.write = fail
            return stream
        with mock.patch("os.fdopen", side_effect=failing_fdopen):
            self.assert_failure(self.invoke("--init", self.output, "--force"))
        self.assertEqual(self.output.read_bytes(), b"keep")
        self.assertEqual(list(self.root.iterdir()), [self.output])

    def test_atomic_race_does_not_clobber_new_destination(self):
        real_link = os.link
        def race(source, destination, *args, **kwargs):
            self.output.write_bytes(b"racing writer")
            return real_link(source, destination, *args, **kwargs)
        with mock.patch("os.link", side_effect=race):
            self.assert_failure(self.invoke("--init", self.output))
        self.assertEqual(self.output.read_bytes(), b"racing writer")
        self.assertEqual(list(self.root.iterdir()), [self.output])

    def test_destination_rechecked_after_write(self):
        real_fdopen = os.fdopen
        def racing_fdopen(*args, **kwargs):
            stream = real_fdopen(*args, **kwargs)
            real_write = stream.write
            def race(text):
                result = real_write(text)
                self.output.symlink_to(self.root / "absent")
                return result
            stream.write = race
            return stream
        with mock.patch("os.fdopen", side_effect=racing_fdopen):
            self.assert_failure(self.invoke("--init", self.output, "--force"))
        self.assertTrue(self.output.is_symlink())
        self.assertEqual(list(self.root.iterdir()), [self.output])

    def test_init_works_independent_of_cwd_and_locale(self):
        result = subprocess.run([sys.executable, "-m", "reference_atlas.cli", "--init", str(self.output)], cwd=self.root, env=dict(os.environ, PYTHONPATH=str(ROOT / "src"), LC_ALL="C", PYTHONUTF8="0", PYTHONCOERCECLOCALE="0"), capture_output=True, encoding="utf-8", timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(validate_atlas(json.loads(self.output.read_text(encoding="utf-8"))), [])

    def test_literal_init_filename_remains_legacy_input(self):
        source = self.root / "init"
        source.write_bytes((ROOT / "examples/atlas.json").read_bytes())
        result = self.invoke(source, self.output)
        self.assertEqual(result[0], 0, result[2])
        self.assertTrue(self.output.read_text(encoding="utf-8").startswith("#"))

    def test_layout_explicit_forwarding_and_omitted_compatibility(self):
        source = ROOT / "examples/atlas.json"
        data = json.loads(source.read_text(encoding="utf-8"))
        for layout in (None, "table", "sections"):
            with self.subTest(layout=layout), mock.patch.object(cli, "render_markdown", return_value="# Rendered\n") as render:
                flags = () if layout is None else ("--layout", layout)
                result = self.invoke(source, self.output, "--force", *flags)
                self.assertEqual(result[0], 0, result[2])
                if layout is None:
                    render.assert_called_once_with(data)
                else:
                    render.assert_called_once_with(data, layout=layout)
                self.assertEqual(self.output.read_text(encoding="utf-8"), "# Rendered\n")

    def test_layout_invalid_or_check_combination_rejected(self):
        source = ROOT / "examples/atlas.json"
        for args in ((source, self.output, "--layout", "other"), (source, "--check", "--layout", "table"), (source, "--check", "--layout", "sections")):
            self.assert_failure(self.invoke(*args), 2)
            self.assertEqual(list(self.root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
