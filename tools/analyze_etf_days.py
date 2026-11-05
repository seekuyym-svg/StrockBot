#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
固定验证点：把「买 ETF 的交易日」换成「买股票」，收益是否提升？

口径：
  股票收益 = 该 ETF 日对应池日（T-1）的 13 分池等权两日收益（空池记 0）
  ETF 收益 = buy_decision_history.txt 里该日的 actual_return（当天确实买的 ETF 篮子）
  差值     = 股票 − ETF（正 = 换股票更好）
  说明     = 池内 0 只时「换股票」实际只能空仓（收益 0），单独标注

产出：
  ① 逐日明细表（哪些天换股票更好 / 更差 / 无票可换）
  ② 汇总：现行 vs 全换股票（复利），以及"仅在有票的天换"的对照
  ③ 纳入每月复盘固定清单

用法：
    python tools/analyze_etf_days.py                  # 全部月份
    python tools/analyze_etf_days.py --month 2026-10  # 只看某月
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_pools() -> dict[str, dict]:
    """读 #dyn（data/ 与 data/2026年/ 两处都要扫）"""
    pools = {}
    for d in (PROJECT_ROOT / "data", PROJECT_ROOT / "data" / "2026年"):
        if not d.exists():
            continue
        for f in d.glob("stockpool_2026*#dyn"):
            m = re.match(r"stockpool_(\d{8})\.txt([+-][\d.]+)#dyn", f.name)
            if not m or m.group(1) in pools:
                continue
            stocks = []
            for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                p = s.split(",")
                if len(p) >= 4:
                    try:
                        stocks.append((p[0], int(float(p[1])), float(p[3])))
                    except ValueError:
                        pass
            pools[m.group(1)] = dict(ret=float(m.group(2)), stocks=stocks)
    return pools


def load_history() -> list[dict]:
    out = []
    path = PROJECT_ROOT / "data" / "buy_decision_history.txt"
    for line in path.read_text(encoding="utf-8").splitlines()[1:]:
        p = line.split(",")
        if len(p) < 15:
            continue
        try:
            out.append(dict(date=p[0], vol=float(p[2]), score=int(float(p[12])),
                            advice=p[13],
                            ret=float(p[14]) if p[14].strip() else None))
        except ValueError:
            continue
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", help="只看某月，如 2026-10")
    args = ap.parse_args()

    pools = load_pools()
    hist = load_history()
    pool_dates = sorted(pools.keys())

    rows = []
    for h in hist:
        if h["advice"] != "买ETF" or h["ret"] is None:
            continue
        if args.month and not h["date"].startswith(args.month):
            continue
        # 池日 = 早于买入日的最近一个池日
        dc = h["date"].replace("-", "")
        cand = [d for d in pool_dates if d < dc]
        if not cand:
            continue
        T = cand[-1]
        p = pools[T]
        stock = p["ret"]
        rows.append(dict(buy=h["date"], T=f"{T[:4]}-{T[4:6]}-{T[6:]}",
                         n=len(p["stocks"]), stock=stock, etf=h["ret"],
                         diff=stock - h["ret"], score=h["score"], vol=h["vol"]))

    if not rows:
        print(f"没有买 ETF 的交易日{'（月份 ' + args.month + '）' if args.month else ''}")
        return 0

    title = f"（{args.month}）" if args.month else ""
    print("=" * 96)
    print(f"验证点：买 ETF 的日子换成买股票，收益是否提升？{title}")
    print("=" * 96)
    print(f"  {'买入日':<12}{'池日':<12}{'评分':>4}{'量比':>6}{'池内':>4}"
          f"{'股票':>9}{'ETF':>9}{'差值':>10}  结论")
    print("  " + "-" * 88)

    better, worse, empty = [], [], []
    for r in rows:
        if r["n"] == 0:
            empty.append(r)
            verdict = "空池（换股票=空仓）"
        elif r["diff"] > 0:
            better.append(r); verdict = f"✅ 换股票更好 +{r['diff']:.2f}pp"
        else:
            worse.append(r); verdict = f"❌ 换股票更差 {r['diff']:.2f}pp"
        print(f"  {r['buy']:<12}{r['T']:<12}{r['score']:>4}{r['vol']:>6.2f}{r['n']:>4}"
              f"{r['stock']:>+8.2f}%{r['etf']:>+8.2f}%{r['diff']:>+9.2f}pp  {verdict}")

    def comp(vals):
        c = 1.0
        for v in vals:
            c *= 1 + v / 100
        return (c - 1) * 100

    print()
    print("  " + "=" * 88)
    print(f"  ETF 日共 {len(rows)} 天：换股票更好 {len(better)} 天 / 更差 {len(worse)} 天 / 空池 {len(empty)} 天")
    cur = comp([r["etf"] for r in rows])
    swap_all = comp([(r["stock"] if r["n"] > 0 else 0.0) for r in rows])
    swap_tradeable = comp([(r["stock"] if r["n"] > 0 else r["etf"]) for r in rows])
    print(f"  现行（全买 ETF）            累计 {cur:>+8.2f}%")
    print(f"  全部换成买股票（空池记0）    累计 {swap_all:>+8.2f}%   差 {swap_all - cur:>+7.2f}pp")
    print(f"  仅在有票的日子换（空池保留ETF）累计 {swap_tradeable:>+8.2f}%   差 {swap_tradeable - cur:>+7.2f}pp")
    print()
    if better:
        print("  ✅ 换股票更好的日子：" + "、".join(r["buy"][5:] for r in better))
    if worse:
        print("  ❌ 换股票更差的日子：" + "、".join(r["buy"][5:] for r in worse))
    if empty:
        print("  ⚪ 池内 0 只（无票可换）：" + "、".join(r["buy"][5:] for r in empty))
    print()
    print("  判据（与项目既有标准一致）：")
    print("    · 若「换股票更好」的天数明显少于一半，或全换后累计更差 ⇒ 门控方向正确，不改")
    print("    · 若某评分档反复出现「换股票更好」⇒ 该档需单独检验是否纳入门控")
    return 0


if __name__ == "__main__":
    sys.exit(main())
