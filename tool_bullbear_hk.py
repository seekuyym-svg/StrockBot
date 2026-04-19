import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ================== 1. 获取腾讯控股历史数据 ==================
def get_tencent_data(period='6mo'):
    """
    使用yfinance获取腾讯控股(00700.HK)数据
    period: 数据周期，可选 '1mo', '3mo', '6mo', '1y', '2y', '5y', 'max'
    """
    ticker = '0700.HK'  # 港股代码需要加.HK后缀
    print(f"正在获取 {ticker} 数据...")
    
    # auto_adjust=True：自动复权，价格已包含分红和拆股调整
    data = yf.download(ticker, period=period, interval='1d', auto_adjust=True)
    
    if data.empty:
        print("❌ 未获取到数据，请检查网络或股票代码")
        return None
    
    print(f"✅ 数据获取成功，共 {len(data)} 个交易日")
    print(f"数据范围: {data.index[0].strftime('%Y-%m-%d')} 至 {data.index[-1].strftime('%Y-%m-%d')}")
    return data

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
def analyze_tencent():
    """分析腾讯控股的技术形态"""
    print("=" * 55)
    print("             腾讯控股 (00700.HK) 技术分析")
    print("=" * 55)
    
    # 获取数据（近6个月）
    df = get_tencent_data(period='6mo')
    if df is None:
        return
    
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

# ================== 5. 运行分析 ==================
if __name__ == "__main__":
    df, result = analyze_tencent()