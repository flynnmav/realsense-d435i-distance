# RealSense D435i 实时测距系统

基于 Intel RealSense **D435i** 深度相机的一整套实时测距方案: 实时显示彩色/深度画面, 鼠标点击目标即可在画面中标注**真实距离**, 并支持把测距数据以 CSV / JSONL 形式输出(传导)给下游程序。

## 功能特性

- 📷 实时彩色画面 + 深度伪彩画面同屏显示
- 🎯 鼠标点击任意目标, 画面实时标注**真实距离**(欧氏斜距)、垂直深度与 3D 坐标
- 📐 基于内参反投影计算光心到目标的真实距离, 而非深度图原始的"垂直深度"
- 💾 一键录制测距数据到 CSV / JSONL, 每帧一行, 供下游程序实时消费
- 🧹 邻域中位数采样抑制飞点噪声, 可选深度后处理滤波(decimation/temporal/spatial)
- ⌨️ 快捷键操作: 点击测距 / `c` 回中心 / `p` 暂停 / `r` 录制 / `q` 退出
- 🧪 无需相机硬件即可运行的单元测试 + 无 GUI 冒烟测试脚本
- 🔁 GitHub Actions 自动跑单元测试(Python 3.10/3.11/3.12)

## 测距原理

深度相机每个像素输出的是**垂直深度 Z**(沿光轴方向的距离), 而不是相机到目标的直线距离; 当目标不在画面正中心时, 两者差异明显。本系统利用针孔相机内参把像素反投影成 3D 点, 再求欧氏距离:

```text
X = (u - ppx) * Z / fx
Y = (v - ppy) * Z / fy
distance = sqrt(X^2 + Y^2 + Z^2)
```

其中 `fx, fy, ppx, ppy` 为相机内参(程序启动时自动读取, 无需手工标定), `(u, v)` 为目标像素坐标。

## 环境要求

- 硬件: Intel RealSense D435i, 建议 USB 3.0 接口
- 系统: Windows 10/11, Ubuntu 20.04 / 22.04
- Python: **3.9 ~ 3.11**(pyrealsense2 官方 wheel 对 3.11 支持最完整; 3.12+ 视 pyrealsense2 版本而定)

## 安装

### Windows

```bash
# 1. 创建虚拟环境(以 Python 3.11 为例)
python -m venv .venv
.venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt
```

> pyrealsense2 的 Windows wheel 自带 librealsense 动态库, 无需额外安装 SDK。

### Linux (Ubuntu)

```bash
# 先按 Intel 官方说明安装 librealsense2 系统库, 再:
pip install -r requirements.txt
```

## 快速开始

1. 插上 D435i(USB 3.0), 先确认设备可用:

```bash
python scripts/check_camera.py
```

2. 启动实时测距:

```bash
python main.py
```

3. 在彩色画面上**鼠标左键点击**任意目标 → 画面即刻标注十字线与距离文本; 右侧为深度伪彩图(越红越近, 越蓝越远)。

4. 按 `r` 开始录制, 再按 `r` 停止 → 数据默认写入 `records/distance_YYYYMMDD_HHMMSS.csv`; 按 `q` 退出。

### 快捷键

| 按键 | 功能 |
| --- | --- |
| 鼠标左键 | 选择测距目标点 |
| c | 目标点回到画面中心 |
| p | 暂停 / 继续画面 |
| r | 开始 / 停止录制测距数据 |
| q / Esc | 退出 |

## 命令行参数

