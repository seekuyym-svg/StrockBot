#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原始池全量重建：对每个 .bak 原始池里的每一只股票，重算
    综合分（local.utils.calculate_trend_score_v2）
    优选分（HistoricalStockScorer._calc_pref_and_veto）
    两日收益（T+1 开盘买 → T+2 收盘卖）
产出 CSV，供「综合分 × 优选分」分档分析。

设计要点（遵循 2026-11-03 立的长任务写入纪律）：
  ① 开跑前探测输出目录可写，不可写直接退出（--check-write 可单测）
  ② 每 N 行追加写 JSONL checkpoint —— 中断也只丢最后一小段，且可断点续跑
  ③ 全部跑完后才由 JSONL 汇总成 CSV；CSV 校验（存在 / 行数 / 大小）通过才算成功
  ④ 绝不删除任何源数据

用法：
    python tools/recon_pool_score.py --check-write            # 只探测
    python tools/recon_pool_score.py --limit-days 2           # 冒烟测试（2 个池日）
    python tools/recon_pool_score.py --out data/recon.csv     # 全量（需提权）
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

CKPT_NAME = "recon_checkpoint.jsonl"
FIELDS = ["date", "code", "close", "ma20", "vol_ratio", "ret_pct",
          "score", "pref", "ret2d", "buy_open", "sell_close"]


# ────────────────────────── 池文件解析 ──────────────────────────
def find_bak_files() -> list[tuple[str, Path]]:
    out = []
    for d in (PROJECT_ROOT / "data", PROJECT_ROOT / "data" / "2026年"):
        if not d.exists():
            continue
        for f in d.glob("stockpool_*.txt.bak"):
            import re
            m = re.search(r"(\d{8})", f.name)
            if m:
                out.append((m.group(1), f))
    out.sort()
    # 同一天若两处都有，保留第一个
    seen, uniq = set(), []
    for dc, f in out:
        if dc not in seen:
            seen.add(dc)
            uniq.append((dc, f))
    return uniq


