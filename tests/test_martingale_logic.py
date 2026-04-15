# -*- coding: utf-8 -*-
"""测试马丁格尔策略加仓价格计算逻辑"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.strategy.engine import get_strategy_engine
from src.market.data_provider import get_market_data
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>", level="INFO")


def test_martingale_logic():
    """测试马丁格尔策略的加仓逻辑"""
    print("\n" + "="*70)
    print("🧪 马丁格尔策略加仓价格计算测试")
    print("="*70)
    
    engine = get_strategy_engine()
    config = engine.config
    strategy_config = engine.strategy_config
    
    print(f"\n📋 策略配置:")
    print(f"   初始资金: ¥{config.initial_capital:,.0f}")
    print(f"   初始仓位比例: {strategy_config.initial_position_pct}%")
    print(f"   加仓跌幅阈值: {strategy_config.add_drop_threshold}%")
    print(f"   最大加仓次数: {strategy_config.max_add_positions}")
    print(f"   止盈阈值: {strategy_config.take_profit_threshold}%")
    
    # 模拟不同加仓阶段的场景
    symbols = ["sh.513120"]
    
    for symbol in symbols:
        print(f"\n{'='*70}")
        print(f"📊 测试标的: {symbol}")
        print(f"{'='*70}")
        
        signal = engine.analyze(symbol)
        
        if not signal:
            print(f"❌ 未获取到信号")
            continue
        
        market_data = get_market_data(symbol)
        if not market_data:
            print(f"❌ 未获取到市场数据")
            continue
        
        position = engine.positions.get(symbol)
        if not position:
            print(f"⚠️  尚未建仓，跳过测试")
            continue
        
        print(f"\n💼 持仓信息:")
        print(f"   状态: {position.status.value}")
        print(f"   初始建仓价: ¥{position.init_price:.3f}")
        print(f"   平均成本: ¥{position.avg_cost:.3f}")
        print(f"   当前价格: ¥{signal.price:.3f}")
        print(f"   已加仓次数: {position.add_count}")
        print(f"   持有份额: {position.total_shares:,}")
        
        # 计算理论上的下次加仓价
        if position.add_count < strategy_config.max_add_positions:
            next_required_drop = strategy_config.add_drop_threshold * (position.add_count + 1)
            theoretical_next_add = position.init_price * (1 - next_required_drop / 100)
            
            print(f"\n📈 下次加仓预测:")
            print(f"   理论跌幅: {next_required_drop:.2f}% (相对于初始建仓价)")
            print(f"   理论加仓价: ¥{theoretical_next_add:.3f}")
            
            if signal.next_add_price:
                print(f"   实际计算的下次加仓价: ¥{signal.next_add_price:.3f}")
                
                # 验证计算是否正确
                if abs(signal.next_add_price - theoretical_next_add) < 0.001:
                    print(f"   ✅ 计算正确！")
                else:
                    print(f"   ❌ 计算错误！差异: ¥{abs(signal.next_add_price - theoretical_next_add):.3f}")
                
                # 计算从当前价到下次加仓价的跌幅
                current_to_next_drop = (signal.price - signal.next_add_price) / signal.price * 100
                print(f"   💡 从当前价还需下跌: {current_to_next_drop:.2f}%")
        else:
            print(f"\n⚠️  已达到最大加仓次数，不再加仓")
        
        # 显示止盈价
        if signal.next_sell_price:
            take_profit_pct = (signal.next_sell_price - position.avg_cost) / position.avg_cost * 100
            print(f"\n📉 止盈卖出:")
            print(f"   止盈价: ¥{signal.next_sell_price:.3f}")
            print(f"   预期盈利: {take_profit_pct:.2f}% (相对于平均成本)")
    
    print(f"\n{'='*70}")
    print("✅ 测试完成")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    test_martingale_logic()
