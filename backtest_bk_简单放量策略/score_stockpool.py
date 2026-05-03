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
    python backtest/score_stockpool.py --date 2024-01-15
    python backtest/score_stockpool.py --start-date 2024-01-01 --end-date 2024-01-10
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
                tdx_dir = config.get('tdx_dir', 'D:\\Install\\zd_zxzq_gm')
            except:
                tdx_dir = 'D:\\Install\\zd_zxzq_gm'
        
        self.reader = Reader.factory(market='std', tdxdir=tdx_dir)
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
            综合评分 (float)，如果分析失败返回 None
        """
        try:
            # 解析股票代码
            parts = symbol.split('.')
            if len(parts) != 2:
                return None
            
            market = parts[0].lower()
            code = parts[1]
            
            # 获取历史K线数据（截断到 analysis_date）
            df = self._get_historical_klines(code, analysis_date, days=300)
            if df.empty:
                return None
            
            # 计算均线
            df = self._calculate_ma(df)
            
            # 判断趋势
            trend, ma_msg = self._check_trend_alignment(df)
            
            # 计算辅助指标
            dif, dea, macd_bar = self._compute_macd(df)
            rsi_val = self._compute_rsi(df)
            boll_pos, upper, lower = self._compute_bollinger(df)
            
            latest_close = df['close'].iloc[-1]
            latest_vol = df['volume'].iloc[-1]
            vol_ma20 = df['volume'].rolling(20).mean().iloc[-1]
            vol_ratio = latest_vol / vol_ma20 if vol_ma20 > 0 else 1
            
            # 综合评分
            score = 0
            
            # 均线排列评分
            if trend == 'bullish':
                score += 3
            elif trend == 'bearish':
                score -= 3
            
            # MACD评分
            if dif > dea and dif > 0:
                score += 1
            elif dif < dea and dif < 0:
                score -= 1
            
            # RSI评分
            if rsi_val > 60:
                score += 1
            elif rsi_val < 40:
                score -= 1
            
            # 布林带评分
            if boll_pos == 1:
                score += 1
            elif boll_pos == -1:
                score -= 1
            
            # 成交量评分
            prev_close = df['close'].iloc[-2]
            if vol_ratio > 1.2 and latest_close > prev_close:
                score += 0.5
            elif vol_ratio > 1.2 and latest_close < prev_close:
                score -= 0.5
            
            return score
                
        except Exception as e:
            logger.debug(f"❌ 分析 {symbol} 失败: {e}")
            return None
    
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
    
    def append_scores_to_file(self, date_str: str, scored_results: List[Tuple[str, float]], backup: bool = False):
        """
        将评分结果追加到股票池文件
        
        Args:
            date_str: 日期字符串 (格式: YYYY-MM-DD)
            scored_results: 评分结果列表 [(股票代码, 评分), ...]
            backup: 是否创建备份文件（默认False）
        """
        # 转换日期格式为 YYYYMMDD
        formatted_date = date_str.replace("-", "")
        filename = f"stockpool_{formatted_date}.txt"
        filepath = Path(__file__).parent.parent / "data" / filename
        
        if not filepath.exists():
            return
        
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
            
            # 写入评分数据（不带市场前缀，保持与原文件格式一致）
            for symbol, score in scored_results:
                # 移除市场前缀以保持与原文件格式一致
                code_without_prefix = symbol.split('.')[1] if '.' in symbol else symbol
                f.write(f"{code_without_prefix},{score:.1f}\n")
    
    def batch_process(self, start_date: str, end_date: str, backup: bool = False):
        """
        批量处理日期范围内的所有股票池
        
        Args:
            start_date: 开始日期 (格式: YYYY-MM-DD)
            end_date: 结束日期 (格式: YYYY-MM-DD)
            backup: 是否创建备份文件（默认False）
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
            for symbol in stocks:
                score = self.analyze_stock(symbol, date_str)
                if score is not None:
                    scored_results.append((symbol, score))
                    scored_count += 1
                
                # 避免请求过快
                time.sleep(0.1)
            
            total_stocks += len(stocks)
            
            # 3. 保存结果
            if scored_results:
                self.append_scores_to_file(date_str, scored_results, backup=backup)
                processed_count += 1
            
            # 4. 打印进度（每处理完一个文件）
            formatted_date = date_str.replace("-", "")
            print(f"[{processed_count}/{total_days}] {date_str} ({len(stocks)}只股票) - 完成")
            
            current += timedelta(days=1)
        
        # 打印最终汇总
        print(f"\n✅ 批量评分完成！处理了 {processed_count} 个交易日，共 {total_stocks} 只股票，成功评分 {scored_count} 只")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="股票池批量评分工具（历史回测版本）")
    parser.add_argument('--date', type=str, help='指定日期 (格式: YYYY-MM-DD)')
    parser.add_argument('--start-date', type=str, help='开始日期 (格式: YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='结束日期 (格式: YYYY-MM-DD)')
    parser.add_argument('--tdx-dir', type=str, help='通达信安装目录（可选）')
    parser.add_argument('--backup', action='store_true', help='是否创建备份文件（默认不创建）')
    
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
    
    # 执行批量评分
    scorer.batch_process(start_date, end_date, backup=args.backup)


if __name__ == "__main__":
    main()