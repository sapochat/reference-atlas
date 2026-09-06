---
name: reference-atlas
description: Use when building a site from multiple visual references. Map section-level borrowing and original decisions, resolve conflicts, then record real implementation checks.
version: 1.1.0
author: Santi Pochat and Janus, adapted from @monokern
license: MIT
metadata:
  hermes:
    tags: [frontend, references, design, workflow, qa]
    related_skills: []
---

# Reference Atlas

## Overview

Turn visual references into an attributed, section-level handoff rather than
cloning one site. The CLI validates and renders decisions; human judgment and
separate browser tools establish design quality and implementation results.

## When to use

Use for reference-driven website planning, implementation handoff and recorded
review. Do not use its validation result as proof of visual fidelity, originality,
accessibility, performance or permission to reuse an asset.

## Workflow

1. Inspect the existing project before designing. Establish the target sections,
   constraints and distinct visual invariants.
2. Run `reference-atlas --init atlas.json` if starting fresh. Replace `TBD` prose
   with real decisions; do not replace an existing atlas without permission.
3. Collect evidence yourself. Record sources with stable IDs, locators and
   attribution. Paths such as `assets/hero.png` are relative to the atlas directory.
   Do not invent screenshots or imply that attribution grants reuse rights.
4. For each target, record exactly one of explicit `references` or an
   `original_design` rationale. Borrowing records explain both what to borrow and
   what not to copy. Record build implications and mobile/accessibility,
   reduced-motion and performance requirements.
5. State which source or original choice controls typography, layout, motion and
   imagery. Resolve conflicting references rather than combining them blindly.
6. Run `reference-atlas atlas.json --check --check-assets --diagnostics json`.
   Fix errors and review warnings. Local asset checks are opt-in; remote URLs are
   never fetched. A valid draft is not automatically ready.
7. Render with `reference-atlas atlas.json handoff.md --layout sections`.
   Table layout is also available; v2 retains full detail after its overview.
   Review the handoff before implementing.
8. Build a complete first pass before polishing. Collect concrete defects and
   batch related repairs. Inspect typography, color, hierarchy, motion, mobile,
   copy, performance, accessibility and reference fidelity.
9. Use separate browser/testing tools to verify real routes at desktop, tablet
   and mobile widths. Check console/network failures, overflow, keyboard/touch
   behavior and reduced motion. Record actual check results with methods and
   evidence; keep untested work `not_checked`.
10. Run `reference-atlas atlas.json --check --strict --check-assets` as a
    completeness gate. Never mark checks passed merely to make this command green.

## Pitfalls

- Non-empty prose is not necessarily a useful decision; review it yourself.
- `pass` is a recorded assertion, not independent verification by this tool.
- Do not fabricate source relationships while migrating a legacy atlas.
- User fields are literal text; embedded Markdown/HTML is escaped deliberately.
- `--force` permits intentional destination replacement, never source overwrite.
- The wheel includes the starter/schema, but does not install this skill into an
  agent. Keep the repository or source distribution for this workflow and its docs.

## Verification checklist

- Every borrowed trait resolves to an attributed source; original work is labeled.
- No accepted requirements disappeared from the rendered handoff.
- Mobile, accessibility, reduced-motion and performance decisions were reviewed.
- Reported checks have actual evidence or justified non-applicability.
- Remaining warnings and external verification limits are stated honestly.

See [the workflow](docs/workflow.md) and [format contract](docs/format.md).
