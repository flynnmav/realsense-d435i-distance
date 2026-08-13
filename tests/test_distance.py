"""测距核心单元测试(无需相机硬件)。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from d435i_distance.distance import measure_at_pixel, sample_depth_median  # noqa: E402
from d435i_distance.types import Intrinsics  # noqa: E402

INTR = Intrinsics(width=1280, height=720, fx=920.0, fy=920.0, ppx=640.0, ppy=360.0)


def make_depth(w=1280, h=720, value=1000):
    return np.full((h, w), value, dtype=np.uint16)


class TestDeprojection(unittest.TestCase):
    def test_center_is_perpendicular(self):
        """画面中心: 斜距 = 垂直深度。"""
        depth = make_depth(value=1000)  # 1.0 m
        m = measure_at_pixel(depth, 640, 360, INTR, depth_units=0.001)
        self.assertTrue(m.valid)
        self.assertAlmostEqual(m.depth_z, 1.0, places=6)
        self.assertAlmostEqual(m.distance, 1.0, places=6)
        self.assertAlmostEqual(m.point[0], 0.0, places=6)
        self.assertAlmostEqual(m.point[1], 0.0, places=6)
        self.assertAlmostEqual(m.point[2], 1.0, places=6)

    def test_off_center_is_euclidean(self):
        """偏离中心的像素: X = z/2, 距离 = z*sqrt(5)/2。"""
        depth = make_depth(value=2000)  # 2.0 m
        u = int(640 + INTR.fx / 2)
        m = measure_at_pixel(depth, u, 360, INTR, depth_units=0.001)
        self.assertTrue(m.valid)
        self.assertAlmostEqual(m.point[0], 1.0, places=6)
        self.assertAlmostEqual(m.distance, 2.0 * np.sqrt(5.0) / 2.0, places=6)

    def test_median_suppresses_outliers(self):
        """邻域中位数应滤掉少数空洞与飞点。"""
        depth = make_depth(value=1000)
        depth[359:362, 639:642] = 0    # 少量空洞
        depth[360, 640] = 9000         # 一个飞点
        v = sample_depth_median(depth, 640, 360, radius=2)
        self.assertEqual(v, 1000.0)

    def test_out_of_bounds_invalid(self):
        depth = make_depth(value=1000)
        m = measure_at_pixel(depth, 5000, 5000, INTR, depth_units=0.001)
        self.assertFalse(m.valid)

    def test_zero_depth_invalid(self):
        depth = make_depth(value=0)
        m = measure_at_pixel(depth, 640, 360, INTR, depth_units=0.001)
        self.assertFalse(m.valid)


if __name__ == "__main__":
    unittest.main()
