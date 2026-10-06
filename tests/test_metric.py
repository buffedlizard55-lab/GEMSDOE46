from __future__ import annotations

import numpy as np
import pytest

from gemsdoe46.metric import dti_components, dti_score


def test_perfectly_aligned_prediction_scores_one() -> None:
    truth = np.zeros((7, 7), dtype=np.uint8)
    truth[3, 3] = 1
    prediction = truth.astype(np.float32)

    result = dti_components(prediction, truth)

    assert result.score == pytest.approx(1.0)
    assert result.true_positive == pytest.approx(1.0)
    assert result.false_positive == pytest.approx(0.0)
    assert result.false_negative == pytest.approx(0.0)


def test_one_pixel_offset_uses_triangular_300m_credit() -> None:
    truth = np.zeros((7, 7), dtype=np.uint8)
    truth[3, 3] = 1
    prediction = np.zeros_like(truth, dtype=np.float32)
    prediction[3, 4] = 1.0  # one 100 m pixel away

    result = dti_components(prediction, truth)

    assert result.true_positive == pytest.approx(2.0 / 3.0)
    assert result.false_negative == pytest.approx(1.0 / 3.0)
    assert result.false_positive == pytest.approx(1.0 / 3.0)
    assert result.score == pytest.approx(2.0 / 3.0)


def test_prediction_at_300m_has_no_tp_credit_and_zero_score() -> None:
    truth = np.zeros((9, 9), dtype=np.uint8)
    truth[4, 2] = 1
    prediction = np.zeros_like(truth, dtype=np.float32)
    prediction[4, 5] = 1.0

    assert dti_score(prediction, truth) == pytest.approx(0.0)


def test_no_prediction_has_zero_score_and_full_fn() -> None:
    truth = np.zeros((5, 5), dtype=np.uint8)
    truth[1, 1] = 1
    prediction = np.zeros_like(truth, dtype=np.float32)

    result = dti_components(prediction, truth)

    assert result.score == pytest.approx(0.0)
    assert result.true_positive == pytest.approx(0.0)
    assert result.false_negative == pytest.approx(1.0)
    assert result.false_positive == pytest.approx(0.0)


def test_invalid_values_are_ignored_only_outside_valid_mask() -> None:
    truth = np.zeros((5, 5), dtype=np.uint8)
    truth[2, 2] = 1
    prediction = np.zeros((5, 5), dtype=np.float32)
    prediction[2, 2] = 1.0
    prediction[0, 0] = np.nan
    valid = np.ones((5, 5), dtype=bool)
    valid[0, 0] = False

    assert dti_score(prediction, truth, valid_mask=valid) == pytest.approx(1.0)
    prediction[2, 2] = 1.01
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        dti_score(prediction, truth, valid_mask=valid)


def test_nonfinite_prediction_inside_valid_mask_is_rejected() -> None:
    truth = np.zeros((3, 3), dtype=np.uint8)
    truth[1, 1] = 1
    prediction = np.zeros((3, 3), dtype=np.float32)
    prediction[0, 0] = np.inf

    with pytest.raises(ValueError, match="finite"):
        dti_score(prediction, truth)


def test_empty_truth_is_rejected() -> None:
    truth = np.zeros((3, 3), dtype=np.uint8)
    prediction = np.zeros((3, 3), dtype=np.float32)

    with pytest.raises(ValueError, match="positive truth"):
        dti_score(prediction, truth)


def test_partitioned_components_sum_to_full_components() -> None:
    truth = np.zeros((8, 8), dtype=np.uint8)
    truth[1, 1] = 1
    truth[1, 6] = 1
    truth[6, 1] = 1
    truth[6, 6] = 1
    prediction = np.zeros((8, 8), dtype=np.float32)
    prediction[1, 2] = 0.4
    prediction[6, 5] = 0.7
    valid = np.ones((8, 8), dtype=bool)

    full = dti_components(prediction, truth, valid_mask=valid)
    components = [
        dti_components(
            prediction,
            truth,
            valid_mask=valid,
            score_mask=np.indices(valid.shape)[0] // 4 * 2 + np.indices(valid.shape)[1] // 4
            == fold_id,
        )
        for fold_id in range(4)
    ]

    assert sum(item.true_positive for item in components) == pytest.approx(full.true_positive)
    assert sum(item.false_positive for item in components) == pytest.approx(full.false_positive)
    assert sum(item.false_negative for item in components) == pytest.approx(full.false_negative)
