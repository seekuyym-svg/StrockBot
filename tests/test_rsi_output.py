# -*- coding: utf-8 -*-
"""验证RSI指标输出功能"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.strategy.engine import get_strategy_engine
from src.market.data_provider import get_market_data


def test_rsi_output():
    """测试RSI指标的输出和判断"""
    print("\n" + "="*70)
    print("测试RSI指标输出功能")
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
        print(f"   RSI值: {market_data.rsi if market_data.rsi else 'N/A'}")
        
        # 生成信号
        signal = engine.analyze(symbol)
        if not signal:
            print("❌ 未生成信号")
            continue
        
        print(f"\n🎯 交易信号:")
        print(f"   信号类型: {signal.signal_type.value}")
        print(f"   信号价格: ¥{signal.price:.3f}")
        
        # 显示RSI信息
        if signal.rsi is not None:
            rsi_value = signal.rsi
            # 判断RSI区域
            if rsi_value > 70:
                rsi_zone = "超买区 ⚠️"
                rsi_emoji = "🔴"
            elif rsi_value >= 30:
                rsi_zone = "中性区"
                rsi_emoji = "🟡"
            else:
                rsi_zone = "超卖区 ✅"
                rsi_emoji = "🟢"
            
            print(f"\n✅ RSI指标:")
            print(f"   📈 RSI: {rsi_value:.2f} ({rsi_emoji} {rsi_zone})")
            
            # 提供交易建议
            if rsi_value > 70:
                print(f"   💡 提示: 市场可能过热，注意回调风险")
            elif rsi_value < 30:
                print(f"   💡 提示: 市场可能超跌，关注反弹机会")
            else:
                print(f"   💡 提示: 市场处于正常波动范围")
        else:
            print(f"\n⚠️ RSI数据不可用")
        
        # 显示BOLL信息（如果存在）
        if all([signal.boll_up_diff_pct is not None, 
                signal.boll_middle_diff_pct is not None, 
                signal.boll_down_diff_pct is not None]):
            
            up_abs = abs(signal.boll_up_diff_pct)
            middle_abs = abs(signal.boll_middle_diff_pct)
            down_abs = abs(signal.boll_down_diff_pct)
            
            min_diff = min(up_abs, middle_abs, down_abs)
            if min_diff == up_abs:
                closest_track = "上轨"
            elif min_diff == middle_abs:
                closest_track = "中轨"
            else:
                closest_track = "下轨"
            
            up_marker = " ← 此轨最近" if closest_track == "上轨" else ""
            middle_marker = " ← 此轨最近" if closest_track == "中轨" else ""
            down_marker = " ← 此轨最近" if closest_track == "下轨" else ""
            
            boll_info = f"BOLL上轨{signal.boll_up_diff_pct:+.2f}%{up_marker} | 中轨{signal.boll_middle_diff_pct:+.2f}%{middle_marker} | 下轨{signal.boll_down_diff_pct:+.2f}%{down_marker}"
            print(f"\n📊 {boll_info}")
    
    print(f"\n{'='*70}")
    print("✅ RSI功能测试完成")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    test_rsi_output()
