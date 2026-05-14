"""
缩量突破选股工具

功能说明:
    根据以下条件筛选股票（缩量整理后的放量突破）:
    1. 前期成交量持续萎缩：近5日平均量 < 过去20日均量 * 0.6
    2. 当日收盘价突破近20日最高价
    3. 当日成交量 > 前一日成交量 * 2 且 > 20日均量 * 1.5
    4. 5日涨跌幅在 3%~18% 区间内

数据来源:
    - 通达信本地数据 (via mootdx): 读取 vipdoc 目录下的 .day 文件

使用方法:
    python selectstock_by_shrinkbreak.py [--shrink-ratio 0.6] [--vol-multiplier-yesterday 2.0] [--vol-multiplier-avg 1.5] [--lookback-days 20]

参数说明:
    --shrink-ratio: 缩量比例阈值，默认0.6（近5日均量/20日均量）
    --vol-multiplier-yesterday: 相对昨日成交量倍数，默认2.0
    --vol-multiplier-avg: 相对20日均量倍数，默认1.5
    --lookback-days: 回看天数（用于最高价突破），默认20
"""

import pandas as pd
import numpy as np
import os
import yaml
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import sys
# 添加项目根目录到Python路径，确保可以导入local模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mootdx.reader import Reader
from local.utils import get_stock_name, calculate_5day_price_change, is_new_stock, calculate_trend_score  # 导入涨跌幅计算函数、新股检测和综合评分函数

