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

from reference_atlas import cli
from reference_atlas.atlas import render_markdown


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "atlas.json"
        self.output = self.root / "atlas.md"
        self.data = json.loads((ROOT / "examples/atlas.json").read_text(encoding="utf-8"))
        self.data["project"] = "Café 日本語"
        self.original = json.dumps(self.data, ensure_ascii=False).encode("utf-8")
        self.source.write_bytes(self.original)

    def run_cli(self, *args, env=None):
        environment = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONDONTWRITEBYTECODE="1")
        if env:
            environment.update(env)
        return subprocess.run(
            [sys.executable, "-m", "reference_atlas.cli", *map(str, args)],
            cwd=self.root, env=environment, capture_output=True, encoding="utf-8", timeout=10,
        )

    def assert_error(self, result, code, path=None):
        self.assertEqual(result.returncode, code, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertTrue(result.stderr.strip())
        self.assertNotIn("Traceback", result.stderr)
        if path is not None:
            self.assertIn(str(path), result.stderr)

    def invoke(self, force=False):
        args = ["reference-atlas", str(self.source), str(self.output)]
        if force:
            args.append("--force")
        stderr = io.StringIO()
        with mock.patch.object(sys, "argv", args), contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
            try:
                code = cli.main()
            except SystemExit as error:
                code = error.code
        self.assertEqual(code, 3, stderr.getvalue())
        self.assertTrue(stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())
        return stderr.getvalue()

    def assert_unchanged(self, old_output=None):
        self.assertEqual(self.source.read_bytes(), self.original)
        if old_output is None:
            self.assertFalse(self.output.exists())
            expected = {self.source.name}
        else:
            self.assertEqual(self.output.read_bytes(), old_output)
            expected = {self.source.name, self.output.name}
        self.assertEqual({p.name for p in self.root.iterdir()}, expected)

    def test_two_positionals_utf8_success(self):
        result = self.run_cli(self.source, self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, str(self.output) + "\n")
        self.assertEqual(result.stderr, "")
        self.assertEqual(self.output.read_bytes(), render_markdown(self.data).encode("utf-8"))
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_utf8_is_independent_of_locale(self):
        result = self.run_cli(self.source, self.output, env={"LC_ALL": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Café 日本語", self.output.read_text(encoding="utf-8"))

    def test_existing_output_requires_force(self):
        self.output.write_bytes(b"keep me")
        self.assert_error(self.run_cli(self.source, self.output), 3, self.output)
        self.assert_unchanged(b"keep me")

    def test_force_replaces_regular_output(self):
        self.output.write_bytes(b"old")
        result = self.run_cli(self.source, self.output, "--force")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_bytes(), render_markdown(self.data).encode("utf-8"))
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertEqual(len(list(self.root.iterdir())), 2)

    def test_same_source_rejected_even_with_force(self):
        for flags in ((), ("--force",)):
            with self.subTest(flags=flags):
                self.assert_error(self.run_cli(self.source, self.source, *flags), 3, self.source)
                self.assertEqual(self.source.read_bytes(), self.original)

    def test_hardlink_source_rejected_even_with_force(self):
        os.link(self.source, self.output)
        for flags in ((), ("--force",)):
            with self.subTest(flags=flags):
                self.assert_error(self.run_cli(self.source, self.output, *flags), 3, self.output)
                self.assert_unchanged(self.original)

    def test_output_symlinks_rejected_even_with_force(self):
        target = self.root / "target"
        target.write_bytes(b"target")
        for destination in (self.source, target, self.root / "missing"):
            for flags in ((), ("--force",)):
                with self.subTest(destination=destination, flags=flags):
                    self.output.symlink_to(destination)
                    try:
                        self.assert_error(self.run_cli(self.source, self.output, *flags), 3, self.output)
                        self.assertTrue(self.output.is_symlink())
                        self.assertEqual(self.source.read_bytes(), self.original)
                        self.assertEqual(target.read_bytes(), b"target")
                        self.assertFalse((self.root / "missing").exists())
                    finally:
                        self.output.unlink()

    def test_symlink_input_alias_rejected(self):
        alias = self.root / "input-alias"
        alias.symlink_to(self.source)
        self.assert_error(self.run_cli(alias, self.source, "--force"), 3, self.source)
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_directory_destination_rejected(self):
        self.output.mkdir()
        for flags in ((), ("--force",)):
            self.assert_error(self.run_cli(self.source, self.output, *flags), 3, self.output)
        self.assertTrue(self.output.is_dir())
        self.assertEqual(list(self.output.iterdir()), [])

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires FIFO support")
    def test_special_destination_rejected(self):
        os.mkfifo(self.output)
        # Force first: the old CLI exits on the unknown flag rather than hanging on a FIFO.
        self.assert_error(self.run_cli(self.source, self.output, "--force"), 3, self.output)
        self.assert_error(self.run_cli(self.source, self.output), 3, self.output)

    def test_missing_input(self):
        missing = self.root / "missing.json"
        self.assert_error(self.run_cli(missing, self.output), 3, missing)
        self.assert_unchanged()

    def test_missing_output_parent(self):
        output = self.root / "missing" / "atlas.md"
        self.assert_error(self.run_cli(self.source, output), 3, output)
        self.assert_unchanged()

    def test_malformed_json_reports_location(self):
        self.source.write_bytes(b'{\n  "project":\n}')
        result = self.run_cli(self.source, self.output)
        self.assert_error(result, 2, self.source)
        self.assertIn("line 3", result.stderr)
        self.assertIn("column 1", result.stderr)
        self.assertFalse(self.output.exists())

    def test_invalid_utf8(self):
        self.source.write_bytes(b'\xff')
        self.assert_error(self.run_cli(self.source, self.output), 2, self.source)
        self.assertFalse(self.output.exists())

    def test_lone_surrogate_preserves_existing_output_with_force(self):
        for surrogate in ("\ud800", "\udfff"):
            with self.subTest(surrogate=ascii(surrogate)):
                self.data["project"] = surrogate
                self.original = json.dumps(self.data, ensure_ascii=True).encode("utf-8")
                self.source.write_bytes(self.original)
                self.output.write_bytes(b"keep")
                result = self.run_cli(self.source, self.output, "--force")
                self.assert_error(result, 2, self.source)
                self.assertEqual(len(result.stderr.splitlines()), 1)
                self.assertIn("UTF-8", result.stderr)
                self.assert_unchanged(b"keep")

    def test_oversized_integer_preserves_existing_output_with_force(self):
        # Query the child interpreter: Python 3.10 may lack the digit-limit
        # API, and a configured limit of zero explicitly disables the guard.
        probe = subprocess.run(
            [sys.executable, "-c", "import sys; print(getattr(sys, 'get_int_max_str_digits', lambda: 0)())"],
            capture_output=True, encoding="utf-8", check=True, timeout=10,
        )
        limit = int(probe.stdout)
        if not limit:
            self.skipTest("interpreter has no configured integer digit limit")
        digits = b"9" * max(5000, limit + 1)
        self.original = self.original.rstrip()[:-1] + b', "unused": ' + digits + b'}'
        self.source.write_bytes(self.original)
        self.output.write_bytes(b"keep")
        result = self.run_cli(self.source, self.output, "--force")
        self.assert_error(result, 2, self.source)
        self.assertEqual(len(result.stderr.splitlines()), 1)
        self.assertIn("invalid JSON", result.stderr)
        self.assert_unchanged(b"keep")

    def test_excessive_nesting_preserves_existing_output_with_force(self):
        # The C JSON decoder's nesting limit can differ from Python's
        # recursion limit: 3.12 accepts 2,000 levels and 3.14 accepts 50,000.
        # Keep the input bounded while exceeding those decoder limits.
        depth = 100_000
        nested = b"[" * depth + b"0" + b"]" * depth
        self.original = self.original.rstrip()[:-1] + b', "unused": ' + nested + b'}'
        self.source.write_bytes(self.original)
        self.output.write_bytes(b"keep")
        result = self.run_cli(self.source, self.output, "--force")
        self.assert_error(result, 2, self.source)
        self.assertEqual(len(result.stderr.splitlines()), 1)
        self.assertIn("invalid JSON", result.stderr)
        self.assert_unchanged(b"keep")

    def test_renderer_recursion_errors_are_not_swallowed(self):
        self.output.write_bytes(b"keep")
        with mock.patch.object(cli, "render_markdown", side_effect=RecursionError("programming bug")):
            with self.assertRaisesRegex(RecursionError, "programming bug"):
                self.invoke(force=True)
        self.assert_unchanged(b"keep")

    def test_schema_failure_preserves_existing_output_with_force(self):
        for invalid in (None, {}, {"project": 123}):
            with self.subTest(invalid=invalid):
                payload = json.dumps(invalid).encode("utf-8")
                self.source.write_bytes(payload)
                self.output.write_bytes(b"keep")
                self.assert_error(self.run_cli(self.source, self.output, "--force"), 2, self.source)
                self.assertEqual(self.output.read_bytes(), b"keep")
                self.assertEqual(self.source.read_bytes(), payload)
                self.assertEqual(len(list(self.root.iterdir())), 2)

    def test_usage_errors(self):
        for args in ((), (self.source,), (self.source, self.output, "--unknown")):
            self.assert_error(self.run_cli(*args), 2)

    def test_failed_replace_cleans_temp_preserves_files(self):
        self.output.write_bytes(b"keep")
        with mock.patch("os.replace", side_effect=PermissionError("injected replace failure")):
            self.invoke(force=True)
        self.assert_unchanged(b"keep")

    def test_failed_publication_cleans_temp(self):
        with mock.patch("os.link", side_effect=PermissionError("injected link failure")):
            self.invoke()
        self.assert_unchanged()

    def test_partial_write_failure_cleans_temp_preserves_files(self):
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
            self.invoke(force=True)
        self.assert_unchanged(b"keep")

    def test_racing_destination_is_not_overwritten(self):
        real_link = os.link

        def race(source, destination, *args, **kwargs):
            self.output.write_bytes(b"racing writer")
            return real_link(source, destination, *args, **kwargs)

        with mock.patch("os.link", side_effect=race):
            self.invoke()
        self.assert_unchanged(b"racing writer")

    def test_programming_errors_are_not_swallowed(self):
        with mock.patch.object(cli, "render_markdown", side_effect=ValueError("programming bug")):
            with self.assertRaisesRegex(ValueError, "programming bug"):
                self.invoke()
        self.assert_unchanged()


if __name__ == "__main__":
    unittest.main()
