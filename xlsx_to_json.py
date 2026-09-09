#!/usr/bin/env python3
"""
Rebuild data/partners.json from the "Partners List" workbook.

    pip install openpyxl
    python scripts/xlsx_to_json.py "Partners List.xlsx" -o data/partners.json
    python build.py

WHAT IT READS
-------------
Three roster sheets, one row per project:

    Active Partners      Low Activity      No Activity

and two monthly-bets sheets, whose header row carries the month columns:

    Source               Source 2

plus two deal sheets:

    Network Promotion offer      (promotion status per partner/project)
    Promotional Discounts        (game discounts and lobby positions)

Roster sheets are matched to bets by (partner, project) with a normalised
key: lowercased, trimmed, inner whitespace collapsed. Rows that do not
match anything in Source / Source 2 have no bets at all and are carried
through with an all-zero month vector, which is what the "never taken a
bet" column on the dashboard counts.

WHAT IT WRITES
--------------
    {
      "labels": ["2026-01", ... ],           # month columns, oldest first
      "rows":   [ {p, pl, j, b, o, c, m[], tb, tp, pk, mw, ja, amt, ggr, src} ],
      "disc":   [ {p, j, s, e, d, g, pos} ], # promotional discounts
      "issues": [ "...html..." ]             # data-quality notes for the Data model tab
    }

    p    partner            (roster sheet, "Partner")
    pl   platform           (roster sheet, "Platform" — often blank or "One communication")
    j    project            (roster sheet, "Project")
    b    which sheet it came from: active | low | none
    o    promotion status   (Network Promotion offer)
    c    comments / notes
    m[]  bets per month, aligned to labels; null means the column is absent
         from that row's source sheet (Source 2 has no June column)
    tb   total bets      tp total players     pk peak month bets
    mw   months with any bets                 ja bets in the latest month
    amt  turnover                             ggr GGR
    src  1 = Source, 2 = Source 2, 0 = no bets row found

Header matching is by name, not by position, so inserted columns are
tolerated. If the workbook is restructured, adjust HEADERS below.
"""

import argparse
import json
import pathlib
import re
import sys
import unicodedata

try:
    from openpyxl import load_workbook
except ImportError:  # pragma: no cover
    sys.exit("openpyxl is required:  pip install openpyxl")

ROSTERS = {"Active Partners": "active", "Low Activity": "low", "No Activity": "none"}
BET_SHEETS = {"Source": 1, "Source 2": 2}
OFFER_SHEET = "Network Promotion offer"
DISCOUNT_SHEET = "Promotional Discounts"

# Accepted spellings for each field we need. First match on the header row wins.
HEADERS = {
    "partner": ["partner", "partner name", "partners"],
    "platform": ["platform", "platform name"],
    "project": ["project", "project name", "brand"],
    "manager": ["partner manager", "manager", "account manager"],
    "players": ["players", "total players", "player count"],
    "comment": ["comment", "comments", "note", "notes"],
    "status": ["status", "offer status", "promotion status", "network promotion"],
    "turnover": ["turnover", "amount", "bet amount", "total amount"],
    "ggr": ["ggr", "gross gaming revenue"],
    "bets": ["bets", "total bets", "bet count"],
    "game": ["game", "game name"],
    "position": ["position", "lobby position", "pos"],
    "discount": ["discount", "discount %", "rate"],
    "start": ["start", "start date", "from"],
    "end": ["end", "end date", "to"],
}

MONTH_RE = re.compile(r"^(20\d\d)[-/. ]?(0[1-9]|1[0-2])$")
MONTH_NAMES = {
    m: i + 1
    for i, m in enumerate(
        "january february march april may june july august september october november december".split()
    )
}


def norm(v) -> str:
    """Normalise a cell for use as a matching key."""
    if v is None:
        return ""
    s = unicodedata.normalize("NFKC", str(v)).strip()
    return re.sub(r"\s+", " ", s)


def key(*parts) -> str:
    return " | ".join(norm(p).lower() for p in parts)


def month_label(v):
    """Turn a header cell into 'YYYY-MM', or None if it is not a month."""
    if v is None:
        return None
    if hasattr(v, "year") and hasattr(v, "month"):
        return f"{v.year:04d}-{v.month:02d}"
    s = norm(v).lower()
    m = MONTH_RE.match(s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.match(r"^([a-z]+)[\s'\-]*(\d{2,4})$", s)  # "June 2026", "Jun-26"
    if m:
        name = next((k for k in MONTH_NAMES if k.startswith(m.group(1)[:3])), None)
        if name:
            year = int(m.group(2))
            year += 2000 if year < 100 else 0
            return f"{year:04d}-{MONTH_NAMES[name]:02d}"
    return None


def num(v) -> float:
    if v is None or v == "":
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d.\-]", "", str(v).replace(",", ""))
    try:
        return float(s)
    except ValueError:
        return 0.0


