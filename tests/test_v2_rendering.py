"""V2 rendering is literal even with a raw-HTML-enabled Markdown parser."""
import copy
import unittest
from html.parser import HTMLParser

from markdown_it import MarkdownIt

from reference_atlas.atlas import render_markdown


def atlas():
    return {
        "schema_version": 2,
        "project": "Project value",
        "design_read": "Design read value",
        "invariants": ["Invariant one", "Invariant two", "Invariant three"],
        "sources": {"source-one": {
            "title": "Source title", "locator": "Source locator", "attribution": "Source credit",
            "url": "https://example.com/source", "rights_notes": "Rights value",
        }},
        "hierarchy": {
            "typography": {"source": "source-one", "reason": "Type reason"},
            "layout": {"decision": "original", "reason": "Layout reason"},
            "motion": {"decision": "not_applicable", "reason": "Motion reason"},
            "imagery": {"source": "source-one", "reason": "Image reason"},
        },
        "items": [{
            "id": "item-one", "target": "Hero target", "build_implication": "Build value",
            "mobile": "Mobile value", "references": [{
                "source": "source-one", "borrow": "Borrow value", "do_not_copy": "Avoid value",
                "evidence": "Evidence value",
            }],
            "requirements": {"accessibility": "Accessibility value", "reduced_motion": "Reduced motion value", "performance": "Performance value"},
            "checks": [{"criterion": criterion, "status": status,
                        "method": "Method " + status, "evidence": "Evidence " + status,
                        "note": "Note " + status, "reason": "Reason " + status}
                       for criterion, status in zip(("mobile", "accessibility", "reduced_motion", "performance"),
                                                    ("not_checked", "pass", "fail", "not_applicable"))],
        }, {
            "id": "item-two", "target": "Footer target", "build_implication": "Footer build",
            "mobile": "Footer mobile", "original_design": "Original design value",
        }],
    }


class Document(HTMLParser):
    def __init__(self, markdown):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.text = ""
        self.feed(MarkdownIt("commonmark", {"html": True}).enable("table").enable("strikethrough").render(markdown))

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, attrs))
        if tag == "br":
            self.text += "\n"

    def handle_data(self, data):
        self.text += data


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from strings(child)


class V2RenderingTests(unittest.TestCase):
    def test_v2_renders_every_accepted_field(self):
        data = atlas()
        data["asset_root"] = "local-assets"
        try:
            output = render_markdown(data)
        except ValueError as exc:
            self.fail(f"A valid v2 atlas must render: {exc}")
        doc = Document(output)
        for value in strings(data):
            self.assertIn(value, doc.text)
        for value in ("source-one", "typography", "layout", "motion", "imagery", "Schema version: 2", "Asset root: local-assets"):
            self.assertIn(value, doc.text)
        self.assertNotIn("table", [tag for tag, _ in doc.tags])
        self.assertIn("reported", doc.text.lower())
        self.assertIn("not independently verified", doc.text.lower())
        self.assertIn("does not certify", doc.text.lower())

    def test_original_only_atlas_displays_default_asset_root(self):
        data = atlas()
        data["sources"] = {}
        data["items"] = data["items"][1:]
        for entry in data["hierarchy"].values():
            entry.pop("source", None)
            entry["decision"] = "original"
        doc = Document(render_markdown(data))
        self.assertIn("Asset root: assets", doc.text)
        self.assertIn("No sources", doc.text)
        self.assertIn("Original design value", doc.text)

    def test_invalid_v2_is_rejected_before_rendering(self):
        for mutate in (
            lambda d: d.update(schema_version=True),
            lambda d: d.update(schema_version=3),
            lambda d: d["items"][0]["references"][0].update(source="missing"),
            lambda d: d["items"][0]["checks"][0].update(status="verified"),
            lambda d: d["items"][0].update(original_design="ambiguous"),
        ):
            data = atlas()
            mutate(data)
            with self.subTest(data=data), self.assertRaises(ValueError):
                render_markdown(data)

    def test_public_validation_exports_are_shared(self):
        import reference_atlas
        from reference_atlas import atlas as module
        from reference_atlas import validation
        self.assertIs(reference_atlas.validate_atlas, validation.validate_atlas)
        self.assertIs(module.validate_atlas, validation.validate_atlas)
        self.assertIs(reference_atlas.inspect_atlas, validation.inspect_atlas)

    def test_source_ids_are_literal_in_registry_hierarchy_and_references(self):
        data = atlas()
        source_id = "exact-source-id"
        data["sources"][source_id] = data["sources"].pop("source-one")
        for choice in data["hierarchy"].values():
            if "source" in choice:
                choice["source"] = source_id
        data["items"][0]["references"][0]["source"] = source_id
        doc = Document(render_markdown(data))
        self.assertEqual(doc.text.count(source_id), 4)
        self.assertFalse({"a", "img", "script"}.intersection(tag for tag, _ in doc.tags))

    def test_locator_markup_is_literal_for_schema_valid_paths_and_urls(self):
        paths = [("asset_root",), ("sources", "source-one", "locator"),
                 ("sources", "source-one", "url"),
                 ("items", 0, "references", 0, "evidence"),
                 ("items", 0, "checks", 0, "evidence")]
        for path in paths:
            payload = '<img src=x onerror=alert(1)>[link](relative)![image](relative)&copy;'
            if path[-1] == "url":
                payload = 'https://example.com/<img>[link](relative)![image](relative)&copy;'
            data = atlas()
            target = data
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = payload
            with self.subTest(path=path):
                doc = Document(render_markdown(data))
                self.assertIn(payload, doc.text)
                self.assertFalse({"a", "img", "script"}.intersection(tag for tag, _ in doc.tags))

    def test_untrusted_text_is_literal_in_all_v2_contexts(self):
        payloads = (
            '<img src=x onerror="alert(1)"><script>alert(1)</script>',
            '[link](https://example.com) ![image](https://example.com/x.png)',
            '<https://example.com> <person@example.com> &copy; &#124;',
            '**bold** _italic_ ~~strike~~ `code` \\| [x] # heading',
            'first\r\n# heading\r- list\n\n| fake | row |\n```code\n<img src=x>',
            '    leading and trailing 日本語 🧭 ',
        )
        base = atlas()
        paths = [("project",), ("design_read",), ("invariants", 0)]
        paths += [("sources", "source-one", field) for field in ("title", "attribution", "rights_notes")]
        paths += [("hierarchy", key, "reason") for key in base["hierarchy"]]
        paths += [("items", i, field) for i, item in enumerate(base["items"]) for field in ("target", "build_implication", "mobile")]
        paths += [("items", 1, "original_design")]
        paths += [("items", 0, "references", 0, field) for field in ("borrow", "do_not_copy")]
        paths += [("items", 0, "requirements", field) for field in base["items"][0]["requirements"]]
        paths += [("items", 0, "checks", 0, field) for field in ("method", "note", "reason")]
        for path in paths:
            for payload in payloads:
                with self.subTest(path=path, payload=payload):
                    data = copy.deepcopy(base)
                    target = data
                    for key in path[:-1]:
                        target = target[key]
                    target[path[-1]] = payload
                    doc = Document(render_markdown(data))
                    self.assertIn(payload.replace("\r\n", "\n").replace("\r", "\n"), doc.text)
                    for tag, attrs in doc.tags:
                        self.assertIn(tag, {"h1", "h2", "h3", "h4", "p", "strong", "ul", "li", "br"})
                        self.assertEqual(attrs, [])


if __name__ == "__main__":
    unittest.main()
