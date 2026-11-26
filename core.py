# -*- coding: utf-8 -*-
"""
批量重命名 / 归档器 —— 核心逻辑

三条设计原则：
1. 所有操作先出"计划"（预览），确认后才真正动文件。
2. 每一次真实操作都写一份撤销记录，随时可以一键还原。
3. 遇到重名不覆盖，自动加 " (2)" 后缀。

命令行用法：
    python core.py rename 某文件夹 --prefix "合同_" --seq --apply
    python core.py archive 某文件夹 --dest 归档 --mode month --apply
    python core.py undo
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

# ---------- 常量 ----------

# Windows 文件名里不能出现的字符
ILLEGAL_CHARS = '\\/:*?"<>|'

# 归档时的文件分类
CATEGORIES = {
    "图片": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".tif", ".tiff", ".raw"},
    "文档": {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".pdf", ".txt", ".md", ".csv", ".rtf", ".wps"},
    "视频": {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".m4v", ".webm"},
    "音频": {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".wma"},
    "压缩包": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"},
}

ARCHIVE_MODES = {
    "按年份": "year",
    "按年/月": "month",
    "按年/月/日": "day",
    "按文件类型": "ext",
    "按年/月 + 类型": "date_ext",
}


# ---------- 数据结构 ----------


@dataclass
class RenameRule:
    """重命名规则，按固定顺序依次套用"""

    prefix: str = ""
    suffix: str = ""
    replace_from: str = ""
    replace_to: str = ""
    use_regex: bool = False
    add_date: bool = False
    date_format: str = "%Y%m%d"
    case: str = "none"          # none / lower / upper
    sequence: bool = False
    seq_start: int = 1
    seq_step: int = 1
    seq_digits: int = 3
    seq_sep: str = "_"
    tidy_spaces: bool = True     # 把连续空格压成一个，并去掉首尾空格


@dataclass
class PlanItem:
    source: str
    target: str
    status: str
    size: int = 0
    mtime: float = 0.0


# ---------- 文件扫描 ----------


def parse_patterns(text: str) -> list[str] | None:
    """把 "*.jpg;*.png" 这种文本解析成模式列表；空或"全部"返回 None"""
    if not text or not text.strip() or text.strip() in ("全部", "*", "*.*"):
        return None
    parts = re.split(r"[;,，；\s]+", text.strip())
    return [p for p in parts if p]


def list_files(
    folder: str,
    patterns: list[str] | None = None,
    recursive: bool = False,
    exclude: str | None = None,
) -> list[Path]:
    """列出文件夹里的文件（不含子文件夹本身）；exclude 用于跳过某个子目录（比如归档目标目录）"""
    root = Path(folder)
    if not root.exists() or not root.is_dir():
        raise ValueError(f"文件夹不存在：{folder}")

    exclude_path = None
    if exclude:
        exclude_path = str(Path(exclude).resolve())

    iterator = root.rglob("*") if recursive else root.glob("*")
    files = []
    for path in iterator:
        if not path.is_file():
            continue
        if path.name.startswith("~$"):      # 跳过 Office 临时文件
            continue
        if exclude_path and str(path.resolve()).startswith(exclude_path + os.sep):
            continue
        if patterns and not any(fnmatch.fnmatch(path.name.lower(), p.lower()) for p in patterns):
            continue
        files.append(path)

    # 按目录 + 文件名排序，保证每次预览顺序一致
    return sorted(files, key=lambda p: (str(p.parent).lower(), p.name.lower()))


def split_ext(name: str) -> tuple[str, str]:
    """拆主名和后缀，兼容 .tar.gz 这种双后缀"""
    lower = name.lower()
    if lower.endswith(".tar.gz"):
        return name[:-7], name[-7:]
    if lower.endswith(".tar.bz2"):
        return name[:-8], name[-8:]
    stem, ext = os.path.splitext(name)
    return stem, ext


def sanitize(name: str) -> str:
    """去掉 Windows 不允许的字符，避免改名失败"""
    cleaned = "".join("_" if ch in ILLEGAL_CHARS else ch for ch in name)
    cleaned = cleaned.strip().strip(".")
    return cleaned or "未命名"


def build_new_name(original: str, index: int, rule: RenameRule, mtime: float) -> str:
    """按规则生成新文件名（不含冲突处理）"""
    stem, ext = split_ext(original)

    # 1. 查找替换
    if rule.replace_from:
        if rule.use_regex:
            try:
                stem = re.sub(rule.replace_from, rule.replace_to, stem)
            except re.error as e:
                raise ValueError(f"正则表达式写错了：{e}")
        else:
            stem = stem.replace(rule.replace_from, rule.replace_to)

    # 2. 大小写
    if rule.case == "lower":
        stem = stem.lower()
    elif rule.case == "upper":
        stem = stem.upper()

    # 2.5 整理多余空格
    if rule.tidy_spaces:
        stem = re.sub(r"\s+", " ", stem).strip()

    # 3. 加日期前缀（默认用文件修改时间）
    if rule.add_date:
        date_text = datetime.fromtimestamp(mtime).strftime(rule.date_format or "%Y%m%d")
        stem = f"{date_text}_{stem}"

    # 4. 加前后缀
    stem = f"{rule.prefix}{stem}{rule.suffix}"

    # 5. 加序号
    if rule.sequence:
        number = rule.seq_start + index * rule.seq_step
        digits = max(1, int(rule.seq_digits))
        stem = f"{stem}{rule.seq_sep}{number:0{digits}d}"

    return sanitize(stem) + ext


# ---------- 重命名计划 ----------


def _unique_name(target: Path, used: set[str]) -> Path:
    """目标已存在或批次内重复时，自动加 " (2)"、" (3)" """
    stem, ext = split_ext(target.name)
    counter = 2
    while True:
        candidate = target.with_name(f"{stem} ({counter}){ext}")
        if str(candidate).lower() not in used and not candidate.exists():
            return candidate
        counter += 1


def plan_rename(files: list[Path], rule: RenameRule) -> list[PlanItem]:
    """生成重命名计划，不碰文件"""
    plans: list[PlanItem] = []
    used: set[str] = set()

    for index, path in enumerate(files):
        try:
            stat = path.stat()
        except OSError as e:
            plans.append(PlanItem(str(path), "", f"无法读取：{e}"))
            continue

        try:
            new_name = build_new_name(path.name, index, rule, stat.st_mtime)
        except ValueError as e:
            plans.append(PlanItem(str(path), "", f"规则错误：{e}", stat.st_size, stat.st_mtime))
            continue

        target = path.parent / new_name

        if new_name == path.name:
            status = "未变化"
        elif str(target).lower() in used or target.exists():
            target = _unique_name(target, used)
            status = "冲突，已自动改名"
        else:
            status = "正常"

        used.add(str(target).lower())
        plans.append(PlanItem(str(path), str(target), status, stat.st_size, stat.st_mtime))

    return plans


def execute_rename(plans: list[PlanItem]) -> tuple[int, int, list[dict]]:
    """真正执行重命名，返回（成功数, 失败数, 操作明细）"""
    ok = failed = 0
    items = []
    for item in plans:
        if item.status in ("未变化",) or item.status.startswith(("规则错误", "无法读取")):
            continue
        try:
            os.rename(item.source, item.target)
            ok += 1
            items.append({"from": item.source, "to": item.target})
        except OSError:
            failed += 1
    return ok, failed, items


# ---------- 归档计划 ----------


def _category_of(path: Path) -> str:
    ext = split_ext(path.name)[1].lower()
    for category, exts in CATEGORIES.items():
        if ext in exts:
            return category
    return "其他"


def plan_archive(
    files: list[Path],
    source_root: str,
    dest_root: str,
    mode: str,
) -> list[PlanItem]:
    """生成归档计划：文件 -> 目标路径"""
    source = Path(source_root)
    dest = Path(dest_root)
    plans: list[PlanItem] = []
    used: set[str] = set()

    for path in files:
        try:
            stat = path.stat()
        except OSError as e:
            plans.append(PlanItem(str(path), "", f"无法读取：{e}"))
            continue

        moment = datetime.fromtimestamp(stat.st_mtime)
        if mode == "year":
            sub = moment.strftime("%Y")
        elif mode == "month":
            sub = moment.strftime("%Y/%Y-%m")
        elif mode == "day":
            sub = moment.strftime("%Y/%Y-%m/%Y-%m-%d")
        elif mode == "ext":
            sub = _category_of(path)
        elif mode == "date_ext":
            sub = moment.strftime("%Y/%Y-%m") + "/" + _category_of(path)
        else:
            raise ValueError(f"不支持的归档方式：{mode}")

        # 保留原有的子目录结构，避免不同目录下的同名文件打起来
        try:
            relative = path.relative_to(source)
        except ValueError:
            relative = Path(path.name)

        target = dest / sub / relative

        if target.exists() or str(target).lower() in used:
            target = _unique_name(target, used)
            status = "冲突，已自动改名"
        else:
            status = "正常"

        used.add(str(target).lower())
        plans.append(PlanItem(str(path), str(target), status, stat.st_size, stat.st_mtime))

    return plans


def execute_archive(plans: list[PlanItem], copy_only: bool = False) -> tuple[int, int, list[dict]]:
    """执行归档。copy_only=True 时复制不移动，也不写撤销记录"""
    ok = failed = 0
    items = []
    for item in plans:
        if item.status.startswith(("无法读取",)) or not item.target:
            continue
        try:
            Path(item.target).parent.mkdir(parents=True, exist_ok=True)
            if copy_only:
                shutil.copy2(item.source, item.target)
            else:
                shutil.move(item.source, item.target)
                items.append({"from": item.source, "to": item.target})
            ok += 1
        except OSError:
            failed += 1
    return ok, failed, items


# ---------- 撤销 ----------


class UndoManager:
    """每次操作写一份 json 记录，支持"撤销上一批"""

    def __init__(self, base_dir: str | Path):
        self.dir = Path(base_dir) / "操作记录"
        self.dir.mkdir(parents=True, exist_ok=True)

    def save(self, kind: str, items: list[dict], note: str = "") -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        path = self.dir / f"{timestamp}_{kind}.json"
        payload = {
            "kind": kind,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "note": note,
            "items": items,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def last_record(self) -> Path | None:
        records = sorted(p for p in self.dir.glob("*.json") if p.suffix == ".json")
        return records[-1] if records else None

    def list_records(self) -> list[Path]:
        return sorted(self.dir.glob("*.json"))

    def undo_last(self) -> dict:
        """撤销最近一次操作"""
        record = self.last_record()
        if record is None:
            return {"restored": 0, "total": 0, "message": "没有可撤销的操作"}

        payload = json.loads(record.read_text(encoding="utf-8"))
        items = payload.get("items", [])
        restored = skipped = 0

        for item in reversed(items):
            source = Path(item["to"])      # 现在的位置
            target = Path(item["from"])    # 原来的位置
            if not source.exists():
                skipped += 1
                continue
            if target.exists():            # 原位置已被别的文件占用，放弃这一条
                skipped += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(source), str(target))
                restored += 1
            except OSError:
                skipped += 1

        # 标记为已撤销，避免下次重复撤销同一批
        record.rename(record.with_suffix(".json.undone"))
        return {
            "restored": restored,
            "skipped": skipped,
            "total": len(items),
            "time": payload.get("time", ""),
            "kind": payload.get("kind", ""),
        }


