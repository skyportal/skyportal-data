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
| `sncosmo/models/`     | sncosmo SED model templates (Hsiao, SALT2/3, Nugent, …) | ~112 MB | **Git LFS** |
| `dustmaps/sfd/`       | Schlegel-Finkbeiner-Davis (SFD) dust maps | ~128 MB | **Git LFS** |

The directory layout mirrors the on-disk cache locations the consumers expect:

- `sncosmo/` maps to the sncosmo cache dir (`sncosmo.conf.data_dir`, default
  `~/.astropy/cache/sncosmo`).
- `dustmaps/` maps to the dustmaps `data_dir`.

## Git LFS

The large binaries (`sncosmo/models/**`, `dustmaps/**`) are tracked with
[Git LFS](https://git-lfs.com/). To clone with the data:

```bash
git lfs install
git clone https://github.com/skyportal/skyportal-data.git
```

The small, diff-friendly bandpass curves are intentionally **not** in LFS, so a
consumer that only needs bandpasses (the common case — that's the flaky one) can
skip the LFS download entirely:

```bash
GIT_LFS_SKIP_SMUDGE=1 git submodule update --init skyportal-data
# -> bandpasses present (plain git), models/dust are lightweight LFS pointers
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
(SVO via sncosmo, the dustmaps SFD mirror). It is run on a schedule by
[`.github/workflows/refresh.yml`](.github/workflows/refresh.yml), which opens a
PR only when the data actually changes.

```bash
python tools/refresh.py            # warm everything into ./sncosmo and ./dustmaps
python tools/refresh.py --no-models # skip the large SED templates
```

Filter transmission curves are effectively static reference data, so refreshes
are driven by *new* filters appearing upstream (a sncosmo version bump) rather
than a fast clock — the scheduled run is a low-frequency backstop.
