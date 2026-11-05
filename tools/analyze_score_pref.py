#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析重建结果：「综合分 60 且 优选分 13」的平均收益是否为正。

数据源：tools/recon_pool_score.py 产出的 CSV
        （date,code,close,ma20,vol_ratio,ret_pct,score,pref,ret2d,buy_open,sell_close）

统计纪律（项目约定，务必遵守）：
  ① 必须先**按日聚合**再跨天检验 —— 个股级 t 会把同天高度相关的股票当独立样本，显著性虚高
  ② 必须同时报「剔除 top3 后」收益 —— 防少数极值冒充规律
  ③ 优选分是离线重算的，约半数股票与生产值差 3-5 分 → 「pref==13」是**近似**口径，
     必须同时给 pref∈[12,14] 的稳健性对照

用法：
    python tools/analyze_score_pref.py --csv data/recon_pool_score_20260506_20261103.csv
"""

from __future__ import annotations

import argparse
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def load_csv(path: Path):
    import csv
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            def fnum(k):
                v = r.get(k, "")
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return None
            rec = dict(date=r["date"], code=r["code"], score=fnum("score"),
                       pref=fnum("pref"), ret=fnum("ret2d"),
                       vol_ratio=fnum("vol_ratio"))
            rows.append(rec)
    return rows


def day_agg(rows) -> dict[str, list[float]]:
    """按日聚合：{date: [每只票的收益]}"""
    d = defaultdict(list)
    for r in rows:
        if r["ret"] is not None:
            d[r["date"]].append(r["ret"])
    return d


def stat_block(rows, label, tol_top=3):
    """同时给个股级与按日聚级的统计，并报剔除 top3 后"""
    rets = [r["ret"] for r in rows if r["ret"] is not None]
    n = len(rets)
    if n == 0:
        print(f"  {label:<28} n=0  —— 无样本")
        return None

    m = sum(rets) / n
    win = sum(1 for x in rets if x > 0) / n * 100

    # 个股级 t（仅供参考，不采信）
    sd = st.stdev(rets) if n > 1 else 0.0
    t_ind = m / (sd / n ** 0.5) if sd > 0 else 0.0

    # 按日聚合
    days = day_agg(rows)
    dm = [sum(v) / len(v) for v in days.values()]
    nd = len(dm)
    if nd > 1:
        sd_d = st.stdev(dm)
        t_day = (sum(dm) / nd) / (sd_d / nd ** 0.5) if sd_d > 0 else 0.0
    else:
        t_day = 0.0

    # 剔除贡献最大的 3 个交易日（按日聚合口径）
    pairs = sorted(zip(days.keys(), dm), key=lambda x: x[1], reverse=True)
    drop = {k for k, _ in pairs[:tol_top]}
    rest = [v for k, v in zip(days.keys(), dm) if k not in drop]
    m_ex = sum(rest) / len(rest) if rest else 0.0

    print(f"  {label:<28} n={n:>5}  日均{m:>+7.3f}%  胜率{win:>4.0f}%  "
          f"按日t={t_day:>+6.2f}  剔top3日均{m_ex:>+7.3f}%  (days={nd})")
    print(f"  {'':<28} 个股级t={t_ind:>+6.2f}（不采信，仅对比）")
    return dict(n=n, mean=m, win=win, t_day=t_day, t_ind=t_ind, m_ex=m_ex, days=nd)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="data/recon_pool_score_20260506_20261103.csv")
    args = ap.parse_args()
    path = Path(args.csv)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        print(f"❌ 找不到 {path}")
        return 1

    rows = load_csv(path)
    valid = [r for r in rows if r["score"] is not None]
    print(f"数据: {path.name}")
    print(f"  总行数 {len(rows)}  有综合分 {len(valid)}  有收益 {sum(1 for r in rows if r['ret'] is not None)}")
    dates = sorted({r['date'] for r in rows})
    print(f"  日期范围 {dates[0]} → {dates[-1]}（{len(dates)} 个池日）")
    print()

    # ── 核心问题：综合分 60 且 优选分 13 ──
    print("=" * 100)
    print("【核心问题】综合分 60 + 优选分 13 的平均收益是否为正？")
    print("=" * 100)
    core = [r for r in valid if r["score"] == 60 and r["pref"] == 13]
    base = stat_block(core, "综合分=60 且 优选分=13")

    print()
    print("── 稳健性对照（优选分离线重算，可能与生产值差 3-5 分）──")
    for lo, hi, lab in [(13, 13, "pref=13"), (12, 14, "pref∈[12,14]"),
                        (13, 15, "pref∈[13,15]"), (11, 15, "pref∈[11,15]")]:
        sub = [r for r in valid if r["score"] == 60 and r["pref"] is not None and lo <= r["pref"] <= hi]
        stat_block(sub, f"综合分=60 且 {lab}")

    print()
    print("── 综合分邻域对照 ──")
    for lo, hi, lab in [(59, 59, "score=59"), (60, 60, "score=60"),
                        (61, 61, "score=61"), (62, 62, "score=62"),
                        (59, 61, "score∈[59,61]")]:
        sub = [r for r in valid if r["score"] is not None and lo <= r["score"] <= hi and r["pref"] == 13]
        stat_block(sub, f"{lab} 且 pref=13")

    print()
    print("=" * 100)
    print("【参照】综合分分档 × 优选分 13（个股两日均值，按日聚合 t）")
    print("=" * 100)
    print(f"  {'综合分段':<12}{'n':>6}{'日均':>10}{'胜率':>7}{'按日t':>8}{'剔top3':>10}")
    for lo, hi in [(60, 64), (65, 66), (67, 69), (70, 70), (71, 79), (80, 100), (60, 100)]:
        sub = [r for r in valid if r["score"] is not None and lo <= r["score"] <= hi
               and r["pref"] == 13 and r["ret"] is not None]
        if not sub:
            continue
        rets = [r["ret"] for r in sub]
        m = sum(rets) / len(rets)
        win = sum(1 for x in rets if x > 0) / len(rets) * 100
        days = day_agg(sub)
        dm = [sum(v) / len(v) for v in days.values()]
        sd = st.stdev(dm) if len(dm) > 1 else 0
        t = (sum(dm) / len(dm)) / (sd / len(dm) ** 0.5) if sd > 0 else 0
        pairs = sorted(zip(days.keys(), dm), key=lambda x: x[1], reverse=True)
        rest = [v for k, v in zip(days.keys(), dm) if k not in {k2 for k2, _ in pairs[:3]}]
        m_ex = sum(rest) / len(rest) if rest else 0
        print(f"  [{lo},{hi}]".ljust(12) + f"{len(sub):>6}{m:>+9.3f}%{win:>6.0f}%{t:>+8.2f}{m_ex:>+9.3f}%")

    print()
    if base:
        print("=" * 100)
        print("【结论判定】")
        print("=" * 100)
        verdict = []
        verdict.append(("日均收益符号", f"{base['mean']:+.3f}%", "正" if base["mean"] > 0 else "负"))
        verdict.append(("胜率", f"{base['win']:.0f}%", "过半" if base["win"] > 50 else "未过半"))
        verdict.append(("按日聚合 t", f"{base['t_day']:+.2f}",
                        "显著(|t|>2)" if abs(base["t_day"]) > 2 else "不显著"))
        verdict.append(("剔 top3 后日均", f"{base['m_ex']:+.3f}%",
                        "仍为正" if base["m_ex"] > 0 else "转负"))
        for k, v, j in verdict:
            print(f"  {k:<14} {v:<12} → {j}")
        print()
        ok = base["mean"] > 0 and base["m_ex"] > 0 and abs(base["t_day"]) > 2
        if ok:
            print("  ✅ 可判定贡献正收益（且通过两道检验）")
        elif base["mean"] > 0 and base["m_ex"] > 0:
            print("  ⚠️ 方向为正，但未通过显著性检验 → 只能说「倾向正贡献」，不足以定案")
        else:
            print("  ❌ 不能判定贡献正收益（方向或稳健性不过关）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
