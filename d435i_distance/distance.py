"""测距核心: 从深度图反投影出 3D 点并计算真实距离。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from .types import Intrinsics


@dataclass
class Measurement:
    """一次测距结果。"""

    u: int
    v: int
    valid: bool
    depth_z: float   # 沿光轴方向的垂直深度(米), 即深度图的原始含义
    distance: float  # 相机光心到目标点的欧氏距离(米), 即真实斜距
    point: Tuple[float, float, float]  # 相机坐标系下的 3D 点

    def format_text(self) -> str:
        if not self.valid:
            return f"({self.u},{self.v}) 无有效深度"
        return (
            f"({self.u},{self.v}) 距离={self.distance:.3f} m "
            f"(垂直深度={self.depth_z:.3f} m, "
            f"3D=({self.point[0]:.3f},{self.point[1]:.3f},{self.point[2]:.3f}) m)"
        )


def sample_depth_median(depth: np.ndarray, u: int, v: int, radius: int = 2) -> Optional[float]:
    """取像素 (u, v) 邻域内非零深度的中位数, 抑制飞点/空洞噪声。"""
    h, w = depth.shape[:2]
    u, v = int(u), int(v)
    if not (0 <= u < w and 0 <= v < h):
        return None
    u0, u1 = max(0, u - radius), min(w, u + radius + 1)
    v0, v1 = max(0, v - radius), min(h, v + radius + 1)
    patch = depth[v0:v1, u0:u1].astype(np.float64)
    patch = patch[patch > 0]
    if patch.size == 0:
        return None
    return float(np.median(patch))


def measure_at_pixel(
    depth: np.ndarray,
    u: int,
    v: int,
    intrinsics: Intrinsics,
    depth_units: float,
    radius: int = 2,
) -> Measurement:
    """测量图像中像素 (u, v) 处目标的真实距离(米)。

    深度相机直接输出的是"垂直深度"(沿光轴方向), 画面边缘的目标其真实
    斜距明显大于垂直深度。本函数利用内参把像素反投影为 3D 点, 再计算
    光心到该点的欧氏距离::

        X = (u - ppx) * Z / fx
        Y = (v - ppy) * Z / fy
        distance = sqrt(X^2 + Y^2 + Z^2)
    """
    raw = sample_depth_median(depth, u, v, radius)
    if raw is None:
        return Measurement(int(u), int(v), False, 0.0, 0.0, (0.0, 0.0, 0.0))
    z = raw * depth_units
    x, y, zz = intrinsics.deproject(u, v, z)
    dist = float(np.sqrt(x * x + y * y + zz * zz))
    return Measurement(int(u), int(v), True, z, dist, (x, y, zz))


def distance_between_pixels(
    depth: np.ndarray,
    p1: Tuple[int, int],
    p2: Tuple[int, int],
    intrinsics: Intrinsics,
    depth_units: float,
) -> Optional[float]:
    """测量图像中两个像素对应 3D 点之间的空间距离(米)。"""
    m1 = measure_at_pixel(depth, p1[0], p1[1], intrinsics, depth_units)
    m2 = measure_at_pixel(depth, p2[0], p2[1], intrinsics, depth_units)
    if not (m1.valid and m2.valid):
        return None
    return float(np.linalg.norm(np.asarray(m1.point) - np.asarray(m2.point)))
