"""RealSense 深度相机的打开、取帧与设备信息。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
import pyrealsense2 as rs

from .types import FrameBundle, Intrinsics


@dataclass
class StreamConfig:
    """流参数配置。"""

    width: int = 1280
    height: int = 720
    fps: int = 30
    laser_emitter: bool = True   # 红外点阵投影, 提升弱纹理场景的深度质量
    use_filters: bool = False    # 深度后处理滤波(降噪/补洞), 会略微增加延迟

    @property
    def resolution(self) -> Tuple[int, int]:
        return self.width, self.height


class RealSenseCamera:
    """RealSense D435i 相机的上下文管理器封装。

    用法::

        with RealSenseCamera(StreamConfig(width=1280, height=720)) as cam:
            bundle = cam.wait_for_frames()   # 对齐后的彩色图 + 深度图
    """

    def __init__(self, config: Optional[StreamConfig] = None):
        self.config = config or StreamConfig()
        self._pipeline: Optional[rs.pipeline] = None
        self._profile = None
        self._align = rs.align(rs.stream.color)  # 深度对齐到彩色, 保证像素一一对应
        self._device: Optional[rs.device] = None
        self._depth_sensor = None
        self._depth_units: float = 0.001
        self._color_intrinsics: Optional[Intrinsics] = None
        self._filters: List = []
        self._started = False

    # ---------------- 生命周期 ----------------
    def __enter__(self) -> "RealSenseCamera":
        ctx = rs.context()
        devices = ctx.query_devices()
        if len(devices) == 0:
            raise RuntimeError(
                "未检测到 RealSense 设备。请检查: "
                "1) USB 线是否插好(建议 USB 3.0 接口); "
                "2) 设备是否被其他程序(如 RealSense Viewer)占用。"
            )
        self._device = devices[0]
        serial = self._device.get_info(rs.camera_info.serial_number)

        cfg = rs.config()
        cfg.enable_device(serial)
        cfg.enable_stream(rs.stream.depth, self.config.width, self.config.height,
                          rs.format.z16, self.config.fps)
        cfg.enable_stream(rs.stream.color, self.config.width, self.config.height,
                          rs.format.bgr8, self.config.fps)

        self._pipeline = rs.pipeline(ctx)
        self._profile = self._pipeline.start(cfg)
        self._started = True
        try:
            self._setup_sensor()
        except Exception:
            self._pipeline.stop()
            self._started = False
            raise

        # 预热若干帧, 等待自动曝光稳定
        for _ in range(15):
            self._pipeline.wait_for_frames(5000)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._pipeline is not None and self._started:
            self._pipeline.stop()
            self._started = False

    def _setup_sensor(self) -> None:
        self._depth_sensor = self._profile.get_device().first_depth_sensor()
        if self._depth_sensor.supports(rs.option.depth_units):
            self._depth_units = float(self._depth_sensor.get_option(rs.option.depth_units))
        try:
            if self._depth_sensor.supports(rs.option.emitter_enabled):
                self._depth_sensor.set_option(
                    rs.option.emitter_enabled, 1 if self.config.laser_emitter else 0)
        except RuntimeError:
            pass  # 个别固件上该选项不可写, 忽略

        if self.config.use_filters:
            self._filters = [
                rs.decimation_filter(2),
                rs.temporal_filter(0.4, 20.0, 3),
                rs.spatial_filter(0.5, 20.0, 2.0, 0.0),
            ]

        # 对齐后的深度图与彩色图共用同一像素坐标系, 使用彩色内参做反投影
        color_profile = self._profile.get_stream(rs.stream.color).as_video_stream_profile()
        self._color_intrinsics = Intrinsics.from_rs(color_profile.get_intrinsics())

    # ---------------- 设备信息 ----------------
    @property
    def serial_number(self) -> str:
        return self._device.get_info(rs.camera_info.serial_number)

    @property
    def device_info(self) -> dict:
        d = self._device
        return {
            "产品名称": d.get_info(rs.camera_info.name),
            "产品线": d.get_info(rs.camera_info.product_line),
            "序列号": d.get_info(rs.camera_info.serial_number),
            "固件版本": d.get_info(rs.camera_info.firmware_version),
            "USB 类型": d.get_info(rs.camera_info.usb_type_descriptor),
        }

    @property
    def depth_units(self) -> float:
        return self._depth_units

    @property
    def color_intrinsics(self) -> Optional[Intrinsics]:
        return self._color_intrinsics

    def print_info(self) -> None:
        print("=" * 60)
        print("RealSense 设备信息")
        for k, v in self.device_info.items():
            print(f"  {k:<12}: {v}")
        print(f"  深度单位     : {self._depth_units * 1000:.3f} mm")
        if self._color_intrinsics is not None:
            i = self._color_intrinsics
            print(f"  彩色内参     : fx={i.fx:.2f} fy={i.fy:.2f} "
                  f"ppx={i.ppx:.2f} ppy={i.ppy:.2f}")
        print("=" * 60)

    # ---------------- 取帧 ----------------
    def wait_for_frames(self, timeout_ms: int = 5000) -> FrameBundle:
        """等待并对齐一帧, 返回彩色图 + 深度图(像素一一对应)。"""
        if self._pipeline is None or not self._started:
            raise RuntimeError("相机未启动, 请通过 with 语句使用。")
        frames = self._pipeline.wait_for_frames(timeout_ms)
        aligned = self._align.process(frames)
        depth_frame = aligned.get_depth_frame()
        color_frame = aligned.get_color_frame()
        if not depth_frame or not color_frame:
            raise RuntimeError("取帧失败: 深度或彩色帧为空。")
        depth_frame = self._apply_filters(depth_frame)

        depth = np.asanyarray(depth_frame.get_data())
        color = np.asanyarray(color_frame.get_data())
        return FrameBundle(
            color=color,
            depth=depth,
            depth_units=self._depth_units,
            intrinsics=self._color_intrinsics,
            timestamp_ms=float(depth_frame.get_timestamp()),
            frame_number=int(depth_frame.get_frame_number()),
        )

    def _apply_filters(self, depth_frame):
        for f in self._filters:
            try:
                depth_frame = f.process(depth_frame)
            except RuntimeError:
                break
        return depth_frame
