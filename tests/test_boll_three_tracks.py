# -*- coding: utf-8 -*-
"""测试BOLL三轨完整价差显示功能"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.strategy.engine import get_strategy_engine
from src.market.data_provider import get_market_data


def test_boll_three_tracks():
    """测试BOLL三轨完整价差计算和显示"""
    print("\n" + "="*70)
    print("📊 BOLL三轨完整价差测试")
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
            print(f"❌ 无法获取市场数据")
            continue
        
        print(f"\n💰 实时行情:")
        print(f"   名称: {market_data.name}")
        print(f"   当前价格: ¥{market_data.current_price:.3f}")
        print(f"   涨跌幅: {market_data.change_pct:+.2f}%")
        
        print(f"\n📈 BOLL指标:")
        print(f"   上轨: ¥{market_data.boll_up:.3f}" if market_data.boll_up else "   上轨: N/A")
        print(f"   中轨: ¥{market_data.boll_middle:.3f}" if market_data.boll_middle else "   中轨: N/A")
        print(f"   下轨: ¥{market_data.boll_down:.3f}" if market_data.boll_down else "   下轨: N/A")
        
        # 生成信号
        signal = engine.analyze(symbol)
        if not signal:
            print(f"❌ 未生成信号")
            continue
        
        print(f"\n🎯 交易信号:")
        print(f"   信号类型: {signal.signal_type.value}")
        print(f"   信号价格: ¥{signal.price:.3f}")
        
        # 显示BOLL三轨价差
        if all([signal.boll_up_diff_pct is not None, 
                signal.boll_middle_diff_pct is not None, 
                signal.boll_down_diff_pct is not None]):
            
            print(f"\n📊 BOLL三轨价差分析:")
            
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
            
            # 显示上轨
            up_position = "上方" if signal.boll_up_diff_pct > 0 else "下方"
            up_marker = " ← 此轨最近" if closest_track == "上轨" else ""
            print(f"   BOLL上轨价差: {signal.boll_up_diff_pct:+.2f}% ({up_position}){up_marker}")
            
            # 显示中轨
            middle_position = "上方" if signal.boll_middle_diff_pct > 0 else "下方"
            middle_marker = " ← 此轨最近" if closest_track == "中轨" else ""
            print(f"   BOLL中轨价差: {signal.boll_middle_diff_pct:+.2f}% ({middle_position}){middle_marker}")
            
            # 显示下轨
            down_position = "上方" if signal.boll_down_diff_pct > 0 else "下方"
            down_marker = " ← 此轨最近" if closest_track == "下轨" else ""
            print(f"   BOLL下轨价差: {signal.boll_down_diff_pct:+.2f}% ({down_position}){down_marker}")
            
            print(f"\n💡 解读:")
            print(f"   当前价格最接近: BOLL{closest_track}")
            print(f"   价差绝对值: {min_diff:.2f}%")
            
            # 判断价格位置
            price = signal.price
            if price > market_data.boll_up:
                print(f"   ⚠️  价格突破BOLL上轨，可能超买")
            elif price < market_data.boll_down:
                print(f"   ⚠️  价格跌破BOLL下轨，可能超卖")
            else:
                print(f"   ✓ 价格在BOLL通道内运行")
        else:
            print(f"   ❌ BOLL价差数据不完整")
            print(f"      boll_up_diff_pct: {signal.boll_up_diff_pct}")
            print(f"      boll_middle_diff_pct: {signal.boll_middle_diff_pct}")
            print(f"      boll_down_diff_pct: {signal.boll_down_diff_pct}")
    
    print(f"\n{'='*70}")
    print("✅ 测试完成")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    test_boll_three_tracks()
