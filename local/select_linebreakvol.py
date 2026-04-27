"""
均线突破选股工具

功能说明:
    根据以下条件筛选股票（均线粘合后的放量突破）:
    1. 短期均线(5/10/20)与长期均线(60)最大与最小值的差距 < 阈值(默认2%)
    2. 当日收盘价同时突破所有均线(>MA5, >MA10, >MA20, >MA60)
    3. 成交量 > 20日均量 * 1.8 (放量)
    4. 涨幅适中(1%~7%)，实体阳线(收盘价>开盘价)
    5. 5日涨跌幅在 3%~18% 区间内

数据来源:
    - 通达信本地数据 (via mootdx): 读取 vipdoc 目录下的 .day 文件

使用方法:
    python selectstock_by_breakout.py [--threshold 2.0] [--min-return 1.0] [--max-return 7.0] [--volume-ratio 1.8]

参数说明:
    --threshold: 均线收敛阈值(百分比)，默认2.0
    --min-return: 最小涨幅(百分比)，默认1.0
    --max-return: 最大涨幅(百分比)，默认7.0
    --volume-ratio: 成交量倍数，默认1.8
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

from local.utils import get_stock_name, calculate_trend_score, calculate_5day_price_change, is_new_stock  # 导入涨跌幅计算函数和新股检测函数

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
        print(f"⚠️  加载配置文件失败: {e}，使用默认配置")
        return {}

config = load_config()
TDX_DIR = config.get('TDX_DIR', r"D:\Install\zd_zxzq_gm")  # 通达信安装目录
DATA_DIR = Path(__file__).parent.parent / "data"  # 选股结果输出目录

# 涨跌幅过滤配置（5日区间）
MIN_PRICE_CHANGE_PCT = config.get('volume_strategy', {}).get('min_price_change_pct', 3.0)   # 最小允许涨跌幅（%）
MAX_PRICE_CHANGE_PCT = config.get('volume_strategy', {}).get('max_price_change_pct', 18.0)  # 最大允许涨跌幅（%）

# 新股过滤配置
MIN_LISTING_DAYS = config.get('linebreak_vol_strategy', {}).get('min_listing_days', 365)  # 最小上市天数，默认365天（1年）

# 均线突破策略默认参数（可通过命令行参数覆盖）
DEFAULT_THRESHOLD = config.get('linebreak_vol_strategy', {}).get('threshold', 2.0)  # 均线收敛阈值
DEFAULT_MIN_RETURN = config.get('linebreak_vol_strategy', {}).get('min_return', 1.0)  # 最小涨幅
DEFAULT_MAX_RETURN = config.get('linebreak_vol_strategy', {}).get('max_return', 7.0)  # 最大涨幅
DEFAULT_VOLUME_RATIO = config.get('linebreak_vol_strategy', {}).get('volume_ratio', 1.8)  # 成交量倍数

def ensure_data_dir():
    """确保data目录存在"""
    if not DATA_DIR.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        print(f"✅ 创建目录: {DATA_DIR}")

def save_selected_stocks(selected: list):
    """
    将选股结果保存到txt文件
    
    Args:
        selected: 选中的股票列表 [(code, name, score), ...]
    
    Returns:
        bool: 保存是否成功
    """
    if not selected:
        print("⚠️  没有选中的股票，跳过保存")
        return False
    
    ensure_data_dir()
    
    # 生成文件名：breakout_YYYYMMDD.txt
    date_str = datetime.now().strftime('%Y%m%d')
    filename = f"breakout_{date_str}.txt"
    filepath = DATA_DIR / filename
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            # 写入表头注释
            f.write(f"# 均线突破选股结果 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# 格式: 股票代码,股票名称,综合评分\n")
            f.write(f"# 总数: {len(selected)} 只\n")
            f.write("-" * 40 + "\n")
            
            # 遍历每只股票
            for code, name, score in selected:
                score_str = f"{score:+.1f}" if score is not None else "N/A"
                f.write(f"{code},{name},{score_str}\n")
        
        print(f"\n💾 选股结果已保存至: {filepath}")
        print(f"📊 共保存 {len(selected)} 只股票")
        return True
        
    except Exception as e:
        print(f"❌ 保存选股结果失败: {e}")
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
        
        print(f"✅ 成功获取 {len(stock_info)} 只A股股票列表")
        return stock_info
        
    except Exception as e:
        print(f"❌ 获取股票列表失败: {e}")
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

def check_breakout_conditions(reader, stock_code, threshold=2.0, min_return=1.0, max_return=7.0, volume_ratio=1.8):
    """
    检查单只股票是否满足均线突破条件
    
    核心逻辑:
        1. 计算MA5, MA10, MA20, MA60
        2. 检查短期均线与长期均线的收敛程度
        3. 检查收盘价是否突破所有均线
        4. 检查成交量是否放大
        5. 检查涨幅和K线形态
    
    Args:
        reader: mootdx Reader实例
        stock_code: 股票代码（不含市场前缀）
        threshold: 均线收敛阈值(百分比)
        min_return: 最小涨幅(百分比)
        max_return: 最大涨幅(百分比)
        volume_ratio: 成交量倍数
    
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
        
        # 边界检查: 至少需要60个交易日数据
        if len(df) < 60:
            return False, {}
        
        # 提取最新数据
        latest = df.iloc[-1]
        close = latest['close']
        open_price = latest['open']
        high = latest['high']
        low = latest['low']
        volume = latest['volume']
        
        # 计算均线
        ma5 = df['close'].rolling(window=5).mean().iloc[-1]
        ma10 = df['close'].rolling(window=10).mean().iloc[-1]
        ma20 = df['close'].rolling(window=20).mean().iloc[-1]
        ma60 = df['close'].rolling(window=60).mean().iloc[-1]
        
        # 计算20日均量
        avg_volume_20 = df['volume'].rolling(window=20).mean().iloc[-1]
        
        # 条件1: 短期均线与长期均线的收敛程度
        # 计算MA5, MA10, MA20, MA60的最大值和最小值
        mas = [ma5, ma10, ma20, ma60]
        max_ma = max(mas)
        min_ma = min(mas)
        
        # 计算差距百分比
        if min_ma == 0:
            return False, {}
        
        ma_gap_pct = ((max_ma - min_ma) / min_ma) * 100
        
        # 检查是否小于阈值
        if ma_gap_pct >= threshold:
            return False, {}
        
        # 条件2: 收盘价突破所有均线
        if not (close > ma5 and close > ma10 and close > ma20 and close > ma60):
            return False, {}
        
        # 条件3: 成交量放大
        if avg_volume_20 == 0:
            return False, {}
        
        vol_ratio = volume / avg_volume_20
        if vol_ratio < volume_ratio:
            return False, {}
        
        # 条件4: 涨幅适中且为实体阳线
        # 计算涨跌幅（相对于昨日收盘）
        prev_close = df['close'].iloc[-2]
        if prev_close == 0:
            return False, {}
        
        return_pct = ((close - prev_close) / prev_close) * 100
        
        # 检查涨幅范围
        if return_pct < min_return or return_pct > max_return:
            return False, {}
        
        # 检查是否为阳线（收盘价 > 开盘价）
        if close <= open_price:
            return False, {}
        
        # 计算实体长度占比（排除长上下影线）
        body_length = abs(close - open_price)
        total_range = high - low
        
        if total_range == 0:
            return False, {}
        
        body_ratio = body_length / total_range
        
        # 实体占比应大于50%，确保是实体阳线而非十字星
        if body_ratio < 0.5:
            return False, {}
        
        # 所有条件满足，返回详细信息
        info = {
            'ma5': ma5,
            'ma10': ma10,
            'ma20': ma20,
            'ma60': ma60,
            'ma_gap_pct': ma_gap_pct,
            'close': close,
            'volume': volume,
            'avg_volume_20': avg_volume_20,
            'vol_ratio': vol_ratio,
            'return_pct': return_pct,
            'body_ratio': body_ratio
        }
        
        return True, info
        
    except Exception as e:
        # 静默处理错误
        return False, {}

