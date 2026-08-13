"""无 GUI 冒烟测试: 连续取帧并对画面中心/四分点测距, 输出统计。

用途: 快速验证相机与测距链路(不打开任何窗口)。
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from d435i_distance.camera import RealSenseCamera, StreamConfig  # noqa: E402
from d435i_distance.distance import distance_between_pixels, measure_at_pixel  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="D435i 无 GUI 测距冒烟测试")
    ap.add_argument("--frames", type=int, default=30, help="采样帧数")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--no-emitter", action="store_true")
    args = ap.parse_args()

    cfg = StreamConfig(width=args.width, height=args.height,
                       laser_emitter=not args.no_emitter)
    try:
        with RealSenseCamera(cfg) as cam:
            cam.print_info()
            bundle = cam.wait_for_frames()
            w, h = bundle.intrinsics.width, bundle.intrinsics.height
            pts = [(w // 2, h // 2), (w // 4, h // 2),
                   (3 * w // 4, h // 2), (w // 2, 3 * h // 4)]
            stats = {p: [] for p in pts}

            t0 = time.perf_counter()
            for _ in range(args.frames):
                bundle = cam.wait_for_frames()
                for p in pts:
                    m = measure_at_pixel(bundle.depth, p[0], p[1],
                                         bundle.intrinsics, bundle.depth_units)
                    if m.valid:
                        stats[p].append(m.distance)
            dt = time.perf_counter() - t0
            print(f"完成 {args.frames} 帧, 耗时 {dt:.2f} s, 平均 {args.frames / dt:.1f} FPS")

            ok = False
            for p, vals in stats.items():
                if vals:
                    ok = True
                    arr = np.asarray(vals)
                    print(f"  点 {p}: 距离 mean={arr.mean():.3f} std={arr.std():.3f} "
                          f"min={arr.min():.3f} max={arr.max():.3f} m")
                else:
                    print(f"  点 {p}: 无有效深度(确认该处有目标且在量程内)")
            if not ok:
                print("[WARN] 所有点均无有效深度, 请确认量程/场景/红外投影设置")

            d = distance_between_pixels(bundle.depth, pts[1], pts[2],
                                        bundle.intrinsics, bundle.depth_units)
            print(f"左右四分点 3D 间距: {d:.3f} m" if d else "左右四分点 3D 间距: N/A")
            return 0
    except RuntimeError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
