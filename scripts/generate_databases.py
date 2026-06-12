#!/usr/bin/env python3
"""
Generate star catalog databases for the Pi Zero 2W finder.

Two formats are produced, both from the same merged Gaia DR3 + Hipparcos
star list:
  cedar_solve_13deg.npz      -- cedar-solve / olive-solve (.npz, from
                                data/gaia_hip_main.dat.gz — hip_main-format
                                file derived from the Gaia merge by
                                scripts/gaia_to_hip.py)
  tetra3rs_13deg.bin         -- tetra3rs (.bin, from data/gaia_hipp_merged.bin)

A "deep" variant for poor-transparency nights (mag limit 8.5 instead of 8.0)
can be built with --variant deep or --max-magnitude 8.5.  It requires a deeper
source catalog (G ≤ 9.0) in data/gaia_hipp_merged_mag90.{bin,csv} and
data/gaia_hipp_merged_mag90.dat.gz (hip_main format).  See README.md for how
to generate that catalog.  When the deep catalog files are present the deep
variant produces:
  cedar_solve_13deg_mag85.npz
  tetra3rs_13deg_mag85.bin

Pass --hip-catalog data/hip_main.dat.gz to build the .npz from the original
Hipparcos catalog instead (41,394 stars to V = 8.0).

Both databases cover 10.5°-14° FOV. All catalog inputs are committed (or
manually generated, for the deep catalog) under data/ — no network access is
required for generation.

A manifest.json is written alongside the databases recording generation
parameters, input/output SHA-256 hashes, and generator package versions.

Usage:
  # Standard build (G ≤ 8.0):
  python generate_databases.py [--output-dir DIR]
                               [--hip-catalog PATH] [--gaia-catalog PATH]
                               [--skip-cedar-solve] [--skip-tetra3rs]

  # Deep build (G ≤ 8.5):
  python generate_databases.py --variant deep [--output-dir DIR]

  # Explicit magnitude (any value):
  python generate_databases.py --max-magnitude 8.5 [--output-dir DIR]

  # Build both standard and deep in one pass:
  python generate_databases.py --all-variants [--output-dir DIR]
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
EPOCH_YEAR = 2026.0

# Default magnitude for the standard build.
DEFAULT_MAGNITUDE = 8.0

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_HIP_CATALOG = REPO_ROOT / "data" / "gaia_hip_main.dat.gz"
DEFAULT_GAIA_CATALOG = REPO_ROOT / "data" / "gaia_hipp_merged.bin"

# Deeper source catalog paths for deep/custom magnitude builds.
# Generated via scripts/download_gaia_catalog.py --mag-limit 9.0; see README.
DEEP_HIP_CATALOG = REPO_ROOT / "data" / "gaia_hipp_merged_mag90.dat.gz"
DEEP_GAIA_CATALOG = REPO_ROOT / "data" / "gaia_hipp_merged_mag90.bin"


def _magnitude_suffix(max_magnitude: float) -> str:
    """Return output-file suffix for a given magnitude limit.

    8.0 → '' (no suffix, keeps existing filenames byte-identical)
    8.5 → '_mag85'
    9.0 → '_mag90'
    """
    if max_magnitude == DEFAULT_MAGNITUDE:
        return ""
    # Format: drop the decimal point (8.5 → "85", 9.0 → "90")
    digits = f"{max_magnitude:.1f}".replace(".", "")
    return f"_mag{digits}"


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
        # Use a name that encodes the source file stem to avoid collisions when
        # both the standard and deep catalogs are decompressed in the same run.
        stem = path.stem  # e.g. "gaia_hip_main.dat" → base after stripping .gz
        dest = output_dir / stem
        if not dest.exists():
            print(f"Decompressing {path} → {dest}")
            with gzip.open(path, "rb") as gz, open(dest, "wb") as out:
                shutil.copyfileobj(gz, out)
        return dest
    return path


def generate_cedar_solve(
    output_dir: pathlib.Path,
    hip_catalog: pathlib.Path,
    max_magnitude: float,
) -> pathlib.Path:
    import tetra3 as t3_mod

    # cedar-solve only loads the hip catalog from its own package directory
    tetra3_pkg = pathlib.Path(t3_mod.__file__).parent
    hip_dest = tetra3_pkg / "hip_main.dat"
    if hip_dest.resolve() != hip_catalog.resolve():
        shutil.copy(hip_catalog, hip_dest)
        print(f"  Copied hip_main.dat → {hip_dest}")

    suffix = _magnitude_suffix(max_magnitude)
    db_stem = output_dir / f"cedar_solve_13deg{suffix}"
    print(f"Generating cedar-solve database → {db_stem}.npz")
    print(f"  max_fov={FOV_MAX}, min_fov={FOV_MIN}, star_max_magnitude={max_magnitude}")

    # save_as must be a pathlib.Path: cedar-solve treats a str as a file
    # name inside its own package data directory
    t3 = t3_mod.Tetra3(load_database=None)
    t3.generate_database(
        save_as=db_stem.resolve(),
        max_fov=FOV_MAX,
        min_fov=FOV_MIN,
        star_max_magnitude=max_magnitude,
        star_catalog="hip_main",
        epoch_proper_motion=EPOCH_YEAR,
    )
    result = pathlib.Path(str(db_stem) + ".npz")
    print(f"  Done: {result.stat().st_size / 1e6:.1f} MB")
    return result


def generate_tetra3rs(
    output_dir: pathlib.Path,
    gaia_catalog: pathlib.Path,
    max_magnitude: float,
) -> pathlib.Path:
    import tetra3rs

    suffix = _magnitude_suffix(max_magnitude)
    db_path = output_dir / f"tetra3rs_13deg{suffix}.bin"
    print(f"Generating tetra3rs database → {db_path}")
    print(f"  fov=[{FOV_MIN}, {FOV_MAX}], star_max_magnitude={max_magnitude}")
    print(f"  catalog: {gaia_catalog}")

    db = tetra3rs.SolverDatabase.generate_from_gaia(
        max_fov_deg=FOV_MAX,
        min_fov_deg=FOV_MIN,
        star_max_magnitude=max_magnitude,
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
    extra_parameters: dict | None = None,
) -> pathlib.Path:
    parameters: dict = {
        "fov_min_deg": FOV_MIN,
        "fov_max_deg": FOV_MAX,
        "epoch_proper_motion_year": EPOCH_YEAR,
    }
    if extra_parameters:
        parameters.update(extra_parameters)

    manifest = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "repo_commit": git_head(),
        "parameters": parameters,
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


def _select_catalogs(
    max_magnitude: float,
    hip_catalog_override: str | None,
    gaia_catalog_override: str | None,
) -> tuple[pathlib.Path, pathlib.Path]:
    """Return (hip_catalog, gaia_catalog) paths for the requested magnitude.

    For the standard magnitude (8.0) the committed catalogs are used unless
    overridden.  For any other magnitude the deep catalogs are required; an
    explicit override still takes priority.
    """
    if max_magnitude == DEFAULT_MAGNITUDE:
        hip = pathlib.Path(hip_catalog_override) if hip_catalog_override else DEFAULT_HIP_CATALOG
        gaia = pathlib.Path(gaia_catalog_override) if gaia_catalog_override else DEFAULT_GAIA_CATALOG
    else:
        hip = pathlib.Path(hip_catalog_override) if hip_catalog_override else DEEP_HIP_CATALOG
        gaia = pathlib.Path(gaia_catalog_override) if gaia_catalog_override else DEEP_GAIA_CATALOG
    return hip, gaia


def build_variant(
    *,
    max_magnitude: float,
    output_dir: pathlib.Path,
    hip_catalog_override: str | None,
    gaia_catalog_override: str | None,
    skip_cedar_solve: bool,
    skip_tetra3rs: bool,
    allow_missing_deep_catalog: bool = False,
) -> tuple[dict[str, pathlib.Path], dict[str, pathlib.Path], list[str]]:
    """Build one magnitude variant.  Returns (inputs, outputs, errors)."""
    hip_src, gaia_catalog = _select_catalogs(
        max_magnitude, hip_catalog_override, gaia_catalog_override
    )

    errors: list[str] = []
    inputs: dict[str, pathlib.Path] = {}
    outputs: dict[str, pathlib.Path] = {}

    # For non-standard magnitudes, check that the deeper catalog is present.
    # When allow_missing_deep_catalog is True (CI gate) we log and skip rather
    # than error, so the workflow doesn't break before the catalog is committed.
    if max_magnitude != DEFAULT_MAGNITUDE:
        missing = []
        if not skip_cedar_solve and not hip_src.exists():
            missing.append(str(hip_src))
        if not skip_tetra3rs and not gaia_catalog.exists():
            missing.append(str(gaia_catalog))
        if missing:
            msg = (
                f"Deep catalog files not found (skipping deep build): "
                + ", ".join(missing)
                + "  — run scripts/download_gaia_catalog.py --mag-limit 9.0 "
                "to generate them (see README.md)"
            )
            if allow_missing_deep_catalog:
                print(f"INFO: {msg}", file=sys.stderr)
                return inputs, outputs, []
            else:
                for m in missing:
                    errors.append(f"catalog not found: {m}")
                return inputs, outputs, errors

    suffix = _magnitude_suffix(max_magnitude)
    label = f"mag{suffix[1:]}" if suffix else "standard"

    if not skip_cedar_solve:
        if not hip_src.exists():
            errors.append(f"cedar-solve ({label}): hip catalog not found: {hip_src}")
        else:
            inputs[f"hip_catalog{suffix}"] = hip_src
            try:
                hip_catalog = resolve_hip_catalog(hip_src, output_dir)
                outputs[f"cedar_solve{suffix}"] = generate_cedar_solve(
                    output_dir, hip_catalog, max_magnitude
                )
            except Exception as exc:
                print(f"ERROR generating cedar-solve database ({label}): {exc}", file=sys.stderr)
                errors.append(f"cedar-solve ({label}): {exc}")

    if not skip_tetra3rs:
        if not gaia_catalog.exists():
            errors.append(f"tetra3rs ({label}): gaia catalog not found: {gaia_catalog}")
        else:
            inputs[f"gaia_hipp_merged{suffix}"] = gaia_catalog
            try:
                outputs[f"tetra3rs{suffix}"] = generate_tetra3rs(
                    output_dir, gaia_catalog, max_magnitude
                )
            except Exception as exc:
                print(f"ERROR generating tetra3rs database ({label}): {exc}", file=sys.stderr)
                errors.append(f"tetra3rs ({label}): {exc}")

    return inputs, outputs, errors


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--output-dir", default="databases",
                    help="Output directory (default: databases)")
    ap.add_argument("--hip-catalog", default=None,
                    help="Path to a hip_main-format .dat or .dat.gz catalog "
                         "(overrides per-variant default)")
    ap.add_argument("--gaia-catalog", default=None,
                    help="Path to merged Gaia binary catalog "
                         "(overrides per-variant default)")
    ap.add_argument("--skip-cedar-solve", action="store_true",
                    help="Skip cedar-solve .npz generation")
    ap.add_argument("--skip-tetra3rs", action="store_true",
                    help="Skip tetra3rs .bin generation")

    mag_group = ap.add_mutually_exclusive_group()
    mag_group.add_argument(
        "--max-magnitude", type=float, default=None, metavar="MAG",
        help="Star magnitude limit (default: 8.0 for standard build, 8.5 for "
             "--variant deep). Determines output filename suffix.")
    mag_group.add_argument(
        "--variant", choices=["standard", "deep"],
        help="Named variant shortcut: 'standard' = mag 8.0 (default), "
             "'deep' = mag 8.5 (requires data/gaia_hipp_merged_mag90.{bin,dat.gz})")
    ap.add_argument(
        "--all-variants", action="store_true",
        help="Build both standard (8.0) and deep (8.5) variants in one pass. "
             "Deep build is silently skipped if the deeper catalog is absent.")
    ap.add_argument(
        "--allow-missing-deep-catalog", action="store_true",
        help="When building the deep variant, log and skip (instead of erroring) "
             "if the deeper source catalog is absent. Intended for CI use.")

    args = ap.parse_args()

    # Resolve the magnitude(s) to build.
    if args.all_variants:
        magnitudes = [DEFAULT_MAGNITUDE, 8.5]
    elif args.variant == "deep":
        magnitudes = [8.5]
    elif args.variant == "standard" or args.variant is None:
        magnitudes = [DEFAULT_MAGNITUDE if args.max_magnitude is None else args.max_magnitude]
    else:
        magnitudes = [args.max_magnitude]

    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_errors: list[str] = []
    all_inputs: dict[str, pathlib.Path] = {}
    all_outputs: dict[str, pathlib.Path] = {}

    for mag in magnitudes:
        allow_missing = args.allow_missing_deep_catalog or (
            args.all_variants and mag != DEFAULT_MAGNITUDE
        )
        inputs, outputs, errors = build_variant(
            max_magnitude=mag,
            output_dir=output_dir,
            hip_catalog_override=args.hip_catalog,
            gaia_catalog_override=args.gaia_catalog,
            skip_cedar_solve=args.skip_cedar_solve,
            skip_tetra3rs=args.skip_tetra3rs,
            allow_missing_deep_catalog=allow_missing,
        )
        all_inputs.update(inputs)
        all_outputs.update(outputs)
        all_errors.extend(errors)

    if all_outputs:
        # Collect magnitude parameters for manifest.
        extra_params: dict = {}
        if len(magnitudes) == 1:
            extra_params["star_max_magnitude"] = magnitudes[0]
        else:
            extra_params["star_max_magnitude_variants"] = magnitudes
        write_manifest(output_dir, all_inputs, all_outputs, extra_params)

    if all_errors:
        print("\nErrors:", file=sys.stderr)
        for e in all_errors:
            print(f"  {e}", file=sys.stderr)
        sys.exit(1)

    if all_outputs:
        print("\nDatabases:")
        for p in sorted(all_outputs.values()):
            print(f"  {p.name}  ({p.stat().st_size / 1e6:.1f} MB)")
    else:
        print("\nNo databases generated.")


if __name__ == "__main__":
    main()
