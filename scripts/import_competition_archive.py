#!/usr/bin/env python3
"""Safely import a locally downloaded competition ZIP without network access."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath


def sha256_stream(stream) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return sha256_stream(stream)


def safe_destination(root: Path, member: str) -> Path:
    """Resolve a ZIP member under root; reject traversal and cross-platform paths."""
    if not member or "\x00" in member or "\\" in member:
        raise ValueError(f"unsafe ZIP member path: {member!r}")
    posix = PurePosixPath(member)
    windows = PureWindowsPath(member)
    if (
        posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or not posix.parts
        or any(part in ("", ".", "..") for part in posix.parts)
    ):
        raise ValueError(f"unsafe ZIP member path: {member!r}")
    destination = (root / Path(*posix.parts)).resolve()
    if destination != root and root not in destination.parents:
        raise ValueError(f"ZIP member escapes destination: {member!r}")
    return destination


def _copy_and_hash(source, target) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_count = 0
    for chunk in iter(lambda: source.read(1024 * 1024), b""):
        target.write(chunk)
        digest.update(chunk)
        byte_count += len(chunk)
    return digest.hexdigest(), byte_count


def import_archive(archive: Path, destination_root: Path) -> dict:
    archive = Path(archive)
    destination_root = Path(destination_root)
    if not archive.is_file():
        raise FileNotFoundError(archive)
    if not zipfile.is_zipfile(archive):
        raise ValueError(f"not a ZIP archive: {archive}")
    destination_root.mkdir(parents=True, exist_ok=True)
    root = destination_root.resolve()
    extracted: list[dict[str, object]] = []

    with zipfile.ZipFile(archive) as bundle:
        entries: list[tuple[zipfile.ZipInfo, Path]] = []
        destinations_seen: set[Path] = set()
        for info in bundle.infolist():
            if info.is_dir():
                continue
            destination = safe_destination(root, info.filename)
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ValueError(f"symbolic links are not allowed in archive: {info.filename}")
            if info.flag_bits & 0x1:
                raise ValueError(f"encrypted ZIP entries are not supported: {info.filename}")
            if destination in destinations_seen:
                raise ValueError(f"duplicate ZIP member destination: {info.filename}")
            destinations_seen.add(destination)
            entries.append((info, destination))
        if not entries:
            raise ValueError("archive contains no files")

        # Validate every member before extracting anything, avoiding partial
        # extraction when a later member contains an unsafe path or link.
        for info, destination in entries:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                with bundle.open(info, "r") as source:
                    content_hash = sha256_stream(source)
                existing_hash = sha256_file(destination)
                if existing_hash != content_hash:
                    raise FileExistsError(
                        f"refusing to overwrite different local file: {destination}"
                    )
                action = "already-present-identical"
            else:
                try:
                    with bundle.open(info, "r") as source, destination.open("xb") as target:
                        content_hash, byte_count = _copy_and_hash(source, target)
                    if byte_count != info.file_size:
                        raise ValueError(
                            f"uncompressed size mismatch for ZIP member {info.filename!r}"
                        )
                except Exception:
                    destination.unlink(missing_ok=True)
                    raise
                action = "extracted"

            extracted.append(
                {
                    "member": info.filename,
                    "bytes": info.file_size,
                    "sha256": content_hash,
                    "action": action,
                }
            )

    return {
        "imported_at_utc": datetime.now(UTC).isoformat(),
        "network_accessed": False,
        "archive_name": archive.name,
        "archive_sha256": sha256_file(archive),
        "destination": str(root),
        "files": extracted,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive", required=True, help="ZIP already downloaded through official portal"
    )
    parser.add_argument(
        "--destination", default="data/raw", help="extraction root (default: %(default)s)"
    )
    parser.add_argument(
        "--receipt",
        default="data/processed/archive-import.json",
        help="import receipt path (default: %(default)s)",
    )
    args = parser.parse_args()
    try:
        receipt = import_archive(Path(args.archive), Path(args.destination))
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"IMPORT FAILED: {exc}", file=sys.stderr)
        return 2

    receipt_path = Path(args.receipt)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, allow_nan=False))
    print("No network request or login was made by this importer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
