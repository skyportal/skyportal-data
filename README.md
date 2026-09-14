# skyportal-data

Pre-fetched external reference data that SkyPortal needs at startup, vendored so
instances don't depend on flaky upstream hosts (notably the SVO Filter Profile
Service).

SkyPortal's photometry API builds a bandpass → colour / wavelength map *at module
import* over every `ALLOWED_BANDPASSES`. For any bandpass not already cached,
`sncosmo` blocks on a network fetch to SVO. When SVO is slow or down, those
fetches stack up and push app start past the health-check window — in CI this
shows up as the server never coming up (HTTP 503). The SFD dustmap has the same
"blocks import on a cold cache" problem. This repo removes the runtime network
dependency entirely by shipping the data.

## Contents

| Path | What | Size | Storage |
|------|------|------|---------|
| `sncosmo/bandpasses/` | sncosmo bandpass transmission curves (ex-SVO etc.) | ~30 MB | plain git |
| `sncosmo/spectra/`    | reference spectra (e.g. Vega) | ~0.2 MB | plain git |
| `sncosmo/models/`     | sncosmo SED model templates (Hsiao, SALT2/3, Nugent, …) | ~322 MB | plain git |
| `dustmaps/sfd/`       | Schlegel-Finkbeiner-Davis (SFD) dust maps | ~128 MB | plain git |

`sncosmo/models/` covers every sncosmo source except most of the `vincenzi`,
`mlcs2k2` and `whalen` families (~690 MB), left out on purpose: they are niche
and would more than double the repo. A fit against one of those still falls back
to a network fetch.

The directory layout mirrors the on-disk cache locations the consumers expect:

- `sncosmo/` maps to the sncosmo cache dir (`sncosmo.conf.data_dir`, default
  `~/.astropy/cache/sncosmo`).
- `dustmaps/` maps to the dustmaps `data_dir`.

## Storage

Everything is a plain git blob. Git LFS was dropped: the shared bandwidth budget
ran out and blocked submodule checkouts in CI, and every file here is under
GitHub's 100 MB per-file limit. The trade-off is a ~480 MB clone.

```bash
git clone https://github.com/skyportal/skyportal-data.git
```

A consumer that only needs the bandpasses (the common case, and the flaky one)
can skip the bulk with a partial, sparse clone:

```bash
git clone --filter=blob:none --sparse https://github.com/skyportal/skyportal-data.git
git -C skyportal-data sparse-checkout set sncosmo/bandpasses sncosmo/spectra
```

## Consuming as a submodule

```bash
git submodule add https://github.com/skyportal/skyportal-data.git skyportal-data
git -C skyportal-data checkout <tag-or-sha>   # pin for reproducibility
```

Then point the libraries at the checked-out data:

```python
import sncosmo
sncosmo.conf.data_dir = "<repo>/skyportal-data/sncosmo"

from dustmaps.config import config
config["data_dir"] = "<repo>/skyportal-data/dustmaps"
```

…or, in CI, copy the trees into the default cache locations:

```bash
mkdir -p ~/.astropy/cache/sncosmo
cp -a skyportal-data/sncosmo/. ~/.astropy/cache/sncosmo/
```

## Refreshing the data

`tools/refresh.py` regenerates everything from the canonical upstream sources
(SVO via sncosmo, the dustmaps SFD mirror).

```bash
python tools/refresh.py            # warm everything into ./sncosmo and ./dustmaps
python tools/refresh.py --no-models # skip the large SED templates
```

Upstream fetches fail often enough that a missing SED template is tolerated, but
a missing *bandpass* is not: those load at consumer import time, so the script
exits 2 and lists them.

[`.github/workflows/refresh.yml`](.github/workflows/refresh.yml) runs it weekly
with `--no-models`, pushes any change to the single `refresh/data` branch and
opens one PR, reusing it on later runs. Tick `include_models` on a manual run to
refresh the SED templates too, and drop the families listed above from the diff
before merging.

Filter transmission curves are effectively static reference data, so refreshes
are driven by *new* filters appearing upstream (a sncosmo version bump) rather
than a fast clock — the scheduled run is a low-frequency backstop.
