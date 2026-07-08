# -*- coding: utf-8 -*-
"""
股票池行业分布统计工具

功能：
1. 读取 stockpool_YYYYMMDD_all.txt（全部符合条件的股票）
2. 从 industry_cache.json 获取每只股票的所属行业
3. 按行业汇总选中股票数量，从高到低排列
4. 显示各行业占比，辅助判断近期强势行业

使用方法:
    python backtest/stat_industry_distribution.py --date 2026-04-13
    python backtest/stat_industry_distribution.py --date 20260413 --top 10
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from collections import Counter

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

DATA_DIR = project_root / "data"
CACHE_FILE = DATA_DIR / "industry_cache.json"


def load_industry_cache() -> dict:
    """加载行业缓存文件，返回 {symbol_key: industry_name} 映射"""
    if not CACHE_FILE.exists():
        print(f"[WARN] 行业缓存文件不存在: {CACHE_FILE}")
        return {}
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] 加载行业缓存失败: {e}")
        return {}


def load_stock_codes(date_str: str, override_path: str = None) -> list:
    """
    加载股票池文件中的股票代码列表

    默认优先读取 stockpool_YYYYMMDD_all.txt，
    没有则降级到 stockpool_YYYYMMDD.txt。
    也可通过 override_path 指定任意文件（相对于 data/ 目录）。

    Args:
        date_str: 日期字符串 (YYYY-MM-DD 或 YYYYMMDD)
        override_path: 指定文件名（相对于 data/ 目录），
                       传此参数后跳过默认查找逻辑

    Returns:
        6位数字代码列表，如 ['002353', '600718', ...]
    """
    # 标准化日期
    if '-' in date_str:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        formatted = dt.strftime('%Y%m%d')
    else:
        formatted = date_str
        dt = datetime.strptime(date_str, '%Y%m%d')

    # 指定文件模式：直接用 override_path
    if override_path:
        filepath = DATA_DIR / override_path
        if not filepath.exists():
            print(f"[ERROR] 指定文件不存在: {filepath}")
            return []
        print(f"[OK] 加载指定文件: {filepath.name}")
        codes = _parse_codes_from(filepath)
        return codes

    # 默认模式：优先 _all.txt，没有则降级到主文件
    all_path = DATA_DIR / f"stockpool_{formatted}_all.txt"
    main_path = DATA_DIR / f"stockpool_{formatted}.txt"

    if all_path.exists():
        filepath = all_path
        source = "_all.txt"
    elif main_path.exists():
        filepath = main_path
        source = ".txt"
    else:
        print(f"[ERROR] 股票池文件不存在: {all_path} 或 {main_path}")
        return []

    codes = _parse_codes_from(filepath)
    print(f"[OK] 加载 {filepath.name} ({source}), 共 {len(codes)} 只股票")
    return codes


def _parse_codes_from(filepath: Path) -> list:
    """
    解析股票池文件，提取股票代码列表

    优先查找 '# === 技术评分数据' 标记区域，
    在该区域内提取每行首列的6位数字股票代码。
    如果文件中没有该标记（如原始 .bak 备份文件），
    则降级为全文解析。

    支持任意文件格式（.txt / .csv / .bak 等）。

    Args:
        filepath: 文件路径

    Returns:
        6位数字代码列表
    """
    codes = []
    in_score_section = False
    found_section_marker = False

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('# === 技术评分数据'):
                in_score_section = True
                found_section_marker = True
                continue
            if not line or line.startswith('#') or line.startswith('-'):
                continue
            if in_score_section and ',' in line:
                parts = line.split(',')
                code = parts[0].strip()
                if code.isdigit() and len(code) == 6:
                    codes.append(code)

    # 没有评分标记区域（如 .bak 原始备份文件）→ 降级为全文解析
    if not found_section_marker:
        codes = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('-'):
                    continue
                if ',' in line:
                    parts = line.split(',')
                    code = parts[0].strip()
                    if code.isdigit() and len(code) == 6:
                        codes.append(code)

    return codes


def get_industry(code: str, cache: dict) -> str:
    """
    从行业缓存中查询股票所属行业

    Args:
        code: 6位股票代码，如 '002353'
        cache: 行业缓存字典

    Returns:
        行业名称，查不到返回 '未知'
    """
    market_prefix = 'sh' if code.startswith('6') or code.startswith('9') else 'sz'
    key = f"{market_prefix}.{code}"
    return cache.get(key, '未知')


def main():
    import argparse

    parser = argparse.ArgumentParser(description="股票池行业分布统计工具")
    parser.add_argument('--date', type=str, required=True,
                        help='日期 (YYYY-MM-DD 或 YYYYMMDD)')
    parser.add_argument('--top', type=int, default=0,
                        help='仅显示前N个行业，0=显示全部')
    parser.add_argument('--file', type=str, default=None,
                        help='指定文件名（相对于 data/ 目录），如 stockpool_20260413.bak')

    args = parser.parse_args()

    print("=" * 76)
    print("  📊 股票池行业分布统计")
    print(f"  📅 日期: {args.date}")
    print("=" * 76)

    # 1. 加载行业缓存
    cache = load_industry_cache()
    print(f"  [INFO] 行业缓存: {len(cache)} 条")

    # 2. 加载股票代码
    codes = load_stock_codes(args.date, override_path=args.file)
    if not codes:
        print("  [ERROR] 无股票数据，退出")
        return

    # 3. 按行业汇总
    industry_counter = Counter()
    unknown_codes = []

    for code in codes:
        industry = get_industry(code, cache)
        if industry == '未知':
            unknown_codes.append(code)
        industry_counter[industry] += 1

    # 覆盖率统计
    known = len(codes) - len(unknown_codes)
    coverage = known / len(codes) * 100 if codes else 0
    print(f"  [INFO] 行业覆盖率: {known}/{len(codes)} ({coverage:.1f}%)\n")

    # 4. 排序输出（按选中个数降序）
    sorted_industries = industry_counter.most_common(args.top if args.top > 0 else None)

    print(f"  {'排名':<6} {'行业':<18} {'选中个数':>10} {'占比':>8}")
    print("  " + "-" * 76)

    max_count = max(c for _, c in sorted_industries) if sorted_industries else 1
    for rank, (industry, count) in enumerate(sorted_industries, 1):
        pct = count / len(codes) * 100
        bar_len = int(count / max_count * 40)
        bar = '█' * bar_len
        print(f"  {rank:<6} {industry:<18} {count:>10}  {pct:>6.1f}%  {bar}")

    print("  " + "=" * 76)
    print(f"  合计: {len(codes)} 只股票, {len(sorted_industries)} 个行业")

    # 提示未知行业
    if unknown_codes:
        print(f"\n  [WARN] {len(unknown_codes)} 只股票未查到行业:")
        sample = ' '.join(unknown_codes[:10])
        suffix = ' ...' if len(unknown_codes) > 10 else ''
        print(f"         {sample}{suffix}")
        print(f"         建议先运行 score_stockpool.py 补充行业缓存")


if __name__ == "__main__":
    main()
