# -*- coding: utf-8 -*-
"""
回测收益率 vs 隔夜美股纳斯达克 + 早盘日经225/KOSPI 关系分析

数据来源（东方财富API）：
  - 纳斯达克(IXIC)：前一日收盘 → 隔夜情绪
  - 日经225(N225)：当日开盘 → 亚洲早盘情绪
  - 韩国KOSPI：当日开盘 → 亚洲早盘情绪

使用方法：
    python backtest/analyze_overseas_relation.py
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import time

import requests

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


BACKTEST_PERIODS = [
    {"buy": "2026-06-15", "sell": "2026-06-16", "return": 5.05},
    {"buy": "2026-06-16", "sell": "2026-06-17", "return": 6.23},
    {"buy": "2026-06-17", "sell": "2026-06-18", "return": 4.67},
    {"buy": "2026-06-18", "sell": "2026-06-22", "return": 3.75, "note": "跨周末"},
    {"buy": "2026-06-22", "sell": "2026-06-23", "return": -1.52},
    {"buy": "2026-06-23", "sell": "2026-06-24", "return": -1.44},
    {"buy": "2026-06-24", "sell": "2026-06-25", "return": 8.52},
    {"buy": "2026-06-25", "sell": "2026-06-26", "return": 2.27},
    {"buy": "2026-06-26", "sell": "2026-06-29", "return": -0.74, "note": "跨周末"},
    {"buy": "2026-06-29", "sell": "2026-06-30", "return": 5.89},
    {"buy": "2026-06-30", "sell": "2026-07-01", "return": 6.36},
    {"buy": "2026-07-01", "sell": "2026-07-02", "return": -1.53},
]


def fetch_nasdaq(start: str, end: str) -> Dict[str, dict]:
    """从腾讯财经获取纳斯达克历史日K线"""
    url = "http://web.ifzq.gtimg.cn/appstock/app/kline/kline"
    params = {"p": 1, "param": f"usIXIC,day,{start},{end},60"}
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        data = resp.json()
        klines = data['data']['us.IXIC']['day']
    except Exception as e:
        print(f"  ❌ 纳斯达克: 获取失败 - {e}")
        return {}
    sorted_klines = []
    for kline in klines:
        d = kline[0]
        sorted_klines.append({
            'date': d,
            'open': float(kline[1]),
            'close': float(kline[2]),
            'high': float(kline[3]),
            'low': float(kline[4]),
        })

    # 按日期排序，为每个交易日计算隔夜涨跌幅（相对于前一日收盘）
    result = {}
    prev_close = None
    for item in sorted_klines:
        d = item['date']
        if prev_close is not None and prev_close > 0:
            overnight_chg = (item['close'] - prev_close) / prev_close * 100
        else:
            overnight_chg = 0.0
        item['change_pct'] = round(overnight_chg, 2)
        result[d] = item
        prev_close = item['close']

    print(f"  ✅ 纳斯达克(腾讯): {len(result)} 个交易日")
    return result


def fetch_index_em(secid: str, name: str, start: str, end: str) -> Optional[Dict[str, dict]]:
    """从东方财富获取全球指数历史K线"""
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101", "fqt": "1",
        "beg": start.replace('-', ''),
        "end": end.replace('-', ''),
        "lmt": "60"
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://quote.eastmoney.com/'
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        data = resp.json()
        klines = data['data']['klines']
    except Exception as e:
        return None  # 返回None表示失败，由调用方决定降级
    result = {}
    for line in klines:
        parts = line.split(',')
        d = parts[0]
        result[d] = {
            'open': float(parts[1]),
            'close': float(parts[2]),
            'high': float(parts[3]),
            'low': float(parts[4]),
        }
    return result


def fetch_index_sina(name: str, start: str, end: str) -> Optional[Dict[str, dict]]:
    """从新浪财经获取全球指数历史K线（东方财富的备用方案）"""
    try:
        import akshare as ak
        df = ak.index_global_hist_sina(symbol=name)
        if df is None or df.empty:
            print(f"    → 新浪返回空数据")
            return None
        # 筛选日期范围（新浪date是datetime.date类型，需统一）
        start_dt = datetime.strptime(start, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end, '%Y-%m-%d').date()
        df = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)]
        if df.empty:
            print(f"    → 新浪数据日期范围不匹配 ({start}~{end})")
            return None
        result = {}
        for _, row in df.iterrows():
            d = row['date'].strftime('%Y-%m-%d')  # 转为字符串统一格式
            result[d] = {
                'open': float(row['open']),
                'close': float(row['close']),
                'high': float(row['high']),
                'low': float(row['low']),
            }
        return result
    except Exception as e:
        print(f"    → 新浪接口异常: {type(e).__name__}: {e}")
        return None


def find_prev_trading_day(data: Dict[str, dict], date: str, max_back: int = 5) -> Optional[str]:
    """找 date 之前最近的一个交易日"""
    check = datetime.strptime(date, '%Y-%m-%d')
    for d in range(1, max_back + 1):
        day = (check - timedelta(days=d)).strftime('%Y-%m-%d')
        if day in data:
            return day
    return None


def main():
    print()
    print("=" * 110)
    print("  📊 回测收益率 vs 隔夜美股 + 亚洲早盘 关系分析")
    print(f"     分析区间: {BACKTEST_PERIODS[0]['buy']} ~ {BACKTEST_PERIODS[-1]['sell']}")
    print("=" * 110)

    # ── 获取三个指数数据（提前15天拉取，确保有隔夜数据）──
    first_buy = datetime.strptime(BACKTEST_PERIODS[0]['buy'], '%Y-%m-%d')
    start = (first_buy - timedelta(days=15)).strftime('%Y-%m-%d')
    end = BACKTEST_PERIODS[-1]['sell']

    print()
    nasdaq = fetch_nasdaq(start, end)

    # 日经225：东方财富优先 → 新浪降级
    nikkei = fetch_index_em("100.N225", "日经225", start, end)
    if nikkei is None:
        print("  ⚠ 日经225: 东方财富获取失败，切换至新浪财经...")
        nikkei = fetch_index_sina("日经225指数", start, end)
        if nikkei:
            print(f"  ✅ 日经225(新浪): {len(nikkei)} 个交易日")
        else:
            print("  ❌ 日经225: 新浪财经也获取失败")

    # KOSPI：东方财富优先 → 新浪降级
    kospi = fetch_index_em("100.KS11", "韩国KOSPI", start, end)
    if kospi is None:
        print("  ⚠ 韩国KOSPI: 东方财富获取失败，切换至新浪财经...")
        kospi = fetch_index_sina("首尔综合指数", start, end)
        if kospi:
            print(f"  ✅ 韩国KOSPI(新浪): {len(kospi)} 个交易日")
        else:
            print("  ❌ 韩国KOSPI: 新浪财经也获取失败")

    if not nasdaq and not nikkei and not kospi:
        print("\n  ❌ 所有指数数据获取失败")
        return

    print()
    print("─" * 110)

    # ── 主表 ──
    header = (
        f"  {'期次':>3}  "
        f"{'买入日':<10}  "
        f"{'收益率':>7}  "
        f"{'隔夜纳指':>10}  "
        f"{'纳指涨跌':>8}  "
        f"{'日经开盘':>10}  "
        f"{'日经涨跌':>8}  "
        f"{'KOSPI开':>10}  "
        f"{'KOSPI涨跌':>8}  "
        f"{'方向一致':<10}"
    )
    print(header)
    print(f"  {'─' * 105}")

    # 统计用数据
    all_directions = []  # (nasdaq>0, 日经>0, kospi>0, 收益>0)

    for i, p in enumerate(BACKTEST_PERIODS, 1):
        buy = p['buy']
        ret = p['return']
        note = p.get('note', '')
        ret_str = f"{ret:+.2f}%"

        # 纳斯达克：隔夜（前一日）
        prev = find_prev_trading_day(nasdaq, buy)
        if prev and prev in nasdaq:
            nd = nasdaq[prev]
            nd_change = nd['change_pct']
            nd_str = f"{nd['close']:>8.0f}"
            nd_chg_str = f"{nd_change:+.2f}%"
            nd_up = nd_change > 0
        else:
            nd_str = f"{'N/A':>8}"
            nd_chg_str = f"{'N/A':>8}"
            nd_up = None

        # 日经225：当日开盘
        if nikkei and buy in nikkei:
            nk = nikkei[buy]
            # 用开盘价与前一日收盘比算涨跌（反映早盘情绪）
            prev_nk = find_prev_trading_day(nikkei, buy)
            if prev_nk and prev_nk in nikkei:
                nk_change = (nk['open'] - nikkei[prev_nk]['close']) / nikkei[prev_nk]['close'] * 100
            else:
                nk_change = 0
            nk_str = f"{nk['open']:>8.0f}"
            nk_chg_str = f"{nk_change:+.2f}%"
            nk_up = nk_change > 0
        else:
            nk_str = f"{'N/A':>8}"
            nk_chg_str = f"{'N/A':>8}"
            nk_up = None

        # KOSPI：当日开盘
        if kospi and buy in kospi:
            ks = kospi[buy]
            prev_ks = find_prev_trading_day(kospi, buy)
            if prev_ks and prev_ks in kospi:
                ks_change = (ks['open'] - kospi[prev_ks]['close']) / kospi[prev_ks]['close'] * 100
            else:
                ks_change = 0
            ks_str = f"{ks['open']:>8.0f}"
            ks_chg_str = f"{ks_change:+.2f}%"
            ks_up = ks_change > 0
        else:
            ks_str = f"{'N/A':>8}"
            ks_chg_str = f"{'N/A':>8}"
            ks_up = None

        # 方向一致性（三个指数中，几个涨？）
        directions = [x for x in [nd_up, nk_up, ks_up] if x is not None]
        up_count = sum(1 for x in directions if x)
        if len(directions) >= 2:
            if up_count >= 2:
                dir_str = "📈📈 多数涨"
            elif up_count <= 0:
                dir_str = "📉📉 多数跌"
            else:
                dir_str = "🔄 分歧"
        else:
            dir_str = "数据不足"

        # 同向/反向标记（相对于A股收益）
        if ret > 0 and nd_up is not None and nd_up:
            tag = "✅"
        elif ret > 0 and nd_up is not None and not nd_up:
            tag = "🟡"
        elif ret < 0 and nd_up is not None and not nd_up:
            tag = "✅"
        elif ret < 0 and nd_up is not None and nd_up:
            tag = "🟡"
        else:
            tag = "  "

        line = (
            f"  {i:>3}  "
            f"{buy:<10}  "
            f"{ret_str:>7}  "
            f"{nd_str:>10}  "
            f"{nd_chg_str:>8}  "
            f"{nk_str:>10}  "
            f"{nk_chg_str:>8}  "
            f"{ks_str:>10}  "
            f"{ks_chg_str:>8}  "
            f"{dir_str:<10}{' '+note if note else ''}"
        )
        print(line)

        # 记录用于统计
        if nd_up is not None and nk_up is not None and ks_up is not None:
            all_directions.append((nd_up, nk_up, ks_up, ret > 0))

    print(f"  {'─' * 105}")

    # ── 统计分析 ──
    print()
    print("  📈 统计分析")
    print(f"  {'─' * 60}")

    # 1. 纳指 vs A股
    nasdaq_ret_pairs = []
    for p in BACKTEST_PERIODS:
        prev = find_prev_trading_day(nasdaq, p['buy'])
        if prev and prev in nasdaq:
            nd = nasdaq[prev]
            nd_chg = nd['change_pct']
            nasdaq_ret_pairs.append((nd_chg, p['return']))

    if nasdaq_ret_pairs:
        same = sum(1 for n, r in nasdaq_ret_pairs if (n > 0) == (r > 0))
        print(f"\n    📊 纳斯达克 vs A股（{len(nasdaq_ret_pairs)}次）:")
        print(f"       同向: {same}次 ({same/len(nasdaq_ret_pairs)*100:.0f}%)")
        nd_up_ret = [r for n, r in nasdaq_ret_pairs if n > 0]
        nd_dn_ret = [r for n, r in nasdaq_ret_pairs if n < 0]
        if nd_up_ret:
            print(f"       纳指涨→A股平均: {sum(nd_up_ret)/len(nd_up_ret):+.2f}%  (胜率{sum(1 for r in nd_up_ret if r>0)}/{len(nd_up_ret)})")
        if nd_dn_ret:
            print(f"       纳指跌→A股平均: {sum(nd_dn_ret)/len(nd_dn_ret):+.2f}%  (胜率{sum(1 for r in nd_dn_ret if r>0)}/{len(nd_dn_ret)})")

    # 2. 日经 vs A股
    nikkei_ret_pairs = []
    for p in BACKTEST_PERIODS:
        buy = p['buy']
        if nikkei and buy in nikkei:
            prev_nk = find_prev_trading_day(nikkei, buy)
            if prev_nk and prev_nk in nikkei:
                nk_chg = (nikkei[buy]['open'] - nikkei[prev_nk]['close']) / nikkei[prev_nk]['close'] * 100
                nikkei_ret_pairs.append((nk_chg, p['return']))

    if nikkei_ret_pairs:
        same_nk = sum(1 for n, r in nikkei_ret_pairs if (n > 0) == (r > 0))
        print(f"\n    📊 日经225开盘 vs A股（{len(nikkei_ret_pairs)}次）:")
        print(f"       同向: {same_nk}次 ({same_nk/len(nikkei_ret_pairs)*100:.0f}%)")
        nk_up_ret = [r for n, r in nikkei_ret_pairs if n > 0]
        nk_dn_ret = [r for n, r in nikkei_ret_pairs if n < 0]
        if nk_up_ret:
            print(f"       日经高开→A股平均: {sum(nk_up_ret)/len(nk_up_ret):+.2f}%  (胜率{sum(1 for r in nk_up_ret if r>0)}/{len(nk_up_ret)})")
        if nk_dn_ret:
            print(f"       日经低开→A股平均: {sum(nk_dn_ret)/len(nk_dn_ret):+.2f}%  (胜率{sum(1 for r in nk_dn_ret if r>0)}/{len(nk_dn_ret)})")

    # 3. KOSPI vs A股
    kospi_ret_pairs = []
    for p in BACKTEST_PERIODS:
        buy = p['buy']
        if kospi and buy in kospi:
            prev_ks = find_prev_trading_day(kospi, buy)
            if prev_ks and prev_ks in kospi:
                ks_chg = (kospi[buy]['open'] - kospi[prev_ks]['close']) / kospi[prev_ks]['close'] * 100
                kospi_ret_pairs.append((ks_chg, p['return']))

    if kospi_ret_pairs:
        same_ks = sum(1 for k, r in kospi_ret_pairs if (k > 0) == (r > 0))
        print(f"\n    📊 KOSPI开盘 vs A股（{len(kospi_ret_pairs)}次）:")
        print(f"       同向: {same_ks}次 ({same_ks/len(kospi_ret_pairs)*100:.0f}%)")
        ks_up_ret = [r for k, r in kospi_ret_pairs if k > 0]
        ks_dn_ret = [r for k, r in kospi_ret_pairs if k < 0]
        if ks_up_ret:
            print(f"       KOSPI高开→A股平均: {sum(ks_up_ret)/len(ks_up_ret):+.2f}%  (胜率{sum(1 for r in ks_up_ret if r>0)}/{len(ks_up_ret)})")
        if ks_dn_ret:
            print(f"       KOSPI低开→A股平均: {sum(ks_dn_ret)/len(ks_dn_ret):+.2f}%  (胜率{sum(1 for r in ks_dn_ret if r>0)}/{len(ks_dn_ret)})")

    # 4. 三指数共识分析
    if all_directions:
        print(f"\n    📊 三指数共识 vs A股（{len(all_directions)}次）:")
        consensus_up = sum(1 for n, nk, ks, r in all_directions if n and nk and ks)
        consensus_dn = sum(1 for n, nk, ks, r in all_directions if not n and not nk and not ks)
        print(f"       三指数一致看涨: {consensus_up}次")
        print(f"       三指数一致看跌: {consensus_dn}次")
        # 三指数一致时A股的表现
        for label, cond in [('一致看涨时', lambda n, nk, ks: n and nk and ks),
                            ('一致看跌时', lambda n, nk, ks: not n and not nk and not ks)]:
            matched = [(n, nk, ks, r) for n, nk, ks, r in all_directions if cond(n, nk, ks)]
            if matched:
                win = sum(1 for _, _, _, r in matched if r)
                win_rate = win / len(matched) * 100
                print(f"       {label}: A股胜率 {win}/{len(matched)} ({win_rate:.0f}%)")

    # ── 结论 ──
    print()
    print("  💡 初步结论")
    print(f"  {'─' * 60}")

    if nasdaq_ret_pairs:
        nd_same_pct = sum(1 for n, r in nasdaq_ret_pairs if (n > 0) == (r > 0)) / len(nasdaq_ret_pairs) * 100
        print(f"\n    📈 纳斯达克与A股同向率: {nd_same_pct:.0f}%")
    if nikkei_ret_pairs:
        nk_same_pct = sum(1 for n, r in nikkei_ret_pairs if (n > 0) == (r > 0)) / len(nikkei_ret_pairs) * 100
        print(f"    📈 日经225开盘与A股同向率: {nk_same_pct:.0f}%")
    if kospi_ret_pairs:
        ks_same_pct = sum(1 for k, r in kospi_ret_pairs if (k > 0) == (r > 0)) / len(kospi_ret_pairs) * 100
        print(f"    📈 KOSPI开盘与A股同向率: {ks_same_pct:.0f}%")

    print(f"\n    ⚠ 仅12期样本，结论需后续更多数据验证")
    print()
    print("=" * 110)
    print()


if __name__ == "__main__":
    main()
