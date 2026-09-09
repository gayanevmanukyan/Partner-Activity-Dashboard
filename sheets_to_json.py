#!/usr/bin/env python3
"""
Rebuild data/partners.json from a Google Sheets copy of the Partners List,
so the dashboard can refresh itself without anyone downloading a workbook.

This is the path to take once the file lives in Google Drive rather than
on SharePoint. It does not replace scripts/xlsx_to_json.py — it downloads
the sheet as .xlsx and hands it to exactly the same parser, so both routes
produce byte-identical output and there is only one set of column rules to
maintain.

    pip install requests openpyxl
    python scripts/sheets_to_json.py <spreadsheet-id> -o data/partners.json

The spreadsheet id is the long token in the URL:
    https://docs.google.com/spreadsheets/d/<THIS BIT>/edit

ACCESS
------
Public / link-shared sheet: nothing else is needed.

Private sheet: create a Google Cloud service account, give it Viewer on the
file, download the JSON key, and point GOOGLE_APPLICATION_CREDENTIALS at
it — or, in GitHub Actions, put the key in a repository secret named
GOOGLE_SERVICE_ACCOUNT_JSON (see .github/workflows/deploy.yml).

    pip install google-auth
    export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
    python scripts/sheets_to_json.py <spreadsheet-id>
"""

import argparse
import json
import os
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

try:
    import requests
except ImportError:  # pragma: no cover
    sys.exit("requests is required:  pip install requests")

from xlsx_to_json import build  # noqa: E402

EXPORT = "https://docs.google.com/spreadsheets/d/{id}/export?format=xlsx"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def auth_header() -> dict:
    """Bearer token from a service-account key, if one is configured."""
    key = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not key and not path:
        return {}
    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
    except ImportError:
        sys.exit("a private sheet needs google-auth:  pip install google-auth")

    if key:
        info = json.loads(key)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        creds = service_account.Credentials.from_service_account_file(path, scopes=SCOPES)
    creds.refresh(Request())
    return {"Authorization": f"Bearer {creds.token}"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spreadsheet_id", nargs="?", default=os.environ.get("PARTNERS_SHEET_ID"))
    ap.add_argument("-o", "--out", type=pathlib.Path, default=pathlib.Path("data/partners.json"))
    ap.add_argument("--keep-xlsx", type=pathlib.Path, help="also save the downloaded workbook here")
    args = ap.parse_args()

    if not args.spreadsheet_id:
        return print("error: pass a spreadsheet id or set PARTNERS_SHEET_ID", file=sys.stderr) or 1

    url = EXPORT.format(id=args.spreadsheet_id)
    resp = requests.get(url, headers=auth_header(), timeout=120, allow_redirects=True)
    if resp.status_code == 404:
        return print("error: no such spreadsheet, or the service account cannot see it", file=sys.stderr) or 1
    if "html" in resp.headers.get("content-type", ""):
        return print("error: Google returned a sign-in page — the sheet is private and no credentials were supplied", file=sys.stderr) or 1
    resp.raise_for_status()

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as fh:
        fh.write(resp.content)
        tmp = pathlib.Path(fh.name)
    if args.keep_xlsx:
        args.keep_xlsx.write_bytes(resp.content)

    try:
        data = build(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {args.out}  ({len(data['rows'])} rows · {len(data['labels'])} months)")
    print("now run:  python build.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
