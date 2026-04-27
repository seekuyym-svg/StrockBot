import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import requests
import yfinance as yf

# ================== 1. 获取腾讯控股历史数据 ==================

def get_tencent_data_from_akshare(period='6mo', max_retries=3):
    """
    使用 AKShare 获取腾讯控股(00700.HK)数据（主数据源）
    period: 数据周期
    max_retries: 最大重试次数
    """
    symbol = '00700'  # 港股代码
    print(f"[AKShare] 正在获取 {symbol}.HK 数据...")
    
    for attempt in range(1, max_retries + 1):
        try:
            # 计算日期范围
            end_date = pd.Timestamp.now().strftime('%Y%m%d')
            
            if period == '1mo':
                start_date = (pd.Timestamp.now() - pd.Timedelta(days=30)).strftime('%Y%m%d')
            elif period == '3mo':
                start_date = (pd.Timestamp.now() - pd.Timedelta(days=90)).strftime('%Y%m%d')
            elif period == '6mo':
                start_date = (pd.Timestamp.now() - pd.Timedelta(days=180)).strftime('%Y%m%d')
            elif period == '1y':
                start_date = (pd.Timestamp.now() - pd.Timedelta(days=365)).strftime('%Y%m%d')
            else:
                start_date = (pd.Timestamp.now() - pd.Timedelta(days=180)).strftime('%Y%m%d')
            
            # 使用 AKShare 获取港股历史数据（前复权）
            df = ak.stock_hk_hist(symbol=symbol, period="daily", 
                                 start_date=start_date, end_date=end_date, adjust="qfq")
            
            if df.empty:
                return None
            
            # 重命名列以匹配后续分析逻辑
            df.rename(columns={
                '日期': 'date',
                '開盤價': 'Open',
                '收盤價': 'Close',
                '最高價': 'High',
                '最低價': 'Low',
                '成交量': 'Volume'
            }, inplace=True)
            
            # 确保日期格式为 datetime
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            df.sort_index(inplace=True)
            
            print(f"✅ [AKShare] 数据获取成功，共 {len(df)} 个交易日")
            return df
            
        except Exception as e:
            error_msg = str(e)
            if attempt < max_retries:
                wait_time = 2 * attempt
                print(f"⚠️  [AKShare] 第 {attempt} 次尝试失败：{error_msg[:100]}")
                print(f"   等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
            else:
                print(f"❌ [AKShare] 数据获取失败（已重试 {max_retries} 次）")
                return None


def get_tencent_data_from_yfinance(period='6mo'):
    """
    使用 yfinance 获取腾讯控股(00700.HK)数据（备用数据源）
    period: 数据周期
    """
    try:
        ticker = '0700.HK'  # yfinance 格式
        print(f"[yfinance] 正在获取 {ticker} 数据...")
        
        # auto_adjust=True：自动复权
        data = yf.download(ticker, period=period, interval='1d', auto_adjust=True, progress=False)
        
        if data.empty:
            print("❌ [yfinance] 未获取到数据")
            return None
        
        # yfinance 返回的是 MultiIndex 列或者简单的列名，需要统一格式
        # 通常 yfinance 返回的列名为: Open, High, Low, Close, Adj Close, Volume
        # 索引已经是 DatetimeIndex
        
        # 重命名以匹配后续逻辑 (虽然 yfinance 默认就是英文，但确保一下 Close 等存在)
        # 注意：yfinance 的 auto_adjust=True 会调整 Open, High, Low, Close，但不会保留未调整的 Close
        # 我们直接使用 Close 作为收盘价
        df = data.copy()
        
        # 确保列名大写且标准
        df.columns = [col[1] if isinstance(col, tuple) else col for col in df.columns]
        
        # 如果因为 multi-index 导致的问题，这里做个清洗
        if 'Adj Close' in df.columns and 'Close' not in df.columns:
             df['Close'] = df['Adj Close']
        
        # 只保留需要的列，防止后续计算出错
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in df.columns for col in required_cols):
             print("❌ [yfinance] 数据列不完整")
             return None
             
        df = df[required_cols]
        
        print(f"✅ [yfinance] 数据获取成功，共 {len(df)} 个交易日")
        return df
        
    except ImportError:
        print("⚠️  [yfinance] 未安装，请运行：pip install yfinance")
        return None
    except Exception as e:
        print(f"❌ [yfinance] 数据获取失败：{e}")
        return None


