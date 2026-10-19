"""Fetch immutable upstream game assets and verify each Git blob before installation.

This module uses only the Python standard library and does not import the Mac runtime.
The manifest comes from the complete Git tree at UPSTREAM_REVISION, not a mutable tag.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
from typing import Callable, Iterable
from urllib.parse import quote
from urllib.request import Request, urlopen

UPSTREAM_REVISION = "f9d808e6e3c60cb65c6e0535fc9fa9eac7e779d3"
UPSTREAM_RAW = "https://raw.githubusercontent.com/ok-oldking/ok-wuthering-waves"
# (repository-relative path, byte count, Git blob SHA-1)
ASSETS: tuple[tuple[str, int, str], ...] = (
    ('assets/coco_annotations.json', 152031, '7f5504b490d3e0b9979bd8673df0a0f36cd34c56'),
    ('assets/echo_model/echo.onnx', 37907104, '9b076c7026dbba4a12fe212f89a1bf7784abb591'),
    ('assets/images/0.png', 588845, '48fb572b4f8c2d93db5ceca65972e685c20987df'),
    ('assets/images/1.png', 281481, 'e8b208104b3afbd8830275d4c5d4cb0d1a9ee7e8'),
    ('assets/images/10.png', 55338, 'c0d4a0310be4990e893be3aff66b47052c4c0ab3'),
    ('assets/images/11.png', 42334, 'ed5818ea5c64bcafb9cbee2c761f9150464b5c2d'),
    ('assets/images/12.png', 65254, 'e938f83de055d30c08d581eb0d489276bd37693a'),
    ('assets/images/13.png', 53666, '5abe5a527f428a91223ff99deff031156846a12b'),
    ('assets/images/14.png', 62145, '325aa6b05fb26b65c3f2f1a22b5a52b578647df8'),
    ('assets/images/15.png', 40814, 'ba78771c150aeace865ad8c991ea316a0a187260'),
    ('assets/images/16.png', 58602, '1154e2bfe0bf1d826a5ed2026f0524a6e2fc140e'),
    ('assets/images/17.png', 41656, '03aedcbb62e6b16f924cff5bfcf0869c76b5bec7'),
    ('assets/images/18.png', 39618, '8c4f352467fc869c108968b6746190392107c31f'),
    ('assets/images/19.png', 53899, '4e5b2815e3c6faf3f0cdccbca642a4dcf357639d'),
    ('assets/images/2.png', 175932, 'ac269ce09546bfca97484d46262a7420fb7750ea'),
    ('assets/images/20.png', 55651, '4f9b3310c51552b4af81bf0d5e2b2d1686c5a1cf'),
    ('assets/images/21.png', 47927, '816aadd6fca6a77857ec4306147db91ace5e7d41'),
    ('assets/images/22.png', 82253, 'af58f2552c9bea482ca77d01426adce9d3b56edf'),
    ('assets/images/23.png', 47284, '9900eb0ca7ee15c67783605fb773a5648818263e'),
    ('assets/images/24.png', 73380, '5629563d555719bd68c01b918189b3a4969a19aa'),
    ('assets/images/25.png', 36158, 'fb15ba954d81ed9cecc1b61f6fefcdcf4111f21e'),
    ('assets/images/26.png', 45521, 'fc480d0bf8bf05214a7bc8c569d26eeb3fc6a932'),
    ('assets/images/27.png', 41062, '9e3334a5773254f1e8a2d48d0bd5690b1915d1fd'),
    ('assets/images/28.png', 48848, 'ca0b97f8764f864bce7f77e3f9b39eb2d5960e1e'),
    ('assets/images/29.png', 48729, 'b824a50d778aec9d887aa4c90e296246f9776f75'),
    ('assets/images/3.png', 110190, 'a9f47bba5f40c4db2fd9d8fe074b4e7ac11ed815'),
    ('assets/images/30.png', 60859, 'bd2b89720948512aad74fbc0a49d693330f10b45'),
    ('assets/images/31.png', 51913, '6ce4d0dc81b68d89e8ce0bf86353cf12d1d4810a'),
    ('assets/images/32.png', 54990, 'f7a174f2720f75d493a4350d202cef84ecdce7c6'),
    ('assets/images/33.png', 62977, '93862ac73078653ec76329b45ed1295c8c6b2737'),
    ('assets/images/34.png', 41780, 'ebb5c5b8560b791ad593bc7a05cf825440bff7dc'),
    ('assets/images/35.png', 44201, '7029b7e793af7843ef11cfd129c37d0caa330901'),
    ('assets/images/36.png', 339148, 'cbfdae55d41f67ede04abc7a864512f18fd3dc75'),
    ('assets/images/37.png', 75212, 'b1679bcbeb6826b8ba5478d0cba01a436c4398ce'),
    ('assets/images/38.png', 32494, 'd150191543bb6476d0109c462a20a4c3f247e061'),
    ('assets/images/39.png', 24557, '7229868b95f3b997fda30725f39f96cdcb7d642a'),
    ('assets/images/4.png', 105977, 'b7c0d72ad649fcf5eb445b7cf1405f77404241b4'),
    ('assets/images/40.png', 22781, '42ac03366912385ac134a6f3daabac896b153f47'),
    ('assets/images/41.png', 13428, 'c397a87f932a139815440884f091b3d67af83151'),
    ('assets/images/42.png', 13067, '20403f85956d3c230710c175320aa37590f49aea'),
    ('assets/images/43.png', 29409, '394fa86041d1a21ff74a83ca9516d8e3b50bfc98'),
    ('assets/images/44.png', 7228, 'd7481b937f926cbd05c059b4b5cc14e92be91250'),
    ('assets/images/45.png', 7620, 'ac758915cf56e2277ad2b9227950d7db02ea240b'),
    ('assets/images/46.png', 7595, 'ea82c3f857e5735ea615b5c1bf4d83d20ffee736'),
    ('assets/images/47.png', 7181, '2ad8d427d58cddd2cfe2a584e4a3481b8cb05e88'),
    ('assets/images/48.png', 14219, '864b495a29bd208f5a50c6f7802307ba46d8ed57'),
    ('assets/images/5.png', 109633, '22897af620477737698ddee7ca0fa7afdd971349'),
    ('assets/images/6.png', 77600, '29bb7daf86b10abd554bf710655d00cd6822fe2a'),
    ('assets/images/7.png', 70844, '5e46c3bcbf7b572c4f3b73cd553f2b1ea742ced6'),
    ('assets/images/8.png', 46460, '49c98684e02df87b823c91388a32ca607aca3b4f'),
    ('assets/images/9.png', 42834, '02ed5f949f7e40ba62d8177123cd1b91e1061dd7'),

)


class AssetError(RuntimeError):
    """An asset failed manifest, download, or integrity validation."""


def _destination(root: Path, entry: tuple[str, int, str]) -> Path:
    relative, size, digest = entry
    path = PurePosixPath(relative)
    if (path.is_absolute() or not path.parts or path.parts[0] != "assets"
            or len(path.parts) < 2 or ".." in path.parts or "\\" in relative
            or "\0" in relative):
        raise AssetError(f"Unsafe asset path: {relative!r}")
    if not isinstance(size, int) or size < 0 or not re.fullmatch(r"[0-9a-f]{40}", digest):
        raise AssetError(f"Invalid asset manifest entry: {relative}")
    destination = root.joinpath(*path.parts)
    if not destination.resolve().is_relative_to(root.resolve()):
        raise AssetError(f"Asset path escapes destination through a symlink: {relative}")
    return destination


def _blob_hasher(size: int):
    # Git identifiers include the blob header; hashing raw bytes alone is incorrect.
    digest = hashlib.sha1(usedforsecurity=False)
    digest.update(f"blob {size}\0".encode("ascii"))
    return digest


def verify_asset(path: Path, size: int, expected_sha: str) -> bool:
    if not path.is_file() or path.stat().st_size != size:
        return False
    digest = _blob_hasher(size)
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == expected_sha


def download_asset(
    root: Path,
    entry: tuple[str, int, str],
    *,
    opener: Callable = urlopen,
) -> bool:
    """Return True when fetched, False when an existing verified file is reused."""
    destination = _destination(root, entry)
    relative, size, expected_sha = entry
    if verify_asset(destination, size, expected_sha):
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    url = f"{UPSTREAM_RAW}/{UPSTREAM_REVISION}/{quote(relative, safe='/')}"
    request = Request(url, headers={"User-Agent": "ok-ww-experimental-macos-assets/1"})
    temporary_path = None
    try:
        # urlopen uses the platform's verified TLS context. Never disable verification.
        with opener(request, timeout=60) as response:
            digest = _blob_hasher(size)
            received = 0
            with tempfile.NamedTemporaryFile(
                mode="wb", prefix=f".{destination.name}.", suffix=".download",
                dir=destination.parent, delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                while True:
                    chunk = response.read(min(1024 * 1024, size - received + 1))
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > size:
                        raise AssetError(f"Asset is larger than expected: {relative}")
                    digest.update(chunk)
                    temporary.write(chunk)
                if received != size or digest.hexdigest() != expected_sha:
                    raise AssetError(
                        f"Asset verification failed: {relative} "
                        f"(received {received}/{size} bytes; Git blob {digest.hexdigest()})"
                    )
                temporary.flush()
                os.fsync(temporary.fileno())
        os.replace(temporary_path, destination)
        return True
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def download_assets(
    root: Path,
    assets: Iterable[tuple[str, int, str]] = ASSETS,
    *,
    opener: Callable = urlopen,
) -> tuple[int, int]:
    """Verify/download all entries, returning (downloaded, reused)."""
    root = root.resolve()
    entries = tuple(assets)
    # Check the entire manifest before making requests or writing any files.
    for entry in entries:
        _destination(root, entry)
    downloaded = reused = 0
    for index, entry in enumerate(entries, 1):
        fetched = download_asset(root, entry, opener=opener)
        downloaded += int(fetched)
        reused += int(not fetched)
        print(f"[{index}/{len(entries)}] {'Downloaded' if fetched else 'Verified'} {entry[0]}", flush=True)
    return downloaded, reused


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parent.parent,
        help="Application root containing the assets directory (default: this source tree)",
    )
    args = parser.parse_args(argv)
    try:
        downloaded, reused = download_assets(args.root)
    except (AssetError, OSError, ValueError) as error:
        print(f"Asset installation failed: {error}", file=sys.stderr)
        return 1
    print(f"Assets ready: {downloaded} downloaded, {reused} already verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
