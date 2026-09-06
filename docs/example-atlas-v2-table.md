# Reference Atlas: Reference handoff page — synthetic draft

## Table overview

Compact item overview; all source metadata, requirements, and reported checks are retained in Full details below.

| Item ID | Target | References / original design | Borrow | Do not copy | Build implication | Mobile |
|---|---|---|---|---|---|---|
| hero | Introduction | atlas-diagram | Warm accent, graphite background and clear label hierarchy | Exact diagram composition or the source's labels | Use semantic headings and a bounded text column | Keep the reading order linear without horizontal scrolling |
| footer | Attribution footer | A plain text footer credits sources without borrowing a reference composition |  |  | Place source credits after the main content | Allow credit text to wrap naturally |

## Full details

**Schema version:** &#50;

**Asset root:** assets

**Design read:** Dark, clear and diagram-led; distinguish decisions from verification

## Invariants

- Readable sans-serif labels
- Warm accent on a graphite background
- No motion needed to understand the content

## Source registry

### Source: atlas-diagram

**Title:** Synthetic Reference Atlas diagram

**Locator:** assets/reference-atlas-example.svg

**Attribution:** Original synthetic diagram from this repository

**Rights notes:** Repository-owned example asset; not a screenshot of a third-party site or evidence of a tested implementation

## Reference hierarchy

### typography

**Source ID:** atlas-diagram

**Reason:** Borrow the distinction between large labels and supporting notes

### layout

**Decision:** original

**Reason:** Use a linear reading order rather than the diagram's two-column map

### motion

**Decision:** original

**Reason:** Keep the page static

### imagery

**Decision:** not\_applicable

**Reason:** The proposed page needs no photography

## Section map

Check statuses are reported by the atlas author, not independently verified. This document does not certify implementation correctness or readiness.

### Item: hero

**Target:** Introduction

**Build implication:** Use semantic headings and a bounded text column

**Mobile:** Keep the reading order linear without horizontal scrolling

#### Reference: atlas-diagram

**Borrow:** Warm accent, graphite background and clear label hierarchy

**Do not copy:** Exact diagram composition or the source's labels

**Evidence:** assets/reference-atlas-example.svg

#### Requirements

**Accessibility:** Measure text contrast and verify heading order

**Reduced motion:** Do not introduce entrance animation

**Performance:** Avoid loading decorative media above the fold

#### Reported checks

**Criterion:** mobile

**Reported status:** not\_checked

**Note:** No implementation has been built

**Criterion:** accessibility

**Reported status:** not\_checked

**Criterion:** reduced\_motion

**Reported status:** not\_checked

**Criterion:** performance

**Reported status:** not\_checked

### Item: footer

**Target:** Attribution footer

**Build implication:** Place source credits after the main content

**Mobile:** Allow credit text to wrap naturally

**Original design:** A plain text footer credits sources without borrowing a reference composition

#### Requirements

**Accessibility:** Keep attribution readable at normal text size

**Reduced motion:** Use static text

**Performance:** No additional assets required

#### Reported checks

**Criterion:** mobile

**Reported status:** not\_checked

**Criterion:** accessibility

**Reported status:** not\_checked

**Criterion:** reduced\_motion

**Reported status:** not\_checked

**Criterion:** performance

**Reported status:** not\_checked
