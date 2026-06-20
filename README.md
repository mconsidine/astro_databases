# astro_databases

Star catalog data and generation pipeline for the Pi Zero 2W electronic
finder. Source catalogs are committed under `data/`; generated solver
databases are published as assets on tagged GitHub releases — they are
**not** committed to git.

## Layout

| Path | Contents |
|------|----------|
| `data/` | Committed source catalogs (see provenance below) |
| `scripts/generate_databases.py` | Builds solver databases + `manifest.json` |
| `scripts/gaia_to_hip.py` | Converts `gaia_hipp_merged.csv` → `gaia_hip_main.dat.gz` |
| `scripts/build_star_names.py` | Builds `data/star_names.csv` (brightest-star labels) from HYG |
| `.github/workflows/build-databases.yml` | CI: builds and attaches results to a release |

## Generated databases

### Standard build (G ≤ 8.0)

Both cover 10.5°–14° FOV, `star_max_magnitude=8.0`, proper-motion epoch
2026.0, and are built from the **same merged Gaia DR3 + Hipparcos star
list** (63,491 stars to G = 8.0):

| Asset | Solver | Built from |
|-------|--------|-----------|
| `diofinder_13deg.npz` | cedar-solve / olive-solve | `data/gaia_hip_main.dat.gz` |
| `tetra3rs_13deg.bin` | tetra3rs | `data/gaia_hipp_merged.bin` |
| `manifest.json` | — | Generation parameters, input/output SHA-256s, generator versions |

### Deep build (G ≤ 8.5)

