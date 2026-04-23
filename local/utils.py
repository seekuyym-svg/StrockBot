"""
通用工具函数模块
提供股票相关的常用辅助功能
"""

import pandas as pd
import requests
from typing import Dict, Optional, Tuple
from pathlib import Path


def get_stock_name(symbol: str) -> str:
    """
    根据股票代码获取股票名称（使用腾讯财经API）
    
    Args:
        symbol: 股票代码（不含市场前缀），如 '000526'
    
    Returns:
        str: 股票名称，获取失败则返回股票代码本身
    
    Example:
        >>> get_stock_name('000526')
        '学大教育'
        >>> get_stock_name('600963')
        '岳阳林纸'
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


def calculate_trend_score(market: str, code: str, days: int = 300) -> Optional[float]:
    """
    计算股票综合趋势评分（-5到+5分）
    
    评分维度：
    1. 均线排列（-3到+3分）
    2. MACD指标（-1到+1分）
    3. RSI指标（-1到+1分）
    4. 布林带位置（-1到+1分）
    5. 成交量配合（-0.5到+0.5分）
    
    Args:
        market: 市场代码 ('sh' 或 'sz')
        code: 股票代码
        days: 获取历史数据天数，默认300天
    
    Returns:
        float: 综合评分（-5.0到+5.0），失败返回None
    """
    try:
        # 1. 获取K线数据
        df = _get_historical_klines(market, code, days)
        if df.empty or len(df) < 60:
            return None
        
        # 2. 计算技术指标
        df = _calculate_ma(df)
        dif, dea, macd_bar = _compute_macd(df)
        rsi_val = _compute_rsi(df)
        boll_pos, upper, lower = _compute_bollinger(df)
        
        # 3. 综合评分
        score = 0
        
        # 均线排列评分
        trend = _check_trend_alignment(df)
        if trend == 'bullish':
            score += 3
        elif trend == 'bearish':
            score -= 3
        
        # MACD评分
        if dif > dea and dif > 0:
            score += 1
        elif dif < dea and dif < 0:
            score -= 1
        
        # RSI评分
        if rsi_val > 60:
            score += 1
        elif rsi_val < 40:
            score -= 1
        
        # 布林带评分
        if boll_pos == 1:
            score += 1
        elif boll_pos == -1:
            score -= 1
        
        # 成交量评分
        latest_close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        latest_vol = df['volume'].iloc[-1]
        vol_ma20 = df['volume'].rolling(20).mean().iloc[-1]
        vol_ratio = latest_vol / vol_ma20 if vol_ma20 > 0 else 1
        
        if vol_ratio > 1.2 and latest_close > prev_close:
            score += 0.5
        elif vol_ratio > 1.2 and latest_close < prev_close:
            score -= 0.5
        
        return round(score, 1)
        
    except Exception as e:
        print(f"⚠️  计算评分失败 ({market}{code}): {e}")
        return None


def _get_historical_klines(market: str, code: str, days: int = 300) -> pd.DataFrame:
    """
    从腾讯财经获取历史K线数据
    
    Args:
        market: 市场代码 (sh 或 sz)
        code: 股票代码
        days: 获取天数
        
    Returns:
        DataFrame包含日期、开盘、收盘、最高、最低、成交量等字段
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        params = {
            "param": f"{market}{code},day,,,{days},qfq"  # qfq=前复权
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        
        if result.get('code') == 0 and result.get('data'):
            stock_data = result['data'].get(f'{market}{code}', {})
            # 兼容处理：优先使用前复权数据，降级到普通日线
            klines = stock_data.get('qfqday', []) or stock_data.get('day', [])
            
            if klines:
                records = []
                for line in klines:
                    # 跳过分红数据（字典类型）
                    if isinstance(line, dict):
                        continue
                    
                    # 兼容6字段格式：[日期, 开, 收, 高, 低, 量]
                    if isinstance(line, (list, tuple)) and len(line) >= 6:
                        try:
                            records.append({
                                'date': pd.to_datetime(line[0]),
                                'open': float(line[1]),
                                'close': float(line[2]),
                                'high': float(line[3]),
                                'low': float(line[4]),
                                'volume': float(line[5]) * 100,  # 手转股
                            })
                        except (ValueError, TypeError):
                            continue
                
                df = pd.DataFrame(records)
                if not df.empty:
                    df = df.sort_values('date').reset_index(drop=True)
                    df.set_index('date', inplace=True)
                    return df
        
        return pd.DataFrame()
        
    except Exception as e:
        print(f"❌ 获取K线数据失败 ({market}{code}): {e}")
        return pd.DataFrame()


def _calculate_ma(df: pd.DataFrame, periods: list = [5, 10, 20, 60]) -> pd.DataFrame:
    """计算移动平均线"""
    for p in periods:
        df[f'MA{p}'] = df['close'].rolling(window=p).mean()
    return df


def _check_trend_alignment(df: pd.DataFrame) -> str:
    """
    判断均线排列状态
    
    Returns:
        str: 'bullish'(多头), 'bearish'(空头), 'neutral'(中性)
    """
    latest = df.iloc[-1]
    
    # 检查数据完整性
    if pd.isna(latest.get('MA5')) or pd.isna(latest.get('MA10')) or pd.isna(latest.get('MA20')):
        return 'neutral'
    
    ma5 = latest['MA5']
    ma10 = latest['MA10']
    ma20 = latest['MA20']
    
    # 多头排列: MA5 > MA10 > MA20
    if ma5 > ma10 > ma20:
        ratio = ma5 / ma20 if ma20 > 0 else 1
        if ratio > 1.01:  # 额外要求1%差距
            return 'bullish'
        else:
            return 'neutral'
    
    # 空头排列: MA5 < MA10 < MA20
    if ma5 < ma10 < ma20:
        ratio = ma20 / ma5 if ma5 > 0 else 1
        if ratio > 1.01:
            return 'bearish'
        else:
            return 'neutral'
    
    return 'neutral'


def _compute_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[float, float, float]:
    """计算MACD指标"""
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd_bar = (dif - dea) * 2
    return dif.iloc[-1], dea.iloc[-1], macd_bar.iloc[-1]


def _compute_rsi(df: pd.DataFrame, period: int = 14) -> float:
    """计算RSI指标"""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]


