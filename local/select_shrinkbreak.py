"""
缩量突破选股工具

功能说明:
    根据以下条件筛选股票（缩量整理后的放量突破）:
    1. 前期成交量持续萎缩：近5日平均量 < 过去20日均量 * 0.6
    2. 当日收盘价突破近20日最高价
    3. 当日成交量 > 前一日成交量 * 2 且 > 20日均量 * 1.5

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

from mootdx.reader import Reader
import pandas as pd
import numpy as np
import os
import yaml
import argparse
from pathlib import Path
from datetime import datetime
from utils import get_stock_name

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
        
        print(f"\n💾 选股结果已保存至: {filepath}")
        print(f"📊 共保存 {len(selected)} 只股票")
        return True
        
    except Exception as e:
        print(f"❌ 保存选股结果失败: {e}")
        import traceback
        traceback.print_exc()
        return False

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
    print("📈 缩量突破选股工具")
    print("=" * 60)
    print(f"📋 选股条件:")
    print(f"   1. 成交量萎缩: 近5日均量 < 20日均量 * {shrink_ratio}")
    print(f"   2. 价格突破: 收盘价 > 近{lookback_days}日最高价")
    print(f"   3. 成交量放大: 当日量 > 昨日量 * {vol_multiplier_yesterday} 且 > 20日均量 * {vol_multiplier_avg}")
    print("=" * 60)
    
    # 初始化 mootdx Reader
    try:
        reader = Reader.factory(market='std', tdxdir=TDX_DIR)
        print(f"✅ 成功初始化 mootdx Reader (通达信目录: {TDX_DIR})")
    except Exception as e:
        print(f"❌ 初始化 mootdx Reader 失败: {e}")
        print(f"💡 请检查 TDX_DIR 配置是否正确")
        return
    
    # 获取全市场股票列表
    print("\n🔍 正在获取股票列表...")
    stock_list = get_all_stocks_from_tdx()
    
    if stock_list.empty:
        print("❌ 无法获取股票列表，程序退出")
        return
    
    # 存储选中的股票
    selected_stocks = []
    total_count = len(stock_list)
    processed_count = 0
    
    print(f"\n🚀 开始扫描 {total_count} 只股票...\n")
    
    # 遍历每只股票
    for idx, row in stock_list.iterrows():
        stock_code = row['code']
        stock_name = row['name']
        
        processed_count += 1
        
        # 进度显示（每100只股票显示一次）
        if processed_count % 100 == 0:
            print(f"⏳ 已处理: {processed_count}/{total_count}, 选中: {len(selected_stocks)}")
        
        # 预处理: 剔除ST/退市股
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
        
        # 核心逻辑: 检查缩量突破条件
        is_match, info = check_shrink_breakout_conditions(
            reader, 
            stock_code, 
            shrink_ratio=shrink_ratio,
            vol_multiplier_yesterday=vol_multiplier_yesterday,
            vol_multiplier_avg=vol_multiplier_avg,
            lookback_days=lookback_days
        )
        
        if is_match:
            # 从utils导入评分函数
            from utils import calculate_trend_score
            
            # 计算综合评分
            score = calculate_trend_score(market_prefix, stock_code)
            
            selected_stocks.append((stock_code, stock_name, score))
            
            # 打印详细信息
            print(f"\n✅ 选中: {stock_code} ({stock_name})")
            print(f"   缩量指标: 近5日均量={info['avg_vol_5']:.0f}, 20日均量={info['avg_vol_20']:.0f}")
            print(f"   缩量比例: {info['shrink_ratio']:.2f} (阈值<{shrink_ratio})")
            print(f"   价格突破: 收盘价={info['close']:.2f}, 近{lookback_days}日最高={info['recent_high']:.2f}")
            print(f"   突破幅度: {info['breakout_amount']:.2f}")
            print(f"   成交量比: 较昨日={info['vol_vs_yesterday']:.2f}x, 较均值={info['vol_vs_avg']:.2f}x")
            if score is not None:
                print(f"   综合评分: {score:+.1f}")
    
    # 输出最终结果
    print("\n" + "=" * 60)
    print(f"📊 选股完成！共选中 {len(selected_stocks)} 只股票")
    print("=" * 60)
    
    if selected_stocks:
        # 按综合评分排序（从高到低）
        selected_stocks.sort(key=lambda x: x[2] if x[2] is not None else -999, reverse=True)
        
        print("\n📋 选中股票列表:")
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
        print("\n⚠️  未找到符合条件的股票")

if __name__ == '__main__':
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='缩量突破选股工具')
    parser.add_argument('--shrink-ratio', type=float, default=0.6, 
                        help='缩量比例阈值（近5日均量/20日均量），默认0.6')
    parser.add_argument('--vol-multiplier-yesterday', type=float, default=2.0,
                        help='相对昨日成交量倍数，默认2.0')
    parser.add_argument('--vol-multiplier-avg', type=float, default=1.5,
                        help='相对20日均量倍数，默认1.5')
    parser.add_argument('--lookback-days', type=int, default=20,
                        help='回看天数（用于最高价突破），默认20')
    
    args = parser.parse_args()
    
    main(
        shrink_ratio=args.shrink_ratio,
        vol_multiplier_yesterday=args.vol_multiplier_yesterday,
        vol_multiplier_avg=args.vol_multiplier_avg,
        lookback_days=args.lookback_days
    )