For poor-transparency nights.  Same FOV range, magnitude limit raised to 8.5.
Built from a deeper source catalog (G ≤ 9.0) that is **not** committed to git
because of its size; see [Regenerating the deep source catalog](#regenerating-the-deep-source-catalog) below.

| Asset | Solver | Built from |
|-------|--------|-----------|
| `diofinder_13deg_mag85.npz` | cedar-solve / olive-solve | `data/gaia_hipp_merged_mag90.dat.gz` |
| `tetra3rs_13deg_mag85.bin` | tetra3rs | `data/gaia_hipp_merged_mag90.bin` |

The deep files are attached to releases whenever the deeper source catalog is
present at build time.  If absent, the CI step logs an INFO message and skips
the deep build without failing.

**Consumer (diofinder):** load the deep `.npz` via the `star_db_deep` config
key in `/etc/efinder/efinder.conf`.  When `star_db_deep` is set, the solver
falls back to it automatically on nights where the standard database yields
no solution.

To build the `.npz` from the original Hipparcos catalog instead (41,394
stars to V = 8.0), pass `--hip-catalog data/hip_main.dat.gz` to the
generation script.

## Releasing

Tag and push; CI does the rest:

```bash
git tag v2026.06 && git push origin v2026.06
```

The workflow can also be run manually (Actions → Build Databases) to test
generation without publishing, or with an explicit tag to (re)publish.
Generation needs no network beyond installing the generator packages —
all standard catalog inputs are in `data/`.

## Vendoring from other repos

```bash
# Standard database
gh release download v2026.06 --repo mconsidine/astro_databases --pattern '*.npz'

# Deep database (if included in that release)
gh release download v2026.06 --repo mconsidine/astro_databases \
  --pattern '*_mag85.*'

# Or pin by URL:
curl -fsSLO https://github.com/mconsidine/astro_databases/releases/download/v2026.06/tetra3rs_13deg.bin
curl -fsSLO https://github.com/mconsidine/astro_databases/releases/download/v2026.06/tetra3rs_13deg_mag85.bin
```

Verify against the `sha256` entries in the release's `manifest.json`.

Note: the `.bin` database format is tied to the tetra3rs version that
generated it. The manifest records that version; regenerate (new tag)
when upgrading tetra3rs on-device.

## Local generation

```bash
pip install numpy tetra3rs "git+https://github.com/mconsidine/cedar-solve.git"

# Standard build (G ≤ 8.0):
python scripts/generate_databases.py --output-dir databases

# Deep build only (G ≤ 8.5, requires deeper source catalog — see below):
python scripts/generate_databases.py --variant deep --output-dir databases

# Both in one pass (deep silently skipped if deeper catalog absent):
python scripts/generate_databases.py --all-variants --output-dir databases

# Explicit magnitude:
python scripts/generate_databases.py --max-magnitude 8.5 --output-dir databases
```

## Regenerating the deep source catalog

The deep build requires a merged Gaia DR3 + Hipparcos catalog at G ≤ 9.0
(roughly ~130 k stars).  This is too large to commit to git; generate it
once locally and then the deep build will pick it up automatically.

**Prerequisites:**

```bash
pip install astroquery astropy numpy
# hip2.dat is already in data/ as hip2.dat.gz — decompress it first:
gunzip -k data/hip2.dat.gz      # produces data/hip2.dat (keeps the .gz)
```

**Download and merge (queries the ESA Gaia TAP service — requires network):**

```bash
# From the repo root.  Writes both the .bin (for tetra3rs) and .csv forms.
# scripts/download_gaia_catalog.py is a copy of the upstream script at
# https://github.com/ssmichael1/tetra3rs/blob/main/scripts/download_gaia_catalog.py
python scripts/download_gaia_catalog.py \
    --mag-limit 9.0 \
    --hip2 data/hip2.dat \
    --output data/gaia_hipp_merged_mag90.bin

python scripts/download_gaia_catalog.py \
    --mag-limit 9.0 \
    --hip2 data/hip2.dat \
    --output data/gaia_hipp_merged_mag90.csv
```

**Convert to hip_main format for cedar-solve:**

```bash
python scripts/gaia_to_hip.py \
    --src data/gaia_hipp_merged_mag90.csv \
    --dest data/gaia_hipp_merged_mag90.dat.gz
```

After running both commands, `python scripts/generate_databases.py --variant deep`
will succeed without network access.

## Data provenance (`data/`)

**`hip_main.dat.gz`** — I/239 The Hipparcos and Tycho Catalogues (ESA 1997).
https://cdsarc.cds.unistra.fr/ftp/cats/I/239/

**`hip2.dat.gz`** — I/311 Hipparcos, the New Reduction (van Leeuwen, 2007).
Astron. Astrophys. 474, 653. https://cdsarc.cds.unistra.fr/ftp/cats/I/311/

**`star_names.csv`** — compact brightest-star naming table (15,567 stars to
mag 7.0): `ra_deg, dec_deg, mag, name, desig`. Built from the HYG database
(Hipparcos + Yale BSC + Gliese; https://github.com/astronexus/HYG-Database) by
`scripts/build_star_names.py`, which downloads HYG, trims to the magnitude
limit, and formats proper / Bayer (α Tau) / Flamsteed (87 Tau) / HR / HIP
labels. Regenerate with `python scripts/build_star_names.py`. Attached to each
release (and SHA-recorded in `manifest.json`) so the eFinder can label the
brightest star in a solved field; not tied to a specific solver database.

**`gaia_hipp_merged.bin`, `gaia_hipp_merged.csv`** — Gaia DR3 merged with
Hipparcos for bright stars (G < 4), 63,491 stars to G ≈ 8.0, created via
https://github.com/ssmichael1/tetra3rs/blob/main/scripts/download_gaia_catalog.py
The `.bin` is the compact binary form consumed by
`tetra3rs.SolverDatabase.generate_from_gaia(catalog_path=...)`; the `.csv`
is the same data in readable form.

**`gaia_hip_main.dat.gz`** — the Gaia merge above, reformatted into the
hip_main pipe-delimited layout so that stock esa/tetra3, cedar-solve, and
olive-solve consume it unmodified. Derived file: regenerate with
`python scripts/gaia_to_hip.py` whenever `gaia_hipp_merged.csv` changes.
Positions are de-propagated from Gaia's 2016.0 epoch to the parsers'
assumed 1991.25; magnitudes are Gaia G band; star IDs are synthetic row
numbers, **not** HIP numbers. See the script docstring for details.

**`gaia_hipp_merged_mag90.bin`, `gaia_hipp_merged_mag90.csv`** *(not committed)*
— same format as `gaia_hipp_merged.{bin,csv}` but extended to G ≤ 9.0
(~130 k stars). Required for the deep build. Generate locally; see
[Regenerating the deep source catalog](#regenerating-the-deep-source-catalog).

**`gaia_hipp_merged_mag90.dat.gz`** *(not committed)* — hip_main format of
the G ≤ 9.0 catalog; derived from the `.csv` by `scripts/gaia_to_hip.py`.
