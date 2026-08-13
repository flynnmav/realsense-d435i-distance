"""命令行入口: 实时测距可视化 + 测距数据记录导出。"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import List, Optional

import cv2
import yaml

from .annotator import colorize_depth, draw_hud, draw_measurement, stack_views
from .camera import RealSenseCamera, StreamConfig
from .distance import Measurement, measure_at_pixel

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "config.yaml"


def load_config(path: Optional[Path]) -> dict:
    if path is not None and path.exists():
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return data if isinstance(data, dict) else {}
        except Exception as e:
            print(f"[WARN] 读取配置文件失败: {e}")
    return {}


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="d435i-distance",
        description="RealSense D435i 实时测距: 实时显示彩色/深度画面, "
                    "鼠标点击目标并在图中标注真实距离, 支持 CSV/JSONL 数据导出。",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                        help="YAML 配置文件路径 (默认 config/config.yaml)")
    parser.add_argument("--width", type=int, help="流宽度 (默认 1280)")
    parser.add_argument("--height", type=int, help="流高度 (默认 720)")
    parser.add_argument("--fps", type=int, help="流帧率 (默认 30)")
    parser.add_argument("--no-emitter", action="store_true", help="关闭红外点阵投影")
    parser.add_argument("--filters", action="store_true", help="启用深度后处理滤波(降噪)")
    parser.add_argument("--min-depth", type=float, help="深度伪彩色最近距离/米 (默认 0.3)")
    parser.add_argument("--max-depth", type=float, help="深度伪彩色最远距离/米 (默认 6.0)")
    parser.add_argument("--target", type=int, nargs=2, metavar=("X", "Y"),
                        help="初始目标像素坐标 (默认画面中心)")
    parser.add_argument("--record", type=Path,
                        help="启动即录制测距数据, 输出 .csv 或 .jsonl 文件")
    parser.add_argument("--print-interval", type=float, default=1.0,
                        help="控制台打印测距结果的间隔(秒)")
    parser.add_argument("--median-radius", type=int, default=None,
                        help="测距取邻域中位数的半径(像素, 默认 2)")
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    cam_cfg = cfg.get("camera", {}) or {}
    vis_cfg = cfg.get("visualization", {}) or {}
    mes_cfg = cfg.get("measurement", {}) or {}

    if args.width is None:
        args.width = int(cam_cfg.get("width", 1280))
    if args.height is None:
        args.height = int(cam_cfg.get("height", 720))
    if args.fps is None:
        args.fps = int(cam_cfg.get("fps", 30))
    if args.min_depth is None:
        args.min_depth = float(vis_cfg.get("min_depth_m", 0.3))
    if args.max_depth is None:
        args.max_depth = float(vis_cfg.get("max_depth_m", 6.0))
    if args.median_radius is None:
        args.median_radius = int(mes_cfg.get("median_radius", 2))
    if not args.no_emitter and cam_cfg.get("laser_emitter") is False:
        args.no_emitter = True
    if not args.filters and cam_cfg.get("use_filters") is True:
        args.filters = True
    return args


class MeasurementRecorder:
    """把每帧测距结果写入 CSV 或 JSONL 文件, 供下游程序消费。"""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.suffix.lower() not in (".csv", ".jsonl"):
            self.path = self.path.with_suffix(".csv")
        self.is_csv = self.path.suffix.lower() == ".csv"
        self._f = None
        self._csv = None

    def open(self) -> None:
        self._f = open(self.path, "w", newline="", encoding="utf-8")
        if self.is_csv:
            self._csv = csv.writer(self._f)
            self._csv.writerow(["frame", "timestamp_ms", "u", "v",
                                "depth_z_m", "distance_m", "x_m", "y_m", "z_m"])
        print(f"[INFO] 开始录制 -> {self.path}")

    def write(self, frame_no: int, ts_ms: float, m: Measurement) -> None:
        if self._f is None:
            return
        if self.is_csv:
            self._csv.writerow([
                frame_no, f"{ts_ms:.1f}", m.u, m.v,
                f"{m.depth_z:.4f}" if m.valid else "",
                f"{m.distance:.4f}" if m.valid else "",
                f"{m.point[0]:.4f}" if m.valid else "",
                f"{m.point[1]:.4f}" if m.valid else "",
                f"{m.point[2]:.4f}" if m.valid else "",
            ])
        else:
            self._f.write(json.dumps({
                "frame": frame_no,
                "timestamp_ms": round(ts_ms, 1),
                "u": m.u, "v": m.v,
                "valid": m.valid,
                "depth_z_m": round(m.depth_z, 4) if m.valid else None,
                "distance_m": round(m.distance, 4) if m.valid else None,
                "point_m": [round(p, 4) for p in m.point] if m.valid else None,
            }, ensure_ascii=False) + "\n")

    def close(self) -> None:
        if self._f is not None:
            self._f.close()
            self._f = None
            print(f"[INFO] 录制完成 -> {self.path}")


class LiveApp:
    """交互式实时测距窗口。"""

    WINDOW = "D435i Distance | click: measure | c: center | p: pause | r: record | q: quit"

    def __init__(self, camera: RealSenseCamera, args: argparse.Namespace):
        self.cam = camera
        self.args = args
        self.target: List[int] = [0, 0]
        self.target_set = args.target is not None
        if self.target_set:
            self.target = [int(args.target[0]), int(args.target[1])]
        self._img_size = (args.width, args.height)
        self.paused = False
        self.recorder: Optional[MeasurementRecorder] = None
        self.fps = 0.0
        self._last_t = time.perf_counter()
        self._last_print = 0.0

    # ---------------- 回调 ----------------
    def _on_mouse(self, event, x, y, flags, param) -> None:
        if event == cv2.EVENT_LBUTTONDOWN:
            w, h = self._img_size
            self.target = [min(max(x, 0), w - 1), min(max(y, 0), h - 1)]
            self.target_set = True
            print(f"[INFO] 目标点设为 ({self.target[0]}, {self.target[1]})")

    # ---------------- 录制 ----------------
    def _toggle_record(self) -> None:
        if self.recorder is not None:
            self.recorder.close()
            self.recorder = None
            return
        if self.args.record:
            path = self.args.record
        else:
            stamp = time.strftime("%Y%m%d_%H%M%S")
            path = Path("records") / f"distance_{stamp}.csv"
        self.recorder = MeasurementRecorder(path)
        self.recorder.open()

    # ---------------- 主循环 ----------------
    def run(self) -> int:
        cv2.namedWindow(self.WINDOW, cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback(self.WINDOW, self._on_mouse)
        print("操作: 鼠标左键点击画面选目标点 | c 回到中心 | p 暂停 | r 开始/停止录制 | q 退出")

        if self.args.record:
            self.recorder = MeasurementRecorder(self.args.record)
            self.recorder.open()

        try:
            while True:
                bundle = self.cam.wait_for_frames()
                h, w = bundle.color.shape[:2]
                self._img_size = (w, h)
                if not self.target_set:
                    self.target = [w // 2, h // 2]

                m = measure_at_pixel(bundle.depth, self.target[0], self.target[1],
                                     bundle.intrinsics, bundle.depth_units,
                                     radius=self.args.median_radius)

                annotated = draw_measurement(bundle.color.copy(), self.target[0], self.target[1], m)
                depth_view = colorize_depth(bundle.depth, bundle.depth_units,
                                            self.args.min_depth, self.args.max_depth)
                depth_view = draw_measurement(depth_view, self.target[0], self.target[1],
                                              m, color=(255, 255, 255))
                view = stack_views(annotated, depth_view)
                draw_hud(view, self.fps, bundle.depth_units,
                         recording=self.recorder is not None, paused=self.paused)
                cv2.imshow(self.WINDOW, view)
                if cv2.getWindowProperty(self.WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                    break  # 窗口被关闭

                if self.recorder is not None:
                    self.recorder.write(bundle.frame_number, bundle.timestamp_ms, m)

                now = time.perf_counter()
                self._update_fps(now)
                if now - self._last_print >= self.args.print_interval:
                    print(f"[{time.strftime('%H:%M:%S')}] {m.format_text()}")
                    self._last_print = now

                delay = 0 if self.paused else 1
                key = cv2.waitKey(delay) & 0xFF
                if key in (ord("q"), 27):
                    break
                elif key == ord("c"):
                    self.target = [w // 2, h // 2]
                    print(f"[INFO] 目标点重置为画面中心 ({w // 2}, {h // 2})")
                elif key == ord("p"):
                    self.paused = not self.paused
                    print(f"[INFO] {'暂停' if self.paused else '继续'}")
                elif key == ord("r"):
                    self._toggle_record()
            return 0
        except KeyboardInterrupt:
            return 0
        finally:
            if self.recorder is not None:
                self.recorder.close()
            cv2.destroyAllWindows()

    def _update_fps(self, now: float) -> None:
        dt = now - self._last_t
        self._last_t = now
        if dt > 0:
            inst = 1.0 / dt
            self.fps = inst if self.fps == 0 else 0.9 * self.fps + 0.1 * inst


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    cfg = StreamConfig(
        width=args.width, height=args.height, fps=args.fps,
        laser_emitter=not args.no_emitter, use_filters=args.filters,
    )
    try:
        with RealSenseCamera(cfg) as cam:
            cam.print_info()
            app = LiveApp(cam, args)
            return app.run()
    except RuntimeError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
