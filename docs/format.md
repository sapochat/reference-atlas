# Atlas format and inspection

Reference Atlas accepts the original unversioned format and an explicit version 2.
It never migrates or rewrites a source document automatically.

## Versions and compatibility

- No `schema_version`, or integer `1`: legacy format. Original field validation
  and Markdown output remain compatible. Unknown root/section fields generate
  inspection warnings because the legacy renderer does not render them.
- Integer `2`: linked sources and explicit evidence/review records, described
  below. Unknown fields are errors rather than silently dropped information.
- Any other version, including strings or booleans, is an error.

The CLI rejects duplicate JSON keys at any nesting level. The Python API cannot
recover duplicate keys already collapsed by another JSON loader.

The structural contract is published in [`atlas-v2.schema.json`](../schemas/atlas-v2.schema.json).
It is useful for editor validation and generating input. Referential integrity,
unique item/check identifiers, exact integer version dispatch, parsed URL checks,
local asset containment and readiness warnings are additional runtime checks;
JSON Schema alone does not certify those. JSON Schema treats numeric `2.0` as an
integer, but the Python/CLI version dispatcher requires the integer `2`, not a
floating-point version value.

## V2 fields

All text is plain text, not trusted Markdown/HTML. Required text must not be blank.

### Document

| Field | Meaning |
|---|---|
| `schema_version` | Integer `2` |
| `project` | Project label |
| `design_read` | Intended visual/behavioral direction |
| `invariants` | At least three non-empty principles; duplicates prompt a warning |
| `sources` | Object keyed by source IDs; may be empty for entirely original work |
| `hierarchy` | Decisions for typography, layout, motion and imagery; omitted categories warn while drafting |
| `items` | Non-empty array of target-section records |
| `asset_root` | Optional local asset directory relative to the atlas file; defaults to `assets` |

IDs use lowercase ASCII slug syntax: letters/digits separated by single hyphens,
starting with a letter. Examples: `hero`, `editorial-study`, `source-2`.

### Sources

Each source requires `title`, `locator` and `attribution`. Optional `url` and
`rights_notes` retain source context. Attribution is a credit, **not proof of
permission to reuse**.

A locator/evidence value is a relative local path or an absolute HTTP(S) URL.
Other URL schemes, absolute filesystem paths and parent traversal are not
supported. URL validation does not establish reachability or trust; no URL is
fetched. Optional `url` is an absolute HTTP(S) URL without embedded credentials.

### Hierarchy

Only `typography`, `layout`, `motion` and `imagery` are supported. Each category
requires a `reason` and exactly one of:

```json
{"source": "editorial-study", "reason": "Borrow its headline scale"}
```

```json
{"decision": "original", "reason": "Use an original layout"}
```

`decision` may also be `not_applicable`, with a reason. Source IDs must resolve.
Missing categories are draft/readiness warnings, not reasons to invent sources.

### Target sections

Every item requires `id`, `target`, `build_implication` and `mobile`. Item IDs must
be unique. Use exactly one of:

- `references`: a non-empty list of `{source, borrow, do_not_copy, evidence?}`.
  Each source must resolve. The optional evidence locator identifies the exact
  inspected artifact. Missing evidence warns; it does not make a draft invalid.
- `original_design`: a non-empty explanation of the original design choice.
  Original sections do not need fabricated source records.

A section can borrow different traits from multiple sources. Keep each borrowing
and non-copy decision attached to its source rather than combining them into a
vague paragraph. The source locator and exact evidence locator may match.

Optional `requirements` supports non-empty `accessibility`, `reduced_motion` and
`performance` text. Missing requirements prompt readiness warnings. `mobile` is
already required on the section.

### Recorded checks

`checks` is an optional array. Each entry requires `criterion` and `status`.
Criteria are `mobile`, `accessibility`, `reduced_motion` and `performance`, with
no duplicate criterion within a section.

| Status | Required supporting context |
|---|---|
| `not_checked` | None; always treated as incomplete |
| `pass` | `method` and `evidence` |
| `fail` | `method` and `evidence`; produces a readiness warning |
| `not_applicable` | `reason` |

Optional `note` preserves context. Optional `method`, `evidence` and `reason`
remain visible when supplied even if the status does not require them.

A check records an assertion by a human or external tool. Reference Atlas does
not execute browser tests or independently certify visual fidelity, accessibility,
performance or rights. Do not mark a check as passed merely because evidence
exists on disk.