def get_tencent_data_from_tencent_api(period='6mo'):
    """
    使用腾讯财经API获取腾讯控股(00700.HK)历史K线数据（项目推荐数据源）
    period: 数据周期
    """
    try:
        import requests
        
        # 腾讯股票代码格式：hk00700
        symbol = 'hk00700'
        
        # 计算天数
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
        
        print(f"[腾讯财经] 正在获取 {symbol} 历史K线数据...")
        
        # 腾讯财经日K线API（前复权）
        url = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        params = {
            "param": f"{symbol},day,,,{days},qfq"  # qfq=前复权
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.encoding = 'gbk'  # 腾讯财经使用 GBK 编码
        
        if response.status_code != 200:
            print(f"❌ [腾讯财经] HTTP 错误：{response.status_code}")
            return None
        
        result = response.json()
        
        # 解析返回数据结构
        if result.get('code') != 0:
            print(f"❌ [腾讯财经] API 返回错误：{result.get('msg')}")
            return None
        
        data = result.get('data', {})
        stock_data = data.get(symbol, {})
        
        # 尝试多种可能的字段名（腾讯API可能返回不同结构）
        klines = None
        for key in ['qfqday', 'day', 'qfq']:
            if key in stock_data:
                klines = stock_data[key]
                print(f"   ℹ️  使用字段: {key}")
                break
        
        if not klines:
            print("❌ [腾讯财经] 未获取到K线数据")
            print(f"   可用字段: {list(stock_data.keys())}")
            return None
        
        # 转换为 DataFrame
        # 腾讯财经K线字段：[日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额]
        df = pd.DataFrame(klines, columns=['date', 'Open', 'Close', 'High', 'Low', 'Volume', 'Amount'])
        
        # 数据类型转换
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df.sort_index(inplace=True)
        
        # 数值类型转换
        for col in ['Open', 'Close', 'High', 'Low', 'Volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        print(f"✅ [腾讯财经] 数据获取成功，共 {len(df)} 个交易日")
        print(f"   数据范围: {df.index[0].strftime('%Y-%m-%d')} 至 {df.index[-1].strftime('%Y-%m-%d')}")
        
        return df
        
    except Exception as e:
        print(f"❌ [腾讯财经] 数据获取失败：{e}")
        return None


def get_tencent_data(period='6mo', use_mock=False):
    """
    获取腾讯控股数据（带 fallback 机制）
    
    Args:
        period: 数据周期 ('1mo', '3mo', '6mo', '1y')
        use_mock: 是否直接使用模拟数据（默认 False）
    
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
    
    # 尝试腾讯财经API（项目推荐数据源）
    df = get_tencent_data_from_tencent_api(period)
    if df is not None:
        return df
    
    print("\n⚠️  腾讯财经失败，尝试 AKShare...")
    print("-" * 55)
    
    # 尝试 AKShare（备用数据源）
    df = get_tencent_data_from_akshare(period)
    if df is not None:
        return df
    
    print("\n⚠️  AKShare 失败，尝试 yfinance...")
    print("-" * 55)
    
    # 尝试 yfinance（最后备用）
    df = get_tencent_data_from_yfinance(period)
    if df is not None:
        return df
    
    print("\n❌ 所有真实数据源均失败")
    print("\n💡 自动切换到模拟数据模式...")
    return generate_mock_data(period)


def generate_mock_data(period='6mo'):
    """
    生成模拟的腾讯控股历史数据（用于测试）
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
    initial_price = 450.0  # 腾讯控股近似价格
    
    # 生成收盘价（随机游走）
    returns = np.random.normal(0.0005, 0.02, len(dates))  # 日均收益 0.05%，波动率 2%
    close_prices = initial_price * np.cumprod(1 + returns)
    
    # 生成 OHLCV 数据
    open_prices = close_prices * (1 + np.random.uniform(-0.01, 0.01, len(dates)))
    high_prices = np.maximum(open_prices, close_prices) * (1 + np.abs(np.random.normal(0, 0.01, len(dates))))
    low_prices = np.minimum(open_prices, close_prices) * (1 - np.abs(np.random.normal(0, 0.01, len(dates))))
    volumes = np.random.randint(10000000, 50000000, len(dates))  # 成交量
    
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
    print(f"价格范围: HKD {df['Close'].min():.2f} - HKD {df['Close'].max():.2f}")
    
    return df

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
    
    return 'neutral', '均线缠绕，无明显趋势'

# ================== 4. 主分析函数 ==================
def analyze_tencent(use_mock=False):
    """分析腾讯控股的技术形态
    
    Args:
        use_mock: 是否使用模拟数据
    """
    print("=" * 55)
    print("             腾讯控股 (00700.HK) 技术分析")
    print("=" * 55)
    
    # 获取数据（近6个月）
    df = get_tencent_data(period='6mo', use_mock=use_mock)
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
    print(f"💰 最新收盘价: HKD {latest_close:.2f}")
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

# ================== 6. 运行分析 ==================
if __name__ == "__main__":
    import sys
    
    # 检查命令行参数
    use_mock = '--mock' in sys.argv
    
    result = analyze_tencent(use_mock=use_mock)
    if result is None:
        print("\n⚠️  分析失败")
    else:
        df, conclusion = result
        print(f"\n✅ 分析完成！最终结论：{conclusion}")
        
        if len(df) > 0:
            print(f"\n📊 数据统计:")
            print(f"   交易日数量: {len(df)}")
            print(f"   价格范围: HKD {df['Close'].min():.2f} - HKD {df['Close'].max():.2f}")
            print(f"   最新收盘价: HKD {df['Close'].iloc[-1]:.2f}")
            
            # 计算区间涨跌幅
            calc_period_returns(df)
