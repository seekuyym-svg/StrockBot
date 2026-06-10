# -*- coding: utf-8 -*-
"""
查看评分后的股票池结果

功能：
1. 读取评分后的股票池文件
2. 显示Top N股票的代码、名称、评分和评级
3. 批量获取股票基本信息

使用方法:
    python backtest/view_scored_results.py --date 2026-04-13
    python backtest/view_scored_results.py --date 2026-04-13 --top 5
"""

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def load_scored_stockpool(date_str: str) -> list:
    """
    加载评分后的股票池文件
    
    Args:
        date_str: 日期字符串 (YYYY-MM-DD 或 YYYYMMDD)
    
    Returns:
        list: [(股票代码, 评分), ...]
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
    
    scored_stocks = []
    in_score_section = False
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            
            # 检测评分数据区域
            if line.startswith('# === 技术评分数据'):
                in_score_section = True
                continue
            
            # 跳过注释行和空行
            if not line or line.startswith('#') or line.startswith('-'):
                continue
            
            # 解析评分数据
            if in_score_section and ',' in line:
                parts = line.split(',')
                if len(parts) == 2:
                    code = parts[0].strip()
                    try:
                        score = float(parts[1].strip())
                        scored_stocks.append((code, score))
                    except ValueError:
                        continue
    
    print(f"[OK] 加载 {filename}，共 {len(scored_stocks)} 只评分股票")
    return scored_stocks


def get_stock_info_batch(scored_stocks: list, top_n: int = None) -> pd.DataFrame:
    """
    批量获取股票基本信息
    
    Args:
        scored_stocks: [(股票代码, 评分), ...]
        top_n: 只显示前N只（用于快速预览）
    
    Returns:
        DataFrame: 包含代码、名称、行业、评分、评级等信息
    """
    try:
        import akshare as ak
        
        # 如果指定了top_n，只处理前N只
        if top_n:
            display_stocks = scored_stocks[:top_n]
            print(f"[INFO] 仅显示前 {top_n} 只股票（共 {len(scored_stocks)} 只）\n")
        else:
            display_stocks = scored_stocks
            print(f"[INFO] 显示全部 {len(scored_stocks)} 只股票\n")
        
        results = []
        for idx, (code, score) in enumerate(display_stocks, 1):
            try:
                # 获取股票基本信息
                df = ak.stock_individual_info_em(symbol=code)
                
                if df is not None and not df.empty:
                    name = df[df['item'] == '股票简称']['value'].values[0] if len(df[df['item'] == '股票简称']) > 0 else code
                    industry = df[df['item'] == '行业']['value'].values[0] if len(df[df['item'] == '行业']) > 0 else '未知'
                else:
                    name = '获取失败'
                    industry = '未知'
                
                # 计算评级
                if score >= 80:
                    rating = "⭐⭐⭐⭐⭐ 优秀"
                elif score >= 60:
                    rating = "⭐⭐⭐⭐ 良好"
                elif score >= 40:
                    rating = "⭐⭐⭐ 中等"
                elif score >= 20:
                    rating = "⭐⭐ 较差"
                else:
                    rating = "⭐ 很差"
                
                results.append({
                    '序号': idx,
                    '代码': code,
                    '名称': name,
                    '行业': industry,
                    '评分': score,
                    '评级': rating
                })
                
                # 进度提示
                if idx % 10 == 0:
                    print(f"[PROGRESS] 已处理 {idx}/{len(display_stocks)} 只股票...")
                
            except Exception as e:
                results.append({
                    '序号': idx,
                    '代码': code,
                    '名称': f'错误',
                    '行业': '未知',
                    '评分': score,
                    '评级': '获取失败'
                })
        
        return pd.DataFrame(results)
        
    except ImportError:
        print("[ERROR] 需要安装 akshare: pip install akshare")
        return pd.DataFrame()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="查看评分后的股票池结果")
    parser.add_argument('--date', type=str, required=True, help='日期 (YYYY-MM-DD 或 YYYYMMDD)')
    parser.add_argument('--top', type=int, default=None, help='只显示前N只股票（用于快速预览）')
    
    args = parser.parse_args()
    
    print("=" * 100)
    print(f"[INFO] 评分结果查看工具")
    print(f"[INFO] 日期: {args.date}")
    print("=" * 100)
    
    # 1. 加载评分后的股票池
    scored_stocks = load_scored_stockpool(args.date)
    
    if not scored_stocks:
        print("[WARN] 未找到评分数据")
        return
    
    # 2. 获取股票信息
    print("\n[STEP 2] 正在获取股票基本信息...\n")
    df = get_stock_info_batch(scored_stocks, top_n=args.top)
    
    if df.empty:
        print("[ERROR] 无法获取股票信息")
        return
    
    # 3. 显示结果
    print("\n" + "=" * 100)
    print("评分结果详情（按评分降序排列）")
    print("=" * 100)
    
    # 设置pandas显示选项
    pd.set_option('display.max_rows', None)
    pd.set_option('display.width', None)
    pd.set_option('display.unicode.ambiguous_as_wide', True)
    pd.set_option('display.unicode.east_asian_width', True)
    
    print(df.to_string(index=False))
    
    # 4. 统计信息
    print("\n" + "=" * 100)
    print("统计摘要")
    print("=" * 100)
    print(f"最高评分: {df['评分'].max():.1f} 分 ({df.loc[df['评分'].idxmax(), '名称']})")
    print(f"最低评分: {df['评分'].min():.1f} 分 ({df.loc[df['评分'].idxmin(), '名称']})")
    print(f"平均评分: {df['评分'].mean():.1f} 分")
    print(f"中位数:   {df['评分'].median():.1f} 分")
    
    # 评级分布
    rating_counts = df['评级'].value_counts()
    print(f"\n评级分布:")
    for rating, count in rating_counts.items():
        print(f"  {rating}: {count} 只")
    
    print("=" * 100)


if __name__ == "__main__":
    main()
