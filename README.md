# astro_databases

Star catalog data and generation pipeline for the Pi Zero 2W electronic
finder. Source catalogs are committed under `data/`; generated solver
databases are published as assets on tagged GitHub releases — they are
**not** committed to git.

## Layout

| Path | Contents |
|------|----------|
| `data/` | Committed source catalogs (see provenance below) |
| `scripts/generate_databases.py` | Builds both solver databases + `manifest.json` |
| `.github/workflows/build-databases.yml` | CI: builds and attaches results to a release |

## Generated databases

Both cover 10.5°–14° FOV, `star_max_magnitude=8.0`, proper-motion epoch 2026.0:

| Asset | Solver | Built from |
|-------|--------|-----------|
| `cedar_solve_13deg.npz` | cedar-solve / olive-solve | `data/hip_main.dat.gz` |
| `tetra3rs_13deg.bin` | tetra3rs | `data/gaia_hipp_merged.bin` |
| `manifest.json` | — | Generation parameters, input/output SHA-256s, generator versions |

## Releasing

Tag and push; CI does the rest:

```bash
git tag v2026.06 && git push origin v2026.06
```

The workflow can also be run manually (Actions → Build Databases) to test
generation without publishing, or with an explicit tag to (re)publish.
Generation needs no network beyond installing the generator packages —
all catalog inputs are in `data/`.

## Vendoring from other repos

```bash
gh release download v2026.06 --repo mconsidine/astro_databases --pattern '*.npz'
# or pin by URL:
curl -fsSLO https://github.com/mconsidine/astro_databases/releases/download/v2026.06/tetra3rs_13deg.bin
```

Verify against the `sha256` entries in the release's `manifest.json`.

Note: the `.bin` database format is tied to the tetra3rs version that
generated it. The manifest records that version; regenerate (new tag)
when upgrading tetra3rs on-device.

## Local generation

```bash
pip install numpy tetra3rs "git+https://github.com/mconsidine/cedar-solve.git"
python scripts/generate_databases.py --output-dir databases
```

## Data provenance (`data/`)

**`hip_main.dat.gz`** — I/239 The Hipparcos and Tycho Catalogues (ESA 1997).
https://cdsarc.cds.unistra.fr/ftp/cats/I/239/

**`hip2.dat.gz`** — I/311 Hipparcos, the New Reduction (van Leeuwen, 2007).
Astron. Astrophys. 474, 653. https://cdsarc.cds.unistra.fr/ftp/cats/I/311/
(Kept as a mirror; not currently used by the generation script.)

**`gaia_hipp_merged.bin`, `gaia_hipp_merged.csv`** — Gaia DR3 merged with
Hipparcos for bright stars (G < 4), 63,491 stars to G ≈ 8.0, created via
https://github.com/ssmichael1/tetra3rs/blob/main/scripts/download_gaia_catalog.py
The `.bin` is the compact binary form consumed by
`tetra3rs.SolverDatabase.generate_from_gaia(catalog_path=...)`; the `.csv`
is the same data in readable form.
