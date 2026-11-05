#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
写权限前置探测 —— 长任务开跑前必须先跑这个。

背景（2026-11-03 查清）：
    DSH 在本机 Windows 上对 **pwsh 子进程** 施加了受限令牌，只放行少数路径；
    而 DSH 自身的文件工具（write/edit）走主进程，整个工作区可写。
    两套通道权限不同 ⇒ 「write 工具能写」不代表「python 脚本能写」。

    pwsh 子进程实测（2026-11-03）：
      可写   = 工作区根、tools/、.acl-reports/、config.yaml
      不可写 = data/、data/{年份}年/、src/、backtest/、trade_decision/、local/、
               files/、signal/、docs/、.reasonix/

历史事故：
    曾有一个跑 1~2 小时的脚本，结果最后写 data/ 时被拒，整轮计算白费；
    另有一次在确认副本成功前删掉了源数据，导致 35,032 行重建结果丢失。

用法：
    # 探测默认关键目录
    python tools/probe_write.py

    # 指定输出目标（脚本里最常用）
    python tools/probe_write.py --target data/recon.csv

    # 作为其它脚本的前置门槛（不可写时退出码 1）
    python tools/probe_write.py --target data/out.json || echo "先提权或换目录"

退出码：
    0 = 所有被检目标可写
    1 = 存在不可写目标（脚本应中止，或改用 --fallback 指定的可写目录）
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

# 项目根 = 本文件上一级
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def is_writable(dirpath: Path) -> tuple[bool, str]:
    """用 1 字节真实写入探测目录可写性（比 os.access 可靠，能绕过 ACL 缓存）。"""
    try:
        dirpath.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return False, f"无法创建目录: {e}"

    probe = dirpath / f".__probe_{os.getpid()}.tmp"
    try:
        probe.write_bytes(b"x")
        probe.unlink()
        return True, "可写"
    except OSError as e:
        return False, str(e)
    finally:
        try:
            if probe.exists():
                probe.unlink()
        except OSError:
            pass


def default_targets() -> list[Path]:
    """默认探测清单：写数据最可能用到的目录。"""
    items = [
        PROJECT_ROOT,
        PROJECT_ROOT / "tools",
        PROJECT_ROOT / "data",
        PROJECT_ROOT / "src",
    ]
    # data 下的年份目录
    data_dir = PROJECT_ROOT / "data"
    if data_dir.exists():
        for child in sorted(data_dir.iterdir()):
            if child.is_dir() and child.name.endswith("年"):
                items.append(child)
    return items


def pick_fallback(preferred: Path) -> Path | None:
    """preferred 不可写时，返回一个可写的替代目录（用于「先落盘再搬运」策略）。"""
    candidates = [
        PROJECT_ROOT / "_out",      # 工作区根下，pwsh 可写
        PROJECT_ROOT / "tools",
        Path(tempfile.gettempdir()) / "stockbot_out",
    ]
    for c in candidates:
        if c.resolve() == preferred.resolve():
            continue
        ok, _ = is_writable(c)
        if ok:
            return c
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="探测 pwsh 子进程对各目录的写权限")
    ap.add_argument("--target", action="append", default=[],
                    help="额外要探测的文件或目录路径，可重复")
    ap.add_argument("--fallback", action="store_true",
                    help="对不可写的目标，额外推荐一个可写的替代目录")
    ap.add_argument("--quiet", action="store_true", help="只输出失败项")
    args = ap.parse_args()

    targets: list[Path] = list(default_targets())
    for t in args.target:
        p = Path(t)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        # 探测的是父目录（文件本身可能还不存在）
        targets.append(p.parent if p.suffix or not p.exists() else p)

    # 去重保序
    seen: set[str] = set()
    uniq: list[Path] = []
    for t in targets:
        key = str(t.resolve()).lower()
        if key not in seen:
            seen.add(key)
            uniq.append(t)

    bad: list[Path] = []
    if not args.quiet:
        print(f"项目根: {PROJECT_ROOT}")
        print(f"{'目录':<48} {'结果':<10} 备注")
        print("-" * 80)

    for t in uniq:
        ok, msg = is_writable(t)
        try:
            shown = str(t.relative_to(PROJECT_ROOT)) or "."
        except ValueError:
            shown = str(t)
        if not ok:
            bad.append(t)
            print(f"{shown:<48} {'❌ 不可写':<10} {msg[:40]}")
        elif not args.quiet:
            print(f"{shown:<48} {'✅ 可写':<10}")

    print()
    if bad:
        print(f"⚠️  {len(bad)} 个目录不可写（pwsh 子进程）：")
        for b in bad:
            try:
                shown = str(b.relative_to(PROJECT_ROOT)) or "."
            except ValueError:
                shown = str(b)
            print(f"     - {shown}")
            if args.fallback:
                fb = pick_fallback(b)
                if fb:
                    print(f"       → 可先落盘到: {fb}")
        print()
        print("对策（三选一）：")
        print("  1) 长任务改用一次性 danger-full-access 运行（推荐，最省事）")
        print("  2) 先写可写目录，成功后再搬运到目标目录")
        print("  3) 文本结果改用 DSH 的 write 工具写（无需提权；但图片/二进制不行）")
        return 1

    print("✅ 全部可写，可安全开跑")
    return 0


if __name__ == "__main__":
    sys.exit(main())
