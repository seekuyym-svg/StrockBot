"""
回测收益率计算工具

基于通达信本地数据，计算股票池在指定日期或区间的收益率。
支持单日收益率和区间收益率两种计算模式。

使用示例:
    # 计算单日收益率
    python backtest/calc_backtest_rate.py --date 2026-04-20 --pooldate 20260420
    
    # 计算区间收益率
    python backtest/calc_backtest_rate.py --start 2026-04-20 --end 2026-04-22 --pooldate 20260420
    
    # 同时计算单日和区间收益
    python backtest/calc_backtest_rate.py --date 2026-04-20 --start 2026-04-20 --end 2026-04-22 --pooldate 20260420
    
    # 自定义初始资金
    python backtest/calc_backtest_rate.py --date 2026-04-20 --pooldate 20260420 --capital 200000
"""

import pandas as pd
from datetime import datetime
import os
import sys
import yaml
import argparse
from pathlib import Path
from typing import List, Dict, Optional

# 添加 local 目录到路径，以便导入 utils 模块
project_root = Path(__file__).parent.parent  # backtest/ -> 项目根目录
sys.path.insert(0, str(project_root / 'local'))  # 添加 StockBot/local/ 到路径
from utils import get_stock_name  # 从 local/utils.py 导入股票名称获取函数
from mootdx.reader import Reader


# ==================== 配置区 ====================
def load_config():
    """加载配置文件"""
    config_path = project_root / 'config.yaml'
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"⚠️  加载配置文件失败: {e}，使用默认配置")
        return {}

config = load_config()
TDX_DIR = config.get('TDX_DIR', r"D:\Install\zd_zxzq_gm")  # 通达信安装目录（从配置文件读取）
DATA_DIR = project_root / "data"  # 报告输出目录（项目根目录下的data文件夹）

# 从 config.yaml 的 backtest 节点读取初始资金，命令行参数可覆盖
BACKTEST_CONFIG = config.get('backtest', {})
DEFAULT_INITIAL_CAPITAL = BACKTEST_CONFIG.get('initial_capital', 100000)


def load_stock_pool(pooldate: str) -> List[Dict[str, str]]:
    """
    从 data/stockpool_YYYYMMDD.txt 读取股票池（带评分过滤）
    
    Args:
        pooldate: 股票池日期，格式 YYYYMMDD
    
    Returns:
        [{'code': '603768', 'market': 'sh'}, ...]
    
    Raises:
        FileNotFoundError: 股票池文件不存在
    """
    stockpool_file = DATA_DIR / f"stockpool_{pooldate}.txt"
    
    if not stockpool_file.exists():
        raise FileNotFoundError(f"❌ 股票池文件不存在: {stockpool_file}")
    
    # 从配置文件读取最低评分阈值
    min_score = BACKTEST_CONFIG.get('backtest_minscore', 1.0)
    
    watchlist = []
    total_count = 0
    no_score_count = 0
    low_score_count = 0
    
    try:
        with open(stockpool_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                
                # 跳过空行和注释行
                if not line or line.startswith('#'):
                    continue
                
                # 按逗号分割
                parts = line.split(',')
                if not parts:
                    continue
                
                code = parts[0].strip()
                
                # 验证股票代码格式（6位数字）
                if not code.isdigit() or len(code) != 6:
                    continue
                
                total_count += 1
                
                # 检查是否有评分数据
                if len(parts) < 2:
                    # 没有评分数据，过滤掉
                    no_score_count += 1
                    continue
                
                # 解析评分
                try:
                    score = float(parts[1].strip())
                except ValueError:
                    # 评分格式错误，过滤掉
                    no_score_count += 1
                    continue
                
                # 评分过滤
                if score < min_score:
                    low_score_count += 1
                    continue
                
                # 根据代码首位判断市场
                if code.startswith('6') or code.startswith('9'):
                    market = 'sh'
                elif code.startswith('0') or code.startswith('3'):
                    market = 'sz'
                else:
                    market = 'bj'
                
                watchlist.append({
                    'code': code,
                    'market': market
                })
        
        # 输出统计信息
        filtered_count = no_score_count + low_score_count
        print(f"✅ 成功读取股票池: {len(watchlist)} 只股票")
        if filtered_count > 0:
            print(f"   📊 过滤统计: 共 {total_count} 只，过滤 {filtered_count} 只")
            if no_score_count > 0:
                print(f"      - 无评分数据: {no_score_count} 只")
            if low_score_count > 0:
                print(f"      - 评分低于 {min_score}: {low_score_count} 只")
        
        return watchlist
        
    except Exception as e:
        print(f"❌ 读取股票池文件失败: {e}")
        raise


def ensure_data_dir():
    """确保data目录存在"""
    if not DATA_DIR.exists():
        DATA_DIR.mkdir(parents=True)
        print(f"✅ 创建目录: {DATA_DIR}")


def save_report_to_file(content: str, filename: str):
    """
    将报告内容保存到文件
    
    Args:
        content: 报告内容字符串
        filename: 文件名（不含路径）
    """
    ensure_data_dir()
    filepath = DATA_DIR / filename
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"\n💾 报告已保存至: {filepath}")
        return True
    except Exception as e:
        print(f"❌ 保存报告失败: {e}")
        return False


