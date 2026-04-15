# -*- coding: utf-8 -*-
"""测试BOLL布林带价差百分比显示功能"""
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


def test_boll_diff_pct_in_signals():
    """测试信号中的BOLL价差百分比计算和显示"""
    print("\n" + "="*70)
    print("📊 BOLL布林带价差百分比显示测试")
    print("="*70)
    
    # 创建策略引擎
    engine = MartingaleEngine()
    
    print("\n📋 策略配置:")
    print(f"   初始建仓比例: {engine.strategy_config.initial_position_pct}%")
    print(f"   止盈涨幅阈值: {engine.strategy_config.take_profit_threshold}%")
    
    symbol = "sh.513120"
    
    # ========== 测试1: BUY信号中的BOLL下轨价差百分比 ==========
    print("\n" + "="*70)
    print("🧪 测试1: BUY信号 - 买入价与BOLL下轨价差百分比")
    print("="*70)
    
    # 模拟市场数据：价格在BOLL下轨上方
    current_price = 1.280
    boll_down = 1.250
    boll_up = 1.350
    avg_cost = 1.280  # 买入时的平均成本
    
    mock_market_data = MarketData(
        symbol=symbol,
        name="港股创新药ETF",
        current_price=current_price,
        open_price=1.270,
        high_price=1.290,
        low_price=1.265,
        volume=1000000,
        amount=1280000,
        change_pct=0.79,
        timestamp=datetime.now(),
        ema_20=1.275,
        ema_60=1.260,
        ma_5=1.278,
        volume_ma5=950000,
        rsi=45.5,
        capital_flow=-50000,
        boll_up=boll_up,
        boll_middle=1.300,
        boll_down=boll_down
    )
    
    print(f"\n💰 市场数据:")
    print(f"   当前价格: ¥{current_price:.3f}")
    print(f"   BOLL上轨: ¥{boll_up:.3f}")
    print(f"   BOLL中轨: ¥1.300")
    print(f"   BOLL下轨: ¥{boll_down:.3f}")
    print(f"   平均成本: ¥{avg_cost:.3f}")
    
    expected_diff_abs = current_price - boll_down
    expected_diff_pct = (expected_diff_abs / current_price) * 100  # 使用买入价格作为分母
    print(f"\n📐 理论价差:")
    print(f"   绝对值: 买入价 - BOLL下轨 = ¥{expected_diff_abs:.3f}")
    print(f"   百分比: (价差 / 买入价格) × 100 = {expected_diff_pct:.2f}%")
    
    with patch('src.strategy.engine.get_market_data', return_value=mock_market_data):
        with patch('src.strategy.engine.get_sh_index', return_value=3988.56):
            with patch('src.strategy.engine.get_capital_flow', return_value=-50000):
                signal = engine.analyze(symbol)
    
    print(f"\n✅ 实际生成的BUY信号:")
    print(f"   信号类型: {signal.signal_type.value}")
    print(f"   买入价格: ¥{signal.price:.3f}")
    print(f"   平均成本: ¥{signal.avg_cost:.3f}")
    
    if signal.boll_down_diff_pct is not None:
        print(f"   ✅ BOLL下轨价差: {signal.boll_down_diff_pct:.2f}%")
        print(f"      与理论值对比: {expected_diff_pct:.2f}% (误差: {abs(signal.boll_down_diff_pct - expected_diff_pct):.4f}%)")
        
        if signal.boll_down_diff_pct > 0:
            print(f"      💡 买入价在BOLL下轨**上方** {signal.boll_down_diff_pct:.2f}%")
        else:
            print(f"      💡 买入价在BOLL下轨**下方** {abs(signal.boll_down_diff_pct):.2f}%")
    else:
        print(f"   ❌ 未提供BOLL下轨价差百分比")
    
    # ========== 测试2: SELL信号中的BOLL上轨价差百分比 ==========
    print("\n" + "="*70)
    print("🧪 测试2: SELL信号 - 卖出价与BOLL上轨价差百分比")
    print("="*70)
    
    # 设置持仓状态为已建仓，并且价格上涨触发止盈
    position = engine.positions[symbol]
    position.status = PositionStatus.INIT
    position.init_price = 1.250
    position.avg_cost = 1.250
    position.total_shares = 1000
    position.position_value = 1250
    position.add_count = 1
    
    # 模拟市场数据：价格在BOLL上轨附近（触发止盈）
    sell_price = 1.340  # 比平均成本高7.2%，超过3%止盈阈值
    
    mock_sell_data = MarketData(
        symbol=symbol,
        name="港股创新药ETF",
        current_price=sell_price,
        open_price=1.330,
        high_price=1.350,
        low_price=1.325,
        volume=1200000,
        amount=1608000,
        change_pct=2.40,
        timestamp=datetime.now(),
        ema_20=1.300,
        ema_60=1.280,
        ma_5=1.320,
        volume_ma5=1000000,
        rsi=65.5,
        capital_flow=80000,
        boll_up=boll_up,
        boll_middle=1.300,
        boll_down=boll_down
    )
    
    print(f"\n💰 市场数据:")
    print(f"   当前价格: ¥{sell_price:.3f}")
    print(f"   BOLL上轨: ¥{boll_up:.3f}")
    print(f"   BOLL中轨: ¥1.300")
    print(f"   BOLL下轨: ¥{boll_down:.3f}")
    print(f"   平均成本: ¥{position.avg_cost:.3f}")
    
    expected_up_diff_abs = boll_up - sell_price
    expected_up_diff_pct = (expected_up_diff_abs / sell_price) * 100  # 使用卖出价格作为分母
    print(f"\n📐 理论价差:")
    print(f"   绝对值: BOLL上轨 - 卖出价 = ¥{expected_up_diff_abs:.3f}")
    print(f"   百分比: (价差 / 卖出价格) × 100 = {expected_up_diff_pct:.2f}%")
    
    with patch('src.strategy.engine.get_market_data', return_value=mock_sell_data):
        with patch('src.strategy.engine.get_sh_index', return_value=3988.56):
            with patch('src.strategy.engine.get_capital_flow', return_value=80000):
                signal = engine.analyze(symbol)
    
    print(f"\n✅ 实际生成的SELL信号:")
    print(f"   信号类型: {signal.signal_type.value}")
    print(f"   卖出价格: ¥{signal.price:.3f}")
    print(f"   平均成本: ¥{signal.avg_cost:.3f}")
    
    if signal.boll_up_diff_pct is not None:
        print(f"   ✅ BOLL上轨价差: {signal.boll_up_diff_pct:.2f}%")
        print(f"      与理论值对比: {expected_up_diff_pct:.2f}% (误差: {abs(signal.boll_up_diff_pct - expected_up_diff_pct):.4f}%)")
        
        if signal.boll_up_diff_pct > 0:
            print(f"      💡 卖出价在BOLL上轨**下方** {signal.boll_up_diff_pct:.2f}%")
        else:
            print(f"      💡 卖出价在BOLL上轨**上方** {abs(signal.boll_up_diff_pct):.2f}%")
    else:
        print(f"   ❌ 未提供BOLL上轨价差百分比")
    
    print("\n" + "="*70)
    print("✅ 测试完成！")
    print("="*70 + "\n")
    
    print("💡 说明:")
    print("   - BUY/ADD信号显示买入价与BOLL下轨的价差百分比")
    print("   - SELL信号显示卖出价与BOLL上轨的价差百分比")
    print("   - 计算公式: (价差 / 信号价格) × 100%")
    print("   - 帮助判断当前价格相对布林带的偏离程度")
    print("   - 百分比形式更直观，便于跨标的比较")


if __name__ == "__main__":
    test_boll_diff_pct_in_signals()
