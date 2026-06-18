import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import requests
import json
import sys

# 设置 UTF-8 编码（解决 Windows 终端 emoji 显示问题）
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# -*- coding: utf-8 -*-
"""
个股多头/空头排列判断模块 - 美股版

功能：
1. 使用 Alpha Vantage API 或 yfinance 获取美股历史K线数据
2. 计算常用移动平均线：MA5、MA10、MA20、MA50、MA200
3. 定义多头/空头判定规则（均线排列 + MACD + RSI + 布林带）
4. 对指定股票进行技术分析并输出结果

数据源优先级：
1. Alpha Vantage API（推荐，需要免费 API Key）
2. yfinance（备用，容易限流）
3. 模拟数据（用于测试）

使用方法：
    python tool_bullbear_us.py              # 自动选择数据源
    python tool_bullbear_us.py --mock       # 强制使用模拟数据

配置 Alpha Vantage API Key：
    1. 访问 https://www.alphavantage.co/support/#api-key 免费注册
    2. 设置环境变量：setx ALPHA_VANTAGE_API_KEY "your_api_key"
    3. 或在代码中直接传入 api_key 参数
"""

# ================== 1. 获取英伟达历史数据 ==================
def get_nvda_data_from_yfinance(period='6mo'):
    """
    使用 yfinance 获取英伟达(NVDA)数据（备用数据源）
    period: 数据周期
    """
    try:
        ticker = 'NVDA'
        print(f"[yfinance] 正在获取 {ticker} 数据...")
        
        # auto_adjust=True：自动复权
        data = yf.download(ticker, period=period, interval='1d', auto_adjust=True, progress=False)
        
        if data.empty:
            print("❌ [yfinance] 未获取到数据")
            return None
        
        print(f"✅ [yfinance] 数据获取成功，共 {len(data)} 个交易日")
        return data
        
    except Exception as e:
        print(f"❌ [yfinance] 数据获取失败：{e}")
        return None


