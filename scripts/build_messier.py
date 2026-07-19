#!/usr/bin/env python3
"""
Build a compact Messier catalog for the diofinder "centered object" label.

The diofinder finder already labels the brightest cataloged *star* at the aim
point (star_names.csv). This adds the DSO sibling: name the bright *Messier*
object the aim point is on ("M31 — Andromeda Galaxy"). Display only — it never
touches the solve, the align, or the aim point.

Source: OpenNGC (mattiaverga/OpenNGC), the maintained open NGC/IC catalog, which
carries J2000 position, angular size, magnitude, morphological type, the Messier
number, and common names. 107 of the 110 Messier objects live in OpenNGC's
NGC.csv; the three that are *not* NGC objects are supplemented from well-known
coordinates below:
  * M40  — Winnecke 4, an optical double star (a Messier "mistake").
  * M45  — the Pleiades (= Melotte 22), a naked-eye open cluster, not in NGC.
  * M102 — disputed; resolved here as NGC 5866 (the Spindle Galaxy), the common
           identification. (Some sources call M102 a duplicate of M101.)

Output columns (data/messier.csv):
  m            Messier id, e.g. "M31"
  name         common name, e.g. "Andromeda Galaxy" (may be empty)
  ra_deg       J2000 RA in degrees
  dec_deg      J2000 Dec in degrees
  size_arcmin  major-axis extent in arcmin (drives the label's match radius)
  mag          integrated magnitude, V preferred else B (may be empty)
  type         OpenNGC type code (G, GCl, OCl, PN, Neb, HII, Cl+N, ...)

Usage:
  python scripts/build_messier.py [--src PATH|URL] [--dest PATH]
"""

import argparse
import csv
import io
import pathlib
import sys
import urllib.request

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_DEST = REPO_ROOT / "data" / "messier.csv"
OPENNGC_URL = (
    "https://raw.githubusercontent.com/mattiaverga/OpenNGC/"
    "master/database_files/NGC.csv"
)

# Messier objects absent from OpenNGC's NGC.csv (not NGC objects). RA/Dec in the
# same HH:MM:SS[.s] / +DD:MM:SS[.s] sexagesimal form OpenNGC uses, so the one
# parser handles them too. Values from standard references (SEDS / SIMBAD).
SUPPLEMENT = [
    # m,   name,            RA,            Dec,          MajAx, mag,  type
    ("M40",  "Winnecke 4",    "12:22:12.5", "+58:04:59",   0.8,  8.4, "**"),
    ("M45",  "Pleiades",      "03:47:24",   "+24:07:00", 110.0,  1.6, "OCl"),
    ("M102", "Spindle Galaxy","15:06:29.5", "+55:45:48",   4.7,  9.9, "G"),
]


def _parse_ra_hms(s: str) -> float:
    """'HH:MM:SS.ss' -> degrees (RA hours * 15)."""
    h, m, sec = (s.strip().split(":") + ["0", "0"])[:3]
    hours = int(h) + int(m) / 60.0 + float(sec) / 3600.0
    return hours * 15.0


def _parse_dec_dms(s: str) -> float:
    """'+DD:MM:SS.s' -> degrees (sign-aware)."""
    s = s.strip()
    sign = -1.0 if s[:1] == "-" else 1.0
    s = s.lstrip("+-")
    d, m, sec = (s.split(":") + ["0", "0"])[:3]
    return sign * (int(d) + int(m) / 60.0 + float(sec) / 3600.0)


def _num(s):
    s = (s or "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _fetch(src: str) -> str:
    if src.startswith(("http://", "https://")):
        with urllib.request.urlopen(src, timeout=60) as r:
            return r.read().decode("utf-8")
    return pathlib.Path(src).read_text(encoding="utf-8")


def build(src: str):
    """Return a list of Messier rows: (m, name, ra_deg, dec_deg, size, mag, type)."""
    rows = {}                     # keyed by Messier number, deduped
    reader = csv.DictReader(io.StringIO(_fetch(src)), delimiter=";")
    for r in reader:
        mraw = (r.get("M") or "").strip()
        if not mraw:
            continue
        mnum = int(mraw)
        try:
            ra = _parse_ra_hms(r["RA"])
            dec = _parse_dec_dms(r["Dec"])
        except (ValueError, KeyError, IndexError):
            print(f"  WARN: bad coords for M{mnum} ({r.get('Name')}); skipped",
                  file=sys.stderr)
            continue
        mag = _num(r.get("V-Mag"))
        if mag is None:
            mag = _num(r.get("B-Mag"))
        size = _num(r.get("MajAx"))
        # OpenNGC "Common names" is comma-separated; keep the first, tidiest one.
        name = (r.get("Common names") or "").split(",")[0].strip()
        row = (f"M{mnum}", name, ra, dec, size, mag, (r.get("Type") or "").strip())
        # If a Messier number appears twice, keep the physically larger entry.
        prev = rows.get(mnum)
        if prev is None or (size or 0) > (prev[4] or 0):
            rows[mnum] = row

    # Supplement the non-NGC objects.
    for m, name, ra_s, dec_s, size, mag, typ in SUPPLEMENT:
        mnum = int(m[1:])
        rows[mnum] = (m, name, _parse_ra_hms(ra_s), _parse_dec_dms(dec_s),
                      size, mag, typ)

    return [rows[k] for k in sorted(rows)]


def main():
    ap = argparse.ArgumentParser(description="Build the Messier label catalog.")
    ap.add_argument("--src", default=OPENNGC_URL,
                    help="OpenNGC NGC.csv path or URL")
    ap.add_argument("--dest", type=pathlib.Path, default=DEFAULT_DEST)
    args = ap.parse_args()

    print(f"Reading OpenNGC from {args.src}")
    rows = build(args.src)

    missing = [m for m in range(1, 111)
               if f"M{m}" not in {r[0] for r in rows}]
    if missing:
        print(f"  WARN: missing Messier numbers: {missing}", file=sys.stderr)

    args.dest.parent.mkdir(parents=True, exist_ok=True)
    with open(args.dest, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["m", "name", "ra_deg", "dec_deg",
                    "size_arcmin", "mag", "type"])
        for m, name, ra, dec, size, mag, typ in rows:
            w.writerow([m, name, f"{ra:.5f}", f"{dec:.5f}",
                        "" if size is None else f"{size:.3g}",
                        "" if mag is None else f"{mag:.2f}", typ])

    print(f"Wrote {len(rows)} Messier objects -> {args.dest}")


if __name__ == "__main__":
    main()
