# -*- coding: utf-8 -*-
"""
选股结果统计分析工具

功能：
1. 统计指定日期范围内的选股数量
2. 计算平均值、最大值、最小值
3. 生成汇总报告

使用方法:
    python backtest/analyze_stockpool.py --start-date 2026-04-13 --end-date 2026-04-24
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

project_root = Path(__file__).parent.parent
data_dir = project_root / "data"


def analyze_stockpools(start_date: str, end_date: str):
    """
    分析指定日期范围内的选股结果
    
    Args:
        start_date: 起始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
    """
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    
    print("=" * 80)
    print("选股结果统计分析")
    print("=" * 80)
    print(f"日期范围: {start_date} 至 {end_date}\n")
    
    results = []
    current = start_dt
    
    while current <= end_dt:
        # 跳过周末
        if current.weekday() >= 5:
            current += timedelta(days=1)
            continue
        
        date_str = current.strftime('%Y%m%d')
        filename = f"stockpool_{date_str}.txt"
        filepath = data_dir / filename
        
        if filepath.exists():
            # 读取文件，统计股票数量
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f 
                        if line.strip() and not line.startswith('#') and not line.startswith('-')]
            
            stock_count = len(lines)
            results.append({
                'date': current.strftime('%Y-%m-%d'),
                'count': stock_count
            })
        
        current += timedelta(days=1)
    
    if not results:
        print("[WARN] 未找到任何股票池文件")
        return
    
    # 显示详细数据
    print(f"{'日期':<15} {'选股数量':>10}")
    print("-" * 30)
    
    counts = []
    for r in results:
        print(f"{r['date']:<15} {r['count']:>10}")
        counts.append(r['count'])
    
    # 统计信息
    print("\n" + "=" * 80)
    print("统计摘要")
    print("=" * 80)
    print(f"交易日数:   {len(results)} 天")
    print(f"总选股数:   {sum(counts)} 只")
    print(f"平均每日:   {sum(counts)/len(counts):.1f} 只")
    print(f"最多单日:   {max(counts)} 只 ({results[counts.index(max(counts))]['date']})")
    print(f"最少单日:   {min(counts)} 只 ({results[counts.index(min(counts))]['date']})")
    print("=" * 80)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="选股结果统计分析工具")
    parser.add_argument('--start-date', type=str, required=True, help='起始日期 (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, required=True, help='结束日期 (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    analyze_stockpools(args.start_date, args.end_date)
