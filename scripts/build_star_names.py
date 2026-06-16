#!/usr/bin/env python3
"""
Build a compact star-names catalog for the eFinder "brightest star" display.

Source: the HYG database (Hipparcos + Yale BSC + Gliese merge), which carries
proper names, Bayer letters, Flamsteed numbers, constellation, and HR/HIP IDs
keyed by position. We trim it to a magnitude limit and emit a small CSV that
the device cross-matches against the solved pointing to label the brightest
star in the field.

Output columns (data/star_names.csv):
  ra_deg   RA in degrees (HYG stores RA in hours; converted here)
  dec_deg  Dec in degrees
  mag      visual magnitude
  name     best human label: proper name, else Bayer (α Tau), else Flamsteed
           (87 Tau), else "HR n" / "HIP n"
  desig    secondary designation when a proper name exists (e.g. "α Tau"),
           otherwise empty

All bright stars (to the magnitude limit, default 7.0) are included — not just
named ones — so the brightest star in any field always resolves to something;
unnamed stars fall back to their HR/HIP id.

Usage:
  python scripts/build_star_names.py [--mag-limit 7.0] [--src PATH|URL] [--dest PATH]
"""

import argparse
import csv
import io
import pathlib
import sys
import urllib.request

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_DEST = REPO_ROOT / "data" / "star_names.csv"
HYG_URL = (
    "https://raw.githubusercontent.com/astronexus/HYG-Database/"
    "main/hyg/CURRENT/hygdata_v41.csv"
)

GREEK = {
    "Alp": "α", "Bet": "β", "Gam": "γ", "Del": "δ", "Eps": "ε", "Zet": "ζ",
    "Eta": "η", "The": "θ", "Iot": "ι", "Kap": "κ", "Lam": "λ", "Mu": "μ",
    "Nu": "ν", "Xi": "ξ", "Omi": "ο", "Pi": "π", "Rho": "ρ", "Sig": "σ",
    "Tau": "τ", "Ups": "υ", "Phi": "φ", "Chi": "χ", "Psi": "ψ", "Ome": "ω",
}
SUPERSCRIPT = {"1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵"}


def bayer_desig(bayer: str, con: str) -> str:
    """'Alp', 'Tau' -> 'α Tau'; 'Alp-1' -> 'α¹ Tau'."""
    if not bayer or not con:
        return ""
    base, _, sup = bayer.partition("-")
    letter = GREEK.get(base)
    if not letter:
        return ""
    if sup:
        letter += "".join(SUPERSCRIPT.get(c, c) for c in sup)
    return f"{letter} {con}"


def flam_desig(flam: str, con: str) -> str:
    if not flam or not con:
        return ""
    return f"{flam} {con}"


def open_source(src: str):
    if src.startswith(("http://", "https://")):
        print(f"Downloading HYG catalog from {src}")
        req = urllib.request.Request(src, headers={"User-Agent": "efinder-build"})
        data = urllib.request.urlopen(req, timeout=120).read()
        return io.StringIO(data.decode("utf-8"))
    return open(src, newline="", encoding="utf-8")


def build(src: str, dest: pathlib.Path, mag_limit: float) -> None:
    out_rows = []
    with open_source(src) as f:
        reader = csv.DictReader(f)
        for r in reader:
            mag_s = r.get("mag", "")
            if not mag_s:
                continue
            try:
                mag = float(mag_s)
            except ValueError:
                continue
            if mag > mag_limit:
                continue
            # HYG id 0 is the Sun; skip it.
            if r.get("proper", "").strip() == "Sol":
                continue

            con = r.get("con", "").strip()
            proper = r.get("proper", "").strip()
            b_desig = bayer_desig(r.get("bayer", "").strip(), con)
            f_desig = flam_desig(r.get("flam", "").strip(), con)

            if proper:
                name = proper
                desig = b_desig or f_desig
            elif b_desig:
                name = b_desig
                desig = f_desig
            elif f_desig:
                name = f_desig
                desig = ""
            elif r.get("hr", "").strip():
                name = f"HR {r['hr'].strip()}"
                desig = ""
            elif r.get("hip", "").strip():
                name = f"HIP {r['hip'].strip()}"
                desig = ""
            else:
                continue  # no usable label

            # ',' would break the simple CSV; none of our fields contain one,
            # but guard anyway.
            if "," in name or "," in desig:
                continue

            ra_deg = float(r["ra"]) * 15.0  # HYG RA is in hours
            dec_deg = float(r["dec"])
            out_rows.append((ra_deg, dec_deg, mag, name, desig))

    out_rows.sort(key=lambda t: t[2])  # brightest first
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", newline="", encoding="utf-8") as out:
        w = csv.writer(out)
        w.writerow(["ra_deg", "dec_deg", "mag", "name", "desig"])
        for ra_deg, dec_deg, mag, name, desig in out_rows:
            w.writerow([f"{ra_deg:.5f}", f"{dec_deg:.5f}", f"{mag:.2f}", name, desig])
    print(f"Wrote {dest} ({len(out_rows)} stars, "
          f"{dest.stat().st_size / 1e3:.0f} KB, mag <= {mag_limit})")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--mag-limit", type=float, default=7.0,
                    help="Faintest star to include (default: 7.0)")
    ap.add_argument("--src", default=HYG_URL,
                    help="HYG CSV path or URL (default: HYG main/CURRENT)")
    ap.add_argument("--dest", default=str(DEFAULT_DEST),
                    help="Output CSV (default: data/star_names.csv)")
    args = ap.parse_args()
    try:
        build(args.src, pathlib.Path(args.dest), args.mag_limit)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
