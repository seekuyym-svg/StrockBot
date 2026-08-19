# -*- coding: utf-8 -*-
"""
大盘环境信号工具（L1过滤器） — 双指数联合信号

独立运行，人工参考。
判断当前大盘是否适合买入，输出清晰明确的信号。

参考指数（可配置，默认双指数联合）：
  - 沪深300（大蓝筹环境，使用本地 data/index_hs300.csv）
  - 科创综指（科技成长环境，使用本地 data/index_kc.csv）
全市场成交额：通过东方财富API获取（上证+深证）

信号逻辑（双指数共识模式）：
  每个指数独立检查两个条件：
    ① 收盘价 > 短期均线（默认20日）
    ② 短期均线 > 长期均线（默认60日）
  两个条件都满足 → 该指数"健康"
  
  决策模式（pass_mode）:
    "dual_consensus" — 所有指数都健康 + 成交额达标（默认）
    "strict"         — 全部条件通过
    "flexible"       — 至少 N 个条件通过

使用方法:
    # 检查今天
    python trade_decision/market_signal.py
    
    # 检查指定日期
    python trade_decision/market_signal.py --date 2026-04-13
    
    # 指定通过模式
    python trade_decision/market_signal.py --mode strict
    
    # JSON输出
    python trade_decision/market_signal.py --json

配置参数（config.yaml trade_decision 节点）:
    ma_short: 20                # 短期均线
    ma_long: 60                 # 长期均线
    min_market_volume: 25000    # 最小全市场成交额（亿元）
    pass_mode: "dual_consensus"  # 通过模式
    indices:                    # 参考指数列表
      - name: "沪深300"
        code: "1.000300"
        data_file: "data/index_hs300.csv"
        enabled: true
      - name: "科创综指"
        code: "1.000680"
        data_file: "data/index_kc.csv"
        enabled: true
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import argparse
import pandas as pd
import requests

project_root = Path(__file__).parent.parent


# ==================== 配置加载 ====================

def load_config() -> dict:
    """从 config.yaml 加载 trade_decision 配置"""
    try:
        import yaml
        config_file = project_root / "config.yaml"
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                full_config = yaml.safe_load(f)
            return full_config.get('trade_decision', {})
    except Exception:
        pass
    return {}


# ==================== 指数数据加载 ====================

def load_index_data(data_file: str) -> Optional[pd.DataFrame]:
    """
    从本地CSV加载指数数据

    Args:
        data_file: 相对于项目根目录的路径，如 "data/index_hs300.csv"

    Returns:
        DataFrame 含 date(索引), close/open/high/low/volume，或 None
    """
    csv_path = project_root / data_file
    if not csv_path.exists():
        return None

    try:
        df = pd.read_csv(csv_path, parse_dates=['date'])
        df = df.set_index('date').sort_index()
        df.index.name = 'date'
        return df
    except Exception as e:
        print(f"⚠️ 读取 {data_file} 失败: {e}")
        return None


def check_single_index(df: pd.DataFrame, check_dt, ma_short: int, ma_long: int, index_name: str) -> Optional[dict]:
    """
    检查单个指数的均线条件

    Args:
        df: 指数DataFrame（date索引，含close列）
        check_dt: 检查日期
        ma_short: 短期均线周期
        ma_long: 长期均线周期
        index_name: 指数显示名称

    Returns:
        dict 包含该指数的均线数据和条件结果，数据不足时返回 None
    """
    df_before = df[df.index <= check_dt].copy()
    if len(df_before) < ma_long + 1:
        return None

    ma_s_name = f'ma{ma_short}'
    ma_l_name = f'ma{ma_long}'

    df_before[ma_s_name] = df_before['close'].rolling(window=ma_short).mean()
    df_before[ma_l_name] = df_before['close'].rolling(window=ma_long).mean()

    latest = df_before.iloc[-1]
    prev = df_before.iloc[-2] if len(df_before) >= 2 else None
    close = latest['close']
    prev_close = prev['close'] if prev is not None else close
    change_pct = round((close - prev_close) / prev_close * 100, 2)
    ma_s_val = latest[ma_s_name]
    ma_l_val = latest[ma_l_name]

    cond1_pass = close > ma_s_val
    cond2_pass = ma_s_val > ma_l_val

    return {
        'name': index_name,
        'data_count': len(df_before),
        'close': round(close, 2),
        'change_pct': change_pct,
        ma_s_name: round(ma_s_val, 2),
        ma_l_name: round(ma_l_val, 2),
        'cond1': (bool(cond1_pass), f"{index_name}收盘 {close:.0f} > {ma_short}日线 {ma_s_val:.0f}?"),
        'cond2': (bool(cond2_pass), f"{index_name} {ma_short}日线 {ma_s_val:.0f} > {ma_long}日线 {ma_l_val:.0f}?"),
        'healthy': cond1_pass and cond2_pass,
    }


# ==================== 沪深市场成交额分析 ====================

def fetch_market_volume(check_date: str) -> Optional[dict]:
    """
    从东方财富获取沪深市场成交额分析

    同时获取上证（000001）和深证（399106）的日K线成交额，
    逐日相加得到沪深合计成交额（亿元），计算5日均量及放缩量判断。

    数据覆盖：
    - 上证指数(000001)：沪市全部，含科创板
    - 深证综指(399106)：深市全部，含创业板

    Returns:
        dict: { current, avg_5, ratio, trend }
        - current: 当日沪深成交额（亿元）
        - avg_5: 过去5个交易日均量（亿元）
        - ratio: 当日 / 5日均量 比值
        - trend: "明显放量" | "温和放量" | "正常" | "温和缩量" | "明显缩量"
        失败时返回 None
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    import re as _re

    # ========== 优先从 signal_history.json 读取当天真实成交额 ==========
    try:
        signal_file = project_root / "data" / "signal_history.json"
        if signal_file.exists():
            with open(signal_file, 'r', encoding='utf-8') as _f:
                records = json.load(_f)
            for record in reversed(records):
                if record.get('date') == check_date:  # 只精确匹配当天记录
                    mv = record.get('market_volume')
                    if mv is not None:
                        result = {
                            'current': round(float(mv), 0),
                            'avg_5': record.get('volume_avg_5'),
                            'ratio': record.get('volume_ratio'),
                            'trend': record.get('volume_trend'),
                        }
                        print(f"   ✅ signal_history.json: 成交额{result['current']:.0f}亿" +
                              (f", 5日均量≈{result['avg_5']:.0f}亿" if result['avg_5'] else ""))
                        return result
                    break
            # 无当天记录且非当日：无法获取该历史日期数据
            if check_date != datetime.now().strftime('%Y-%m-%d'):
                print(f"   ⚠️ {check_date} 无存档记录且非当日，无法获取成交额")
                return None
            print(f"   ⚠️ signal_history.json 无 {check_date} 当天记录，改用腾讯实时行情")
    except Exception as e:
        print(f"   ⚠️ signal_history.json 读取失败({e})，降级腾讯行情")

    # ========== 获取成交额（腾讯财经主源） ==========
    current_yuan = 0.0
    try:
        # 1. 实时行情获取今日成交额（元）
        for _code in ('sh000001', 'sz399106'):
            resp = requests.get(f"http://qt.gtimg.cn/q={_code}", headers=headers, timeout=10)
            resp.encoding = 'gbk'
            match = _re.search(r'=\"([^\"]+)\"', resp.text)
            if match:
                parts = match.group(1).split('~')
                if len(parts) > 35:
                    vol_parts = parts[35].split('/')
                    if len(vol_parts) >= 3:
                        current_yuan += float(vol_parts[2])
        current = round(current_yuan / 1e8, 0)

        # 2. K线成交量估算历史成交额
        sh_kline, sz_kline = {}, {}
        for _code in ('sh000001', 'sz399106'):
            resp = requests.get(
                "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
                params={"param": f"{_code},day,,,15,qfq"},
                headers=headers, timeout=10
            )
            data = resp.json()
            if data.get('data') and data['data'].get(_code, {}).get('day'):
                dic = {k[0]: float(k[5]) for k in data['data'][_code]['day']}
                if _code == 'sh000001':
                    sh_kline = dic
                else:
                    sz_kline = dic

        common_dates = sorted(set(sh_kline.keys()) & set(sz_kline.keys()))
        if common_dates and len(common_dates) >= 3:
            today_str = common_dates[-1]
            today_total_vol = sh_kline[today_str] + sz_kline[today_str]
            price_per_lot = current_yuan / today_total_vol if today_total_vol > 0 else 0
            daily_totals = []
            for d in common_dates:
                vol = sh_kline[d] + sz_kline[d]
                est_amt = round(vol * price_per_lot / 1e8, 0)
                daily_totals.append({'date': d, 'total': est_amt})
            recent5 = [d for d in daily_totals if d['total'] > 0][-5:]
            avg_5 = round(sum(d['total'] for d in recent5) / len(recent5), 0) if len(recent5) >= 3 else None
        else:
            avg_5 = None

        print(f"   ✅ 腾讯行情: 成交额{current:.0f}亿" +
              (f", 5日均量≈{avg_5:.0f}亿" if avg_5 else ""))

    except Exception as e:
        print(f"   ❌ 腾讯行情也失败: {e}")
        return None

    # 放缩量判断
    ratio = round(current / avg_5, 2) if (avg_5 is not None and avg_5 > 0) else None

    if ratio is None:
        trend = None
    elif ratio >= 1.20:
        trend = "明显放量"
    elif ratio >= 1.05:
        trend = "温和放量"
    elif ratio <= 0.80:
        trend = "明显缩量"
    elif ratio <= 0.95:
        trend = "温和缩量"
    else:
        trend = "正常"

    return {
        'current': current,
        'avg_5': avg_5,
        'ratio': ratio,
        'trend': trend,
    }


