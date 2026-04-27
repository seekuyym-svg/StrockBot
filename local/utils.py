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
    计算指定时间段内的股票涨跌幅（收盘价对比）
    
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


def calculate_5day_price_change(market: str, code: str) -> Optional[float]:
    """
    计算5个交易日涨跌幅（按交易日而非自然日）
    
    计算逻辑：
    - 如果当前时间在15:00前或是周末：使用上一个交易日作为结束日期，往前推4个交易日
    - 如果当前时间在15:00后：使用今天作为结束日期，往前推4个交易日
    - 涨跌幅 = (结束日收盘价 - 起始日开盘价) / 起始日开盘价 * 100
    
    Args:
        market: 市场代码 ('sh' 或 'sz')
        code: 股票代码
    
    Returns:
        float: 5日涨跌幅百分比，失败返回None
    
    Example:
        >>> calculate_5day_price_change('sh', '600000')
        8.65  # 表示5个交易日上涨8.65%
    """
    try:
        from datetime import datetime, time
        
        # 获取K线数据（至少需要10个交易日数据以确保有足够的历史）
        df = _get_historical_klines(market, code, days=30)
        
        if df.empty or len(df) < 5:
            return None
        
        # 确保索引是datetime类型
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        
        # 按日期排序（从早到晚）
        df = df.sort_index()
        
        # 确定结束日期和起始日期（基于交易日索引）
        # 获取最后5个交易日的数据
        last_5_days = df.iloc[-5:]
        
        if len(last_5_days) < 5:
            return None
        
        # 起始日：5个交易日前的那一天（第1天）
        start_day = last_5_days.iloc[0]
        # 结束日：最后一个交易日（第5天）
        end_day = last_5_days.iloc[-1]
        
        # 计算涨跌幅：(结束日收盘价 - 起始日开盘价) / 起始日开盘价 * 100
        start_open = start_day['open']
        end_close = end_day['close']
        
        if start_open == 0:
            return None
        
        change_pct = (end_close - start_open) / start_open * 100
        
        return round(change_pct, 2)
        
    except Exception as e:
        print(f"[WARN] 计算5日涨跌幅失败 ({market}{code}): {e}")
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


def get_stock_list_date(symbol: str) -> Optional[str]:
    """
    获取股票上市日期（使用akshare接口）
    
    Args:
        symbol: 股票代码（不含市场前缀），如 '000526'
    
    Returns:
        str: 上市日期（格式: 'YYYY-MM-DD'），获取失败返回None
    
    Example:
        >>> get_stock_list_date('000526')
        '1996-08-08'
    """
    try:
        import akshare as ak
        
        # 获取A股股票基本信息
        stock_info_df = ak.stock_individual_info_em(symbol=symbol)
        
        if stock_info_df is None or stock_info_df.empty:
            return None
        
        # 查找上市日期字段
        # akshare返回的列名为 'item' 和 'value'
        list_date_row = stock_info_df[stock_info_df['item'] == '上市时间']
        
        if not list_date_row.empty:
            list_date_str = list_date_row['value'].iloc[0]
            # 标准化日期格式为 YYYY-MM-DD
            if len(list_date_str) == 8 and list_date_str.isdigit():
                # 格式: YYYYMMDD
                return f"{list_date_str[:4]}-{list_date_str[4:6]}-{list_date_str[6:8]}"
            else:
                # 尝试直接解析
                try:
                    dt = pd.to_datetime(list_date_str)
                    return dt.strftime('%Y-%m-%d')
                except:
                    return list_date_str
        
        return None
        
    except Exception as e:
        print(f"⚠️  获取股票 {symbol} 上市日期失败: {e}")
        return None


