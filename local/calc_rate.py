import pandas as pd
from datetime import datetime
import os
import yaml
from pathlib import Path
from utils import get_stock_name  # 导入统一的股票名称获取函数
from mootdx.reader import Reader


# ==================== 配置区 ====================
# 从 config.yaml 读取配置
def load_config():
    """加载配置文件"""
    # 获取当前脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # config.yaml 在项目根目录（local目录的上一级）
    config_path = os.path.join(script_dir, '..', 'config.yaml')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"⚠️  加载配置文件失败: {e}，使用默认配置")
        return {}

config = load_config()
TDX_DIR = config.get('TDX_DIR', r"D:\Install\zd_zxzq_gm")  # 通达信安装目录（从配置文件读取）
INITIAL_CAPITAL = 100000  # 初始资金10万元
DATA_DIR = Path(__file__).parent.parent / "data"  # 报告输出目录（项目根目录下的data文件夹）

"""
# 自选股列表1（0420选股，放量金叉，共8只个股）
watchlist = [
    {'code': '601991', 'market': 'sh'},
    {'code': '603565', 'market': 'sh'},
    {'code': '603606', 'market': 'sh'},
    {'code': '688089', 'market': 'sh'},
    {'code': '688211', 'market': 'sh'},
    {'code': '688392', 'market': 'sh'},
    {'code': '688558', 'market': 'sh'},
    {'code': '688683', 'market': 'sh'}
]
"""

"""
# 自选股列表2（0421选股，仙人指路，共7只个股）
watchlist = [
    {'code': '300179', 'market': 'sz'},
    {'code': '301150', 'market': 'sz'},
    {'code': '301389', 'market': 'sz'},
    {'code': '688146', 'market': 'sh'},
    {'code': '688268', 'market': 'sh'},
    {'code': '688655', 'market': 'sh'},
    {'code': '688707', 'market': 'sh'}  
]
"""

# 自选股列表3（0422选股，持续放量+高评分，共6只个股）
watchlist = [
    {'code': '000526', 'market': 'sz'},
    {'code': '002830', 'market': 'sz'},
    {'code': '003013', 'market': 'sz'},
    {'code': '600963', 'market': 'sh'},
    {'code': '601777', 'market': 'sh'},
    {'code': '688020', 'market': 'sh'}
]

