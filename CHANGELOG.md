# Changelog

## Unreleased

### Fixed

- POSIX output permissions: new renders and starters honor the process umask;
  forced replacements retain existing ordinary permission bits without copying
  special mode bits. Staging remains private until atomic publication and retains
  inherited directory setgid for normal group assignment.

## 0.2.0 — 2026-09-06

### Added

- Version 2 atlas format with named sources/targets, explicit borrowing or original
  design, evidence locators, requirements and reported implementation checks.
- JSON Schema and `inspect_atlas` structured diagnostics.
- `--check`, `--strict`, JSON diagnostics and opt-in `--check-assets` without
  fetching remote URLs.
- Packaged `--init` starter with no fabricated sources or passed checks.
- Explicit `--layout sections` and `--layout table`; v2 table output retains full
  detail beneath a compact overview.
- Self-contained synthetic evidence example, workflow guide and golden outputs.
- Wheel resources, source-distribution fixtures and installed-artifact verification.
- Python 3.10/3.12/3.14 CI with read-only repository permissions.

### Safety and compatibility

- Existing destinations now require `--force`. Conversion always rejects source
  aliases; symlink/directory/special destinations are rejected even with `--force`.
- Output publication is atomic; expected failures preserve the source and existing
  destination. These controls do not promise power-loss durability or resistance
  to hostile concurrent replacement of parent directories.
- Author fields are literal text: embedded Markdown and HTML are escaped, and
  multiline table cells do not break document structure.
- Expected JSON, UTF-8, data and I/O failures produce actionable diagnostics.
  Duplicate JSON keys are rejected instead of silently selecting the last value.
- Exit codes are 0 for success, 2 for usage/data errors or strict warnings, and 3
  for I/O failures. Unexpected programming errors remain observable.
- Legacy unversioned and explicit v1 documents remain supported. Default legacy
  Markdown is unchanged; default v2 rendering remains section-based.
- Unsupported legacy fields warn instead of disappearing silently; v2 unknown
  fields are errors. No automatic migration is performed.
- `validate_atlas(data) -> list[str]` is preserved. `render_markdown(data)` remains
  valid; optional layout selection is keyword-only.
- Runtime remains standard-library-only. Test/build dependencies are separate.
- Distribution license metadata uses the MIT SPDX expression. The wheel includes
  starter/schema resources; workflow/skill documents ship in repository and sdist.

Readiness is a completeness signal based on recorded data—not independent
certification of a website, source provenance, permissions or review claims.

## 0.1.0

Initial installable JSON-to-Markdown workflow and subsequent rendered-field
validation fixes.
