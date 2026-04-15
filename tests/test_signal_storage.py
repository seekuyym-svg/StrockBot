# -*- coding: utf-8 -*-
"""测试信号持久化功能"""
import sys
from pathlib import Path
import json

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.signal_storage import get_signal_storage
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


def test_signal_storage():
    """测试信号存储功能"""
    logger.info("=" * 60)
    logger.info("测试信号持久化功能")
    logger.info("=" * 60)
    
    storage = get_signal_storage()
    
    # 测试1: 保存单个信号
    logger.info("\n📝 测试1: 保存单个信号")
    test_signal_1 = {
        "symbol": "sh.513120",
        "name": "港股创新药ETF",
        "signal_type": "BUY",
        "price": 1.272,
        "change_pct": -0.78,
        "reason": "初始建仓信号",
        "target_shares": 3934,
        "position_count": 0,
        "avg_cost": 0,
        "position_value": 0
    }
    
    path1 = storage.save_signal("sh.513120", test_signal_1)
    if path1:
        logger.success(f"✅ 单个信号保存成功: {path1}")
    else:
        logger.error("❌ 单个信号保存失败")
    
    # 测试2: 保存另一个信号
    logger.info("\n📝 测试2: 保存第二个信号")
    test_signal_2 = {
        "symbol": "sh.513050",
        "name": "中概互联网ETF",
        "signal_type": "WAIT",
        "price": 1.185,
        "change_pct": -1.90,
        "reason": "观望中",
        "target_shares": 0,
        "position_count": 0,
        "avg_cost": 0,
        "position_value": 0
    }
    
    path2 = storage.save_signal("sh.513050", test_signal_2)
    if path2:
        logger.success(f"✅ 第二个信号保存成功: {path2}")
    else:
        logger.error("❌ 第二个信号保存失败")
    
    # 测试3: 保存所有信号
    logger.info("\n📝 测试3: 保存所有信号到汇总文件")
    all_signals = [test_signal_1, test_signal_2]
    path3 = storage.save_all_signals(all_signals)
    if path3:
        logger.success(f"✅ 所有信号保存成功: {path3}")
    else:
        logger.error("❌ 所有信号保存失败")
    
    # 测试4: 查看今天的信号文件
    logger.info("\n📝 测试4: 查看今天的信号文件")
    today_files = storage.get_today_signals()
    logger.info(f"今天共有 {len(today_files)} 个信号文件:")
    for f in today_files:
        logger.info(f"   - {f.name}")
    
    # 测试5: 读取并验证保存的数据
    logger.info("\n📝 测试5: 读取并验证保存的数据")
    if today_files:
        latest_file = today_files[-1]
        data = storage.load_signal_file(latest_file)
        logger.info(f"读取文件: {latest_file.name}")
        logger.info(f"数据内容: {json.dumps(data, ensure_ascii=False, indent=2)[:200]}...")
    
    # 测试6: 查看目录结构
    logger.info("\n📝 测试6: 信号存储目录结构")
    base_dir = Path("signal")
    if base_dir.exists():
        for date_dir in sorted(base_dir.iterdir()):
            if date_dir.is_dir():
                logger.info(f"📁 {date_dir.name}/")
                for file in sorted(date_dir.glob("*.json")):
                    logger.info(f"   📄 {file.name}")
    
    logger.info("\n" + "=" * 60)
    logger.success("✅ 信号持久化功能测试完成！")
    logger.info("=" * 60)
    logger.info("\n💡 提示:")
    logger.info("   - 信号文件保存在 signal/ 目录下")
    logger.info("   - 按日期分类存储，格式: signal/YYYY-MM-DD/")
    logger.info("   - 文件名格式: sh_513120_HHMMSS.json")
    logger.info("   - 可通过 /api/signals/history 查询历史记录")
    logger.info("   - 可通过 /api/signals/today 查询今日记录")


if __name__ == "__main__":
    test_signal_storage()