def main(threshold=2.0, min_return=1.0, max_return=7.0, volume_ratio=1.8):
    """
    主函数：执行均线突破选股策略
    
    Args:
        threshold: 均线收敛阈值(百分比)
        min_return: 最小涨幅(百分比)
        max_return: 最大涨幅(百分比)
        volume_ratio: 成交量倍数
    """
    print("=" * 60)
    print("📈 均线突破选股工具")
    print("=" * 60)
    print(f"📋 选股条件:")
    print(f"   1. 均线收敛: MA5/10/20/60 最大最小差距 < {threshold}%")
    print(f"   2. 价格突破: 收盘价 > 所有均线")
    print(f"   3. 成交量放大: 成交量 > 20日均量 * {volume_ratio}")
    print(f"   4. 涨幅范围: {min_return}% ~ {max_return}%，实体阳线")
    print(f"   5. 5日涨跌幅区间: {MIN_PRICE_CHANGE_PCT}% ~ {MAX_PRICE_CHANGE_PCT}%")
    print("=" * 60)
    
    # 初始化 mootdx Reader
    try:
        from mootdx.reader import Reader
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
        
        # 如果使用白名单，跳过ST和停牌检测
        if not use_whitelist:
            # 预处理: 剔除ST/退市股（需要名称）
            stock_name = get_stock_name(stock_code)
            if is_st_or_terminated(stock_name):
                continue
            
            # 确定市场前缀
            if stock_code.startswith('6') or stock_code.startswith('9'):
                market_prefix = 'sh'
            else:
                market_prefix = 'sz'
            
            # 检查是否停牌
            if is_suspended(reader, stock_code):
                continue
        else:
            # 确定市场前缀（使用白名单时仍需要）
            if stock_code.startswith('6') or stock_code.startswith('9'):
                market_prefix = 'sh'
            else:
                market_prefix = 'sz'
        
        # 核心逻辑: 检查均线突破条件（纯本地数据，速度极快）
        is_match, info = check_breakout_conditions(
            reader, 
            stock_code, 
            threshold=threshold,
            min_return=min_return,
            max_return=max_return,
            volume_ratio=volume_ratio
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
            
            # 2. 计算5日涨跌幅
            change_pct = calculate_5day_price_change(market_prefix, stock_code)
            
            if change_pct is None:
                # 计算失败，保守保留
                score = calculate_trend_score(market_prefix, stock_code)
                selected_stocks.append((stock_code, stock_name, score))
                print(f"[KEEP] {stock_code} {stock_name} (5日涨跌幅计算失败，保留)")
                continue
            
            # 检查是否在目标区间内
            if change_pct < MIN_PRICE_CHANGE_PCT or change_pct > MAX_PRICE_CHANGE_PCT:
                print(f"[FILTER] {stock_code} {stock_name} - 5日涨跌幅: {change_pct:+.2f}% (超出区间)")
                continue
            
            # 符合条件，计算评分
            score = calculate_trend_score(market_prefix, stock_code)
            selected_stocks.append((stock_code, stock_name, score))
            print(f"[SELECTED] {stock_code} {stock_name} - 5日涨跌幅: {change_pct:+.2f}%")
    
    print(f"\n[PHASE2] 第二阶段筛选完成")
    print(f"[FILTER] 过滤新股: {filtered_new_stock_count} 只")
    print(f"[RESULT] 最终选股结果: {len(selected_stocks)} 只")
    
    # 输出最终结果
    if selected_stocks:
        # 按综合评分排序（从高到低）
        selected_stocks.sort(key=lambda x: x[2] if x[2] is not None else -999, reverse=True)
        
        print("\n" + "=" * 60)
        print("选中股票列表:")
        print("-" * 60)
        print(f"{'代码':<10} {'名称':<10} {'评分':<8}")
        print("-" * 60)
        for code, name, score in selected_stocks:
            score_str = f"{score:+.1f}" if score is not None else "N/A"
            print(f"{code:<10} {name:<10} {score_str:<8}")
        print("-" * 60)
        
        # 保存结果
        save_selected_stocks(selected_stocks)
    else:
        print("\n" + "=" * 60)
        print("未找到符合条件的股票")
        print("=" * 60)


if __name__ == "__main__":
    """
    主入口：执行均线突破选股策略
    
    使用方法:
        python select_linebreakvol.py [--threshold 2.0] [--min-return 1.0] [--max-return 7.0] [--volume-ratio 1.8]
    
    参数说明:
        --threshold: 均线收敛阈值(百分比)，默认2.0
        --min-return: 最小涨幅(百分比)，默认1.0
        --max-return: 最大涨幅(百分比)，默认7.0
        --volume-ratio: 成交量倍数，默认1.8
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="均线突破选股工具")
    parser.add_argument('--threshold', type=float, default=DEFAULT_THRESHOLD, help='均线收敛阈值(百分比)')
    parser.add_argument('--min-return', type=float, default=DEFAULT_MIN_RETURN, help='最小涨幅(百分比)')
    parser.add_argument('--max-return', type=float, default=DEFAULT_MAX_RETURN, help='最大涨幅(百分比)')
    parser.add_argument('--volume-ratio', type=float, default=DEFAULT_VOLUME_RATIO, help='成交量倍数')
    args = parser.parse_args()
    
    main(
        threshold=args.threshold,
        min_return=args.min_return,
        max_return=args.max_return,
        volume_ratio=args.volume_ratio
    )
