# -*- coding: utf-8 -*-
"""验证简化后的BOLL输出格式 - 真实数据测试"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.strategy.engine import get_strategy_engine
from src.market.data_provider import get_market_data


def test_simplified_boll_format():
    """测试简化后的BOLL输出格式（使用真实数据）"""
    print("\n" + "="*70)
    print("BOLL三轨简化格式验证 - 真实数据测试")
    print("="*70)
    
    engine = get_strategy_engine()
    symbols = ["sh.513120", "sh.513050"]
    
    for symbol in symbols:
        print(f"\n{'='*70}")
        print(f"标的: {symbol}")
        print(f"{'='*70}")
        
        # 获取市场数据
        market_data = get_market_data(symbol)
        if not market_data:
            print("❌ 无法获取市场数据")
            continue
        
        print(f"\n📊 基础数据:")
        print(f"   名称: {market_data.name}")
        print(f"   当前价格: ¥{market_data.current_price:.3f}")
        print(f"   BOLL上轨: ¥{market_data.boll_up:.3f}")
        print(f"   BOLL中轨: ¥{market_data.boll_middle:.3f}")
        print(f"   BOLL下轨: ¥{market_data.boll_down:.3f}")
        
        # 生成信号
        signal = engine.analyze(symbol)
        if not signal:
            print("❌ 未生成信号")
            continue
        
        print(f"\n🎯 交易信号:")
        print(f"   信号类型: {signal.signal_type.value}")
        print(f"   信号价格: ¥{signal.price:.3f}")
        
        # 显示简化格式的BOLL信息
        if all([signal.boll_up_diff_pct is not None, 
                signal.boll_middle_diff_pct is not None, 
                signal.boll_down_diff_pct is not None]):
            
            # 计算各轨道价差的绝对值
            up_abs = abs(signal.boll_up_diff_pct)
            middle_abs = abs(signal.boll_middle_diff_pct)
            down_abs = abs(signal.boll_down_diff_pct)
            
            # 找出最近的轨道
            min_diff = min(up_abs, middle_abs, down_abs)
            closest_track = ""
            if min_diff == up_abs:
                closest_track = "上轨"
            elif min_diff == middle_abs:
                closest_track = "中轨"
            else:
                closest_track = "下轨"
            
            # 构建简化的BOLL信息显示
            up_marker = " <- 此轨最近" if closest_track == "上轨" else ""
            middle_marker = " <- 此轨最近" if closest_track == "中轨" else ""
            down_marker = " <- 此轨最近" if closest_track == "下轨" else ""
            
            boll_info = f"BOLL上轨{signal.boll_up_diff_pct:+.2f}%{up_marker} | 中轨{signal.boll_middle_diff_pct:+.2f}%{middle_marker} | 下轨{signal.boll_down_diff_pct:+.2f}%{down_marker}"
            
            print(f"\n✅ 简化格式输出:")
            print(f"   {boll_info}")
            
            # 验证计算正确性
            print(f"\n🔍 计算验证:")
            expected_up = ((signal.price / market_data.boll_up) - 1) * 100
            expected_middle = ((signal.price / market_data.boll_middle) - 1) * 100
            expected_down = ((signal.price / market_data.boll_down) - 1) * 100
            
            print(f"   上轨价差: {expected_up:+.2f}% (实际: {signal.boll_up_diff_pct:+.2f}%) {'✓' if abs(expected_up - signal.boll_up_diff_pct) < 0.01 else '✗'}")
            print(f"   中轨价差: {expected_middle:+.2f}% (实际: {signal.boll_middle_diff_pct:+.2f}%) {'✓' if abs(expected_middle - signal.boll_middle_diff_pct) < 0.01 else '✗'}")
            print(f"   下轨价差: {expected_down:+.2f}% (实际: {signal.boll_down_diff_pct:+.2f}%) {'✓' if abs(expected_down - signal.boll_down_diff_pct) < 0.01 else '✗'}")
            print(f"   最近轨道: {closest_track} (差值: {min_diff:.2f}%)")
        else:
            print("❌ BOLL价差数据不完整")
    
    print(f"\n{'='*70}")
    print("✅ 测试完成 - 所有数据均为实时计算")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    test_simplified_boll_format()
