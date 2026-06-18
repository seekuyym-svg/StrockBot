# -*- coding: utf-8 -*-
"""
批量更新所有参考指数本地数据

从 config.yaml 的 trade_decision.indices 读取所有 enabled 的指数，
逐个执行增量更新，一次命令搞定。

支持两种运行模式：
- 即时运行：直接执行更新（默认）
- 守护模式：注册定时任务，每个交易日 20:50 自动更新

使用示例:
    # 立即更新一次
    python trade_decision/update_indices.py

    # 启动定时守护（每交易日 20:50 自动更新）
    python trade_decision/update_indices.py --daemon

配置参考（config.yaml）:
    trade_decision:
      indices:
        - name: "沪深300"
          code: "1.000300"
          data_file: "data/index_hs300.csv"
          enabled: true
        - name: "科创综指"
          code: "1.000680"
          data_file: "data/index_kc.csv"
          enabled: true
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
import yaml
import pandas as pd

# 确保能导入 update_index_data
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from trade_decision.update_index_data import update_index_data


# ==================== 交易日历缓存 ====================

_trading_days_cache = None


def _load_trading_calendar():
    """
    加载A股交易日历（带缓存）

    使用 akshare 获取，失败时仅按周末过滤降级。
    """
    global _trading_days_cache
    if _trading_days_cache is not None:
        return _trading_days_cache

    try:
        import akshare as ak
        trade_dates_df = ak.tool_trade_date_hist_sina()
        if trade_dates_df is not None and not trade_dates_df.empty:
            _trading_days_cache = pd.to_datetime(trade_dates_df['trade_date']).tolist()
            return _trading_days_cache
    except Exception:
        pass

    return None


def is_trading_day(check_date=None) -> bool:
    """
    判断指定日期是否为A股交易日

    使用 akshare 交易日历判断，失败时降级为仅过滤周末。
    """
    if check_date is None:
        check_date = datetime.now()
    if isinstance(check_date, str):
        check_date = pd.to_datetime(check_date)

    cal = _load_trading_calendar()
    if cal:
        check_date_only = check_date.replace(hour=0, minute=0, second=0, microsecond=0)
        return check_date_only in cal

    # 降级：仅过滤周末
    return check_date.weekday() < 5


# ==================== 配置加载 ====================

def load_indices_config() -> list:
    """从 config.yaml 加载所有 enabled 的指数配置"""
    config_file = project_root / "config.yaml"
    if not config_file.exists():
        print(f"❌ config.yaml 不存在")
        return []

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            full_config = yaml.safe_load(f)

        indices = full_config.get('trade_decision', {}).get('indices', [])
        enabled = [ic for ic in indices if ic.get('enabled', True)]

        if not enabled:
            print("⚠️  trade_decision.indices 中没有启用的指数")

        return enabled

    except Exception as e:
        print(f"❌ 读取配置失败: {e}")
        return []


# ==================== 核心更新逻辑 ====================

def run_all() -> bool:
    """
    执行所有 enabled 指数的数据更新

    Returns:
        bool: 是否全部成功
    """
    print("=" * 80)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"  📊 批量更新参考指数数据 — {now}")
    print("=" * 80)

    indices = load_indices_config()
    if not indices:
        print("\n💡 请先在 config.yaml 的 trade_decision.indices 中配置指数")
        return False

    success_count = 0
    fail_count = 0

    for i, ic in enumerate(indices, 1):
        name = ic['name']
        secid = ic['code']
        data_file = ic.get('data_file')
        print(f"\n[{i}/{len(indices)}] {name} ({secid})")

        ok = update_index_data(
            index_name=name,
            secid=secid,
            output_path=data_file,
        )

        if ok:
            success_count += 1
        else:
            fail_count += 1

    print()
    print("=" * 80)
    print(f"  ✅ 完成: {success_count} 个成功", end="")
    if fail_count > 0:
        print(f"  ⚠️  {fail_count} 个失败")
    else:
        print()
    print("=" * 80)

    return fail_count == 0


# ==================== 守护模式 ====================

def _scheduled_update():
    """定时任务回调：仅在交易日执行更新 + 生成大盘信号"""
    today_str = datetime.now().strftime('%Y-%m-%d')
    weekday_map = {0: '周一', 1: '周二', 2: '周三', 3: '周四',
                   4: '周五', 5: '周六', 6: '周日'}
    weekday_str = weekday_map[datetime.now().weekday()]

    if not is_trading_day():
        print(f"\n[SKIP] [{today_str}] {weekday_str} 非交易日，跳过数据更新\n")
        return

    print(f"\n[UPDATE] [{today_str}] {weekday_str} 交易日，开始更新指数数据\n")
    success = run_all()

    if not success:
        print(f"\n[WARN] 指数数据更新有失败，继续尝试生成大盘信号...\n")

    # 生成当日大盘环境信号并存入 signal_history.json
    print(f"\n[SIGNAL] 正在生成当日大盘环境信号...\n")
    try:
        from trade_decision.market_signal import check_market_signal, save_signal_history
        result = check_market_signal()
        save_signal_history(result)
        passed = result.get('passed', False)
        reasons = result.get('reasons', [])
        print(f"\n[SIGNAL] 大盘环境信号: {'✅ 允许买入' if passed else '❌ 禁止买入'}")
        if reasons:
            for r in reasons:
                print(f"         原因: {r}")
    except Exception as e:
        print(f"\n[ERROR] 生成大盘信号失败: {e}\n")


def start_daemon():
    """
    启动守护模式：注册定时任务，每交易日 20:50 自动更新

    使用 apscheduler 在后台运行，持续监听定时触发。
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        print("❌ 请先安装 apscheduler: pip install apscheduler")
        return

    # 预加载交易日历
    cal = _load_trading_calendar()
    if cal:
        print(f"[OK] 已加载 {len(cal)} 个交易日至缓存")
    else:
        print("[WARN] 交易日历加载失败，降级为仅过滤周末")

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=_scheduled_update,
        trigger=CronTrigger(hour=20, minute=50, timezone='Asia/Shanghai'),
        id='index_data_update_job',
        name='指数数据定时更新',
        replace_existing=True,
    )

    scheduler.start()
    print(f"\n{'=' * 60}")
    print(f"  [DAEMON] 指数数据定时更新守护已启动")
    print(f"  每个交易日 20:50 自动更新")
    print(f"  按 Ctrl+C 停止")
    print(f"{'=' * 60}")

    try:
        from apscheduler.schedulers.base import STATE_RUNNING
        import time

        heartbeat_interval = 600  # 10分钟
        heartbeat_count = 0

        while scheduler.state == STATE_RUNNING:
            time.sleep(heartbeat_interval)
            heartbeat_count += 1
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"[HEARTBEAT] {now} 守护运行中... (第{heartbeat_count}次心跳)")
    except KeyboardInterrupt:
        print("\n\n[STOP] 收到停止信号，正在关闭...")
        scheduler.shutdown()
        print("[OK] 定时更新守护已停止")


# ==================== CLI ====================

def main():
    parser = argparse.ArgumentParser(
        description="批量更新参考指数数据（支持即时运行和定时守护）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python trade_decision/update_indices.py               # 立即更新一次
  python trade_decision/update_indices.py --daemon       # 启动定时守护
        """
    )
    parser.add_argument('--daemon', action='store_true',
                        help='启动守护模式，每个交易日 20:50 自动更新')

    args = parser.parse_args()

    if args.daemon:
        start_daemon()
    else:
        run_all()


if __name__ == "__main__":
    main()
