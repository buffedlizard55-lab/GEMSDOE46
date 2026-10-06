from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from import_competition_archive import import_archive


def test_importer_extracts_local_zip_and_records_hashes(tmp_path) -> None:
    archive = tmp_path / "official-data.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("nested/features.tif", b"test-raster-bytes")
        bundle.writestr("readme.txt", b"archive note")

    destination = tmp_path / "raw"
    receipt = import_archive(archive, destination)

    assert receipt["network_accessed"] is False
    assert len(receipt["files"]) == 2
    assert (destination / "nested/features.tif").read_bytes() == b"test-raster-bytes"
    assert all(row["sha256"] for row in receipt["files"])


def test_importer_rejects_zip_slip_before_extracting_any_member(tmp_path) -> None:
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("safe.txt", b"would otherwise be extracted")
        bundle.writestr("../escape.txt", b"not allowed")

    destination = tmp_path / "raw"
    with pytest.raises(ValueError, match="unsafe ZIP member"):
        import_archive(archive, destination)
    assert not (tmp_path / "escape.txt").exists()
    assert not (destination / "safe.txt").exists()


def test_importer_rejects_windows_absolute_and_backslash_paths(tmp_path) -> None:
    archive = tmp_path / "windows-paths.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("C:/outside.txt", b"not allowed")

    with pytest.raises(ValueError, match="unsafe ZIP member"):
        import_archive(archive, tmp_path / "raw")


def test_importer_refuses_to_overwrite_different_file(tmp_path) -> None:
    archive = tmp_path / "data.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("features.tif", b"new content")
    destination = tmp_path / "raw"
    destination.mkdir()
    (destination / "features.tif").write_bytes(b"old content")

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        import_archive(archive, destination)