def get_nvda_data_from_alpha_vantage(period='6mo', api_key=None):
    """
    使用 Alpha Vantage API 获取英伟达数据（主数据源，需要 API Key）
    period: 数据周期
    api_key: Alpha Vantage API Key（可从 https://www.alphavantage.co/support/#api-key 免费获取）
    """
    if not api_key:
        # 尝试从环境变量获取
        import os
        api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
    
    # 临时测试：如果环境变量未设置，使用硬编码的 Key（仅用于调试）
    if not api_key:
        api_key = 'EW68AUQKLKTJ3IEP'  # TODO: 请设置环境变量 ALPHA_VANTAGE_API_KEY
    
    if not api_key:
        print("⚠️  [Alpha Vantage] 未配置 API Key，跳过此数据源")
        print("   💡 提示：可从 https://www.alphavantage.co/support/#api-key 免费获取")
        return None
    
    try:
        ticker = 'NVDA'
        print(f"[Alpha Vantage] 正在获取 {ticker} 数据...")
        
        # Alpha Vantage API - 使用免费版 TIME_SERIES_DAILY（不带 outputsize）
        url = "https://www.alphavantage.co/query"
        params = {
            'function': 'TIME_SERIES_DAILY',  # 免费版端点
            'symbol': ticker,
            # 注意：免费版不支持 outputsize=full，只能获取最近100个交易日
            'apikey': api_key
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code != 200:
            print(f"❌ [Alpha Vantage] HTTP 错误：{response.status_code}")
            return None
        
        result = response.json()
        
        # 检查是否有错误信息
        if 'Error Message' in result:
            print(f"❌ [Alpha Vantage] API 错误：{result['Error Message']}")
            return None
        
        if 'Note' in result:
            print(f"⚠️  [Alpha Vantage] 限流提示：{result['Note']}")
            print("   💡 建议：等待 60 秒后重试，或配置多个 API Key")
            return None
        
        # 检查是否为付费端点提示
        if 'Information' in result:
            print(f"❌ [Alpha Vantage] {result['Information']}")
            print("   💡 提示：TIME_SERIES_DAILY_ADJUSTED 是付费端点，已自动切换到 TIME_SERIES_DAILY")
            return None
        
        # 解析时间序列数据
        time_series = result.get('Time Series (Daily)', {})
        
        if not time_series:
            print("❌ [Alpha Vantage] 未获取到时间序列数据")
            print("   💡 可能原因：")
            print("      1. API Key 无效或已过期")
            print("      2. 股票代码不正确")
            print("      3. 非交易时间且无最新数据")
            print(f"   🔍 完整响应: {json.dumps(result, indent=2, ensure_ascii=False)[:500]}")
            return None
        
        # 转换为 DataFrame
        df = pd.DataFrame.from_dict(time_series, orient='index')
        df.index = pd.to_datetime(df.index)
        df.sort_index(inplace=True)
        
        # 重命名列（TIME_SERIES_DAILY 没有 adjusted close）
        df.rename(columns={
            '1. open': 'Open',
            '2. high': 'High',
            '3. low': 'Low',
            '4. close': 'Close',
            '5. volume': 'Volume'
        }, inplace=True)
        
        # 数据类型转换
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 根据 period 过滤数据
        if period == '1mo':
            cutoff_date = datetime.now() - timedelta(days=30)
        elif period == '3mo':
            cutoff_date = datetime.now() - timedelta(days=90)
        elif period == '6mo':
            cutoff_date = datetime.now() - timedelta(days=180)
        elif period == '1y':
            cutoff_date = datetime.now() - timedelta(days=365)
        else:
            cutoff_date = datetime.now() - timedelta(days=180)
        
        df = df[df.index >= cutoff_date]
        
        print(f"✅ [Alpha Vantage] 数据获取成功，共 {len(df)} 个交易日")
        print(f"   数据范围: {df.index[0].strftime('%Y-%m-%d')} 至 {df.index[-1].strftime('%Y-%m-%d')}")
        
        return df
        
    except Exception as e:
        print(f"❌ [Alpha Vantage] 数据获取失败：{e}")
        import traceback
        traceback.print_exc()
        return None


def generate_mock_data(period='6mo'):
    """
    生成模拟的英伟达历史数据（用于测试）
    """
    print("正在生成模拟数据...")
    
    # 计算日期范围
    end_date = pd.Timestamp.now()
    
    if period == '1mo':
        days = 30
    elif period == '3mo':
        days = 90
    elif period == '6mo':
        days = 180
    elif period == '1y':
        days = 365
    else:
        days = 180
    
    # 生成交易日日期（排除周末）
    dates = pd.bdate_range(end=end_date, periods=days)
    
    # 生成模拟价格数据（随机游走模型）
    np.random.seed(42)  # 固定种子，保证可重复性
    initial_price = 140.0  # 英伟达近似价格
    
    # 生成收盘价（随机游走）
    returns = np.random.normal(0.001, 0.025, len(dates))  # 日均收益 0.1%，波动率 2.5%
    close_prices = initial_price * np.cumprod(1 + returns)
    
    # 生成 OHLCV 数据
    open_prices = close_prices * (1 + np.random.uniform(-0.01, 0.01, len(dates)))
    high_prices = np.maximum(open_prices, close_prices) * (1 + np.abs(np.random.normal(0, 0.015, len(dates))))
    low_prices = np.minimum(open_prices, close_prices) * (1 - np.abs(np.random.normal(0, 0.015, len(dates))))
    volumes = np.random.randint(30000000, 80000000, len(dates))  # 成交量
    
    # 创建 DataFrame
    df = pd.DataFrame({
        'Open': open_prices,
        'High': high_prices,
        'Low': low_prices,
        'Close': close_prices,
        'Volume': volumes
    }, index=dates)
    
    df.index.name = 'date'
    
    print(f"✅ 模拟数据生成成功，共 {len(df)} 个交易日")
    print(f"数据范围: {df.index[0].strftime('%Y-%m-%d')} 至 {df.index[-1].strftime('%Y-%m-%d')}")
    print(f"价格范围: USD {df['Close'].min():.2f} - USD {df['Close'].max():.2f}")
    
    return df


def get_nvda_data(period='6mo', use_mock=False, api_key=None):
    """
    获取英伟达数据（带 fallback 机制）
    
    Args:
        period: 数据周期 ('1mo', '3mo', '6mo', '1y')
        use_mock: 是否直接使用模拟数据（默认 False）
        api_key: Alpha Vantage API Key（可选）
    
    Returns:
        DataFrame 或 None
    """
    print("=" * 55)
    print("             数据源选择策略")
    print("=" * 55)
    
    # 如果指定使用模拟数据，直接生成
    if use_mock:
        print("\n⚠️  用户指定使用模拟数据")
        return generate_mock_data(period)
    
    # 尝试 Alpha Vantage（主数据源，需要 API Key）
    df = get_nvda_data_from_alpha_vantage(period, api_key=api_key)
    if df is not None:
        return df

    print("\n⚠️  Alpha Vantage 不可用，尝试 yfinance...")
    print("-" * 55)
    
    # 尝试 yfinance（备用数据源）
    df = get_nvda_data_from_yfinance(period)
    if df is not None:
        return df
    
    print("\n❌ 所有真实数据源均失败")
    print("\n💡 建议解决方案:")
    print("   1. 配置 Alpha Vantage API Key（推荐）")
    print("      - 访问: https://www.alphavantage.co/support/#api-key")
    print("      - 设置环境变量: ALPHA_VANTAGE_API_KEY")
    print("   2. 稍后重试 yfinance（可能暂时限流）")
    print("   3. 使用模拟数据进行功能测试")
    print("\n⚠️  自动切换到模拟数据模式...")
    return generate_mock_data(period)

# ================== 2. 计算技术指标 ==================
def calculate_indicators(df):
    """计算均线、MACD、RSI、布林带等指标"""
    # 移动平均线
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA10'] = df['Close'].rolling(window=10).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA50'] = df['Close'].rolling(window=50).mean()
    df['MA200'] = df['Close'].rolling(window=200).mean()
    
    # MACD (12, 26, 9)
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = exp1 - exp2                     # 快线
    df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()  # 慢线
    df['MACD'] = 2 * (df['DIF'] - df['DEA'])    # 柱状线
    
    # RSI (14)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # 布林带 (20, 2)
    df['BB_middle'] = df['Close'].rolling(window=20).mean()
    bb_std = df['Close'].rolling(window=20).std()
    df['BB_upper'] = df['BB_middle'] + 2 * bb_std
    df['BB_lower'] = df['BB_middle'] - 2 * bb_std
    
    return df

