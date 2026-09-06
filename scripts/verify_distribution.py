#!/usr/bin/env python3
"""Build sdist -> wheel and exercise only the installed artifact.

Run: python scripts/verify_distribution.py (install build first).
All builds and environments use disposable directories outside the checkout.
The checkout itself is never moved or changed. No runtime third-party imports.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile


def clean_environment(environment=None):
    env = dict(os.environ if environment is None else environment)
    for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(name, None)
    env.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1", PIP_DISABLE_PIP_VERSION_CHECK="1")
    return env


def run(command, cwd, env, expected=0):
    print("+", " ".join(map(str, command)), flush=True)
    result = subprocess.run(list(map(str, command)), cwd=cwd, env=env,
                            capture_output=True, text=True, encoding="utf-8", timeout=300)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != expected:
        raise RuntimeError(f"expected exit {expected}, got {result.returncode}: {command}")
    output = (result.stdout + result.stderr).lower()
    if "license" in output and ("setuptoolsdeprecationwarning" in output or "license classifiers are deprecated" in output):
        raise RuntimeError("deprecated license metadata emitted a build warning")
    return result


def main():
    root = Path(__file__).resolve().parents[1]
    env = clean_environment()
    with tempfile.TemporaryDirectory(prefix="reference-atlas-dist-") as temporary:
        work = Path(temporary).resolve()
        if work == root or root in work.parents:
            raise RuntimeError("temporary directory must be outside the checkout; set TMPDIR")
        snapshot = work / "snapshot"
        shutil.copytree(root, snapshot, ignore=shutil.ignore_patterns(
            ".git", ".venv", "venv", "__pycache__", "*.pyc", "*.egg-info", "build", "dist", ".pytest_cache"))
        artifacts = work / "artifacts"
        run([sys.executable, "-m", "build", "--sdist", "--outdir", artifacts, snapshot], work, env)
        sdists = list(artifacts.glob("*.tar.gz"))
        if len(sdists) != 1:
            raise RuntimeError(f"expected one sdist, got {sdists}")
        unpacked = work / "unpacked"
        unpacked.mkdir()
        with tarfile.open(sdists[0]) as archive:
            # Only regular files/directories inside one archive root are needed.
            # Validate ourselves for compatibility with Python 3.10's tar API.
            for member in archive.getmembers():
                target = (unpacked / member.name).resolve()
                if unpacked not in target.parents or not (member.isfile() or member.isdir()):
                    raise RuntimeError(f"unsafe sdist member: {member.name}")
            archive.extractall(unpacked)
        roots = list(unpacked.iterdir())
        if len(roots) != 1 or not roots[0].is_dir():
            raise RuntimeError("sdist must contain one project directory")
        extracted = roots[0]
        required = [Path(name) for name in ("SKILL.md", "ATTRIBUTION.md", "README.md", "CHANGELOG.md", "LICENSE", "requirements-test.txt", "pyproject.toml", "MANIFEST.in")]
        for folder in ("tests", "examples", "docs", "schemas", "scripts"):
            required.extend(p.relative_to(snapshot) for p in (snapshot / folder).rglob("*") if p.is_file())
        for relative in required:
            if not (extracted / relative).is_file():
                raise RuntimeError(f"missing from sdist: {relative}")
            if (snapshot / relative).read_bytes() != (extracted / relative).read_bytes():
                raise RuntimeError(f"sdist changed file: {relative}")
        run([sys.executable, "-m", "build", "--wheel", "--outdir", artifacts, extracted], work, env)
        wheels = list(artifacts.glob("*.whl"))
        if len(wheels) != 1:
            raise RuntimeError(f"expected one wheel, got {wheels}")
        # Remove both source trees before running anything from the wheel.
        # Existing test subprocess helpers set PYTHONPATH to extracted/src;
        # this path now does not exist and cannot mask missing wheel modules.
        shutil.move(extracted / "src", work / "hidden-sdist-source")
        shutil.move(snapshot / "src", work / "hidden-snapshot-source")
        environment = work / "installed"
        run([sys.executable, "-m", "venv", environment], work, env)
        bin_dir = environment / ("Scripts" if os.name == "nt" else "bin")
        python = bin_dir / ("python.exe" if os.name == "nt" else "python")
        cli = bin_dir / ("reference-atlas.exe" if os.name == "nt" else "reference-atlas")
        run([python, "-m", "pip", "install", "--no-deps", wheels[0]], work, env)
        probe = '''import importlib.metadata as m, importlib.resources as r, json, pathlib, sysconfig
import reference_atlas
site = pathlib.Path(sysconfig.get_path("purelib")).resolve()
assert site in pathlib.Path(reference_atlas.__file__).resolve().parents
assert m.version("reference-atlas") == "0.2.0"
assert not m.requires("reference-atlas")
assert m.metadata("reference-atlas")["License-Expression"] == "MIT"
bundle = r.files("reference_atlas.resources")
for name in ("starter.json", "atlas-v2.schema.json"):
    assert json.loads(bundle.joinpath(name).read_text(encoding="utf-8"))
assert not any(str(p).endswith("SKILL.md") for p in m.files("reference-atlas"))
print("Verified installed import:", reference_atlas.__file__)
'''
        run([python, "-I", "-c", probe], work, env)
        outside = work / "consumer"
        outside.mkdir()
        run([cli, "--help"], outside, env)
        starter = outside / "starter.json"
        run([cli, "--init", starter], outside, env)
        initial = starter.read_bytes()
        if json.loads(initial)["schema_version"] != 2 or set(outside.iterdir()) != {starter}:
            raise RuntimeError("init must create only a v2 JSON file, no assets")
        run([cli, "--init", starter], outside, env, expected=3)
        if starter.read_bytes() != initial:
            raise RuntimeError("init clobbered existing file")
        starter.write_text("replace me", encoding="utf-8")
        run([cli, "--init", starter, "--force"], outside, env)
        if starter.read_bytes() != initial:
            raise RuntimeError("forced init was not deterministic")
        result = run([cli, starter, "--check", "--check-assets", "--diagnostics", "json"], outside, env)
        report = json.loads(result.stdout)
        if report["valid"] is not True or report["ready"] is not False:
            raise RuntimeError("starter must be valid but not ready")
        run([cli, starter, "--check", "--strict"], outside, env, expected=2)
        broken = outside / "broken.json"
        broken.write_text("{", encoding="utf-8")
        result = run([cli, broken, outside / "broken.md"], outside, env, expected=2)
        if "Traceback" in result.stderr or (outside / "broken.md").exists():
            raise RuntimeError("invalid JSON must fail cleanly without output")
        for example, golden, default_layout in (("atlas.json", "example-atlas.md", "table"), ("atlas-v2.json", "example-atlas-v2.md", "sections")):
            source = extracted / "examples" / example
            default = outside / (example + ".md")
            run([cli, source, default], outside, env)
            if default.read_bytes() != (extracted / "docs" / golden).read_bytes():
                raise RuntimeError(f"default rendering changed: {example}")
            for layout in ("table", "sections"):
                output = outside / (example + "." + layout + ".md")
                run([cli, source, output, "--layout", layout], outside, env)
                if not output.read_bytes():
                    raise RuntimeError(f"empty {layout} layout")
                if layout == default_layout and output.read_bytes() != default.read_bytes():
                    raise RuntimeError(f"default is not {layout}: {example}")
        # The CLI/resources were exercised before any test dependencies existed.
        run([python, "-m", "pip", "install", "-r", extracted / "requirements-test.txt"], work, env)
        run([python, "-I", "-m", "unittest", "discover", "-s", "tests", "-v"], extracted, env)
        print("PASS: sdist contents, wheel-only imports/resources/CLI, golden defaults, both layouts, and shipped tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
