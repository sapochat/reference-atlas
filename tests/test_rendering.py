"""Parse Markdown with raw HTML enabled so unsafe output cannot hide."""
import json
import unittest
from html.parser import HTMLParser
from pathlib import Path

from markdown_it import MarkdownIt

from reference_atlas.atlas import REQUIRED_ITEM, render_markdown, validate_atlas


class RenderedDocument(HTMLParser):
    def __init__(self, markdown):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.stack = []
        self.feed(MarkdownIt("commonmark").enable("table").enable("strikethrough").render(markdown))

    def handle_starttag(self, tag, attrs):
        element = {"tag": tag, "attrs": attrs, "text": ""}
        self.elements.append(element)
        if tag == "br":
            self.handle_data("\n")
        elif tag not in {"img", "hr", "input", "meta", "link"}:
            self.stack.append(element)

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1]["tag"] == tag:
            self.stack.pop()

    def handle_data(self, data):
        for element in self.stack:
            element["text"] += data

    def texts(self, tag):
        return [e["text"] for e in self.elements if e["tag"] == tag]


class RenderingTests(unittest.TestCase):
    @staticmethod
    def atlas(value="plain"):
        return {
            "project": value,
            "design_read": value,
            "invariants": [value, "second", "third"],
            "hierarchy": {value: value},
            "items": [{key: value for key in REQUIRED_ITEM}],
        }

    def assert_literal_document(self, value):
        data = self.atlas(value)
        self.assertEqual(validate_atlas(data), [])
        markdown = render_markdown(data)
        document = RenderedDocument(markdown)
        expected = value.replace("\r\n", "\n").replace("\r", "\n")
        self.assertEqual(document.texts("h1"), ["Reference Atlas: " + expected])
        self.assertEqual(document.texts("p"), ["Design read: " + expected])
        self.assertEqual(document.texts("li"), [expected, "second", "third", expected + ": " + expected])
        self.assertEqual(document.texts("td"), [expected] * 7)
        self.assertEqual(document.texts("strong"), ["Design read:", expected + ":"])
        self.assertEqual(document.texts("h2"), ["Invariants", "Reference hierarchy", "Section map"])
        self.assertEqual(len(document.texts("table")), 1)
        self.assertEqual(len(document.texts("tr")), 2)
        self.assertEqual(len(document.texts("th")), 7)
        allowed = {"h1", "h2", "p", "strong", "ul", "li", "table", "thead", "tbody", "tr", "th", "td", "br"}
        for element in document.elements:
            self.assertIn(element["tag"], allowed)
            self.assertEqual(element["attrs"], [])
        return markdown

    def test_user_markup_is_literal_in_every_context(self):
        for value in (
            "Unicode café 日本語 🧭",
            r"back\slash \\ pair | pipe \| and \\|",
            "[link](https://example.com) ![image](https://example.com/x.png)",
            '<img src=x onerror="alert(1)"><script>alert(1)</script>',
            "<https://example.com> <person@example.com> &copy; &#124; & < >",
            "**bold** _italic_ ~~strike~~ `code` ``ticks`` [brackets] ###",
        ):
            with self.subTest(value=value):
                self.assert_literal_document(value)

    def test_block_markers_at_start_remain_literal_list_text(self):
        for value in ("- nested", "+ nested", "1. nested", "1) nested", "---", "    indented", " leading and trailing "):
            with self.subTest(value=value):
                self.assert_literal_document(value)

    def test_newlines_are_deliberate_breaks_not_new_blocks_or_rows(self):
        value = "first\r\n# injected heading\r- injected list\n\n| fake | row |\n```code\n<img src=x>"
        markdown = self.assert_literal_document(value)
        self.assertNotIn("\r", markdown)
        self.assertEqual(len(markdown.splitlines()), len(render_markdown(self.atlas()).splitlines()))

    def test_backslashes_next_to_pipes_preserve_seven_columns(self):
        for count in range(6):
            value = "left" + "\\" * count + "|right\\"
            with self.subTest(backslashes=count):
                self.assert_literal_document(value)

    def test_existing_example_is_byte_for_byte_unchanged(self):
        root = Path(__file__).parents[1]
        data = json.loads((root / "examples/atlas.json").read_text(encoding="utf-8"))
        self.assertEqual(render_markdown(data).encode("utf-8"), (root / "docs/example-atlas.md").read_bytes())


if __name__ == "__main__":
    unittest.main()