# ================== 3. 判断均线排列状态 ==================
def check_alignment(latest):
    """判断均线是何种排列，返回(状态, 描述)"""
    # 多头排列：MA5 > MA10 > MA20 > MA50
    if (latest['MA5'] > latest['MA10'] > latest['MA20'] > latest['MA50']):
        return 'bullish', '多头排列（MA5>MA10>MA20>MA50）'
    
    # 空头排列：MA5 < MA10 < MA20 < MA50
    if (latest['MA5'] < latest['MA10'] < latest['MA20'] < latest['MA50']):
        return 'bearish', '空头排列（MA5<MA10<MA20<MA50）'
    
    # 次多头：MA5 > MA20 且 MA10 > MA20
    if latest['MA5'] > latest['MA20'] and latest['MA10'] > latest['MA20']:
        return 'weak_bullish', '偏多（短中期均线位于长期之上）'
    
    # 次空头：MA5 < MA20 且 MA10 < MA20
    if latest['MA5'] < latest['MA20'] and latest['MA10'] < latest['MA20']:
        return 'weak_bearish', '偏空（短中期均线位于长期之下）'
    
    # 额外检查 MA200 空头信号（价格低于MA200是长期空头的典型特征）
    if not pd.isna(latest['MA200']) and latest['Close'] < latest['MA200']:
        return 'bearish', '空头（价格跌破MA200长期均线）'
    
    return 'neutral', '均线缠绕，无明显趋势'

