# -*- coding: utf-8 -*-
"""
生成测试用的示例文件（文件名故意弄乱、修改时间打散）
运行：python generate_samples.py
"""
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

base = Path(__file__).parent / "示例文件"
if base.exists():
    shutil.rmtree(base)
base.mkdir(parents=True)
(base / "子文件夹").mkdir()

# (文件名, 修改日期) —— 故意带空格、括号、"副本"、大小写混乱
samples = [
    (" IMG 0001 .JPG", "2026-08-03"),
    ("IMG 0002.JPG", "2026-08-21"),
    ("合同 副本 (1).docx", "2026-09-05"),
    ("合同 副本 (2).docx", "2026-09-18"),
    ("会议纪要 2026.11.20.docx", "2026-11-20"),
    ("scan001.PDF", "2026-10-11"),
    ("产品视频 final.mp4", "2026-10-30"),
    ("报价单.xlsx", "2026-10-30"),
    ("背景音乐.mp3", "2026-11-02"),
    ("打包资料.zip", "2026-11-15"),
]

for name, day in samples:
    path = base / name
    path.write_text(f"这是测试文件：{name}", encoding="utf-8")
    stamp = time.mktime(datetime.strptime(day + " 10:00:00", "%Y-%m-%d %H:%M:%S").timetuple())
    os.utime(path, (stamp, stamp))

note = base / "子文件夹" / "notes.txt"
note.write_text("子文件夹里的文件", encoding="utf-8")
os.utime(note, (time.time(), time.time()))

print(f"示例文件已生成：{base}（共 {len(list(base.rglob('*')))} 项）")
