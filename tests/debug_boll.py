# -*- coding: utf-8 -*-
"""调试BOLL指标计算问题"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.market.data_provider import EastMoneyWebScraper
from loguru import logger

# 配置日志显示DEBUG信息
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>", level="DEBUG")


def test_boll_calculation():
    """测试BOLL指标计算"""
    print("\n" + "="*70)
    print("🔍 BOLL指标计算诊断")
    print("="*70)
    
    scraper = EastMoneyWebScraper()
    
    # 测试两个ETF
    symbols = ["sh.513120", "sh.513050"]
    
    for symbol in symbols:
        print(f"\n{'='*70}")
        print(f"📊 测试标的: {symbol}")
        print(f"{'='*70}")
        
        try:
            # 获取实时数据
            market_data = scraper.get_realtime_data(symbol)
            
            if market_data:
                print(f"✅ 成功获取市场数据")
                print(f"   名称: {market_data.name}")
                print(f"   当前价格: ¥{market_data.current_price:.3f}")
                print(f"   涨跌幅: {market_data.change_pct:+.2f}%")
                
                # 检查BOLL指标
                print(f"\n📈 技术指标:")
                print(f"   EMA20: {market_data.ema_20 if market_data.ema_20 else 'N/A'}")
                print(f"   EMA60: {market_data.ema_60 if market_data.ema_60 else 'N/A'}")
                print(f"   MA5: {market_data.ma_5 if market_data.ma_5 else 'N/A'}")
                print(f"   RSI: {market_data.rsi if market_data.rsi else 'N/A'}")
                
                print(f"\n📊 BOLL布林带:")
                if market_data.boll_up and market_data.boll_middle and market_data.boll_down:
                    print(f"   ✅ BOLL上轨: ¥{market_data.boll_up:.3f}")
                    print(f"   ✅ BOLL中轨: ¥{market_data.boll_middle:.3f}")
                    print(f"   ✅ BOLL下轨: ¥{market_data.boll_down:.3f}")
                    
                    # 计算价格相对BOLL的位置
                    price = market_data.current_price
                    up_diff = (market_data.boll_up - price) / price * 100
                    down_diff = (price - market_data.boll_down) / price * 100
                    
                    print(f"\n💡 价格位置分析:")
                    print(f"   当前价格距上轨: {up_diff:+.2f}%")
                    print(f"   当前价格距下轨: {down_diff:+.2f}%")
                    
                    if price > market_data.boll_up:
                        print(f"   ⚠️  价格突破BOLL上轨")
                    elif price < market_data.boll_down:
                        print(f"   ⚠️  价格跌破BOLL下轨")
                    else:
                        print(f"   ✓ 价格在BOLL通道内")
                else:
                    print(f"   ❌ BOLL指标未计算")
                    print(f"      boll_up: {market_data.boll_up}")
                    print(f"      boll_middle: {market_data.boll_middle}")
                    print(f"      boll_down: {market_data.boll_down}")
                    print(f"\n💡 可能原因:")
                    print(f"      1. 历史K线数据获取失败")
                    print(f"      2. 历史数据不足20天")
                    print(f"      3. 数据格式解析错误")
            else:
                print(f"❌ 获取市场数据失败")
        
        except Exception as e:
            print(f"❌ 测试出错: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*70}")
    print("✅ 诊断完成")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    test_boll_calculation()