# ================== 4. 主分析函数 ==================
def analyze_nvda(use_mock=False, api_key=None):
    """分析英伟达的技术形态
    
    Args:
        use_mock: 是否使用模拟数据
        api_key: Alpha Vantage API Key（可选）
    """
    print("=" * 55)
    print("             英伟达 (NVDA) 技术分析")
    print("=" * 55)
    
    # 获取数据（近6个月）
    df = get_nvda_data(period='6mo', use_mock=use_mock, api_key=api_key)
    if df is None:
        return None
    
    # 计算技术指标
    df = calculate_indicators(df)
    
    # 获取最新数据
    latest = df.iloc[-1]
    latest_date = df.index[-1].strftime('%Y-%m-%d')
    latest_close = latest['Close']
    
    # 判断均线排列
    alignment, alignment_desc = check_alignment(latest)
    
    # 判断MACD状态
    macd_bullish = latest['DIF'] > latest['DEA'] and latest['DIF'] > 0
    macd_bearish = latest['DIF'] < latest['DEA'] and latest['DIF'] < 0
    
    # 判断价格相对于布林带的位置
    if latest_close > latest['BB_upper']:
        bb_position = "突破上轨（超强）"
        bb_score = 2
    elif latest_close > latest['BB_middle']:
        bb_position = "中轨上方（偏强）"
        bb_score = 1
    elif latest_close > latest['BB_lower']:
        bb_position = "中轨下方（偏弱）"
        bb_score = -1
    else:
        bb_position = "跌破下轨（超弱）"
        bb_score = -2
    
    # 综合评分
    score = 0
    if alignment == 'bullish':
        score += 3
    elif alignment == 'weak_bullish':
        score += 1
    elif alignment == 'weak_bearish':
        score -= 1
    elif alignment == 'bearish':
        score -= 3
    
    if macd_bullish:
        score += 1
    if macd_bearish:
        score -= 1
    
    score += bb_score
    
    # 最终结论
    if score >= 3:
        conclusion = "🟢 强烈多头排列"
    elif score >= 1:
        conclusion = "🟡 偏多震荡"
    elif score <= -3:
        conclusion = "🔴 强烈空头排列"
    elif score <= -1:
        conclusion = "🟠 偏空震荡"
    else:
        conclusion = "⚪ 无明显趋势，建议观望"
    
    # ================== 输出结果 ==================
    print(f"\n📅 最新数据日期: {latest_date}")
    print(f"💰 最新收盘价: USD {latest_close:.2f}")
    print("-" * 55)
    
    print(f"\n📊 移动平均线:")
    print(f"   MA5:   {latest['MA5']:.2f}")
    print(f"   MA10:  {latest['MA10']:.2f}")
    print(f"   MA20:  {latest['MA20']:.2f}")
    print(f"   MA50:  {latest['MA50']:.2f}")
    print(f"   MA200: {latest['MA200']:.2f}" if not pd.isna(latest['MA200']) else "   MA200: 数据不足")
    print(f"   均线状态: {alignment_desc}")
    
    print(f"\n📈 MACD:")
    print(f"   DIF: {latest['DIF']:.3f}")
    print(f"   DEA: {latest['DEA']:.3f}")
    print(f"   柱线: {latest['MACD']:.3f}")
    print(f"   状态: {'金叉向上，位于零轴上' if macd_bullish else '死叉向下，位于零轴下' if macd_bearish else '其他'}")
    
    print(f"\n📉 RSI (14):")
    print(f"   值: {latest['RSI']:.1f}")
    if latest['RSI'] > 70:
        print(f"   状态: 超买区 (>70)")
    elif latest['RSI'] < 30:
        print(f"   状态: 超卖区 (<30)")
    else:
        print(f"   状态: 正常区间")
    
    print(f"\n📦 布林带:")
    print(f"   上轨: {latest['BB_upper']:.2f}")
    print(f"   中轨: {latest['BB_middle']:.2f}")
    print(f"   下轨: {latest['BB_lower']:.2f}")
    print(f"   当前位置: {bb_position}")
    
    print(f"\n🎯 综合评分: {score}")
    print(f"🏁 最终判断: {conclusion}")
    print("=" * 55)
    
    return df, conclusion

# ================== 5. 计算区间涨跌幅（可选扩展） ==================
def calc_period_returns(df):
    """计算近1日、近1周、近1月涨跌幅"""
    latest_close = df['Close'].iloc[-1]
    
    # 近1日：上一个交易日
    price_1d_ago = df['Close'].iloc[-2] if len(df) >= 2 else None
    # 近1周：5个交易日之前
    price_1w_ago = df['Close'].iloc[-6] if len(df) >= 6 else None
    # 近1月：20个交易日之前
    price_1m_ago = df['Close'].iloc[-21] if len(df) >= 21 else None
    
    returns = {}
    returns['近1日涨跌幅'] = (latest_close - price_1d_ago) / price_1d_ago * 100 if price_1d_ago is not None else None
    returns['近1周涨跌幅'] = (latest_close - price_1w_ago) / price_1w_ago * 100 if price_1w_ago is not None else None
    returns['近1月涨跌幅'] = (latest_close - price_1m_ago) / price_1m_ago * 100 if price_1m_ago is not None else None
    
    print("\n📈 区间涨跌幅:")
    for period, ret in returns.items():
        if ret is not None:
            print(f"   {period}: {ret:.2f}%")
        else:
            print(f"   {period}: 数据不足")
    
    return returns

# ================== 5. 运行分析 ==================
if __name__ == "__main__":
    import sys
    
    # 检查命令行参数
    use_mock = '--mock' in sys.argv
    
    # 检查是否通过命令行传入 API Key
    api_key = None
    for i, arg in enumerate(sys.argv):
        if arg == '--api-key' and i + 1 < len(sys.argv):
            api_key = sys.argv[i + 1]
            print(f"✅ 使用命令行提供的 API Key")
            break
    
    result = analyze_nvda(use_mock=use_mock, api_key=api_key)
    if result is None:
        print("\n⚠️  分析失败")
    else:
        df, conclusion = result
        print(f"\n✅ 分析完成！最终结论：{conclusion}")
        
        if len(df) > 0:
            print(f"\n📊 数据统计:")
            print(f"   交易日数量: {len(df)}")
            print(f"   价格范围: USD {df['Close'].min():.2f} - USD {df['Close'].max():.2f}")
            print(f"   最新收盘价: USD {df['Close'].iloc[-1]:.2f}")
            
            # 计算区间涨跌幅
            calc_period_returns(df)