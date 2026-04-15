# -*- coding: utf-8 -*-
"""测试交易时间判断功能"""
import sys
from pathlib import Path
from datetime import datetime, time
from unittest.mock import patch

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.scheduler import SignalScheduler
from src.utils.config import get_config
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


def test_trading_time():
    """测试交易时间判断"""
    print("\n" + "="*70)
    print("🕒 交易时间判断功能测试")
    print("="*70)
    
    # 获取配置
    config = get_config()
    trading_hours = config.scheduler.trading_hours
    
    print("\n📋 当前配置:")
    print(f"   交易日: {trading_hours.trading_days}")
    print(f"   开始时间: {trading_hours.start_time}")
    print(f"   结束时间: {trading_hours.end_time}")
    
    # 创建调度器（不启动）
    scheduler = SignalScheduler(interval_minutes=5)
    
    # 测试不同时间点
    test_times = [
        (datetime(2026, 4, 13, 8, 59), "周一 08:59（交易前）"),
        (datetime(2026, 4, 13, 9, 0), "周一 09:00（交易开始）"),
        (datetime(2026, 4, 13, 12, 0), "周一 12:00（交易中）"),
        (datetime(2026, 4, 13, 15, 0), "周一 15:00（交易结束）"),
        (datetime(2026, 4, 13, 15, 1), "周一 15:01（交易后）"),
        (datetime(2026, 4, 18, 10, 0), "周六 10:00（周末）"),
        (datetime(2026, 4, 19, 10, 0), "周日 10:00（周末）"),
    ]
    
    print("\n🧪 测试结果:")
    print("-" * 70)
    
    weekday_map = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 
                  4: "周五", 5: "周六", 6: "周日"}
    
    for test_dt, description in test_times:
        # 使用mock模拟datetime.now
        with patch('src.utils.scheduler.datetime') as mock_datetime:
            mock_datetime.now.return_value = test_dt
            # 保留time类
            from datetime import time as time_class
            mock_datetime.time = time_class
            
            is_trading = scheduler.is_trading_time()
            status = "✅ 交易时间" if is_trading else "❌ 非交易时间"
            
            weekday = weekday_map[test_dt.weekday()]
            
            print(f"{status} | {description:20s} | {weekday} {test_dt.strftime('%H:%M')}")
    
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


if __name__ == "__main__":
    test_trading_time()
