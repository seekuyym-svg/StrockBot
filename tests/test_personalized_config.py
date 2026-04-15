# -*- coding: utf-8 -*-
"""测试个性化策略参数配置"""
from src.utils.config import get_config, load_config
from src.strategy.engine import get_strategy_engine


def test_personalized_config():
    """测试个性化策略参数配置"""
    print("=" * 60)
    print("测试个性化策略参数配置")
    print("=" * 60)
    
    # 重新加载配置
    config = load_config()
    
    print("\n1. 检查配置文件中的symbol配置:")
    for symbol_cfg in config.symbols:
        print(f"\n   {symbol_cfg.code} - {symbol_cfg.name}")
        print(f"      enabled: {symbol_cfg.enabled}")
        print(f"      add_drop_threshold: {symbol_cfg.add_drop_threshold}")
        print(f"      take_profit_threshold: {symbol_cfg.take_profit_threshold}")
        print(f"      max_add_positions: {symbol_cfg.max_add_positions}")
        print(f"      initial_position_pct: {symbol_cfg.initial_position_pct}")
    
    print("\n2. 全局默认策略配置:")
    print(f"   add_drop_threshold: {config.strategy.add_drop_threshold}")
    print(f"   take_profit_threshold: {config.strategy.take_profit_threshold}")
    print(f"   max_add_positions: {config.strategy.max_add_positions}")
    print(f"   initial_position_pct: {config.strategy.initial_position_pct}")
    
    print("\n3. 测试策略引擎获取个性化配置:")
    engine = get_strategy_engine()
    
    for symbol_cfg in config.symbols:
        if symbol_cfg.enabled:
            strategy_config = engine._get_symbol_strategy_config(symbol_cfg.code)
            print(f"\n   {symbol_cfg.code} - {symbol_cfg.name}:")
            print(f"      add_drop_threshold: {strategy_config.add_drop_threshold}")
            print(f"      take_profit_threshold: {strategy_config.take_profit_threshold}")
            print(f"      max_add_positions: {strategy_config.max_add_positions}")
            print(f"      initial_position_pct: {strategy_config.initial_position_pct}")
            
            # 验证是否使用了个性化配置
            if symbol_cfg.add_drop_threshold is not None:
                assert strategy_config.add_drop_threshold == symbol_cfg.add_drop_threshold, \
                    f"{symbol_cfg.code} 的 add_drop_threshold 配置不正确"
                print(f"      ✓ 使用个性化配置")
            else:
                assert strategy_config.add_drop_threshold == config.strategy.add_drop_threshold, \
                    f"{symbol_cfg.code} 应该使用全局默认配置"
                print(f"      ✓ 使用全局默认配置")
    
    print("\n" + "=" * 60)
    print("✓ 所有测试通过！个性化配置功能正常工作。")
    print("=" * 60)


if __name__ == "__main__":
    test_personalized_config()
