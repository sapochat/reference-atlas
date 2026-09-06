from collections.abc import Mapping

from .validation import validate_atlas


REQUIRED_ITEM = ["target", "reference", "borrow", "do_not_copy", "build_implication", "mobile", "attribution"]
REQUIRED_ROOT = ["project", "design_read", "invariants", "hierarchy", "items"]

def _literal_text(value: str) -> str:
    """Encode untrusted inline text without introducing Markdown structure.

    Encode pipes as entities rather than backslash escapes: table parsers split
    rows before parsing inline escapes, especially adjacent backslashes. Generate
    breaks only after escaping input so user-provided HTML is never trusted.
    """
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    replacements = {"&": "&amp;", "<": "&lt;", ">": "&gt;", "|": "&#124;", "\n": "<br>"}
    leading_end = len(value) - len(value.lstrip(" \t"))
    trailing_start = len(value.rstrip(" \t"))
    encoded = []
    for index, char in enumerate(value):
        # Entities preserve boundary whitespace and prevent list/code blocks.
        # Encoding a leading digit also disables ordered-list punctuation.
        if (char in " \t" and (index < leading_end or index >= trailing_start)) or (
            index == 0 and char in "-+0123456789"
        ):
            encoded.append(f"&#{ord(char)};")
        else:
            encoded.append(replacements.get(char, "\\" + char if char in "\\`*_[]#!~" else char))
    return "".join(encoded)


def _render_v2(data: Mapping, *, table: bool = False) -> str:
    """Render a validated v2 document; no user text is active Markdown."""
    lines = [f"# Reference Atlas: {_literal_text(data['project'])}", ""]

    if table:
        lines.extend([
            "## Table overview", "",
            "Compact item overview; all source metadata, requirements, and reported checks "
            "are retained in Full details below.", "",
            "| Item ID | Target | References / original design | Borrow | Do not copy | Build implication | Mobile |",
            "|---|---|---|---|---|---|---|",
        ])
        for item in data["items"]:
            references = item.get("references", [])
            values = [
                item["id"], item["target"],
                item.get("original_design", "\n".join(ref["source"] for ref in references)),
                "\n".join(ref["borrow"] for ref in references),
                "\n".join(ref["do_not_copy"] for ref in references),
                item["build_implication"], item["mobile"],
            ]
            lines.append("| " + " | ".join(_literal_text(value) for value in values) + " |")
        lines.extend(["", "## Full details", ""])

    def field(label: str, value: str) -> None:
        lines.extend([f"**{label}:** {_literal_text(value)}", ""])

    field("Schema version", str(data["schema_version"]))
    field("Asset root", data.get("asset_root", "assets"))
    field("Design read", data["design_read"])
    lines.extend(["## Invariants", ""])
    lines.extend(f"- {_literal_text(value)}" for value in data["invariants"])
    lines.extend(["", "## Source registry", ""])
    if not data["sources"]:
        lines.extend(["No sources (original-only design).", ""])
    for source_id, source in data["sources"].items():
        lines.extend([f"### Source: {_literal_text(source_id)}", ""])
        for key, label in (("title", "Title"), ("locator", "Locator"),
                           ("attribution", "Attribution"), ("url", "URL"),
                           ("rights_notes", "Rights notes")):
            if key in source:
                field(label, source[key])
    lines.extend(["## Reference hierarchy", ""])
    for key, choice in data["hierarchy"].items():
        lines.extend([f"### {_literal_text(key)}", ""])
        if "source" in choice:
            field("Source ID", choice["source"])
        else:
            field("Decision", choice["decision"])
        field("Reason", choice["reason"])
    lines.extend([
        "## Section map", "",
        "Check statuses are reported by the atlas author, not independently verified. "
        "This document does not certify implementation correctness or readiness.", "",
    ])
    for item in data["items"]:
        lines.extend([f"### Item: {_literal_text(item['id'])}", ""])
        for key, label in (("target", "Target"), ("build_implication", "Build implication"),
                           ("mobile", "Mobile")):
            field(label, item[key])
        if "original_design" in item:
            field("Original design", item["original_design"])
        else:
            for reference in item["references"]:
                lines.extend([f"#### Reference: {_literal_text(reference['source'])}", ""])
                for key, label in (("borrow", "Borrow"), ("do_not_copy", "Do not copy"),
                                   ("evidence", "Evidence")):
                    if key in reference:
                        field(label, reference[key])
        if "requirements" in item:
            lines.extend(["#### Requirements", ""])
            for key, label in (("accessibility", "Accessibility"),
                               ("reduced_motion", "Reduced motion"), ("performance", "Performance")):
                if key in item["requirements"]:
                    field(label, item["requirements"][key])
        if "checks" in item:
            lines.extend(["#### Reported checks", ""])
            if not item["checks"]:
                lines.extend(["No checks reported.", ""])
            for check in item["checks"]:
                for key, label in (("criterion", "Criterion"), ("status", "Reported status"),
                                   ("method", "Method"), ("evidence", "Evidence"),
                                   ("note", "Note"), ("reason", "Reason")):
                    if key in check:
                        field(label, check[key])
    return "\n".join(lines).rstrip("\n") + "\n"


def render_markdown(data: object, *, layout: str | None = None) -> str:
    """Render literal Markdown; defaults are legacy table and v2 sections.

    The v2 table is an overview followed by lossless section details.
    """
    if layout is not None and layout not in ("table", "sections"):
        raise ValueError("layout must be 'table' or 'sections'")
    errors = validate_atlas(data)
    if errors:
        raise ValueError("; ".join(errors))
    assert isinstance(data, Mapping)
    if data.get("schema_version") == 2:
        return _render_v2(data, table=layout == "table")
    lines = [
        f"# Reference Atlas: {_literal_text(data['project'])}",
        "",
        f"**Design read:** {_literal_text(data['design_read'])}",
        "",
        "## Invariants",
        "",
    ]
    lines += [f"- {_literal_text(value)}" for value in data["invariants"]]
    lines += ["", "## Reference hierarchy", ""]
    lines += [
        f"- **{_literal_text(key)}:** {_literal_text(value)}"
        for key, value in data["hierarchy"].items()
    ]
    if layout == "sections":
        if "schema_version" in data:
            lines[2:2] = [f"**Schema version:** {_literal_text(str(data['schema_version']))}", ""]
        lines += ["", "## Section map", ""]
        for index, item in enumerate(data["items"], 1):
            lines += [f"### Item {index}: {_literal_text(item['target'])}", ""]
            for key in REQUIRED_ITEM:
                label = key.replace("_", " ").capitalize()
                lines += [f"**{label}:** {_literal_text(item[key])}", ""]
        return "\n".join(lines).rstrip("\n") + "\n"
    lines += [
        "", "## Section map", "",
        "| Target | Reference | Borrow | Do not copy | Build implication | Mobile | Attribution |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in data["items"]:
        values = [_literal_text(item[key]) for key in REQUIRED_ITEM]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n"
