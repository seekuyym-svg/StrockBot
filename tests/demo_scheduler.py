# -*- coding: utf-8 -*-
"""定时任务功能演示脚本"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.scheduler import get_signal_scheduler
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


def demo():
    """演示定时任务功能"""
    print("\n" + "="*70)
    print("🎯 ETF信号定时检查功能演示")
    print("="*70)
    
    print("\n📋 功能说明:")
    print("   1. 每5分钟自动检查sh.513120和sh.513050的信号")
    print("   2. BUY/ADD/SELL信号 → 打印 + 持久化保存")
    print("   3. WAIT信号 → 仅打印（不保存）")
    print("   4. 启动时立即执行首次检查")
    
    print("\n💡 使用方式:")
    print("   方式1: python main.py                    # 启动完整系统")
    print("   方式2: python test_scheduler.py          # 测试调度器")
    
    print("\n🔧 现在执行一次手动检查演示...\n")
    
    # 创建调度器并执行一次检查
    scheduler = get_signal_scheduler(interval_minutes=5)
    scheduler.check_all_signals()
    
    print("\n" + "="*70)
    print("✅ 演示完成！")
    print("="*70)
    
    print("\n📊 查看生成的信号文件:")
    print("   ls signal/$(date +%Y-%m-%d)/")
    
    print("\n🚀 要启动完整系统，请运行:")
    print("   python main.py")
    print("\n")


if __name__ == "__main__":
    demo()
