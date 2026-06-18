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
    python backtest/score_stockpool.py --date 2026-05-06 --min-score 70 --max-score 85
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
        logger.info(f"✅ 已初始化 mootdx Reader (通达信目录: {tdx_dir})")
    
    def _get_historical_klines(self, stock_code: str, analysis_date: str, days: int = 300) -> pd.DataFrame:
        """
        获取指定日期之前的历史K线数据
        
        Args:
            stock_code: 股票代码（6位数字，不含市场前缀）
            analysis_date: 分析日期 (格式: YYYY-MM-DD)
            days: 需要获取的K线数量
            
        Returns:
            DataFrame 包含日期索引和 OHLCV 数据，仅包含 analysis_date 及之前的数据
        """
        try:
            df = self.reader.daily(symbol=stock_code)
            
            if df is None or df.empty:
                return pd.DataFrame()
            
            # 转换索引为 datetime
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            
            # 关键：截断到 analysis_date 及之前的数据
            analysis_dt = pd.to_datetime(analysis_date)
            df_filtered = df[df.index <= analysis_dt]
            
            if len(df_filtered) < 60:
                logger.debug(f"⚠️ {stock_code} 在 {analysis_date} 之前数据不足 ({len(df_filtered)}条)")
                return pd.DataFrame()
            
            return df_filtered
            
        except Exception as e:
            logger.debug(f"❌ 获取 {stock_code} K线数据失败: {e}")
            return pd.DataFrame()
    
    def _calculate_ma(self, df: pd.DataFrame, periods: List[int] = [5, 10, 20, 60]) -> pd.DataFrame:
        """计算移动平均线"""
        for p in periods:
            df[f'MA{p}'] = df['close'].rolling(window=p).mean()
        return df
    
    def _check_trend_alignment(self, df: pd.DataFrame) -> Tuple[str, str]:
        """
        判断均线排列状态
        
        Returns:
            (trend_type, message): 趋势类型和描述
        """
        latest = df.iloc[-1]
        
        # 检查数据完整性
        if pd.isna(latest.get('MA5')) or pd.isna(latest.get('MA10')) or pd.isna(latest.get('MA20')):
            return 'neutral', "数据不足，无法判断均线排列"
        
        ma5 = latest['MA5']
        ma10 = latest['MA10']
        ma20 = latest['MA20']
        
        # 多头排列: MA5 > MA10 > MA20
        if ma5 > ma10 > ma20:
            ratio = ma5 / ma20 if ma20 > 0 else 1
            if ratio > 1.01:
                return 'bullish', f"均线多头排列 (MA5>MA10>MA20)"
            else:
                return 'neutral', f"均线粘合略偏多 (差距<1%)"
        
        # 空头排列: MA5 < MA10 < MA20
        if ma5 < ma10 < ma20:
            ratio = ma20 / ma5 if ma5 > 0 else 1
            if ratio > 1.01:
                return 'bearish', f"均线空头排列 (MA5<MA10<MA20)"
            else:
                return 'neutral', f"均线粘合略偏空 (差距<1%)"
        
        return 'neutral', "均线相互缠绕，无明显趋势"
    
    def _compute_macd(self, df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[float, float, float]:
        """计算MACD指标"""
        ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=signal, adjust=False).mean()
        macd_bar = (dif - dea) * 2
        return dif.iloc[-1], dea.iloc[-1], macd_bar.iloc[-1]
    
    def _compute_rsi(self, df: pd.DataFrame, period: int = 14) -> float:
        """计算RSI指标"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]
    
    def _compute_bollinger(self, df: pd.DataFrame, period: int = 20, std_dev: int = 2) -> Tuple[int, float, float]:
        """
        计算布林带位置
        
        Returns:
            (position, upper, lower): 位置标识(1=突破上轨, 0=中轨附近, -1=跌破下轨)、上轨、下轨
        """
        ma = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()
        upper = ma + std_dev * std
        lower = ma - std_dev * std
        latest_close = df['close'].iloc[-1]
        
        if latest_close > upper.iloc[-1]:
            position = 1
        elif latest_close < lower.iloc[-1]:
            position = -1
        else:
            position = 0
        
        return position, upper.iloc[-1], lower.iloc[-1]
    
    def analyze_stock(self, symbol: str, analysis_date: str) -> Optional[float]:
        """
        分析单只股票并返回评分（基于指定历史日期）
        
        Args:
            symbol: 股票代码 (格式: sh.600519 或 sz.000858)
            analysis_date: 分析日期 (格式: YYYY-MM-DD)
            
        Returns:
            综合评分 (float)，如果分析失败返回 None（新版：0-100分制）
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
            
            return score
                
        except Exception as e:
            logger.debug(f"❌ 分析 {symbol} 失败: {e}")
            return None
    
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
                                              min_count: int) -> List[Tuple[str, float]]:
        """
        按行业分散选股：优先取高评分，但每个行业不超过上限
        
        Args:
            sorted_results: 已按评分降序排序的列表
            max_count: 最多保留的股票数量
            max_per_industry: 每个行业最多选几只
            min_count: 最少保留的股票数量（保底）
        
        Returns:
            行业分散后的股票列表
        """
        selected = []
        industry_count = {}
        skipped_industry = []  # 因行业超限被跳过的优质股
        
        # 第一轮：按行业限制选股
        for symbol, score in sorted_results:
            industry = self._get_industry(symbol)
            
            if industry and industry_count.get(industry, 0) >= max_per_industry:
                # 行业已满，先记下来，后面可能补选
                skipped_industry.append((symbol, score))
                continue
            
            selected.append((symbol, score))
            if industry:
                industry_count[industry] = industry_count.get(industry, 0) + 1
            
            if len(selected) >= max_count:
                return selected[:max_count]
        
        # 第二轮：不够 max_count 的话，放宽行业限制补选
        if len(selected) < min_count:
            logger.warning(f"[WARN] 行业限制导致选股不足 {min_count} 只（当前 {len(selected)} 只），放宽行业限制补选")
            for symbol, score in skipped_industry:
                if len(selected) >= max_count:
                    break
                selected.append((symbol, score))
        
        return selected[:max_count]
    
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
    
    def append_scores_to_file(self, date_str: str, scored_results: List[Tuple[str, float]], 
                             backup: bool = False, min_score: float = 60.0, max_score: float = 100.0, 
                             max_count: int = 10, max_per_industry: int = 3, min_count: int = 3):
        """
        将评分结果追加到股票池文件，并应用评分筛选和数量限制
        
        Args:
            date_str: 日期字符串 (格式: YYYY-MM-DD)
            scored_results: 评分结果列表 [(股票代码, 评分), ...]
            backup: 是否创建备份文件（默认False）
            min_score: 最低评分阈值（默认60）
            max_score: 最高评分阈值（默认100）
            max_count: 最多保留的股票数量（默认10）
            max_per_industry: 每个行业最多选几只（默认3，用于行业分散）
            min_count: 最少保留的股票数量（默认3，保底）
        """
        # 转换日期格式为 YYYYMMDD
        formatted_date = date_str.replace("-", "")
        filename = f"stockpool_{formatted_date}.txt"
        filepath = Path(__file__).parent.parent / "data" / filename
        
        if not filepath.exists():
            return
        
        # === 第一步：按评分区间筛选 ===
        filtered_results = [
            (symbol, score) for symbol, score in scored_results 
            if min_score <= score <= max_score
        ]
        
        original_count = len(scored_results)
        after_filter_count = len(filtered_results)
        
        logger.info(f"[FILTER] {date_str}: 原始 {original_count} 只 -> 评分[{min_score}-{max_score}] 筛选后 {after_filter_count} 只")
        
        if not filtered_results:
            logger.warning(f"[WARN] {date_str}: 无股票满足评分要求（[{min_score}-{max_score}]），跳过保存")
            return
        
        # === 第二步：按评分降序排序，再按行业分散取Top N ===
        sorted_results = sorted(filtered_results, key=lambda x: x[1], reverse=True)
        top_results = self._select_with_industry_diversification(
            sorted_results, max_count, max_per_industry, min_count
        )
        
        final_count = len(top_results)
        logger.info(f"[TOP] {date_str}: 保留 {final_count} 只股票（行业上限: {max_per_industry}/行业，评分排序）")
        
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
            f.write(f"# 原始数量: {original_count}, 筛选后: {after_filter_count}, 最终保留: {final_count}\n")
            
            # 写入评分数据（不带市场前缀，保持与原文件格式一致）
            for symbol, score in top_results:
                # 移除市场前缀以保持与原文件格式一致
                code_without_prefix = symbol.split('.')[1] if '.' in symbol else symbol
                f.write(f"{code_without_prefix},{score:.1f}\n")
    
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
            
            logger.info(f"[CONFIG] 评分区间: [{min_score}-{max_score}], 最大选股数: {max_stocks}, 行业上限: {max_per_industry}")
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
                score = self.analyze_stock(symbol, date_str)
                if score is not None:
                    scored_results.append((symbol, score))
                    scored_count += 1
                
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
                                          min_count=min_stocks_per_cycle)
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