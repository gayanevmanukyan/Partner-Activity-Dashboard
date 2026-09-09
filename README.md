# Partnership Desk

A single-page dashboard over the **Partners List** workbook: which partners and
projects are taking bets, which have gone quiet, where the network promotion
offers stand, and which games sit in which lobby positions.

The whole dashboard is one self-contained HTML file. No server, no build
toolchain, no npm — open `index.html` and it works, including from a file://
path. The only outbound request is the Google Fonts stylesheet, and the page
falls back to system fonts without it.

---

## Layout of this repo

```
index.html                     the built page — this is what gets deployed
src/index.template.html        the page source, with a __PDATA__ placeholder
data/partners.json             the dataset (918 project rows, Jan–Sep 2026)
build.py                       injects the JSON into the template -> index.html
scripts/xlsx_to_json.py        rebuild the JSON from Partners List.xlsx
scripts/sheets_to_json.py      rebuild the JSON from a Google Sheets copy
_github/workflows/deploy.yml   build + publish to GitHub Pages on every push
setup-workflow.bat             run once: renames _github\ to .github\
```

> **Run `setup-workflow.bat` once before the first push.** The workflow had to
> arrive as `_github\` because folders beginning with a dot cannot be written
> to the Desktop remotely; GitHub only reads it from `.github\workflows\`.
> Double-click the .bat, or do it by hand:
>
> ```
> mkdir .github\workflows
> move _github\workflows\deploy.yml .github\workflows\deploy.yml
> rmdir /s /q _github
> ```

The template and the data are kept apart so that refreshing the numbers never
means touching the markup, and changing the markup never means re-exporting the
numbers.

---

## Everyday use

**Refresh the numbers from a new workbook export**

```bash
pip install openpyxl
python scripts/xlsx_to_json.py "Partners List.xlsx" -o data/partners.json
python build.py
```

**Change something on the page** — edit `src/index.template.html`, then:

```bash
python build.py
```

Never edit `index.html` by hand; the next build overwrites it.

**Preview locally** — open `index.html` in a browser, or:

```bash
python -m http.server 8000     # then http://localhost:8000
```

---

## Deploying

### First push — the easy way

Double-click **`push-to-github.bat`**. It renames `_github\` to `.github\`,
creates the repository, commits everything, asks for the repository URL (the
green **Code** button on GitHub, HTTPS tab) and pushes. If GitHub asks you to
sign in, a browser window opens and you confirm it yourself.

If the repository already has a README committed at creation, the script
merges it in and pushes again, so that case is handled too.

### Or by hand

```bash
cd partnership-desk
setup-workflow.bat
git init -b main
git add .
git commit -m "Partnership Desk: initial version"
git remote add origin https://github.com/<you>/partnership-desk.git
git push -u origin main
```

Then, either way, in the repository: **Settings → Pages → Source: GitHub
Actions**. The workflow in `.github/workflows/deploy.yml` runs `build.py` and
publishes the result. The page lands at
`https://<you>.github.io/partnership-desk/`.

### Keep the repo private

A private repo can still publish Pages on GitHub Team or Enterprise, with the
site restricted to organisation members. On a free account, Pages from a
private repo is public — so either use the organisation account, or keep the
repo private and share the built `index.html` file directly.

Either way, `.gitignore` keeps the workbook itself out of the repo. The
dataset in `data/partners.json` does contain commercial figures, so treat the
repository as confidential.

### Updating later

```bash
python scripts/xlsx_to_json.py "Partners List.xlsx" -o data/partners.json
python build.py
git commit -am "Data refresh: <month>"
git push
```

Pages redeploys within a minute or two.

---

## Making it refresh itself

The manual export is the weak point: someone has to remember. Once the
workbook lives in Google Drive rather than SharePoint, the pipeline can run on
a schedule with nobody in the loop.

1. Open the workbook in Google Sheets, copy the id out of the URL
   (`https://docs.google.com/spreadsheets/d/`**`<id>`**`/edit`).
2. Add it as a repository **variable** named `PARTNERS_SHEET_ID`
   (Settings → Secrets and variables → Actions → Variables).
3. If the sheet is not link-shared, create a Google Cloud service account,
   give its email Viewer access on the file, and paste the JSON key into a
   repository **secret** named `GOOGLE_SERVICE_ACCOUNT_JSON`.
4. Uncomment the *Refresh data from Google Sheets* step and the `schedule:`
   block in `.github/workflows/deploy.yml`.

