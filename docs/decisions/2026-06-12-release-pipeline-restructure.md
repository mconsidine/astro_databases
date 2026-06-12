# Decision record — release-pipeline restructure across the eFinder repos

- **Date:** 2026-06-12T14:47Z (session spanned 2026-06-10 — 2026-06-12)
- **Session:** Claude Code session "pensive-allen", ID `session_01MBjXhx3TLxkk3WEkvHWqRX`
  (https://claude.ai/code/session_01MBjXhx3TLxkk3WEkvHWqRX), working branches `claude/pensive-allen-q5iis1`
- **Repositories affected:** astro_databases, diofinder, olive-solve, sycamore-extract, tetra3rs
  (plus user-applied changes to the cedar-solve fork)

## Changes in this repository (astro_databases)

**Role after this session:** catalog data + database generation + tagged-release publishing. The single
source of star data for the whole system.

- Restructured: source catalogs moved to `data/`; committed wheel artifacts (`databases-latest/`) and the
  800-line multi-repo `manual_build.yml` removed (`e86e707`).
- New `build-databases.yml`: a `v*` tag builds both databases and attaches them plus `manifest.json`
  (parameters, input/output SHA-256s, generator versions) to a GitHub release; manual dispatch builds an
  artifact without publishing.
- `generate_databases.py` fixed against the real cedar-solve API: `max_fov`/`min_fov` (the original
  `fov_range=`/`catalog=` parameters never existed), `Tetra3(load_database=None)`, `save_as` passed as a
  `pathlib.Path` (a `str` is treated as a name inside cedar-solve's package data dir) (`580a740`, `3cb8629`).
- cedar-solve installed via `uv pip install --override` to neutralize stale dependency ceilings
  (Pillow<9 etc.) while still resolving future upstream deps (`18c98ff`); the user later removed the
  ceilings in the cedar-solve fork itself and bumped its version 0.5.1 → 0.6.0.
- New `scripts/gaia_to_hip.py`: converts `gaia_hipp_merged.csv` into committed
  `data/gaia_hip_main.dat.gz` — hip_main pipe format that stock esa/tetra3, cedar-solve, and olive-solve
  parse unmodified. De-propagates positions 2016.0 → 1991.25 with Gaia PMs; writes 0.0 for the 912
  missing-PM rows (blank would drop 86 of the 704 brightest stars); synthetic row-number IDs (`995c384`).
- The Gaia catalog became the default `.npz` source: 63,154 stars kept at G ≤ 8.0 vs 41,394 (V ≤ 8.0)
  from hip_main; `--hip-catalog data/hip_main.dat.gz` keeps the Hipparcos path.
- tetra3rs database built from the mconsidine fork (`tetra3rs-ref` dispatch input / `TETRA3RS_REF` var;
  default `main` tracks upstream, so left alone the result equals a PyPI install) (`deee9a7`).
- Validated by three green dispatch runs; first release **v2026.06** published with
  `cedar_solve_13deg.npz` (13.3 MB), `tetra3rs_13deg.bin` (25.0 MB), `manifest.json`.
- *Adjacent post-session work (not part of this record):* a "deep" G ≤ 8.5 database variant
  (`--variant deep`, `*_mag85` outputs from a locally generated G ≤ 9.0 catalog) was added on main.

## Session narrative and key decisions

1. **astro_databases assessed, then narrowed to its name** — the repo had ~52 MB of committed binaries,
   a single failed CI run, a workflow depending on a release and a sibling workflow that never existed,
   and a generation script written against an imagined cedar-solve API (`fov_range=`) that had never
   executed. Decision: data + generation + tagged releases only; the five foreign wheel-build jobs were
   dropped in favor of per-repo workflows.
2. **GitHub releases over going offline** — release assets don't count against repo quotas (2 GB/file)
   and Actions is free for public repos, so the contemplated local/'act' pipeline was unnecessary;
   'act' was specifically recommended against (token still required, runner-image drift, no benefit
   over a plain script).
3. **Tagged, immutable, manifest-verified releases as the vendoring contract** — every database release
   carries `manifest.json` (parameters, input/output SHA-256s, generator versions); consumers verify
   hashes at fetch time.
4. **One star list for everything** — the merged Gaia DR3 + Hipparcos catalog (63,491 stars to G ≈ 8.0)
   feeds both database formats. A ~100-line converter (`gaia_to_hip.py`) reformats it into hip_main
   layout so stock esa/tetra3, cedar-solve, and olive-solve parse it **unmodified** — upstream
   compatibility preserved with zero solver patches. Verified: identical pattern counts vs hip_main
   with substantially denser lattice fields (min field depth 26 → 35 stars), `.npz` cost only ~0.5 MB.
5. **Per-repo wheel workflows, not an aggregator repo** — build config lives next to the code it
   builds; the old aggregator's pathologies (cross-repo SHA bookkeeping, drifting build configs) are
   structurally avoided. diofinder pulls from three release URLs instead of one.
6. **diofinder pulls everything at build time** — no binaries in git; `vendor/wheels/` survives only as
   a gitignored staging dir so `install.sh`/chroot flow stayed untouched. OTA (`efinder-update`)
   refreshes wheels from latest releases, deliberately non-fatally.
7. **Branch-testing without fleet risk** — hyphenated tags (e.g. `v0.2.0-noext`) publish as
   prereleases everywhere, invisible to "latest"-following consumers; selected explicitly via dispatch
   inputs or repo variables.
8. **Identity clarifications** — three codebases answer to `tetra3`: cedar-solve (Python; generates the
   `.npz` in CI only), olive-solve (Rust; the wheel *named* tetra3 that does all on-device solving),
   and upstream esa/tetra3 (custom-FOV fallback only). cedar-detect and cedar-solve do not overlap:
   they are the extract/solve halves of the Cedar design, mirrored here by sycamore / olive-solve.

## Assessments performed

- Initial astro_databases audit (broken paths, phantom dependencies, dead API calls — all documented in
  commit messages).
- Catalog compatibility: committed `gaia_hipp_merged.bin` header (`GDR3` v1, 63,491 stars) matches the
  current tetra3rs parser; G-band depth exactly 8.01; converter output survives the exact hip_main
  parser logic 63,491/63,491.
- olive-solve loader verified to support the cedar-solve `.npz` schema (828-byte props branch) —
  basis for `efinder-db-update` on existing devices.
- Database A/B (hip vs Gaia): 41,394 → 63,154 stars kept; patterns ~950k in both (capped); lattice
  field density up ~20–30%; `cedar_solve_13deg.npz` 13.3 MB.
- Post-release audit of the first green diofinder image (v0.0.24, first build): found it had silently
  shipped **without** the sycamore extractor (abi3 wheel name vs cp313 fetch pattern) — fixed and
  rebuilt; the second v0.0.24 build verified complete.

## Outstanding recommendations

- **olive-solve `main` lags `olive-solve-noext`** (extractor feature-gate, rayon perf work, release
  workflow). Either declare noext the trunk or merge it into main before they drift further.
- **GitHub Actions Node 20 deprecation:** runners force Node 24 from 2026-06-16; the workflows use
  actions/checkout@v4, setup-python@v5, upload-artifact@v4 — bump majors when convenient.
- **cedar-solve fork hygiene:** the fork now carries relaxed dependency floors and version 0.6.0;
  re-apply/verify on future upstream syncs. The uv `--override` in build-databases.yml remains as a
  safety net.
- **tetra3rs `.bin` format coupling:** the database format is tied to the generating tetra3rs version
  (recorded in the manifest). Regenerate + retag astro_databases when upgrading tetra3rs on a device;
  use `TETRA3RS_REF` if the fork diverges.
- **Derived-file discipline:** rerun `scripts/gaia_to_hip.py` whenever `gaia_hipp_merged.csv` changes
  (deterministic, byte-identical output for unchanged input).
- **Existing devices** get the new database via `sudo efinder-db-update [tag]` (after an OTA update
  delivers the script) or the documented curl one-liner against
  `releases/latest/download/cedar_solve_13deg.npz`.