# ==================== 情绪数据（同花顺涨跌家数） ====================

EMOTION_FILE = project_root / "data" / "market_emotion.txt"


def load_market_emotion(check_date: str) -> Optional[dict]:
    """
    读取同花顺市场情绪数据，判断情绪开关（允许开仓/熔断）

    从 market_emotion.txt 中获取指定日期的涨跌家数、涨跌停等数据。
    判断逻辑（与飞书推送保持一致）:
      - 涨停 < 35 家 → 短线冷清
      - 跌停 > 15 家 → 恐慌蔓延
      - 涨跌比 < 0.25 → 极端普跌
      - 昨涨停今收益 < -1.5% → 接力亏钱

    Returns:
        dict: { up, down, limit_up, limit_down, zt_pct, score, suggestion,
                emotion_safe, emotion_reason }
        文件不存在或无当日数据时返回 None
    """
    if not EMOTION_FILE.exists():
        return None

    try:
        import csv
        with open(EMOTION_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('date') == check_date:
                    limit_up = int(row.get('limit_up', 0))
                    limit_down = int(row.get('limit_down', 0))
                    up_count = int(row.get('up', 0))
                    down_count = int(row.get('down', 0))
                    zt_pct = float(row.get('zt_percent', 0))
                    score = row.get('score', '')
                    suggestion = row.get('suggestion', '')
                    ratio = round(up_count / (down_count + 0.01), 2)

                    # 情绪开关判断（同 news_scheduler.py 逻辑）
                    emotion_safe = True
                    emotion_reason = ""
                    emotion_reason = ""
                    if limit_up < 35:
                        emotion_safe = False
                        emotion_reason = f"涨停仅{limit_up}家，低于35家"
                    elif limit_down > 30:
                        emotion_safe = False
                        emotion_reason = f"跌停{limit_down}家，超过30家"
                    elif ratio < 0.25:
                        emotion_safe = False
                        emotion_reason = f"涨跌比{ratio}，市场普跌"
                    elif zt_pct < -1.5:
                        emotion_safe = False
                        emotion_reason = f"昨涨停今均{zt_pct:+.2f}%，接力亏钱"

                    # 沪深港通数据（可能为空，历史数据无此列）
                    north_total = row.get('north_total', '').strip()
                    south_net = row.get('south_net', '').strip()

                    return {
                        'date': check_date,
                        'ratio': ratio,
                        'score': score,
                        'emotion_pass': emotion_safe,
                        'emotion_reason': emotion_reason,
                        'north_total': float(north_total) if north_total else None,
                        'south_net': float(south_net) if south_net else None,
                    }

        return None

    except Exception:
        return None


# ==================== 核心信号判断 ====================

def check_market_signal(check_date: str = None, pass_mode: str = None) -> Dict:
    """
    检查大盘环境信号（双指数联合）

    流程:
    1. 加载所有 enabled 的指数本地数据
    2. 每个指数计算均线并检查条件（close>MA20? MA20>MA60?）
    3. 获取全市场成交额
    4. 根据 pass_mode 合并判断

    Args:
        check_date: 检查日期 (YYYY-MM-DD)，默认今天
        pass_mode: 覆盖配置中的 pass_mode，可选

    Returns:
        dict 包含完整信号结果
    """
    if check_date is None:
        check_date = datetime.now().strftime('%Y-%m-%d')

    cfg = load_config()
    ma_short = cfg.get('ma_short', 20)
    ma_long = cfg.get('ma_long', 60)
    min_volume = cfg.get('min_market_volume', 25000)       # 活跃度充足线
    min_volume_low = cfg.get('min_market_volume_low', 20000)  # 活跃度及格线
    indices_cfg = cfg.get('indices', [])
    mode = pass_mode or cfg.get('pass_mode', 'dual_consensus')
    flex_count = cfg.get('flexible_pass_count', 3)

    check_dt = pd.to_datetime(check_date)

    # ========== 加载各指数数据 ==========
    index_results = []
    data_errors = []

    for ic in indices_cfg:
        if not ic.get('enabled', True):
            continue

        df = load_index_data(ic['data_file'])
        if df is None:
            data_errors.append(f"{ic['name']}数据文件不存在: {ic['data_file']}")
            continue

        result = check_single_index(df, check_dt, ma_short, ma_long, ic['name'])
        if result is None:
            data_errors.append(f"{ic['name']}数据不足（需要至少{ma_long+1}条），请更新数据")
            continue

        index_results.append(result)

    # ========== 检查是否有有效的指数数据 ==========
    if not index_results:
        return {
            'date': check_date,
            'passed': False,
            'reasons': data_errors or ['没有可用的指数数据'],
            'pass_mode': mode,
        }

    # ========== 获取全市场成交额 ==========
    market_volume = fetch_market_volume(check_date)

    if market_volume is not None:
        vol_current = market_volume['current']
        # 三层活跃度：<20000亿不足 | 20000~25000还行 | >=25000充足
        cond_vol_pass = vol_current >= min_volume_low
        if vol_current >= min_volume:
            vol_level = "充足"
        elif vol_current >= min_volume_low:
            vol_level = "还行"
        else:
            vol_level = "不足"
        cond_vol_desc = f"全市场成交额 {vol_current:.0f}亿（活跃度{vol_level}）"
    else:
        cond_vol_pass = True  # 获取失败时不阻挡
        cond_vol_desc = "全市场成交额 获取失败（跳过此条件）"

    # ========== 获取同花顺情绪数据 ==========
    emotion = load_market_emotion(check_date)
    if emotion is not None:
        cond_emotion_pass = emotion['emotion_pass']
        status = "允许开仓" if cond_emotion_pass else "禁止开仓"
        cond_emotion_desc = f"情绪开关: {status}"
    else:
        cond_emotion_pass = True  # 情绪数据不存在时不阻挡
        cond_emotion_desc = "情绪开关: 暂无数据（跳过此条件）"

    # ========== 汇总条件列表 ==========
    # 每个指数贡献2个条件
    all_conditions = []
    for ir in index_results:
        all_conditions.append(ir['cond1'])
        all_conditions.append(ir['cond2'])
    # 成交额条件
    all_conditions.append((cond_vol_pass, cond_vol_desc))
    # 情绪条件
    all_conditions.append((cond_emotion_pass, cond_emotion_desc))

    passed_count = sum(1 for c in all_conditions if c[0])
    total_count = len(all_conditions)

    # ========== 根据 pass_mode 判断 ==========
    passed = False
    reasons = []

    if mode == 'dual_consensus':
        # 每个指数必须都健康 + 成交额达标 + 情绪健康
        all_healthy = all(ir['healthy'] for ir in index_results)
        passed = all_healthy and cond_vol_pass and cond_emotion_pass

        if not all_healthy:
            for ir in index_results:
                if not ir['healthy']:
                    unhealthy_parts = []
                    if not ir['cond1'][0]:
                        unhealthy_parts.append(f"收盘({ir['close']:.0f}) < {ma_short}日线({ir[f'ma{ma_short}']:.0f})")
                    if not ir['cond2'][0]:
                        unhealthy_parts.append(f"{ma_short}日线({ir[f'ma{ma_short}']:.0f}) < {ma_long}日线({ir[f'ma{ma_long}']:.0f})")
                    reasons.append(f"{ir['name']}不健康: {'; '.join(unhealthy_parts)}")
        if not cond_vol_pass and market_volume is not None:
            reasons.append(f"成交额({market_volume['current']:.0f}亿) < {min_volume_low}亿，市场活跃度不足")
        if not cond_emotion_pass and emotion is not None:
            reasons.append(f"情绪禁止开仓: {emotion['emotion_reason']}")

    elif mode == 'strict':
        passed = passed_count == total_count

        for ir in index_results:
            if not ir['cond1'][0]:
                reasons.append(f"{ir['name']}收盘({ir['close']:.0f}) < {ma_short}日线({ir[f'ma{ma_short}']:.0f})")
            if not ir['cond2'][0]:
                reasons.append(f"{ir['name']}{ma_short}日线({ir[f'ma{ma_short}']:.0f}) < {ma_long}日线({ir[f'ma{ma_long}']:.0f})")
        if not cond_vol_pass and market_volume is not None:
            reasons.append(f"成交额({market_volume['current']:.0f}亿) < {min_volume_low}亿，市场活跃度不足")

    else:  # 'flexible'
        passed = passed_count >= flex_count

        if passed_count < flex_count:
            for ir in index_results:
                if not ir['cond1'][0]:
                    reasons.append(f"{ir['name']}收盘({ir['close']:.0f}) < {ma_short}日线({ir[f'ma{ma_short}']:.0f})")
                if not ir['cond2'][0]:
                    reasons.append(f"{ir['name']}{ma_short}日线({ir[f'ma{ma_short}']:.0f}) < {ma_long}日线({ir[f'ma{ma_long}']:.0f})")
            if not cond_vol_pass and market_volume is not None:
                reasons.append(f"成交额({market_volume['current']:.0f}亿) < {min_volume_low}亿，市场活跃度不足")

    # ========== 构建结果 ==========
    # 扁平化条件编号（cond1 ~ condN）用于输出
    flat_conds = {}
    cond_idx = 1
    for ir in index_results:
        flat_conds[f'cond{cond_idx}'] = ir['cond1']
        cond_idx += 1
        flat_conds[f'cond{cond_idx}'] = ir['cond2']
        cond_idx += 1
    flat_conds[f'cond{cond_idx}'] = (cond_vol_pass, cond_vol_desc)
    cond_idx += 1
    flat_conds[f'cond{cond_idx}'] = (cond_emotion_pass, cond_emotion_desc)

    # 量能趋势（从 market_volume dict 中提取）
    vol_avg_5 = market_volume['avg_5'] if market_volume is not None else None
    vol_ratio = market_volume['ratio'] if market_volume is not None else None
    vol_trend = market_volume['trend'] if market_volume is not None else None

    result = {
        'date': check_date,
        'pass_mode': mode,
        'ma_short': ma_short,
        'ma_long': ma_long,
        'min_volume': min_volume,
        'indices': index_results,
        'market_volume': market_volume,
        'volume_avg_5': vol_avg_5,
        'volume_ratio': vol_ratio,
        'volume_trend': vol_trend,
        'volume_level': vol_level if market_volume is not None else None,
        'cond_volume': (cond_vol_pass, cond_vol_desc),
        'emotion': emotion,
        'cond_emotion': (cond_emotion_pass, cond_emotion_desc),
        'passed': passed,
        'reasons': reasons,
        'passed_conditions': passed_count,
        'total_conditions': total_count,
        **flat_conds,  # cond1, cond2, ... condN for simple access
    }

    return result


# ==================== 输出格式化 ====================

def format_output(result: Dict):
    """格式化输出双指数联合信号结果"""
    mode_labels = {
        'dual_consensus': '双指数共识',
        'strict': '全部通过',
        'flexible': f"灵活通过 (≥{result.get('passed_conditions', 0)}/{result.get('total_conditions', 0)})",
    }
    mode_label = mode_labels.get(result['pass_mode'], result['pass_mode'])

    print()
    print("=" * 64)
    print(f"  📡 大盘环境信号（双指数）— {result['date']}")
    print(f"     模式: {mode_label}")
    print("=" * 64)

    # ========== 各指数情况 ==========
    for ir in result.get('indices', []):
        icon = "✅" if ir['healthy'] else "❌"
        ma_s = result['ma_short']
        ma_l = result['ma_long']
        ma_s_val = ir[f'ma{ma_s}']
        ma_l_val = ir[f'ma{ma_l}']
        chg = ir.get('change_pct', 0)
        print(f"\n  {icon} {ir['name']}  ({chg:+.2f}%)")
        print(f"    收盘: {ir['close']:.0f}  |  {ma_s}日线: {ma_s_val:.0f}  |  {ma_l}日线: {ma_l_val:.0f}")
        c1_pass, c1_desc = ir['cond1']
        c2_pass, c2_desc = ir['cond2']
        print(f"    {'✅' if c1_pass else '❌'} {c1_desc}")
        print(f"    {'✅' if c2_pass else '❌'} {c2_desc}")

    # ========== 成交额 ==========
    vol = result.get('market_volume')
    if vol is not None:
        trend = result.get('volume_trend', '') or ''
        avg = result.get('volume_avg_5', 0)
        if avg:
            vol_str = f"{vol['current']:.0f}亿 (5日均量: {avg:.0f}亿, {trend})" if trend else f"{vol['current']:.0f}亿"
        else:
            vol_str = f"{vol['current']:.0f}亿"
        print(f"\n  {'✅' if result['cond_volume'][0] else '❌'} 沪深市场成交额: {vol_str}  (阈值: {result['min_volume']}亿)")
    else:
        print(f"\n  ⚠️  沪深市场成交额: 获取失败（跳过此条件）")

    # ========== 情绪 ==========
    emotion = result.get('emotion')
    if emotion is not None:
        emoji = "✅" if emotion['emotion_pass'] else "❌"
        status = "允许开仓" if emotion['emotion_pass'] else "禁止开仓"
        print(f"\n  {emoji} 情绪开关: {status}")
    else:
        print(f"\n  ⚪ 情绪开关: 暂无数据")

    # ========== 汇总 ==========
    print(f"\n  {'─' * 58}")
    print(f"  条件通过: {result['passed_conditions']}/{result['total_conditions']}")
    print(f"  {'─' * 58}")

    if result['passed']:
        print(f"\n  📗 结果: ✅ 允许买入")
        print(f"    所有指数环境健康，可以执行选股+评分+买入")
    else:
        print(f"\n  📕 结果: ❌ 禁止买入")
        for r in result['reasons']:
            print(f"    • {r}")
        print(f"    建议: 空仓等待，等信号好转再入场")

    print(f"\n{'=' * 64}")
    print()


def format_output_single(result: Dict):
    """
    兼容单指数模式的格式化输出（用于 indices 为空时回退）
    保留旧版输出风格
    """
    print()
    print("=" * 60)
    print(f"  📡 大盘环境信号 - {result['date']}")
    print("=" * 60)
    print()
    print(f"  条件通过: {result.get('passed_conditions', '?')}/{result.get('total_conditions', '?')}")

    vol = result.get('market_volume')
    if vol is not None:
        trend = result.get('volume_trend', '') or ''
        avg = result.get('volume_avg_5', 0)
        if avg:
            trend_str = f' ({trend})' if trend else ''
            print(f"  沪深市场成交额: {vol['current']:.0f}亿  (5日均量: {avg:.0f}亿{trend_str})")
        else:
            print(f"  沪深市场成交额: {vol['current']:.0f}亿")
    else:
        print(f"  沪深市场成交额:   获取失败")
    print()
    print(f"  {'─' * 50}")
    print(f"  条件检查:")
    for i in range(1, result.get('total_conditions', 0) + 1):
        k = f'cond{i}'
        if k in result:
            passed, desc = result[k]
            icon = "✅" if passed else "❌"
            print(f"   条件{i}: {icon} {desc}")
    print()
    print(f"  {'─' * 50}")

    if result['passed']:
        print(f"  结果: ✅ 允许买入")
    else:
        print(f"  结果: ❌ 禁止买入")
        for r in result['reasons']:
            print(f"    原因: {r}")

    print(f"\n{'=' * 60}")
    print()


def _serialize_conditions(result: Dict) -> Dict:
    """将结果中的条件元组转为可JSON序列化的字典"""
    out = result.copy()

    # 扁平条件 cond1 ~ condN
    for i in range(1, 10):
        k = f'cond{i}'
        if k in out and isinstance(out[k], tuple):
            passed, desc = out[k]
            out[k] = {'passed': passed, 'desc': desc}

    # cond_volume
    if 'cond_volume' in out and isinstance(out['cond_volume'], tuple):
        passed, desc = out['cond_volume']
        out['cond_volume'] = {'passed': passed, 'desc': desc}

    # indices 内的条件和类型转换
    if 'indices' in out:
        for ir in out['indices']:
            if 'cond1' in ir and isinstance(ir['cond1'], tuple):
                p, d = ir['cond1']
                ir['cond1'] = {'passed': bool(p), 'desc': d}
            if 'cond2' in ir and isinstance(ir['cond2'], tuple):
                p, d = ir['cond2']
                ir['cond2'] = {'passed': bool(p), 'desc': d}
            # numpy 类型转 Python 原生
            for k, v in ir.items():
                if hasattr(v, 'item'):
                    ir[k] = v.item()

    return out


# ==================== 历史信号存档 ====================

SIGNAL_HISTORY_FILE = project_root / "data" / "signal_history.json"


def save_signal_history(result: Dict):
    """
    将本次信号结果存入 signal_history.json（按日期追加/更新）

    每日执行时自动保存，同一日期重复运行则覆盖更新（不产生重复条目）。
    用于后续分析信号准确度、对比历史表现。

    存储内容（精简可序列化）：
    - 日期、通过模式、最终结果
    - 各指数收盘/均线/条件详情
    - 成交额
    """
    if not result.get('indices'):
        return  # 数据不完整不保存

    # 构建精简记录（纯Python原生类型，可直接JSON序列化）
    def _get_cond_pass(cond):
        """兼容 tuple (bool, str) 和 dict {'passed': bool, 'desc': str} 两种格式"""
        if isinstance(cond, tuple):
            return bool(cond[0])
        if isinstance(cond, dict):
            return bool(cond['passed'])
        return False

    indices_summary = []
    for ir in result['indices']:
        ma_s = result['ma_short']
        ma_l = result['ma_long']
        indices_summary.append({
            'name': ir['name'],
            'close': ir['close'],
            'change_pct': ir.get('change_pct', 0),
            f'ma{ma_s}': ir[f'ma{ma_s}'],
            f'ma{ma_l}': ir[f'ma{ma_l}'],
            'cond1_pass': _get_cond_pass(ir['cond1']),
            'cond2_pass': _get_cond_pass(ir['cond2']),
            'healthy': bool(ir['healthy']),
        })

    mv = result.get('market_volume')
    record = {
        'date': result['date'],
        'pass_mode': result['pass_mode'],
        'passed': bool(result['passed']),
        'passed_conditions': int(result['passed_conditions']),
        'total_conditions': int(result['total_conditions']),
        'indices': indices_summary,
        'market_volume': mv['current'] if mv else None,
        'volume_avg_5': mv['avg_5'] if mv else None,
        'volume_ratio': mv['ratio'] if mv else None,
        'volume_trend': mv['trend'] if mv else None,
        'volume_level': result.get('volume_level'),
        'volume_pass': bool(result['cond_volume'][0]),
        'emotion': result.get('emotion'),
        'reasons': result.get('reasons', []),
        'saved_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

    # 读取已有历史
    history = []
    if SIGNAL_HISTORY_FILE.exists():
        try:
            with open(SIGNAL_HISTORY_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    history = json.loads(content)
                    if not isinstance(history, list):
                        history = []
        except (json.JSONDecodeError, Exception):
            history = []

    # 按日期去重：同日期覆盖，新日期追加
    date_idx = {entry['date']: i for i, entry in enumerate(history)}
    if result['date'] in date_idx:
        history[date_idx[result['date']]] = record
    else:
        history.append(record)

    # 按日期排序（最新的在最后）
    history.sort(key=lambda x: x['date'])

    # 写入
    SIGNAL_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SIGNAL_HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    print(f"  📝 已存档 → {SIGNAL_HISTORY_FILE.relative_to(project_root)}")


# ==================== CLI ====================

def main():
    parser = argparse.ArgumentParser(
        description="大盘环境信号工具（双指数联合）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python trade_decision/market_signal.py                          # 检查今天
  python trade_decision/market_signal.py --date 2026-04-13        # 指定日期
  python trade_decision/market_signal.py --mode strict            # 严格模式
  python trade_decision/market_signal.py --mode flexible          # 灵活模式
  python trade_decision/market_signal.py --json                   # JSON输出
        """
    )
    parser.add_argument('--date', type=str, help='检查日期 (YYYY-MM-DD)，默认今天')
    parser.add_argument('--mode', type=str, choices=['dual_consensus', 'strict', 'flexible'],
                        help='覆盖配置中的通过模式')
    parser.add_argument('--json', action='store_true', help='以JSON格式输出')

    args = parser.parse_args()
    result = check_market_signal(check_date=args.date, pass_mode=args.mode)

    if args.json:
        print(json.dumps(_serialize_conditions(result), ensure_ascii=False, indent=2))
    else:
        format_output(result)

    save_signal_history(result)


if __name__ == "__main__":
    main()