`scripts/sheets_to_json.py` downloads the sheet as .xlsx and hands it to the
same parser as the manual route, so both produce identical output and there is
only one set of column rules to keep in step with the file.

---

## How the data is read

`scripts/xlsx_to_json.py` matches columns **by header name**, not by position,
so inserting a column into the workbook does not break it. Accepted spellings
live in the `HEADERS` dictionary at the top of the file — add to it rather than
renaming columns in the workbook.

It reads:

| Sheet | What comes out of it |
|---|---|
| Active Partners / Low Activity / No Activity | the roster: one row per project, and which bucket it sits in |
| Source, Source 2 | bets per month, turnover, GGR |
| Network Promotion offer | the offer status per partner/project |
| Promotional Discounts | game discounts and the lobby position bought with them |

Roster rows are matched to bets on partner + project. A row with no match has
taken no bets at all — that is what the *never taken a bet* column counts, and
it is a real signal, not a parsing failure.

### Two rules that are deliberate, not bugs

- **Activity is measured per unit, not per project.** A unit is one line of
  communication: a whole partner, a platform inside a partner (Softswiss →
  Luckydreams), or a single project (Trio Group → Pinup). The mapping lives in
  `UNIT_RULES` inside `src/index.template.html`; the 325 Active-sheet projects
  roll up into 44 units. If a partner starts or ends a separate conversation,
  edit that table.
- **"Relax Gaming" and "RelaxGaming" stay separate.** They are two partners in
  the file and two entries in the unit list. Merging them makes the partner
  count 22 instead of 23.

`Uplatform / Melbet` is held as active by hand (`ASSUME_ACTIVE`) despite having
no row in Source, pending a check. Anything else the parser finds odd is listed
on the **Data model & roadmap** tab of the dashboard itself, so the workbook's
rough edges are visible rather than silently smoothed over.

---

## Entering data on the board

The workbook stays the database, but nothing has to be typed into it first. **Data entry** in the header
turns every row into a form: click a project to change its platform, sheet, players, promotion status,
comment or its monthly bets; **+ Project** and **+ Placement** add rows; **Delete row** removes one. Every
counter, split, trend and activity verdict is derived, so it all recomputes from what was typed.

Entries live **in the editor's own browser** — this is a static page, there is no server to save to and
nobody else sees them until the file moves. The **Changes** button is that move, and it goes both ways:

- **Board → file.** Download an `.xlsx` carrying the same six sheets as Partners List (Active Partners,
  Low Activity, No Activity, Network Promotion offer, Promotional Discounts, Source), or the
  `partners.json` this page reads. Drop the JSON into `data/`, run `python build.py`, push — the page
  now holds the entries for everyone.
- **File → board.** Point **Choose a file…** at a newer Partners List. It is parsed in the page, becomes
  the new base for that browser, and anything already typed stays on top of it.

Each entry is stored as the *difference* from the file, field by field, so the Changes list names exactly
what was touched, any single entry can be undone, and a newer workbook does not wipe unsent work.

Both the writer and the reader for `.xlsx` are written into the page — no library, no CDN, nothing
uploaded. Reading a workbook needs `DecompressionStream`, which Chrome and Edge have; a browser without it
gets a clear message and can still import `partners.json`.

When the file moves to Google Sheets, the same forms point at the sheet instead of the browser: the entry
side does not change, only where it saves. `scripts/sheets_to_json.py` is the other half of that already.

## What is on the page

**Partners & projects** — activity units, what the bets say, bets per month
(hover for the three biggest contributors, click for the full ranked list),
biggest projects, and the full table at three levels: units, partners,
projects. The *Sheet · units* switch at the top left moves between Active, Low
and No Activity; Active is where you start and the other two are there when you
need them.

**Promotion offers** — the pipeline by status, uptake, and the offer table.

**Game placements** — discounts given against lobby positions, filtered by
partner then project.

**Data model & roadmap** — where each number comes from, and the data-quality
notes above.

Plus, across the whole page: light / dark / auto theme, drag-and-drop widget
rearranging, and review mode — every widget takes a comment, which is how the
dashboard gets read before it is finalised.

### One note about review comments

On the version published as a Claude artifact, review comments are shared: they
save to the artifact's own store and everyone signed in to the organisation
sees the same list. On GitHub Pages there is no such store, so comments stay in
the reader's own browser — the banner under the tabs says which mode is
running. If shared comments matter more than a public URL, keep using the
artifact; if the URL matters more, use Pages and collect comments another way.
