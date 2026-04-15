# -*- coding: utf-8 -*-
"""测试市场研判功能"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.market_analyzer import analyze_market, get_analysis_description


def test_market_analysis():
    """测试各种市场状态的研判"""
    
    print("\n" + "="*70)
    print("测试市场研判功能（RSI + BOLL综合分析）")
    print("="*70)
    
    # 测试场景1: RSI超买 + 价格接近BOLL上轨 → 回调
    print("\n📊 场景1: RSI超买 + 价格接近BOLL上轨")
    result1 = analyze_market(
        rsi=75.5,
        boll_up_diff_pct=-3.2,  # 距离上轨3.2%
        boll_middle_diff_pct=8.5,
        boll_down_diff_pct=20.2
    )
    desc1 = get_analysis_description(result1)
    print(f"   研判结果: {result1}")
    print(f"   详细说明: {desc1}")
    assert result1 == "回调", f"期望'回调'，实际得到'{result1}'"
    
    # 测试场景2: RSI超卖 + 价格接近BOLL下轨 → 反弹
    print("\n📊 场景2: RSI超卖 + 价格接近BOLL下轨")
    result2 = analyze_market(
        rsi=25.3,
        boll_up_diff_pct=-18.5,
        boll_middle_diff_pct=-10.2,
        boll_down_diff_pct=4.1  # 距离下轨4.1%
    )
    desc2 = get_analysis_description(result2)
    print(f"   研判结果: {result2}")
    print(f"   详细说明: {desc2}")
    assert result2 == "反弹", f"期望'反弹'，实际得到'{result2}'"
    
    # 测试场景3: RSI中性 + 价格在中轨附近 → 震荡
    print("\n📊 场景3: RSI中性 + 价格在中轨附近")
    result3 = analyze_market(
        rsi=50.2,
        boll_up_diff_pct=-12.5,
        boll_middle_diff_pct=2.8,  # 距离中轨2.8%
        boll_down_diff_pct=15.3
    )
    desc3 = get_analysis_description(result3)
    print(f"   研判结果: {result3}")
    print(f"   详细说明: {desc3}")
    assert result3 == "震荡", f"期望'震荡'，实际得到'{result3}'"
    
    # 测试场景4: RSI超买但价格远离上轨 → 暂无
    print("\n📊 场景4: RSI超买但价格远离上轨")
    result4 = analyze_market(
        rsi=72.8,
        boll_up_diff_pct=-12.5,  # 距离上轨12.5%，不接近
        boll_middle_diff_pct=5.2,
        boll_down_diff_pct=22.8
    )
    desc4 = get_analysis_description(result4)
    print(f"   研判结果: {result4}")
    print(f"   详细说明: {desc4}")
    assert result4 == "暂无", f"期望'暂无'，实际得到'{result4}'"
    
    # 测试场景5: RSI为None → 暂无
    print("\n📊 场景5: RSI数据缺失")
    result5 = analyze_market(
        rsi=None,
        boll_up_diff_pct=-5.2,
        boll_middle_diff_pct=2.1,
        boll_down_diff_pct=10.5
    )
    desc5 = get_analysis_description(result5)
    print(f"   研判结果: {result5}")
    print(f"   详细说明: {desc5}")
    assert result5 == "暂无", f"期望'暂无'，实际得到'{result5}'"
    
    # 测试场景6: 边界值测试 - RSI刚好70
    print("\n📊 场景6: RSI=70（边界值，不算超买）")
    result6 = analyze_market(
        rsi=70.0,
        boll_up_diff_pct=-3.5,
        boll_middle_diff_pct=8.2,
        boll_down_diff_pct=18.5
    )
    desc6 = get_analysis_description(result6)
    print(f"   研判结果: {result6}")
    print(f"   详细说明: {desc6}")
    # RSI=70不算超买，应该返回"暂无"
    assert result6 == "暂无", f"期望'暂无'，实际得到'{result6}'"
    
    # 测试场景7: 边界值测试 - RSI刚好30
    print("\n📊 场景7: RSI=30（边界值，不算超卖）")
    result7 = analyze_market(
        rsi=30.0,
        boll_up_diff_pct=-15.2,
        boll_middle_diff_pct=-8.5,
        boll_down_diff_pct=3.8
    )
    desc7 = get_analysis_description(result7)
    print(f"   研判结果: {result7}")
    print(f"   详细说明: {desc7}")
    # RSI=30不算超卖，应该返回"暂无"
    assert result7 == "暂无", f"期望'暂无'，实际得到'{result7}'"
    
    # 测试场景8: BOLL数据不完整 → 暂无
    print("\n📊 场景8: BOLL数据不完整")
    result8 = analyze_market(
        rsi=65.2,
        boll_up_diff_pct=-8.5,
        boll_middle_diff_pct=None,  # 缺少中轨数据
        boll_down_diff_pct=12.3
    )
    desc8 = get_analysis_description(result8)
    print(f"   研判结果: {result8}")
    print(f"   详细说明: {desc8}")
    assert result8 == "暂无", f"期望'暂无'，实际得到'{result8}'"
    
    print("\n" + "="*70)
    print("✅ 所有测试场景通过！")
    print("="*70)
    
    # 显示研判规则总结
    print("\n📋 研判规则总结:")
    print("   1️⃣  RSI > 70 (超买) + 距BOLL上轨 ≤ 5% → 回调 ⚠️")
    print("   2️⃣  RSI < 30 (超卖) + 距BOLL下轨 ≤ 5% → 反弹 ✅")
    print("   3️⃣  30 ≤ RSI ≤ 70 (中性) + 距BOLL中轨 ≤ 5% → 震荡 🔄")
    print("   4️⃣  其他情况 → 暂无 ⏸️")
    print("\n💡 提示:")
    print("   - '接近'的定义：距离轨道价格在5%以内")
    print("   - 阈值可在 market_analyzer.py 中调整")
    print("="*70 + "\n")


if __name__ == "__main__":
    test_market_analysis()
