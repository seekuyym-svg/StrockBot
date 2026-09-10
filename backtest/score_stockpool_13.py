# -*- coding: utf-8 -*-
"""
股票池13精选工具（动态综合分档）

功能：
1. 读取 _all.txt（当日全部评分结果）
2. 只选优选分13分的股票
3. 依据当日(收盘后)成交量能自动切换综合分档(与buy_decision评分量比口径统一)：
   - 缩量/正常（volume_ratio < 1.05）→ 选 13分 ∩ 综合分≤66（错杀价值）
   - 温和放量（1.05 ≤ volume_ratio ≤ 1.15）→ 选 13分 ∩ 综合分67~69（强者恒强，剔除70过热）
   - 过热（volume_ratio > 1.15）→ 空仓（与 buy_decision 评分过热扣分口径一致，不追高）
4. 有多少选多少，不补足（宁可少选/空着，不买凑数的票）
5. 输出 stockpool_YYYYMMDD.txt（直接作为选股池）

依据（全样本回测，见 backtest/FINAL_PLAN_v2026.md）：
- 动态分档(缩量选≤66 / 温和放量选67-69剔70 / 量比>1.15空仓)优于静态单档
- 配合9:26评分门控{3,4,6}：46天复利+32.52%（买13分21天/空仓5天/ETF20天）
- 逻辑：市场温和放量=资金抱团强者(选67-69)；缩量=资金精挑错杀票(选≤66)；过热=空仓
- 量比来源：复用 trade_decision.market_signal.fetch_market_volume（与评分口径统一）：
  优先 signal_history.json（update_indices.py 20:50 生成）；无记录（如当日16:00收盘后）
  则用腾讯行情实时计算（比东财 push2his 稳定），无需等 20:50

使用方法：
    python backtest/score_stockpool_13.py --date 2026-07-14
    python backtest/score_stockpool_13.py --start-date 2026-07-01 --end-date 2026-07-15
"""

import argparse
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

DATA_DIR = Path(__file__).parent.parent / "data"

# 放量阈值：volume_ratio >= 1.05 视为放量
VOL_RATIO_THRESHOLD = 1.05


def load_volume_ratio(date_str: str):
    """
    计算当日沪深市场量比（与 buy_decision 评分、market_signal 口径完全统一）

    直接复用 trade_decision.market_signal.fetch_market_volume：
      1. 优先读 signal_history.json（update_indices.py 20:50 生成，覆盖历史回测日期）；
      2. 无记录（如当日16:00收盘后）则用腾讯行情实时计算（sh000001+sz399106 成交额，
         5日均量按K线成交量×均价估算）——腾讯源比东财 push2his 稳定。
    该函数就是 signal_history.json 中 volume_ratio 的生成源，故口径天然一致。

    Returns:
        float volume_ratio（当日成交额 / 前5日均量），失败返回 None
    """
    try:
        import sys as _sys
        root = str(Path(__file__).parent.parent)
        if root not in _sys.path:
            _sys.path.insert(0, root)
        from trade_decision.market_signal import fetch_market_volume
        mv = fetch_market_volume(date_str)
        if mv and mv.get('ratio') is not None:
            avg = mv.get('avg_5')
            tail = f" / 5日均{avg:.0f}亿" if avg else ""
            print(f"     📊 量比: 当日{mv['current']:.0f}亿{tail} = {mv['ratio']:.2f}")
            return mv['ratio']
        print(f"     ⚠ {date_str} 量比获取失败（signal_history无记录且非交易日）")
    except Exception as e:
        print(f"     ⚠ 量比获取失败({e})")
    return None


def process_date(date_str: str, override_vol: float = None):
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
    
    # 读当日量比，决定综合分档（--vol-ratio 手工值优先）
    vol_ratio = override_vol if override_vol is not None else load_volume_ratio(date_str)
    # 与 buy_decision 评分量比口径统一：
    #   量比 0.85~1.05 → 评分3分(健康)  1.05~1.15 → 2分(温和放量)
    #   量比 <0.85     → 2分(缩量)      1.15~1.30 → 1分(过热)  >1.30 → 0分(极度过热)
    if vol_ratio is not None and vol_ratio > 1.15:
        # 过热区（评分只给0-1分）：与评分一致，不追高 → 空仓
        mode = 'halt'
        mode_desc = f'量比{vol_ratio:.2f}>1.15(评分过热区) → 空仓'
        filtered = []
    elif vol_ratio is not None and vol_ratio >= 1.05:
        # 温和放量(评分2-3分健康)：强者恒强 → 高分13分（67~69，剔除70过热分）
        mode = 'high'
        mode_desc = f'放量(vol_ratio={vol_ratio:.2f},1.05~1.15评分尚可) → 选高分13分(综合分67-69)'
        filtered = [r for r in records if int(r['pref']) == 13 and 67 <= r['score'] <= 69]
    else:
        # 缩量/正常(评分2-3分健康)：错杀价值 → 低分13分（≤66）
        mode = 'low'
        vr = vol_ratio if vol_ratio is not None else 'N/A'
        mode_desc = f'缩量/正常(vol_ratio={vr}) → 选低分13分(综合分≤66)'
        filtered = [r for r in records if int(r['pref']) == 13 and r['score'] <= 66]
    filtered.sort(key=lambda r: (-r['score']))
    
    # 输出结果
    print(f"\n  📅 {date_str}  —  原始{len(records)}只 → 13精选{len(filtered)}只")
    print(f"     🔀 {mode_desc}")
    
    if not filtered:
        print(f"     今日无符合条件的股票，空仓")
        print(f"     💡 注意：不生成 stockpool_{dc}.txt，若明日评分=4/6将按【空仓】处理（buy_decision_history记空仓）")
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
        f.write(f"# 筛选规则: 仅13分; 动态分档({mode}); 不补足; 按综合评分降序\n")
        f.write(f"# 格式: 股票代码,综合评分,优选分\n")
        f.write("# === 精选数据 ===\n")
        for r in filtered:
            f.write(f"{r['code']},{r['score']},{r['pref']:.0f}\n")
    
    print(f"     ✅ 已保存: {out_path.name}")
    return filtered


def main():
    parser = argparse.ArgumentParser(description='股票池13精选工具（动态综合分档，不补足）')
    parser.add_argument('--date', type=str, help='处理日期 (YYYY-MM-DD)')
    parser.add_argument('--start-date', type=str, help='起始日期')
    parser.add_argument('--end-date', type=str, help='结束日期')
    parser.add_argument('--vol-ratio', type=float, default=None, help='手工指定当日量比（联网失败时用，如 1.03）')
    
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
        process_date(dt, args.vol_ratio)


if __name__ == "__main__":
    main()