def is_new_stock(symbol: str, min_listing_days: int = 365) -> bool:
    """
    判断股票是否为新股（上市时间不足指定天数）
    
    使用腾讯财经API间接验证：获取最近的历史K线数据
    - 如果能获取到足够多的历史数据（>=min_listing_days天），说明上市超过指定天数
    - 如果数据不足，可能是新股或长期停牌（都需过滤）
    
    Args:
        symbol: 股票代码（不含市场前缀）
        min_listing_days: 最小上市天数，默认365天（1年）
    
    Returns:
        bool: True表示是新股（上市不足指定天数），False表示不是新股
    
    Example:
        >>> is_new_stock('688001', 365)
        False  # 如果上市超过1年
    """
    try:
        # 确定市场前缀
        if symbol.startswith('6') or symbol.startswith('9'):
            market_prefix = 'sh'
        else:
            market_prefix = 'sz'
        
        full_code = f"{market_prefix}{symbol}"
        
        # 使用腾讯财经API获取历史K线数据（请求min_listing_days天的数据）
        url = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        params = {
            "param": f"{full_code},day,,,{min_listing_days + 30},qfq"  # 多取30天作为缓冲
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        
        # 检查返回码
        if result.get('code') != 0:
            print(f"[WARN] {symbol} 腾讯财经API返回错误: {result.get('msg', '未知错误')}")
            return True  # 保守策略：无法验证时视为新股
        
        # 解析数据
        stock_data = result.get('data', {}).get(full_code, {})
        
        # 兼容处理：优先使用前复权数据，降级到普通日线
        klines = stock_data.get('qfqday', []) or stock_data.get('day', [])
        
        if not klines or len(klines) < min_listing_days:
            # 历史数据不足，判定为新股或长期停牌
            actual_days = len(klines) if klines else 0
            print(f"[INFO] {symbol} 历史数据不足: 仅{actual_days}天（需要{min_listing_days}天），判定为新股/停牌")
            return True
        
        # 有足够历史数据，说明上市超过指定天数
        return False
        
    except Exception as e:
        print(f"⚠️  判断股票 {symbol} 是否为新时失败: {e}")
        return True  # 出错时保守策略：视为新股并过滤


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
    
    print("\n\n测试上市日期获取功能:")
    print("-" * 40)
    for code in test_codes:
        list_date = get_stock_list_date(code)
        is_new = is_new_stock(code, 365)
        print(f"{code}: 上市日期={list_date}, 是否新股(<1年)={is_new}")


def load_whitelist(date_str=None):
    """
    加载股票白名单（正常交易股票）
    
    Args:
        date_str: 日期字符串 YYYYMMDD，默认今天
    
    Returns:
        set: 白名单股票代码集合
    """
    from pathlib import Path
    from datetime import datetime
    
    if date_str is None:
        date_str = datetime.now().strftime('%Y%m%d')
    
    # 项目根目录的 data 文件夹
    data_dir = Path(__file__).parent.parent / "data"
    whitelist_file = data_dir / f"whitelist_{date_str}.txt"
    
    if not whitelist_file.exists():
        print(f"[WARN] 白名单文件不存在: {whitelist_file}")
        return set()
    
    try:
        whitelist_codes = set()
        with open(whitelist_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    whitelist_codes.add(line)
        
        print(f"[LOAD] 加载白名单: {len(whitelist_codes)} 只股票")
        return whitelist_codes
    except Exception as e:
        print(f"[ERROR] 加载白名单失败: {e}")
        return set()


def load_blacklist(date_str=None):
    """
    加载股票黑名单（ST/停牌/退市股）
    
    Args:
        date_str: 日期字符串 YYYYMMDD，默认今天
    
    Returns:
        dict: {code: (name, reason), ...}
    """
    from pathlib import Path
    from datetime import datetime
    
    if date_str is None:
        date_str = datetime.now().strftime('%Y%m%d')
    
    # 项目根目录的 data 文件夹
    data_dir = Path(__file__).parent.parent / "data"
    blacklist_file = data_dir / f"blacklist_{date_str}.txt"
    
    if not blacklist_file.exists():
        print(f"[WARN] 黑名单文件不存在: {blacklist_file}")
        return {}
    
    try:
        blacklist_dict = {}
        with open(blacklist_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split(',')
                    if len(parts) >= 3:
                        code, name, reason = parts[0], parts[1], parts[2]
                        blacklist_dict[code] = (name, reason)
        
        print(f"[LOAD] 加载黑名单: {len(blacklist_dict)} 只股票")
        return blacklist_dict
    except Exception as e:
        print(f"[ERROR] 加载黑名单失败: {e}")
        return {}
