# -*- coding: utf-8 -*-
"""
验证 [超跌] 标记的优选分门槛是否需要存在

方法：取6月初的一批股票评分，按综合分≤15分组后，
      对比 优选分≤6 vs 优选分>6 两组后续5日收益率。
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta
from typing import List, Tuple, Optional
import pandas as pd
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="INFO")


def find_next_trading_day(df: pd.DataFrame, base_date: str, offset: int = 5):
    """在 DataFrame 中找到 base_date 之后第 offset 个交易日"""
    base_dt = pd.to_datetime(base_date)
    future_dates = df[df.index > base_dt].index.sort_values()
    if len(future_dates) >= offset:
        target = future_dates[offset - 1]
        return target.strftime('%Y-%m-%d'), float(df.loc[target, 'close'])
    return None, None


def get_price_at_date(df: pd.DataFrame, target_date: str) -> Optional[float]:
    target_dt = pd.to_datetime(target_date)
    if target_dt in df.index:
        return float(df.loc[target_dt, 'close'])
    return None


def analyze_stock_forward(code: str, market: str, analysis_date: str,
                          lookahead: int = 5) -> Optional[float]:
    """分析股票在 analysis_date 之后 lookahead 个交易日的收益率"""
    try:
        from local.utils import _get_historical_klines
        df = _get_historical_klines(market, code, days=400, end_date=None, min_data_length=60)
        if df is None or df.empty:
            return None

        entry_price = get_price_at_date(df, analysis_date)
        if entry_price is None or entry_price <= 0:
            return None

        _, exit_price = find_next_trading_day(df, analysis_date, offset=lookahead)
        if exit_price is None or exit_price <= 0:
            return None

        return (exit_price - entry_price) / entry_price * 100
    except Exception as e:
        logger.debug(f"[ERROR] {code}: {e}")
        return None


def main():
    # === 选一批股票作为样本（从主池文件里收集代码）===
    data_dir = Path(__file__).parent.parent / "data"
    all_codes = set()
    for f in sorted(data_dir.glob("stockpool_202606*.txt")):
        if '_all' in f.name or 'bak' in f.name or 'score' in f.name:
            continue
        with open(f, 'r', encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('-'):
                    continue
                parts = line.split(',')
                if parts and parts[0].isdigit() and len(parts[0]) == 6:
                    all_codes.add(parts[0])

    all_codes = sorted(all_codes)
    print(f"收集到 {len(all_codes)} 只不同股票代码")

    # === 选一个历史评分日期（6月初，确保有未来数据）===
    analysis_date = "2026-06-01"
    lookahead = 5
    
    from local.utils import calculate_trend_score_v2
    from local.utils import _get_historical_klines
    
    candidates = []
    total = len(all_codes)
    
    print(f"\n开始评分（日期: {analysis_date}，向前看{lookahead}个交易日）...")
    
    for i, code in enumerate(all_codes):
        if (i+1) % 50 == 0 or i == 0:
            print(f"  进度: {i+1}/{total}")
        
        market = 'sh' if code.startswith(('6', '9')) else 'sz'
        
        # 计算综合评分
        score = calculate_trend_score_v2(market, code, days=300, end_date=analysis_date)
        if score is None or score > 15:
            continue
        
        # 计算优选分（复用 score_stockpool_my.py 的逻辑）
        # 直接在这里计算简单版优选分
        pref = 0
        try:
            df = _get_historical_klines(market, code, days=90, end_date=analysis_date, min_data_length=30)
            if df is not None and len(df) >= 30:
                closes = df['close'].values
                latest_close = closes[-1]
                total_p = 0.0
                
                # ①趋势疲劳度
                consecutive_up = 0
                for j in range(len(df)-1, max(0, len(df)-15), -1):
                    if df['close'].iloc[j] > df['open'].iloc[j]:
                        consecutive_up += 1
                    else:
                        break
                if consecutive_up <= 3:
                    total_p += 6.0
                elif consecutive_up <= 5:
                    total_p += 4.0
                elif consecutive_up <= 7:
                    total_p += 2.0
                
                # ②前高压力
                lookback = min(60, len(df))
                high_60d = df['high'].iloc[-lookback:].max()
                dist = (latest_close - high_60d) / high_60d * 100 if high_60d > 0 else 0
                if dist > 5:
                    total_p += 2.0
                elif dist > 0:
                    total_p += 4.0
                elif dist > -5:
                    total_p += 2.0
                elif dist > -10:
                    total_p += 4.0
                else:
                    total_p += 6.0
                
                # ③当日强度（简化版）
                prev_close = closes[-2] if len(closes) >= 2 else latest_close
                chg_pct = (latest_close - prev_close) / prev_close * 100 if prev_close > 0 else 0
                if 1 <= chg_pct <= 3:
                    total_p += 4.0
                elif 0 <= chg_pct <= 1:
                    total_p += 2.0
                elif -1 <= chg_pct <= 0:
                    total_p += 2.0
                elif chg_pct > 3:
                    total_p += 1.0
                else:
                    total_p += 0.0
                
                # ④乖离率（简化版）
                ma20 = df['close'].rolling(20).mean().iloc[-1]
                if pd.notna(ma20) and ma20 > 0:
                    dev = (latest_close - ma20) / ma20 * 100
                    if 2 <= dev <= 4:
                        total_p += 4.0
                    elif 0 <= dev < 2 or 4 < dev <= 6:
                        total_p += 2.0
                    elif dev > 6:
                        total_p += 0.0
                    else:
                        total_p += 0.0
                
                pref = min(total_p, 25.0)
        except Exception:
            pass
        
        # 计算后续收益率
        ret = analyze_stock_forward(code, market, analysis_date, lookahead=lookahead)
        if ret is not None:
            candidates.append((code, market, score, pref, ret))
    
    print(f"\n评分完成，综合分≤15的样本: {len(candidates)} 只")
    
    if not candidates:
        print("没有样本数据，无法验证")
        return
    
    # === 分组对比 ===
    group_A = candidates  # 全部综合分≤15
    group_B = [(c, m, s, p, r) for c, m, s, p, r in candidates if p <= 6]  # 优选分≤6
    group_C = [(c, m, s, p, r) for c, m, s, p, r in candidates if p > 6]   # 优选分>6
    
    def stats(group, label):
        if not group:
            print(f"\n{label}: 无样本")
            return
        returns = [r for _, _, _, _, r in group]
        scores = [s for _, _, s, _, _ in group]
        prefs = [p for _, _, _, p, _ in group]
        avg_ret = sum(returns) / len(returns)
        pos_count = sum(1 for r in returns if r > 0)
        neg_count = sum(1 for r in returns if r < 0)
        zero_count = sum(1 for r in returns if r == 0)
        win_rate = pos_count / len(returns) * 100
        max_gain = max(returns)
        max_loss = min(returns)
        
        print(f"\n{label}: {len(group)} 个样本")
        print(f"  平均综合分: {sum(scores)/len(scores):.1f}  平均优选分: {sum(prefs)/len(prefs):.1f}")
        print(f"  平均{lookahead}日收益率: {avg_ret:+.2f}%")
        print(f"  胜率: {win_rate:.0f}% ({pos_count}涨/{neg_count}跌/{zero_count}平)")
        print(f"  最大涨幅: {max_gain:+.2f}%")
        print(f"  最大跌幅: {max_loss:+.2f}%")
        
        # 打印具体股票
        print(f"  明细:")
        sorted_g = sorted(group, key=lambda x: x[3], reverse=True)
        for code, mkt, sc, pr, rr in sorted_g[:10]:
            tag = ' ←超跌标的' if pr <= 6 else ''
            print(f"    {code} 综合{sc:.0f} 优选{pr:.0f} 收益{rr:+.1f}%{tag}")
    
    stats(group_A, f"【组A】综合分≤15（全部）")
    stats(group_B, f"【组B】综合分≤15 + 优选分≤6")
    stats(group_C, f"【组C】综合分≤15 + 优选分>6")
    
    # 结论
    if group_B and group_C:
        rets_B = [r for _, _, _, _, r in group_B]
        rets_C = [r for _, _, _, _, r in group_C]
        avg_B = sum(rets_B) / len(rets_B)
        avg_C = sum(rets_C) / len(rets_C)
        diff = avg_B - avg_C
        win_B = sum(1 for r in rets_B if r > 0) / len(rets_B) * 100
        win_C = sum(1 for r in rets_C if r > 0) / len(rets_C) * 100
        
        print(f"\n{'='*60}")
        print(f"【核心对比】组B(优选分≤6) vs 组C(优选分>6)")
        print(f"{'='*60}")
        print(f"  平均收益率:    组B {avg_B:+.2f}%  vs  组C {avg_C:+.2f}%  (差值 {diff:+.2f}%)")
        print(f"  胜率:          组B {win_B:.0f}%  vs  组C {win_C:.0f}%")
        if diff > 1 and win_B > win_C:
            print(f"\n  ✅ 结论: 优选分≤6 限制有效！动能衰竭的超跌股后续表现更好")
        elif diff > 0:
            print(f"\n  ⚠️ 结论: 优选分≤6 限制有微弱正向作用，但差距不明显")
        elif diff > -1:
            print(f"\n  ⚠️ 结论: 优选分≤6 限制基本无区别")
        else:
            print(f"\n  ❌ 结论: 优选分≤6 限制反而漏掉好股票，建议去掉")


if __name__ == "__main__":
    main()
