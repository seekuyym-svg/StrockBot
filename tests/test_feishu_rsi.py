# -*- coding: utf-8 -*-
"""测试飞书通知中的RSI信息显示"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.notification import get_feishu_notifier


def test_feishu_rsi_notification():
    """测试飞书通知中RSI信息的显示"""
    print("\n" + "="*70)
    print("测试飞书通知中的RSI信息显示")
    print("="*70)
    
    notifier = get_feishu_notifier()
    
    # 测试数据1：超买区RSI
    print("\n📊 测试场景1: RSI超买区 (>70)")
    signal_data_overbought = {
        'symbol': 'sh.513120',
        'name': '港股创新药ETF广发',
        'signal_type': 'BUY',
        'price': 1.281,
        'change_pct': 0.71,
        'reason': '初始建仓：买入14000份，成本1.281元/份',
        'target_shares': 14000,
        'avg_cost': 1.281,
        'boll_up_diff_pct': -5.56,
        'boll_middle_diff_pct': 4.22,
        'boll_down_diff_pct': 13.99,
        'rsi': 74.32  # 超买区
    }
    
    message1 = notifier._build_message(signal_data_overbought)
    content1 = message1['card']['elements'][0]['text']['content']
    print("\n生成的消息内容:")
    print(content1)
    
    # 测试数据2：中性区RSI
    print("\n" + "-"*70)
    print("\n📊 测试场景2: RSI中性区 (30-70)")
    signal_data_neutral = {
        'symbol': 'sh.513050',
        'name': '中概互联网ETF易方达',
        'signal_type': 'WAIT',
        'price': 1.195,
        'change_pct': 0.84,
        'reason': '等待建仓时机',
        'target_shares': 0,
        'avg_cost': 0,
        'boll_up_diff_pct': -8.12,
        'boll_middle_diff_pct': -1.32,
        'boll_down_diff_pct': 5.48,
        'rsi': 47.58  # 中性区
    }
    
    message2 = notifier._build_message(signal_data_neutral)
    content2 = message2['card']['elements'][0]['text']['content']
    print("\n生成的消息内容:")
    print(content2)
    
    # 测试数据3：超卖区RSI
    print("\n" + "-"*70)
    print("\n📊 测试场景3: RSI超卖区 (<30)")
    signal_data_oversold = {
        'symbol': 'sh.513120',
        'name': '港股创新药ETF广发',
        'signal_type': 'ADD',
        'price': 1.250,
        'change_pct': -2.42,
        'reason': '加仓10000份，成本1.250元/份，累计1次加仓',
        'target_shares': 10000,
        'avg_cost': 1.265,
        'boll_up_diff_pct': -7.85,
        'boll_middle_diff_pct': 2.15,
        'boll_down_diff_pct': 12.15,
        'rsi': 25.80  # 超卖区
    }
    
    message3 = notifier._build_message(signal_data_oversold)
    content3 = message3['card']['elements'][0]['text']['content']
    print("\n生成的消息内容:")
    print(content3)
    
    # 测试数据4：无RSI数据
    print("\n" + "-"*70)
    print("\n📊 测试场景4: 无RSI数据")
    signal_data_no_rsi = {
        'symbol': 'sh.513120',
        'name': '港股创新药ETF广发',
        'signal_type': 'SELL',
        'price': 1.320,
        'change_pct': 3.04,
        'reason': '达到止盈目标（盈利4.35%），总收益XXX元 (+X.XX%)',
        'target_shares': 0,
        'avg_cost': 1.265,
        'boll_up_diff_pct': -2.35,
        'boll_middle_diff_pct': 7.65,
        'boll_down_diff_pct': 17.65,
        'rsi': None  # 无RSI数据
    }
    
    message4 = notifier._build_message(signal_data_no_rsi)
    content4 = message4['card']['elements'][0]['text']['content']
    print("\n生成的消息内容:")
    print(content4)
    
    print("\n" + "="*70)
    print("✅ 飞书通知RSI功能测试完成")
    print("="*70)
    print("\n💡 提示:")
    print("- 如果已配置飞书Webhook，可以调用 notifier.test_notification() 发送真实测试")
    print("- RSI > 70: 🔴 超买区 ⚠️")
    print("- 30 ≤ RSI ≤ 70: 🟡 中性区")
    print("- RSI < 30: 🟢 超卖区 ✅")
    print("="*70 + "\n")


if __name__ == "__main__":
    test_feishu_rsi_notification()
