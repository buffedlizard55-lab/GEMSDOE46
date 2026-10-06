from __future__ import annotations

import numpy as np
import pytest
import rasterio
from affine import Affine

from gemsdoe46.raster import (
    RasterValidationError,
    preflight_inputs,
    validate_submission_tif,
    write_submission_tif,
)


def write_raster(path, array, *, nodata=None, transform=None, crs="EPSG:32611"):
    array = np.asarray(array)
    if array.ndim == 2:
        count, height, width = 1, *array.shape
        data = array[np.newaxis, ...]
    elif array.ndim == 3:
        count, height, width = array.shape
        data = array
    else:
        raise ValueError("test raster array must be 2D or 3D")
    dtype = data.dtype
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=width,
        height=height,
        count=count,
        dtype=dtype,
        crs=crs,
        transform=transform or Affine(100, 0, 500000, 0, -100, 4500000),
        nodata=nodata,
    ) as dataset:
        dataset.write(data)


def test_submission_writer_sets_nan_nodata_and_validates_bytes(tmp_path) -> None:
    nodata = np.float32(-9999)
    sample_array = np.zeros((5, 5), dtype=np.float32)
    sample_array[0, 0] = nodata
    sample = tmp_path / "sample.tif"
    write_raster(sample, sample_array, nodata=nodata)

    candidate_array = np.full((5, 5), 0.4, dtype=np.float32)
    candidate_array[0, 0] = -12345.0  # ignored outside the sample footprint
    candidate = tmp_path / "candidate.tif"
    write_raster(candidate, candidate_array, nodata=-12345.0)

    output = tmp_path / "submission.tif"
    report = write_submission_tif(
        candidate,
        sample,
        output,
        candidate_id="test-candidate-v1",
        validation_report_sha256="a" * 64,
    )

    assert report["status"] == "pass"
    assert report["dtype"] == "float32"
    assert report["count"] == 1
    with rasterio.open(output) as dataset:
        result = dataset.read(1)
        assert dataset.nodata is not None and np.isnan(dataset.nodata)
        assert np.isnan(result[0, 0])
        assert np.all(result[1:, :] == np.float32(0.4))
    assert validate_submission_tif(output, sample)["status"] == "pass"


def test_writer_rejects_out_of_range_value_inside_footprint(tmp_path) -> None:
    sample = tmp_path / "sample.tif"
    candidate = tmp_path / "candidate.tif"
    write_raster(sample, np.zeros((4, 4), dtype=np.float32))
    values = np.full((4, 4), 0.3, dtype=np.float32)
    values[2, 2] = -0.001
    write_raster(candidate, values)

    with pytest.raises(RasterValidationError, match=r"\[0, 1\]"):
        write_submission_tif(
            candidate,
            sample,
            tmp_path / "bad.tif",
            candidate_id="test-candidate-v1",
            validation_report_sha256="b" * 64,
        )


def test_submission_validator_rejects_multiband_and_wrong_dtype(tmp_path) -> None:
    sample = tmp_path / "sample.tif"
    write_raster(sample, np.zeros((4, 4), dtype=np.float32))

    multiband = tmp_path / "multiband.tif"
    write_raster(multiband, np.zeros((2, 4, 4), dtype=np.float32))
    with pytest.raises(RasterValidationError, match="exactly one band"):
        validate_submission_tif(multiband, sample)

    wrong_dtype = tmp_path / "wrong-dtype.tif"
    write_raster(wrong_dtype, np.zeros((4, 4), dtype=np.float64), nodata=np.nan)
    with pytest.raises(RasterValidationError, match="float32"):
        validate_submission_tif(wrong_dtype, sample)

    with pytest.raises(RasterValidationError, match="sample/reference"):
        validate_submission_tif(multiband, multiband)


def test_preflight_checks_grid_and_binary_labels(tmp_path) -> None:
    transform = Affine(100, 0, 500000, 0, -100, 4500000)
    sample = tmp_path / "sample.tif"
    features = tmp_path / "features.tif"
    labels = tmp_path / "labels.tif"

    sample_data = np.zeros((8, 8), dtype=np.float32)
    sample_data[0, 0] = -9999
    write_raster(sample, sample_data, nodata=-9999, transform=transform)
    write_raster(features, np.zeros((2, 8, 8), dtype=np.float32), transform=transform)
    label_data = np.zeros((8, 8), dtype=np.uint8)
    label_data[3, 3] = 1
    label_data[0, 0] = 255  # masked by the label nodata value
    write_raster(labels, label_data, nodata=255, transform=transform)

    report = preflight_inputs(features, labels, sample)

    assert report["status"] == "pass"
    assert report["grid"]["epsg"] == 32611
    assert report["labels"]["positive_pixels"] == 1


def test_preflight_rejects_grid_mismatch(tmp_path) -> None:
    sample = tmp_path / "sample.tif"
    features = tmp_path / "features.tif"
    labels = tmp_path / "labels.tif"
    write_raster(sample, np.zeros((5, 5), dtype=np.float32))
    write_raster(features, np.zeros((1, 5, 5), dtype=np.float32))
    write_raster(
        labels, np.zeros((5, 5), dtype=np.uint8), transform=Affine(100, 0, 500100, 0, -100, 4500000)
    )

    with pytest.raises(RasterValidationError, match="does not match sample grid"):
        preflight_inputs(features, labels, sample)
