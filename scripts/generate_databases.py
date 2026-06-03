#!/usr/bin/env python3
"""
Generate star catalog databases for the Pi Zero 2W finder.

Two formats are produced:
  cedar_solve_13deg.npz  -- cedar-solve / olive-solve (.npz, hip_main.dat)
  tetra3rs_13deg.bin     -- tetra3rs (.bin, Gaia DR3 via gaia-catalog package)

Both databases cover 10.5°–14° FOV, star_max_magnitude=8.0.

Usage:
  python generate_databases.py [--output-dir DIR] [--hip-catalog PATH]
                               [--skip-cedar-solve] [--skip-tetra3rs]
"""

import argparse
import gzip
import pathlib
import shutil
import sys
import urllib.request

FOV_MIN = 10.5
FOV_MAX = 14.0
STAR_MAX_MAGNITUDE = 8.0
EPOCH_YEAR = 2026.0
HIP_URL = "hip_main.dat.gz"


# def download_hip_main(dest: pathlib.Path) -> None:
#     print(f"Downloading hip_main.dat → {dest}")
#     with urllib.request.urlopen(HIP_URL) as resp, gzip.open(resp) as gz:
#         dest.write_bytes(gz.read())
#     print(f"  {dest.stat().st_size / 1e6:.1f} MB")


def generate_cedar_solve(output_dir: pathlib.Path, hip_catalog: pathlib.Path) -> pathlib.Path:
    import tetra3 as t3_mod

    tetra3_pkg = pathlib.Path(t3_mod.__file__).parent
    hip_dest = tetra3_pkg / "hip_main.dat"
    if hip_dest.resolve() != hip_catalog.resolve():
        shutil.copy(hip_catalog, hip_dest)
        print(f"  Copied hip_main.dat → {hip_dest}")

    db_stem = output_dir / "cedar_solve_13deg"
    print(f"Generating cedar-solve database → {db_stem}.npz")
    print(f"  fov_range=({FOV_MIN}, {FOV_MAX}), star_max_magnitude={STAR_MAX_MAGNITUDE}")

    t3 = t3_mod.Tetra3()
    t3.generate_database(
        save_as=str(db_stem),
        fov_range=(FOV_MIN, FOV_MAX),
        star_max_magnitude=STAR_MAX_MAGNITUDE,
        catalog="hip",
        pattern_stars_per_fov=10,
        verification_stars_per_fov=30,
    )
    result = pathlib.Path(str(db_stem) + ".npz")
    print(f"  Done: {result.stat().st_size / 1e6:.1f} MB")
    return result


def generate_tetra3rs(output_dir: pathlib.Path) -> pathlib.Path:
    import tetra3rs

    db_path = output_dir / "tetra3rs_13deg.bin"
    print(f"Generating tetra3rs database → {db_path}")
    print(f"  fov=[{FOV_MIN}, {FOV_MAX}], star_max_magnitude={STAR_MAX_MAGNITUDE}")
    print("  catalog: Gaia DR3 via gaia-catalog package")

    db = tetra3rs.SolverDatabase.generate_from_gaia(
        max_fov_deg=FOV_MAX,
        min_fov_deg=FOV_MIN,
        star_max_magnitude=STAR_MAX_MAGNITUDE,
        epoch_proper_motion_year=EPOCH_YEAR,
        catalog_path=None,
    )
    db.save_to_file(str(db_path))
    print(f"  Done: {db_path.stat().st_size / 1e6:.1f} MB")
    return db_path


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--output-dir", default="databases",
                    help="Output directory (default: databases)")
    ap.add_argument("--hip-catalog", default=None,
                    help="Path to hip_main.dat; downloaded into output-dir if omitted")
    ap.add_argument("--skip-cedar-solve", action="store_true",
                    help="Skip cedar-solve .npz generation")
    ap.add_argument("--skip-tetra3rs", action="store_true",
                    help="Skip tetra3rs .bin generation")
    args = ap.parse_args()

    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []

    if not args.skip_cedar_solve:
        hip_catalog = (
            pathlib.Path(args.hip_catalog)
            if args.hip_catalog
            else output_dir / "hip_main.dat"
        )
        if not hip_catalog.exists():
            try:
                download_hip_main(hip_catalog)
            except Exception as exc:
                print(f"ERROR downloading hip_main.dat: {exc}", file=sys.stderr)
                errors.append(f"cedar-solve: hip_main.dat download failed ({exc})")
                hip_catalog = None
        if hip_catalog and hip_catalog.exists():
            try:
                generate_cedar_solve(output_dir, hip_catalog)
            except Exception as exc:
                print(f"ERROR generating cedar-solve database: {exc}", file=sys.stderr)
                errors.append(f"cedar-solve: {exc}")

    if not args.skip_tetra3rs:
        try:
            generate_tetra3rs(output_dir)
        except Exception as exc:
            print(f"ERROR generating tetra3rs database: {exc}", file=sys.stderr)
            errors.append(f"tetra3rs: {exc}")

    if errors:
        print("\nErrors:", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        sys.exit(1)

    print("\nDatabases:")
    for ext in ("*.npz", "*.bin"):
        for f in sorted(output_dir.glob(ext)):
            print(f"  {f.name}  ({f.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
