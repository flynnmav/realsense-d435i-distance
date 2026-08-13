"""基础数据结构: 相机内参与帧数据。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

import numpy as np


@dataclass
class Intrinsics:
    """针孔相机内参。

    注意: 深度流对齐到彩色流之后, 深度图与彩色图共用同一像素坐标系,
    因此反投影一律使用彩色相机内参。
    """

    width: int
    height: int
    fx: float
    fy: float
    ppx: float
    ppy: float
    model: int = 0
    coeffs: Tuple[float, ...] = field(default_factory=tuple)

    @classmethod
    def from_rs(cls, intr) -> "Intrinsics":
        """从 pyrealsense2 的 intrinsics 对象构造。"""
        return cls(
            width=int(intr.width),
            height=int(intr.height),
            fx=float(intr.fx),
            fy=float(intr.fy),
            ppx=float(intr.ppx),
            ppy=float(intr.ppy),
            model=int(intr.model),
            coeffs=tuple(float(c) for c in intr.coeffs),
        )

    def deproject(self, u: float, v: float, z: float) -> Tuple[float, float, float]:
        """把像素 (u, v) 与垂直深度 z(米) 反投影成相机坐标系 3D 点 (x, y, z)。

        相机坐标系: 原点为光心, +x 向右, +y 向下, +z 沿光轴向前。

            X = (u - ppx) * Z / fx
            Y = (v - ppy) * Z / fy
        """
        x = (float(u) - self.ppx) * z / self.fx
        y = (float(v) - self.ppy) * z / self.fy
        return x, y, z


@dataclass
class FrameBundle:
    """一帧对齐后的彩色 + 深度数据。"""

    color: np.ndarray          # BGR uint8 (H, W, 3)
    depth: np.ndarray          # uint16   (H, W), 真实米数 = 值 * depth_units
    depth_units: float         # 每个深度单位的米数 (D435i 通常为 0.001)
    intrinsics: Intrinsics     # 对齐后深度图的内参(与彩色图像素一一对应)
    timestamp_ms: float
    frame_number: int
