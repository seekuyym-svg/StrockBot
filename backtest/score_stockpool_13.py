# -*- coding: utf-8 -*-
"""
股票池13精选工具

功能：
1. 读取 _all.txt（当日全部评分结果）
2. 优先选优选分13分的股票
3. 不足5只时从其他分中按综合评分补足至5只
4. 输出 stockpool_YYYYMMDD.txt（直接作为选股池）

使用方法：
    python backtest/score_stockpool_913.py --date 2026-07-14
    python backtest/score_stockpool_913.py --start-date 2026-07-01 --end-date 2026-07-15
"""

import argparse
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

DATA_DIR = Path(__file__).parent.parent / "data"

PREF_PRIORITY = [{13}, {9, 12}, {10, 11, 14}]

def sort_key(pref: float, score: int) -> tuple:
    p = int(pref)
    for i, group in enumerate(PREF_PRIORITY):
        if p in group:
            return (i, -score)
    return (999, -score)


def process_date(date_str: str):
    """处理单个日期"""
    dc = date_str.replace('-', '')
    src = DATA_DIR / f"stockpool_{dc}_all.txt"
    
    if not src.exists():
        print(f"  ❌ {date_str}: 文件不存在 {src.name}")
        return None
    
    records = []
    in_score = False
    with open(src, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('# === 技术评分数据'):
                in_score = True
                continue
            if not in_score or not line or line.startswith('#'):
                continue
            parts = line.split(',')
            if len(parts) >= 3:
                try:
                    records.append({
                        'code': parts[0].strip(),
                        'score': int(parts[1]),
                        'pref': float(parts[2]),
                    })
                except:
                    pass
    
    # 第一步：优先选优选分13分
    filtered = [r for r in records if int(r['pref']) == 13]
    filtered.sort(key=lambda r: sort_key(r['pref'], r['score']))
    
    # 第二步：不足5只时从其他分补足（按综合评分降序）
    if len(filtered) < 5:
        others = [r for r in records if r['code'] not in {c['code'] for c in filtered}]
        others.sort(key=lambda r: -r['score'])
        needed = 5 - len(filtered)
        filtered.extend(others[:needed])
    
    # 输出结果
    print(f"\n  📅 {date_str}  —  原始{len(records)}只 → 13精选{len(filtered)}只")
    
    if not filtered:
        print(f"     没有符合条件的股票（优选分全部≤8）")
        return None
    
    # 统计各分数段
    pref_dist = defaultdict(int)
    for r in filtered:
        pref_dist[int(r['pref'])] += 1
    dist_str = ', '.join(f'{k}分×{v}' for k, v in sorted(pref_dist.items()))
    print(f"     优选分分布: {dist_str}")
    print(f"     综合评分范围: {min(r['score'] for r in filtered)}~{max(r['score'] for r in filtered)}分")
    
    # 写入文件
    out_path = DATA_DIR / f"stockpool_{dc}.txt"
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(f"# 优选分过滤结果 (生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n")
        f.write(f"# 筛选规则: 优先13分, 不足5只从其他分补至5只, 同组按综合评分降序\n")
        f.write(f"# 格式: 股票代码,综合评分,优选分\n")
        f.write("# === 精选数据 ===\n")
        for r in filtered:
            f.write(f"{r['code']},{r['score']},{r['pref']:.0f}\n")
    
    print(f"     ✅ 已保存: {out_path.name}")
    return filtered


def main():
    parser = argparse.ArgumentParser(description='股票池优选分过滤工具')
    parser.add_argument('--date', type=str, help='处理日期 (YYYY-MM-DD)')
    parser.add_argument('--start-date', type=str, help='起始日期')
    parser.add_argument('--end-date', type=str, help='结束日期')
    
    args = parser.parse_args()
    
    if args.date:
        dates = [args.date]
    elif args.start_date and args.end_date:
        start = datetime.strptime(args.start_date, '%Y-%m-%d')
        end = datetime.strptime(args.end_date, '%Y-%m-%d')
        dates = []
        cur = start
        while cur <= end:
            if cur.weekday() < 5:
                dates.append(cur.strftime('%Y-%m-%d'))
            cur += timedelta(days=1)
    else:
        dates = [datetime.now().strftime('%Y-%m-%d')]
    
    for dt in dates:
        process_date(dt)


if __name__ == "__main__":
    main()
