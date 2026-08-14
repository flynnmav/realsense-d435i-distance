"""深度图诊断: 统计整幅深度分布并用 ASCII 可视化, 排查"无深度"问题。

用法: python scripts/depth_diag.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pyrealsense2 as rs

from d435i_distance.camera import RealSenseCamera, StreamConfig


def main() -> int:
    ctx = rs.context()
    if len(ctx.query_devices()) == 0:
        print("[ERROR] 未检测到 RealSense 设备", file=sys.stderr)
        return 1
    ds = ctx.query_devices()[0].first_depth_sensor()
    print("红外点阵投影(emitter):", ds.get_option(rs.option.emitter_enabled))
    try:
        print("激光功率(laser_power):", ds.get_option(rs.option.laser_power))
    except RuntimeError:
        pass

    with RealSenseCamera(StreamConfig(laser_emitter=True)) as cam:
        for _ in range(20):
            b = cam.wait_for_frames()
        d = b.depth.astype(np.float64) * b.depth_units
        valid = d[d > 0]
        print(f"有效深度像素占比: {valid.size / d.size * 100:.1f}%")
        if valid.size:
            near = d[(d > 0) & (d < 65.0)]  # 排除"过远"哨兵值 65.535 m
            print(f"距离范围: min={near.min():.3f} m  max={near.max():.3f} m  mean={near.mean():.3f} m")
        print("ASCII 深度图(每字符约 80x60 像素):")
        print("  . = 无深度   # = <0.5m   o = <1m   + = <2m   空格 = >=2m")
        small = d[::60, ::80]
        for row in small:
            line = "".join(
                "." if v <= 0 else ("#" if v < 0.5 else ("o" if v < 1.0 else ("+" if v < 2.0 else " ")))
                for v in row
            )
            print(line)
        if valid.size == 0:
            print("[WARN] 整幅图像无有效深度, 请检查: 镜头保护膜是否撕掉/镜头是否被遮挡, "
                  "场景是否在 0.3~3 m 且有纹理(或开启红外点阵)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
