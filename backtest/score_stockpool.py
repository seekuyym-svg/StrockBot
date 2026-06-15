# -*- coding: utf-8 -*-
"""
股票池批量评分工具（历史回测版本）

功能：
1. 批量读取指定日期范围内的股票池文件 (stockpool_YYYYMMDD.txt)
2. 对股票池中的股票进行技术分析评分（基于历史指定日期的K线数据）
3. 将评分结果追加到原股票池文件中
4. 保留原文件备份以防数据丢失

核心特性：
- ✅ 完全独立实现，不依赖 local/calc_bb.py
- ✅ 使用 mootdx Reader 直接读取本地通达信数据
- ✅ 技术指标计算严格基于指定的历史日期（而非当前最新日期）

使用方法：
    # 基础用法（从配置文件读取评分参数）
    python backtest/score_stockpool.py --date 2026-05-06
    python backtest/score_stockpool.py --start-date 2024-01-01 --end-date 2024-01-10
    
    # 自定义评分区间（命令行参数优先级高于配置文件）
    python backtest/score_stockpool.py --date 2026-05-06 --min-score 0 --max-score 100
    python backtest/score_stockpool.py --start-date 2024-01-01 --end-date 2024-01-10 --min-score 65 --max-stocks 15
    
    # 创建备份文件
    python backtest/score_stockpool.py --date 2026-05-06 --backup
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
    """历史股票评分器（独立实现）"""
    
    def __init__(self, tdx_dir: str = None):
        """
        初始化评分器
        
        Args:
            tdx_dir: 通达信安装目录，默认从环境变量或配置读取
        """
        # 初始化 mootdx Reader
        if tdx_dir is None:
            # 尝试从 config.yaml 读取，或使用默认路径
            try:
                from src.utils.config import get_config
                config = get_config()
                # Pydantic模型使用属性访问，而非 .get() 方法
                tdx_dir = getattr(config, 'tdx_dir', 'D:\\Install\\zd_zxzq_gm')
            except Exception as e:
                logger.debug(f"⚠️ 读取配置失败: {e}，使用默认通达信目录")
                tdx_dir = 'D:\\Install\\zd_zxzq_gm'
        
        self.reader = Reader.factory(market='std', tdxdir=tdx_dir)
        self.industry_cache = {}           # 行业信息缓存: symbol -> industry_name
        self.industry_cache_file = Path(__file__).parent.parent / "data" / "industry_cache.json"
        self._load_industry_cache()        # 尝试从本地文件恢复上次的缓存
        self.pref_vol_ratio_threshold = 2.8  # 优选分量比上限
        self.pref_vol_ratio_min = 1.2  # 优选分量比下限
        self.min_pref_score = 0  # 优选分最低门槛（0=仅排序不淘汰）
        self.max_pref_score = 16 # 优选分上限（16以上多为过热股）
        self.dynamic_select_ratio = 0.4  # 动态选股比例
        self.pref_upper_shadow_threshold = 2.5  # 上影线出货信号阈值（平均超过此值扣分）
        self.max_per_score = 3  # 同分值最多保留几只（默认3）
        # 评分趋势缓存
        self._score_trend_cache = {}
        logger.info(f"✅ 已初始化 mootdx Reader (通达信目录: {tdx_dir})")
    
    def _get_historical_klines(self, stock_code: str, analysis_date: str, days: int = 300) -> pd.DataFrame:
        """
        获取指定日期之前的历史K线数据
        统一委托给 local/utils.py 的实现（本地通达信 → 腾讯API降级）
        """
        # 解析市场和代码
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
        
        Args:
            symbol: 股票代码 (格式: sh.600519 或 sz.000858)
            analysis_date: 分析日期 (格式: YYYY-MM-DD)
            
        Returns:
            Tuple[综合评分(0-100), 优选分(0-10)]，失败返回 None
        """
        try:
            # 解析股票代码
            parts = symbol.split('.')
            if len(parts) != 2:
                return None
            
            market = parts[0].lower()
            code = parts[1]
            
            # 使用新版100分评分系统（传入历史日期）
            from local.utils import calculate_trend_score_v2
            score = calculate_trend_score_v2(market, code, days=300, end_date=analysis_date)
            
            # 评分失败则整只股票跳过
            if score is None:
                return None
            
            # 计算优选分（传入当前综合评分，用于评分趋势判断）
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
        
        Args:
            current_score: 当前综合评分（传入后用于评分趋势判断）
        
        Returns:
            优选分(0~25)，仅用于排序（配置min_pref_score=0）
        """
        try:
            df = self._get_historical_klines(f"{market}{code}", analysis_date, days=90)
            if df.empty or len(df) < 30:
                return 0
            
            closes = df['close'].values
            highs = df['high'].values
            latest_close = closes[-1]
            total = 0.0
            
            # === ① 趋势疲劳度（6分）— 连续上涨天数 ===
            consecutive_up = 0
            for i in range(len(df)-1, max(0, len(df)-15), -1):
                if df['close'].iloc[i] > df['open'].iloc[i]:
                    consecutive_up += 1
                else:
                    break
            
            if consecutive_up <= 3:
                total += 6.0      # 刚启动1~3天，空间最大
            elif consecutive_up <= 5:
                total += 4.0      # 上涨4~5天，还在中途
            elif consecutive_up <= 7:
                total += 2.0      # 上涨6~7天，接近尾声
            else:
                total += 0.0      # 连涨>7天，强弩之末
            
            # === ② 前高压力（6分）— 距60日最高价的距离 ===
            lookback = min(60, len(df))
            high_60d = df['high'].iloc[-lookback:].max()
            # 正值=已突破前高，负值=未突破
            distance_to_high = (latest_close - high_60d) / high_60d * 100 if high_60d > 0 else 0
            
            if distance_to_high > 5:
                total += 2.0      # 远超前高5%+，回调风险大
            elif distance_to_high > 0:
                total += 4.0      # 刚突破前高(0~5%)，强势延续
            elif distance_to_high > -5:
                total += 2.0      # 离前高5%以内，空间有限
            elif distance_to_high > -10:
                total += 4.0      # 距前高5~10%，有适中空间
            else:
                total += 6.0      # 距前高>10%，上涨空间巨大
            
            # === ③ 当日强度（4分）— 涨跌幅+量比配合 ===
            prev_close = closes[-2] if len(closes) >= 2 else latest_close
            change_pct = (latest_close - prev_close) / prev_close * 100 if prev_close > 0 else 0
            
            vol_ma20 = df['volume'].iloc[-20:].mean()
            vol_ratio = df['volume'].iloc[-1] / vol_ma20 if vol_ma20 > 0 else 0
            pr_min = self.pref_vol_ratio_min       # 配置量比下限
            pr_mid = (pr_min + self.pref_vol_ratio_threshold) / 2  # 量比中值
            
            if 1 <= change_pct <= 3 and pr_min <= vol_ratio <= pr_mid:
                total += 4.0      # 温和放量上涨，最佳形态
            elif 0 <= change_pct <= 1 and pr_min * 0.7 <= vol_ratio <= pr_mid:
                total += 2.0      # 缩量小涨/平盘，蓄力
            elif -1 <= change_pct <= 0 and pr_min * 0.7 <= vol_ratio <= pr_mid:
                total += 2.0      # 缩量小跌，洗盘
            elif change_pct > 3:
                total += 1.0      # 大涨过热
            elif change_pct < -2:
                total += 0.0      # 大跌
            else:
                total += 1.0      # 其他情况
            
            # 上影线修正（3天平均上影线>阈值，说明连续出货，扣2分）
            upper_shadows = []
            for i in range(3):
                h = df['high'].iloc[-1-i]
                c = df['close'].iloc[-1-i]
                o = df['open'].iloc[-1-i]
                if h > 0:
                    upper_shadows.append((h - max(c, o)) / h * 100)
            if len(upper_shadows) == 3 and sum(upper_shadows)/3 > self.pref_upper_shadow_threshold:
                total -= 2.0
            
            # === ④ 乖离率（4分）— 偏离20日线幅度 ===
            ma20 = df['close'].rolling(20).mean().iloc[-1]
            if pd.notna(ma20) and ma20 > 0:
                deviation = (latest_close - ma20) / ma20 * 100
                if 2 <= deviation <= 4:
                    total += 4.0    # 偏离适中，最佳
                elif 4 < deviation <= 6:
                    total += 2.0    # 偏高，有可能回调
                elif 0 <= deviation < 2:
                    total += 2.0    # 偏离较小，还没启动
                elif deviation > 6:
                    total += 0.0    # 严重偏离，回调风险大
                else:
                    total += 0.0    # 跌破20日线
            
            # === ⑤ 评分趋势（5分）— 对比历史综合评分走势 ===
            # 优先从文件读，不够时自己算
            hist_scores = (self._score_trend_cache.get(code) or [])
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
            
            # 不够时自己算（从已有K线数据中取前两个交易日，用calculate_trend_score_v2补评分）
            if current_score is not None:
                from local.utils import calculate_trend_score_v2 as _calc_s
                trade_dates = df.index[-3:]  # 最后3个交易日
                if len(trade_dates) >= 2 and yesterday_score is None:
                    yesterday_score = _calc_s(market, code, end_date=trade_dates[-2].strftime('%Y-%m-%d'))
                if len(trade_dates) >= 3 and day_before_score is None:
                    day_before_score = _calc_s(market, code, end_date=trade_dates[-3].strftime('%Y-%m-%d'))
                
                if day_before_score is not None and yesterday_score is not None:
                    if day_before_score < yesterday_score < current_score:
                        total += 5.0    # 逐日升高
                    elif yesterday_score < current_score:
                        total += 3.0    # 最后一天扭转
                elif yesterday_score is not None and yesterday_score < current_score:
                    total += 3.0        # 仅两天且向上
            
            return min(total, 25.0)
            
        except Exception:
            return 0
    
    def _load_industry_cache(self):
        """从本地文件加载行业信息缓存"""
        try:
            if self.industry_cache_file.exists():
                import json
                with open(self.industry_cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                # 只加载非空值
                for k, v in cache.items():
                    if v is not None:
                        self.industry_cache[k] = v
                logger.info(f"[CACHE] 从本地文件加载 {len(self.industry_cache)} 条行业信息缓存")
        except Exception as e:
            logger.debug(f"[CACHE] 加载行业缓存文件失败: {e}")
    
    def _save_industry_cache(self):
        """将行业信息缓存保存到本地文件"""
        try:
            import json
            # 只保存有行业信息的条目（None的不保存）
            cache = {k: v for k, v in self.industry_cache.items() if v is not None}
            with open(self.industry_cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
            logger.debug(f"[CACHE] 已保存 {len(cache)} 条行业信息缓存到本地文件")
        except Exception as e:
            logger.debug(f"[CACHE] 保存行业缓存文件失败: {e}")
    
    def _get_industry(self, symbol: str) -> Optional[str]:
        """
        获取股票所属行业（带缓存）
        
        数据源优先级：
        1. 内存缓存 / 本地文件缓存
        2. 东方财富HTTP接口（绕过akshare，更稳定）
        3. akshare（降级方案）
        
        Args:
            symbol: 股票代码 (格式: sh.600519 或 sz.000858)
        
        Returns:
            行业名称，获取失败返回 None
        """
        # 检查内存缓存
        if symbol in self.industry_cache:
            return self.industry_cache[symbol]
        
        industry = None
        code = symbol.split('.')[1] if '.' in symbol else symbol
        
        # === 方案1：直接调用东方财富HTTP接口 ===
        try:
            industry = self._get_industry_via_http(code, symbol)
        except Exception as e:
            logger.debug(f"[INDUSTRY] HTTP接口获取 {symbol} 失败: {e}")
        
        # === 方案2：降级到akshare ===
        if industry is None:
            try:
                industry = self._get_industry_via_akshare(code)
            except Exception as e:
                logger.debug(f"[INDUSTRY] akshare获取 {symbol} 失败: {e}")
        
        # 缓存结果（无论成功与否）
        self.industry_cache[symbol] = industry
        if industry is not None:
            self._save_industry_cache()
        
        return industry
    
    def _get_industry_via_http(self, code: str, full_symbol: str) -> Optional[str]:
        """
        通过东方财富HTTP底层接口获取行业信息
        
        使用东方财富公司概况接口，直接返回中文行业名称（如"专用设备"）
        """
        import time
        import requests as req
        
        # 市场代码：SZ=深交所, SH=上交所
        market_code = 'SZ' if full_symbol.startswith('sz') else 'SH'
        
        url = "http://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/CompanySurveyAjax"
        params = {"code": f"{market_code}{code}"}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'http://quote.eastmoney.com/'
        }
        
        time.sleep(0.3)
        response = req.get(url, params=params, headers=headers, timeout=5)
        data = response.json()
        
        if data.get('jbzl') and data['jbzl'].get('sshy'):
            return str(data['jbzl']['sshy'])
        
        return None
    
    def _get_industry_via_akshare(self, code: str) -> Optional[str]:
        """
        通过akshare获取行业信息（降级方案）
        """
        import time
        
        max_retries = 2
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    time.sleep(1)
                
                import akshare as ak
                info = ak.stock_individual_info_em(symbol=code)
                
                if info is not None and not info.empty:
                    industry_row = info[info['item'] == '行业']
                    if not industry_row.empty:
                        return industry_row['value'].iloc[0]
                break
            except Exception:
                if attempt < max_retries - 1:
                    continue
                raise
        
        return None
    
    def _select_with_industry_diversification(self, sorted_results: List[Tuple[str, float]], 
                                              max_count: int, max_per_industry: int, 
                                              min_count: int, pref_map: dict = None) -> List[Tuple[str, float]]:
        """
        按行业分散选股：行业内部先按(综合评分,优选分)排序取前N只，
        再跨行业合并按评分降序排列取前max_count只。
        
        Args:
            sorted_results: 已按评分降序排序的列表
            max_count: 最多保留的股票数量
            max_per_industry: 每个行业最多选几只
            min_count: 最少保留的股票数量（保底）
            pref_map: 优选分查找表 {symbol: pref_score}，用于行业内部排序
        
        Returns:
            行业分散后的股票列表
        """
        # 1. 按行业分组
        industry_groups = {}   # industry -> [(symbol, score, pref), ...]
        no_industry = []       # 无行业信息的股票（不限行业）
        
        for symbol, score in sorted_results:
            pref = pref_map.get(symbol, 0) if pref_map else 0
            industry = self._get_industry(symbol)
            if industry:
                industry_groups.setdefault(industry, []).append((symbol, score, pref))
            else:
                no_industry.append((symbol, score, pref))
        
        # 2. 每个行业内部按(综合评分,优选分)降序排列，取前max_per_industry只
        candidates = []
        for stocks in industry_groups.values():
            stocks.sort(key=lambda x: (x[1], x[2]), reverse=True)
            candidates.extend(stocks[:max_per_industry])
        
        # 3. 加入无行业信息的股票（不限行业名额）
        candidates.extend(no_industry)
        
        # 4. 跨行业合并后按(综合评分,优选分)降序排列
        candidates.sort(key=lambda x: (x[1], x[2]), reverse=True)
        
        # 5. 取前max_count只
        result = [(s, sc) for s, sc, _ in candidates[:max_count]]
        
        # 6. 不足min_count时放宽行业限制补选
        if len(result) < min_count:
            remaining = candidates[max_count:]
            remaining.sort(key=lambda x: (x[1], x[2]), reverse=True)
            for s, sc, _ in remaining:
                if len(result) >= max_count:
                    break
                result.append((s, sc))
        
        return result[:max_count]
    
    def _select_with_score_distribution(self, 
                                        sorted_results: List[Tuple[str, float]], 
                                        max_candidates: int) -> List[Tuple[str, float]]:
        """
        评分分布控制：直接取最高分的候选，同分值不超过max_per_score只
        
        已经按(综合评分,优选分)排好序了，直接取前max_candidates只。
        同分值超过max_per_score只的，跳过，从后续候选中递补。
        
        Args:
            sorted_results: 已按(综合评分,优选分)降序排序的列表
            max_candidates: 最多保留的候选数量
        
        Returns:
            评分筛选后的股票列表
        """
        if len(sorted_results) <= max_candidates:
            return sorted_results
        
        # 直接取前max_candidates只（保持排序顺序）
        selected = sorted_results[:max_candidates]
        
        # 同分值限制 + 递补
        score_count = {}
        final_selected = []
        for symbol, score in selected:
            int_score = int(score)
            if score_count.get(int_score, 0) >= self.max_per_score:
                continue
            score_count[int_score] = score_count.get(int_score, 0) + 1
            final_selected.append((symbol, score))
        
        # 被同分限制砍掉的名额，从后续候选中递补
        if len(final_selected) < max_candidates:
            for symbol, score in sorted_results[max_candidates:]:
                if len(final_selected) >= max_candidates:
                    break
                int_score = int(score)
                if score_count.get(int_score, 0) >= self.max_per_score:
                    continue
                score_count[int_score] = score_count.get(int_score, 0) + 1
                final_selected.append((symbol, score))
        
        return final_selected
    
    def load_stock_pool(self, date_str: str) -> List[str]:
        """
        加载指定日期的股票池
        
        Args:
            date_str: 日期字符串，格式为 YYYY-MM-DD
            
        Returns:
            股票代码列表（带市场前缀）
        """
        # 转换日期格式为 YYYYMMDD
        formatted_date = date_str.replace("-", "")
        filename = f"stockpool_{formatted_date}.txt"
        filepath = Path(__file__).parent.parent / "data" / filename
        
        if not filepath.exists():
            return []
        
        stocks = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # 跳过注释行、分隔线和空行
                if not line or line.startswith('#') or line.startswith('-'):
                    continue
                
                # 处理已有评分的格式: 股票代码,评分
                if ',' in line:
                    code = line.split(',')[0].strip()
                else:
                    code = line
                
                # 如果代码没有市场前缀，自动添加
                if not code.startswith(('sh.', 'sz.', 'bj.')):
                    # 根据代码首位判断市场
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
                             backup: bool = False, min_score: float = 60.0, max_score: float = 100.0, 
                             max_count: int = 10, max_per_industry: int = 3, min_count: int = 3,
                             max_pref_score: float = 16, dynamic_select_ratio: float = 0.4):
        """
        将评分结果追加到股票池文件，并应用评分筛选和数量限制
        
        Args:
            date_str: 日期字符串 (格式: YYYY-MM-DD)
            scored_results: [(股票代码, 评分, 优选分), ...]
            backup: 是否创建备份文件（默认False）
            min_score: 最低评分阈值（默认60）
            max_score: 最高评分阈值（默认100）
            max_count: 最多保留的股票数量（默认10）
            max_per_industry: 每个行业最多选几只（默认3，用于行业分散）
            min_count: 最少保留的股票数量（默认3，保底）
        """
        formatted_date = date_str.replace("-", "")
        filename = f"stockpool_{formatted_date}.txt"
        filepath = Path(__file__).parent.parent / "data" / filename
        
        if not filepath.exists():
            return
        
        # === 第一步：按评分区间筛选 ===
        filtered_results = [
            (symbol, score, pref) for symbol, score, pref in scored_results 
            if min_score <= score <= max_score 
            and pref >= self.min_pref_score
            and pref <= max_pref_score
        ]
        
        original_count = len(scored_results)
        after_filter_count = len(filtered_results)
        
        # 动态计算实际选股数量
        actual_count = max(3, min(max_count, int(after_filter_count * dynamic_select_ratio)))
        if actual_count != max_count:
            logger.info(f"[DYNAMIC] {date_str}: 候选{after_filter_count}只, 比例{dynamic_select_ratio:.0%}, 动态选{actual_count}只 (原{max_count}只)")
        
        logger.info(f"[FILTER] {date_str}: 原始 {original_count} 只 -> 评分[{min_score}-{max_score}] 优选[{self.min_pref_score}-{max_pref_score}] 筛选后 {after_filter_count} 只, 最终选{actual_count}只")
        
        if not filtered_results:
            logger.warning(f"[WARN] {date_str}: 无股票满足条件，跳过保存")
            return
        
        # === 第二步：正常选出TOP N只 ===
        max_count = actual_count  # 用动态数量替代
        sorted_results = sorted(filtered_results, key=lambda x: (x[1], x[2]), reverse=True)
        sorted_pairs = [(s, sc) for s, sc, _ in sorted_results]
        distributed = self._select_with_score_distribution(sorted_pairs, max_count * 2)
        pref_map = {s: p for s, _, p in scored_results}
        top_results = self._select_with_industry_diversification(
            distributed, max_count, max_per_industry, min_count, pref_map=pref_map
        )
        
        # 不足max_count时，从剩余候选中按综合分补选
        if len(top_results) < max_count:
            remaining = sorted_results[max_count * 2:] if len(sorted_results) > max_count * 2 else []
            for symbol, score in remaining:
                if len(top_results) >= max_count:
                    break
                if not any(s == symbol for s, _ in top_results):
                    top_results.append((symbol, score))
        
        final_count = len(top_results)
        scores_str = ",".join(f"{s:.0f}" for _, s in top_results)
        
        # 根据参数决定是否创建备份文件
        if backup:
            backup_path = filepath.with_suffix('.txt.bak')
            if not backup_path.exists():
                shutil.copy(filepath, backup_path)
                logger.debug(f"💾 已创建备份文件: {backup_path.name}")
        
        # 读取原始文件内容（保留注释和表头）
        original_lines = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                stripped = line.strip()
                # 保留注释行、分隔线和空行
                if stripped.startswith('#') or stripped.startswith('-') or stripped == '':
                    original_lines.append(line.rstrip('\n'))
        
        # 重新写入文件：原始内容 + 新评分数据
        with open(filepath, 'w', encoding='utf-8') as f:
            # 写入原始注释和表头
            for line in original_lines:
                f.write(line + '\n')
            
            # 添加评分数据标识
            f.write(f"\n# === 技术评分数据 (自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===\n")
            f.write(f"# 筛选条件: 评分 [{min_score}-{max_score}], 最多保留 {max_count} 只\n")
            f.write(f"# 格式: 股票代码,评分,优选分\n")
            f.write(f"# 原始数量: {original_count}, 筛选后: {after_filter_count}, 最终保留: {final_count}\n")
            
            # 构建优选分查找表
            pref_map = {s: p for s, _, p in scored_results}
            # 写入评分数据（不带市场前缀，格式: 股票代码,评分,优选分）
            for symbol, score in top_results:
                code_without_prefix = symbol.split('.')[1] if '.' in symbol else symbol
                pref = pref_map.get(symbol, 0)
                f.write(f"{code_without_prefix},{score:.0f},{pref}\n")
    
    def batch_process(self, start_date: str, end_date: str, backup: bool = False, 
                     min_score: float = None, max_score: float = None, max_stocks: int = None):
        """
        批量处理日期范围内的所有股票池
        
        Args:
            start_date: 开始日期 (格式: YYYY-MM-DD)
            end_date: 结束日期 (格式: YYYY-MM-DD)
            backup: 是否创建备份文件（默认False）
            min_score: 最低评分阈值（None则从配置文件读取）
            max_score: 最高评分阈值（None则从配置文件读取）
            max_stocks: 最多保留的股票数量（None则从配置文件读取）
        """
        # 从 config.yaml 读取评分配置（命令行参数优先）
        try:
            import yaml
            # 使用绝对路径，基于当前文件位置定位项目根目录
            config_path = Path(__file__).parent.parent / 'config.yaml'
            
            if not config_path.exists():
                logger.warning(f"[WARN] 配置文件不存在: {config_path}，使用默认值")
                if min_score is None:
                    min_score = 60.0
                if max_score is None:
                    max_score = 100.0
                if max_stocks is None:
                    max_stocks = 10
                return
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            backtest_config = config.get('backtest', {})
            
            # 优先级：命令行参数 > 配置文件 > 默认值
            if min_score is None:
                min_score = backtest_config.get('min_score', 60.0)
            if max_score is None:
                max_score = backtest_config.get('max_score', 100.0)
            if max_stocks is None:
                max_stocks = backtest_config.get('max_stocks_per_cycle', 10)
            
            # 行业分散配置
            max_per_industry = backtest_config.get('max_stocks_per_industry', 3)
            min_stocks_per_cycle = backtest_config.get('min_stocks_per_cycle', 3)
            # 优选分配置
            pref_vol_ratio = backtest_config.get('pref_vol_ratio_threshold', 2.8)
            self.pref_vol_ratio_threshold = pref_vol_ratio
            self.min_pref_score = backtest_config.get('min_pref_score', 7)
            self.pref_vol_ratio_min = backtest_config.get('pref_vol_ratio_min', 1.2)
            self.max_per_score = backtest_config.get('max_per_score', 3)
            self.max_pref_score = backtest_config.get('max_pref_score', 16)
            self.dynamic_select_ratio = backtest_config.get('dynamic_select_ratio', 0.4)
            self.pref_upper_shadow_threshold = backtest_config.get('pref_upper_shadow_threshold', 2.5)
            
            logger.info(f"[CONFIG] 评分区间: [{min_score}-{max_score}], 最大选股数: {max_stocks}, "
                        f"优选分量比: [{self.pref_vol_ratio_min}-{pref_vol_ratio}]x, "
                        f"优选分最低: {self.min_pref_score}")
        except Exception as e:
            logger.warning(f"[WARN] 读取配置文件失败: {e}，使用默认值")
            # 如果配置文件读取失败，使用硬编码默认值
            if min_score is None:
                min_score = 60.0
            if max_score is None:
                max_score = 100.0
            if max_stocks is None:
                max_stocks = 10
            max_per_industry = 3
            min_stocks_per_cycle = 3
            self.pref_vol_ratio_threshold = 2.8
            self.min_pref_score = 0
            self.pref_vol_ratio_min = 1.2
            self.max_per_score = 3
            self.max_pref_score = 16
            self.dynamic_select_ratio = 0.4
            self.pref_upper_shadow_threshold = 2.5
        
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
                    
                    # 写入个股评分文件（去重：同一日期只保留一条）
                    code = symbol.split('.')[1] if '.' in symbol else symbol
                    score_file = Path(__file__).parent.parent / "data" / "score" / f"{code}.txt"
                    score_file.parent.mkdir(parents=True, exist_ok=True)
                    already_exists = (score_file.exists() and 
                        any(line.startswith(date_str) for line in score_file.read_text(encoding='utf-8').splitlines()))
                    if not already_exists:
                        with open(score_file, 'a', encoding='utf-8') as f:
                            f.write(f"{date_str},{score},{pref_score}\n")
                
                # 每10只股票或最后一只时更新进度
                if stock_index % 10 == 0 or stock_index == len(stocks):
                    elapsed = time.time() - day_start_time
                    progress_pct = (stock_index / len(stocks)) * 100
                    print(f"\r[{processed_count+1}/{total_days}] {date_str} | "
                          f"股票 {stock_index}/{len(stocks)} ({progress_pct:.0f}%) | "
                          f"已耗时: {elapsed:.0f}秒", end='', flush=True)
            
            total_stocks += len(stocks)
            
            # 3. 保存结果（应用筛选和限制）
            if scored_results:
                self.append_scores_to_file(date_str, scored_results, backup=backup, 
                                          min_score=min_score, max_score=max_score, 
                                          max_count=max_stocks, max_per_industry=max_per_industry,
                                          min_count=min_stocks_per_cycle,
                                          max_pref_score=self.max_pref_score,
                                          dynamic_select_ratio=self.dynamic_select_ratio)
                processed_count += 1
            
            # 4. 打印完成信息并换行
            formatted_date = date_str.replace("-", "")
            print(f"\n[{processed_count}/{total_days}] {date_str} ({len(stocks)}只股票) - 完成")
            
            current += timedelta(days=1)
        
        # 打印最终汇总（移除emoji以兼容Windows GBK编码）
        print(f"\n[SUCCESS] 批量评分完成！处理了 {processed_count} 个交易日，共 {total_stocks} 只股票，成功评分 {scored_count} 只")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="股票池批量评分工具（历史回测版本）")
    parser.add_argument('--date', type=str, help='指定日期 (格式: YYYY-MM-DD)')
    parser.add_argument('--start-date', type=str, help='开始日期 (格式: YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='结束日期 (格式: YYYY-MM-DD)')
    parser.add_argument('--tdx-dir', type=str, help='通达信安装目录（可选）')
    parser.add_argument('--backup', action='store_true', help='是否创建备份文件（默认不创建）')
    
    # 新增：评分筛选参数（优先级高于配置文件）
    parser.add_argument('--min-score', type=float, default=None, 
                       help='最低评分阈值（100分制，默认从配置文件读取）')
    parser.add_argument('--max-score', type=float, default=None, 
                       help='最高评分阈值（100分制，默认从配置文件读取）')
    parser.add_argument('--max-stocks', type=int, default=None, 
                       help='最多保留的股票数量（默认从配置文件读取）')
    
    args = parser.parse_args()
    
    # 参数验证
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
    
    # 创建评分器
    scorer = HistoricalStockScorer(tdx_dir=args.tdx_dir)
    
    # 执行批量评分（传递命令行参数，None表示使用配置文件值）
    scorer.batch_process(start_date, end_date, backup=args.backup,
                        min_score=args.min_score, max_score=args.max_score, 
                        max_stocks=args.max_stocks)


if __name__ == "__main__":
    main()