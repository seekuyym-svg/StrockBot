# -*- coding: utf-8 -*-
"""
选股策略回测工具 - 主入口

功能：
1. 对 select_daysvol.py 的持续放量选股策略进行历史回测
2. 模拟真实交易过程（次日开盘买入，3个交易日后收盘卖出）
3. 计算各项统计指标并与沪深300对比
4. 生成详细的回测报告和可视化图表

使用方法:
    # 基本用法（使用默认配置）
    python backtest/run_backtest.py
    
    # 自定义回测周期
    python backtest/run_backtest.py --start-date 2021-07-01 --end-date 2021-09-30
    
    # 自定义参数
    python backtest/run_backtest.py --volume-period 5 --hold-days 3
    
    # 指定白名单文件
    python backtest/run_backtest.py --whitelist data/whitelist_20260424.txt
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import argparse
from loguru import logger

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backtest.backtest_engine import BacktestEngine


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="选股策略回测工具 - 验证持续放量选股策略的有效性",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用方式:

1. 生成每日选股股票池（如果还没有生成）
  python backtest/generate_stockpool.py --start-date 2024-01-01 --end-date 2026-01-01

2. 基于股票池进行回测
  python backtest/run_backtest.py --start-date 2024-01-01 --end-date 2026-01-01

3. 启用DEBUG模式查看详细资金明细
  python backtest/run_backtest.py --start-date 2024-01-01 --end-date 2024-01-10 --debug

自定义参数:
  python backtest/run_backtest.py --volume-period 5 --hold-days 3 --min-score 0.6
        """
    )
    
    parser.add_argument('--start-date', type=str, default='2021-01-01',
                       help='回测起始日期 (YYYY-MM-DD)，默认: 2021-01-01')
    parser.add_argument('--end-date', type=str, default='2021-12-31',
                       help='回测结束日期 (YYYY-MM-DD)，默认: 2021-12-31')
    parser.add_argument('--volume-period', type=int, default=5,
                       help='连续放量天数，默认: 5')
    parser.add_argument('--hold-days', type=int, default=3,
                       help='持仓天数（交易日），默认: 3')
    parser.add_argument('--whitelist', type=str, default=None,
                       help='白名单文件路径（可选），默认: 自动查找data目录下最新的whitelist文件')
    parser.add_argument('--tdx-dir', type=str, default=r"D:\Install\zd_zxzq_gm",
                       help='通达信安装目录，默认: D:\\Install\\zd_zxzq_gm')
    parser.add_argument('--output-dir', type=str, default=None,
                       help='输出目录，默认: 项目根目录/data')
    parser.add_argument('--min-score', type=float, default=None,
                       help='最小评分阈值（覆盖配置文件中的backtest.backtest_minscore）')
    parser.add_argument('--debug', action='store_true',
                       help='启用DEBUG日志级别，显示详细的资金明细和调试信息')
    
    args = parser.parse_args()
    
    # 配置日志 - 根据 --debug 参数动态设置日志级别
    log_level = "DEBUG" if args.debug else "INFO"
    logger.remove()
    logger.add(
        sys.stderr, 
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
    )
    logger.add(
        project_root / "data" / "backtest.log",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} | {message}"  # 日志文件保留详细信息
    )
    
    if args.debug:
        logger.info("[DEBUG] DEBUG日志模式已启用")
    
    # 打印欢迎信息
    print("=" * 80)
    print("🎯 选股策略回测工具")
    print("=" * 80)
    print(f"📅 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # 从配置文件读取默认值
    try:
        import yaml
        config_file = project_root / "config.yaml"
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f)
                backtest_config = yaml_config.get('backtest', {})
                default_hold_days = backtest_config.get('hold_days', 3)
                default_volume_period = backtest_config.get('volume_period', 5)
                default_initial_capital = backtest_config.get('initial_capital', 1000000.0)
                default_min_score = backtest_config.get('backtest_minscore', 0.5)
                logger.info(f"[CONFIG] 从配置文件读取默认值: hold_days={default_hold_days}, volume_period={default_volume_period}, min_score={default_min_score}")
            tdx_dir_from_config = yaml_config.get('TDX_DIR', r"D:\Install\zd_zxzq_gm")
        else:
            default_hold_days = 3
            default_volume_period = 5
            default_initial_capital = 1000000.0
            default_min_score = 0.5
            tdx_dir_from_config = r"D:\Install\zd_zxzq_gm"
    except Exception as e:
        logger.warning(f"[WARN] 读取配置文件失败: {e}，使用硬编码默认值")
        default_hold_days = 3
        default_volume_period = 5
        default_initial_capital = 1000000.0
        default_min_score = 0.5
        tdx_dir_from_config = r"D:\Install\zd_zxzq_gm"
    
    # 确定最小评分（命令行参数优先于配置文件）
    min_score = args.min_score if args.min_score is not None else default_min_score
    
    # 构建配置（命令行参数优先，否则使用配置文件默认值）
    config = {
        'start_date': datetime.strptime(args.start_date, '%Y-%m-%d'),
        'end_date': datetime.strptime(args.end_date, '%Y-%m-%d'),
        'volume_period': args.volume_period if args.volume_period != 5 else default_volume_period,
        'hold_days': args.hold_days if args.hold_days != 3 else default_hold_days,
        'whitelist_file': args.whitelist,
        'tdx_dir': args.tdx_dir if args.tdx_dir != r"D:\Install\zd_zxzq_gm" else tdx_dir_from_config,
        'initial_capital': default_initial_capital,
        'min_score': min_score
    }
    
    # 确定输出目录
    output_dir = args.output_dir if args.output_dir else str(project_root / "data")
    
    try:
        # 创建并运行回测引擎
        logger.info("\n[INIT] 初始化回测引擎...")
        engine = BacktestEngine(config)
        
        # 执行回测
        logger.info("\n🚀 开始执行回测...")
        engine.run_backtest()
        
        # 计算指标
        logger.info("\n[CALC] 计算统计指标...")
        
        # ========== 关键：输出每个交易周期的详细信息 ==========
        logger.info("\n" + "="*100)
        logger.info("🔍 【调试模式】详细输出每个交易周期的资金变化")
        logger.info("="*100)
        
        # 调用 calculate_cycle_metrics 来显示详细的周期信息
        cycle_metrics = engine.calculate_cycle_metrics()
        
        # 然后再计算总体指标
        metrics = engine.calculate_metrics()
        
        # 额外输出：验证最终资金是否正确
        if cycle_metrics:
            last_cycle = cycle_metrics[-1]
            logger.info("\n" + "="*100)
            logger.info("✅ 【资金验证】")
            logger.info(f"   初始资金: {engine.initial_capital:,.2f} 元")
            logger.info(f"   最后一个周期期末资金: {last_cycle['final_capital']:,.2f} 元")
            logger.info(f"   最后一个周期累计收益率: {last_cycle['cumulative_return']:+.2f}%")
            logger.info(f"   calculate_metrics计算的总收益率: {metrics.get('total_return', 'N/A'):+.2f}%")
            logger.info(f"   calculate_metrics计算的期末资金: {metrics.get('final_capital', 'N/A'):,.2f} 元")
            
            # 检查是否有巨大差异
            if abs(last_cycle['final_capital'] - metrics.get('final_capital', 0)) > 0.01:
                logger.error(f"   ❌ 警告：两种计算方法得到的期末资金不一致！")
                logger.error(f"      calculate_cycle_metrics: {last_cycle['final_capital']:,.2f}")
                logger.error(f"      calculate_metrics: {metrics.get('final_capital', 0):,.2f}")
            else:
                logger.info(f"   ✅ 两种计算方法一致")
            logger.info("="*100 + "\n")
        
        # 生成报告
        logger.info("\n[REPORT] 生成回测报告...")
        engine.generate_report(output_dir)
        
        print("\n" + "=" * 80)
        print("✅ 回测完成！")
        print("=" * 80)
        print(f"\n📊 详细报告已保存至: {output_dir}")
        print(f"   - 文本报告: 控制台输出")
        print(f"   - 可视化图表: backtest_*.png")
        print(f"   - 交易明细: backtest_trades_*.csv")
        print(f"   - 日志文件: backtest.log")
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️  用户中断回测")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ 回测失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
