"""RealSense D435i 实时测距与可视化工具包。"""
__version__ = "1.0.0"

__all__ = [
    "FrameBundle",
    "Intrinsics",
    "Measurement",
    "RealSenseCamera",
    "StreamConfig",
    "distance_between_pixels",
    "measure_at_pixel",
]

# 延迟导入: 保证未安装 pyrealsense2 时也能使用测距数学与可视化模块,
# 便于在没有相机的机器上运行单元测试。
_LAZY = {
    "FrameBundle": ("types", "FrameBundle"),
    "Intrinsics": ("types", "Intrinsics"),
    "Measurement": ("distance", "Measurement"),
    "measure_at_pixel": ("distance", "measure_at_pixel"),
    "distance_between_pixels": ("distance", "distance_between_pixels"),
    "RealSenseCamera": ("camera", "RealSenseCamera"),
    "StreamConfig": ("camera", "StreamConfig"),
}


def __getattr__(name: str):
    import importlib
    if name in _LAZY:
        mod_name, attr = _LAZY[name]
        value = getattr(importlib.import_module(f"{__name__}.{mod_name}"), attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
