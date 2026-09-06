"""Versioned, offline atlas validation and explicitly opt-in asset inspection.

The published JSON Schema describes v2 shapes. Cross-record identity/reference
constraints, exact Python integer version dispatch, readiness warnings, and file
containment are runtime checks. File existence never establishes visual fidelity.
"""
from collections.abc import Mapping
from pathlib import Path
import re
from urllib.parse import urlsplit


REQUIRED_ITEM = ("target", "reference", "borrow", "do_not_copy", "build_implication", "mobile", "attribution")
REQUIRED_ROOT = ("project", "design_read", "invariants", "hierarchy", "items")
CATEGORIES = ("typography", "layout", "motion", "imagery")
REQUIREMENTS = ("accessibility", "reduced_motion", "performance")
CRITERIA = ("mobile",) + REQUIREMENTS
IDENTIFIER = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*"
# Deliberately excludes credentials, whitespace, backslashes and unsupported schemes.
HTTP = r"[hH][tT][tT][pP][sS]?://(?![^/?#]*@)(?:\[[0-9a-fA-F:.]+\]|[^\s/:?#@\\]+)(?::[0-9]+)?(?:[/?#][^\s\\]*)?"
LOCAL = r"(?!/)(?![\s\S]*(?:^|/)\.\.(?:/|$))(?!\s*$)[^:\\\x00-\x1f\x7f]+"


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _matches(pattern, value):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def _pointer(path, key):
    return path + "/" + str(key).replace("~", "~0").replace("/", "~1")