def date_str(v) -> str:
    if v is None:
        return ""
    if hasattr(v, "strftime"):
        return v.strftime("%d.%m.%Y")
    return norm(v)


def header_map(row) -> dict:
    """{field: column index} for one header row."""
    found, seen = {}, [norm(c).lower() for c in row]
    for field, names in HEADERS.items():
        for name in names:
            if name in seen:
                found[field] = seen.index(name)
                break
    return found


def find_header(ws, needed=("partner",), scan=8):
    """Locate the header row — some sheets carry a title line above it."""
    for r, row in enumerate(ws.iter_rows(min_row=1, max_row=scan, values_only=True), start=1):
        hm = header_map(row)
        if all(f in hm for f in needed):
            return r, hm, row
    return None, {}, ()


# --------------------------------------------------------------------------
# Overrides. Keep these in step with the dashboard's own UNIT_RULES.
# --------------------------------------------------------------------------

# Rows held as active by hand despite having no bets row.
ASSUME_ACTIVE = {("uplatform", "melbet")}

# "Relax Gaming" and "RelaxGaming" are two partners in the file and are NOT
# merged here — the unit list on the dashboard treats them separately, and
# merging them makes the partner count 22 instead of 23.
MERGE_PARTNERS: dict = {}


def build(path: pathlib.Path) -> dict:
    wb = load_workbook(path, data_only=True, read_only=True)
    missing = [s for s in list(ROSTERS) + list(BET_SHEETS) if s not in wb.sheetnames]
    if missing:
        sys.exit(f"workbook is missing sheet(s): {', '.join(missing)}\nfound: {wb.sheetnames}")

    # ---- 1. month columns, unioned across both bet sheets -----------------
    labels: list[str] = []
    sheet_months = {}
    for sheet, src in BET_SHEETS.items():
        ws = wb[sheet]
        hr, hm, row = find_header(ws, needed=("partner",))
        if hr is None:
            sys.exit(f"could not find a header row on '{sheet}'")
        cols = {}
        for i, cell in enumerate(row):
            lab = month_label(cell)
            if lab:
                cols[lab] = i
                if lab not in labels:
                    labels.append(lab)
        sheet_months[sheet] = (hr, hm, cols)
    labels.sort()

    # ---- 2. bets per (partner, project) ----------------------------------
    bets = {}
    for sheet, src in BET_SHEETS.items():
        ws = wb[sheet]
        hr, hm, cols = sheet_months[sheet]
        pi, ji = hm.get("partner"), hm.get("project", hm.get("platform"))
        for row in ws.iter_rows(min_row=hr + 1, values_only=True):
            if pi is None or ji is None:
                break
            p, j = norm(row[pi]), norm(row[ji])
            if not p and not j:
                continue
            months = [num(row[cols[l]]) if l in cols and cols[l] < len(row) else None for l in labels]
            rec = {
                "m": months,
                "amt": num(row[hm["turnover"]]) if "turnover" in hm and hm["turnover"] < len(row) else 0,
                "ggr": num(row[hm["ggr"]]) if "ggr" in hm and hm["ggr"] < len(row) else 0,
                "src": src,
            }
            bets[key(p, j)] = rec
            bets.setdefault(key(j), rec)  # fall back to project-only matching

    # ---- 3. promotion statuses -------------------------------------------
    offers = {}
    if OFFER_SHEET in wb.sheetnames:
        ws = wb[OFFER_SHEET]
        hr, hm, _ = find_header(ws, needed=("partner",))
        if hr is not None and "status" in hm:
            pi = hm["partner"]
            ji = hm.get("project", hm.get("platform", pi))
            for row in ws.iter_rows(min_row=hr + 1, values_only=True):
                p = norm(row[pi]) if pi < len(row) else ""
                j = norm(row[ji]) if ji < len(row) else ""
                st = norm(row[hm["status"]]) if hm["status"] < len(row) else ""
                if p or j:
                    offers[key(p, j)] = st
                    offers.setdefault(key(p), st)

    # ---- 4. promotional discounts / lobby placements ----------------------
    disc = []
    if DISCOUNT_SHEET in wb.sheetnames:
        ws = wb[DISCOUNT_SHEET]
        hr, hm, _ = find_header(ws, needed=("partner",))
        if hr is not None:
            for row in ws.iter_rows(min_row=hr + 1, values_only=True):
                get = lambda f: row[hm[f]] if f in hm and hm[f] < len(row) else None
                p = norm(get("partner"))
                if not p:
                    continue
                disc.append(
                    {
                        "p": p,
                        "j": norm(get("project")),
                        "s": date_str(get("start")),
                        "e": date_str(get("end")),
                        "d": num(get("discount")),
                        "g": norm(get("game")),
                        "pos": norm(get("position")),
                    }
                )

    # ---- 5. roster rows ---------------------------------------------------
    rows = []
    for sheet, bucket in ROSTERS.items():
        ws = wb[sheet]
        hr, hm, _ = find_header(ws, needed=("partner",))
        if hr is None:
            sys.exit(f"could not find a header row on '{sheet}'")
        for raw in ws.iter_rows(min_row=hr + 1, values_only=True):
            get = lambda f: raw[hm[f]] if f in hm and hm[f] < len(raw) else None
            p = MERGE_PARTNERS.get(norm(get("partner")), norm(get("partner")))
            pl = norm(get("platform"))
            j = norm(get("project")) or pl or p
            if not p and not j:
                continue

            b = bets.get(key(p, j)) or bets.get(key(j)) or {}
            months = b.get("m") or [0.0] * len(labels)
            vals = [v for v in months if v is not None]

            rows.append(
                {
                    "p": p,
                    "pl": pl,
                    "j": j,
                    "b": bucket,
                    "o": offers.get(key(p, j), offers.get(key(p), "")),
                    "c": norm(get("comment")),
                    "m": [None if v is None else int(v) for v in months],
                    "tb": int(sum(vals)),
                    "tp": int(num(get("players"))),
                    "pk": int(max(vals) if vals else 0),
                    "mw": sum(1 for v in vals if v > 0),
                    "ja": int(next((v for v in reversed(months) if v is not None), 0)),
                    "amt": int(b.get("amt", 0)),
                    "ggr": int(b.get("ggr", 0)),
                    "src": b.get("src", 0),
                }
            )

    # ---- 6. data-quality notes -------------------------------------------
    issues = []
    names = {r["p"] for r in rows}
    if "Relax Gaming" in names and "RelaxGaming" in names:
        issues.append(
            "“Relax Gaming” and “RelaxGaming” are kept as <b>two separate "
            "partners</b>, as they are written in the file and as your unit list treats them."
        )
    slug = {}
    for r in rows:
        slug.setdefault(re.sub(r"[^a-z0-9]", "", r["j"].lower()), set()).add(r["j"])
    for variants in slug.values():
        if len(variants) > 1:
            a, b_ = sorted(variants)[:2]
            issues.append(f"“{a}” and “{b_}” differ only in spacing — probably one project.")
    for r in rows:
        if r["src"] == 0:
            held = (r["p"].lower(), r["j"].lower()) in ASSUME_ACTIVE
            issues.append(
                f"<b>{r['p']} / {r['j']}</b> has no row in Source, so it scores as never-bet."
                + (" It is <b>held as active</b> pending your check." if held else "")
            )
    if len(sheet_months.get("Source 2", (0, {}, {}))[2]) < len(labels):
        gap = sorted(set(labels) - set(sheet_months["Source 2"][2]))
        if gap:
            issues.append(
                f"Source 2 has no {', '.join(gap)} column, so the projects it covers show a gap "
                "there rather than a zero."
            )

    return {"labels": labels, "rows": rows, "disc": disc, "issues": issues[:12]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("xlsx", type=pathlib.Path, help="path to Partners List.xlsx")
    ap.add_argument("-o", "--out", type=pathlib.Path, default=pathlib.Path("data/partners.json"))
    args = ap.parse_args()

    if not args.xlsx.exists():
        return print(f"error: {args.xlsx} not found", file=sys.stderr) or 1

    data = build(args.xlsx)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    counts = {}
    for r in data["rows"]:
        counts[r["b"]] = counts.get(r["b"], 0) + 1
    print(
        f"wrote {args.out}  ({len(data['rows'])} rows: "
        + ", ".join(f"{k} {v}" for k, v in counts.items())
        + f" · {len(data['labels'])} months · {len(data['disc'])} placements · {len(data['issues'])} notes)"
    )
    print("now run:  python build.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
