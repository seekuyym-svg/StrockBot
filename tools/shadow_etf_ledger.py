#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
影子账本（shadow ledger）—— 补齐"没买的那几只"的模拟数据。

背景：
    当前篮子只有 6 只（513120/515650/516310/518880/513850/162411），
    588080 科创50 与 513050 中概互联**不在配置里、实盘不会买**，
    因此 buy_decision_history 里没有它们的收益记录。
    要验证"8 只候选选 6 只"的分位法，就必须把 8 只都模拟一遍。

做法：
    对 buy_decision_history 里的**每一个交易日**，对 8 只 ETF 各算：
      · 前一日 250 日分位（决策时已知，无未来函数）
      · 前一日近 5 日 / 近 10 日涨幅（动量）
      · T+1 开盘买入 → T+2 收盘卖出的两日收益（与生产口径一致）
    追加写入 data/shadow_etf_ledger.csv，按 (date, code) 去重，可反复运行。

用法：
    python tools/shadow_etf_ledger.py            # 增量补齐并输出摘要
    python tools/shadow_etf_ledger.py --summary  # 只看摘要，不写盘
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ETFS = {
    "513120": ("sh", "港股创新药"),
    "515650": ("sh", "消费50"),
    "516310": ("sh", "银行"),
    "518880": ("sh", "黄金"),
    "513850": ("sh", "美国50"),
    "162411": ("sz", "华宝油气"),
    "588080": ("sh", "科创50"),
    "513050": ("sh", "中概互联"),
}
# 当前在篮子里的 6 只（用于标注，分析时可作分组）
IN_BASKET = {"513120", "515650", "516310", "518880", "513850", "162411"}

FIELDS = ["date", "code", "name", "in_basket", "close_prev",
          "pct250", "mom5", "mom10", "ret2d"]


def load_history_dates() -> list[str]:
    dates = set()
    for p in [ROOT / "data" / "buy_decision_history.txt.bak",
              ROOT / "data" / "buy_decision_history.txt"]:
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines()[1:]:
            q = line.split(",")
            if len(q) >= 15 and q[0].count("-") == 2:
                dates.add(q[0])
    return sorted(dates)


def fetch(mk: str, code: str):
    import requests
    import pandas as pd
    r = requests.get("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
                     params={"param": f"{mk}{code},day,2023-01-01,2027-01-01,2000,qfq"},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    d = r.json()["data"][f"{mk}{code}"]
    k = d.get("qfqday") or d.get("day")
    return pd.DataFrame([(x[0], float(x[1]), float(x[2])) for x in k],
                        columns=["date", "open", "close"]).set_index("date")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/shadow_etf_ledger.csv")
    ap.add_argument("--summary", action="store_true", help="只看摘要，不写盘")
    args = ap.parse_args()

    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out

    if not args.summary:
        from tools.probe_write import is_writable
        ok, msg = is_writable(out.parent)
        print(f"[1/4] 输出目录 {out.parent.name} 可写性: {'✅' if ok else '❌ ' + msg[:50]}")
        if not ok:
            print("      ❌ 中止：请用 danger-full-access 提权运行")
            return 2

    # 已有记录（去重）
    done = set()
    if out.exists():
        with out.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                done.add(f"{r['date']}|{r['code']}")
    print(f"[2/4] 已有记录 {len(done)} 行")

    dates = load_history_dates()
    print(f"[3/4] history 覆盖 {len(dates)} 个交易日: {dates[0]} → {dates[-1]}")

    # 逐只拉数据（每只只要拉一次）
    frames = {}
    for code, (mk, nm) in ETFS.items():
        frames[code] = fetch(mk, code)

    new_rows = []
    for code, (mk, nm) in ETFS.items():
        df = frames[code]
        closes = df["close"]
        pct = closes.rolling(250).apply(lambda x: (x <= x.iloc[-1]).mean(), raw=False)
        cal = list(df.index)
        for d in dates:
            if f"{d}|{code}" in done:
                continue
            if d not in cal:
                continue
            i = cal.index(d)
            if i + 1 >= len(cal):
                continue
            # 决策依据：前一日
            if i == 0:
                continue
            p = cal[i - 1]
            if i < 11:
                continue
            buy_open = df.loc[d, "open"]
            sell_close = df.loc[cal[i + 1], "close"]
            if buy_open <= 0:
                continue
            new_rows.append(dict(
                date=d, code=code, name=nm,
                in_basket="Y" if code in IN_BASKET else "N",
                close_prev=round(float(closes.loc[p]), 4),
                pct250=round(float(pct.loc[p]), 4) if pct.notna().loc[p] else "",
                mom5=round(float(closes.loc[p] / closes.loc[cal[i - 6]] - 1) * 100, 3),
                mom10=round(float(closes.loc[p] / closes.loc[cal[i - 11]] - 1) * 100, 3),
                ret2d=round(float(sell_close / buy_open - 1) * 100, 4),
            ))

    print(f"[4/4] 本轮新增 {len(new_rows)} 行")
    if args.summary:
        return 0

    write_header = not out.exists() or out.stat().st_size == 0
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if write_header:
            w.writeheader()
        for r in new_rows:
            w.writerow(r)

    # 校验
    with out.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    dates_all = sorted({r["date"] for r in rows})
    print(f"      ✅ {out}")
    print(f"      总行数 {len(rows)}  覆盖 {len(dates_all)} 个交易日  "
          f"大小 {out.stat().st_size/1024:.0f} KB")
    if len(rows) == 0:
        print("      ❌ 校验失败：无数据")
        return 1

    # 摘要：8 只在已覆盖日子里的平均两日收益
    import statistics as st
    print()
    print("  ── 各只平均两日收益（已覆盖的交易日）──")
    by = {}
    for r in rows:
        by.setdefault(r["code"], []).append(float(r["ret2d"]))
    for code in ETFS:
        v = by.get(code, [])
        if not v:
            continue
        nm = ETFS[code][1]
        tag = "篮子内" if code in IN_BASKET else "**未配置**"
        print(f"    {code} {nm:<10} n={len(v):>3}  均值 {st.mean(v):>+7.3f}%  "
              f"胜率 {sum(1 for x in v if x > 0)/len(v)*100:>4.0f}%  {tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
