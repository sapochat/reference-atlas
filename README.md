# Reference Atlas

A section-level method for building ambitious websites from multiple visual references without cloning any one source.

The key artifact is an atlas that maps each target section to a source, the exact trait to borrow, what must not be copied, mobile relevance, and implementation implications. It turns “make it cinematic” into inspectable design evidence.

This workflow was adapted from a portfolio-building walkthrough by [@monokern](https://x.com/monokern/status/2071246711222055363), then extended with reference hierarchy, attribution, mobile behavior, accessibility, performance, and browser-verification gates. No source code from that walkthrough is included.

## Install and run

```bash
python3 -m venv .venv
.venv/bin/pip install -e .

.venv/bin/reference-atlas examples/atlas.json /tmp/atlas.md
.venv/bin/python -m unittest discover -s tests -v
```

MIT licensed.
