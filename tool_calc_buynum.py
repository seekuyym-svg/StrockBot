import requests
import pandas as pd
from datetime import datetime, timedelta
import os
import yaml
from pathlib import Path

# ==================== 配置区 ====================
# 从 config.yaml 读取配置
def load_config():
    """加载配置文件"""
    # 获取当前脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # config.yaml 在项目根目录（同一级）
    config_path = os.path.join(script_dir, 'config.yaml')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"⚠️  加载配置文件失败: {e}，使用默认配置")
        return {}

config = load_config()
# 从配置文件读取初始资金，如果配置不存在则使用默认值20万
INITIAL_CAPITAL = config.get('initial_capital', 200000)
DATA_DIR = Path(__file__).parent / "data"  # 报告输出目录（项目根目录下的data文件夹）
# 从配置文件读取最低综合评分阈值，优先从buy_order_scheduler.min_score读取，如果不存在则使用默认值0.5
MIN_SCORE = config.get('buy_order_scheduler', {}).get('min_score', 0.5)

def load_stock_pool_from_file():
    """
    从选股结果文件中读取股票列表和评分
    
    Returns:
        list: 包含股票代码、名称和评分的字典列表
              [{'code': '000526', 'name': '学大教育', 'score': 3.5}, ...]
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
        filepath = DATA_DIR / filename
        
        if not filepath.exists():
            print(f"❌ 选股结果文件不存在: {filepath}")
            print(f"💡 提示：请确保已运行 select_stocks_volume.py 生成选股结果")
            return []
        
        print(f"📂 读取选股结果文件: {filepath}")
        
        stocks = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                
                # 跳过注释和空行
                if not line or line.startswith('#') or line.startswith('-'):
                    continue
                
                # 解析格式：股票代码,评分
                parts = line.split(',')
                if len(parts) != 2:
                    continue
                
                code = parts[0].strip()
                score_str = parts[1].strip()
                
                # 处理评分为N/A的情况
                if score_str.upper() == 'N/A':
                    print(f"⚠️  {code}: 评分为N/A，跳过")
                    continue
                
                try:
                    score = float(score_str)
                except ValueError:
                    print(f"⚠️  {code}: 评分格式错误 ({score_str})，跳过")
                    continue
                
                # 确定市场前缀并获取股票名称
                if code.startswith('6') or code.startswith('9'):
                    market = 'sh'
                else:
                    market = 'sz'
                
                # 获取股票名称
                stock_name = get_stock_name(code)
                
                stocks.append({
                    'code': code,
                    'market': market,
                    'name': stock_name,
                    'score': score
                })
        
        print(f"✅ 成功读取 {len(stocks)} 只股票")
        return stocks
        
    except Exception as e:
        print(f"❌ 读取选股结果文件失败: {e}")
        import traceback
        traceback.print_exc()
        return []

def filter_stocks_by_score(stocks: list, min_score: float = MIN_SCORE) -> list:
    """
    根据综合评分过滤股票
    
    Args:
        stocks: 股票列表
        min_score: 最低评分阈值
    
    Returns:
        list: 过滤后的股票列表
    """
    filtered = [s for s in stocks if s['score'] >= min_score]
    
    print(f"\n📊 评分过滤结果:")
    print(f"   原始数量: {len(stocks)} 只")
    print(f"   过滤条件: 评分 >= {min_score}")
    print(f"   符合条件: {len(filtered)} 只")
    
    if filtered:
        print(f"\n📋 符合要求的股票:")
        print("-" * 60)
        for s in sorted(filtered, key=lambda x: x['score'], reverse=True):
            print(f"   {s['code']} {s['name']}: {s['score']:+.1f}分")
    
    return filtered

def get_stock_name(symbol: str) -> str:
    """
    根据股票代码获取股票名称（使用腾讯财经API）
    
    Args:
        symbol: 股票代码（不含市场前缀），如 '000526'
    
    Returns:
        str: 股票名称，获取失败则返回股票代码本身
    """
    try:
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
        print(f"⚠️  获取股票 {symbol} 名称失败: {e}")
        return symbol

def get_stock_realtime_data(code: str, market: str) -> dict:
    """
    从腾讯财经API获取股票实时行情数据
    
    Args:
        code: 股票代码（不含市场前缀）
        market: 市场标识（'sh' 或 'sz'）
    
    Returns:
        包含实时行情数据的字典，失败返回None
    """
    try:
        full_code = f"{market}{code}"
        url = f"http://qt.gtimg.cn/q={full_code}"
        response = requests.get(url, timeout=5)
        response.encoding = 'gbk'
        
        if response.status_code != 200:
            print(f"❌ {code}: HTTP请求失败，状态码 {response.status_code}")
            return None
        
        data_str = response.text.strip()
        if '=' not in data_str:
            print(f"❌ {code}: 响应格式错误")
            return None
        
        content = data_str.split('=')[1].strip('"').strip(';')
        parts = content.split('~')
        
        if len(parts) < 46:
            print(f"❌ {code}: 数据字段不完整")
            return None
        
        # 提取关键字段
        stock_name = parts[1] if len(parts) > 1 else code
        current_price = float(parts[3]) if parts[3] else 0  # 当前价
        prev_close = float(parts[4]) if parts[4] else 0      # 昨收价
        open_price = float(parts[5]) if parts[5] else 0      # 今开价
        high_price = float(parts[33]) if len(parts) > 33 and parts[33] else 0  # 最高价
        low_price = float(parts[34]) if len(parts) > 34 and parts[34] else 0   # 最低价
        volume = int(parts[6]) if parts[6] else 0            # 成交量（手）
        amount = float(parts[37]) if len(parts) > 37 and parts[37] else 0      # 成交额（元）
        change_pct = float(parts[32]) if parts[32] else 0    # 涨跌幅%
        
        return {
            'code': code,
            'name': stock_name,
            'current_price': current_price,
            'prev_close': prev_close,
            'open_price': open_price,
            'high_price': high_price,
            'low_price': low_price,
            'volume': volume,
            'amount': amount,
            'change_pct': change_pct
        }
        
    except Exception as e:
        print(f"❌ {code}: 获取实时数据失败 - {e}")
        return None

def calculate_buy_shares(open_price: float, investment_per_stock: float) -> int:
    """
    计算买入股数（必须是100的倍数）
    
    Args:
        open_price: 开盘价或当前价
        investment_per_stock: 每只股票分配的资金
    
    Returns:
        买入股数（100的倍数），不足100股返回0
    """
    if open_price <= 0:
        return 0
    
    # 计算理论可买股数
    raw_shares = int(investment_per_stock / open_price)
    
    # 向下取整到100的倍数
    shares_bought = (raw_shares // 100) * 100
    
    # 如果不足100股，则不买入
    if shares_bought < 100:
        return 0
    
    return shares_bought

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

def format_buy_report(results: list, total_investment: float, remaining_capital: float, stock_count: int):
    """格式化买入委托报告"""
    lines = []
    lines.append("=" * 80)
    lines.append(f"📊 买入委托计算报告")
    lines.append(f"💰 初始资金: {INITIAL_CAPITAL:,} 元")
    lines.append(f"📈 股票数量: {stock_count} 只")
    lines.append(f"🕒 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 80)
    lines.append("")
    
    # 个股详情
    for r in results:
        status = "🟢" if r['shares'] > 0 else "⚪"
        lines.append(f"{status} {r['code']} ({r['name']}) [评分: {r['score']:+.1f}]")
        lines.append(f"   当前价格: {r['current_price']:.2f} 元")
        lines.append(f"   今日开盘: {r['open_price']:.2f} 元")
        lines.append(f"   涨跌幅: {r['change_pct']:+.2f}%")
        lines.append(f"   建议买入股数: {r['shares']} 股")
        lines.append(f"   委托金额: {r['investment']:,.2f} 元")
        if r['shares'] == 0:
            lines.append(f"   ⚠️  价格过高，资金不足以买入100股")
        lines.append("")
    
    # 汇总信息
    lines.append("=" * 80)
    lines.append("📊 汇总报告")
    lines.append("=" * 80)
    lines.append(f"💰 总委托金额: {total_investment:,.2f} 元")
    lines.append(f"💵 剩余资金: {remaining_capital:,.2f} 元")
    lines.append(f"📊 资金使用率: {(total_investment/INITIAL_CAPITAL*100):.2f}%")
    lines.append("")
    
    # 统计可买入股票数量
    can_buy = [r for r in results if r['shares'] > 0]
    cannot_buy = [r for r in results if r['shares'] == 0]
    
    lines.append(f"🟢 可买入: {len(can_buy)} 只")
    lines.append(f"⚪ 无法买入: {len(cannot_buy)} 只")
    lines.append("")
    
    # 详细表格
    lines.append("=" * 80)
    lines.append("📋 委托明细表")
    lines.append("=" * 80)
    lines.append(f"{'代码':<10} {'名称':<12} {'评分':>6} {'当前价':>8} {'开盘价':>8} {'涨跌幅':>8} {'股数':>8} {'金额':>12}")
    lines.append("-" * 80)
    
    for r in results:
        shares_str = f"{r['shares']}" if r['shares'] > 0 else "0 (不足)"
        lines.append(f"{r['code']:<10} {r['name']:<12} {r['score']:>+5.1f} {r['current_price']:>8.2f} {r['open_price']:>8.2f} {r['change_pct']:>+7.2f}% {shares_str:>8} {r['investment']:>11,.2f}")
    
    lines.append("")
    lines.append("=" * 80)
    lines.append("✅ 计算完成！")
    lines.append("=" * 80)
    
    return "\n".join(lines)

def calculate_buy_orders():
    """
    计算买入委托股数和金额（基于选股结果文件）
    """
    print("=" * 80)
    print(f"📊 买入委托计算工具（基于选股结果）")
    print(f"💰 初始资金: {INITIAL_CAPITAL:,} 元")
    print(f"🎯 最低评分要求: {MIN_SCORE}")
    print(f"🕒 查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # 1. 从选股结果文件读取股票列表
    print("\n🔄 正在读取选股结果文件...")
    all_stocks = load_stock_pool_from_file()
    
    if not all_stocks:
        print("❌ 没有可用的股票数据，退出")
        return
    
    # 2. 根据评分过滤股票
    print("\n🔍 正在根据评分过滤股票...")
    filtered_stocks = filter_stocks_by_score(all_stocks, MIN_SCORE)
    
    if not filtered_stocks:
        print("\n❌ 没有符合评分要求的股票，退出")
        return
    
    # 3. 转换为watchlist格式
    watchlist = [{'code': s['code'], 'market': s['market'], 'name': s['name'], 'score': s['score']} for s in filtered_stocks]
    
    results = []
    total_investment = 0
    
    # 计算每只股票的分配资金
    investment_per_stock = INITIAL_CAPITAL / len(watchlist)
    print(f"\n💡 每只股票分配资金: {investment_per_stock:,.2f} 元\n")
    
    for stock in watchlist:
        code = stock['code']
        market = stock['market']
        name = stock['name']
        score = stock['score']
        
        # 获取实时行情
        realtime_data = get_stock_realtime_data(code, market)
        
        if realtime_data is None:
            print(f"❌ {code}: 无法获取实时数据，跳过")
            continue
        
        current_price = realtime_data['current_price']
        open_price = realtime_data['open_price']
        change_pct = realtime_data['change_pct']
        
        # 计算买入股数（使用当前价格）
        shares_bought = calculate_buy_shares(current_price, investment_per_stock)
        
        # 实际投入金额
        actual_investment = shares_bought * current_price
        
        results.append({
            'code': code,
            'name': name,
            'score': score,
            'current_price': current_price,
            'open_price': open_price,
            'change_pct': change_pct,
            'shares': shares_bought,
            'investment': actual_investment
        })
        
        total_investment += actual_investment
        
        # 打印单只股票结果
        status = "🟢" if shares_bought > 0 else "⚪"
        print(f"{status} {code} ({name}) [评分: {score:+.1f}]")
        print(f"   当前价格: {current_price:.2f} 元")
        print(f"   今日开盘: {open_price:.2f} 元")
        print(f"   涨跌幅: {change_pct:+.2f}%")
        print(f"   建议买入: {shares_bought} 股")
        print(f"   委托金额: {actual_investment:,.2f} 元")
        if shares_bought == 0:
            print(f"   ⚠️  价格过高，{investment_per_stock:,.2f}元不足以买入100股")
        print("")
    
    # 汇总结果
    if results:
        remaining_capital = INITIAL_CAPITAL - total_investment
        usage_rate = (total_investment / INITIAL_CAPITAL * 100) if INITIAL_CAPITAL > 0 else 0
        
        print("=" * 80)
        print("📊 汇总报告")
        print("=" * 80)
        print(f"💰 总委托金额: {total_investment:,.2f} 元")
        print(f"💵 剩余资金: {remaining_capital:,.2f} 元")
        print(f"📊 资金使用率: {usage_rate:.2f}%")
        
        # 统计可买入股票数量
        can_buy = [r for r in results if r['shares'] > 0]
        cannot_buy = [r for r in results if r['shares'] == 0]
        
        print(f"\n🟢 可买入: {len(can_buy)} 只")
        print(f"⚪ 无法买入: {len(cannot_buy)} 只")
        
        # 详细表格
        print("\n" + "=" * 80)
        print("📋 委托明细表")
        print("=" * 80)
        print(f"{'代码':<10} {'名称':<12} {'评分':>6} {'当前价':>8} {'开盘价':>8} {'涨跌幅':>8} {'股数':>8} {'金额':>12}")
        print("-" * 80)
        
        for r in results:
            shares_str = f"{r['shares']}" if r['shares'] > 0 else "0 (不足)"
            print(f"{r['code']:<10} {r['name']:<12} {r['score']:>+5.1f} {r['current_price']:>8.2f} {r['open_price']:>8.2f} {r['change_pct']:>+7.2f}% {shares_str:>8} {r['investment']:>11,.2f}")
        
        # 生成并保存报告
        stock_count = len(results)
        report_content = format_buy_report(results, total_investment, remaining_capital, stock_count)
        
        # 生成文件名：buynum_YYYYMMDD_HHMMSS.txt
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"buynum_{timestamp}.txt"
        save_report_to_file(report_content, filename)
    
    print("\n" + "=" * 80)
    print("✅ 计算完成！")
    print("=" * 80)

if __name__ == "__main__":
    calculate_buy_orders()