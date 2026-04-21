from mootdx.reader import Reader
import pandas as pd

TDX_DIR = r"D:\Install\zd_zxzq_gm"   # 请修改为你的实际路径
reader = Reader.factory(market='std', tdxdir=TDX_DIR)

# 自选股列表（示例）
watchlist = ['600519', '000858', '300750', '002706']   # 贵州茅台、五粮液、宁德时代、良信股份

def check_alignment(df, short=5, mid=20, long=60):
    """
    判断均线排列状态
    df: 日线DataFrame，需包含close列
    返回: 'bullish'(多头排列), 'bearish'(空头排列), 'neutral'(中性)
    """
    if len(df) < long:
        return 'neutral'
    
    df['MA5'] = df['close'].rolling(window=short).mean()
    df['MA20'] = df['close'].rolling(window=mid).mean()
    df['MA60'] = df['close'].rolling(window=long).mean()
    
    latest = df.iloc[-1]
    
    if latest['MA5'] > latest['MA20'] > latest['MA60']:
        return 'bullish'
    elif latest['MA5'] < latest['MA20'] < latest['MA60']:
        return 'bearish'
    else:
        return 'neutral'

# 批量分析
results = []
for symbol in watchlist:
    try:
        df = reader.daily(symbol=symbol)
        if df is not None and not df.empty:
            alignment = check_alignment(df)
            latest_close = df['close'].iloc[-1]
            results.append({
                'code': symbol,
                'latest_close': latest_close,
                'alignment': alignment
            })
            print(f"{symbol}: 收盘价 {latest_close:.2f} | 均线状态: {alignment}")
    except Exception as e:
        print(f"{symbol}: 读取失败 - {e}")

# 输出汇总
print("\n========== 分析结果汇总 ==========")
for r in results:
    status = "🟢 多头" if r['alignment'] == 'bullish' else "🔴 空头" if r['alignment'] == 'bearish' else "⚪ 中性"
    print(f"{r['code']}: {status} (收盘 {r['latest_close']:.2f})")