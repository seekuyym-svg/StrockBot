# -*- coding: utf-8 -*-
"""测试WAIT信号中的目标价格显示功能"""
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.strategy.engine import MartingaleEngine
from src.models.models import SignalType, PositionStatus, MarketData
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


def test_wait_signal_with_target_prices():
    """测试WAIT信号中包含目标价格"""
    print("\n" + "="*70)
    print("🎯 WAIT信号目标价格显示测试")
    print("="*70)
    
    # 创建策略引擎
    engine = MartingaleEngine()
    
    print("\n📋 策略配置:")
    print(f"   初始建仓比例: {engine.strategy_config.initial_position_pct}%")
    print(f"   最大加仓次数: {engine.strategy_config.max_add_positions}")
    print(f"   加仓倍数: {engine.strategy_config.add_position_multiplier}x")
    print(f"   加仓跌幅阈值: {engine.strategy_config.add_drop_threshold}%")
    print(f"   止盈涨幅阈值: {engine.strategy_config.take_profit_threshold}%")
    
    # 模拟持仓状态 - 已初始建仓
    symbol = "sh.513120"
    position = engine.positions[symbol]
    
    # 设置持仓状态为已建仓
    position.status = PositionStatus.INIT
    position.init_price = 1.300
    position.avg_cost = 1.300
    position.total_shares = 1000
    position.position_value = 1300
    position.add_count = 1
    
    print(f"\n💼 当前持仓状态:")
    print(f"   标的: {position.name} ({position.symbol})")
    print(f"   状态: {position.status.value}")
    print(f"   平均成本: ¥{position.avg_cost:.3f}")
    print(f"   持仓份额: {position.total_shares:,}")
    print(f"   加仓次数: {position.add_count}")
    
    # 计算理论上的目标价格
    avg_cost = position.avg_cost
    init_price = position.init_price
    add_drop_threshold = engine.strategy_config.add_drop_threshold
    take_profit_threshold = engine.strategy_config.take_profit_threshold
    
    # 下一次加仓价格（第2次加仓，需要累计下跌7%从初始价格）
    next_add_drop = add_drop_threshold * (position.add_count + 1)  # 3.5% * 2 = 7%
    expected_add_price = init_price * (1 - next_add_drop / 100)
    
    # 止盈价格（基于平均成本）
    expected_sell_price = avg_cost * (1 + take_profit_threshold / 100)
    
    print(f"\n📊 理论目标价格:")
    print(f"   下次加仓价: ¥{expected_add_price:.3f} (从初始价累计下跌 {next_add_drop:.2f}%)")
    print(f"   止盈卖出价: ¥{expected_sell_price:.3f} (从平均成本上涨 {take_profit_threshold:.2f}%)")
    
    # 模拟当前价格在中间位置
    current_price = avg_cost * 0.98  # 下跌2%
    
    print(f"\n🧪 测试场景: 当前价格 ¥{current_price:.3f} (下跌2%)")
    print("-" * 70)
    
    # Mock市场数据
    mock_market_data = MarketData(
        symbol=symbol,
        name="港股创新药ETF",
        current_price=current_price,
        open_price=1.310,
        high_price=1.320,
        low_price=1.290,
        volume=1000000,
        amount=1300000,
        change_pct=-1.54,
        timestamp=datetime.now(),
        ema_20=1.305,
        ema_60=1.295,
        ma_5=1.308,
        volume_ma5=950000,
        rsi=45.5,
        capital_flow=-50000
    )
    
    with patch('src.strategy.engine.get_market_data', return_value=mock_market_data):
        with patch('src.strategy.engine.get_sh_index', return_value=3988.56):
            with patch('src.strategy.engine.get_capital_flow', return_value=-50000):
                signal = engine.analyze(symbol)
    
    print(f"\n✅ 实际生成的信号:")
    print(f"   信号类型: {signal.signal_type.value}")
    print(f"   当前价格: ¥{signal.price:.3f}")
    print(f"   涨跌幅: {signal.change_pct:+.2f}%")
    print(f"   原因: {signal.reason}")
    
    if signal.signal_type == SignalType.WAIT:
        print(f"\n🎯 目标价格信息:")
        if signal.next_add_price:
            actual_add_drop = (signal.price - signal.next_add_price) / signal.price * 100
            print(f"   ✅ 下次加仓价: ¥{signal.next_add_price:.3f}")
            print(f"      与理论值对比: ¥{expected_add_price:.3f} (误差: {abs(signal.next_add_price - expected_add_price):.4f})")
            print(f"      还需下跌: {actual_add_drop:.2f}%")
        else:
            print(f"   ❌ 未提供下次加仓价格")
        
        if signal.next_sell_price:
            actual_sell_profit = (signal.next_sell_price - signal.price) / signal.price * 100
            print(f"   ✅ 止盈卖出价: ¥{signal.next_sell_price:.3f}")
            print(f"      与理论值对比: ¥{expected_sell_price:.3f} (误差: {abs(signal.next_sell_price - expected_sell_price):.4f})")
            print(f"      需上涨: {actual_sell_profit:.2f}%")
        else:
            print(f"   ❌ 未提供止盈卖出价格")
    else:
        print(f"   ⚠️  信号类型不是WAIT，无法测试目标价格")
    
    print("\n" + "="*70)
    print("✅ 测试完成！")
    print("="*70 + "\n")
    
    print("💡 说明:")
    print("   - WAIT信号现在会显示下次加仓和止盈的目标价格")
    print("   - 帮助投资者提前了解关键价位，做好交易准备")
    print("   - 价格计算基于当前平均成本和策略配置参数")


if __name__ == "__main__":
    test_wait_signal_with_target_prices()
    
    # 额外测试：验证多次加仓后的目标价格计算
    print("\n" + "="*70)
    print("🔍 多次加仓场景验证")
    print("="*70)
    
    engine = MartingaleEngine()
    symbol = "sh.513120"
    init_price = 1.000
    add_threshold = engine.strategy_config.add_drop_threshold
    
    print(f"\n📊 策略参数:")
    print(f"   初始价格: ¥{init_price:.3f}")
    print(f"   加仓阈值: {add_threshold}%")
    print(f"   最大加仓次数: {engine.strategy_config.max_add_positions}")
    
    print(f"\n✅ 预期的加仓价格序列（基于初始价格）:")
    for i in range(1, engine.strategy_config.max_add_positions + 2):
        drop_pct = add_threshold * i
        add_price = init_price * (1 - drop_pct / 100)
        print(f"   第{i}次加仓: 下跌{drop_pct:5.1f}% → ¥{add_price:.3f}")
    
    stop_loss_pct = add_threshold * (engine.strategy_config.max_add_positions + 1)
    stop_loss_price = init_price * (1 - stop_loss_pct / 100)
    print(f"   止损触发: 下跌{stop_loss_pct:5.1f}% → ¥{stop_loss_price:.3f}")
    
    print("\n💡 说明:")
    print("   - 所有加仓价格都基于初始建仓价格计算")
    print("   - 每次加仓间隔固定为3.5%（从初始价格）")
    print("   - 确保加仓层级清晰、可预测")
    print("="*70 + "\n")