def ensure_data_dir():
    """确保data目录存在"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"✅ 创建目录: {DATA_DIR}")

def save_report_to_file(content: str, filename: str):
    """
    将报告内容保存到文件
    
    Args:
        content: 报告内容字符串
        filename: 文件名（不含路径）
    """
    ensure_data_dir()
    filepath = os.path.join(DATA_DIR, filename)
    
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
                             total_profit_loss: float, winners: list, losers: list, flat: list):
    """格式化单日收益率报告"""
    lines = []
    lines.append("=" * 80)
    lines.append(f"📊 单日收益率计算报告")
    lines.append(f"📅 目标日期: {target_date}")
    lines.append(f"💰 初始资金: {INITIAL_CAPITAL:,} 元")
    lines.append(f"📈 股票数量: {len(watchlist)} 只")
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
                         winners: list, losers: list, flat: list):
    """格式化区间收益率报告"""
    lines = []
    lines.append("=" * 80)
    lines.append(f"📊 区间收益率计算报告")
    lines.append(f"📅 起始日期: {start_date} (开盘买入)")
    lines.append(f"📅 结束日期: {end_date} (收盘卖出)")
    lines.append(f"💰 初始资金: {INITIAL_CAPITAL:,} 元")
    lines.append(f"📈 股票数量: {len(watchlist)} 只")
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

def calculate_single_day_returns(target_date: str):
    """
    计算指定日期的单日收益率
    
    Args:
        target_date: 目标日期，格式 YYYY-MM-DD
    """
    print("=" * 80)
    print(f"📊 单日收益率计算工具")
    print(f"📅 目标日期: {target_date}")
    print(f"💰 初始资金: {INITIAL_CAPITAL:,} 元")
    print(f"📈 股票数量: {len(watchlist)} 只")
    print("=" * 80)
    
    # 初始化Reader
    reader = Reader.factory(market='std', tdxdir=TDX_DIR)
    
    results = []
    total_investment = 0
    total_value_at_close = 0
    
    for stock in watchlist:
        code = stock['code']
        market = stock['market']
        
        try:
            # 获取股票名称
            stock_name = get_stock_name(code)
            
            # 读取日线数据
            df = reader.daily(symbol=code)
            
            if df is None or df.empty:
                print(f"❌ {code} ({stock_name}): 无法读取数据")
                continue
            
            # 将索引转换为datetime
            df.index = pd.to_datetime(df.index)
            
            # 查找目标日期的数据
            target_date_dt = pd.to_datetime(target_date)
            
            if target_date_dt not in df.index:
                print(f"⚠️  {code} ({stock_name}): {target_date} 无交易数据（可能是非交易日）")
                continue
            
            # 获取该日数据
            day_data = df.loc[target_date_dt]
            
            # 提取开盘价和收盘价
            open_price = float(day_data['open'])
            close_price = float(day_data['close'])
            
            # 计算每只股票的投入金额（平均分配）
            investment_per_stock = INITIAL_CAPITAL / len(watchlist)
            
            # 计算买入股数（向下取整）
            shares_bought = int(investment_per_stock / open_price)
            
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
            
        except Exception as e:
            print(f"❌ {code}: 处理失败 - {e}")
            import traceback
            traceback.print_exc()
    
    # 汇总结果
    if results:
        total_return_rate = (total_value_at_close - total_investment) / total_investment * 100
        total_profit_loss = total_value_at_close - total_investment
        
        # 统计涨跌情况
        winners = [r for r in results if r['return_rate'] > 0]
        losers = [r for r in results if r['return_rate'] < 0]
        flat = [r for r in results if r['return_rate'] == 0]
        
        # 生成报告内容
        report_content = format_single_day_report(
            target_date, results, total_investment, total_value_at_close,
            total_return_rate, total_profit_loss, winners, losers, flat
        )
        
        # 打印报告到控制台
        print(report_content)
        
        # 生成文件名：report_YYYYMMDD.txt
        date_str = target_date.replace('-', '')
        filename = f"report_{date_str}.txt"
        save_report_to_file(report_content, filename)
    else:
        print("\n" + "=" * 80)
        print("✅ 计算完成！(无有效数据)")
        print("=" * 80)

def calculate_period_returns(start_date: str, end_date: str):
    """
    计算指定区间的累计收益率
    
    Args:
        start_date: 起始日期，格式 YYYY-MM-DD（开盘买入）
        end_date: 结束日期，格式 YYYY-MM-DD（收盘卖出）
    """
    print("=" * 80)
    print(f"📊 区间收益率计算工具")
    print(f"📅 起始日期: {start_date} (开盘买入)")
    print(f"📅 结束日期: {end_date} (收盘卖出)")
    print(f"💰 初始资金: {INITIAL_CAPITAL:,} 元")
    print(f"📈 股票数量: {len(watchlist)} 只")
    print("=" * 80)
    
    # 初始化Reader
    reader = Reader.factory(market='std', tdxdir=TDX_DIR)
    
    results = []
    total_investment = 0
    total_value_at_end = 0
    
    for stock in watchlist:
        code = stock['code']
        market = stock['market']
        
        try:
            # 获取股票名称
            stock_name = get_stock_name(code)
            
            # 读取日线数据
            df = reader.daily(symbol=code)
            
            if df is None or df.empty:
                print(f"❌ {code} ({stock_name}): 无法读取数据")
                continue
            
            # 将索引转换为datetime
            df.index = pd.to_datetime(df.index)
            
            # 查找起始日期和结束日期的数据
            start_date_dt = pd.to_datetime(start_date)
            end_date_dt = pd.to_datetime(end_date)
            
            if start_date_dt not in df.index:
                print(f"⚠️  {code} ({stock_name}): {start_date} 无交易数据")
                continue
            
            if end_date_dt not in df.index:
                print(f"⚠️  {code} ({stock_name}): {end_date} 无交易数据")
                continue
            
            # 获取起始日和结束日数据
            start_data = df.loc[start_date_dt]
            end_data = df.loc[end_date_dt]
            
            # 提取价格
            buy_price = float(start_data['open'])      # 起始日开盘价买入
            sell_price = float(end_data['close'])       # 结束日收盘价卖出
            
            # 计算每只股票的投入金额（平均分配）
            investment_per_stock = INITIAL_CAPITAL / len(watchlist)
            
            # 计算买入股数（向下取整）
            shares_bought = int(investment_per_stock / buy_price)
            
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
            
        except Exception as e:
            print(f"❌ {code}: 处理失败 - {e}")
            import traceback
            traceback.print_exc()
    
    # 汇总结果
    if results:
        total_return_rate = (total_value_at_end - total_investment) / total_investment * 100
        total_profit_loss = total_value_at_end - total_investment
        
        # 统计涨跌情况
        winners = [r for r in results if r['return_rate'] > 0]
        losers = [r for r in results if r['return_rate'] < 0]
        flat = [r for r in results if r['return_rate'] == 0]
        
        # 生成报告内容
        report_content = format_period_report(
            start_date, end_date, results, total_investment, total_value_at_end,
            total_return_rate, total_profit_loss, winners, losers, flat
        )
        
        # 打印报告到控制台
        print(report_content)
        
        # 生成文件名：report_YYYYMMDD_YYYYMMDD.txt
        start_str = start_date.replace('-', '')
        end_str = end_date.replace('-', '')
        filename = f"report_{start_str}_{end_str}.txt"
        save_report_to_file(report_content, filename)
    else:
        print("\n" + "=" * 80)
        print("✅ 计算完成！(无有效数据)")
        print("=" * 80)

if __name__ == "__main__":
    print("请选择计算模式：")
    print("1. 计算单日收益率")
    print("2. 计算区间收益率")
    print("3. 同时计算单日及区间收益")
    
    choice = input("\n请输入选项 (1/2/3，默认3): ").strip() or "3"
    
    if choice == "1":
        target_date = input("请输入目标日期 (YYYY-MM-DD，默认2026-04-20): ").strip() or "2026-04-20"
        calculate_single_day_returns(target_date)
    
    elif choice == "2":
        start_date = input("请输入起始日期 (YYYY-MM-DD，默认2026-04-20): ").strip() or "2026-04-20"
        end_date = input("请输入结束日期 (YYYY-MM-DD，默认2026-04-22): ").strip() or "2026-04-22"
        calculate_period_returns(start_date, end_date)
    
    elif choice == "3":
        print("\n" + "=" * 80)
        print("开始计算 4月20日 单日收益率...")
        print("=" * 80)
        calculate_single_day_returns("2026-04-20")
        
        print("\n\n")
        print("=" * 80)
        print("开始计算 4月21日 单日收益率...")
        print("=" * 80)
        calculate_single_day_returns("2026-04-21")

        print("\n\n")
        print("=" * 80)
        print("开始计算 4月22日 单日收益率...")
        print("=" * 80)
        calculate_single_day_returns("2026-04-22")
        
        print("\n\n")
        print("=" * 80)
        print("开始计算 4月20日开盘至4月21日收盘 区间收益率...")
        print("=" * 80)
        calculate_period_returns("2026-04-20", "2026-04-22")
    
    else:
        print("❌ 无效选项")