import argparse,json
from pathlib import Path
from .atlas import render_markdown

def main():
    p=argparse.ArgumentParser(); p.add_argument("atlas"); p.add_argument("output"); a=p.parse_args()
    Path(a.output).write_text(render_markdown(json.loads(Path(a.atlas).read_text()))); print(a.output); return 0
if __name__ == "__main__": raise SystemExit(main())
