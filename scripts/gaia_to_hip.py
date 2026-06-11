#!/usr/bin/env python3
"""
Convert data/gaia_hipp_merged.csv into a hip_main-format catalog file.

The output (data/gaia_hip_main.dat.gz) is a pipe-delimited file laid out
so that the stock hip_main parsers in esa/tetra3, cedar-solve, and
olive-solve read it unmodified. Only the six fields those parsers use
are populated:

  field 1   synthetic star ID (1-based row number — NOT a HIP number)
  field 5   magnitude (Gaia G band)
  field 8   RA in degrees, ICRS, de-propagated to epoch 1991.25
  field 9   Dec in degrees, ICRS, de-propagated to epoch 1991.25
  field 12  pmRA*cos(Dec) in mas/yr (0.0 when Gaia has no solution)
  field 13  pmDec in mas/yr (0.0 when Gaia has no solution)

Gaia DR3 positions are epoch 2016.0; the hip_main parsers assume epoch
1991.25 and propagate proper motion forward from there. Positions are
therefore de-propagated by -24.75 yr using Gaia's own proper motions so
the parsers' forward propagation reproduces the correct sky positions.
Stars without a proper-motion solution keep their 2016.0 position with
pm written as 0.0 (never blank — the parsers *skip* blank-pm rows, which
would silently drop 86 of the 704 brightest stars). The worst-case error
from either approximation is a few arcseconds, far below the ~51"/px
plate scale of the target instrument.

Usage:
  python scripts/gaia_to_hip.py        # rewrites data/gaia_hip_main.dat.gz
"""

import csv
import gzip
import io
import math
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "data" / "gaia_hipp_merged.csv"
DEST = REPO_ROOT / "data" / "gaia_hip_main.dat.gz"

GAIA_EPOCH = 2016.0
HIP_PM_ORIGIN = 1991.25
DELTA_YR = HIP_PM_ORIGIN - GAIA_EPOCH  # -24.75
MAS_TO_DEG = 1.0 / 1000.0 / 3600.0
# Same pole guard as the hip_main parsers: below this cos(Dec) they
# ignore proper motion entirely, so de-propagation must match.
MIN_COS_DEC = 0.05


def convert() -> None:
    lines = []
    with open(SRC, newline="") as f:
        reader = csv.reader(f)
        next(reader)  # header
        for i, row in enumerate(reader, start=1):
            ra = float(row[1])
            dec = float(row[2])
            mag = float(row[3])
            pmra = row[7].strip()
            pmdec = row[8].strip()
            cos_dec = math.cos(math.radians(dec))

            if pmra and pmdec and cos_dec > MIN_COS_DEC:
                pmra_v = float(pmra)
                pmdec_v = float(pmdec)
                ra = ra + (pmra_v / cos_dec) * MAS_TO_DEG * DELTA_YR
                dec = dec + pmdec_v * MAS_TO_DEG * DELTA_YR
            else:
                pmra_v = 0.0
                pmdec_v = 0.0

            fields = [" "] * 14
            fields[0] = "H"
            fields[1] = str(i)
            fields[5] = f"{mag:.2f}"
            fields[8] = f"{ra:.8f}"
            fields[9] = f"{dec:.8f}"
            fields[12] = f"{pmra_v:.2f}"
            fields[13] = f"{pmdec_v:.2f}"
            lines.append("|".join(fields))

    payload = ("\n".join(lines) + "\n").encode("ascii")
    # mtime=0 so regeneration from unchanged input is byte-identical
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        gz.write(payload)
    DEST.write_bytes(buf.getvalue())
    print(f"Wrote {DEST} ({len(lines)} stars, {DEST.stat().st_size / 1e6:.1f} MB gz)")


if __name__ == "__main__":
    convert()
