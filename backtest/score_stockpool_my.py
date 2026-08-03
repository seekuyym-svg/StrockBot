# -*- coding: utf-8 -*-
"""
股票池批量评分工具（针对 _my.txt 自定义股票池 — 简洁版）

功能：
1. 读取 _my.txt 股票池文件（仅有股票代码），计算综合评分 + 优选分
2. 按综合评分降序排列，将所有结果写入文件
3. 不做任何过滤：保留所有分值的股票

使用方法：
    python backtest/score_stockpool_my.py --date 2026-05-06
    python backtest/score_stockpool_my.py --start-date 2024-01-01 --end-date 2024-01-10
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import argparse
import os
import sys
import time
from pathlib import Path
import shutil
from loguru import logger

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from mootdx.reader import Reader
except ImportError:
    print("错误: 无法导入 mootdx 模块，请安装: pip install mootdx")
    raise


class HistoricalStockScorer:
    """历史股票评分器（针对 _my.txt 自定义股票池 — 简洁版）"""
    
    def __init__(self, tdx_dir: str = None):
        """
        初始化评分器
        
        Args:
            tdx_dir: 通达信安装目录，默认从环境变量或配置读取
        """
        if tdx_dir is None:
            try:
                from src.utils.config import get_config
                config = get_config()
                tdx_dir = getattr(config, 'tdx_dir', 'D:\\Install\\zd_zxzq_gm')
            except Exception as e:
                logger.debug(f"⚠️ 读取配置失败: {e}，使用默认通达信目录")
                tdx_dir = 'D:\\Install\\zd_zxzq_gm'
        
        self.reader = Reader.factory(market='std', tdxdir=tdx_dir)
        # 优选分计算所需参数
        self.pref_vol_ratio_threshold = 2.8
        self.pref_vol_ratio_min = 1.2
        self.pref_upper_shadow_threshold = 2.5
        # 评分趋势缓存
        self._score_trend_cache = {}
        # 名称+行业信息缓存
        self.info_cache = {}  # code -> {name, industry}
        self.info_cache_file = Path(__file__).parent.parent / "data" / "stock_info_cache.json"
        self._load_info_cache()
        logger.info(f"✅ 已初始化 mootdx Reader (通达信目录: {tdx_dir})")
    
    def _load_info_cache(self):
        """从本地文件加载股票名称+行业信息缓存"""
        try:
            if self.info_cache_file.exists():
                import json
                with open(self.info_cache_file, 'r', encoding='utf-8') as f:
                    self.info_cache = json.load(f)
                logger.debug(f"[CACHE] 已加载 {len(self.info_cache)} 条名称+行业信息")
        except Exception as e:
            logger.debug(f"[CACHE] 加载信息缓存失败: {e}")
    
    def _save_info_cache(self):
        """保存股票名称+行业信息缓存到本地文件"""
        try:
            import json
            with open(self.info_cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.info_cache, f, ensure_ascii=False, indent=2)
            logger.debug(f"[CACHE] 已保存 {len(self.info_cache)} 条名称+行业信息")
        except Exception as e:
            logger.debug(f"[CACHE] 保存信息缓存失败: {e}")
    
    def _get_stock_info(self, symbol: str) -> Tuple[str, Optional[str]]:
        """
        获取股票名称和行业（带缓存）

        名称复用 local/utils.py 的 get_stock_name（腾讯→新浪→东方财富多数据源降级），
        行业通过东方财富公司概况接口获取，结果缓存到本地 JSON 文件。

        Returns:
            (股票名称, 行业名称)，获取失败时名称返回 code，行业返回 None
        """
        code = symbol.split('.')[1] if '.' in symbol else symbol

        # 检查缓存
        if code in self.info_cache:
            info = self.info_cache[code]
            return info.get('name', code), info.get('industry')

        name = code
        industry = None

        # === 名称：复用 local/utils.py 的 get_stock_name ===
        try:
            from local.utils import get_stock_name as _get_name
            fetched = _get_name(code)
            if fetched and fetched != code:
                name = fetched
        except Exception as e:
            logger.debug(f"[INFO] get_stock_name 获取 {code} 失败: {e}")

        # === 行业：东方财富公司概况接口 ===
        try:
            import requests as req
            market_code = 'SZ' if code.startswith(('0', '3')) else 'SH'
            url = "http://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/CompanySurveyAjax"
            params = {"code": f"{market_code}{code}"}
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'http://quote.eastmoney.com/'
            }
            time.sleep(0.25)
            response = req.get(url, params=params, headers=headers, timeout=10)
            data = response.json()
            jbzl = data.get('jbzl')
            if jbzl:
                ind = jbzl.get('sshy')
                if ind:
                    industry = str(ind)
        except Exception as e:
            logger.debug(f"[INFO] 东方财富行业获取 {code} 失败: {e}")

        # 缓存并保存
        self.info_cache[code] = {'name': name, 'industry': industry}
        self._save_info_cache()

        return name, industry
    
    def _get_historical_klines(self, stock_code: str, analysis_date: str, days: int = 300) -> pd.DataFrame:
        """
        获取指定日期之前的历史K线数据
        统一委托给 local/utils.py 的实现（本地通达信 → 腾讯API降级）
        """
        if stock_code.startswith(('sh', 'sz', 'bj')):
            market = stock_code[:2]
            code = stock_code[2:]
        else:
            code = stock_code
            market = 'sh' if code.startswith(('6', '9')) else 'sz'
        
        from local.utils import _get_historical_klines as _get_data
        return _get_data(market, code, days=days, end_date=analysis_date, min_data_length=60)
    
    def analyze_stock(self, symbol: str, analysis_date: str) -> Optional[Tuple[float, float]]:
        """
        分析单只股票并返回评分（基于指定历史日期）
        
        Returns:
            Tuple[综合评分(0-100), 优选分(0-25)]，失败返回 None
        """
        try:
            parts = symbol.split('.')
            if len(parts) != 2:
                return None
            
            market = parts[0].lower()
            code = parts[1]
            
            from local.utils import calculate_trend_score_v2
            score = calculate_trend_score_v2(market, code, days=300, end_date=analysis_date)
            
            if score is None:
                return None
            
            pref_score = self._calc_pref_and_veto(market, code, analysis_date, current_score=score)
            return (score, pref_score)
                
        except Exception as e:
            logger.debug(f"❌ 分析 {symbol} 失败: {e}")
            return None
    
    def _calc_pref_and_veto(self, market: str, code: str, 
                            analysis_date: str, current_score: float = None) -> float:
        """
        计算优选分（0~25分）— 强势延续性评估
        
        五项评分：
          ① 趋势疲劳度（连续上涨天数）→ 0~6分
          ② 前高压力（距离60日最高价）→ 0~6分
          ③ 当日强度（涨跌幅+量比配合）→ 0~4分
          ④ 乖离率（偏离20日线幅度）→ 0~4分
          ⑤ 评分趋势（历史综合评分走势）→ 0~5分
        """
        try:
            df = self._get_historical_klines(f"{market}{code}", analysis_date, days=90)
            if df.empty or len(df) < 30:
                return 0
            
            closes = df['close'].values
            latest_close = closes[-1]
            total = 0.0
            
            # === ① 趋势疲劳度（6分） ===
            consecutive_up = 0
            for i in range(len(df)-1, max(0, len(df)-15), -1):
                if df['close'].iloc[i] > df['open'].iloc[i]:
                    consecutive_up += 1
                else:
                    break
            
            if consecutive_up <= 3:
                total += 6.0
            elif consecutive_up <= 5:
                total += 4.0
            elif consecutive_up <= 7:
                total += 2.0
            else:
                total += 0.0
            
            # === ② 前高压力（6分） ===
            lookback = min(60, len(df))
            high_60d = df['high'].iloc[-lookback:].max()
            distance_to_high = (latest_close - high_60d) / high_60d * 100 if high_60d > 0 else 0
            
            if distance_to_high > 5:
                total += 2.0
            elif distance_to_high > 0:
                total += 4.0
            elif distance_to_high > -5:
                total += 2.0
            elif distance_to_high > -10:
                total += 4.0
            else:
                total += 6.0
            
            # === ③ 当日强度（4分） ===
            prev_close = closes[-2] if len(closes) >= 2 else latest_close
            change_pct = (latest_close - prev_close) / prev_close * 100 if prev_close > 0 else 0
            
            vol_ma20 = df['volume'].iloc[-20:].mean()
            vol_ratio = df['volume'].iloc[-1] / vol_ma20 if vol_ma20 > 0 else 0
            pr_min = self.pref_vol_ratio_min
            pr_mid = (pr_min + self.pref_vol_ratio_threshold) / 2
            
            if 1 <= change_pct <= 3 and pr_min <= vol_ratio <= pr_mid:
                total += 4.0
            elif 0 <= change_pct <= 1 and pr_min * 0.7 <= vol_ratio <= pr_mid:
                total += 2.0
            elif -1 <= change_pct <= 0 and pr_min * 0.7 <= vol_ratio <= pr_mid:
                total += 2.0
            elif change_pct > 3:
                total += 1.0
            elif change_pct < -2:
                total += 0.0
            else:
                total += 1.0
            
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
            
            # === ④ 乖离率（4分） ===
            ma20 = df['close'].rolling(20).mean().iloc[-1]
            if pd.notna(ma20) and ma20 > 0:
                deviation = (latest_close - ma20) / ma20 * 100
                if 2 <= deviation <= 4:
                    total += 4.0
                elif 4 < deviation <= 6:
                    total += 2.0
                elif 0 <= deviation < 2:
                    total += 2.0
                elif deviation > 6:
                    total += 0.0
                else:
                    total += 0.0
            
            # === ⑤ 评分趋势（5分） ===
            hist_scores = self._score_trend_cache.get(code) or []
            if not hist_scores:
                score_file = Path(__file__).parent.parent / "data" / "score" / f"{code}.txt"
                if score_file.exists():
                    for line in score_file.read_text(encoding='utf-8').splitlines():
                        parts = line.strip().split(',')
                        if len(parts) >= 2:
                            try:
                                hist_scores.append(float(parts[1]))
                            except ValueError:
                                continue
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
                    if day_before_score < yesterday_score < current_score:
                        total += 5.0
                    elif yesterday_score < current_score:
                        total += 3.0
                elif yesterday_score is not None and yesterday_score < current_score:
                    total += 3.0
            
            return min(total, 25.0)
            
        except Exception:
            return 0
    
    def load_stock_pool(self, date_str: str) -> List[str]:
        """
        加载指定日期的 _my.txt 股票池
        
        Args:
            date_str: 日期字符串，格式为 YYYY-MM-DD
            
        Returns:
            股票代码列表（带市场前缀）
        """
        formatted_date = date_str.replace("-", "")
        filename = f"stockpool_{formatted_date}_my.txt"
        filepath = Path(__file__).parent.parent / "data" / filename
        
        if not filepath.exists():
            return []
        
        stocks = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('-'):
                    continue
                
                if ',' in line:
                    code = line.split(',')[0].strip()
                else:
                    code = line
                
                if not code.startswith(('sh.', 'sz.', 'bj.')):
                    if code.startswith('6'):
                        code = f'sh.{code}'
                    elif code.startswith(('0', '3')):
                        code = f'sz.{code}'
                    elif code.startswith(('8', '4')):
                        code = f'bj.{code}'
                    else:
                        continue
                
                stocks.append(code)
        
        return stocks
    
    def append_scores_to_file(self, date_str: str, 
                              scored_results: List[Tuple[str, float, int]], 
                              backup: bool = False):
        """
        将全部评分结果按综合分降序写入 _my.txt 文件，不做过滤
        
        Args:
            date_str: 日期字符串 (格式: YYYY-MM-DD)
            scored_results: [(股票代码, 评分, 优选分), ...]
            backup: 是否创建备份文件
        """
        formatted_date = date_str.replace("-", "")
        filename = f"stockpool_{formatted_date}_my.txt"
        filepath = Path(__file__).parent.parent / "data" / filename
        
        if not scored_results:
            logger.warning(f"[WARN] {date_str}: 无评分结果，跳过保存")
            return
        
        # 读取原始文件中的注释/表头
        original_lines = []
        has_original = filepath.exists()
        if has_original:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    stripped = line.strip()
                    if stripped.startswith('#') or stripped.startswith('-') or stripped == '':
                        original_lines.append(line.rstrip('\n'))
        
        # 按综合评分降序排列（综合分相同则优选分高的在前）
        sorted_results = sorted(scored_results, key=lambda x: (x[1], x[2]), reverse=True)
        
        # 备份
        if backup and has_original:
            backup_path = filepath.with_suffix('.txt.bak')
            if not backup_path.exists():
                shutil.copy(filepath, backup_path)
                logger.debug(f"💾 已创建备份文件: {backup_path.name}")
        
        # 写入文件：原始注释 + 评分数据（全部保留，不做过滤）
        with open(filepath, 'w', encoding='utf-8') as f:
            for line in original_lines:
                f.write(line + '\n')
            
            f.write(f"\n# === 技术评分数据 (自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===\n")
            f.write(f"# 格式: 股票代码,综合评分,优选分,行业,股票名称[,[可能超跌]]  | 共 {len(sorted_results)} 只\n")
            f.write(f"# 已按综合评分降序排列\n")
            f.write(f"# [\u53ef\u80fd\u8d85\u8dcc] = \u7efc\u5408\u5206\u226410\uff0c\u610f\u5473\u6781\u5ea6\u4f4e\u5206\uff0c\u53ef\u80fd\u5c5e\u4e8e\u8d85\u8dcc\u53cd\u5f39\u5019\u9009\n")
            
            for symbol, score, pref in sorted_results:
                code = symbol.split('.')[1] if '.' in symbol else symbol
                name, industry = self._get_stock_info(symbol)
                ind_str = industry if industry else ''
                # \u53ef\u80fd\u8d85\u8dcc\u6807\u8bb0\uff1a\u7efc\u5408\u5206\u226410\uff0c\u610f\u5473\u6781\u5ea6\u4f4e\u5206\uff0c\u53ef\u80fd\u5c5e\u4e8e\u8d85\u8dcc\u53cd\u5f39\u5019\u9009
                oversold = score <= 10
                tag = ',[\u53ef\u80fd\u8d85\u8dcc]' if oversold else ''
                f.write(f"{code},{score:.0f},{pref},{ind_str},{name}{tag}\n")
        
        scores_range = f"{sorted_results[-1][1]:.0f}~{sorted_results[0][1]:.0f}"
        logger.info(f"[SAVE] {date_str}: 已保存 {len(sorted_results)} 只股票 (评分区间 {scores_range}) 到 {filename}")
        
        # ── 额外保存：触发[可能超跌]的个股单独存为 _low.txt（暂不启用）──
        if False:
            low_stocks = [(s, sc, pf) for s, sc, pf in sorted_results if sc <= 10]
            if low_stocks:
                low_filepath = filepath.with_name(f"stockpool_{formatted_date}_low.txt")
                with open(low_filepath, 'w', encoding='utf-8') as f:
                    f.write(f"# === [可能超跌] 个股 (自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===\n")
                    f.write(f"# 数据源: {filename} | 综合评分≤10\n")
                    f.write(f"# 格式: 股票代码,综合评分,优选分  | 共 {len(low_stocks)} 只\n")
                    f.write(f"# 已按综合评分升序排列（最低的排最前）\n")
                    low_sorted = sorted(low_stocks, key=lambda x: x[1])
                    for symbol, score, pref in low_sorted:
                        code = symbol.split('.')[1] if '.' in symbol else symbol
                        f.write(f"{code},{score:.0f},{pref}\n")
                logger.info(f"[LOW] 已保存 {len(low_stocks)} 只 [可能超跌] 个股到 stockpool_{formatted_date}_low.txt")
            else:
                logger.warning(f"[LOW] {date_str}: 无触发 [可能超跌] 的个股（综合评分≤10）")
    
    def batch_process(self, start_date: str, end_date: str, backup: bool = False):
        """
        批量处理日期范围内的所有 _my.txt 股票池
        
        Args:
            start_date: 开始日期 (格式: YYYY-MM-DD)
            end_date: 结束日期 (格式: YYYY-MM-DD)
            backup: 是否创建备份文件
        """
        current = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        processed_count = 0
        total_stocks = 0
        scored_count = 0
        total_days = (end - current).days + 1
        
        while current <= end:
            date_str = current.strftime('%Y-%m-%d')
            
            # 1. 加载股票池
            stocks = self.load_stock_pool(date_str)
            if not stocks:
                current += timedelta(days=1)
                continue
            
            # 2. 批量评分
            scored_results = []
            day_start_time = time.time()
            stock_index = 0
            
            for symbol in stocks:
                stock_index += 1
                result = self.analyze_stock(symbol, date_str)
                if result is not None:
                    score, pref_score = result
                    scored_results.append((symbol, score, pref_score))
                    scored_count += 1
                    
                    # 写入个股评分记录
                    code = symbol.split('.')[1] if '.' in symbol else symbol
                    score_file = Path(__file__).parent.parent / "data" / "score" / f"{code}.txt"
                    score_file.parent.mkdir(parents=True, exist_ok=True)
                    already_exists = (score_file.exists() and 
                        any(line.startswith(date_str) for line in score_file.read_text(encoding='utf-8').splitlines()))
                    if not already_exists:
                        with open(score_file, 'a', encoding='utf-8') as f:
                            f.write(f"{date_str},{score},{pref_score}\n")
                
                time.sleep(0.1)
                
                if stock_index % 10 == 0 or stock_index == len(stocks):
                    elapsed = time.time() - day_start_time
                    progress_pct = (stock_index / len(stocks)) * 100
                    print(f"\r[{processed_count+1}/{total_days}] {date_str} | "
                          f"股票 {stock_index}/{len(stocks)} ({progress_pct:.0f}%) | "
                          f"已耗时: {elapsed:.0f}秒", end='', flush=True)
            
            total_stocks += len(stocks)
            
            # 3. 保存全部结果
            if scored_results:
                self.append_scores_to_file(date_str, scored_results, backup=backup)
                processed_count += 1
            
            print(f"\n[{processed_count}/{total_days}] {date_str} ({len(stocks)}只股票) - 完成")
            
            current += timedelta(days=1)
        
        print(f"\n[SUCCESS] 批量评分完成！处理了 {processed_count} 个交易日，共 {total_stocks} 只股票，成功评分 {scored_count} 只")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="股票池批量评分工具（针对 _my.txt 自定义股票池）")
    parser.add_argument('--date', type=str, help='指定日期 (格式: YYYY-MM-DD)')
    parser.add_argument('--start-date', type=str, help='开始日期 (格式: YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='结束日期 (格式: YYYY-MM-DD)')
    parser.add_argument('--tdx-dir', type=str, help='通达信安装目录（可选）')
    parser.add_argument('--backup', action='store_true', help='是否创建备份文件（默认不创建）')
    
    args = parser.parse_args()
    
    if args.date:
        if args.start_date or args.end_date:
            print("错误: 不能同时指定 --date 和 --start-date/--end-date")
            return
        start_date = args.date
        end_date = args.date
    elif args.start_date and args.end_date:
        start_date = args.start_date
        end_date = args.end_date
    else:
        print("错误: 请指定 --date 或 --start-date 和 --end-date")
        return
    
    scorer = HistoricalStockScorer(tdx_dir=args.tdx_dir)
    scorer.batch_process(start_date, end_date, backup=args.backup)


if __name__ == "__main__":
    main()
