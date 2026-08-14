"""检查 RealSense 设备连接与流可用性, 打印序列号/固件/内参/深度单位。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from d435i_distance.camera import RealSenseCamera, StreamConfig  # noqa: E402


def main() -> int:
    try:
        with RealSenseCamera(StreamConfig()) as cam:
            cam.print_info()
            bundle = cam.wait_for_frames()
            print(f"取帧成功: 彩色 {bundle.color.shape}, 深度 {bundle.depth.shape}")
            h, w = bundle.depth.shape
            raw = int(bundle.depth[h // 2, w // 2])
            print(f"画面中心原始深度值: {raw} (约 {raw * bundle.depth_units:.3f} m)")
            print("设备工作正常 [OK]")
            return 0
    except RuntimeError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1
    except ImportError as e:
        print(f"[ERROR] 缺少依赖: {e}", file=sys.stderr)
        print("请先安装: pip install -r requirements.txt")
        return 1


if __name__ == "__main__":
    sys.exit(main())
