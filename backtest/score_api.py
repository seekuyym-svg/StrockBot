# -*- coding: utf-8 -*-
"""
股票评分 API 桥（JSON-in/JSON-out，供 DSH 插件等外部程序调用）

功能：
1. 对单个或多个股票代码计算 综合评分(0-100) + 优选分(0-25)
2. 同时输出股票名称和所属行业
3. 纯查询模式：不做任何文件写入（不写 stockpool、不写 data/score 历史）

使用方法：
    python backtest/score_api.py --codes 600519,000001
    python backtest/score_api.py --codes "sh.600519 sz.000001" --date 2026-07-28
    python backtest/score_api.py --codes 513120 --no-industry

输出：stdout 输出 JSON，格式：
    {
      "date": "2026-07-28",
      "count": 2,
      "results": [
        {"code": "600519", "symbol": "sh.600519", "name": "贵州茅台", "industry": "白酒",
         "score": 85.3, "pref_score": 18.0},
        {"code": "999999", "symbol": null, "name": "999999", "industry": null,
         "error": "无法识别市场前缀: 999999"}
      ]
    }
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# 添加项目根目录到 Python 路径（与 score_stockpool_my.py 同款做法）
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

# 静音：只保留 WARNING 及以上日志到 stderr，保证 stdout 只有 JSON
logger.remove()
logger.add(sys.stderr, level='WARNING')


def normalize_code(raw: str) -> Optional[str]:
    """
    归一化股票代码为带市场前缀的完整格式（sh./sz./bj.）

    支持输入：
        sh.600519 / sz.000001 / bj.430047   （已带前缀）
        600519 / 000001 / 300750 / 688127   （自动识别）
        513120（ETF）                        （5 开头 → sh）
    """
    raw = raw.strip()
    if not raw:
        return None

    if raw.startswith(('sh.', 'sz.', 'bj.')):
        return raw

    # 纯数字代码自动识别市场
    if raw.startswith(('6', '9', '5', '1')):
        return f'sh.{raw}'   # 6/9=沪市股票，5/1=沪市ETF
    if raw.startswith(('0', '3')):
        return f'sz.{raw}'   # 深市主板/中小板/创业板
    if raw.startswith(('8', '4')):
        return f'bj.{raw}'   # 北交所

    return None


def main():
    # 强制 stdout 以 UTF-8 输出：Windows 下默认 GBK，Node 侧按 UTF-8 解码会乱码
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="股票评分 API 桥（JSON 输出）")
    parser.add_argument('--codes', required=True,
                        help='股票代码，逗号或空格分隔，兼容 sh.600519 / 600519 / 600519,000001')
    parser.add_argument('--date', type=str, default=None,
                        help='分析日期 (YYYY-MM-DD)，默认今天')
    parser.add_argument('--no-industry', action='store_true',
                        help='跳过行业查询（东方财富接口，更快；名称仍会获取）')
    args = parser.parse_args()

    # === 参数校验 ===
    date_str = args.date or datetime.now().strftime('%Y-%m-%d')
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        print(json.dumps({'date': date_str, 'count': 0,
                          'error': f'日期格式错误: {date_str}，应为 YYYY-MM-DD'},
                         ensure_ascii=False))
        return 2

    raw_codes: List[str] = [c for c in re.split(r'[,\s]+', args.codes) if c]
    if not raw_codes:
        print(json.dumps({'date': date_str, 'count': 0, 'error': '未提供任何股票代码'},
                         ensure_ascii=False))
        return 2

    # === 初始化评分器（复用现有引擎，单实例共享缓存） ===
    try:
        from backtest.score_stockpool_my import HistoricalStockScorer
        scorer = HistoricalStockScorer()
    except Exception as e:
        print(json.dumps({'date': date_str, 'count': 0,
                          'error': f'初始化评分器失败: {e}'}, ensure_ascii=False))
        return 1

    results = []
    for raw in raw_codes:
        symbol = normalize_code(raw)
        entry = {'code': raw, 'symbol': symbol}

        if symbol is None:
            entry['name'] = raw
            entry['industry'] = None
            entry['error'] = f'无法识别市场前缀: {raw}'
            results.append(entry)
            continue

        code = symbol.split('.')[1]

        # === 名称 + 行业 ===
        try:
            if args.no_industry:
                from local.utils import get_stock_name
                name = get_stock_name(code)
                entry['name'] = name if name else code
                entry['industry'] = None
            else:
                name, industry = scorer._get_stock_info(symbol)
                entry['name'] = name if name else code
                entry['industry'] = industry
        except Exception as e:
            logger.warning(f"[API] 名称/行业获取失败 {symbol}: {e}")
            entry['name'] = code
            entry['industry'] = None

        # === 评分 ===
        try:
            result = scorer.analyze_stock(symbol, date_str)
            if result is None:
                entry['error'] = '评分失败（K线数据不足 60 条或获取失败）'
            else:
                entry['score'] = round(result[0], 1)
                entry['pref_score'] = round(result[1], 1)
        except Exception as e:
            logger.warning(f"[API] 评分异常 {symbol}: {e}")
            entry['error'] = f'评分异常: {e}'

        results.append(entry)

    # === 按综合评分降序排列（失败的排最后） ===
    results.sort(key=lambda e: e.get('score', -1), reverse=True)

    print(json.dumps({'date': date_str, 'count': len(results), 'results': results},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
