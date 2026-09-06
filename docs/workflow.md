# From references to a reviewable handoff

Reference Atlas is a local authoring and inspection tool. It does not collect
screenshots, generate a website or independently verify design quality.

## 1. Initialize a draft

After installing the project, work in a directory of your choice:

```sh
reference-atlas --init atlas.json
reference-atlas atlas.json --check --diagnostics json
```

Initialization uses a template included in the wheel, so it works outside the
checkout without a network connection. It creates only the requested JSON file;
its parent directory must already exist. Existing files require `--force`, and
symlinks, directories and special destinations are rejected even with that flag.

The starter is structurally valid but deliberately not ready. Replace its `TBD`
text with actual decisions. It begins as original work with no sources rather
than fabricating evidence. All implementation checks start as `not_checked`.

`--init` cannot be combined with conversion inputs, inspection flags or layout
selection. The legacy positional interface is unchanged; `init` is not a reserved
subcommand or filename.

## 2. Collect and attribute evidence

Capture references yourself, respecting their terms and usage rights. Save local
evidence under a directory beside your atlas, conventionally `assets/`. Add each
source to the v2 `sources` registry with a stable ID, title, locator and attribution.
Use `rights_notes` for unresolved permission questions; attribution is not a license.

Paths are relative to the **atlas directory**, not to the assets directory. With
`"asset_root": "assets"`, use `"locator": "assets/hero.png"`, not `"hero.png"`.
Reference Atlas never fetches remote URLs, captures browser screenshots or copies
referenced files into a deliverable.

See [the synthetic example](../examples/atlas-v2.json), which includes its actual
[synthetic SVG evidence](../examples/assets/reference-atlas-example.svg). It is
not a screenshot of a verified implementation.

## 3. Map decisions, not vague inspiration

For each target section, choose exactly one:

- `references`: identify the source, the exact trait to borrow and what must not
  be copied. Multiple sources are supported.
- `original_design`: explain the original decision without inventing a source.

Record build implications, mobile behavior and accessibility, reduced-motion and
performance requirements. State which reference or original decision controls
layout, typography, imagery and motion. Resolve contradictions yourself; the tool
can validate source IDs but cannot decide whether the result is coherent.

## 4. Check and repair

```sh
reference-atlas atlas.json --check
reference-atlas atlas.json --check --check-assets --diagnostics json
```

Normal checking exits 0 for a structurally valid draft, even with readiness
warnings. JSON diagnostics distinguish `valid` from `ready`; individual issues
include a code, severity, JSON-pointer path and message.

For a small repair exercise, temporarily change an item's `id` to `"Bad ID"`.
Checking exits 2 and identifies the invalid field. Restore a lowercase ID such as
`"hero"` and check again. This exercises an actual error without manufacturing
passed implementation checks or changing source evidence.

`--check-assets` verifies existing local regular files within the declared asset
root, including resolved symlink containment. It does not inspect their contents
or certify fidelity. Original-only documents need no empty assets directory;
remote evidence is reported as unchecked. No network requests are made.

## 5. Render and review

```sh
reference-atlas atlas.json handoff.md --layout sections
reference-atlas atlas.json overview.md --layout table
```

The default remains table layout for legacy atlases and sections for v2. Explicit
`sections` works with both formats. V2 `table` adds a compact overview while
retaining full evidence and decision details; it is not a lossy export.

All author-supplied values are literal text, not embedded Markdown or HTML.
Line breaks are preserved deliberately without breaking table columns. Use
`--force` only to intentionally replace an existing, different regular output
file. It never permits replacing the source or an alias of it.

Review the rendered handoff with a person. Check originality, conflicting
references, evidence usefulness, mobile behavior and actual requirements—not just
whether the validator accepts the JSON.

## 6. Implement and record checks

Build the website separately. Perform real browser, keyboard, reduced-motion and
performance checks using suitable tools. Then record each criterion's result:

- `pass` or `fail`: include a method and evidence locator.
- `not_applicable`: explain why the criterion does not apply.
- `not_checked`: leave it explicit until work is actually checked.

A result stored in JSON is an author's claim. The CLI does not run the browser,
interpret a screenshot or verify that a claimed pass is true. Do not mark a check
passed merely to silence a warning.

```sh
reference-atlas atlas.json --check --strict --check-assets
```

Strict mode turns warnings into exit 2. It is a completeness gate, not a design,
accessibility, performance or legal certification. Non-empty but poor prose can
still pass structural checks; human review remains necessary. Legacy documents
have no equivalent v2 evidence model—clean legacy diagnostics do not establish
v2 handoff readiness.

## Compatibility and distribution

Unversioned atlases and explicit version 1 remain supported. No migration is
performed automatically. The v2 format rejects unknown fields; legacy extras
produce warnings so ignored requirements do not disappear silently.

The wheel includes the starter and JSON Schema under `reference_atlas.resources`.
The full workflow, `SKILL.md`, examples and test fixtures ship in the repository
and source distribution; they are not installed as a Hermes skill by the wheel.

See [format details](format.md), [release notes](../CHANGELOG.md), and the
[README](../README.md) for installation and verification commands.
