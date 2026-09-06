"""Render an atlas without risking the source or an existing destination."""

import argparse
from importlib import resources
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

from .atlas import render_markdown
from .validation import inspect_atlas


def _check_destination(source_stat, output: Path, force: bool) -> os.stat_result | None:
    try:
        destination_stat = output.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(destination_stat.st_mode):
        raise OSError(f"{output}: output symlinks are not allowed")
    if not stat.S_ISREG(destination_stat.st_mode):
        raise OSError(f"{output}: output must be a regular file")
    if source_stat is not None and os.path.samestat(source_stat, destination_stat):
        raise OSError(f"{output}: input and output must be different files")
    if not force:
        raise FileExistsError(f"{output}: output already exists (use --force to overwrite)")
    return destination_stat


def _publish(markdown: str, source_stat, output: Path, force: bool) -> None:
    """Write fully, then publish atomically; never clobber without --force."""
    _check_destination(source_stat, output, force)
    # Keep unfinished content private while letting the kernel apply the real
    # umask to a normal 0666 creation. Reading umask via os.umask would race
    # with other threads; mkstemp would instead impose an unwanted 0600 mode.
    staging = Path(tempfile.mkdtemp(prefix=".reference-atlas-", dir=output.parent))
    temporary = staging / "output.tmp"
    try:
        if os.name == "posix":
            # Restore private traversal while retaining directory setgid
            # inheritance; output files still receive their own umask/mode.
            staging_mode = staging.stat().st_mode
            inherited_setgid = staging_mode & stat.S_ISGID
            if staging_mode & 0o700 != 0o700:
                os.chmod(staging, 0o700 | inherited_setgid)
                if inherited_setgid and not staging.stat().st_mode & stat.S_ISGID:
                    raise PermissionError("cannot preserve staging directory group inheritance")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        try:
            stream = os.fdopen(fd, "w", encoding="utf-8", newline="\n")
        except BaseException:
            os.close(fd)
            raise
        with stream:
            stream.write(markdown)
            stream.flush()
            # Use the rechecked destination, not a stale pre-write mode. Only
            # ordinary POSIX permissions survive replacement, never special bits.
            destination_stat = _check_destination(source_stat, output, force)
            if destination_stat is not None and os.name == "posix":
                os.fchmod(stream.fileno(), destination_stat.st_mode & 0o777)
        if force:
            os.replace(temporary, output)
        else:
            # A rename would overwrite a file created after our check. Linking
            # instead provides atomic create-if-absent on the same filesystem.
            os.link(temporary, output)
    finally:
        try:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
        finally:
            staging.rmdir()


def _error(path: str, message: object, code: int) -> int:
    print(f"reference-atlas: {path}: {message}", file=sys.stderr)
    return code


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _json_diagnostics(diagnostics):
    valid = not any(item["severity"] == "error" for item in diagnostics)
    ready = valid and not any(item["severity"] == "warning" for item in diagnostics)
    print(json.dumps({"valid": valid, "ready": ready, "diagnostics": diagnostics}, ensure_ascii=True))


def _load_error(args, message, exit_code):
    if args.check and args.diagnostics == "json":
        # The decoder cannot provide a reliable JSON pointer. Preserve its
        # location (when available) and the source filename in the message.
        _json_diagnostics([{
            "code": "io_error" if exit_code == 3 else "invalid_json",
            "severity": "error", "path": "",
            "message": f"{args.atlas}: {message}",
        }])
        return exit_code
    return _error(args.atlas, message, exit_code)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("atlas", nargs="?")
    parser.add_argument("output", nargs="?")
    parser.add_argument("--init", metavar="OUTPUT", help="create an original-only v2 draft")
    parser.add_argument("--layout", choices=("table", "sections"), default=None)
    parser.add_argument("--force", action="store_true", help="overwrite an existing regular output file")
    parser.add_argument("--check", action="store_true", help="inspect without writing output")
    parser.add_argument("--strict", action="store_true", help="reject warnings as well as errors")
    parser.add_argument("--diagnostics", choices=("text", "json"), default=None)
    parser.add_argument("--check-assets", action="store_true", help="inspect local asset paths without fetching URLs")
    args = parser.parse_args()
    if args.init is not None:
        if args.atlas is not None or args.output is not None:
            parser.error("--init cannot be combined with positional inputs")
        if args.check or args.strict or args.diagnostics is not None or args.check_assets or args.layout is not None:
            parser.error("--init cannot be combined with --check, --strict, --diagnostics, --check-assets or --layout")
        try:
            starter = resources.files("reference_atlas.resources").joinpath("starter.json").read_text(encoding="utf-8")
            _publish(starter, None, Path(args.init), args.force)
        except OSError as error:
            return _error(args.init, error, 3)
        print(args.init)
        return 0
    if args.atlas is None:
        parser.error("atlas is required unless --init is used")
    if args.diagnostics is None:
        args.diagnostics = "text"
    if args.check:
        if args.layout is not None:
            parser.error("--layout cannot be combined with --check")
        if args.output is not None:
            parser.error("--check cannot be combined with an output path")
        if args.force:
            parser.error("--force cannot be combined with --check")
    else:
        if args.output is None:
            parser.error("output is required unless --check is used")
        if args.diagnostics == "json":
            parser.error("--diagnostics json requires --check")

    try:
        with Path(args.atlas).open(encoding="utf-8") as source:
            source_stat = os.fstat(source.fileno())
            try:
                data = json.load(source, object_pairs_hook=_unique_object)
            except UnicodeDecodeError:
                raise  # Preserve the dedicated UTF-8 diagnostic below.
            except json.JSONDecodeError as error:
                return _load_error(args, error, 2)
            except (ValueError, RecursionError) as error:
                return _load_error(args, f"invalid JSON: {error}", 2)
    except UnicodeDecodeError as error:
        return _load_error(args, f"invalid UTF-8: {error}", 2)
    except OSError as error:
        return _load_error(args, error, 3)

    # Inspect explicitly: unexpected renderer bugs must retain their traceback.
    diagnostics = inspect_atlas(
        data, base_dir=Path(args.atlas).parent, check_assets=args.check_assets,
    )
    invalid = any(item["severity"] == "error" for item in diagnostics)
    markdown = None
    if not invalid:
        markdown = render_markdown(data) if args.layout is None else render_markdown(data, layout=args.layout)
        # JSON permits escaped lone surrogates. Check the actual rendered text
        # before certifying validity or creating any publication temporary file.
        try:
            markdown.encode("utf-8")
        except UnicodeEncodeError as error:
            diagnostics.append({
                "code": "invalid_unicode", "severity": "error", "path": "",
                "message": f"invalid UTF-8 text: {error}",
            })
            invalid = True
    warnings = any(item["severity"] == "warning" for item in diagnostics)
    rejected = invalid or (args.strict and warnings)
    if args.check and args.diagnostics == "json":
        _json_diagnostics(diagnostics)
        return 2 if rejected else 0
    for item in diagnostics:
        _error(args.atlas, f"{item['severity']} [{item['code']}] {item['path']}: {item['message']}", 2)
    if rejected:
        return 2
    if args.check:
        print("valid")
        return 0
    assert args.output is not None
    assert markdown is not None
    try:
        _publish(markdown, source_stat, Path(args.output), args.force)
    except OSError as error:
        return _error(args.output, error, 3)

    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
