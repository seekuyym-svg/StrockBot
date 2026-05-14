# -*- coding: utf-8 -*-
"""
选股结果快速查看工具

功能：
1. 读取指定日期的股票池文件
2. 批量获取股票名称和行业信息
3. 以表格形式展示，方便人工审查

使用方法:
    python backtest/view_stockpool.py --date 2026-04-13
    python backtest/view_stockpool.py --date 2026-04-16 --top 20
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import pandas as pd

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def load_stockpool(date_str: str) -> list:
    """
    加载指定日期的股票池文件
    
    Args:
        date_str: 日期字符串 (YYYY-MM-DD 或 YYYYMMDD)
    
    Returns:
        list: 股票代码列表
    """
    # 标准化日期格式
    if '-' in date_str:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        filename = f"stockpool_{dt.strftime('%Y%m%d')}.txt"
    else:
        filename = f"stockpool_{date_str}.txt"
    
    filepath = project_root / "data" / filename
    
    if not filepath.exists():
        print(f"[ERROR] 文件不存在: {filepath}")
        return []
    
    stock_codes = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # 跳过注释行和空行
            if line and not line.startswith('#') and not line.startswith('-'):
                stock_codes.append(line)
    
    print(f"[OK] 加载 {filename}，共 {len(stock_codes)} 只股票")
    return stock_codes


def get_stock_info_batch(stock_codes: list, top_n: int = None) -> pd.DataFrame:
    """
    批量获取股票基本信息
    
    Args:
        stock_codes: 股票代码列表
        top_n: 只显示前N只（用于快速预览）
    
    Returns:
        DataFrame: 包含代码、名称、行业等信息
    """
    try:
        import akshare as ak
        
        # 如果指定了top_n，只处理前N只
        if top_n:
            display_codes = stock_codes[:top_n]
            print(f"[INFO] 仅显示前 {top_n} 只股票（共 {len(stock_codes)} 只）\n")
        else:
            display_codes = stock_codes
            print(f"[INFO] 显示全部 {len(stock_codes)} 只股票\n")
        
        results = []
        for idx, code in enumerate(display_codes, 1):
            try:
                # 获取股票基本信息
                df = ak.stock_individual_info_em(symbol=code)
                
                if df is not None and not df.empty:
                    name = df[df['item'] == '股票简称']['value'].values[0] if len(df[df['item'] == '股票简称']) > 0 else code
                    industry = df[df['item'] == '行业']['value'].values[0] if len(df[df['item'] == '行业']) > 0 else '未知'
                    
                    results.append({
                        '序号': idx,
                        '代码': code,
                        '名称': name,
                        '行业': industry
                    })
                else:
                    results.append({
                        '序号': idx,
                        '代码': code,
                        '名称': '获取失败',
                        '行业': '未知'
                    })
                
                # 进度提示
                if idx % 10 == 0:
                    print(f"[PROGRESS] 已处理 {idx}/{len(display_codes)} 只股票...")
                
            except Exception as e:
                results.append({
                    '序号': idx,
                    '代码': code,
                    '名称': f'错误: {str(e)[:20]}',
                    '行业': '未知'
                })
        
        return pd.DataFrame(results)
        
    except ImportError:
        print("[ERROR] 需要安装 akshare: pip install akshare")
        return pd.DataFrame()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="选股结果快速查看工具")
    parser.add_argument('--date', type=str, required=True, help='日期 (YYYY-MM-DD 或 YYYYMMDD)')
    parser.add_argument('--top', type=int, default=None, help='只显示前N只股票（用于快速预览）')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print(f"[INFO] 选股结果查看工具")
    print(f"[INFO] 日期: {args.date}")
    print("=" * 80)
    
    # 1. 加载股票池
    stock_codes = load_stockpool(args.date)
    
    if not stock_codes:
        print("[WARN] 股票池为空")
        return
    
    # 2. 获取股票信息
    print("\n[STEP 2] 正在获取股票基本信息...\n")
    df = get_stock_info_batch(stock_codes, top_n=args.top)
    
    if df.empty:
        print("[ERROR] 无法获取股票信息")
        return
    
    # 3. 显示结果
    print("\n" + "=" * 80)
    print("选股结果详情")
    print("=" * 80)
    
    # 设置pandas显示选项
    pd.set_option('display.max_rows', None)
    pd.set_option('display.width', None)
    pd.set_option('display.unicode.ambiguous_as_wide', True)
    pd.set_option('display.unicode.east_asian_width', True)
    
    print(df.to_string(index=False))
    
    print("\n" + "=" * 80)
    print(f"[DONE] 共显示 {len(df)} 只股票")
    print("=" * 80)


if __name__ == "__main__":
    main()