def parse_bak(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("-") or s.startswith("code,"):
            continue
        p = s.split(",")
        if len(p) < 5:
            continue
        code = p[0].strip()
        if not (len(code) == 6 and code.isdigit()):
            continue
        try:
            rows.append(dict(code=code, close=float(p[1]), ma20=float(p[2]),
                             vol_ratio=float(p[3]), ret_pct=float(p[4])))
        except ValueError:
            pass
    return rows


def market_of(code: str) -> str:
    return "sh" if code.startswith(("6", "9")) else "sz"


# ────────────────────────── 交易日历 ──────────────────────────
def load_calendar() -> list[str]:
    """用沪深300 日线做交易日历"""
    import requests
    r = requests.get(
        "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
        params={"param": "sh000300,day,2026-01-01,2027-01-01,300,qfq"},
        headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    d = r.json()["data"]["sh000300"]
    k = d.get("qfqday") or d.get("day")
    return sorted(x[0] for x in k)


# ────────────────────────── K 线缓存（关键提速） ──────────────────────────
def install_kline_cache(days_back: int = 1000):
    """给 local.utils._get_historical_klines 套一层「按股票」的内存缓存。

    原函数每次调用都会重新读 config.yaml + 解析整个 .day 文件（无任何缓存），
    每行记录要调 3 次（综合分/优选分/收益）→ 实测 1.5 秒/行，38k 行要 15 小时。
    套上缓存后：每只股票只真正读盘一次，其余按 end_date 切片 → 约 25 分钟。

    注意：score_stockpool._get_historical_klines 内部是「函数内 import」，
    因此替换 local.utils 上的属性即可被它取到 ✓
    """
    import pandas as pd
    import local.utils as lu

    orig = lu._get_historical_klines
    cache: dict[tuple[str, str], object] = {}
    stats = {"miss": 0, "hit": 0}

    def cached(market: str, code: str, days: int = 300,
               end_date: str = None, min_data_length: int = 60):
        key = (market, code)
        full = cache.get(key)
        if full is None:
            stats["miss"] += 1
            full = orig(market, code, days=days_back, end_date=None,
                        min_data_length=1)
            cache[key] = full
        else:
            stats["hit"] += 1
        if full is None or len(full) == 0:
            return full

        # min_data_length 校验针对「原始可得长度」（与原函数语义一致），
        # 不能放在 days 切片之后 —— 否则 days=10 的短取会被误判为空。
        if min_data_length and len(full) < min_data_length:
            return full.iloc[0:0]

        sub = full
        if end_date:
            try:
                mask = pd.to_datetime(sub.index) <= pd.Timestamp(end_date)
                sub = sub[mask]
            except Exception:
                pass
        if days and len(sub) > days:
            sub = sub.iloc[-days:]
        return sub

    cached.stats = stats          # type: ignore[attr-defined]
    lu._get_historical_klines = cached
    return stats


# ────────────────────────── 主流程 ──────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/recon_pool_score.csv")
    ap.add_argument("--limit-days", type=int, default=0, help="只跑前 N 个池日（冒烟测试）")
    ap.add_argument("--check-write", action="store_true", help="只探测输出目录可写性")
    ap.add_argument("--ckpt-every", type=int, default=200)
    ap.add_argument("--no-cache", action="store_true", help="关闭 K 线内存缓存（调试用）")
    args = ap.parse_args()

    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = PROJECT_ROOT / out_path

    # ① 写入探测
    from tools.probe_write import is_writable
    ok, msg = is_writable(out_path.parent)
    print(f"[1/5] 输出目录 {out_path.parent.relative_to(PROJECT_ROOT)} 可写性: {'✅' if ok else '❌ ' + msg[:60]}")
    if not ok:
        print("      ❌ 中止。请用 danger-full-access 提权运行，或改用 --out 指到可写目录。")
        return 2
    if args.check_write:
        return 0

    ckpt_path = out_path.parent / CKPT_NAME

    # ② 已完成集合（断点续跑）
    done: set[str] = set()
    if ckpt_path.exists():
        for line in ckpt_path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                done.add(f"{r['date']}|{r['code']}")
            except Exception:
                pass
    print(f"[2/5] 断点文件 {ckpt_path.name}: 已完成 {len(done)} 行")

    files = find_bak_files()
    if args.limit_days:
        files = files[-args.limit_days:]   # 取最近的 N 天做冒烟
    print(f"[3/5] 池文件 {len(files)} 个: {files[0][0]} → {files[-1][0]}")

    cal = load_calendar()
    cal_idx = {d.replace("-", ""): i for i, d in enumerate(cal)}

    # ★ 必须在导入评分函数之前安装缓存（否则脚本内绑定的仍是原函数）
    kstats = None
    if not args.no_cache:
        kstats = install_kline_cache()
        print("[缓存] 已安装 K 线内存缓存（按股票，只读盘一次）")

    from local.utils import calculate_trend_score_v2, _get_historical_klines
    from backtest.score_stockpool import HistoricalStockScorer
    scorer = HistoricalStockScorer()

    total_new = 0
    t0 = time.time()
    ckpt = ckpt_path.open("a", encoding="utf-8")

    try:
        for k, (dc, path) in enumerate(files, 1):
            stocks = parse_bak(path)
            d_str = f"{dc[:4]}-{dc[4:6]}-{dc[6:]}"
            i = cal_idx.get(dc)
            if i is None or i + 2 >= len(cal):
                print(f"  [{k}/{len(files)}] {dc} 跳过（日历缺 T+1/T+2）")
                continue
            buy_d, sell_d = cal[i + 1], cal[i + 2]

            n_ok = n_skip = 0
            for s in stocks:
                key = f"{d_str}|{s['code']}"
                if key in done:
                    n_skip += 1
                    continue
                mk = market_of(s["code"])
                try:
                    score = calculate_trend_score_v2(mk, s["code"], days=300, end_date=d_str)
                    pref = scorer._calc_pref_and_veto(mk, s["code"], d_str, current_score=score)
                except Exception:
                    score, pref = None, None

                buy_open = sell_close = ret2d = None
                try:
                    df = _get_historical_klines(mk, s["code"], days=10, end_date=sell_d)
                    if df is not None and not df.empty:
                        idx = {str(x)[:10]: j for j, x in enumerate(df.index)}
                        bi = idx.get(buy_d)
                        si = idx.get(sell_d)
                        if bi is not None and si is not None:
                            buy_open = float(df["open"].iloc[bi])
                            sell_close = float(df["close"].iloc[si])
                            if buy_open > 0:
                                ret2d = (sell_close / buy_open - 1) * 100
                except Exception:
                    pass

                rec = dict(date=d_str, code=s["code"], close=s["close"], ma20=s["ma20"],
                           vol_ratio=s["vol_ratio"], ret_pct=s["ret_pct"],
                           score=score, pref=pref, ret2d=ret2d,
                           buy_open=buy_open, sell_close=sell_close)
                ckpt.write(json.dumps(rec, ensure_ascii=False) + "\n")
                total_new += 1
                n_ok += 1
                if total_new % args.ckpt_every == 0:
                    ckpt.flush()
                    el = time.time() - t0
                    rate = total_new / el if el > 0 else 0
                    print(f"  … 已写 {total_new} 行  ({rate:.1f} 行/秒, 本日 {dc})", flush=True)
            ckpt.flush()
            print(f"  [{k}/{len(files)}] {dc}: 原池 {len(stocks)} 只 → 新增 {n_ok}, 跳过 {n_skip}", flush=True)
    finally:
        ckpt.close()

    # ③ 汇总成 CSV
    print(f"[4/5] 汇总 JSONL → CSV …")
    all_rows = []
    for line in ckpt_path.read_text(encoding="utf-8").splitlines():
        try:
            all_rows.append(json.loads(line))
        except Exception:
            pass
    # 去重（同 date|code 保留最后一条）
    dedup = {}
    for r in all_rows:
        dedup[f"{r['date']}|{r['code']}"] = r
    rows = list(dedup.values())
    rows.sort(key=lambda r: (r["date"], r["code"]))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in FIELDS})

    # ④ 校验
    size = out_path.stat().st_size
    n_lines = sum(1 for _ in out_path.open(encoding="utf-8-sig")) - 1
    print(f"[5/5] ✅ CSV: {out_path}")
    print(f"      行数={n_lines}  大小={size/1024:.0f} KB  唯一(date,code)={len(rows)}")
    print(f"      其中 综合分非空={sum(1 for r in rows if r.get('score') is not None)}"
          f"  优选分非空={sum(1 for r in rows if r.get('pref') is not None)}"
          f"  收益非空={sum(1 for r in rows if r.get('ret2d') is not None)}")
    if n_lines == 0 or size == 0:
        print("      ❌ 校验失败：CSV 为空")
        return 1
    print("      ✅ 校验通过（CSV 保留，JSONL checkpoint 也保留以便续跑）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