class _Inspection:
    def __init__(self):
        self.diagnostics = []

    def add(self, code, path, message, severity="error"):
        self.diagnostics.append(dict(code=code, severity=severity, path=path, message=message))

    def warn(self, code, path, message):
        self.add(code, path, message, "warning")

    def obj(self, value, path, required=(), optional=()):
        if not isinstance(value, Mapping):
            self.add("type", path, f"{path or 'atlas'} must be an object")
            return False
        for key in required:
            if key not in value:
                self.add("required", _pointer(path, key), f"required field: {key}")
        for key in value:
            if key not in required and key not in optional:
                self.add("unknown_field", _pointer(path, key), f"unknown field: {key}")
        return True

    def text(self, value, path):
        if not _text(value):
            self.add("text", path, f"{path} must be non-empty text")
            return False
        return True

    def texts(self, obj, path, keys):
        for key in keys:
            if key in obj:
                self.text(obj[key], _pointer(path, key))

    def identifier(self, value, path):
        if not _matches(IDENTIFIER, value):
            self.add("identifier", path, f"{path} must be a lowercase kebab-case ID")

    def locator(self, value, path, *, remote_only=False, local_only=False):
        good = (not local_only and _matches(HTTP, value)) or (not remote_only and _matches(LOCAL, value))
        if good and _matches(HTTP, value):
            try:
                parsed = urlsplit(value)
                # Parsing validates bracketed addresses; accessing port checks range.
                good = bool(parsed.hostname) and (parsed.port is None or 0 <= parsed.port <= 65535)
            except ValueError:
                good = False
        if not good:
            kind = "absolute HTTP(S) URL without credentials" if remote_only else "safe relative path" if local_only else "safe relative path or absolute HTTP(S) URL without credentials"
            self.add("locator", path, f"{path} must be a {kind}")

    def enum(self, value, path, choices):
        if not isinstance(value, str) or value not in choices:
            self.add("enum", path, f"{path} must be one of: {', '.join(choices)}")

    def exclusive(self, value, path, first, second):
        if (first in value) == (second in value):
            self.add("exclusive", path, f"{path} requires exactly one of {first} or {second}")

    def legacy(self, data):
        for key in ("project", "design_read"):
            if not _text(data.get(key)):
                self.add("text", "/" + key, f"root field must be non-empty text: {key}")
        invariants = data.get("invariants")
        if not isinstance(invariants, list) or len(invariants) < 3:
            self.add("invariants", "/invariants", "invariants must contain at least three items")
        elif any(not _text(value) for value in invariants):
            self.add("invariants", "/invariants", "invariants must contain only non-empty text")
        hierarchy = data.get("hierarchy")
        if not isinstance(hierarchy, Mapping) or not hierarchy:
            self.add("hierarchy", "/hierarchy", "hierarchy must be a non-empty object")
        elif any(not _text(key) or not _text(value) for key, value in hierarchy.items()):
            self.add("hierarchy", "/hierarchy", "hierarchy keys and values must be non-empty text")
        items = data.get("items")
        if not isinstance(items, list) or not items:
            self.add("items", "/items", "items must be a non-empty list")
        else:
            for index, item in enumerate(items):
                path = f"/items/{index}"
                if not isinstance(item, Mapping):
                    self.add("type", path, f"item {index} must be an object")
                    continue
                for key in REQUIRED_ITEM:
                    if not _text(item.get(key)):
                        self.add("text", _pointer(path, key), f"item {index} field must be non-empty text: {key}")
        # Keep all legacy error text/order intact; extras are warnings only.
        for key in data:
            if key not in REQUIRED_ROOT + ("schema_version",):
                self.warn("unknown_field", _pointer("", key), f"unknown field is not rendered: {key}")
        if isinstance(items, list):
            for index, item in enumerate(items):
                if isinstance(item, Mapping):
                    for key in item:
                        if key not in REQUIRED_ITEM:
                            self.warn("unknown_field", _pointer(f"/items/{index}", key), f"unknown field is not rendered: {key}")

    def v2(self, data):
        self.obj(data, "", ("schema_version", "project", "design_read", "invariants", "sources", "hierarchy", "items"), ("asset_root",))
        self.texts(data, "", ("project", "design_read"))
        if "asset_root" in data:
            self.locator(data["asset_root"], "/asset_root", local_only=True)
        invariants = data.get("invariants")
        if not isinstance(invariants, list) or len(invariants) < 3:
            self.add("invariants", "/invariants", "invariants must contain at least three items")
        if isinstance(invariants, list):
            for index, invariant in enumerate(invariants):
                self.text(invariant, f"/invariants/{index}")
        sources = data.get("sources")
        if isinstance(sources, Mapping):
            for key, source in sources.items():
                path = _pointer("/sources", key)
                self.identifier(key, path)
                if self.obj(source, path, ("title", "locator", "attribution"), ("url", "rights_notes")):
                    self.texts(source, path, ("title", "attribution", "rights_notes"))
                    if "locator" in source:
                        self.locator(source["locator"], path + "/locator")
                    if "url" in source:
                        self.locator(source["url"], path + "/url", remote_only=True)
        else:
            self.add("type", "/sources", "sources must be an object")
        hierarchy = data.get("hierarchy")
        if self.obj(hierarchy, "/hierarchy", optional=CATEGORIES):
            for key, entry in hierarchy.items():
                path = _pointer("/hierarchy", key)
                if self.obj(entry, path, ("reason",), ("source", "decision")):
                    self.texts(entry, path, ("reason",))
                    self.exclusive(entry, path, "source", "decision")
                    if "source" in entry:
                        self.identifier(entry["source"], path + "/source")
                    if "decision" in entry:
                        self.enum(entry["decision"], path + "/decision", ("original", "not_applicable"))
        items = data.get("items")
        if not isinstance(items, list) or not items:
            self.add("items", "/items", "items must be a non-empty list")
            return
        for index, item in enumerate(items):
            path = f"/items/{index}"
            if not self.obj(item, path, ("id", "target", "build_implication", "mobile"), ("references", "original_design", "requirements", "checks")):
                continue
            if "id" in item:
                self.identifier(item["id"], path + "/id")
            self.texts(item, path, ("target", "build_implication", "mobile", "original_design"))
            self.exclusive(item, path, "references", "original_design")
            if "references" in item:
                refs = item["references"]
                if not isinstance(refs, list) or not refs:
                    self.add("references", path + "/references", "references must be a non-empty list")
                if isinstance(refs, list):
                    for ri, ref in enumerate(refs):
                        rp = f"{path}/references/{ri}"
                        if self.obj(ref, rp, ("source", "borrow", "do_not_copy"), ("evidence",)):
                            self.texts(ref, rp, ("borrow", "do_not_copy"))
                            if "source" in ref:
                                self.identifier(ref["source"], rp + "/source")
                            if "evidence" in ref:
                                self.locator(ref["evidence"], rp + "/evidence")
            if "requirements" in item and self.obj(item["requirements"], path + "/requirements", optional=REQUIREMENTS):
                self.texts(item["requirements"], path + "/requirements", REQUIREMENTS)
            if "checks" in item:
                if not isinstance(item["checks"], list):
                    self.add("type", path + "/checks", "checks must be a list")
                else:
                    for ci, check in enumerate(item["checks"]):
                        self.check(check, f"{path}/checks/{ci}")

    def check(self, check, path):
        if not self.obj(check, path, ("criterion", "status"), ("method", "evidence", "note", "reason")):
            return
        if "criterion" in check:
            self.enum(check["criterion"], path + "/criterion", CRITERIA)
        if "status" in check:
            self.enum(check["status"], path + "/status", ("not_checked", "pass", "fail", "not_applicable"))
        self.texts(check, path, ("method", "note", "reason"))
        if "evidence" in check:
            self.locator(check["evidence"], path + "/evidence")
        status = check.get("status")
        needed = ("method", "evidence") if status in ("pass", "fail") else ("reason",) if status == "not_applicable" else ()
        for key in needed:
            if key not in check:
                self.add("required", path + "/" + key, f"{status} check requires {key}")

    def semantics(self, data):
        seen = set()
        for index, value in enumerate(data["invariants"]):
            if value in seen:
                self.warn("duplicate_invariant", f"/invariants/{index}", "duplicate invariant")
            seen.add(value)
        sources = data["sources"]
        for category in CATEGORIES:
            path = "/hierarchy/" + category
            entry = data["hierarchy"].get(category)
            if entry is None:
                self.warn("missing_hierarchy", path, f"hierarchy category is not declared: {category}")
            elif "source" in entry and entry["source"] not in sources:
                self.add("unknown_source", path + "/source", f"unknown source: {entry['source']}")
        ids = set()
        for index, item in enumerate(data["items"]):
            path = f"/items/{index}"
            if item["id"] in ids:
                self.add("duplicate_id", path + "/id", f"duplicate item ID: {item['id']}")
            ids.add(item["id"])
            for ri, ref in enumerate(item.get("references", [])):
                rp = f"{path}/references/{ri}"
                if ref["source"] not in sources:
                    self.add("unknown_source", rp + "/source", f"unknown source: {ref['source']}")
                if "evidence" not in ref:
                    self.warn("missing_evidence", rp + "/evidence", "reference evidence is not declared")
            requirements = item.get("requirements", {})
            for key in REQUIREMENTS:
                if key not in requirements:
                    self.warn("missing_requirement", path + "/requirements/" + key, f"requirement is not declared: {key}")
            checked = {}
            for ci, check in enumerate(item.get("checks", [])):
                cp = f"{path}/checks/{ci}"
                criterion = check["criterion"]
                if criterion in checked:
                    self.add("duplicate_criterion", cp + "/criterion", f"duplicate check criterion: {criterion}")
                checked[criterion] = check["status"]
                if check["status"] == "fail":
                    self.warn("failed_check", cp + "/status", f"reported check failed: {criterion}")
            for criterion in CRITERIA:
                if criterion == "mobile" or criterion in requirements:
                    if checked.get(criterion, "not_checked") == "not_checked":
                        self.warn("unchecked_check", path + "/checks", f"check is absent or not checked: {criterion}")

    def assets(self, data, base_dir):
        if base_dir is None:
            self.add("asset_base_required", "/asset_root", "base_dir is required when checking assets")
            return
        locators = []
        for key, source in data["sources"].items():
            locators.append((_pointer("/sources", key) + "/locator", source["locator"]))
        for index, item in enumerate(data["items"]):
            for field in ("references", "checks"):
                for ri, record in enumerate(item.get(field, [])):
                    if "evidence" in record:
                        locators.append((f"/items/{index}/{field}/{ri}/evidence", record["evidence"]))
        local = []
        for path, locator in locators:
            if _matches(HTTP, locator):
                self.warn("remote_unchecked", path, "remote evidence was not fetched or verified")
            else:
                local.append((path, locator))
        # Original-only and remote-only drafts need no empty assets directory.
        if not local:
            return
        try:
            base = Path(base_dir).resolve()
            root = (base / data.get("asset_root", "assets")).resolve()
            if not root.is_relative_to(base):
                self.add("asset_escape", "/asset_root", "asset root escapes base_dir")
                return
            if not root.is_dir():
                self.add("asset_missing", "/asset_root", "asset root is not an existing directory")
                return
        except (OSError, RuntimeError, TypeError, ValueError):
            self.add("asset_root", "/asset_root", "asset root cannot be resolved")
            return
        for path, locator in local:
            try:
                target = (base / locator).resolve()
                if not target.is_relative_to(root):
                    self.add("asset_escape", path, "asset path escapes asset_root")
                elif not target.is_file():
                    self.add("asset_missing", path, "asset is not an existing regular file")
            except (OSError, RuntimeError, ValueError):
                self.add("asset_missing", path, "asset cannot be resolved to a regular file")