def format_single_day_report(target_date: str, results: list, total_investment: float, 
                             total_value_at_close: float, total_return_rate: float, 
                             total_profit_loss: float, winners: list, losers: list, flat: list,
                             initial_capital: float, idle_capital: float = 0.0, 
                             capital_utilization_rate: float = 0.0):
    """格式化单日收益率报告"""
    lines = []
    lines.append("=" * 80)
    lines.append(f"📊 单日收益率计算报告")
    lines.append(f"📅 目标日期: {target_date}")
    lines.append(f"💰 初始资金: {initial_capital:,} 元")
    lines.append(f"📈 股票数量: {len(results)} 只")
    lines.append(f"⏰ 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 80)
    lines.append("")
    
    # 个股详情
    for r in sorted(results, key=lambda x: x['return_rate'], reverse=True):
        status = "🟢" if r['return_rate'] > 0 else "🔴" if r['return_rate'] < 0 else "⚪"
        lines.append(f"{status} {r['code']} ({r['name']})")
        lines.append(f"   开盘价: {r['open_price']:.2f} 元")
        lines.append(f"   收盘价: {r['close_price']:.2f} 元")
        lines.append(f"   买入股数: {r['shares']} 股")
        lines.append(f"   投入金额: {r['investment']:,.2f} 元")
        lines.append(f"   收盘市值: {r['value_at_close']:,.2f} 元")
        lines.append(f"   收益率: {r['return_rate']:+.2f}%")
        lines.append(f"   盈亏: {r['profit_loss']:+,.2f} 元")
        lines.append("")
    
    # 汇总信息
    lines.append("=" * 80)
    lines.append("📊 汇总报告")
    lines.append("=" * 80)
    lines.append(f"💰 总投入金额: {total_investment:,.2f} 元")
    lines.append(f"📈 总市值（收盘）: {total_value_at_close:,.2f} 元")
    lines.append(f"📊 综合收益率: {total_return_rate:+.2f}%")
    lines.append(f"💵 总盈亏: {total_profit_loss:+,.2f} 元")
    lines.append("")
    
    # ========== 新增：资金使用率诊断 ==========
    lines.append("=" * 80)
    lines.append("💹 资金使用率诊断")
    lines.append("=" * 80)
    lines.append(f"💰 初始资金: {initial_capital:,.2f} 元")
    lines.append(f"✅ 实际投入: {total_investment:,.2f} 元")
    lines.append(f"⏸️ 闲置资金: {idle_capital:,.2f} 元")
    lines.append(f"📊 资金使用率: {capital_utilization_rate:.2f}%")
    lines.append("")
    
    if capital_utilization_rate < 80:
        lines.append("⚠️  警告: 资金使用率低于 80%，存在较多闲置资金")
        lines.append("💡 建议:")
        lines.append("   1. 增加初始资金规模，使每只股票能买入至少100股")
        lines.append("   2. 减少选股数量，集中资金到更少的股票")
        lines.append("   3. 过滤掉高价股（股价 > 初始资金/股票数/100）")
        lines.append("")
    elif capital_utilization_rate < 95:
        lines.append("ℹ️  提示: 资金使用率在 80%-95% 之间，有少量闲置资金")
        lines.append("💡 这是正常现象，由于100股整数倍限制导致")
        lines.append("")
    else:
        lines.append("✅ 资金使用率良好 (>95%)")
        lines.append("")
    
    lines.append(f"🟢 上涨: {len(winners)} 只")
    lines.append(f"🔴 下跌: {len(losers)} 只")
    lines.append(f"⚪ 持平: {len(flat)} 只")
    lines.append("")
    
    # 最佳和最差表现
    if winners:
        best = max(winners, key=lambda x: x['return_rate'])
        lines.append(f"🏆 最佳表现: {best['code']} ({best['name']}) {best['return_rate']:+.2f}%")
    
    if losers:
        worst = min(losers, key=lambda x: x['return_rate'])
        lines.append(f"📉 最差表现: {worst['code']} ({worst['name']}) {worst['return_rate']:+.2f}%")
    
    lines.append("")
    lines.append("=" * 80)
    lines.append("📋 详细数据表")
    lines.append("=" * 80)
    lines.append(f"{'代码':<10} {'名称':<15} {'开盘价':>8} {'收盘价':>8} {'收益率':>10} {'盈亏':>12}")
    lines.append("-" * 80)
    
    for r in sorted(results, key=lambda x: x['return_rate'], reverse=True):
        lines.append(f"{r['code']:<10} {r['name']:<15} {r['open_price']:>8.2f} {r['close_price']:>8.2f} {r['return_rate']:>+9.2f}% {r['profit_loss']:>+11,.2f}")
    
    lines.append("")
    lines.append("=" * 80)
    lines.append("✅ 计算完成！")
    lines.append("=" * 80)
    
    return "\n".join(lines)


def format_period_report(start_date: str, end_date: str, results: list, total_investment: float,
                         total_value_at_end: float, total_return_rate: float, total_profit_loss: float,
                         winners: list, losers: list, flat: list, initial_capital: float,
                         idle_capital: float = 0.0, capital_utilization_rate: float = 0.0):
    """格式化区间收益率报告"""
    lines = []
    lines.append("=" * 80)
    lines.append(f"📊 区间收益率计算报告")
    lines.append(f"📅 起始日期: {start_date} (开盘买入)")
    lines.append(f"📅 结束日期: {end_date} (收盘卖出)")
    lines.append(f"💰 初始资金: {initial_capital:,} 元")
    lines.append(f"📈 股票数量: {len(results)} 只")
    lines.append(f"⏰ 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 80)
    lines.append("")
    
    # 个股详情
    for r in sorted(results, key=lambda x: x['return_rate'], reverse=True):
        status = "🟢" if r['return_rate'] > 0 else "🔴" if r['return_rate'] < 0 else "⚪"
        lines.append(f"{status} {r['code']} ({r['name']})")
        lines.append(f"   买入价 ({start_date}开盘): {r['buy_price']:.2f} 元")
        lines.append(f"   卖出价 ({end_date}收盘): {r['sell_price']:.2f} 元")
        lines.append(f"   买入股数: {r['shares']} 股")
        lines.append(f"   投入金额: {r['investment']:,.2f} 元")
        lines.append(f"   期末市值: {r['value_at_end']:,.2f} 元")
        lines.append(f"   区间收益率: {r['return_rate']:+.2f}%")
        lines.append(f"   价格涨跌幅: {r['price_change_pct']:+.2f}%")
        lines.append(f"   盈亏: {r['profit_loss']:+,.2f} 元")
        lines.append("")
    
    # 汇总信息
    lines.append("=" * 80)
    lines.append("📊 汇总报告")
    lines.append("=" * 80)
    lines.append(f"💰 总投入金额: {total_investment:,.2f} 元")
    lines.append(f"📈 期末总市值: {total_value_at_end:,.2f} 元")
    lines.append(f"📊 综合收益率: {total_return_rate:+.2f}%")
    lines.append(f"💵 总盈亏: {total_profit_loss:+,.2f} 元")
    lines.append("")
    
    # ========== 新增：资金使用率诊断 ==========
    lines.append("=" * 80)
    lines.append("💹 资金使用率诊断")
    lines.append("=" * 80)
    lines.append(f"💰 初始资金: {initial_capital:,.2f} 元")
    lines.append(f"✅ 实际投入: {total_investment:,.2f} 元")
    lines.append(f"⏸️ 闲置资金: {idle_capital:,.2f} 元")
    lines.append(f"📊 资金使用率: {capital_utilization_rate:.2f}%")
    lines.append("")
    
    if capital_utilization_rate < 80:
        lines.append("⚠️  警告: 资金使用率低于 80%，存在较多闲置资金")
        lines.append("💡 建议:")
        lines.append("   1. 增加初始资金规模，使每只股票能买入至少100股")
        lines.append("   2. 减少选股数量，集中资金到更少的股票")
        lines.append("   3. 过滤掉高价股（股价 > 初始资金/股票数/100）")
        lines.append("")
    elif capital_utilization_rate < 95:
        lines.append("ℹ️  提示: 资金使用率在 80%-95% 之间，有少量闲置资金")
        lines.append("💡 这是正常现象，由于100股整数倍限制导致")
        lines.append("")
    else:
        lines.append("✅ 资金使用率良好 (>95%)")
        lines.append("")
    
    lines.append(f"🟢 盈利: {len(winners)} 只")
    lines.append(f"🔴 亏损: {len(losers)} 只")
    lines.append(f"⚪ 持平: {len(flat)} 只")
    lines.append("")
    
    # 最佳和最差表现
    if winners:
        best = max(winners, key=lambda x: x['return_rate'])
        lines.append(f"🏆 最佳表现: {best['code']} ({best['name']}) {best['return_rate']:+.2f}%")
    
    if losers:
        worst = min(losers, key=lambda x: x['return_rate'])
        lines.append(f"📉 最差表现: {worst['code']} ({worst['name']}) {worst['return_rate']:+.2f}%")
    
    lines.append("")
    lines.append("=" * 80)
    lines.append("📋 详细数据表")
    lines.append("=" * 80)
    lines.append(f"{'代码':<10} {'名称':<15} {'买入价':>8} {'卖出价':>8} {'收益率':>10} {'盈亏':>12}")
    lines.append("-" * 80)
    
    for r in sorted(results, key=lambda x: x['return_rate'], reverse=True):
        lines.append(f"{r['code']:<10} {r['name']:<15} {r['buy_price']:>8.2f} {r['sell_price']:>8.2f} {r['return_rate']:>+9.2f}% {r['profit_loss']:>+11,.2f}")
    
    lines.append("")
    lines.append("=" * 80)
    lines.append("✅ 计算完成！")
    lines.append("=" * 80)
    
    return "\n".join(lines)


def calculate_single_day_returns(target_date: str, watchlist: list, initial_capital: float):
    """
    计算指定日期的单日收益率
    
    Args:
        target_date: 目标日期，格式 YYYY-MM-DD
        watchlist: 股票列表 [{'code': '603768', 'market': 'sh'}, ...]
        initial_capital: 初始资金
    """
    print("=" * 80)
    print(f"📊 单日收益率计算工具")
    print(f"📅 目标日期: {target_date}")
    print(f"💰 初始资金: {initial_capital:,} 元")
    print(f"📈 股票数量: {len(watchlist)} 只")
    print("=" * 80)
    
    # 初始化Reader
    reader = Reader.factory(market='std', tdxdir=TDX_DIR)
    
    results = []
    total_investment = 0
    total_value_at_close = 0
    
    for idx, stock in enumerate(watchlist, 1):
        code = stock['code']
        market = stock['market']
        
        try:
            # 获取股票名称
            stock_name = get_stock_name(code)
            
            # 读取日线数据
            df = reader.daily(symbol=code)
            
            if df is None or df.empty:
                print(f"[{idx}/{len(watchlist)}] ⚠️  {code} ({stock_name}): 无交易数据，跳过")
                continue
            
            # 将索引转换为datetime
            df.index = pd.to_datetime(df.index)
            
            # 查找目标日期的数据
            target_date_dt = pd.to_datetime(target_date)
            
            if target_date_dt not in df.index:
                print(f"[{idx}/{len(watchlist)}] ⚠️  {code} ({stock_name}): {target_date} 无交易数据（可能是非交易日），跳过")
                continue
            
            # 获取该日数据
            day_data = df.loc[target_date_dt]
            
            # 提取开盘价和收盘价
            open_price = float(day_data['open'])
            close_price = float(day_data['close'])
            
            # 计算每只股票的投入金额（平均分配）
            investment_per_stock = initial_capital / len(watchlist)
            
            # 计算买入股数（向下取整到100的整数倍）
            raw_shares = int(investment_per_stock / open_price)
            shares_bought = (raw_shares // 100) * 100  # 确保是100的整数倍
            
            # 如果不足100股，跳过
            if shares_bought < 100:
                print(f"[{idx}/{len(watchlist)}] ⚠️  {code} ({stock_name}): 股价过高，不足100股，跳过")
                continue
            
            # 实际投入金额
            actual_investment = shares_bought * open_price
            
            # 收盘时的市值
            value_at_close = shares_bought * close_price
            
            # 收益率
            return_rate = (value_at_close - actual_investment) / actual_investment * 100
            
            # 盈亏金额
            profit_loss = value_at_close - actual_investment
            
            results.append({
                'code': code,
                'name': stock_name,
                'open_price': open_price,
                'close_price': close_price,
                'shares': shares_bought,
                'investment': actual_investment,
                'value_at_close': value_at_close,
                'return_rate': return_rate,
                'profit_loss': profit_loss
            })
            
            total_investment += actual_investment
            total_value_at_close += value_at_close
            
            print(f"[{idx}/{len(watchlist)}] ✅ {code} ({stock_name}): 收益率 {return_rate:+.2f}%")
            
        except Exception as e:
            print(f"[{idx}/{len(watchlist)}] ❌ {code}: 处理失败 - {e}")
    
    # 汇总结果
    if results:
        total_return_rate = (total_value_at_close - total_investment) / total_investment * 100
        total_profit_loss = total_value_at_close - total_investment
        
        # ========== 新增：资金使用率诊断 ==========
        # 理论应投入总额 = 初始资金（如果所有股票都能买入）
        theoretical_investment = initial_capital
        # 实际闲置资金
        idle_capital = initial_capital - total_investment
        # 资金使用率
        capital_utilization_rate = (total_investment / theoretical_investment * 100) if theoretical_investment > 0 else 0
        
        # 统计涨跌情况
        winners = [r for r in results if r['return_rate'] > 0]
        losers = [r for r in results if r['return_rate'] < 0]
        flat = [r for r in results if r['return_rate'] == 0]
        
        # 生成报告内容
        report_content = format_single_day_report(
            target_date, results, total_investment, total_value_at_close,
            total_return_rate, total_profit_loss, winners, losers, flat,
            initial_capital, idle_capital, capital_utilization_rate
        )
        
        # 打印报告到控制台
        print("\n" + report_content)
        
        # 生成文件名：report_YYYYMMDD.txt
        date_str = target_date.replace('-', '')
        filename = f"report_{date_str}.txt"
        save_report_to_file(report_content, filename)
    else:
        print("\n" + "=" * 80)
        print("✅ 计算完成！(无有效数据)")
        print("=" * 80)


def calculate_period_returns(start_date: str, end_date: str, watchlist: list, initial_capital: float):
    """
    计算指定区间的累计收益率
    
    Args:
        start_date: 起始日期，格式 YYYY-MM-DD（开盘买入）
        end_date: 结束日期，格式 YYYY-MM-DD（收盘卖出）
        watchlist: 股票列表 [{'code': '603768', 'market': 'sh'}, ...]
        initial_capital: 初始资金
    """
    print("=" * 80)
    print(f"📊 区间收益率计算工具")
    print(f"📅 起始日期: {start_date} (开盘买入)")
    print(f"📅 结束日期: {end_date} (收盘卖出)")
    print(f"💰 初始资金: {initial_capital:,} 元")
    print(f"📈 股票数量: {len(watchlist)} 只")
    print("=" * 80)
    
    # 初始化Reader
    reader = Reader.factory(market='std', tdxdir=TDX_DIR)
    
    results = []
    total_investment = 0
    total_value_at_end = 0
    
    for idx, stock in enumerate(watchlist, 1):
        code = stock['code']
        market = stock['market']
        
        try:
            # 获取股票名称
            stock_name = get_stock_name(code)
            
            # 读取日线数据
            df = reader.daily(symbol=code)
            
            if df is None or df.empty:
                print(f"[{idx}/{len(watchlist)}] ⚠️  {code} ({stock_name}): 无交易数据，跳过")
                continue
            
            # 将索引转换为datetime
            df.index = pd.to_datetime(df.index)
            
            # 查找起始日期和结束日期的数据
            start_date_dt = pd.to_datetime(start_date)
            end_date_dt = pd.to_datetime(end_date)
            
            if start_date_dt not in df.index:
                print(f"[{idx}/{len(watchlist)}] ⚠️  {code} ({stock_name}): {start_date} 无交易数据，跳过")
                continue
            
            if end_date_dt not in df.index:
                print(f"[{idx}/{len(watchlist)}] ⚠️  {code} ({stock_name}): {end_date} 无交易数据，跳过")
                continue
            
            # 获取起始日和结束日数据
            start_data = df.loc[start_date_dt]
            end_data = df.loc[end_date_dt]
            
            # 提取价格
            buy_price = float(start_data['open'])      # 起始日开盘价买入
            sell_price = float(end_data['close'])       # 结束日收盘价卖出
            
            # 计算每只股票的投入金额（平均分配）
            investment_per_stock = initial_capital / len(watchlist)
            
            # 计算买入股数（向下取整到100的整数倍）
            raw_shares = int(investment_per_stock / buy_price)
            shares_bought = (raw_shares // 100) * 100  # 确保是100的整数倍
            
            # 如果不足100股，跳过
            if shares_bought < 100:
                print(f"[{idx}/{len(watchlist)}] ⚠️  {code} ({stock_name}): 股价过高，不足100股，跳过")
                continue
            
            # 实际投入金额
            actual_investment = shares_bought * buy_price
            
            # 结束时的市值
            value_at_end = shares_bought * sell_price
            
            # 区间收益率
            return_rate = (value_at_end - actual_investment) / actual_investment * 100
            
            # 盈亏金额
            profit_loss = value_at_end - actual_investment
            
            # 计算区间涨跌幅（仅价格变化）
            price_change_pct = (sell_price - buy_price) / buy_price * 100
            
            results.append({
                'code': code,
                'name': stock_name,
                'buy_price': buy_price,
                'sell_price': sell_price,
                'shares': shares_bought,
                'investment': actual_investment,
                'value_at_end': value_at_end,
                'return_rate': return_rate,
                'price_change_pct': price_change_pct,
                'profit_loss': profit_loss
            })
            
            total_investment += actual_investment
            total_value_at_end += value_at_end
            
            print(f"[{idx}/{len(watchlist)}] ✅ {code} ({stock_name}): 收益率 {return_rate:+.2f}%")
            
        except Exception as e:
            print(f"[{idx}/{len(watchlist)}] ❌ {code}: 处理失败 - {e}")
    
    # 汇总结果
    if results:
        total_return_rate = (total_value_at_end - total_investment) / total_investment * 100
        total_profit_loss = total_value_at_end - total_investment
        
        # ========== 新增：资金使用率诊断 ==========
        # 理论应投入总额 = 初始资金（如果所有股票都能买入）
        theoretical_investment = initial_capital
        # 实际闲置资金
        idle_capital = initial_capital - total_investment
        # 资金使用率
        capital_utilization_rate = (total_investment / theoretical_investment * 100) if theoretical_investment > 0 else 0
        
        # 统计涨跌情况
        winners = [r for r in results if r['return_rate'] > 0]
        losers = [r for r in results if r['return_rate'] < 0]
        flat = [r for r in results if r['return_rate'] == 0]
        
        # 生成报告内容
        report_content = format_period_report(
            start_date, end_date, results, total_investment, total_value_at_end,
            total_return_rate, total_profit_loss, winners, losers, flat,
            initial_capital, idle_capital, capital_utilization_rate
        )
        
        # 打印报告到控制台
        print("\n" + report_content)
        
        # 生成文件名：report_YYYYMMDD_YYYYMMDD.txt
        start_str = start_date.replace('-', '')
        end_str = end_date.replace('-', '')
        filename = f"report_{start_str}_{end_str}.txt"
        save_report_to_file(report_content, filename)
    else:
        print("\n" + "=" * 80)
        print("✅ 计算完成！(无有效数据)")
        print("=" * 80)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='回测收益率计算工具 - 基于通达信本地数据计算股票池的单日或区间收益率',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 计算单日收益率
  python backtest/calc_backtest_rate.py --date 2026-04-20 --pooldate 20260420
  
  # 计算区间收益率
  python backtest/calc_backtest_rate.py --start 2026-04-20 --end 2026-04-22 --pooldate 20260420
  
  # 同时计算单日和区间收益
  python backtest/calc_backtest_rate.py --date 2026-04-20 --start 2026-04-20 --end 2026-04-22 --pooldate 20260420
  
  # 自定义初始资金
  python backtest/calc_backtest_rate.py --date 2026-04-20 --pooldate 20260420 --capital 200000
        """
    )
    
    parser.add_argument('--date', type=str, help='单日收益率计算日期 (YYYY-MM-DD)')
    parser.add_argument('--start', type=str, help='区间起始日期 (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='区间结束日期 (YYYY-MM-DD)')
    parser.add_argument('--pooldate', type=str, help='股票池日期 (YYYYMMDD)')
    parser.add_argument('--capital', type=float, default=None, help=f'初始资金，默认从config.yaml读取（当前配置: {DEFAULT_INITIAL_CAPITAL:,}）')
    
    args = parser.parse_args()
    
    # 如果没有任何参数，显示帮助信息
    if not any([args.date, args.start, args.end, args.pooldate]):
        parser.print_help()
        sys.exit(0)
    
    # 验证必需参数
    if not args.pooldate:
        print("\n❌ 错误: 必须指定 --pooldate（股票池日期）")
        sys.exit(1)
    
    if not args.date and not (args.start and args.end):
        print("\n❌ 错误: 必须指定 --date（单日）或 --start 和 --end（区间）")
        sys.exit(1)
    
    # 设置初始资金：命令行参数优先，否则使用配置文件中的值
    initial_capital = args.capital if args.capital is not None else DEFAULT_INITIAL_CAPITAL
    
    if args.start and not args.end:
        print("❌ 错误: 指定 --start 时必须同时指定 --end")
        sys.exit(1)
    
    if args.end and not args.start:
        print("❌ 错误: 指定 --end 时必须同时指定 --start")
        sys.exit(1)
    
    # 验证日期格式
    def validate_date(date_str, name):
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            print(f"❌ 错误: {name} 日期格式不正确，应为 YYYY-MM-DD")
            sys.exit(1)
    
    if args.date:
        validate_date(args.date, '--date')
    
    if args.start:
        validate_date(args.start, '--start')
    
    if args.end:
        validate_date(args.end, '--end')
    
    # 验证股票池日期格式
    try:
        datetime.strptime(args.pooldate, '%Y%m%d')
    except ValueError:
        print("❌ 错误: --pooldate 日期格式不正确，应为 YYYYMMDD")
        sys.exit(1)
    
    # 加载股票池
    try:
        watchlist = load_stock_pool(args.pooldate)
    except FileNotFoundError as e:
        print(str(e))
        sys.exit(1)
    
    if not watchlist:
        print("❌ 错误: 股票池为空")
        sys.exit(1)
    
    # 执行计算
    if args.date:
        calculate_single_day_returns(args.date, watchlist, initial_capital)
    
    if args.start and args.end:
        if args.date:
            print("\n\n")
        calculate_period_returns(args.start, args.end, watchlist, initial_capital)


if __name__ == "__main__":
    main()
