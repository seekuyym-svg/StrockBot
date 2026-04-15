# -*- coding: utf-8 -*-
"""测试动态检查间隔功能"""
import sys
from pathlib import Path
from datetime import datetime, time

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.config import get_config


def test_dynamic_interval():
    """测试动态检查间隔配置"""
    
    print("\n" + "="*70)
    print("测试动态检查间隔功能")
    print("="*70)
    
    # 加载配置
    config = get_config()
    
    print("\n📋 当前配置:")
    print(f"   交易时间检查间隔: {config.scheduler.trading_check_interval} 分钟")
    print(f"   非交易时间检查间隔: {config.scheduler.non_trading_check_interval} 分钟")
    print(f"   兼容旧配置间隔: {config.scheduler.signal_check_interval} 分钟（已废弃）")
    
    # 显示交易时间配置
    trading_hours = config.scheduler.trading_hours
    print(f"\n⏰ 交易时间配置:")
    print(f"   交易日: 周{trading_hours.trading_days}")
    for i, session in enumerate(trading_hours.sessions, 1):
        print(f"   时段{i}: {session.start_time} - {session.end_time}")
    
    # 模拟不同时间点，判断是否为交易时间
    print(f"\n🧪 时间点测试:")
    
    test_times = [
        ("2026-04-15 09:30:00", "交易时间内（上午开盘）"),
        ("2026-04-15 10:30:00", "交易时间内（上午）"),
        ("2026-04-15 11:30:00", "交易时间内（上午收盘）"),
        ("2026-04-15 12:00:00", "非交易时间（午休）"),
        ("2026-04-15 13:30:00", "交易时间内（下午开盘）"),
        ("2026-04-15 15:00:00", "交易时间内（下午收盘前）"),
        ("2026-04-15 18:00:00", "非交易时间（晚上）"),
        ("2026-04-15 22:00:00", "交易时间内（晚上收盘）"),
        ("2026-04-19 10:00:00", "非交易时间（周日）"),
    ]
    
    from src.utils.scheduler import SignalScheduler
    
    scheduler = SignalScheduler()
    
    for time_str, description in test_times:
        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        
        # 临时修改系统时间来测试
        original_now = datetime.now
        
        class MockDateTime:
            @staticmethod
            def now():
                return dt
            
            @staticmethod
            def today():
                return dt.date()
        
        import src.utils.scheduler as scheduler_module
        scheduler_module.datetime = MockDateTime
        
        is_trading = scheduler.is_trading_time()
        expected_interval = scheduler.trading_check_interval if is_trading else scheduler.non_trading_check_interval
        
        status = "✅ 交易时间" if is_trading else "❌ 非交易时间"
        print(f"   {time_str} - {description}")
        print(f"      状态: {status}, 应使用间隔: {expected_interval}分钟")
        
        # 恢复
        scheduler_module.datetime = type('module', (), {'datetime': type('datetime', (), {'now': original_now})})()
    
    print("\n" + "="*70)
    print("✅ 动态间隔配置测试完成")
    print("="*70)
    
    print("\n💡 使用说明:")
    print("   1. 在 config.yaml 中配置 trading_check_interval 和 non_trading_check_interval")
    print("   2. 系统会根据当前时间自动选择合适的检查间隔")
    print("   3. 交易时间: 频繁检查（如1分钟），及时捕捉交易机会")
    print("   4. 非交易时间: 低频检查（如10分钟），仅监控指数状态")
    print("="*70 + "\n")


if __name__ == "__main__":
    test_dynamic_interval()
