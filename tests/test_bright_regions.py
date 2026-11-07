import unittest

import numpy as np

from bright_regions import (apply_fluorescence_calibration, background_record,
                            channel_statistics)


class FluorescenceStatisticsTests(unittest.TestCase):
    def test_standard_deviation_and_relative_error(self):
        pixels = np.array([[10, 100, 20], [20, 140, 40]], dtype=np.uint8)
        mean, standard_deviation, relative_error = channel_statistics(pixels)
        np.testing.assert_allclose(mean, [15, 120, 30])
        np.testing.assert_allclose(standard_deviation, [5, 20, 10])
        np.testing.assert_allclose(relative_error, [1 / 3, 1 / 6, 1 / 3])

    def test_background_record_uses_green_as_fluorescence(self):
        rgb = np.array([[[10, 100, 20], [20, 140, 40]]], dtype=np.uint8)
        record, _ = background_record(rgb, np.ones((1, 2), dtype=bool), image_id="sample",
                                      area_id="E01", location="top-left",
                                      selection_method="test", origin=(0, 0))
        self.assertEqual(record["mean_fluorescence_0_255"], 120.0)
        self.assertEqual(record["std_fluorescence_0_255"], 20.0)
        self.assertAlmostEqual(record["relative_error_fluorescence"], 1 / 6, places=6)

    def test_shared_calibration_targets_weighted_broad_green_mean(self):
        records = [
            {"kind": "broad", "area_px": 2, "integrated_G": 200,
             "mean_R_0_255": 50, "mean_G_0_255": 100, "mean_B_0_255": 25,
             "std_R_0_255": 5, "std_G_0_255": 10, "std_B_0_255": 2},
            {"kind": "broad", "area_px": 1, "integrated_G": 200,
             "mean_R_0_255": 100, "mean_G_0_255": 200, "mean_B_0_255": 50,
             "std_R_0_255": 10, "std_G_0_255": 20, "std_B_0_255": 4},
        ]
        reference, factor = apply_fluorescence_calibration(records, [], 147.0)
        self.assertAlmostEqual(reference, 400 / 3)
        self.assertAlmostEqual(factor, 147 / (400 / 3))
        weighted_scaled_green = sum(row["scaled_mean_G_0_255"] * row["area_px"]
                                    for row in records) / 3
        self.assertAlmostEqual(weighted_scaled_green, 147.0, places=2)


if __name__ == "__main__":
    unittest.main()
