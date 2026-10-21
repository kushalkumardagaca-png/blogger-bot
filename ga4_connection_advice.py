#!/usr/bin/env python3
"""Read the newest Analytics measurement file and print one sentence a person can act on.

This runs at the end of the "Connect Analytics read access" workflow, so the owner gets the answer
while they are still on the page instead of waiting for the next night's job. It never prints a
token or a secret: this repository is public and Actions logs are readable by anyone, so credentials
are described by length only.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "GA4_MEASUREMENT.json"

# Every status the measurement module can write, with the sentence the owner should read. The
# annotation levels are chosen by who can fix it: NOTICE for a success, ERROR when the robots are
# blocked by something only a person can authorise, WARNING when the connection works but is quiet.
ADVICE = {
    "MEASURED": ("notice", "Analytics is readable: {views} pageviews and {readers} engaged readers "
                            "on the most recent whole day, over {days} days of data."),
    "NO_DATA_YET": ("warning", "The connection works and Google answered, but the property returned no "
                               "rows for the last 7 days. That is normal on a brand-new property or "
                               "right after a tag change; it is not a measured audience of zero."),
    "TAG_UNKNOWN": ("warning", "Google answered, but the public homepage could not be fetched from this "
                               "network, so the tag could not be confirmed from here. The numbers are "
                               "still real; open the site once in your browser to confirm the tag is there."),
    "TAG_NOT_OBSERVED": ("error", "The connection is fine but the analytics tag is not on the live pages, "
                                  "so nothing is being counted. The tag has to be added before any number "
                                  "can exist."),
    "CREDENTIALS_MISSING": ("error", "No Analytics token is stored yet. Follow GA4_CONNECT.md "
                                     "(browser steps, nothing to install) and add the repository secret "
                                     "GA4_REFRESH_TOKEN; then run this workflow again."),
    "SCOPE_INSUFFICIENT": ("error", "The stored token was created before Analytics was added to it. "
                                    "Repeat the browser step and replace the GA4_REFRESH_TOKEN secret; "
                                    "no other value needs changing."),
    "TOKEN_REFUSED": ("error", "Google refused the stored token (expired or revoked). Google cuts "
                               "refresh tokens short while an OAuth app is still in Testing. Repeat the "
                               "browser step and replace the GA4_REFRESH_TOKEN secret."),
    "PROPERTY_NOT_FOUND": ("error", "The token works but no GA4 property could be matched to "
                                    "G-WLEEYTKV12. Add the numeric Property ID as a repository variable "
                                    "named GA4_PROPERTY_ID (Analytics -> Admin -> Property settings)."),
    "READ_FAILED": ("error", "The read failed for a reason Google did not classify: see the error line "
                             "above. Nothing was invented in place of a number."),
}


def main() -> int:
    if not REPORT.exists():
        print("::error title=Analytics check::the measurement file was not written, so the check itself "
              "did not run; the workflow log above shows why")
        return 1
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    status = str(report.get("status") or "READ_FAILED")
    totals = report.get("totals") or {}
    level, sentence = ADVICE.get(status, ADVICE["READ_FAILED"])
    if status == "MEASURED":
        sentence = sentence.format(views=totals.get("views"), readers=totals.get("dailyReaders"),
                                   days=report.get("windowDays"))
    print(f"status: {status}")
    print(f"property: {report.get('propertyId') or 'not resolved'} "
          f"({report.get('propertyIdSource') or 'unknown'})")
    print(f"measurement id: {report.get('measurementId')}")
    if report.get("error"):
        print(f"google said: {report['error']}")
    if report.get("remedy"):
        print(f"what to do: {report['remedy']}")
    print(f"::{level} title=Analytics read access::{sentence}")
    # 0 only when Google actually returned numbers, so a red run means the connection is not finished.
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