def _compute_bollinger(df: pd.DataFrame, period: int = 20, std_dev: int = 2) -> Tuple[int, float, float]:
    """
    计算布林带位置
    
    Returns:
        (position, upper, lower): 位置标识(1=突破上轨, 0=中轨附近, -1=跌破下轨)、上轨、下轨
    """
    ma = df['close'].rolling(window=period).mean()
    std = df['close'].rolling(window=period).std()
    upper = ma + std_dev * std
    lower = ma - std_dev * std
    latest_close = df['close'].iloc[-1]
    
    if latest_close > upper.iloc[-1]:
        position = 1
    elif latest_close < lower.iloc[-1]:
        position = -1
    else:
        position = 0
    
    return position, upper.iloc[-1], lower.iloc[-1]


def calculate_price_change(market: str, code: str, start_date: str, end_date: str) -> Optional[float]:
    """
    计算指定时间段内的股票涨跌幅
    
    Args:
        market: 市场代码 ('sh' 或 'sz')
        code: 股票代码
        start_date: 起始日期 (格式: 'YYYY-MM-DD' 或 'YYYYMMDD')
        end_date: 结束日期 (格式: 'YYYY-MM-DD' 或 'YYYYMMDD')
    
    Returns:
        float: 涨跌幅百分比（如 +15.5 表示上涨15.5%，-8.3 表示下跌8.3%）
               失败返回None
    
    Example:
        >>> calculate_price_change('sz', '000526', '2024-01-01', '2024-01-31')
        5.23  # 表示上涨5.23%
    """
    try:
        # 获取K线数据（需要足够的数据覆盖时间段）
        df = _get_historical_klines(market, code, days=300)
        
        if df.empty:
            return None
        
        # 标准化日期格式
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        # 确保索引是datetime类型
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        
        # 筛选指定时间段的数据
        mask = (df.index >= start_dt) & (df.index <= end_dt)
        period_data = df.loc[mask]
        
        if len(period_data) < 2:
            # 数据不足，无法计算
            return None
        
        # 获取起始日和结束日的收盘价
        start_price = period_data['close'].iloc[0]
        end_price = period_data['close'].iloc[-1]
        
        # 计算涨跌幅
        if start_price == 0:
            return None
        
        change_pct = (end_price - start_price) / start_price * 100
        
        return round(change_pct, 2)
        
    except Exception as e:
        print(f"[WARN] 计算涨跌幅失败 ({market}{code}, {start_date}~{end_date}): {e}")
        return None


def format_number(num: float, decimals: int = 2) -> str:
    """
    格式化数字，添加千位分隔符
    
    Args:
        num: 要格式化的数字
        decimals: 小数位数，默认2位
    
    Returns:
        str: 格式化后的字符串
    
    Example:
        >>> format_number(1234567.89)
        '1,234,567.89'
    """
    return f"{num:,.{decimals}f}"


if __name__ == "__main__":
    # 测试
    test_codes = ['000526', '600963', '688020', '300179']
    print("测试股票名称获取功能:")
    print("-" * 40)
    for code in test_codes:
        name = get_stock_name(code)
        print(f"{code}: {name}")
    
    print("\n\n测试综合评分功能:")
    print("-" * 40)
    for code in test_codes:
        if code.startswith('6') or code.startswith('9'):
            market = 'sh'
        else:
            market = 'sz'
        
        score = calculate_trend_score(market, code)
        if score is not None:
            print(f"{code}: {score:+.1f}分")
        else:
            print(f"{code}: 评分失败")