"""Refresh the vendored SkyPortal reference data.

Populates the repo's ``sncosmo/`` and ``dustmaps/`` trees from the canonical
upstream sources:

  * sncosmo bandpasses + reference spectra (fetched from SVO et al. via sncosmo)
  * sncosmo SED model templates           (unless --no-models)
  * the Schlegel-Finkbeiner-Davis dust map (via dustmaps.sfd.fetch)

Upstream hosts (SVO especially) are flaky, so each fetch is retried; the set of
failures rotates between attempts, which is why we retry the *misses* rather
than the whole list. Run this from anywhere — paths are resolved relative to the
repository root, not the working directory.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SNCOSMO_DIR = REPO_ROOT / "sncosmo"
DUSTMAP_DIR = REPO_ROOT / "dustmaps"

# SVO is flaky; the failing set rotates, so retry only the misses each round.
DEFAULT_ATTEMPTS = int(os.environ.get("REFRESH_ATTEMPTS", "5"))


def _warm(fetch, names: list[str], kind: str) -> list[str]:
    """Try ``fetch(name)`` for each name; return the names that still failed."""
    failed: list[str] = []
    for name in names:
        try:
            fetch(name)
        except Exception as e:  # noqa: BLE001 - upstream raises a zoo of errors
            print(f"  skip {kind} {name}: {e}", file=sys.stderr)
            failed.append(name)
    return failed


def _warm_with_retries(fetch, names: list[str], kind: str, attempts: int) -> None:
    failed = list(names)
    for i in range(1, attempts + 1):
        if not failed:
            break
        print(f"Warming {kind} attempt {i}/{attempts}: {len(failed)} remaining")
        failed = _warm(fetch, failed, kind)
    cached = len(names) - len(failed)
    print(f"{kind}: {cached}/{len(names)} cached, {len(failed)} skipped")


def refresh_sncosmo(attempts: int, include_models: bool) -> None:
    import sncosmo
    from sncosmo.bandpasses import _BANDPASSES

    # Relocate sncosmo's cache into the repo so downloads land in ./sncosmo.
    SNCOSMO_DIR.mkdir(parents=True, exist_ok=True)
    sncosmo.conf.data_dir = str(SNCOSMO_DIR)

    bandpasses = [m["name"] for m in _BANDPASSES.get_loaders_metadata() if m.get("name")]
    _warm_with_retries(sncosmo.get_bandpass, bandpasses, "bandpass", attempts)

    if include_models:
        from sncosmo.models import _SOURCES

        sources = [m["name"] for m in _SOURCES.get_loaders_metadata() if m.get("name")]
        _warm_with_retries(sncosmo.get_source, sources, "model", attempts)


def refresh_dustmaps(attempts: int) -> None:
    sfd_dir = DUSTMAP_DIR / "sfd"
    sfd_dir.mkdir(parents=True, exist_ok=True)

    from dustmaps.config import config

    config["data_dir"] = str(DUSTMAP_DIR)

    import dustmaps.sfd

    required = ["sfd/SFD_dust_4096_ngp.fits", "sfd/SFD_dust_4096_sgp.fits"]
    if all((DUSTMAP_DIR / f).is_file() for f in required):
        print("dustmaps SFD: already present")
        return
    for i in range(1, attempts + 1):
        try:
            dustmaps.sfd.fetch()
            print("dustmaps SFD: fetched")
            return
        except Exception as e:  # noqa: BLE001
            print(f"  dustmaps SFD attempt {i}/{attempts} failed: {e}", file=sys.stderr)
    print("dustmaps SFD: FAILED after retries", file=sys.stderr)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--no-models", action="store_true", help="skip sncosmo SED model templates")
    p.add_argument("--no-dust", action="store_true", help="skip the SFD dust map")
    p.add_argument("--attempts", type=int, default=DEFAULT_ATTEMPTS)
    args = p.parse_args()

    refresh_sncosmo(args.attempts, include_models=not args.no_models)
    if not args.no_dust:
        refresh_dustmaps(args.attempts)


if __name__ == "__main__":
    main()
