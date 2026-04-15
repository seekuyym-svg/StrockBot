# -*- coding: utf-8 -*-
"""测试非交易时间功能"""
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.scheduler import SignalScheduler
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


def test_non_trading_time():
    """测试非交易时间功能"""
    print("\n" + "="*70)
    print("⏰ 非交易时间功能测试")
    print("="*70)
    
    # 创建调度器
    scheduler = SignalScheduler(interval_minutes=5)
    
    print("\n📋 当前配置:")
    print(f"   交易日: {scheduler.trading_days}")
    print(f"   交易时间: {scheduler.start_time} - {scheduler.end_time}")
    
    # 模拟非交易时间（周末）
    saturday_time = datetime(2026, 4, 18, 10, 30, 0)  # 周六上午10:30
    
    print(f"\n🧪 测试场景: {saturday_time.strftime('%Y-%m-%d %H:%M:%S')} (周六)")
    print("-" * 70)
    
    with patch('src.utils.scheduler.datetime') as mock_datetime:
        from datetime import time as time_class
        mock_datetime.now.return_value = saturday_time
        mock_datetime.time = time_class
        
        is_trading = scheduler.is_trading_time()
        print(f"   是否交易时间: {is_trading}")
        
        if not is_trading:
            print(f"   预期行为: 输出上证指数，不检查ETF信号")
            print(f"\n📊 执行非交易时间逻辑:")
            current_time_str = saturday_time.strftime("%Y-%m-%d %H:%M:%S")
            scheduler._log_non_trading_time(current_time_str)
        else:
            print(f"   ❌ 错误：应该判断为非交易时间")
    
    # 模拟非交易时间（交易日晚上的情况）
    evening_time = datetime(2026, 4, 13, 20, 0, 0)  # 周一晚上8点
    
    print(f"\n🧪 测试场景: {evening_time.strftime('%Y-%m-%d %H:%M:%S')} (周一晚上)")
    print("-" * 70)
    
    with patch('src.utils.scheduler.datetime') as mock_datetime:
        from datetime import time as time_class
        mock_datetime.now.return_value = evening_time
        mock_datetime.time = time_class
        
        is_trading = scheduler.is_trading_time()
        print(f"   是否交易时间: {is_trading}")
        
        if not is_trading:
            print(f"   预期行为: 输出上证指数，不检查ETF信号")
            print(f"\n📊 执行非交易时间逻辑:")
            current_time_str = evening_time.strftime("%Y-%m-%d %H:%M:%S")
            scheduler._log_non_trading_time(current_time_str)
        else:
            print(f"   ❌ 错误：应该判断为非交易时间")
    
    # 模拟交易时间
    trading_time = datetime(2026, 4, 13, 10, 30, 0)  # 周一上午10:30
    
    print(f"\n🧪 测试场景: {trading_time.strftime('%Y-%m-%d %H:%M:%S')} (周一上午)")
    print("-" * 70)
    
    with patch('src.utils.scheduler.datetime') as mock_datetime:
        from datetime import time as time_class
        mock_datetime.now.return_value = trading_time
        mock_datetime.time = time_class
        
        is_trading = scheduler.is_trading_time()
        print(f"   是否交易时间: {is_trading}")
        
        if is_trading:
            print(f"   预期行为: 检查ETF信号")
            print(f"   ✅ 正确：应该执行信号检查逻辑")
        else:
            print(f"   ❌ 错误：应该判断为交易时间")
    
    print("\n" + "="*70)
    print("✅ 测试完成！")
    print("="*70 + "\n")
    
    print("💡 说明:")
    print("   - 非交易时间会输出上证指数（INFO级别日志）")
    print("   - 交易时间会检查ETF信号并可能发送飞书通知")
    print("   - 可以通过修改 config.yaml 中的 trading_hours 调整交易时间")


if __name__ == "__main__":
    test_non_trading_time()
