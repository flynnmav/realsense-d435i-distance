"""可视化函数测试(无需相机与窗口)。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from d435i_distance.annotator import (  # noqa: E402
    colorize_depth,
    draw_hud,
    draw_measurement,
    stack_views,
)
from d435i_distance.distance import Measurement  # noqa: E402
from d435i_distance.types import Intrinsics  # noqa: E402


class TestAnnotator(unittest.TestCase):
    def setUp(self):
        self.depth = np.full((720, 1280), 1000, dtype=np.uint16)
        self.depth[100:200, 100:200] = 0
        self.color = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.intr = Intrinsics(1280, 720, 920.0, 920.0, 640.0, 360.0)

    def test_colorize_shape_and_type(self):
        out = colorize_depth(self.depth, 0.001)
        self.assertEqual(out.shape, (720, 1280, 3))
        self.assertEqual(out.dtype, np.uint8)

    def test_draw_measurement_valid(self):
        m = Measurement(640, 360, True, 1.0, 1.0, (0.0, 0.0, 1.0))
        img = draw_measurement(self.color.copy(), 640, 360, m)
        self.assertEqual(img.shape, self.color.shape)
        self.assertTrue((img != 0).any())  # 确实画了内容

    def test_draw_measurement_invalid(self):
        m = Measurement(640, 360, False, 0.0, 0.0, (0.0, 0.0, 0.0))
        img = draw_measurement(self.color.copy(), 640, 360, m)
        self.assertTrue((img != 0).any())

    def test_hud_and_stack(self):
        d = colorize_depth(self.depth, 0.001)
        out = stack_views(self.color.copy(), d)
        self.assertEqual(out.shape, (720, 2560, 3))
        draw_hud(out, 30.0, 0.001, recording=True)
        self.assertTrue((out != 0).any())


if __name__ == "__main__":
    unittest.main()
