# -*- coding: utf-8 -*-
"""
批量重命名 / 归档器 —— 图形界面
两个标签页：重命名、归档；底部共用一份日志和"撤销上一批"。
"""

import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import core

APP_TITLE = "批量重命名 / 归档器 v1.0"


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.rename_plans: list[core.PlanItem] = []
        self.archive_plans: list[core.PlanItem] = []
        self.undo = core.UndoManager(app_dir())

        root.title(APP_TITLE)
        root.geometry("1040x820")
        root.minsize(920, 760)

        self._build_ui()

    # ---------------- 界面骨架 ----------------
    def _build_ui(self):
        header = ttk.Frame(self.root)
        header.pack(fill="x", padx=12, pady=(10, 0))

        title_box = ttk.Frame(header)
        title_box.pack(side="left", anchor="n")
        ttk.Label(title_box, text="批量重命名 / 归档器", font=("Microsoft YaHei", 15, "bold")).pack(anchor="w")
        ttk.Label(
            title_box,
            text="先预览、再执行；每次操作都能一键撤销。",
            foreground="#666666",
        ).pack(anchor="w", pady=(2, 0))

        # 撤销按钮固定在右上角，不跟日志挤在一起，窗口缩小也不会被挤出去
        self.undo_btn = ttk.Button(header, text="撤销上一批操作", command=self.do_undo)
        self.undo_btn.pack(side="right", anchor="n", pady=(4, 0))
        ttk.Label(header, text="操作记录：程序目录 / 操作记录/", foreground="#888888").pack(
            side="right", anchor="n", padx=(0, 10), pady=(10, 0)
        )

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=8)

        self.rename_tab = ttk.Frame(self.notebook)
        self.archive_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.rename_tab, text="  批量重命名  ")
        self.notebook.add(self.archive_tab, text="  批量归档  ")

        self._build_rename_tab(self.rename_tab)
        self._build_archive_tab(self.archive_tab)
        self._build_log_area()

    def _build_log_area(self):
        frame = ttk.LabelFrame(self.root, text=" 日志 ")
        frame.pack(fill="x", padx=12, pady=(0, 10))

        self.log_text = tk.Text(frame, height=5, wrap="word", font=("Consolas", 9), state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=8, pady=6)

    # ---------------- 重命名页 ----------------
    def _build_rename_tab(self, parent):
        pad = {"padx": 8, "pady": 4}

        # 文件夹
        row = ttk.Frame(parent)
        row.pack(fill="x", **pad)
        ttk.Label(row, text="文件夹").pack(side="left")
        self.var_rn_folder = tk.StringVar()
        ttk.Entry(row, textvariable=self.var_rn_folder).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(row, text="浏览…", command=lambda: self.pick_folder(self.var_rn_folder)).pack(side="left")
        self.var_rn_recursive = tk.BooleanVar(value=False)
        ttk.Checkbutton(row, text="包含子文件夹", variable=self.var_rn_recursive).pack(side="left", padx=8)

        row2 = ttk.Frame(parent)
        row2.pack(fill="x", **pad)
        ttk.Label(row2, text="只处理").pack(side="left")
        self.var_rn_patterns = tk.StringVar(value="全部")
        ttk.Entry(row2, textvariable=self.var_rn_patterns, width=30).pack(side="left", padx=6)
        ttk.Label(row2, text='例：*.jpg;*.png（留“全部”则处理所有文件）', foreground="#888888").pack(side="left")

        # 规则
        rule_frame = ttk.LabelFrame(parent, text=" 命名规则（按下面的顺序依次套用） ")
        rule_frame.pack(fill="x", **pad)

        r1 = ttk.Frame(rule_frame)
        r1.pack(fill="x", padx=8, pady=4)
        ttk.Label(r1, text="前缀").pack(side="left")
        self.var_prefix = tk.StringVar()
        ttk.Entry(r1, textvariable=self.var_prefix, width=14).pack(side="left", padx=4)
        ttk.Label(r1, text="后缀").pack(side="left")
        self.var_suffix = tk.StringVar()
        ttk.Entry(r1, textvariable=self.var_suffix, width=14).pack(side="left", padx=4)
        self.var_add_date = tk.BooleanVar(value=False)
        ttk.Checkbutton(r1, text="加日期前缀", variable=self.var_add_date).pack(side="left", padx=(12, 2))
        self.var_date_format = tk.StringVar(value="%Y%m%d")
        ttk.Combobox(
            r1, textvariable=self.var_date_format, width=14, state="readonly",
            values=["%Y%m%d", "%Y-%m-%d", "%Y%m%d_%H%M", "%y%m%d"],
        ).pack(side="left")

        r2 = ttk.Frame(rule_frame)
        r2.pack(fill="x", padx=8, pady=4)
        ttk.Label(r2, text="查找").pack(side="left")
        self.var_find = tk.StringVar()
        ttk.Entry(r2, textvariable=self.var_find, width=16).pack(side="left", padx=4)
        ttk.Label(r2, text="替换为").pack(side="left")
        self.var_replace = tk.StringVar()
        ttk.Entry(r2, textvariable=self.var_replace, width=16).pack(side="left", padx=4)
        self.var_regex = tk.BooleanVar(value=False)
        ttk.Checkbutton(r2, text="用正则", variable=self.var_regex).pack(side="left", padx=(10, 2))
        ttk.Label(r2, text="大小写").pack(side="left", padx=(12, 2))
        self.var_case = tk.StringVar(value="不转换")
        ttk.Combobox(
            r2, textvariable=self.var_case, width=10, state="readonly",
            values=["不转换", "转小写", "转大写"],
        ).pack(side="left")

        r3 = ttk.Frame(rule_frame)
        r3.pack(fill="x", padx=8, pady=(4, 8))
        self.var_seq = tk.BooleanVar(value=False)
        ttk.Checkbutton(r3, text="加序号", variable=self.var_seq).pack(side="left")
        ttk.Label(r3, text="起始").pack(side="left", padx=(8, 2))
        self.var_seq_start = tk.StringVar(value="1")
        ttk.Spinbox(r3, from_=0, to=999999, textvariable=self.var_seq_start, width=6).pack(side="left")
        ttk.Label(r3, text="位数").pack(side="left", padx=(8, 2))
        self.var_seq_digits = tk.StringVar(value="3")
        ttk.Spinbox(r3, from_=1, to=10, textvariable=self.var_seq_digits, width=4).pack(side="left")
        ttk.Label(r3, text="步长").pack(side="left", padx=(8, 2))
        self.var_seq_step = tk.StringVar(value="1")
        ttk.Spinbox(r3, from_=1, to=1000, textvariable=self.var_seq_step, width=4).pack(side="left")
        ttk.Label(r3, text="分隔符").pack(side="left", padx=(8, 2))
        self.var_seq_sep = tk.StringVar(value="_")
        ttk.Entry(r3, textvariable=self.var_seq_sep, width=4).pack(side="left")
        self.var_tidy = tk.BooleanVar(value=True)
        ttk.Checkbutton(r3, text="整理多余空格", variable=self.var_tidy).pack(side="left", padx=(12, 0))

        # 按钮
        btns = ttk.Frame(parent)
        btns.pack(fill="x", **pad)
        ttk.Button(btns, text="预览改名结果", command=self.preview_rename).pack(side="left")
        self.rn_exec_btn = ttk.Button(btns, text="执行重命名", command=self.execute_rename, state="disabled")
        self.rn_exec_btn.pack(side="left", padx=8)
        ttk.Label(btns, text="执行前必须先生成预览", foreground="#888888").pack(side="left", padx=6)

        # 预览表
        table_wrap = ttk.Frame(parent)
        table_wrap.pack(fill="both", expand=True, **pad)
        self.rn_tree = self._make_tree(table_wrap, ("编号", "原文件名", "新文件名", "状态"),
                                      (60, 300, 360, 130))

    # ---------------- 归档页 ----------------
    def _build_archive_tab(self, parent):
        pad = {"padx": 8, "pady": 4}

        row = ttk.Frame(parent)
        row.pack(fill="x", **pad)
        ttk.Label(row, text="源文件夹").pack(side="left")
        self.var_ar_source = tk.StringVar()
        ttk.Entry(row, textvariable=self.var_ar_source).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(row, text="浏览…", command=lambda: self.pick_folder(self.var_ar_source)).pack(side="left")
        self.var_ar_recursive = tk.BooleanVar(value=True)
        ttk.Checkbutton(row, text="包含子文件夹", variable=self.var_ar_recursive).pack(side="left", padx=8)

        row2 = ttk.Frame(parent)
        row2.pack(fill="x", **pad)
        ttk.Label(row2, text="目标文件夹").pack(side="left")
        self.var_ar_dest = tk.StringVar()
        ttk.Entry(row2, textvariable=self.var_ar_dest).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(row2, text="浏览…", command=lambda: self.pick_folder(self.var_ar_dest)).pack(side="left")

        row3 = ttk.Frame(parent)
        row3.pack(fill="x", **pad)
        ttk.Label(row3, text="归档方式").pack(side="left")
        self.var_ar_mode = tk.StringVar(value="按年/月")
        ttk.Combobox(
            row3, textvariable=self.var_ar_mode, width=16, state="readonly",
            values=list(core.ARCHIVE_MODES.keys()),
        ).pack(side="left", padx=6)
        ttk.Label(row3, text="只处理").pack(side="left", padx=(12, 2))
        self.var_ar_patterns = tk.StringVar(value="全部")
        ttk.Entry(row3, textvariable=self.var_ar_patterns, width=26).pack(side="left")
        self.var_ar_copy = tk.BooleanVar(value=False)
        ttk.Checkbutton(row3, text="只复制不移动", variable=self.var_ar_copy).pack(side="left", padx=10)

        hint = ttk.Label(
            parent,
            text="按日期归档用的是文件的“修改时间”；保留原有子目录结构，重名自动加 (2)。",
            foreground="#888888",
        )
        hint.pack(anchor="w", padx=8)

        btns = ttk.Frame(parent)
        btns.pack(fill="x", **pad)
        ttk.Button(btns, text="预览归档结果", command=self.preview_archive).pack(side="left")
        self.ar_exec_btn = ttk.Button(btns, text="执行归档", command=self.execute_archive, state="disabled")
        self.ar_exec_btn.pack(side="left", padx=8)

        table_wrap = ttk.Frame(parent)
        table_wrap.pack(fill="both", expand=True, **pad)
        self.ar_tree = self._make_tree(table_wrap, ("编号", "文件", "将移动到", "状态"),
                                       (60, 280, 460, 130))

    def _make_tree(self, parent, columns, widths):
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=10)
        for col, width in zip(columns, widths):
            tree.heading(col, text=col)
            tree.column(col, width=width, anchor="w")
        scroll = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        tree.tag_configure("warn", foreground="#b36b00")
        tree.tag_configure("skip", foreground="#999999")
        return tree

    # ---------------- 公共操作 ----------------
    def pick_folder(self, var: tk.StringVar):
        folder = filedialog.askdirectory(title="选择文件夹")
        if folder:
            var.set(folder)

    def _log(self, message: str):
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def _fill_tree(self, tree, plans, source_of, target_of):
        tree.delete(*tree.get_children())
        for index, item in enumerate(plans, start=1):
            tags = ()
            if "冲突" in item.status:
                tags = ("warn",)
            elif item.status in ("未变化",):
                tags = ("skip",)
            tree.insert("", "end", values=(index, source_of(item), target_of(item), item.status), tags=tags)

    # ---------------- 重命名 ----------------
    def _collect_rule(self) -> core.RenameRule:
        def to_int(value, default):
            try:
                return int(str(value).strip())
            except (TypeError, ValueError):
                return default

        case_map = {"不转换": "none", "转小写": "lower", "转大写": "upper"}
        return core.RenameRule(
            prefix=self.var_prefix.get(),
            suffix=self.var_suffix.get(),
            replace_from=self.var_find.get(),
            replace_to=self.var_replace.get(),
            use_regex=self.var_regex.get(),
            add_date=self.var_add_date.get(),
            date_format=self.var_date_format.get() or "%Y%m%d",
            case=case_map.get(self.var_case.get(), "none"),
            sequence=self.var_seq.get(),
            seq_start=to_int(self.var_seq_start.get(), 1),
            seq_step=to_int(self.var_seq_step.get(), 1),
            seq_digits=to_int(self.var_seq_digits.get(), 3),
            seq_sep=self.var_seq_sep.get(),
            tidy_spaces=self.var_tidy.get(),
        )

    def preview_rename(self):
        folder = self.var_rn_folder.get().strip()
        if not folder:
            messagebox.showwarning("还没选文件夹", "请先选择要处理的文件夹。")
            return
        try:
            files = core.list_files(folder, core.parse_patterns(self.var_rn_patterns.get()),
                                    self.var_rn_recursive.get())
        except ValueError as e:
            messagebox.showerror("读取失败", str(e))
            return

        if not files:
            messagebox.showinfo("没有文件", "这个文件夹里没有符合条件的文件。")
            return

        self.rename_plans = core.plan_rename(files, self._collect_rule())
        self._fill_tree(
            self.rn_tree, self.rename_plans,
            lambda item: Path(item.source).name,
            lambda item: Path(item.target).name if item.target else "-",
        )

        changed = sum(1 for p in self.rename_plans if p.status in ("正常", "冲突，已自动改名"))
        conflicts = sum(1 for p in self.rename_plans if "冲突" in p.status)
        errors = sum(1 for p in self.rename_plans if p.status.startswith(("规则错误", "无法读取")))
        unchanged = sum(1 for p in self.rename_plans if p.status == "未变化")

        self._log(f"预览：共 {len(self.rename_plans)} 个文件，将改名 {changed} 个，未变化 {unchanged} 个，冲突 {conflicts} 个，错误 {errors} 个")
        self.rn_exec_btn.configure(state="normal" if changed else "disabled")

    def execute_rename(self):
        if not self.rename_plans:
            return
        changed = [p for p in self.rename_plans if p.status in ("正常", "冲突，已自动改名")]
        if not changed:
            messagebox.showinfo("无需处理", "没有需要改名的文件。")
            return
        if not messagebox.askokcancel("确认执行", f"将重命名 {len(changed)} 个文件。\n执行后可以点“撤销上一批操作”还原。"):
            return

        ok, failed, items = core.execute_rename(self.rename_plans)
        if items:
            record = self.undo.save("rename", items)
            self._log(f"已写入撤销记录：{record.name}")
        self._log(f"重命名完成：成功 {ok} 个，失败 {failed} 个")
        messagebox.showinfo("完成", f"成功重命名 {ok} 个文件，失败 {failed} 个。")
        self.rn_exec_btn.configure(state="disabled")
        self.rename_plans = []

    # ---------------- 归档 ----------------
    def preview_archive(self):
        source = self.var_ar_source.get().strip()
        dest = self.var_ar_dest.get().strip()
        if not source:
            messagebox.showwarning("还没选文件夹", "请先选择源文件夹。")
            return
        if not dest:
            dest = str(Path(source) / "已归档")
            self.var_ar_dest.set(dest)

        try:
            # 跳过目标目录本身，避免“已归档”里的文件被反复归档
            files = core.list_files(
                source, core.parse_patterns(self.var_ar_patterns.get()),
                self.var_ar_recursive.get(), exclude=dest,
            )
        except ValueError as e:
            messagebox.showerror("读取失败", str(e))
            return
        if not files:
            messagebox.showinfo("没有文件", "源文件夹里没有符合条件的文件。")
            return

        mode = core.ARCHIVE_MODES.get(self.var_ar_mode.get(), "month")
        try:
            self.archive_plans = core.plan_archive(files, source, dest, mode)
        except ValueError as e:
            messagebox.showerror("归档失败", str(e))
            return

        def _target_text(item):
            if not item.target:
                return "-"
            try:
                return str(Path(item.target).relative_to(dest))
            except ValueError:
                return item.target

        self._fill_tree(
            self.ar_tree, self.archive_plans,
            lambda item: Path(item.source).name,
            _target_text,
        )
        conflicts = sum(1 for p in self.archive_plans if "冲突" in p.status)
        self._log(f"预览：共 {len(self.archive_plans)} 个文件将归档到 {dest}，其中重名自动改名 {conflicts} 个")
        self.ar_exec_btn.configure(state="normal")

    def execute_archive(self):
        if not self.archive_plans:
            return
        copy_only = self.var_ar_copy.get()
        tip = "将复制文件（原文件保留，此操作不可撤销）。" if copy_only else "将移动文件（可撤销）。"
        if not messagebox.askokcancel("确认执行", f"共 {len(self.archive_plans)} 个文件。{tip}\n是否继续？"):
            return

        ok, failed, items = core.execute_archive(self.archive_plans, copy_only=copy_only)
        if items:
            record = self.undo.save("archive", items)
            self._log(f"已写入撤销记录：{record.name}")
        self._log(f"归档完成：成功 {ok} 个，失败 {failed} 个")
        messagebox.showinfo("完成", f"成功归档 {ok} 个文件，失败 {failed} 个。")
        self.ar_exec_btn.configure(state="disabled")
        self.archive_plans = []

    # ---------------- 撤销 ----------------
    def do_undo(self):
        if not messagebox.askokcancel("确认撤销", "将把上一批文件还原到原来的位置，是否继续？"):
            return
        result = self.undo.undo_last()
        if result.get("total", 0) == 0:
            messagebox.showinfo("没有记录", "还没有可撤销的操作。")
            return
        self._log(f"撤销 {result.get('kind')}（{result.get('time')}）：还原 {result['restored']} 个，跳过 {result['skipped']} 个")
        messagebox.showinfo(
            "撤销完成",
            f"还原 {result['restored']} 个文件，跳过 {result['skipped']} 个。\n"
            "（跳过通常是因为原位置已有同名文件，或文件已被挪走）",
        )


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
