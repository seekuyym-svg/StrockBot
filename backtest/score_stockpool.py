# -*- coding: utf-8 -*-
"""
股票池批量评分工具

功能：
1. 批量读取指定日期范围内的股票池文件 (stockpool_YYYYMMDD.txt)
2. 对股票池中的股票进行技术分析评分
3. 将评分结果追加到原股票池文件中
4. 保留原文件备份以防数据丢失

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
    from local.calc_bb import StockTrendAnalyzer
except ImportError:
    print("错误: 无法导入 calc_bb 模块，请确保 local/calc_bb.py 存在")
    raise


class StockPoolScorer:
    """股票池批量评分器"""
    
    def __init__(self):
        """初始化评分器"""
        self.analyzer = StockTrendAnalyzer()
        self.data_dir = Path(__file__).parent.parent / "data"
    
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
        filepath = self.data_dir / filename
        
        if not filepath.exists():
            return []
        
        stocks = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # 跳过注释行和空行
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
    
    def analyze_stock(self, symbol: str, analysis_date: str) -> Optional[float]:
        """
        分析单只股票并返回评分
        
        Args:
            symbol: 股票代码 (格式: sh.600519 或 sz.000858)
            analysis_date: 分析日期 (格式: YYYY-MM-DD)
            
        Returns:
            综合评分 (float)，如果分析失败返回 None
        """
        try:
            # 临时禁用所有日志输出
            logger.disable("local.calc_bb")
            
            # 调用 calc_bb 中的分析器
            result = self.analyzer.analyze_stock(symbol, name='')
            
            # 恢复日志
            logger.enable("local.calc_bb")
            
            if result:
                return result.get('score', 0.0)
            else:
                return None
                
        except Exception as e:
            logger.enable("local.calc_bb")
            return None
    
    def append_scores_to_file(self, date_str: str, scored_results: List[Tuple[str, float]]):
        """
        将评分结果追加到股票池文件
        
        Args:
            date_str: 日期字符串 (格式: YYYY-MM-DD)
            scored_results: 评分结果列表 [(股票代码, 评分), ...]
        """
        # 转换日期格式为 YYYYMMDD
        formatted_date = date_str.replace("-", "")
        filename = f"stockpool_{formatted_date}.txt"
        filepath = self.data_dir / filename
        
        if not filepath.exists():
            return
        
        # 创建备份文件
        backup_path = filepath.with_suffix('.txt.bak')
        if not backup_path.exists():
            shutil.copy(filepath, backup_path)
        
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
    
    def batch_process(self, start_date: str, end_date: str):
        """
        批量处理日期范围内的所有股票池
        
        Args:
            start_date: 开始日期 (格式: YYYY-MM-DD)
            end_date: 结束日期 (格式: YYYY-MM-DD)
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
                time.sleep(0.3)
            
            total_stocks += len(stocks)
            
            # 3. 保存结果
            if scored_results:
                self.append_scores_to_file(date_str, scored_results)
                processed_count += 1
            
            # 4. 打印进度（每处理完一个文件）
            formatted_date = date_str.replace("-", "")
            print(f"[{processed_count}/{total_days}] {date_str} ({len(stocks)}只股票) - 完成")
            
            current += timedelta(days=1)
        
        # 打印最终汇总
        print(f"\n✅ 批量评分完成！处理了 {processed_count} 个交易日，共 {total_stocks} 只股票，成功评分 {scored_count} 只")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="股票池批量评分工具")
    parser.add_argument('--date', type=str, help='指定日期 (格式: YYYY-MM-DD)')
    parser.add_argument('--start-date', type=str, help='开始日期 (格式: YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='结束日期 (格式: YYYY-MM-DD)')
    
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
    scorer = StockPoolScorer()
    
    # 执行批量评分
    scorer.batch_process(start_date, end_date)


if __name__ == "__main__":
    main()