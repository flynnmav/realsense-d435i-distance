"""RealSense D435i 实时测距程序入口。

用法示例:
    python main.py                       # 实时画面, 鼠标点击测距
    python main.py --record out.jsonl    # 实时画面 + 距离数据导出
    python main.py --target 640 360      # 固定测量某像素目标
"""
import sys

from d435i_distance.cli import main

if __name__ == "__main__":
    sys.exit(main())
