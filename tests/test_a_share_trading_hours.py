# -*- coding: utf-8 -*-
"""测试A股多时间段交易时间判断功能"""
import sys
from pathlib import Path
from datetime import datetime, time
from unittest.mock import patch

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.scheduler import SignalScheduler
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


def test_a_share_trading_hours():
    """测试A股多时间段交易时间判断"""
    print("\n" + "="*70)
    print("🕒 A股多时间段交易时间判断测试")
    print("="*70)
    
    # 创建调度器
    scheduler = SignalScheduler(interval_minutes=5)
    
    print("\n📋 当前配置:")
    print(f"   交易日: {scheduler.trading_days}")
    print(f"   交易时段:")
    for i, session in enumerate(scheduler.sessions, 1):
        print(f"     时段{i}: {session['start'].strftime('%H:%M')} - {session['end'].strftime('%H:%M')}")
    
    # 测试不同时间点
    test_times = [
        # 上午开盘前
        (datetime(2026, 4, 13, 9, 29), "周一 09:29（上午开盘前）"),
        # 上午交易时间
        (datetime(2026, 4, 13, 9, 30), "周一 09:30（上午开盘）"),
        (datetime(2026, 4, 13, 10, 30), "周一 10:30（上午交易中）"),
        (datetime(2026, 4, 13, 11, 30), "周一 11:30（上午收盘）"),
        # 午休时间
        (datetime(2026, 4, 13, 11, 31), "周一 11:31（午休开始）"),
        (datetime(2026, 4, 13, 12, 0), "周一 12:00（午休中）"),
        (datetime(2026, 4, 13, 12, 59), "周一 12:59（午休结束前）"),
        # 下午交易时间
        (datetime(2026, 4, 13, 13, 0), "周一 13:00（下午开盘）"),
        (datetime(2026, 4, 13, 14, 0), "周一 14:00（下午交易中）"),
        (datetime(2026, 4, 13, 15, 0), "周一 15:00（下午收盘）"),
        # 下午收盘后
        (datetime(2026, 4, 13, 15, 1), "周一 15:01（下午收盘后）"),
        # 周末
        (datetime(2026, 4, 18, 10, 0), "周六 10:00（周末）"),
        (datetime(2026, 4, 19, 14, 0), "周日 14:00（周末）"),
    ]
    
    print("\n🧪 测试结果:")
    print("-" * 70)
    
    weekday_map = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 
                  4: "周五", 5: "周六", 6: "周日"}
    
    for test_dt, description in test_times:
        # 使用mock模拟datetime.now
        with patch('src.utils.scheduler.datetime') as mock_datetime:
            from datetime import time as time_class
            mock_datetime.now.return_value = test_dt
            mock_datetime.time = time_class
            
            is_trading = scheduler.is_trading_time()
            status = "✅ 交易时间" if is_trading else "❌ 非交易时间"
            
            weekday = weekday_map[test_dt.weekday()]
            
            # 标记时间段类型
            period_tag = ""
            hour = test_dt.hour
            minute = test_dt.minute
            time_val = hour * 60 + minute
            
            if 570 <= time_val <= 690:  # 09:30-11:30
                period_tag = "[上午]"
            elif 780 <= time_val <= 900:  # 13:00-15:00
                period_tag = "[下午]"
            else:
                period_tag = "[休市]"
            
            print(f"{status} | {description:25s} | {weekday} {test_dt.strftime('%H:%M')} {period_tag}")
    
    print("-" * 70)
    
    # 测试当前时间
    print("\n⏰ 当前时间测试:")
    now = datetime.now()
    is_trading = scheduler.is_trading_time()
    weekday = weekday_map[now.weekday()]
    
    print(f"   当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')} ({weekday})")
    print(f"   状态: {'✅ 交易时间' if is_trading else '❌ 非交易时间'}")
    
    if is_trading:
        print(f"   操作: 将检查ETF信号")
    else:
        print(f"   操作: 仅输出上证指数")
    
    print("\n" + "="*70)
    print("✅ 测试完成！")
    print("="*70 + "\n")
    
    print("💡 A股交易时间说明:")
    print("   上午: 09:30 - 11:30 (2小时)")
    print("   午休: 11:30 - 13:00 (1.5小时)")
    print("   下午: 13:00 - 15:00 (2小时)")
    print("   总计: 4小时交易时间")


if __name__ == "__main__":
    test_a_share_trading_hours()
