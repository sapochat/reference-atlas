"""POSIX publication modes, tested with kernel-applied child umasks."""

import contextlib
from importlib import resources
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from reference_atlas import cli
from reference_atlas.atlas import render_markdown


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "posix", "requires POSIX permission semantics")
class OutputPermissionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "atlas.json"
        self.original = (ROOT / "examples/atlas.json").read_bytes()
        self.source.write_bytes(self.original)
        self.output = self.root / "output"

    def args(self, operation, force=False):
        args = ["--init", str(self.output)] if operation == "init" else [str(self.source), str(self.output)]
        return args + (["--force"] if force else [])

    def expected(self, operation):
        if operation == "init":
            return resources.files("reference_atlas.resources").joinpath("starter.json").read_bytes()
        return render_markdown(json.loads(self.original)).encode("utf-8")

    def run_child(self, operation, mask, force=False):
        # subprocess applies the mask only in the child before exec. Forbid
        # even a temporary process-global umask change in the actual CLI.
        script = (
            "from unittest.mock import patch\n"
            "from reference_atlas import cli\n"
            "with patch.object(cli.os, 'umask', side_effect=AssertionError('global umask mutation')):\n"
            "    raise SystemExit(cli.main())\n"
        )
        return subprocess.run(
            [sys.executable, "-c", script, *self.args(operation, force)],
            cwd=self.root, env=dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONDONTWRITEBYTECODE="1"),
            umask=mask, capture_output=True, text=True, timeout=10,
        )

    def assert_success(self, result, operation, mode):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, str(self.output) + "\n")
        self.assertEqual(result.stderr, "")
        self.assertEqual(self.output.read_bytes(), self.expected(operation))
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), mode)
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertEqual(set(self.root.iterdir()), {self.source, self.output})

    def test_new_outputs_honor_umask(self):
        for operation in ("init", "render"):
            for mask in (0o022, 0o002, 0o077):
                with self.subTest(operation=operation, umask=oct(mask)):
                    self.output.unlink(missing_ok=True)
                    self.assert_success(self.run_child(operation, mask), operation, 0o666 & ~mask)

    def test_force_absent_outputs_honor_umask(self):
        for operation in ("init", "render"):
            for mask in (0o022, 0o002, 0o077):
                with self.subTest(operation=operation, umask=oct(mask)):
                    self.output.unlink(missing_ok=True)
                    self.assert_success(self.run_child(operation, mask, True), operation, 0o666 & ~mask)

    def test_force_preserves_existing_ordinary_mode_regardless_of_umask(self):
        for operation in ("init", "render"):
            for mask in (0o022, 0o002, 0o077):
                for mode in (0o600, 0o640, 0o664, 0o751):
                    with self.subTest(operation=operation, umask=oct(mask), mode=oct(mode)):
                        self.output.write_bytes(b"keep")
                        self.output.chmod(mode)
                        self.assert_success(self.run_child(operation, mask, True), operation, mode)

    def test_owner_restrictive_umasks_do_not_block_staging(self):
        for operation in ("init", "render"):
            for mask in (0o700, 0o777):
                for scenario in ("new", "force_absent", "force_existing"):
                    with self.subTest(operation=operation, mask=oct(mask), scenario=scenario):
                        self.output.unlink(missing_ok=True)
                        if scenario == "force_existing":
                            self.output.write_bytes(b"keep")
                            self.output.chmod(0o640)
                        result = self.run_child(operation, mask, scenario != "new")
                        self.assertEqual(result.returncode, 0, result.stderr)
                        expected_mode = 0o640 if scenario == "force_existing" else 0o666 & ~mask
                        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), expected_mode)
                        # Inspect content only after asserting its deliberately
                        # unreadable final mode; restore owner access for the test.
                        self.output.chmod(0o600)
                        self.assert_success(result, operation, 0o600)

    def test_force_strips_special_bits(self):
        for operation in ("init", "render"):
            for special in (stat.S_ISUID, stat.S_ISGID, stat.S_ISVTX):
                with self.subTest(operation=operation, special=oct(special)):
                    self.output.write_bytes(b"keep")
                    self.output.chmod(special | 0o754)
                    if not self.output.stat().st_mode & special:
                        self.skipTest("filesystem does not retain requested special bit")
                    self.assert_success(self.run_child(operation, 0o077, True), operation, 0o754)

    def invoke(self, operation, force=False):
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", ["reference-atlas", *self.args(operation, force)]), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli.main()
        return code, stdout.getvalue(), stderr.getvalue()

    def test_chmod_failure_preserves_output_and_cleans_staging(self):
        for operation in ("init", "render"):
            with self.subTest(operation=operation):
                self.output.write_bytes(b"keep")
                self.output.chmod(0o640)
                with mock.patch.object(os, "fchmod", side_effect=PermissionError("injected chmod failure")):
                    code, stdout, stderr = self.invoke(operation, True)
                self.assertEqual(code, 3)
                self.assertEqual(stdout, "")
                self.assertIn("injected chmod failure", stderr)
                self.assertNotIn("Traceback", stderr)
                self.assertEqual(self.output.read_bytes(), b"keep")
                self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o640)
                self.assertEqual(set(self.root.iterdir()), {self.source, self.output})
                self.assertEqual(self.source.read_bytes(), self.original)

    def test_incomplete_content_is_inside_private_staging_directory(self):
        real_fdopen = os.fdopen
        for operation in ("init", "render"):
            for force in (False, True):
                with self.subTest(operation=operation, force=force):
                    self.output.unlink(missing_ok=True)
                    if force:
                        self.output.write_bytes(b"keep")
                        self.output.chmod(0o664)

                    def inspecting_fdopen(*args, **kwargs):
                        stream = real_fdopen(*args, **kwargs)
                        real_write = stream.write

                        def inspect(text):
                            real_write(text[:10])
                            stream.flush()
                            staging = list(self.root.glob(".reference-atlas-*"))
                            self.assertEqual(len(staging), 1)
                            self.assertTrue(staging[0].is_dir(), "partial content needs a private directory")
                            self.assertEqual(stat.S_IMODE(staging[0].stat().st_mode) & 0o077, 0)
                            if force:
                                self.assertEqual(self.output.read_bytes(), b"keep")
                            else:
                                self.assertFalse(self.output.exists())
                            raise OSError("injected partial write")

                        stream.write = inspect
                        return stream

                    with mock.patch.object(os, "fdopen", side_effect=inspecting_fdopen):
                        code, stdout, stderr = self.invoke(operation, force)
                    self.assertEqual(code, 3)
                    self.assertEqual(stdout, "")
                    self.assertIn("injected partial write", stderr)
                    expected = {self.source, self.output} if force else {self.source}
                    self.assertEqual(set(self.root.iterdir()), expected)


if __name__ == "__main__":
    unittest.main()