## Inspection and CLI

```bash
# Structural validation and readiness diagnostics; no output file is written.
reference-atlas examples/atlas-v2.json --check

# Machine-readable report. A valid draft may still have ready=false.
reference-atlas examples/atlas-v2.json --check --diagnostics json

# Fail on warnings as well as errors.
reference-atlas examples/atlas-v2.json --check --strict

# Explicit local file-existence/containment checks. Never fetch URLs.
reference-atlas examples/atlas-v2.json --check --check-assets

# Render a draft; warnings go to stderr. --strict can refuse incomplete handoffs.
reference-atlas examples/atlas-v2.json /tmp/atlas-v2.md
```

`--check` rejects an output argument and `--force`. `--diagnostics json` requires
`--check`. `--strict` and `--check-assets` also work during rendering. File safety
and overwrite rules in the README still apply.

JSON inspection returns `valid`, `ready` and `diagnostics`. Each diagnostic has a
stable `code`, `severity`, JSON-pointer `path` and `message`. JSON-pointer path is
empty for document-level or file-loading errors; decoding errors cannot always
identify a field path.

- `valid`: no structural/reference/asset errors under the selected checks.
- `ready`: no errors or readiness warnings under the selected checks. **This is
  not a certification of the implementation.** Without `--check-assets`, it does
  not mean local evidence exists. Legacy inspection does not apply the v2
  readiness model; a clean legacy report only means no implemented checks found
  an issue.
- Exit `0`: no errors, and no warnings if strict mode was requested.
- Exit `2`: invalid arguments/input, or warnings in strict mode.
- Exit `3`: file-loading/output I/O failure.

## Initialization and layout

`reference-atlas --init atlas.json` writes the packaged v2 starter. It accepts
`--force` for deliberate replacement, but cannot be combined with positional
inputs, inspection flags or `--layout`. The starter is valid but not ready and
contains no fabricated evidence or passed checks.

Conversion accepts `--layout table` or `--layout sections`. Omitting the option
preserves the existing defaults: a legacy table, or v2 sections. Both explicit
layouts preserve all supported information. V2 table layout retains full detail
below its overview so provenance and checks are not lost. Layout options cannot
be combined with `--check`.

Golden examples: [legacy sections](example-atlas-sections.md),
[v2 table plus details](example-atlas-v2-table.md). See
[the workflow](workflow.md) for the full offline authoring loop.

## Python API

```python
from pathlib import Path
from reference_atlas import inspect_atlas, render_markdown, validate_atlas

errors = validate_atlas(data)  # list[str], structural errors only
issues = inspect_atlas(data, base_dir=Path("examples"), check_assets=True)
markdown = render_markdown(data)  # raises ValueError on invalid input
```

Inspection returns a list of diagnostic dictionaries. Library rendering does not
print warnings, perform asset checks or mutate its input. Call inspection when
you need readiness warnings or explicit local checks.

## Local evidence boundary

Asset paths are relative to the input document's directory, not the shell's
working directory. `asset_root` must stay within that directory. Local source
locators and evidence must resolve to regular files inside the asset root;
traversal and symlink escapes are rejected. `base_dir` is required when using the
Python inspection API with `check_assets=True`.

Remote HTTP(S) evidence is left unchecked and reported as such when asset checks
are requested. No assets are read as instructions, copied, embedded or uploaded
by inspection. File existence does not prove visual content or test results.

## Example and manual migration

[`examples/atlas-v2.json`](../examples/atlas-v2.json) and its
[rendered handoff](example-atlas-v2.md) are deliberately a **draft**.
Its included SVG is a synthetic reference diagram, not a browser screenshot or
implementation verification. It demonstrates a borrowed section and an original
section; all implementation checks remain `not_checked`.

To migrate a legacy document manually:

1. Keep the original JSON as a backup; create a separate v2 document.
2. Inventory real sources, assign IDs and retain credits/rights notes.
3. Explicitly connect each hierarchy choice and borrowing record to its source.
4. Mark genuinely original decisions as original; do not infer that an old
   “Reference A” label and a screenshot filename describe the same source.
5. Carry across build/mobile requirements; add real evidence locators where known.
6. Leave unperformed checks `not_checked`. Inspect, resolve meaningful warnings
   and review the rendered handoff before implementation.
