#!/usr/bin/env python3
"""
Build index.html from src/index.template.html + data/partners.json.

The template is a complete, standalone HTML document with one placeholder,
__PDATA__, sitting inside <script type="application/json" id="pdata">.
Building simply substitutes the dataset into that placeholder, so the
result is a single file with no network dependencies apart from the
Google Fonts stylesheet.

    python build.py                 # -> index.html
    python build.py --out docs/index.html
    python build.py --data data/partners.json

Exit code is non-zero if the template or the data is missing or malformed,
so this is safe to run in CI.
"""

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
PLACEHOLDER = "__PDATA__"


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the Partnership Desk page.")
    ap.add_argument("--template", default=ROOT / "src" / "index.template.html", type=pathlib.Path)
    ap.add_argument("--data", default=ROOT / "data" / "partners.json", type=pathlib.Path)
    ap.add_argument("--out", default=ROOT / "index.html", type=pathlib.Path)
    ap.add_argument("--pretty", action="store_true", help="do not minify the embedded JSON")
    args = ap.parse_args()

    if not args.template.exists():
        print(f"error: template not found: {args.template}", file=sys.stderr)
        return 1
    if not args.data.exists():
        print(f"error: data not found: {args.data}", file=sys.stderr)
        return 1

    template = args.template.read_text(encoding="utf-8")
    if PLACEHOLDER not in template:
        print(f"error: {PLACEHOLDER} placeholder missing from the template", file=sys.stderr)
        return 1

    try:
        data = json.loads(args.data.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"error: {args.data} is not valid JSON: {exc}", file=sys.stderr)
        return 1

    for key in ("labels", "rows"):
        if key not in data:
            print(f"error: {args.data} has no '{key}' key", file=sys.stderr)
            return 1

    blob = json.dumps(
        data,
        ensure_ascii=False,
        indent=2 if args.pretty else None,
        separators=None if args.pretty else (",", ":"),
    )
    # A literal </script> inside the JSON would close the tag early.
    blob = blob.replace("</", "<\\/")

    html = template.replace(PLACEHOLDER, blob)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")

    print(
        f"built {args.out}  "
        f"({len(html) / 1024:.0f} KB · {len(data['rows'])} project rows · "
        f"{len(data['labels'])} months · {len(data.get('disc', []))} placements)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
