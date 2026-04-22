from mootdx.reader import Reader
import pandas as pd
import requests

TDX_DIR = r"D:\Install\zd_zxzq_gm"   # 请修改为你的实际路径
reader = Reader.factory(market='std', tdxdir=TDX_DIR)

def get_stock_name(symbol: str) -> str:
    """
    根据股票代码获取股票名称（使用腾讯财经API）
    
    Args:
        symbol: 股票代码（纯数字，如 '601991'）
        
    Returns:
        股票名称，如果获取失败则返回代码本身
    """
    try:
        # 判断市场前缀
        if symbol.startswith('6') or symbol.startswith('9'):
            market_prefix = 'sh'
        else:
            market_prefix = 'sz'
        
        # 构建腾讯财经API URL
        full_code = f"{market_prefix}{symbol}"
        url = f"http://qt.gtimg.cn/q={full_code}"
        
        # 发送请求
        response = requests.get(url, timeout=5)
        response.encoding = 'gbk'  # 腾讯财经使用GBK编码
        
        if response.status_code == 200:
            # 解析响应数据
            # 格式: v_sh601991="1~深粮控股~000019~10.50~...";
            data_str = response.text.strip()
            if '=' in data_str:
                # 提取引号内的内容
                content = data_str.split('=')[1].strip('"').strip(';')
                parts = content.split('~')
                if len(parts) >= 2:
                    stock_name = parts[1]
                    if stock_name and stock_name != '':
                        return stock_name
        
        return symbol
    except Exception as e:
        print(f"获取股票 {symbol} 名称失败: {e}")
        return symbol

# 自选股列表（示例）
watchlist = ['601991', '603565', '603606', '688089','688211','688392','688558','688683']   

def check_alignment(df, short=5, mid=10, long_period=20):
    """
    判断均线排列状态（与tool_calc_nb.py保持一致）
    df: 日线DataFrame，需包含close列
    返回: 'bullish'(多头排列), 'bearish'(空头排列), 'neutral'(中性)
    """
    if len(df) < long_period:
        return 'neutral', "数据不足"
    
    df['MA5'] = df['close'].rolling(window=short).mean()
    df['MA10'] = df['close'].rolling(window=mid).mean()
    df['MA20'] = df['close'].rolling(window=long_period).mean()
    
    latest = df.iloc[-1]
    
    # 检查数据完整性
    if pd.isna(latest['MA5']) or pd.isna(latest['MA10']) or pd.isna(latest['MA20']):
        return 'neutral', "数据不足"
    
    ma5 = latest['MA5']
    ma10 = latest['MA10']
    ma20 = latest['MA20']
    
    # 多头排列: MA5 > MA10 > MA20
    if ma5 > ma10 > ma20:
        ratio = ma5 / ma20 if ma20 > 0 else 1
        if ratio > 1.01:  # 额外要求1%差距
            return 'bullish', f"均线多头排列 (MA5>MA10>MA20)"
        else:
            return 'neutral', f"均线粘合略偏多 (差距<1%)"
    
    # 空头排列: MA5 < MA10 < MA20
    if ma5 < ma10 < ma20:
        ratio = ma20 / ma5 if ma5 > 0 else 1
        if ratio > 1.01:
            return 'bearish', f"均线空头排列 (MA5<MA10<MA20)"
        else:
            return 'neutral', f"均线粘合略偏空 (差距<1%)"
    
    return 'neutral', "均线相互缠绕，无明显趋势"

# 批量分析
results = []
for symbol in watchlist:
    try:
        df = reader.daily(symbol=symbol)
        if df is not None and not df.empty:
            alignment, msg = check_alignment(df)
            latest_close = df['close'].iloc[-1]
            
            # 获取股票名称
            stock_name = get_stock_name(symbol)
            
            results.append({
                'code': symbol,
                'name': stock_name,
                'latest_close': latest_close,
                'alignment': alignment,
                'message': msg
            })
            print(f"{symbol}: 收盘价 {latest_close:.2f} | {msg}")
    except Exception as e:
        print(f"{symbol}: 读取失败 - {e}")

# 输出汇总
print("\n========== 分析结果汇总 ==========")
for r in results:
    status = "🟢 多头" if r['alignment'] == 'bullish' else "🔴 空头" if r['alignment'] == 'bearish' else "⚪ 中性"
    print(f"{r['code']} ({r['name']}): {status} (收盘 {r['latest_close']:.2f})")
    print(f"   详情: {r['message']}")