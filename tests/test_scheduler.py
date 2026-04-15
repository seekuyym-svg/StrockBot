# -*- coding: utf-8 -*-
"""测试定时任务调度器"""
import sys
from pathlib import Path
import time

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.scheduler import get_signal_scheduler
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


def test_scheduler():
    """测试调度器功能"""
    logger.info("=" * 60)
    logger.info("测试定时任务调度器")
    logger.info("=" * 60)
    
    # 创建调度器（使用较短的间隔用于测试）
    scheduler = get_signal_scheduler(interval_minutes=1)
    
    logger.info("\n📝 测试1: 手动执行一次信号检查")
    scheduler.check_all_signals()
    
    logger.info("\n📝 测试2: 启动定时任务（仅运行30秒用于测试）")
    scheduler.start()
    
    try:
        # 等待30秒观察效果
        logger.info("⏰ 等待30秒，观察定时任务执行情况...")
        time.sleep(30)
        
        logger.info(f"下次运行时间: {scheduler._get_next_run_time()}")
        
    except KeyboardInterrupt:
        logger.info("\n⚠️ 用户中断")
    finally:
        # 停止调度器
        scheduler.stop()
        logger.info("\n✅ 测试完成")


if __name__ == "__main__":
    test_scheduler()
