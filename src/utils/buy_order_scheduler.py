# -*- coding: utf-8 -*-
"""
买入委托定时任务调度器

功能：
1. 每周一至周五上午9:26自动执行买入委托计算
2. 读取前一日的选股结果文件
3. 生成交易委托明细并保存
4. 通过飞书推送委托明细通知
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.notification import get_feishu_notifier

# 全局调度器实例
_buy_order_scheduler = None


def check_stockpool_file() -> bool:
    """
    检查是否存在前一日的选股结果文件
    
    Returns:
        bool: 文件是否存在
    """
    try:
        # 计算前一天的日期
        yesterday = datetime.now() - timedelta(days=1)
        
        # 如果是周一，前一日是周日，需要追溯到周五
        if yesterday.weekday() == 6:  # 周日
            yesterday = yesterday - timedelta(days=2)
        elif yesterday.weekday() == 5:  # 周六
            yesterday = yesterday - timedelta(days=1)
        
        date_str = yesterday.strftime('%Y%m%d')
        filename = f"stockpool_{date_str}.txt"
        filepath = project_root / "data" / filename
        
        if filepath.exists():
            logger.info(f"[OK] 找到选股结果文件: {filepath}")
            return True
        else:
            logger.warning(f"[WARN] 选股结果文件不存在: {filepath}")
            return False
            
    except Exception as e:
        logger.error(f"[ERROR] 检查选股结果文件失败: {e}")
        return False


def execute_buy_calculation():
    """
    执行买入委托计算并发送飞书通知
    """
    logger.info("=" * 80)
    logger.info(f"[START] 开始执行买入委托计算任务")
    logger.info(f"[TIME] 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    
    # 1. 检查选股结果文件
    logger.info("\n[STEP 1] 检查选股结果文件...")
    if not check_stockpool_file():
        logger.warning("[SKIP] 未找到前一日的选股结果文件，跳过本次执行")
        logger.info("[TIP] 提示：请确保已运行 select_stocks_volume.py 生成选股结果")
        return
    
    # 2. 导入并执行买入计算模块
    logger.info("\n[STEP 2] 执行买入委托计算...")
    try:
        # 动态导入 tool_calc_buynum_simple 模块
        import tool_calc_buynum_simple as buy_module
        
        # 执行买入计算
        buy_module.calculate_buy_orders()
        
        logger.success("[OK] 买入委托计算完成")
        
    except ImportError as e:
        logger.error(f"[ERROR] 导入买入计算模块失败: {e}")
        logger.error("[TIP] 提示：请确保 tool_calc_buynum_simple.py 文件存在于项目根目录")
        return
    except Exception as e:
        logger.error(f"[ERROR] 执行买入计算失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return
    
    # 3. 读取交易报告文件并发送飞书通知
    logger.info("\n[STEP 3] 发送飞书通知...")
    send_trade_notification()


def send_trade_notification():
    """
    读取交易报告文件并通过飞书发送通知
    """
    try:
        # 读取今天的交易报告文件
        date_str = datetime.now().strftime('%Y%m%d')
        filename = f"trade_{date_str}.txt"
        filepath = project_root / "data" / filename
        
        if not filepath.exists():
            logger.warning(f"[WARN] 交易报告文件不存在: {filepath}")
            return
        
        logger.info(f"[FILE] 读取交易报告: {filepath}")
        
        # 解析文件内容
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if len(lines) < 2:
            logger.warning("[WARN] 交易报告文件格式错误")
            return
        
        # 第一行是可买入股票个数
        stock_count = int(lines[0].strip())
        
        if stock_count == 0:
            logger.info("[INFO] 今日没有可买入的股票")
            return
        
        # 构建飞书消息内容
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        content = f"**今日买入委托明细**\n"
        content += f"**时间**: {current_time}\n"
        content += f"**数量**: {stock_count} 只股票\n\n"
        content += f"**━━━━━━━━━━━━━━━**\n\n"
        
        # 解析每只股票的委托明细
        for i, line in enumerate(lines[2:], 1):  # 从第3行开始（跳过表头）
            line = line.strip()
            if not line:
                continue
            
            parts = line.split(',')
            if len(parts) != 4:
                continue
            
            code = parts[0].strip()
            open_price = float(parts[1].strip())
            shares = int(parts[2].strip())
            amount = float(parts[3].strip())
            
            # 获取股票名称
            stock_name = get_stock_name(code)
            
            # 格式化输出
            content += f"**{i}. {stock_name} ({code})**\n"
            content += f"   开盘价: ¥{open_price:.2f}\n"
            content += f"   股数: {shares:,} 股\n"
            content += f"   金额: ¥{amount:,.2f}\n\n"
        
        content += f"**━━━━━━━━━━━━━━━**\n"
        
        # 获取飞书通知器
        notifier = get_feishu_notifier()
        
        if not notifier.enabled:
            logger.warning("[WARN] 飞书通知未启用，跳过发送")
            return
        
        # 构建飞书消息体
        message = {
            "msg_type": "interactive",
            "card": {
                "config": {
                    "wide_screen_mode": True
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": "今日买入委托"
                    },
                    "template": "green"
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": content
                        }
                    },
                    {
                        "tag": "hr"
                    },
                    {
                        "tag": "note",
                        "elements": [
                            {
                                "tag": "plain_text",
                                "content": f"ETF马丁格尔量化交易系统 | {current_time}"
                            }
                        ]
                    }
                ]
            }
        }
        
        # 发送飞书通知
        import requests
        import json
        
        headers = {'Content-Type': 'application/json'}
        response = requests.post(
            notifier.webhook_url,
            headers=headers,
            data=json.dumps(message, ensure_ascii=False).encode('utf-8'),
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('StatusCode') == 0 or result.get('code') == 0:
                logger.success(f"[OK] 飞书通知发送成功: {stock_count} 只股票")
            else:
                error_code = result.get('code', 'unknown')
                error_msg = result.get('msg', '未知错误')
                logger.error(f"[ERROR] 飞书API返回错误 (code: {error_code}): {error_msg}")
        else:
            logger.error(f"[ERROR] 飞书通知发送失败，HTTP状态码: {response.status_code}")
        
    except Exception as e:
        logger.error(f"[ERROR] 发送飞书通知失败: {e}")
        import traceback
        logger.error(traceback.format_exc())


def get_stock_name(symbol: str) -> str:
    """
    根据股票代码获取股票名称（使用腾讯财经API）
    
    Args:
        symbol: 股票代码（不含市场前缀），如 '000526'
    
    Returns:
        str: 股票名称，获取失败则返回股票代码本身
    """
    try:
        import requests
        
        # 判断市场前缀
        if symbol.startswith('6') or symbol.startswith('9'):
            market_prefix = 'sh'
        else:
            market_prefix = 'sz'
        
        # 构建完整代码
        full_code = f"{market_prefix}{symbol}"
        
        # 调用腾讯财经API
        url = f"http://qt.gtimg.cn/q={full_code}"
        response = requests.get(url, timeout=5)
        response.encoding = 'gbk'  # 腾讯财经返回GBK编码
        
        if response.status_code == 200:
            data_str = response.text.strip()
            if '=' in data_str:
                content = data_str.split('=')[1].strip('"').strip(';')
                parts = content.split('~')
                if len(parts) >= 2:
                    stock_name = parts[1]
                    if stock_name and stock_name != '':
                        return stock_name
        
        # 获取失败，返回股票代码
        return symbol
        
    except Exception as e:
        logger.warning(f"⚠️  获取股票 {symbol} 名称失败: {e}")
        return symbol


def start_buy_order_scheduler():
    """
    启动买入委托定时任务调度器
    
    Returns:
        BlockingScheduler: 调度器实例
    """
    global _buy_order_scheduler
    
    if _buy_order_scheduler is not None and _buy_order_scheduler.running:
        logger.warning("⚠️  买入委托调度器已在运行")
        return _buy_order_scheduler
    
    # 从配置文件读取配置
    from src.utils.config import get_config
    config = get_config()
    buy_order_config = config.buy_order_scheduler
    
    logger.info("=" * 80)
    logger.info("[TASK] 买入委托定时任务调度器")
    logger.info("=" * 80)
    logger.info(f"[TIME] 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"[SCHEDULE] 定时任务: 周一至周五 {buy_order_config.hour:02d}:{buy_order_config.minute:02d}")
    logger.info(f"[CONFIG] 最低评分要求: {buy_order_config.min_score}")
    logger.info("=" * 80)
    
    # 创建调度器
    _buy_order_scheduler = BlockingScheduler()
    
    # 添加定时任务：从配置文件读取执行时间
    _buy_order_scheduler.add_job(
        func=execute_buy_calculation,
        trigger=CronTrigger(
            day_of_week='mon-fri',
            hour=buy_order_config.hour,
            minute=buy_order_config.minute
        ),
        id='buy_order_task',
        name='买入委托计算任务',
        misfire_grace_time=300,  # 允许5分钟的误差
        coalesce=True  # 合并错过的执行
    )
    
    logger.info("[OK] 定时任务已注册")
    logger.info("[START] 调度器启动中...")
    
    # 在后台线程中启动（非阻塞）
    import threading
    def run_scheduler():
        try:
            _buy_order_scheduler.start()
        except Exception as e:
            logger.error(f"[ERROR] 调度器运行异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    logger.info("[OK] 买入委托调度器已在后台启动")
    return _buy_order_scheduler


def stop_buy_order_scheduler():
    """停止买入委托定时任务调度器"""
    global _buy_order_scheduler
    
    if _buy_order_scheduler is not None:
        try:
            _buy_order_scheduler.shutdown(wait=False)
            logger.info("[STOP] 买入委托调度器已停止")
        except Exception as e:
            logger.error(f"[ERROR] 停止买入委托调度器失败: {e}")
        finally:
            _buy_order_scheduler = None
    else:
        logger.debug("[INFO] 买入委托调度器未运行")


def main():
    """主函数：独立运行时的入口（阻塞模式）"""
    logger.info("=" * 80)
    logger.info("🎯 买入委托定时任务调度器（独立运行模式）")
    logger.info("=" * 80)
    logger.info(f"📅 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("⏰ 定时任务: 周一至周五 09:26")
    logger.info("=" * 80)
    
    # 创建调度器
    scheduler = BlockingScheduler()
    
    # 添加定时任务：周一至周五上午9:26执行
    scheduler.add_job(
        func=execute_buy_calculation,
        trigger=CronTrigger(day_of_week='mon-fri', hour=9, minute=26),
        id='buy_order_task',
        name='买入委托计算任务',
        misfire_grace_time=300,  # 允许5分钟的误差
        coalesce=True  # 合并错过的执行
    )
    
    logger.info("✅ 定时任务已注册")
    logger.info("🚀 调度器启动中...")
    
    try:
        # 启动调度器（阻塞模式）
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("\n👋 收到中断信号，调度器停止")
    except Exception as e:
        logger.error(f"❌ 调度器运行异常: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    main()