# ---------- 命令行入口（方便测试） ----------


def _default_undo_dir() -> Path:
    return Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description="批量重命名 / 归档")
    sub = parser.add_subparsers(dest="command")

    p_rename = sub.add_parser("rename", help="批量重命名")
    p_rename.add_argument("folder")
    p_rename.add_argument("--patterns", default="")
    p_rename.add_argument("--recursive", action="store_true")
    p_rename.add_argument("--prefix", default="")
    p_rename.add_argument("--suffix", default="")
    p_rename.add_argument("--replace-from", default="")
    p_rename.add_argument("--replace-to", default="")
    p_rename.add_argument("--regex", action="store_true")
    p_rename.add_argument("--case", default="none", choices=["none", "lower", "upper"])
    p_rename.add_argument("--date", action="store_true")
    p_rename.add_argument("--seq", action="store_true")
    p_rename.add_argument("--apply", action="store_true", help="不传只预览")

    p_archive = sub.add_parser("archive", help="批量归档")
    p_archive.add_argument("folder")
    p_archive.add_argument("--dest", required=True)
    p_archive.add_argument("--mode", default="month", choices=list(ARCHIVE_MODES.values()))
    p_archive.add_argument("--patterns", default="")
    p_archive.add_argument("--recursive", action="store_true")
    p_archive.add_argument("--copy", action="store_true")
    p_archive.add_argument("--apply", action="store_true")

    sub.add_parser("undo", help="撤销上一批操作")

    args = parser.parse_args()
    undo = UndoManager(_default_undo_dir())

    if args.command == "rename":
        patterns = parse_patterns(args.patterns)
        files = list_files(args.folder, patterns, args.recursive)
        rule = RenameRule(
            prefix=args.prefix, suffix=args.suffix,
            replace_from=args.replace_from, replace_to=args.replace_to,
            use_regex=args.regex, add_date=args.date, case=args.case,
            sequence=args.seq,
        )
        plans = plan_rename(files, rule)
        for p in plans:
            print(f"{p.status}\t{Path(p.source).name}  ->  {Path(p.target).name if p.target else '-'}")
        if args.apply:
            ok, failed, items = execute_rename(plans)
            if items:
                undo.save("rename", items)
            print(f"执行完成：成功 {ok}，失败 {failed}")

    elif args.command == "archive":
        patterns = parse_patterns(args.patterns)
        files = list_files(args.folder, patterns, args.recursive)
        plans = plan_archive(files, args.folder, args.dest, args.mode)
        for p in plans:
            print(f"{p.status}\t{Path(p.source).name}  ->  {p.target}")
        if args.apply:
            ok, failed, items = execute_archive(plans, copy_only=args.copy)
            if items:
                undo.save("archive", items)
            print(f"执行完成：成功 {ok}，失败 {failed}")

    elif args.command == "undo":
        print(undo.undo_last())

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