| 参数 | 说明 | 默认 |
| --- | --- | --- |
| `--width / --height` | 彩色/深度流分辨率 | 1280 x 720 |
| `--fps` | 流帧率 | 30 |
| `--target X Y` | 初始目标像素坐标 | 画面中心 |
| `--min-depth / --max-depth` | 深度伪彩显示范围(米) | 0.3 / 6.0 |
| `--record PATH` | 启动即录制, PATH 以 .csv 或 .jsonl 结尾 | 无 |
| `--filters` | 启用深度后处理滤波(降噪/补洞) | 关闭 |
| `--no-emitter` | 关闭红外点阵投影 | 开启 |
| `--print-interval` | 控制台打印测距间隔(秒) | 1.0 |
| `--median-radius` | 测距邻域中位数半径(像素) | 2 |
| `--config` | YAML 配置文件 | config/config.yaml |

示例:

```bash
# 录制 JSONL 数据(每帧一行, 便于下游程序实时读取)
python main.py --record out.jsonl

# 固定测量某像素并输出 CSV
python main.py --target 640 360 --record dist.csv
```

## 数据输出(距离传导)

录制文件每帧一行。CSV 表头: `frame, timestamp_ms, u, v, depth_z_m, distance_m, x_m, y_m, z_m`。

JSONL 每行示例:

```json
{"frame": 123, "timestamp_ms": 45678.9, "u": 640, "v": 360,
 "valid": true, "depth_z_m": 1.234, "distance_m": 1.241,
 "point_m": [0.11, -0.02, 1.234]}
```

字段说明:

- `depth_z_m`: 垂直深度(沿光轴方向, 米)
- `distance_m`: **真实距离**(相机光心到目标点的欧氏距离, 米)
- `point_m`: 相机坐标系 3D 点(米), +x 向右 / +y 向下 / +z 向前

控制台同时按 `--print-interval` 周期打印测距结果, 可直接重定向/管道给其他进程。

## 作为库使用

```python
from d435i_distance import RealSenseCamera, StreamConfig, measure_at_pixel

with RealSenseCamera(StreamConfig(width=1280, height=720)) as cam:
    bundle = cam.wait_for_frames()   # 对齐后的彩色图 + 深度图
    m = measure_at_pixel(bundle.depth, 640, 360,
                         bundle.intrinsics, bundle.depth_units)
    print(m.format_text())           # 真实距离 / 垂直深度 / 3D 坐标
```

## 项目结构

```text
.
├── main.py                    # 程序入口: 实时测距可视化
├── config/config.yaml         # 默认参数(分辨率/显示范围/滤波半径)
├── d435i_distance/
│   ├── camera.py              # 相机打开/取帧/设备信息(深度对齐彩色)
│   ├── distance.py            # 测距核心: 反投影 + 真实距离
│   ├── annotator.py           # OpenCV 可视化: 伪彩/十字线/距离标注/HUD
│   ├── types.py               # 内参与帧数据结构
│   └── cli.py                 # 命令行入口 + 交互窗口 + 数据录制
├── scripts/
│   ├── check_camera.py        # 设备连接检查
│   └── smoke_test.py          # 无 GUI 冒烟测试(连续测距统计)
└── tests/                     # 无需相机的单元测试
```

## 测试

```bash
# 单元测试(测距数学与可视化函数, 不需要相机)
python -m unittest discover -s tests -v

# 冒烟测试(需要连接相机, 无窗口, 输出各点测距统计)
python scripts/smoke_test.py --frames 30
```

## 常见问题

- **提示"未检测到 RealSense 设备"**: 检查 USB 连接(需 USB 3.0)、是否被 RealSense Viewer 等其他程序占用; 更换数据线/接口重试。
- **画面中部分区域无深度(显示 N/A)**: 强反光、玻璃/纯黑表面、超出量程(约 0.3~6 m)都会导致无深度; 弱纹理场景建议保持红外点阵开启。
- **距离精度**: D435i 深度误差通常为量程的 1% 以内(近距离约毫米级), 目标过远或反光材质时变差; 多次测量取均值可进一步降噪。
- **D435i 与 D435 的区别**: D435i 额外内置 IMU(BMI055)。本系统当前只用深度+彩色, 两者均可直接运行。

## License

MIT © 2026 Liu Leyan
