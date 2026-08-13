"""OpenCV 可视化: 深度伪彩色、距离标注、HUD 信息栏。"""
from __future__ import annotations

from typing import Optional, Sequence, Tuple

import cv2
import numpy as np

from .distance import Measurement

FONT = cv2.FONT_HERSHEY_SIMPLEX
COLOR_CROSSHAIR_OK = (0, 220, 0)   # 有有效深度时的绿色十字线
COLOR_CROSSHAIR_BAD = (0, 0, 255)  # 无深度时的红色十字线


def colorize_depth(depth: np.ndarray, depth_units: float,
                   min_m: float = 0.3, max_m: float = 6.0) -> np.ndarray:
    """把 uint16 深度图映射为 JET 伪彩色 BGR 图, 越近越暖(红)、越远越冷(蓝)。"""
    d = depth.astype(np.float32) * depth_units
    disp = np.zeros(depth.shape[:2], dtype=np.uint8)
    valid = (d > 0) & (d <= max_m)
    if valid.any():
        scaled = (d[valid] - min_m) / (max_m - min_m) * 255.0
        disp[valid] = np.clip(scaled, 0, 255).astype(np.uint8)
    return cv2.applyColorMap(disp, cv2.COLORMAP_JET)


def draw_crosshair(img: np.ndarray, u: int, v: int,
                   color: Tuple[int, int, int],
                   size: int = 14, thickness: int = 2) -> None:
    cv2.line(img, (u - size, v), (u + size, v), color, thickness, cv2.LINE_AA)
    cv2.line(img, (u, v - size), (u, v + size), color, thickness, cv2.LINE_AA)
    cv2.circle(img, (u, v), size // 2, color, 1, cv2.LINE_AA)


def draw_text_box(img: np.ndarray, lines: Sequence[str],
                  anchor: Tuple[int, int] = (12, 30),
                  scale: float = 0.6, thickness: int = 1,
                  fg: Tuple[int, int, int] = (255, 255, 255),
                  bg: Tuple[int, int, int] = (0, 0, 0),
                  alpha: float = 0.55) -> None:
    """在图像上绘制半透明底色的多行文本(原地修改)。"""
    line_h = int(26 * scale) + 2
    widths = [cv2.getTextSize(line, FONT, scale, thickness)[0][0] for line in lines]
    box_w = max(widths) + 18
    box_h = line_h * len(lines) + 10
    x, y = anchor
    overlay = img.copy()
    cv2.rectangle(overlay, (x, y), (x + box_w, y + box_h), bg, -1)
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
    for i, line in enumerate(lines):
        cv2.putText(img, line, (x + 9, y + line_h * i + int(21 * scale)),
                    FONT, scale, fg, thickness, cv2.LINE_AA)


def draw_measurement(img: np.ndarray, u: int, v: int, m: Measurement,
                     color: Optional[Tuple[int, int, int]] = None) -> np.ndarray:
    """在图像上标注十字线与距离文本, 原地修改并返回。"""
    c = color or (COLOR_CROSSHAIR_OK if m.valid else COLOR_CROSSHAIR_BAD)
    draw_crosshair(img, int(u), int(v), c)
    if m.valid:
        lines = [
            f"Distance: {m.distance:.3f} m",
            f"Perp z  : {m.depth_z:.3f} m",
            f"3D: ({m.point[0]:.2f}, {m.point[1]:.2f}, {m.point[2]:.2f}) m",
        ]
    else:
        lines = ["Distance: N/A (no depth)"]
    h, w = img.shape[:2]
    tx = min(max(int(u) + 18, 4), max(w - 400, 4))
    ty = min(max(int(v) + 26, 4), max(h - 130, 4))
    draw_text_box(img, lines, anchor=(tx, ty))
    return img


def draw_hud(img: np.ndarray, fps: float, depth_units: float,
             recording: bool = False, paused: bool = False) -> np.ndarray:
    """左上角状态栏: FPS / 深度单位 / 录制与暂停状态。"""
    lines = [f"FPS: {fps:5.1f}", f"Depth unit: {depth_units * 1000:.2f} mm"]
    if recording:
        lines.append("[REC] recording...")
    if paused:
        lines.append("[PAUSED]")
    draw_text_box(img, lines)
    return img


def stack_views(color_view: np.ndarray, depth_view: np.ndarray,
                divider_color: Tuple[int, int, int] = (255, 255, 255)) -> np.ndarray:
    """左右拼接彩色视图与深度伪彩视图, 中间画分隔线。"""
    if color_view.shape != depth_view.shape:
        depth_view = cv2.resize(depth_view, (color_view.shape[1], color_view.shape[0]))
    h, w = depth_view.shape[:2]
    combined = np.hstack([color_view, depth_view])
    cv2.line(combined, (w - 1, 0), (w - 1, h), divider_color, 2)
    return combined
