#!/usr/bin/env python3
"""
Generate star catalog databases for the Pi Zero 2W finder.

Two formats are produced:
  cedar_solve_13deg.npz  -- cedar-solve / olive-solve (.npz, from data/hip_main.dat.gz)
  tetra3rs_13deg.bin     -- tetra3rs (.bin, from data/gaia_hipp_merged.bin)

Both databases cover 10.5°-14° FOV, star_max_magnitude=8.0. All catalog
inputs are committed in this repository under data/ — no network access
is required.

A manifest.json is written alongside the databases recording generation
parameters, input/output SHA-256 hashes, and generator package versions.

Usage:
  python generate_databases.py [--output-dir DIR]
                               [--hip-catalog PATH] [--gaia-catalog PATH]
                               [--skip-cedar-solve] [--skip-tetra3rs]
"""

import argparse
import datetime
import gzip
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

FOV_MIN = 10.5
FOV_MAX = 14.0
STAR_MAX_MAGNITUDE = 8.0
EPOCH_YEAR = 2026.0

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_HIP_CATALOG = REPO_ROOT / "data" / "hip_main.dat.gz"
DEFAULT_GAIA_CATALOG = REPO_ROOT / "data" / "gaia_hipp_merged.bin"


def sha256_of(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def package_version(module_name: str) -> str:
    try:
        from importlib.metadata import version

        return version(module_name)
    except Exception:
        return "unknown"


def resolve_hip_catalog(path: pathlib.Path, output_dir: pathlib.Path) -> pathlib.Path:
    """Return a plain hip_main.dat, decompressing the committed .gz if needed."""
    if path.suffix == ".gz":
        dest = output_dir / "hip_main.dat"
        if not dest.exists():
            print(f"Decompressing {path} → {dest}")
            with gzip.open(path, "rb") as gz, open(dest, "wb") as out:
                shutil.copyfileobj(gz, out)
        return dest
    return path


def generate_cedar_solve(output_dir: pathlib.Path, hip_catalog: pathlib.Path) -> pathlib.Path:
    import tetra3 as t3_mod

    # cedar-solve only loads the hip catalog from its own package directory
    tetra3_pkg = pathlib.Path(t3_mod.__file__).parent
    hip_dest = tetra3_pkg / "hip_main.dat"
    if hip_dest.resolve() != hip_catalog.resolve():
        shutil.copy(hip_catalog, hip_dest)
        print(f"  Copied hip_main.dat → {hip_dest}")

    db_stem = output_dir / "cedar_solve_13deg"
    print(f"Generating cedar-solve database → {db_stem}.npz")
    print(f"  max_fov={FOV_MAX}, min_fov={FOV_MIN}, star_max_magnitude={STAR_MAX_MAGNITUDE}")

    t3 = t3_mod.Tetra3(load_database=None)
    t3.generate_database(
        save_as=str(db_stem),
        max_fov=FOV_MAX,
        min_fov=FOV_MIN,
        star_max_magnitude=STAR_MAX_MAGNITUDE,
        star_catalog="hip_main",
        epoch_proper_motion=EPOCH_YEAR,
    )
    result = pathlib.Path(str(db_stem) + ".npz")
    print(f"  Done: {result.stat().st_size / 1e6:.1f} MB")
    return result


def generate_tetra3rs(output_dir: pathlib.Path, gaia_catalog: pathlib.Path) -> pathlib.Path:
    import tetra3rs

    db_path = output_dir / "tetra3rs_13deg.bin"
    print(f"Generating tetra3rs database → {db_path}")
    print(f"  fov=[{FOV_MIN}, {FOV_MAX}], star_max_magnitude={STAR_MAX_MAGNITUDE}")
    print(f"  catalog: {gaia_catalog}")

    db = tetra3rs.SolverDatabase.generate_from_gaia(
        max_fov_deg=FOV_MAX,
        min_fov_deg=FOV_MIN,
        star_max_magnitude=STAR_MAX_MAGNITUDE,
        epoch_proper_motion_year=EPOCH_YEAR,
        catalog_path=str(gaia_catalog),
    )
    db.save_to_file(str(db_path))
    print(f"  Done: {db_path.stat().st_size / 1e6:.1f} MB")
    return db_path


def git_head() -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


def write_manifest(
    output_dir: pathlib.Path,
    inputs: dict[str, pathlib.Path],
    outputs: dict[str, pathlib.Path],
) -> pathlib.Path:
    manifest = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "repo_commit": git_head(),
        "parameters": {
            "fov_min_deg": FOV_MIN,
            "fov_max_deg": FOV_MAX,
            "star_max_magnitude": STAR_MAX_MAGNITUDE,
            "epoch_proper_motion_year": EPOCH_YEAR,
        },
        "generators": {
            "cedar-solve": package_version("cedar-solve"),
            "tetra3rs": package_version("tetra3rs"),
        },
        "inputs": {
            name: {"path": str(p), "sha256": sha256_of(p)}
            for name, p in inputs.items()
        },
        "outputs": {
            name: {
                "file": p.name,
                "size_bytes": p.stat().st_size,
                "sha256": sha256_of(p),
            }
            for name, p in outputs.items()
        },
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote {manifest_path}")
    return manifest_path


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--output-dir", default="databases",
                    help="Output directory (default: databases)")
    ap.add_argument("--hip-catalog", default=str(DEFAULT_HIP_CATALOG),
                    help="Path to hip_main.dat or .dat.gz "
                         "(default: data/hip_main.dat.gz)")
    ap.add_argument("--gaia-catalog", default=str(DEFAULT_GAIA_CATALOG),
                    help="Path to merged Gaia binary catalog "
                         "(default: data/gaia_hipp_merged.bin)")
    ap.add_argument("--skip-cedar-solve", action="store_true",
                    help="Skip cedar-solve .npz generation")
    ap.add_argument("--skip-tetra3rs", action="store_true",
                    help="Skip tetra3rs .bin generation")
    args = ap.parse_args()

    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    inputs: dict[str, pathlib.Path] = {}
    outputs: dict[str, pathlib.Path] = {}

    if not args.skip_cedar_solve:
        hip_src = pathlib.Path(args.hip_catalog)
        if not hip_src.exists():
            errors.append(f"cedar-solve: hip catalog not found: {hip_src}")
        else:
            inputs["hip_main"] = hip_src
            try:
                hip_catalog = resolve_hip_catalog(hip_src, output_dir)
                outputs["cedar_solve"] = generate_cedar_solve(output_dir, hip_catalog)
            except Exception as exc:
                print(f"ERROR generating cedar-solve database: {exc}", file=sys.stderr)
                errors.append(f"cedar-solve: {exc}")

    if not args.skip_tetra3rs:
        gaia_catalog = pathlib.Path(args.gaia_catalog)
        if not gaia_catalog.exists():
            errors.append(f"tetra3rs: gaia catalog not found: {gaia_catalog}")
        else:
            inputs["gaia_hipp_merged"] = gaia_catalog
            try:
                outputs["tetra3rs"] = generate_tetra3rs(output_dir, gaia_catalog)
            except Exception as exc:
                print(f"ERROR generating tetra3rs database: {exc}", file=sys.stderr)
                errors.append(f"tetra3rs: {exc}")

    if outputs:
        write_manifest(output_dir, inputs, outputs)

    if errors:
        print("\nErrors:", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        sys.exit(1)

    print("\nDatabases:")
    for p in sorted(outputs.values()):
        print(f"  {p.name}  ({p.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
