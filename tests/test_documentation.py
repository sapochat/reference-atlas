"""Documentation and source-distribution resources must stay self-contained."""
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class DocumentationTests(unittest.TestCase):
    def test_workflow_release_notes_and_skill_ship_together(self):
        for name in ("README.md", "CHANGELOG.md", "SKILL.md", "ATTRIBUTION.md", "docs/workflow.md"):
            with self.subTest(name=name):
                self.assertTrue((ROOT / name).is_file(), f"missing documentation: {name}")

    def test_local_document_links_resolve(self):
        documents = [ROOT / name for name in ("README.md", "CHANGELOG.md", "SKILL.md", "ATTRIBUTION.md")]
        documents.extend((ROOT / "docs").glob("*.md"))
        for document in documents:
            self.assertTrue(document.is_file(), str(document))
            for target in re.findall(r"!?\[[^\]\n]*\]\(([^)\s]+)\)", document.read_text(encoding="utf-8")):
                url = urlsplit(target)
                if url.scheme or url.netloc or not url.path:
                    continue
                with self.subTest(document=document.name, target=target):
                    resolved = (document.parent / unquote(url.path)).resolve()
                    self.assertTrue(resolved.is_relative_to(ROOT), "documentation escapes project")
                    self.assertTrue(resolved.is_file(), f"broken local link: {target}")

    def test_skill_frontmatter_and_scope(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        frontmatter, body = text[4:].split("\n---\n", 1)
        self.assertIn("name: reference-atlas", frontmatter)
        description = next(line for line in frontmatter.splitlines() if line.startswith("description: "))
        self.assertLessEqual(len(description.removeprefix("description: ")), 1024)
        self.assertTrue(body.strip())
        self.assertIn("not independent verification", body)


if __name__ == "__main__":
    unittest.main()
