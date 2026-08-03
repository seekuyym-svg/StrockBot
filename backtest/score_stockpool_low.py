# -*- coding: utf-8 -*-
"""
股票池低分扫描工具 — 从 generate_stockpool.py 生成的股票池中找出综合评分≤20 的股票

数据流：
  data/stockpool_YYYYMMDD.txt (选股原池)
      → 本地K线评分 (综合分 + 优选分)
      → 综合分≤10 过滤
      → data/stockpool_YYYYMMDD_low.txt

用法：
    python backtest/score_stockpool_low.py --date 2026-07-23
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import time
from datetime import datetime
from loguru import logger
import pandas as pd
from typing import List, Optional, Tuple


class LowScoreFinder:
    """低分扫描器"""
    
    def __init__(self, tdx_dir: str = None):
        if tdx_dir is None:
            try:
                from src.utils.config import get_config
                config = get_config()
                tdx_dir = getattr(config, 'tdx_dir', 'D:\\Install\\zd_zxzq_gm')
            except Exception:
                tdx_dir = 'D:\\Install\\zd_zxzq_gm'
        
        from mootdx.reader import Reader
        self.reader = Reader.factory(market='std', tdxdir=tdx_dir)
        
        # 优选分计算参数（与 score_stockpool_my.py 一致）
        self.pref_vol_ratio_threshold = 2.8
        self.pref_vol_ratio_min = 1.2
        self.pref_upper_shadow_threshold = 2.5
        self._score_trend_cache = {}
        
        logger.info(f"✅ 已初始化 (通达信目录: {tdx_dir})")
    
    def _get_historical_klines(self, stock_code: str, analysis_date: str, days: int = 300) -> pd.DataFrame:
        if stock_code.startswith(('sh', 'sz', 'bj')):
            market = stock_code[:2]
            code = stock_code[2:]
        else:
            code = stock_code
            market = 'sh' if code.startswith(('6', '9')) else 'sz'
        from local.utils import _get_historical_klines as _get_data
        return _get_data(market, code, days=days, end_date=analysis_date, min_data_length=60)
    
    def calc_pref_score(self, market: str, code: str, analysis_date: str, current_score: float = None) -> float:
        """计算优选分（0~25），与 score_stockpool_my.py 一致"""
        try:
            df = self._get_historical_klines(f"{market}{code}", analysis_date, days=90)
            if df is None or df.empty or len(df) < 30:
                return 0
            
            closes = df['close'].values
            latest_close = closes[-1]
            total = 0.0
            
            # ①趋势疲劳度（6分）
            consecutive_up = 0
            for i in range(len(df)-1, max(0, len(df)-15), -1):
                if df['close'].iloc[i] > df['open'].iloc[i]:
                    consecutive_up += 1
                else:
                    break
            if consecutive_up <= 3: total += 6.0
            elif consecutive_up <= 5: total += 4.0
            elif consecutive_up <= 7: total += 2.0
            
            # ②前高压力（6分）
            lookback = min(60, len(df))
            high_60d = df['high'].iloc[-lookback:].max()
            distance_to_high = (latest_close - high_60d) / high_60d * 100 if high_60d > 0 else 0
            if distance_to_high > 5: total += 2.0
            elif distance_to_high > 0: total += 4.0
            elif distance_to_high > -5: total += 2.0
            elif distance_to_high > -10: total += 4.0
            else: total += 6.0
            
            # ③当日强度（4分）
            prev_close = closes[-2] if len(closes) >= 2 else latest_close
            change_pct = (latest_close - prev_close) / prev_close * 100 if prev_close > 0 else 0
            vol_ma20 = df['volume'].iloc[-20:].mean()
            vol_ratio = df['volume'].iloc[-1] / vol_ma20 if vol_ma20 > 0 else 0
            pr_min = self.pref_vol_ratio_min
            pr_mid = (pr_min + self.pref_vol_ratio_threshold) / 2
            if 1 <= change_pct <= 3 and pr_min <= vol_ratio <= pr_mid: total += 4.0
            elif 0 <= change_pct <= 1 and pr_min * 0.7 <= vol_ratio <= pr_mid: total += 2.0
            elif -1 <= change_pct <= 0 and pr_min * 0.7 <= vol_ratio <= pr_mid: total += 2.0
            elif change_pct > 3: total += 1.0
            elif change_pct < -2: total += 0.0
            else: total += 1.0
            
            # 上影线修正
            upper_shadows = []
            for i in range(3):
                h = df['high'].iloc[-1-i]
                c = df['close'].iloc[-1-i]
                o = df['open'].iloc[-1-i]
                if h > 0:
                    upper_shadows.append((h - max(c, o)) / h * 100)
            if len(upper_shadows) == 3 and sum(upper_shadows)/3 > self.pref_upper_shadow_threshold:
                total -= 2.0
            
            # ④乖离率（4分）
            ma20 = df['close'].rolling(20).mean().iloc[-1]
            if pd.notna(ma20) and ma20 > 0:
                deviation = (latest_close - ma20) / ma20 * 100
                if 2 <= deviation <= 4: total += 4.0
                elif 4 < deviation <= 6: total += 2.0
                elif 0 <= deviation < 2: total += 2.0
                elif deviation > 6: total += 0.0
                else: total += 0.0
            
            # ⑤评分趋势（5分）
            hist_scores = self._score_trend_cache.get(code) or []
            if not hist_scores:
                score_file = Path(__file__).parent.parent / "data" / "score" / f"{code}.txt"
                if score_file.exists():
                    for line in score_file.read_text(encoding='utf-8').splitlines():
                        parts = line.strip().split(',')
                        if len(parts) >= 2:
                            try: hist_scores.append(float(parts[1]))
                            except ValueError: continue
                self._score_trend_cache[code] = hist_scores
            
            yesterday_score = hist_scores[-1] if len(hist_scores) >= 1 else None
            day_before_score = hist_scores[-2] if len(hist_scores) >= 2 else None
            
            if current_score is not None:
                from local.utils import calculate_trend_score_v2 as _calc_s
                trade_dates = df.index[-3:]
                if len(trade_dates) >= 2 and yesterday_score is None:
                    yesterday_score = _calc_s(market, code, end_date=trade_dates[-2].strftime('%Y-%m-%d'))
                if len(trade_dates) >= 3 and day_before_score is None:
                    day_before_score = _calc_s(market, code, end_date=trade_dates[-3].strftime('%Y-%m-%d'))
                if day_before_score is not None and yesterday_score is not None:
                    if day_before_score < yesterday_score < current_score: total += 5.0
                    elif yesterday_score < current_score: total += 3.0
                elif yesterday_score is not None and yesterday_score < current_score: total += 3.0
            
            return min(total, 25.0)
        except Exception:
            return 0
    
    def load_stockpool(self, date_str: str) -> List[str]:
        """加载 generate_stockpool.py 生成的股票池"""
        formatted_date = date_str.replace("-", "")
        filepath = Path(__file__).parent.parent / "data" / f"stockpool_{formatted_date}.txt"
        
        if not filepath.exists():
            print(f"[ERROR] 股票池文件不存在: {filepath}")
            return []
        
        stocks = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('-') or line.startswith('code'):
                    continue
                parts = line.split(',')
                if parts and parts[0].isdigit() and len(parts[0]) == 6:
                    stocks.append(parts[0])
        
        print(f"[LOAD] {filepath.name}: {len(stocks)} 只股票")
        return stocks
    
    def analyze_stock(self, code: str, analysis_date: str) -> Optional[Tuple[float, float]]:
        """分析单只股票, 返回 (综合评分, 优选分)"""
        market = 'sh' if code.startswith(('6', '9')) else 'sz'
        try:
            from local.utils import calculate_trend_score_v2
            score = calculate_trend_score_v2(market, code, days=300, end_date=analysis_date)
            if score is None:
                return None
            pref = self.calc_pref_score(market, code, analysis_date, current_score=score)
            return (score, pref)
        except Exception as e:
            return None


def main():
    parser = argparse.ArgumentParser(description="从选股池中找出综合评分≤20 的股票")
    parser.add_argument('--date', type=str, required=True, help='分析日期 (格式: YYYY-MM-DD)')
    parser.add_argument('--tdx-dir', type=str, help='通达信安装目录')
    args = parser.parse_args()
    
    date_str = args.date
    formatted_date = date_str.replace("-", "")
    
    finder = LowScoreFinder(tdx_dir=args.tdx_dir)
    
    # 1. 加载股票池
    stocks = finder.load_stockpool(date_str)
    if not stocks:
        print("[EXIT] 无股票可分析")
        return
    
    # 2. 批量评分
    print(f"\n[SCORE] 开始评分（日期: {date_str}）...")
    results = []
    start_time = time.time()
    total = len(stocks)
    
    for i, code in enumerate(stocks, 1):
        result = finder.analyze_stock(code, date_str)
        if result is not None:
            score, pref = result
            if score <= 20:
                results.append((code, score, pref))
        
        if i % 50 == 0 or i == total:
            elapsed = time.time() - start_time
            print(f"\r  进度: {i}/{total} ({i/total*100:.0f}%) | 已找到 {len(results)} 只 ≤10分 | 耗时: {elapsed:.0f}s", end='', flush=True)
    
    elapsed = time.time() - start_time
    print(f"\n\n[OK] 评分完成: {total} 只, 耗时 {elapsed:.0f}s")
    
    # 3. 按评分升序排列（最低的排最前）
    results.sort(key=lambda x: x[1])
    
    # 4. 输出
    output_file = Path(__file__).parent.parent / "data" / f"stockpool_{formatted_date}_low.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"# === 综合评分≤20 股票 (自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===\n")
        f.write(f"# 数据源: stockpool_{formatted_date}.txt ({len(stocks)} 只)\n")
        f.write(f"# 格式: 股票代码,综合评分,优选分  | 共 {len(results)} 只\n")
        f.write(f"# 已按综合评分升序排列（最低的排最前）\n")
        f.write("\n")
        for code, score, pref in results:
            f.write(f"{code},{score:.0f},{pref}\n")
    
    print(f"[SAVE] {output_file}")
    print(f"[DONE] 共找到 {len(results)} 只综合评分≤20 的股票（来源池 {len(stocks)} 只）")


if __name__ == "__main__":
    main()
