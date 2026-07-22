# Reference Atlas

A section-level method for building ambitious websites from multiple visual references without cloning any one source.

The key artifact is an atlas that maps each target section to a source, the exact trait to borrow, what must not be copied, mobile relevance, and implementation implications. It turns “make it cinematic” into inspectable design evidence.

This workflow was adapted from a portfolio-building walkthrough by [@monokern](https://x.com/monokern/status/2071246711222055363), then extended with reference hierarchy, attribution, mobile behavior, accessibility, performance, and browser-verification gates. No source code from that walkthrough is included.

![Synthetic Reference Atlas showing section-level borrowing rules and reference hierarchy](docs/reference-atlas-example.svg)

The visual above is synthetic. The committed [rendered Markdown atlas](docs/example-atlas.md) comes from the same example JSON used by the CLI tests.

## Install and run

```bash
python3 -m venv .venv
.venv/bin/pip install -e .

.venv/bin/reference-atlas examples/atlas.json /tmp/atlas.md
.venv/bin/python -m unittest discover -s tests -v
```

MIT licensed.
