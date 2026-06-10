# -*- coding: utf-8 -*-
"""
选股条件诊断工具

功能：
1. 对指定日期的白名单股票逐一检查每个粗筛条件
2. 输出每个条件分别过滤了多少只股票
3. 重点展示新增条件（最大回撤 / 冲高回落）的过滤效果
4. 列出被新增条件过滤掉的具体股票

使用方法：
    python backtest/diagnose_conditions.py --date 2026-04-13
    python backtest/diagnose_conditions.py --date 2026-04-13 --sample 200
"""

import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import argparse

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backtest.generate_stockpool import StockPoolGenerator


def diagnose_single_stock(generator: StockPoolGenerator, stock_code: str, 
                          check_date: datetime) -> Dict:
    """
    对单只股票逐条件诊断，返回每个条件的通过情况
    
    Returns:
        dict: {
            'cond1_volume': True/False,       # 成交量放量
            'cond2_uptrend': True/False,       # ②a 突破启动
            'cond2b_final_up': True/False,      # ②b 最终上涨
            'cond2c_retracement': True/False,   # ②c 允许洗盘
            'cond2b_pullback': True/False,      # ②d 冲高回落
            'cond3_ma20': True/False,          # 站上MA20
            'cond4_return': True/False,        # 涨幅区间
            'cond5_vol_ratio': True/False,     # 量比区间
            'recent_return': float,            # 近期涨幅（用于展示）
            'vol_ratio': float,                # 量比（用于展示）
            'data_ok': True/False,             # 数据是否充足
        }
    """
    result = {
        'cond1_volume': False,
        'cond2_uptrend': False,
        'cond2b_final_up': False,
        'cond2c_retracement': False,
        'cond2b_pullback': False,
        'cond3_ma20': False,
        'cond4_return': False,
        'cond5_vol_ratio': False,
        'recent_return': 0.0,
        'vol_ratio': 0.0,
        'data_ok': False,
    }
    
    try:
        df = generator.get_stock_data(stock_code)
        if df is None or df.empty:
            return result
        
        df_before = df[df.index <= check_date]
        
        if len(df_before) < generator.volume_period + 20:
            return result
        
        result['data_ok'] = True
        
        # === 条件1：成交量放量（已优化）===
        base_volume = df_before['volume'].iloc[-generator.volume_period - 1]
        period_volumes = df_before['volume'].iloc[-generator.volume_period:].values
        threshold = base_volume * 0.95
        result['cond1_volume'] = all(v > threshold for v in period_volumes)
        
        closes = df_before['close'].iloc[-generator.volume_period:].values
        opens = df_before['open'].iloc[-generator.volume_period:].values
        
        # === 条件2：放量期价格稳步上涨（允许第2天小幅回调洗盘）===
        base_close = df_before['close'].iloc[-generator.volume_period - 1]
        
        # 2a：第1天收盘 > 基准日收盘（突破启动）
        cond2a = closes[0] > base_close
        result['cond2_uptrend'] = cond2a
        
        # 2b：最后1天收盘 > 第1天收盘（最终上涨）
        cond2b = closes[-1] > closes[0]
        result['cond2b_final_up'] = cond2b
        
        # 2c：第2天收盘 >= 启动开盘价 × 95%（允许洗盘，但不跌破）
        if len(closes) >= 2:
            start_price = opens[0]
            min_allowed = start_price * (1 + generator.max_retracement_pct / 100)
            cond2c = closes[1] >= min_allowed
        else:
            cond2c = True
        result['cond2c_retracement'] = cond2c
        
        # === 条件2d：冲高回落 ===
        highs = df_before['high'].iloc[-generator.volume_period:].values
        closes_check = df_before['close'].iloc[-generator.volume_period:].values
        cond2b_pass = True
        for h, c in zip(highs, closes_check):
            if h > 0:
                pullback = (h - c) / h * 100
                if pullback >= generator.max_intraday_pullback_pct:
                    cond2b_pass = False
                    break
        result['cond2b_pullback'] = cond2b_pass
        
        # === 条件3：站上MA20 ===
        ma20 = df_before['close'].rolling(20).mean().iloc[-1]
        latest_close = df_before['close'].iloc[-1]
        result['cond3_ma20'] = latest_close >= ma20
        
        # === 条件4：涨幅区间 ===
        recent_return = (closes[-1] - closes[0]) / closes[0] * 100
        result['recent_return'] = round(recent_return, 2)
        result['cond4_return'] = (generator.min_price_change_pct <= recent_return <= generator.max_price_change_pct)
        
        # === 条件5：量比区间 ===
        vol_ma20 = df_before['volume'].rolling(20).mean().iloc[-1]
        latest_vol = df_before['volume'].iloc[-1]
        vol_ratio = latest_vol / vol_ma20 if vol_ma20 > 0 else 1
        result['vol_ratio'] = round(vol_ratio, 2)
        result['cond5_vol_ratio'] = (generator.min_volume_ratio <= vol_ratio <= generator.max_volume_ratio)
        
        # === 条件6：相对强度（新增）===
        index_ret = generator._get_index_return(check_date, generator.volume_period)
        if index_ret is not None:
            relative_strength = recent_return - index_ret
            result['cond6_relative_strength'] = relative_strength >= generator.min_relative_strength
            result['index_return'] = round(index_ret, 2)
            result['relative_strength'] = round(relative_strength, 2)
        else:
            result['cond6_relative_strength'] = True  # 无沪深300数据时不限制
            result['index_return'] = 0.0
            result['relative_strength'] = 0.0
        
        # === 条件7：波动率风险过滤（新增）===
        daily_returns = df_before['close'].iloc[-21:].pct_change().dropna()
        volatility = float(daily_returns.std() * 100)
        result['cond7_volatility'] = volatility <= generator.max_volatility_pct
        result['volatility'] = round(volatility, 2)
        
    except Exception:
        pass
    
    return result