def inspect_atlas(data: object, *, base_dir=None, check_assets=False) -> list[dict]:
    """Return deterministic error/warning diagnostics with escaped JSON pointers.

    No network access occurs, including with ``check_assets=True``. Semantic and
    filesystem inspection runs only after v2 shape validation succeeds, ensuring
    malformed records never reach operations that assume structurally safe data.
    Legacy atlases retain legacy validation with extra-field warnings only.
    """
    inspection = _Inspection()
    if not isinstance(data, Mapping):
        inspection.add("type", "", "atlas must be an object")
        return inspection.diagnostics
    version = data.get("schema_version", 1)
    if type(version) is not int or version not in (1, 2):
        inspection.add("schema_version", "/schema_version", "schema_version must be integer 1 or 2")
    elif version == 1:
        inspection.legacy(data)
        if check_assets:
            inspection.warn("legacy_assets_unchecked", "", "legacy asset checking is unsupported; assets were not checked")
    else:
        inspection.v2(data)
        if not inspection.diagnostics:
            inspection.semantics(data)
            if check_assets:
                inspection.assets(data, base_dir)
    return inspection.diagnostics


def validate_atlas(data: object) -> list[str]:
    """Return errors only; preserve v1 message text and ordering."""
    return [d["message"] for d in inspect_atlas(data) if d["severity"] == "error"]