# ==================== 配置区 ====================
def load_config():
    """
    加载配置文件
    
    Returns:
        dict: 配置字典
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, '..', 'config.yaml')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"[WARN]  加载配置文件失败: {e}，使用默认配置")
        return {}

config = load_config()
TDX_DIR = config.get('TDX_DIR', r"D:\Install\zd_zxzq_gm")  # 通达信安装目录
DATA_DIR = Path(__file__).parent.parent / "data"  # 选股结果输出目录

# 涨跌幅过滤配置（5日区间）
MIN_PRICE_CHANGE_PCT = config.get('volume_strategy', {}).get('min_price_change_pct', 3.0)   # 最小允许涨跌幅（%）
MAX_PRICE_CHANGE_PCT = config.get('volume_strategy', {}).get('max_price_change_pct', 18.0)  # 最大允许涨跌幅（%）

# 缩量突破策略默认参数（可通过命令行参数覆盖）
DEFAULT_SHRINK_RATIO = 0.6  # 缩量比例阈值
DEFAULT_VOL_MULTIPLIER_YESTERDAY = 2.0  # 相对昨日成交量倍数
DEFAULT_VOL_MULTIPLIER_AVG = 1.5  # 相对20日均量倍数
DEFAULT_LOOKBACK_DAYS = 20  # 回看天数
MIN_LISTING_DAYS = config.get('volume_strategy', {}).get('min_listing_days', 60)  # 最小上市天数，默认60天

def ensure_data_dir():
    """确保data目录存在"""
    if not DATA_DIR.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        print(f"[OK] 创建目录: {DATA_DIR}")

def save_selected_stocks(selected: list):
    """
    将选股结果保存到txt文件
    
    Args:
        selected: 选中的股票列表 [(code, name, score), ...]
    
    Returns:
        bool: 保存是否成功
    """
    if not selected:
        print("[WARN]  没有选中的股票，跳过保存")
        return False
    
    ensure_data_dir()
    
    # 生成文件名：shrinkbreak_YYYYMMDD.txt
    date_str = datetime.now().strftime('%Y%m%d')
    filename = f"shrinkbreak_{date_str}.txt"
    filepath = DATA_DIR / filename
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            # 写入表头注释
            f.write(f"# 缩量突破选股结果 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# 格式: 股票代码,股票名称,综合评分\n")
            f.write(f"# 总数: {len(selected)} 只\n")
            f.write("-" * 40 + "\n")
            
            # 遍历每只股票
            for code, name, score in selected:
                score_str = f"{score:+.1f}" if score is not None else "N/A"
                f.write(f"{code},{name},{score_str}\n")
        
        print(f"\n[SAVE] 选股结果已保存至: {filepath}")
        print(f"[INFO] 共保存 {len(selected)} 只股票")
        return True
        
    except Exception as e:
        print(f"[ERROR] 保存选股结果失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def get_all_stocks_from_local():
    """
    从通达信本地数据文件扫描获取全部A股股票列表
    
    数据来源:
        - 通达信本地文件系统: 扫描 vipdoc/{market}/lday/ 目录下的 .day 文件
        - 优点: 速度极快（本地IO），无需网络连接
        - 缺点: 依赖通达信数据的完整性
    
    过滤规则:
        - 只保留主板(60/00)、创业板(30)、科创板(68)开头的股票
        - 排除北交所(83/87等)和其他市场
    
    Returns:
        list: 股票代码列表（不含市场前缀的6位数字）
    """
    stock_codes = set()
    vipdoc_dir = Path(TDX_DIR) / "vipdoc"
    
    print("[LOAD] 正在扫描本地通达信数据文件...")
    
    # 扫描上海和深圳市场
    for market in ['sh', 'sz']:
        lday_dir = vipdoc_dir / market / "lday"
        
        if not lday_dir.exists():
            print(f"[WARN]  目录不存在: {lday_dir}")
            continue
        
        # 遍历所有 .day 文件
        day_files = list(lday_dir.glob("*.day"))
        
        for day_file in day_files:
            # 文件名格式: {market}{code}.day (如 sh600000.day)
            filename = day_file.stem  # 去掉 .day 扩展名
            
            # 提取6位股票代码（最后6个字符）
            if len(filename) >= 6:
                code = filename[-6:]
                
                # 验证是否为纯数字
                if code.isdigit():
                    # 过滤规则: 只保留 00/30/60/68 开头的股票
                    if code.startswith(('00', '30', '60', '68')):
                        stock_codes.add(code)
    
    # 转换为排序列表
    stock_list = sorted(list(stock_codes))
    
    print(f"[OK] 从本地文件扫描到 {len(stock_list)} 只A股股票")
    
    return stock_list

def get_all_stocks_from_tdx():
    """
    获取全部A股股票列表
    
    Returns:
        DataFrame: 包含 code（代码）和 name（名称）的股票列表
    """
    try:
        import akshare as ak
        stock_info = ak.stock_info_a_code_name()
        
        # 过滤规则: 只保留主板(60/00)、创业板(30)、科创板(68)
        stock_info = stock_info[stock_info['code'].str.match(r'^(00|30|60|68)')]
        
        print(f"[OK] 成功获取 {len(stock_info)} 只A股股票列表")
        return stock_info
        
    except Exception as e:
        print(f"[ERROR] 获取股票列表失败: {e}")
        return pd.DataFrame()

def is_st_or_terminated(stock_name):
    """
    判断是否为ST或退市股
    
    Args:
        stock_name: 股票名称
    
    Returns:
        bool: True表示是ST或退市股，需要剔除
    """
    if not stock_name:
        return False
    
    if 'ST' in stock_name or '*ST' in stock_name or '退' in stock_name:
        return True
    
    return False

def is_suspended(reader, stock_code):
    """
    判断股票是否停牌
    
    Args:
        reader: mootdx Reader实例
        stock_code: 股票代码（不含市场前缀）
    
    Returns:
        bool: True表示股票停牌，需要剔除
    """
    try:
        df = reader.daily(symbol=stock_code)
        
        if df is None or df.empty:
            return False
        
        latest_volume = df['volume'].iloc[-1]
        
        if latest_volume == 0:
            return True
        
        return False
        
    except Exception as e:
        return False

def check_shrink_breakout_conditions(reader, stock_code, shrink_ratio=0.6, vol_multiplier_yesterday=2.0, vol_multiplier_avg=1.5, lookback_days=20):
    """
    检查单只股票是否满足缩量突破条件
    
    核心逻辑:
        1. 计算近5日均量和20日均量，检查是否缩量
        2. 检查收盘价是否突破近20日最高价
        3. 检查成交量是否显著放大
    
    Args:
        reader: mootdx Reader实例
        stock_code: 股票代码（不含市场前缀）
        shrink_ratio: 缩量比例阈值（近5日均量/20日均量）
        vol_multiplier_yesterday: 相对昨日成交量倍数
        vol_multiplier_avg: 相对20日均量倍数
        lookback_days: 回看天数（用于最高价突破）
    
    Returns:
        tuple: (bool, dict) - 是否满足条件, 详细指标信息
    """
    try:
        # 读取日线数据
        df = reader.daily(symbol=stock_code)
        
        if df is None or df.empty:
            return False, {}
        
        # 数据处理: 确保时间序列有序
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        
        # 边界检查: 至少需要 lookback_days + 5 个交易日数据
        required_days = max(lookback_days, 20) + 5
        if len(df) < required_days:
            return False, {}
        
        # 提取最新数据
        latest = df.iloc[-1]
        close = latest['close']
        volume = latest['volume']
        
        # 前一日数据
        prev_day = df.iloc[-2]
        prev_volume = prev_day['volume']
        
        # 条件1: 成交量持续萎缩
        # 计算近5日平均成交量
        avg_vol_5 = df['volume'].iloc[-5:].mean()
        
        # 计算近20日平均成交量
        avg_vol_20 = df['volume'].iloc[-20:].mean()
        
        if avg_vol_20 == 0:
            return False, {}
        
        # 检查缩量比例
        current_shrink_ratio = avg_vol_5 / avg_vol_20
        if current_shrink_ratio >= shrink_ratio:
            return False, {}
        
        # 条件2: 收盘价突破近20日最高价
        # 获取近20日的最高价（不包括今天）
        recent_high = df['high'].iloc[-lookback_days-1:-1].max()
        
        if close <= recent_high:
            return False, {}
        
        # 条件3: 成交量显著放大
        # 检查1: 当日成交量 > 前一日成交量 * 倍数
        if prev_volume == 0:
            return False, {}
        
        vol_vs_yesterday = volume / prev_volume
        if vol_vs_yesterday < vol_multiplier_yesterday:
            return False, {}
        
        # 检查2: 当日成交量 > 20日均量 * 倍数
        vol_vs_avg = volume / avg_vol_20
        if vol_vs_avg < vol_multiplier_avg:
            return False, {}
        
        # 所有条件满足，返回详细信息
        info = {
            'avg_vol_5': avg_vol_5,
            'avg_vol_20': avg_vol_20,
            'shrink_ratio': current_shrink_ratio,
            'recent_high': recent_high,
            'close': close,
            'volume': volume,
            'prev_volume': prev_volume,
            'vol_vs_yesterday': vol_vs_yesterday,
            'vol_vs_avg': vol_vs_avg,
            'breakout_amount': close - recent_high
        }
        
        return True, info
        
    except Exception as e:
        # 静默处理错误
        return False, {}

def main(shrink_ratio=0.6, vol_multiplier_yesterday=2.0, vol_multiplier_avg=1.5, lookback_days=20):
    """
    主函数：执行缩量突破选股策略
    
    Args:
        shrink_ratio: 缩量比例阈值
        vol_multiplier_yesterday: 相对昨日成交量倍数
        vol_multiplier_avg: 相对20日均量倍数
        lookback_days: 回看天数
    """
    print("=" * 60)
    print("[INFO] 缩量突破选股工具")
    print("=" * 60)
    print(f"[INFO] 选股条件:")
    print(f"   1. 成交量萎缩: 近5日均量 < 20日均量 * {shrink_ratio}")
    print(f"   2. 价格突破: 收盘价 > 近{lookback_days}日最高价")
    print(f"   3. 成交量放大: 当日量 > 昨日量 * {vol_multiplier_yesterday} 且 > 20日均量 * {vol_multiplier_avg}")
    print(f"   4. 5日涨跌幅区间: {MIN_PRICE_CHANGE_PCT}% ~ {MAX_PRICE_CHANGE_PCT}%")
    print("=" * 60)
    
    # 初始化 mootdx Reader
    try:
        reader = Reader.factory(market='std', tdxdir=TDX_DIR)
        print(f"[OK] 成功初始化 mootdx Reader (通达信目录: {TDX_DIR})")
    except Exception as e:
        print(f"[ERROR] 初始化 mootdx Reader 失败: {e}")
        print(f"[TIP] 请检查 TDX_DIR 配置是否正确")
        return
    
    # ========== 新增：加载白名单 ==========
    from local.utils import load_whitelist
    
    whitelist = load_whitelist()
    
    if not whitelist:
        print("[WARN] 白名单未生成，将使用传统方式扫描")
        print("[TIP] 建议先运行: python local/manage_stock_list.py --update\n")
        # 降级到原有逻辑
        stock_codes = get_all_stocks_from_local()
        use_whitelist = False
    else:
        stock_codes = list(whitelist)
        use_whitelist = True
        print(f"[OK] 使用白名单快速筛选，共 {len(stock_codes)} 只候选股票\n")
    # ======================================
    
    if not stock_codes:
        print("[ERROR] 无法获取股票列表，程序退出")
        return
    
    # 存储选中的股票（第一阶段仅保存代码）
    selected_codes = []
    total_count = len(stock_codes)
    processed_count = 0
    
    print(f"\n[SCAN] 开始扫描 {total_count} 只股票...\n")
    
    # 第一阶段：极速筛选（仅使用股票代码 + 本地技术指标）
    for idx, stock_code in enumerate(stock_codes):
        processed_count += 1
        
        # 进度显示（每100只股票显示一次）
        if processed_count % 100 == 0:
            print(f"[PROGRESS] 已处理: {processed_count}/{total_count}, 选中: {len(selected_codes)}")
        
        # 如果使用白名单，跳过ST检测
        if not use_whitelist:
            # 预处理: 剔除ST/退市股（需要名称）
            stock_name = get_stock_name(stock_code)
            if is_st_or_terminated(stock_name):
                continue
            
            # 检查是否停牌
            if is_suspended(reader, stock_code):
                continue
        
        # 确定市场前缀
        if stock_code.startswith('6') or stock_code.startswith('9'):
            market_prefix = 'sh'
        else:
            market_prefix = 'sz'
        
        # 核心逻辑: 检查缩量突破条件（纯本地数据，速度极快）
        is_match, info = check_shrink_breakout_conditions(
            reader, 
            stock_code, 
            shrink_ratio=shrink_ratio,
            vol_multiplier_yesterday=vol_multiplier_yesterday,
            vol_multiplier_avg=vol_multiplier_avg,
            lookback_days=lookback_days
        )
        
        if is_match:
            selected_codes.append((stock_code, market_prefix))  # 保存代码和市场前缀
    
    print(f"\n[PHASE1] 第一阶段筛选完成，候选股票: {len(selected_codes)} 只")
    
    # 第二阶段：结果增强（仅对选中的股票执行高成本操作）
    selected_stocks = []
    filtered_new_stock_count = 0
    
    if selected_codes:
        print(f"\n[PHASE2] 开始第二阶段：获取名称 + 新股检测 + 涨跌幅过滤...\n")
        
        # 2.1 批量获取候选股票的名称
        print("[LOAD] 正在获取候选股票名称...")
        stock_name_cache = {}
        for code, _ in selected_codes:
            stock_name_cache[code] = get_stock_name(code)
        print(f"[OK] 名称获取完成\n")
        
        # 2.2 对每个候选股票进行新股检测和涨跌幅过滤
        for stock_code, market_prefix in selected_codes:
            stock_name = stock_name_cache.get(stock_code, stock_code)
            
            # 1. 新股检测（仅对候选股票执行）
            if is_new_stock(stock_code, MIN_LISTING_DAYS):
                filtered_new_stock_count += 1
                print(f"[FILTER] {stock_code} {stock_name} - 新股（上市不足{MIN_LISTING_DAYS}天）")
                continue
            
            # 2. 计算综合评分
            score = calculate_trend_score(market_prefix, stock_code)
            
            selected_stocks.append((stock_code, stock_name, score))
            
            # 打印详细信息
            print(f"\n[SELECTED] {stock_code} ({stock_name})")
            if score is not None:
                print(f"   综合评分: {score:+.1f}")
    
    print(f"\n[PHASE2] 第二阶段筛选完成")
    print(f"[FILTER] 过滤新股: {filtered_new_stock_count} 只")
    print(f"[RESULT] 最终选股结果: {len(selected_stocks)} 只")
    
    # 输出最终结果
    print("\n" + "=" * 60)
    print(f"[INFO] 选股完成！共选中 {len(selected_stocks)} 只股票")
    print("=" * 60)
    
    if selected_stocks:
        # 第四阶段：5日涨跌幅过滤（按交易日计算）
        final_selected = []
        filtered_low_change_count = 0
        filtered_high_change_count = 0
        
        print(f"\n[PHASE4] 开始第四阶段筛选：5日涨跌幅过滤（{MIN_PRICE_CHANGE_PCT}% ~ {MAX_PRICE_CHANGE_PCT}）...\n")
        
        for idx, (code, name, score) in enumerate(selected_stocks, 1):
            # 确定市场前缀
            if code.startswith('6') or code.startswith('9'):
                market = 'sh'
            else:
                market = 'sz'
            
            # 计算5日涨跌幅（按交易日，使用起始日开盘价和结束日收盘价）
            change_pct = calculate_5day_price_change(market, code)
            
            if change_pct is None:
                # 计算失败，保守起见保留该股票
                final_selected.append((code, name, score))
                print(f"[KEEP] {code} {name} (5日涨跌幅计算失败，保留)")
                continue
            
            # 检查是否在目标区间内
            if change_pct < MIN_PRICE_CHANGE_PCT:
                filtered_low_change_count += 1
                print(f"[FILTER] {code} {name} - 5日涨跌幅 {change_pct:+.2f}% < {MIN_PRICE_CHANGE_PCT}%")
                continue
            
            if change_pct > MAX_PRICE_CHANGE_PCT:
                filtered_high_change_count += 1
                print(f"[FILTER] {code} {name} - 5日涨跌幅 {change_pct:+.2f}% > {MAX_PRICE_CHANGE_PCT}%")
                continue
            
            final_selected.append((code, name, score))
            print(f"[KEEP] {code} {name} - 5日涨跌幅 {change_pct:+.2f}%")
        
        print(f"\n[PHASE4] 第四阶段筛选完成")
        print(f"[FILTER] 过滤涨跌幅过低: {filtered_low_change_count} 只")
        print(f"[FILTER] 过滤涨跌幅过高: {filtered_high_change_count} 只")
        print(f"[RESULT] 最终选股结果: {len(final_selected)} 只")
        
        # 保存最终结果
        save_selected_stocks(final_selected)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="缩量突破选股工具")
    parser.add_argument('--shrink-ratio', type=float, default=DEFAULT_SHRINK_RATIO, help='缩量比例阈值（近5日均量/20日均量）')
    parser.add_argument('--vol-multiplier-yesterday', type=float, default=DEFAULT_VOL_MULTIPLIER_YESTERDAY, help='相对昨日成交量倍数')
    parser.add_argument('--vol-multiplier-avg', type=float, default=DEFAULT_VOL_MULTIPLIER_AVG, help='相对20日均量倍数')
    parser.add_argument('--lookback-days', type=int, default=DEFAULT_LOOKBACK_DAYS, help='回看天数（用于最高价突破）')
    args = parser.parse_args()
    
    main(
        shrink_ratio=args.shrink_ratio,
        vol_multiplier_yesterday=args.vol_multiplier_yesterday,
        vol_multiplier_avg=args.vol_multiplier_avg,
        lookback_days=args.lookback_days
    )