def main():
    parser = argparse.ArgumentParser(description="选股条件诊断工具")
    parser.add_argument('--date', type=str, required=True,
                       help='诊断日期 (YYYY-MM-DD)')
    parser.add_argument('--sample', type=int, default=None,
                       help='抽样数量（默认全部白名单）')
    parser.add_argument('--show-detail', action='store_true',
                       help='显示被新增条件过滤的详细股票')
    args = parser.parse_args()
    
    check_date = datetime.strptime(args.date, '%Y-%m-%d')
    
    # 构建配置
    config = {
        'start_date': check_date,
        'end_date': check_date,
        'volume_period': 3,
        'hold_days': 3,
        'whitelist_file': None,
        'tdx_dir': r"D:\Install\zd_zxzq_gm",
        'min_price_change_pct': 0.0,
        'max_price_change_pct': 20.0,
        'min_volume_ratio': 1.1,
        'max_volume_ratio': 5.0,
        'max_retracement_pct': -5.0,
        'max_intraday_pullback_pct': 8.0,
        'min_relative_strength': -2.0,
        'max_volatility_pct': 4.5,
    }
    
    print("=" * 70)
    print(f"  选股条件诊断报告 - {args.date}")
    print("=" * 70)
    
    # 初始化选股器
    print("\n[1/3] 初始化选股器...")
    generator = StockPoolGenerator(config)
    
    print("\n[2/3] 加载白名单...")
    generator.load_whitelist_stocks()
    
    whitelist = list(generator.whitelist)
    total_stocks = len(whitelist)
    
    if args.sample and args.sample < total_stocks:
        import random
        random.seed(42)
        whitelist = random.sample(whitelist, args.sample)
        print(f"  抽样 {args.sample} 只（共 {total_stocks} 只）")
    else:
        print(f"  全量白名单 {total_stocks} 只股票")
    
    print(f"\n[3/3] 逐条件诊断中（{len(whitelist)} 只）...")
    
    # 收集统计
    cond_stats = {
        'cond1_volume': {'name': '① 成交量放量（已优化）',       'pass': 0, 'fail': 0},
        'cond2_uptrend': {'name': '②a 突破启动（优化✅）',      'pass': 0, 'fail': 0},
        'cond2b_final_up': {'name': '②b 最终上涨（优化✅）',    'pass': 0, 'fail': 0},
        'cond2c_retracement': {'name': '②c 允许洗盘（优化✅）',  'pass': 0, 'fail': 0},
        'cond2b_pullback': {'name': '②d 冲高回落',              'pass': 0, 'fail': 0},
        'cond3_ma20': {'name': '③ 站上MA20',                  'pass': 0, 'fail': 0},
        'cond4_return': {'name': '④ 涨幅区间',                 'pass': 0, 'fail': 0},
        'cond5_vol_ratio': {'name': '⑤ 量比区间',              'pass': 0, 'fail': 0},
        'cond6_relative_strength': {'name': '⑥ 相对强度（新增✅）','pass': 0, 'fail': 0},
        'cond7_volatility': {'name': '⑦ 波动率过滤（新增✅）', 'pass': 0, 'fail': 0},
    }
    
    # 新增条件的详细淘汰记录
    pullback_rejected = []        # 被冲高回落过滤的
    relative_strength_rejected = []  # 被相对强度过滤的
    old_conditions_pass = 0       # 旧条件（不含2a/2b/6/7）全部通过的数量
    old_plus_new_pass = 0         # 旧条件+2a/2b+6通过的数量
    all_conditions_pass = 0       # 全部条件（含7）通过的数量
    volatility_rejected = []      # 被波动率过滤的
    
    start_time = time.time()
    for idx, stock_code in enumerate(whitelist):
        if (idx + 1) % 500 == 0:
            elapsed = time.time() - start_time
            print(f"    进度: {idx + 1}/{len(whitelist)} ({elapsed:.0f}s)")
        
        diag = diagnose_single_stock(generator, stock_code, check_date)
        
        if not diag['data_ok']:
            continue
        
        # 统计每个条件
        for cond_key in cond_stats:
            if diag.get(cond_key, False):
                cond_stats[cond_key]['pass'] += 1
            else:
                cond_stats[cond_key]['fail'] += 1
        
        # 旧条件（不含2a~2d/6/7）全部通过？
        cond2_pass = (diag['cond2_uptrend'] and diag['cond2b_final_up'] and diag['cond2c_retracement'])
        old_pass = (diag['cond1_volume'] and cond2_pass
                    and diag['cond3_ma20'] and diag['cond4_return'] 
                    and diag['cond5_vol_ratio'])
        if old_pass:
            old_conditions_pass += 1
        
        # 旧条件+2d+6通过（不含7）？
        old_plus_new = (old_pass and diag['cond2b_pullback']
                        and diag['cond6_relative_strength'])
        if old_plus_new:
            old_plus_new_pass += 1
        
        # 全部条件（含7）通过？
        all_pass = (old_plus_new and diag['cond7_volatility'])
        if all_pass:
            all_conditions_pass += 1
        
        # 记录被新增条件过滤的股票
        if old_pass and not diag['cond2b_pullback']:
            pullback_rejected.append((stock_code, diag['recent_return']))
        if old_plus_new and not diag['cond6_relative_strength']:
            relative_strength_rejected.append((stock_code, diag['recent_return'], diag.get('relative_strength', 0)))
        if old_plus_new and not diag['cond7_volatility']:
            volatility_rejected.append((stock_code, diag['recent_return'], diag.get('volatility', 0)))
    
    elapsed = time.time() - start_time
    
    # === 输出报告 ===
    print("\n" + "=" * 70)
    print("  📊 诊断结果汇总")
    print("=" * 70)
    
    # 条件通过率排行
    print(f"\n{'条件':<28} {'通过':>6} {'淘汰':>6} {'通过率':>8}")
    print("-" * 50)
    for key, stat in cond_stats.items():
        total = stat['pass'] + stat['fail']
        rate = stat['pass'] / total * 100 if total > 0 else 0
        tag = " ⭐新" if '新增' in stat['name'] else ""
        print(f"  {stat['name']:<25} {stat['pass']:>6} {stat['fail']:>6} {rate:>7.1f}%{tag}")
    
    # 新增条件效果
    print(f"\n{'─' * 50}")
    print(f"  🔍 新增条件过滤效果")
    print(f"{'─' * 50}")
    print(f"  旧条件（不含②a/②b/⑥）全部通过:        {old_conditions_pass:>6} 只")
    print(f"  旧条件+②a/②b通过（不含⑥）:          {old_plus_new_pass:>6} 只")
    print(f"  全部条件（含⑥）通过:                 {all_conditions_pass:>6} 只")
    if old_conditions_pass > 0:
        all_new_reject = old_conditions_pass - all_conditions_pass
        all_new_rate = all_new_reject / old_conditions_pass * 100
        print(f"  新增条件合计过滤:                   {all_new_reject:>6} 只 ({all_new_rate:.1f}%)")
    print(f"    其中 ②d 冲高回落过滤:              {len(pullback_rejected):>6} 只")
    print(f"    其中 ②b 冲高回落过滤:              {len(pullback_rejected):>6} 只")
    print(f"    其中 ⑥ 相对强度过滤:               {len(relative_strength_rejected):>6} 只")
    print(f"    其中 ⑦ 波动率过滤:                 {len(volatility_rejected):>6} 只")
    
    # 新增条件淘汰的详细股票
    if args.show_detail:
        if pullback_rejected:
            print(f"\n{'─' * 50}")
            print(f"  ❌ 被 ②d 冲高回落 过滤的股票（{len(pullback_rejected)} 只）")
            print(f"{'─' * 50}")
            for code, ret in sorted(pullback_rejected, key=lambda x: x[1])[:20]:
                print(f"    {code}  涨幅: {ret:>6.1f}%")
            if len(pullback_rejected) > 20:
                print(f"    ... 还有 {len(pullback_rejected) - 20} 只")
        
        if relative_strength_rejected:
            print(f"\n{'─' * 50}")
            print(f"  ❌ 被 ⑥ 相对强度 过滤的股票（{len(relative_strength_rejected)} 只）")
            print(f"{'─' * 50}")
            for code, ret, rs in sorted(relative_strength_rejected, key=lambda x: x[2])[:20]:
                print(f"    {code}  涨幅: {ret:>6.1f}%  相对强度: {rs:>6.1f}%")
            if len(relative_strength_rejected) > 20:
                print(f"    ... 还有 {len(relative_strength_rejected) - 20} 只")
        
        if volatility_rejected:
            print(f"\n{'─' * 50}")
            print(f"  ❌ 被 ⑦ 波动率 过滤的股票（{len(volatility_rejected)} 只）")
            print(f"{'─' * 50}")
            for code, ret, vol in sorted(volatility_rejected, key=lambda x: x[2], reverse=True)[:20]:
                print(f"    {code}  涨幅: {ret:>6.1f}%  波动率: {vol:>5.2f}%")
            if len(volatility_rejected) > 20:
                print(f"    ... 还有 {len(volatility_rejected) - 20} 只")
    
    print(f"\n{'─' * 50}")
    print(f"  ⏱  耗时: {elapsed:.1f} 秒")
    print(f"  📈 诊断股票数: {len(whitelist)} 只")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
