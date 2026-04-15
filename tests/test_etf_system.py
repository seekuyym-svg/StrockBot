# -*- coding: utf-8 -*-
"""ETF T+0交易系统测试脚本"""
import sys
from pathlib import Path
import time

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.market.data_provider import get_market_data, get_sh_index
from src.strategy.engine import get_strategy_engine
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


def test_data_provider():
    """测试数据提供者"""
    logger.info("=" * 60)
    logger.info("测试1: 数据提供者")
    logger.info("=" * 60)
    
    success_count = 0
    total_count = 0
    
    # 测试上证指数
    logger.info("\n📊 获取上证指数...")
    total_count += 1
    sh_index = get_sh_index()
    if sh_index:
        logger.success(f"✅ 上证指数: {sh_index:.2f}")
        success_count += 1
    else:
        logger.warning("⚠️  获取上证指数失败（可能是网络问题或非交易时间）")
    
    # 测试两个ETF的实时数据
    etfs = ["sh.513120", "sh.513050"]
    
    for etf in etfs:
        logger.info(f"\n📈 获取 {etf} 实时行情...")
        total_count += 1
        data = get_market_data(etf)
        
        if data:
            logger.success(f"✅ {data.name} ({data.symbol})")
            logger.info(f"   当前价格: ¥{data.current_price:.3f}")
            logger.info(f"   涨跌幅: {data.change_pct:+.2f}%")
            logger.info(f"   成交量: {data.volume:,.0f} 股")
            logger.info(f"   成交额: ¥{data.amount:,.2f}")
            
            if data.ema_20:
                logger.info(f"   EMA20: {data.ema_20:.3f}")
            if data.ema_60:
                logger.info(f"   EMA60: {data.ema_60:.3f}")
            if data.rsi:
                rsi_status = "超卖" if data.rsi < 30 else "超买" if data.rsi > 70 else "正常"
                logger.info(f"   RSI: {data.rsi:.2f} ({rsi_status})")
            
            success_count += 1
        else:
            logger.error(f"❌ 获取 {etf} 数据失败")
            logger.warning("   可能原因:")
            logger.warning("   1. 东方财富API临时故障（502错误）")
            logger.warning("   2. 网络连接问题")
            logger.warning("   3. 非交易时间数据不可用")
            logger.warning("   建议: 稍后重试或检查网络连接")
    
    print()
    
    # 显示测试结果统计
    logger.info("=" * 60)
    logger.info(f"测试结果: {success_count}/{total_count} 成功")
    if success_count == total_count:
        logger.success("✅ 所有数据获取成功！")
    elif success_count > 0:
        logger.warning(f"⚠️  部分数据获取失败，但不影响系统运行")
    else:
        logger.error("❌ 所有数据获取失败，请检查网络连接")
        logger.info("\n💡 提示:")
        logger.info("   - 这可能是东方财富API的临时故障")
        logger.info("   - 系统已内置自动重试机制（重试3次）")
        logger.info("   - 建议等待几分钟后再次尝试")
        logger.info("   - 或者您可以直接启动服务，服务会在运行时继续尝试")
    logger.info("=" * 60)
    print()
    
    return success_count > 0


def test_strategy_engine():
    """测试策略引擎"""
    logger.info("=" * 60)
    logger.info("测试2: 策略引擎")
    logger.info("=" * 60)
    
    engine = get_strategy_engine()
    
    # 获取所有信号
    logger.info("\n🎯 获取所有ETF交易信号...")
    signals = engine.get_all_signals()
    
    has_valid_signal = False
    for signal in signals:
        logger.info(f"\n{signal.name} ({signal.symbol}):")
        logger.info(f"   信号类型: {signal.signal_type.value}")
        
        if signal.price > 0:
            logger.info(f"   当前价格: ¥{signal.price:.3f}")
            logger.info(f"   涨跌幅: {signal.change_pct:+.2f}%")
            has_valid_signal = True
        
        logger.info(f"   原因: {signal.reason}")
        
        if signal.position_count > 0:
            logger.info(f"   持仓次数: {signal.position_count}")
            logger.info(f"   平均成本: ¥{signal.avg_cost:.3f}")
            logger.info(f"   持仓市值: ¥{signal.position_value:,.2f}")
        
        if signal.target_shares > 0:
            logger.info(f"   目标份额: {signal.target_shares:,} 份")
    
    # 获取持仓信息
    logger.info("\n💼 获取持仓信息...")
    positions = engine.get_all_positions()
    
    for pos in positions:
        logger.info(f"\n{pos.name} ({pos.symbol}):")
        logger.info(f"   状态: {pos.status.value}")
        logger.info(f"   加仓次数: {pos.add_count}")
        logger.info(f"   总份额: {pos.total_shares:,}")
        if pos.avg_cost > 0:
            logger.info(f"   平均成本: ¥{pos.avg_cost:.3f}")
            logger.info(f"   持仓市值: ¥{pos.position_value:,.2f}")
        else:
            logger.info(f"   平均成本: 无持仓")
            logger.info(f"   持仓市值: ¥0.00")
    
    print()
    
    if has_valid_signal:
        logger.success("✅ 策略引擎运行正常，已生成有效信号")
    else:
        logger.warning("⚠️  策略引擎未能生成有效信号（可能是数据获取失败导致）")
    
    return True


def test_api_endpoints():
    """测试API端点（需要启动服务后）"""
    logger.info("=" * 60)
    logger.info("测试3: API端点")
    logger.info("=" * 60)
    logger.info("\n🌐 请启动服务后访问以下URL测试:")
    logger.info("   📖 API文档: http://localhost:8080/docs")
    logger.info("   🏥 健康检查: http://localhost:8080/api/health")
    logger.info("   📊 所有信号: http://localhost:8080/api/signals")
    logger.info("   🎯 单个信号: http://localhost:8080/api/signal/sh.513120")
    logger.info("   💼 持仓信息: http://localhost:8080/api/positions")
    logger.info("   📈 市场数据: http://localhost:8080/api/market/sh.513120")
    print()


def main():
    """主测试函数"""
    logger.info("\n" + "=" * 60)
    logger.info("ETF链接基金T+0马丁格尔量化交易系统 - 测试")
    logger.info("=" * 60 + "\n")
    
    try:
        # 测试数据提供者
        data_ok = test_data_provider()
        
        # 即使数据获取失败，也继续测试策略引擎
        test_strategy_engine()
        
        # 提示API测试
        test_api_endpoints()
        
        logger.success("\n" + "=" * 60)
        logger.success("✅ 测试完成！")
        logger.success("=" * 60)
        
        if data_ok:
            logger.info("\n🚀 系统运行正常，可以启动服务了！")
            logger.info("   运行命令: python main.py")
        else:
            logger.warning("\n⚠️  数据获取存在问题，但系统架构正常")
            logger.info("\n💡 建议:")
            logger.info("   1. 检查网络连接")
            logger.info("   2. 等待几分钟后重试")
            logger.info("   3. 或直接启动服务: python main.py")
            logger.info("      (服务会在运行时继续尝试获取数据)")
        
    except Exception as e:
        logger.error(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
