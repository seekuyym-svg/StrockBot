# -*- coding: utf-8 -*-
"""
回测收益率 vs 沪深成交量 & 科创50指数 关系分析

分析12期回测数据，看看收益率与市场环境之间是否存在可归纳的规律。

数据来源：
  - 沪深成交额：东方财富API（上证+深证逐日相加）
  - 科创50指数：本地 data/index_kc.csv
  - 回测收益率：data/backtest_reports/ 目录下的报告

使用方法：
    python backtest/analyze_market_relation.py
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

DATA_DIR = project_root / "data"

# ──────────────────────────────────────────────
# 12期回测数据
# ──────────────────────────────────────────────

BACKTEST_PERIODS = [
    {"buy": "2026-06-15", "sell": "2026-06-16", "return": 5.05, "win": 6, "lose": 1, "note": "仅7只票"},
    {"buy": "2026-06-16", "sell": "2026-06-17", "return": 6.23, "win": 7, "lose": 3, "note": "连胜①"},
    {"buy": "2026-06-17", "sell": "2026-06-18", "return": 4.67, "win": 8, "lose": 2, "note": "连胜②"},
    {"buy": "2026-06-18", "sell": "2026-06-22", "return": 3.75, "win": 6, "lose": 4, "note": "连胜③跨周末"},
    {"buy": "2026-06-22", "sell": "2026-06-23", "return": -1.52, "win": 3, "lose": 8, "note": "连亏开始"},
    {"buy": "2026-06-23", "sell": "2026-06-24", "return": -1.44, "win": 3, "lose": 7, "note": "连亏②"},
    {"buy": "2026-06-24", "sell": "2026-06-25", "return": 8.52, "win": 5, "lose": 3, "note": "仅8只票"},
    {"buy": "2026-06-25", "sell": "2026-06-26", "return": 2.27, "win": 8, "lose": 2, "note": ""},
    {"buy": "2026-06-26", "sell": "2026-06-29", "return": -0.74, "win": 5, "lose": 5, "note": "跨周末"},
    {"buy": "2026-06-29", "sell": "2026-06-30", "return": 5.89, "win": 9, "lose": 1, "note": "近满堂红"},
    {"buy": "2026-06-30", "sell": "2026-07-01", "return": 6.36, "win": 10, "lose": 0, "note": "满堂红"},
    {"buy": "2026-07-01", "sell": "2026-07-02", "return": -1.53, "win": 3, "lose": 7, "note": "满堂红后变脸"},
]


# ──────────────────────────────────────────────
# 沪深成交额获取
# ──────────────────────────────────────────────

def fetch_market_volumes(dates: List[str]) -> Dict[str, dict]:
    """
    批量获取多个日期的沪深市场成交额

    通过东方财富API获取上证(000001)+深证(399106)日K线成交额，
    逐日相加得到沪深合计成交额（亿元），同时计算5日均量。

    Returns:
        { '2026-06-15': { 'current': 12345, 'avg_5': 12000, 'ratio': 1.03, 'trend': '正常' } }
    """
    if not dates:
        return {}

    # 确定需要拉取的数据范围（最早日期往前推15天，用于算5日均量）
    all_dates_sorted = sorted(dates)
    start_dt = datetime.strptime(all_dates_sorted[0], '%Y-%m-%d') - timedelta(days=15)
    end_dt = datetime.strptime(all_dates_sorted[-1], '%Y-%m-%d')
    start_date = start_dt.strftime('%Y-%m-%d')
    end_date = end_dt.strftime('%Y-%m-%d')

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    def _fetch_index_klines(secid: str) -> dict:
        """获取单个指数的日K线成交额 { '2026-06-15': 1234.5 }"""
        try:
            resp = requests.get(
                "http://push2his.eastmoney.com/api/qt/stock/kline/get",
                params={
                    "secid": secid,
                    "fields1": "f1,f2,f3,f4,f5,f6",
                    "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
                    "klt": "101", "fqt": "1",
                    "beg": start_date.replace('-', ''),
                    "end": end_date.replace('-', ''),
                    "lmt": "30"
                },
                headers=headers, timeout=10
            )
            data = resp.json()
            result = {}
            if data.get('data') and data['data'].get('klines'):
                for line in data['data']['klines']:
                    parts = line.split(',')
                    if len(parts) >= 7:
                        result[parts[0]] = float(parts[6]) / 1e8  # 元→亿元
            return result
        except Exception as e:
            print(f"  ⚠ 获取{secid}失败: {e}")
            return {}

    print(f"  📡 正在获取沪深成交额数据 ({start_date} ~ {end_date})...")
    sh_volumes = _fetch_index_klines("1.000001")
    sz_volumes = _fetch_index_klines("0.399106")

    if not sh_volumes or not sz_volumes:
        print("  ❌ 获取成交额失败")
        return {}

    # 合并两市成交额
    all_dates_avail = sorted(set(sh_volumes.keys()) & set(sz_volumes.keys()))
    daily_total = {}
    for d in all_dates_avail:
        daily_total[d] = sh_volumes[d] + sz_volumes[d]

    # 计算每个目标日期的成交量数据
    result = {}
    for date in dates:
        if date not in daily_total:
            result[date] = None
            continue

        current = daily_total[date]

        # 往前找5个有数据的交易日算5日均量
        avail_dates = [d for d in all_dates_avail if d < date][-5:]
        if avail_dates:
            avg_5 = sum(daily_total[d] for d in avail_dates) / len(avail_dates)
        else:
            avg_5 = current

        ratio = round(current / avg_5, 2) if avg_5 > 0 else 1.0

        # 量能趋势判断
        if ratio >= 1.20:
            trend = "明显放量"
        elif ratio >= 1.05:
            trend = "温和放量"
        elif ratio <= 0.80:
            trend = "明显缩量"
        elif ratio <= 0.95:
            trend = "温和缩量"
        else:
            trend = "正常"

        result[date] = {
            'current': round(current, 0),
            'avg_5': round(avg_5, 0),
            'ratio': round(ratio, 2),
            'trend': trend,
        }

    return result


# ──────────────────────────────────────────────
# 科创50指数分析
# ──────────────────────────────────────────────

def load_kc_index() -> pd.DataFrame:
    """加载科创50指数数据"""
    csv_path = DATA_DIR / "index_kc.csv"
    if not csv_path.exists():
        print(f"  ❌ 科创50数据文件不存在: {csv_path}")
        return pd.DataFrame()
    df = pd.read_csv(csv_path, parse_dates=['date'])
    df = df.set_index('date').sort_index()
    return df


def analyze_kc_index(df: pd.DataFrame, dates: List[str]) -> Dict[str, dict]:
    """
    分析指定日期的科创50指数状态

    Returns:
        { '2026-06-15': { 'close': 2128.58, 'ma20': ..., 'ma60': ..., 'ma20_above_ma60': True, 'close_above_ma20': True, 'healthy': True } }
    """
    if df.empty:
        return {}

    result = {}
    for date in dates:
        check_dt = pd.to_datetime(date)
        df_before = df[df.index <= check_dt].copy()
        if len(df_before) < 60:
            result[date] = None
            continue

        closes = df_before['close'].values
        ma20 = pd.Series(closes).rolling(20).mean().iloc[-1]
        ma60 = pd.Series(closes).rolling(60).mean().iloc[-1]
        close = df_before['close'].iloc[-1]
        open_val = df_before['open'].iloc[-1]

        close_above_ma20 = close > ma20
        ma20_above_ma60 = ma20 > ma60
        healthy = close_above_ma20 and ma20_above_ma60

        # 涨跌幅
        change_pct = (close - open_val) / open_val * 100 if open_val > 0 else 0

        # 前一日涨跌幅
        if len(df_before) >= 2:
            prev_close = df_before['close'].iloc[-2]
            prev_change = (close - prev_close) / prev_close * 100 if prev_close > 0 else 0
        else:
            prev_change = 0

        result[date] = {
            'close': round(close, 2),
            'ma20': round(ma20, 2),
            'ma60': round(ma60, 2),
            'change_pct': round(change_pct, 2),
            'prev_change_pct': round(prev_change, 2),
            'close_above_ma20': bool(close_above_ma20),
            'ma20_above_ma60': bool(ma20_above_ma60),
            'healthy': bool(healthy),
        }

    return result


# ──────────────────────────────────────────────
# 辅助：量价信号判断
# ──────────────────────────────────────────────

def volume_signal(vol: dict) -> str:
    """成交量信号"""
    if vol is None:
        return "数据不足"
    if vol['ratio'] >= 1.20:
        return "🔴极度放量"
    elif vol['trend'] == '温和放量':
        return "🟡温和放量"
    elif vol['trend'] == '正常':
        return "🟢正常"
    elif vol['trend'] in ('温和缩量', '明显缩量'):
        return "🔵缩量"
    return "🟢正常"


# ──────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────

def main():
    print()
    print("=" * 90)
    print("  📊 回测收益率 vs 沪深成交量 & 科创50指数 关系分析")
    print(f"     分析区间: {BACKTEST_PERIODS[0]['buy']} ~ {BACKTEST_PERIODS[-1]['sell']}")
    print("=" * 90)

    # ── Step 1: 获取数据 ──
    buy_dates = sorted(set(p['buy'] for p in BACKTEST_PERIODS))
    sell_dates = sorted(set(p['sell'] for p in BACKTEST_PERIODS))
    all_dates = sorted(set(buy_dates + sell_dates))

    # 沪深成交额
    volumes = fetch_market_volumes(all_dates)
    if volumes:
        vol_ok = sum(1 for v in volumes.values() if v is not None)
        print(f"  ✅ 获取到 {vol_ok}/{len(all_dates)} 个交易日的成交额数据")
    else:
        print("  ❌ 成交额数据获取失败")

    # 科创50指数
    kc_df = load_kc_index()
    kc_data = analyze_kc_index(kc_df, all_dates)
    if kc_data:
        print(f"  ✅ 科创50指数数据加载完成 ({len(kc_data)} 个交易日)")
    else:
        print("  ❌ 科创50数据加载失败")

    print()
    print("─" * 90)

    # ── Step 2: 输出主表 ──
    header = (
        f"  {'期次':>3}  "
        f"{'买入日':<10}  "
        f"{'卖出日':<10}  "
        f"{'收益率':>7}  "
        f"{'盈/亏':>6}  "
        f"{'沪深成交额':>10}  "
        f"{'量比':>5}  "
        f"{'量能信号':<10}  "
        f"{'科创50收盘':>9}  "
        f"{'MA20':>8}  "
        f"{'MA60':>8}  "
        f"{'科创信号':<8}"
    )
    print(header)
    print(f"  {'─' * 115}")

    for i, p in enumerate(BACKTEST_PERIODS, 1):
        buy = p['buy']
        ret = p['return']
        ret_str = f"{ret:+.2f}%"
        winloss = f"{p['win']}/{p['lose']}"

        # 沪深成交额（用买入日的数据）
        vol = volumes.get(buy)
        if vol:
            vol_str = f"{vol['current']:>8.0f}亿"
            ratio_str = f"{vol['ratio']:>4.2f}"
            signal_str = volume_signal(vol)
        else:
            vol_str = "   N/A"
            ratio_str = " N/A"
            signal_str = "N/A"

        # 科创50
        kc = kc_data.get(buy)
        if kc:
            kc_close = f"{kc['close']:>8.2f}"
            ma20_str = f"{kc['ma20']:>8.0f}"
            ma60_str = f"{kc['ma60']:>8.0f}"
            kc_signal = "✅健康" if kc['healthy'] else "❌不健康"
        else:
            kc_close = "   N/A"
            ma20_str = "   N/A"
            ma60_str = "   N/A"
            kc_signal = "N/A"

        # 用颜色标记收益率
        ret_display = f"  {ret_str}" if ret >= 0 else f" {ret_str}"

        line = (
            f"  {i:>3}  "
            f"{buy:<10}  "
            f"{p['sell']:<10}  "
            f"{ret_display:>7}  "
            f"{winloss:>6}  "
            f"{vol_str:>10}  "
            f"{ratio_str:>5}  "
            f"{signal_str:<10}  "
            f"{kc_close:>9}  "
            f"{ma20_str:>8}  "
            f"{ma60_str:>8}  "
            f"{kc_signal:<8}"
        )
        print(line)

    print(f"  {'─' * 115}")

    # ── Step 3: 分析规律 ──
    print()
    print("  📈 规律分析")
    print()

    # 规律1：量能信号 vs 收益率
    print("  ▶ 规律一：量能信号 vs 收益率")
    print(f"  {'─' * 50}")
    for i, p in enumerate(BACKTEST_PERIODS, 1):
        vol = volumes.get(p['buy'])
        if vol is None:
            continue
        ret = p['return']
        signal = volume_signal(vol)
        note = ""
        if vol['ratio'] >= 1.20 and ret < 0:
            note = " ← ⚠ 极度放量+亏损，物极必反"
        elif vol['ratio'] >= 1.20 and ret > 0:
            note = " （放量上涨，趋势延续）"
        elif vol['ratio'] <= 0.90 and ret > 0:
            note = " （缩量上涨，筹码稳定）"
        elif vol['ratio'] <= 0.90 and ret < 0:
            note = " （缩量下跌，不宜入场）"
        print(f"    第{i:>2}期: 买入日{p['buy']} {signal} 量比{vol['ratio']:>4.2f}  → {ret:+.2f}%{note}")

    # 规律2：科创50健康度 vs 收益率
    print()
    print("  ▶ 规律二：科创50指数健康度 vs 收益率")
    print(f"  {'─' * 50}")
    for i, p in enumerate(BACKTEST_PERIODS, 1):
        kc = kc_data.get(p['buy'])
        if kc is None:
            continue
        ret = p['return']
        healthy = kc['healthy']
        close = kc['close']
        ma20_val = kc['ma20']
        ma60_val = kc['ma60']
        signal = "✅健康" if healthy else "❌不健康"
        note = ""
        if not healthy and ret < 0:
            note = " ← ⚠ 指数不健康+亏损"
        elif not healthy and ret > 0:
            note = " （指数弱但个股强，选股有效）"
        elif healthy and ret > 0:
            note = " （指数健康，顺势）"
        elif healthy and ret < 0:
            note = " （指数健康但亏损，选股问题）"
        print(f"    第{i:>2}期: 买入日{p['buy']} {signal} 收盘{close:.0f} MA20={ma20_val:.0f} MA60={ma60_val:.0f} → {ret:+.2f}%{note}")

    # ── Step 4: 交叉分析总结 ──
    print()
    print("  ▶ 交叉分析总结")
    print(f"  {'─' * 60}")

    # 统计各象限
    healthy_win = sum(1 for p in BACKTEST_PERIODS if
                      kc_data.get(p['buy']) and kc_data[p['buy']]['healthy'] and p['return'] > 0)
    healthy_lose = sum(1 for p in BACKTEST_PERIODS if
                       kc_data.get(p['buy']) and kc_data[p['buy']]['healthy'] and p['return'] <= 0)
    unhealthy_win = sum(1 for p in BACKTEST_PERIODS if
                        kc_data.get(p['buy']) and not kc_data[p['buy']]['healthy'] and p['return'] > 0)
    unhealthy_lose = sum(1 for p in BACKTEST_PERIODS if
                         kc_data.get(p['buy']) and not kc_data[p['buy']]['healthy'] and p['return'] <= 0)

    print(f"    ├ 科创50健康 + 盈利: {healthy_win}次")
    print(f"    ├ 科创50健康 + 亏损: {healthy_lose}次")
    print(f"    ├ 科创50不健康 + 盈利: {unhealthy_win}次")
    print(f"    └ 科创50不健康 + 亏损: {unhealthy_lose}次")

    # 极度放量分析
    extreme_vol_dates = []
    for p in BACKTEST_PERIODS:
        vol = volumes.get(p['buy'])
        if vol and vol['ratio'] >= 1.15:
            extreme_vol_dates.append((p['buy'], vol['ratio'], p['return']))

    if extreme_vol_dates:
        print(f"\n    ⚠ 量比≥1.15的交易日（市场过热）:")
        for d, r, ret in extreme_vol_dates:
            direction = "盈利" if ret > 0 else "亏损"
            print(f"      {d} 量比{r:.2f} → 当期{ret:+.2f}%（{direction}）")

    # 缩量分析
    shrink_dates = []
    for p in BACKTEST_PERIODS:
        vol = volumes.get(p['buy'])
        if vol and vol['ratio'] <= 0.90:
            shrink_dates.append((p['buy'], vol['ratio'], p['return']))
    if shrink_dates:
        print(f"\n    🔵 量比≤0.90的交易日（市场冷清）:")
        for d, r, ret in shrink_dates:
            direction = "盈利" if ret > 0 else "亏损"
            print(f"      {d} 量比{r:.2f} → 当期{ret:+.2f}%（{direction}）")

    # ── Step 5: 结论 ──
    print()
    print("  💡 初步结论")
    print(f"  {'─' * 60}")
    print()

    # 基于统计给出结论
    if healthy_win + healthy_lose > 0:
        healthy_win_rate = healthy_win / (healthy_win + healthy_lose) * 100
        print(f"    ① 科创50健康时交易: 胜率 {healthy_win_rate:.0f}% ({healthy_win}/{healthy_win + healthy_lose})")
    else:
        print(f"    ① 科创50健康时交易: 数据不足")

    if unhealthy_win + unhealthy_lose > 0:
        unhealthy_win_rate = unhealthy_win / (unhealthy_win + unhealthy_lose) * 100
        print(f"    ② 科创50不健康时交易: 胜率 {unhealthy_win_rate:.0f}% ({unhealthy_win}/{unhealthy_win + unhealthy_lose})")
    else:
        print(f"    ② 科创50不健康时交易: 数据不足")

    # 整体胜率
    total_win = sum(1 for p in BACKTEST_PERIODS if p['return'] > 0)
    total_lose = sum(1 for p in BACKTEST_PERIODS if p['return'] <= 0)
    print(f"    ③ 12期整体胜率: {total_win}/{total_win + total_lose}")

    print()
    print("=" * 90)
    print()


if __name__ == "__main__":
    main()
