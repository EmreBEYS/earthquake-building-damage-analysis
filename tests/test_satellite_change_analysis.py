from affine import Affine
import numpy as np
import pytest

from earthquake_damage.satellite_change_analysis import (
    assert_aligned,
    normalized_difference,
    valid_scl_mask,
)


def test_normalized_difference_and_zero_denominator():
    result = normalized_difference(np.array([3, 0]), np.array([1, 0]))
    assert result[0] == pytest.approx(0.5)
    assert np.isnan(result[1])


def test_scl_mask_rejects_cloud_shadow_cirrus_snow_and_nodata():
    scl = np.array([0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11])
    valid = valid_scl_mask(scl, [0, 1, 3, 8, 9, 10, 11])
    assert valid.tolist() == [False, False, False, True, True, True, True,
                              False, False, False, False]


def test_alignment_requires_identical_grid():
    base = {"crs": "EPSG:32637", "transform": Affine(10, 0, 0, 0, -10, 100),
            "width": 10, "height": 10}
    assert assert_aligned([base, dict(base)]) == base
    shifted = {**base, "transform": Affine(10, 0, 5, 0, -10, 100)}
    with pytest.raises(ValueError, match="not exactly aligned"):
        assert_aligned([base, shifted])
