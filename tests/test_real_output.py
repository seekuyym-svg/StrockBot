# -*- coding: utf-8 -*-
"""模拟main.py启动时的首次信号检查输出"""
import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.strategy.engine import get_strategy_engine
from loguru import logger

# 配置日志格式（模拟scheduler的输出）
logger.remove()
logger.add(sys.stdout, format="{message}", level="SUCCESS")


def simulate_first_signal_check():
    """模拟首次启动时的信号检查"""
    print("\n" + "="*70)
    print("🚀 模拟首次启动信号检查")
    print("="*70)
    
    engine = get_strategy_engine()
    signals = engine.get_all_signals()
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for signal in signals:
        if signal.signal_type.value in ["BUY", "SELL", "ADD"]:
            # 使用与scheduler相同的格式
            emoji_map = {
                "BUY": "🟢",
                "ADD": "🔵",
                "SELL": "🔴"
            }
            
            emoji = emoji_map.get(signal.signal_type.value, "📊")
            
            logger.success(f"\n{'='*60}")
            logger.success(f"{emoji} 【重要信号】{current_time}")
            logger.success(f"{'='*60}")
            logger.success(f"标的: {signal.name} ({signal.symbol})")
            logger.success(f"信号: {signal.signal_type.value}")
            logger.success(f"价格: ¥{signal.price:.3f}")
            logger.success(f"涨跌幅: {signal.change_pct:+.2f}%")
            
            if signal.target_shares > 0:
                logger.success(f"目标份额: {signal.target_shares:,}")
            
            if signal.avg_cost > 0:
                logger.success(f"平均成本: ¥{signal.avg_cost:.3f}")
            
            # 显示BOLL三轨信息（简化格式）
            if all([signal.boll_up_diff_pct is not None, 
                    signal.boll_middle_diff_pct is not None, 
                    signal.boll_down_diff_pct is not None]):
                
                up_abs = abs(signal.boll_up_diff_pct)
                middle_abs = abs(signal.boll_middle_diff_pct)
                down_abs = abs(signal.boll_down_diff_pct)
                
                min_diff = min(up_abs, middle_abs, down_abs)
                if min_diff == up_abs:
                    closest_track = "上轨"
                elif min_diff == middle_abs:
                    closest_track = "中轨"
                else:
                    closest_track = "下轨"
                
                up_marker = " ← 此轨最近" if closest_track == "上轨" else ""
                middle_marker = " ← 此轨最近" if closest_track == "中轨" else ""
                down_marker = " ← 此轨最近" if closest_track == "下轨" else ""
                
                boll_info = f"BOLL上轨{signal.boll_up_diff_pct:+.2f}%{up_marker} | 中轨{signal.boll_middle_diff_pct:+.2f}%{middle_marker} | 下轨{signal.boll_down_diff_pct:+.2f}%{down_marker}"
                logger.success(f"📊 {boll_info}")
            
            if signal.reason:
                logger.success(f"原因: {signal.reason}")
            
            logger.success(f"{'='*60}\n")
    
    print("="*70)
    print("✅ 模拟完成 - 所有数值均为实时计算")
    print("="*70 + "\n")


if __name__ == "__main__":
    simulate_first_signal_check()
