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


def get_circulating_shares_from_tencent(market: str, code: str) -> Optional[float]:
    """
    从腾讯财经API获取流通股本
    
    Args:
        market: 市场代码 ('sh' 或 'sz')
        code: 股票代码 (如 '002706')
        
    Returns:
        float: 流通股本（股），失败返回None
    """
    try:
        # 构建腾讯财经实时行情URL
        url = f"http://qt.gtimg.cn/q={market}{code}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        response.encoding = 'gbk'
        
        content = response.text
        
        # 解析数据
        if '~' in content and '=' in content:
            import re
            match = re.search(r'="([^"]+)"', content)
            if match:
                data_str = match.group(1)
                parts_data = data_str.split('~')
                
                # 尝试从多个可能的字段位置获取流通股本
                circulating_shares = 0
                
                # 字段[72]和[76]通常是流通股本（股数）
                for idx in [72, 76]:
                    if len(parts_data) > idx and parts_data[idx]:
                        try:
                            shares = float(parts_data[idx])
                            if shares > 0:
                                circulating_shares = shares
                                break
                        except ValueError:
                            continue
                
                if circulating_shares > 0:
                    return circulating_shares
        
        return None
        
    except Exception as e:
        print(f"⚠️  获取 {market}{code} 流通股本失败: {e}")
        return None


# 模块级换手率评分缓存（只初始化一次）
_TURNOVER_VOL_PERIOD = 3

def calculate_cumulative_turnover_score(market: str, code: str, analysis_date: str = None,
                                        df: pd.DataFrame = None, vol_ma20: float = None) -> float:
    """
    计算换手率活跃度评分（0~5分）
    
    优先用真实换手率评分（获取流通股本），失败时降级为量比评分。
    有传入df时用已有数据，避免重复获取K线。
    
    Args:
        market: 市场代码 ('sh' 或 'sz')
        code: 股票代码
        analysis_date: 分析日期
        df: 已有的K线DataFrame（可选）
        vol_ma20: 已有的20日均量（可选）
        
    Returns:
        float: 评分 (0~5分)
    """
    # === 优先方案：真实换手率评分 ===
    try:
        circulating_shares = get_circulating_shares_from_tencent(market, code)
        if circulating_shares is not None and circulating_shares > 0:
            # 有df直接用，没有就临时获取
            if df is None or df.empty or len(df) < _TURNOVER_VOL_PERIOD:
                kline_df = _get_historical_klines(market, code, days=10, end_date=analysis_date,
                                                   min_data_length=_TURNOVER_VOL_PERIOD)
            else:
                kline_df = df
            
            if kline_df is not None and not kline_df.empty and len(kline_df) >= _TURNOVER_VOL_PERIOD:
                last_n = kline_df.iloc[-_TURNOVER_VOL_PERIOD:]
                turnovers = []
                for _, row in last_n.iterrows():
                    vol_shares = row['volume'] * 100
                    rate = (vol_shares / circulating_shares) * 100
                    turnovers.append(rate)
                
                avg_turnover = sum(turnovers) / len(turnovers)
                
                # 连续评分：基于3天平均换手率
                if 2 <= avg_turnover <= 8:
                    return 5.0   # 最佳活跃度，匹配2~4%收益目标
                elif 1 <= avg_turnover < 2 or 8 < avg_turnover <= 15:
                    return 3.0   # 一般活跃度
                elif avg_turnover > 15:
                    return 1.0   # 过热
                else:
                    return 2.0   # 偏低但还不是僵尸
    except Exception:
        pass
    
    # === 降级方案：量比评分（获取流通股本失败时）===
    if df is not None and not df.empty and len(df) >= 5:
        if vol_ma20 is None or vol_ma20 <= 0:
            vol_ma20 = df['volume'].iloc[-20:].mean()
        if vol_ma20 <= 0:
            return 0
        ratios = [df['volume'].iloc[-1-i] / vol_ma20 for i in range(3)]
        avg_ratio = sum(ratios) / 3
        if 0.8 <= avg_ratio <= 2.0:
            return 5.0
        elif 2.0 < avg_ratio <= 2.8:
            return 3.0
        elif 0.5 <= avg_ratio < 0.8:
            return 2.0
        else:
            return 1.0
    
    return 0


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


def _get_historical_klines(market: str, code: str, days: int = 300, 
                           end_date: str = None, min_data_length: int = 60) -> pd.DataFrame:
    """
    获取历史K线数据（支持本地数据和网络API双模式）
    
    Args:
        market: 市场代码 (sh 或 sz)
        code: 股票代码
        days: 获取天数
        end_date: 截止日期 (格式: YYYY-MM-DD)，如果提供则只返回此日期之前的数据
        min_data_length: 最小数据长度要求，默认60条
        
    Returns:
        DataFrame包含日期、开盘、收盘、最高、最低、成交量等字段（前复权）
    """
    # 尝试从配置读取数据源设置
    try:
        import yaml
        from pathlib import Path
        
        # 使用基于 __file__ 的绝对路径定位 config.yaml
        # local/utils.py -> local/ -> 项目根目录
        project_root = Path(__file__).parent.parent
        config_path = project_root / 'config.yaml'
        
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            full_config = yaml.safe_load(f)
        
        # 读取 backtest 配置
        backtest_config = full_config.get('backtest', {})
        use_local = backtest_config.get('use_local_data', True)
        consistency_check = backtest_config.get('data_consistency_check', False)
        
        # 读取 TDX_DIR（在根级别）
        tdx_dir = full_config.get('TDX_DIR', 'D:\\Install\\zd_zxzq_gm')
        
    except Exception as e:
        # 配置读取失败时的降级方案
        print(f"⚠️  配置读取失败: {e}，使用默认配置（本地数据模式）")
        use_local = True
        tdx_dir = 'D:\\Install\\zd_zxzq_gm'
        consistency_check = False
    
    # 根据配置选择数据源
    if use_local:
        return _get_klines_from_local(market, code, days, tdx_dir, consistency_check, end_date, min_data_length)
    else:
        # 直接使用腾讯财经API，不尝试加载 mootdx
        return _get_klines_from_tencent(market, code, days, end_date, min_data_length)


def _get_klines_from_local(market: str, code: str, days: int, tdx_dir: str, 
                           consistency_check: bool = False,
                           end_date: str = None, min_data_length: int = 60) -> pd.DataFrame:
    """
    从本地通达信数据获取K线（前复权）
    
    Args:
        market: 市场代码 (sh 或 sz)
        code: 股票代码
        days: 获取天数
        tdx_dir: 通达信安装目录
        consistency_check: 是否进行数据一致性验证
        end_date: 截止日期
        min_data_length: 最小数据长度要求，默认60条
        
    Returns:
        DataFrame包含前复权K线数据
    """
    # 首先检查 tdx_dir 是否存在，如果不存在直接降级到网络API
    import os
    if not tdx_dir or not os.path.exists(tdx_dir):
        return _get_klines_from_tencent(market, code, days, end_date, min_data_length)
    
    try:
        # 动态导入 mootdx，如果模块不存在则抛出异常并降级
        from mootdx.reader import Reader
        from mootdx.utils.adjust import to_adjust
        from datetime import datetime, timedelta
        
        # 构建完整代码（如 sh600000）
        full_code = f"{market}{code}"
        
        # 1. 检查数据文件是否存在及更新日期
        data_file = None
        if market == 'sh':
            data_file = os.path.join(tdx_dir, 'vipdoc', 'sh', 'lday', f'sh{code}.day')
        elif market == 'sz':
            data_file = os.path.join(tdx_dir, 'vipdoc', 'sz', 'lday', f'sz{code}.day')
        
        if data_file and os.path.exists(data_file):
            # 检查文件修改时间
            file_mtime = datetime.fromtimestamp(os.path.getmtime(data_file))
            days_since_update = (datetime.now() - file_mtime).days
            
            # 获取配置的交易日阈值
            try:
                import yaml
                import os
                
                config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.yaml')
                if not os.path.exists(config_path):
                    config_path = 'config.yaml'
                
                with open(config_path, 'r', encoding='utf-8') as f:
                    full_config = yaml.safe_load(f)
                
                max_age = full_config.get('backtest', {}).get('max_data_age_days', 7)
            except:
                max_age = 7
            
            # Data age check skipped to reduce log noise
        
        # 2. 初始化Reader
        reader = Reader.factory(market='std', tdxdir=tdx_dir)
        
        # 3. 获取原始K线数据
        # 注意：mootdx market='std' 模式下，symbol 需要纯数字代码（如 "300183"）
        # 不能用带市场前缀的 "sz300183"，否则读取失败
        raw_data = reader.daily(symbol=code)
        
        if raw_data is None or raw_data.empty:
            # 降级到网络API
            # [DEBUG] 输出诊断信息，排查本地数据读取失败的原因
            print(f"🔍 [DEBUG] {market}{code} 本地数据读取失败，降级到腾讯API")
            print(f"   tdx_dir: {tdx_dir}")
            print(f"   data_file_exists: {os.path.exists(data_file) if data_file else 'N/A'}")
            return _get_klines_from_tencent(market, code, days, end_date, min_data_length)
        
        # 4. 转换为前复权数据
        # 注意：通达信本地数据文件(.day)本身已经是前复权数据
        # mootdx的to_adjust函数在当前版本中存在bug，暂时不使用
        df = raw_data.copy()

        # 5. 标准化列名和索引
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        
        # 确保列名统一（小写）
        df.columns = [col.lower() for col in df.columns]
        
        # 检查必要列是否存在
        required_cols = ['open', 'close', 'high', 'low', 'volume']
        if not all(col in df.columns for col in required_cols):
            return pd.DataFrame()
        
        # 8. 【修复】先按截止日期过滤，再截取最近N天
        # 顺序不能反：先过滤日期，再取最近N条，否则当end_date远早于最新数据时会得到0条
        if end_date:
            end_dt = pd.to_datetime(end_date)
            df = df[df.index <= end_dt]
            if len(df) < min_data_length:  # 使用可配置的最小长度
                # 本地数据不足，降级到腾讯API
                return _get_klines_from_tencent(market, code, days, end_date, min_data_length)
        
        # 7. 截取最近N天数据
        if len(df) > days:
            df = df.iloc[-days:]
        
        # 9. 数据一致性验证（可选）
        if consistency_check and len(df) > 0:
            _verify_data_consistency(full_code, df, tdx_dir)
        
        return df
        
    except Exception as e:
        print(f"❌本地数据读取失败 ({market}{code}): {e}")
        import traceback
        traceback.print_exc()
        # 降级到网络API
        return _get_klines_from_tencent(market, code, days, end_date)


def _verify_data_consistency(full_code: str, local_df: pd.DataFrame, tdx_dir: str):
    """
    验证本地数据与腾讯API数据的一致性
    
    Args:
        full_code: 完整股票代码（如 sh600000）
        local_df: 本地数据DataFrame
        tdx_dir: 通达信目录（暂未使用）
    """
    try:
        import requests
        
        # 提取市场和代码
        market = full_code[:2]
        code = full_code[2:]
        
        # 从腾讯API获取最新一条数据进行对比
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        params = {
            "param": f"{full_code},day,,,1,qfq"  # 只获取最新1条
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=5)
        response.raise_for_status()
        
        result = response.json()
        
        if result.get('code') == 0 and result.get('data'):
            stock_data = result['data'].get(full_code, {})
            klines = stock_data.get('qfqday', []) or stock_data.get('day', [])
            
            if klines and len(klines) > 0:
                # 解析腾讯数据
                latest_line = klines[-1]
                if isinstance(latest_line, (list, tuple)) and len(latest_line) >= 6:
                    tencent_close = float(latest_line[2])
                    tencent_date = latest_line[0]
                    
                    # 获取本地数据的最新收盘价
                    local_latest = local_df.iloc[-1]
                    local_close = local_latest['close']
                    local_date = local_latest.name
                    
                    # 计算差异
                    if tencent_close > 0:
                        diff_pct = abs(local_close - tencent_close) / tencent_close * 100
                        
                        # 如果差异超过1%，给出警告
                        if diff_pct > 1.0:
                            pass  # print(f"⚠️  数据一致性警告: {full_code}")
                            # print(f"   日期: {local_date} | {tencent_date}")
                            # print(f"   本地收盘价: {local_close:.2f}")
                            # print(f"   腾讯收盘价: {tencent_close:.2f}")
                            # print(f"   差异: {diff_pct:.2f}%")
                        else:
                            pass  # print(f"✅ {full_code} 数据一致性验证通过 (差异: {diff_pct:.2f}%)")
    
    except Exception as e:
        # 静默失败，不影响主流程
        pass


def _get_klines_from_tencent(market: str, code: str, days: int, end_date: str = None, min_data_length: int = 60) -> pd.DataFrame:
    """
    从腾讯财经API获取历史K线数据（降级方案）
    
    Args:
        market: 市场代码 (sh 或 sz)
        code: 股票代码
        days: 获取天数
        end_date: 截止日期 (格式: YYYY-MM-DD)，如果提供则只返回此日期之前的数据
        min_data_length: 最小数据长度要求，默认60条
        
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
                    
                    # 【新增】如果指定了截止日期，截断数据到该日期之前
                    if end_date:
                        end_dt = pd.to_datetime(end_date)
                        df = df[df.index <= end_dt]
                        if len(df) < min_data_length:  # 使用可配置的最小长度
                            return pd.DataFrame()
                    
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


def _find_latest_whitelist(data_dir: Path):
    """
    查找最新的白名单文件
    
    Args:
        data_dir: 数据目录路径
    
    Returns:
        str or None: 最新白名单的日期字符串 (YYYYMMDD)，如果未找到返回 None
    """
    import glob
    import os
    
    # 查找所有 whitelist_*.txt 文件
    pattern = str(data_dir / "whitelist_*.txt")
    files = glob.glob(pattern)
    
    if not files:
        return None
    
    # 提取日期并排序
    dates = []
    for f in files:
        filename = os.path.basename(f)
        # 提取 YYYYMMDD
        date_str = filename.replace('whitelist_', '').replace('.txt', '')
        if date_str.isdigit() and len(date_str) == 8:
            dates.append(date_str)
    
    if not dates:
        return None
    
    # 返回最新的日期
    return max(dates)


def _load_whitelist_file(filepath: Path, date_str: str):
    """
    加载单个白名单文件
    
    Args:
        filepath: 白名单文件路径
        date_str: 日期字符串
    
    Returns:
        set: 白名单股票代码集合
    """
    try:
        whitelist_codes = set()
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    whitelist_codes.add(line)
        
        print(f"[LOAD] 加载白名单 ({date_str}): {len(whitelist_codes)} 只股票")
        print(f"[PATH] 文件路径: {filepath}")
        return whitelist_codes
    except Exception as e:
        print(f"[ERROR] 加载白名单失败: {e}")
        return set()


def load_whitelist(date_str=None):
    """
    加载股票白名单（正常交易股票，支持智能回退）
    
    加载策略:
        1. 优先使用指定日期的白名单
        2. 如果不存在，自动查找最近的白名单文件
        3. 如果完全没有，返回空集合并提示用户生成
    
    Args:
        date_str: 日期字符串 YYYYMMDD，默认今天
    
    Returns:
        set: 白名单股票代码集合
    """
    from pathlib import Path
    from datetime import datetime
    
    data_dir = Path(__file__).parent.parent / "data"
    
    # 1. 尝试加载指定日期的白名单
    if date_str is None:
        date_str = datetime.now().strftime('%Y%m%d')
    
    whitelist_file = data_dir / f"whitelist_{date_str}.txt"
    
    if whitelist_file.exists():
        # 成功加载指定日期
        return _load_whitelist_file(whitelist_file, date_str)
    
    # 2. 智能回退：查找最新的白名单
    print(f"[WARNING] 指定日期白名单不存在: {whitelist_file.name}")
    print("[INFO] 正在查找最近的白名单文件...")
    
    latest_date = _find_latest_whitelist(data_dir)
    
    if latest_date:
        latest_file = data_dir / f"whitelist_{latest_date}.txt"
        print(f"[OK] 使用最近白名单: {latest_date}")
        return _load_whitelist_file(latest_file, latest_date)
    
    # 3. 完全没有白名单
    print("[ERROR] 未找到任何白名单文件")
    print("[TIP] 请先运行: python local/manage_stock_list.py --update")
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


def _get_hs300_period_return(end_date: str, period: int = 5) -> Optional[float]:
    """
    获取沪深300在指定日期前period天的涨跌幅
    
    优先使用本地数据文件（data/index_hs300.csv），
    数据不足时通过腾讯财经API补充获取
    
    Args:
        end_date: 截止日期 (格式: YYYY-MM-DD)
        period: 天数
    
    Returns:
        涨跌幅（%），失败返回 None
    """
    # 1. 尝试从本地数据文件读取
    try:
        hs300_file = Path(__file__).parent.parent / "data" / "index_hs300.csv"
        if hs300_file.exists():
            df = pd.read_csv(hs300_file, parse_dates=['date'])
            df = df.set_index('date').sort_index()
            
            end_dt = pd.to_datetime(end_date)
            df_before = df[df.index <= end_dt]
            
            if len(df_before) >= period + 1:
                closes = df_before['close'].iloc[-period:].values
                opens_idx = df_before['open'].iloc[-period:].values
                ret = (closes[-1] - opens_idx[0]) / opens_idx[0] * 100
                return ret
    except Exception as e:
        print(f"⚠️  读取本地HS300数据失败: {e}")
    
    # 2. 本地数据不足，通过腾讯财经API获取
    try:
        fetch_days = max(period * 2, 10)  # 多取一些确保覆盖
        df = _get_klines_from_tencent('sh', '000300', fetch_days, end_date=end_date, min_data_length=period + 1)
        if df is not None and not df.empty:
            end_dt = pd.to_datetime(end_date)
            df_before = df[df.index <= end_dt]
            if len(df_before) >= period + 1:
                closes = df_before['close'].iloc[-period:].values
                opens_idx = df_before['open'].iloc[-period:].values
                ret = (closes[-1] - opens_idx[0]) / opens_idx[0] * 100
                return ret
    except Exception as e:
        print(f"⚠️  从腾讯API获取HS300数据失败: {e}")
    
    return None


def calculate_trend_score_v2(market: str, code: str, days: int = 300,
                             end_date: str = None) -> Optional[float]:
    """
    计算股票综合趋势评分（持股2~3天优化版，满分100分）

    评分维度及权重（25+25+20+20+10）：
    1. 量能因子（25分）
       - 成交量递增强度（10分）
       - 量比大小（10分）
       - 换手率活跃度（5分）

    2. 趋势因子（25分）
       - 均线多头排列（15分）
       - 均线斜率（10分）

    3. 动量因子（20分）
       - 近3日涨幅（8分）
       - 相对强度RS（7分）
       - 偏移5日均线（5分）

    4. 形态因子（20分）
       - MACD金叉及位置（10分）
       - 布林带位置与带宽（5分）
       - K线形态（5分）

    5. 风险因子（10分）
       - RSI超买超卖（5分）
       - 波动率控制（5分）

    Args:
        market: 市场代码 ('sh' 或 'sz')
        code: 股票代码
        days: 获取历史数据天数，默认300天
        end_date: 截止日期 (格式: YYYY-MM-DD)，用于回测场景

    Returns:
        float: 综合评分（0-100分），失败返回None
    """
    try:
        # 1. 获取K线数据（支持历史日期）
        df = _get_historical_klines(market, code, days, end_date=end_date)
        if df.empty or len(df) < 60:
            return None

        # 2. 计算技术指标
        df = _calculate_ma(df, periods=[5, 10, 20])
        # MACD: 需要系列数据判断柱体变化，内联计算
        ema_fast = df['close'].ewm(span=12, adjust=False).mean()
        ema_slow = df['close'].ewm(span=26, adjust=False).mean()
        dif_series = ema_fast - ema_slow
        dea_series = dif_series.ewm(span=9, adjust=False).mean()
        macd_bar_series = (dif_series - dea_series) * 2
        dif = dif_series.iloc[-1]
        dea = dea_series.iloc[-1]
        macd_bar_current = macd_bar_series.iloc[-1]
        macd_bar_prev = macd_bar_series.iloc[-2] if len(macd_bar_series) >= 2 else macd_bar_current

        rsi_val = _compute_rsi(df)
        boll_pos, upper, lower = _compute_bollinger(df)

        # 3. 综合评分（满分100分）
        total_score = 0
        latest_close = df['close'].iloc[-1]

        # ========== 1. 量能因子（25分）==========
        latest_vol = df['volume'].iloc[-1]
        vol_ma20 = df['volume'].rolling(20).mean().iloc[-1]

        # 1.1 成交量递增强度（10分）
        volumes_5d = df['volume'].iloc[-5:].values
        vol_increase_days = sum(1 for i in range(1, 5) if volumes_5d[i] > volumes_5d[i-1])
        if vol_increase_days >= 4:
            total_score += 10
        elif vol_increase_days >= 3:
            total_score += 8
        elif vol_increase_days >= 2:
            total_score += 5
        elif vol_increase_days >= 1:
            total_score += 3

        # 1.2 量比大小（10分）— 适中最好，保留强势股通道
        vol_ratio = latest_vol / vol_ma20 if vol_ma20 > 0 else 1
        if 1.0 <= vol_ratio <= 2.0:
            total_score += 10    # 温和放量，最优
        elif 2.0 < vol_ratio <= 2.5:
            total_score += 7     # 偏高但可接受（强势股通道）
        elif 0.8 <= vol_ratio < 1.0 and volumes_5d[-1] > volumes_5d[-2]:
            total_score += 5     # 缩量上涨
        elif vol_ratio > 2.5:
            total_score += 3     # 过热但还给分
        elif vol_ratio >= 0.8:
            total_score += 1
        else:
            total_score += 0

        # 1.3 换手率活跃度（5分）— 用已有df计算，避免重复获取K线
        turnover_score = calculate_cumulative_turnover_score(market, code, end_date, df=df, vol_ma20=vol_ma20)
        total_score += turnover_score

        # ========== 2. 趋势因子（25分）==========
        ma5 = df['MA5'].iloc[-1]
        ma10 = df['MA10'].iloc[-1]
        ma20 = df['MA20'].iloc[-1]

        # 2.1 均线多头排列（15分）— 去掉MA60
        if pd.notna(ma5) and pd.notna(ma10) and pd.notna(ma20):
            if ma5 > ma10 > ma20:
                total_score += 15   # 完整短期多头
            elif ma5 > ma10:
                total_score += 10   # 仅MA5>MA10
            elif ma5 > ma20:
                total_score += 7    # 仅MA5>MA20
            elif ma5 < ma10 < ma20:
                total_score += 0    # 空头
            else:
                total_score += 4    # 震荡

        # 2.2 均线斜率（10分）— 温和上行最优
        if pd.notna(ma20):
            ma20_5d_ago = df['MA20'].iloc[-5] if len(df) >= 5 else ma20
            ma20_slope = (ma20 - ma20_5d_ago) / ma20_5d_ago * 100 if ma20_5d_ago > 0 else 0

            if 0.5 <= ma20_slope <= 2.0:
                total_score += 10   # 温和上行，最优
            elif 2.0 < ma20_slope <= 4.0:
                total_score += 7    # 较快上行（强势股通道）
            elif ma20_slope > 4.0:
                total_score += 3    # 过陡
            elif ma20_slope > 0:
                total_score += 5    # 微幅上升
            else:
                total_score += 0    # 下降

        # ========== 3. 动量因子（20分）==========

        # 3.1 近3日涨幅（8分）
        close_3d_ago = df['close'].iloc[-3] if len(df) >= 3 else latest_close
        return_3d = (latest_close - close_3d_ago) / close_3d_ago * 100 if close_3d_ago > 0 else 0

        if 2 <= return_3d <= 5:
            total_score += 8     # 最优：恰好在目标起步区间
        elif 5 < return_3d <= 8:
            total_score += 6     # 偏高但强势股通道
        elif 0 <= return_3d < 2:
            total_score += 4     # 微涨
        elif 8 < return_3d <= 10:
            total_score += 2     # 涨多了
        elif return_3d > 10:
            total_score += 0     # 过热
        else:
            total_score += 0     # 下跌

        # 3.2 相对强度RS（7分）
        close_5d_ago = df['close'].iloc[-5] if len(df) >= 5 else latest_close
        return_5d = (latest_close - close_5d_ago) / close_5d_ago * 100 if close_5d_ago > 0 else 0

        hs300_return = _get_hs300_period_return(end_date, 5) if end_date else None
        if hs300_return is not None:
            relative_strength = return_5d - hs300_return
            if 0 <= relative_strength <= 3:
                total_score += 7   # 刚刚跑赢，最优
            elif 3 < relative_strength <= 5:
                total_score += 5   # 明显跑赢（强势股通道）
            elif relative_strength > 5:
                total_score += 3   # 大幅跑赢，透支可能
            else:
                total_score += 0   # 跑输
        else:
            if 2 <= return_5d <= 5:
                total_score += 7
            elif 5 < return_5d <= 8:
                total_score += 5
            elif 0 <= return_5d < 2:
                total_score += 3
            else:
                total_score += 0

        # 3.3 偏移5日均线（5分）
        deviation_pct = (latest_close - ma5) / ma5 * 100 if pd.notna(ma5) and ma5 > 0 else 0
        if 0.5 <= deviation_pct <= 2.5:
            total_score += 5     # 最佳买点
        elif -0.5 <= deviation_pct < 0.5:
            total_score += 3     # 在5日线附近
        elif 2.5 < deviation_pct <= 4.0:
            total_score += 3     # 略偏离（强势股可接受）
        elif 4.0 < deviation_pct <= 6.0:
            total_score += 2     # 偏高
        else:
            total_score += 0     # 偏移过大

        # ========== 4. 形态因子（20分）==========

        # 4.1 MACD金叉及位置+柱体变化（10分）
        if dif > dea and dif > 0:
            if macd_bar_current > macd_bar_prev:
                total_score += 10   # 金叉+零轴上+柱体放大，最强信号
            else:
                total_score += 6    # 金叉+零轴上+柱体缩小
        elif dif > dea and dif <= 0:
            total_score += 4        # 金叉+零轴下
        elif dif < dea and dif > 0:
            total_score += 3        # 死叉+零轴上
        else:
            total_score += 0        # 死叉+零轴下

        # 4.2 布林带位置与带宽（5分）
        ma20_series = df['close'].rolling(20).mean()
        std20_series = df['close'].rolling(20).std()
        upper_band = ma20_series + 2 * std20_series
        lower_band = ma20_series - 2 * std20_series
        bandwidth_pct = (upper_band - lower_band) / df['close'] * 100
        current_bw = bandwidth_pct.iloc[-1]
        avg_bw_10 = bandwidth_pct.iloc[-10:].mean() if len(bandwidth_pct) >= 10 else current_bw
        is_narrowing = current_bw < avg_bw_10 * 0.85  # 收窄15%以上

        if boll_pos == 0:
            mid = (upper + lower) / 2
            if latest_close > mid and is_narrowing:
                total_score += 5    # 中轨上方+收窄蓄力
            elif latest_close > mid:
                total_score += 3    # 中轨上方但无收窄
            else:
                total_score += 1    # 中轨下方
        elif boll_pos == 1:
            total_score += 2        # 突破上轨
        else:
            total_score += 0        # 跌破下轨

        # 4.3 K线形态（5分）
        latest_open = df['open'].iloc[-1]
        latest_high = df['high'].iloc[-1]
        latest_low = df['low'].iloc[-1]
        prev_close = df['close'].iloc[-2] if len(df) >= 2 else latest_open

        amplitude = (latest_high - latest_low) / prev_close * 100 if prev_close > 0 else 0
        candle_body_pct = (latest_close - latest_open) / latest_open * 100 if latest_open > 0 else 0
        upper_shadow = (latest_high - max(latest_open, latest_close)) / latest_high * 100 if latest_high > 0 else 0

        if amplitude < 3 and candle_body_pct > 0 and upper_shadow < 1.5:
            total_score += 5        # 小阳线/十字星+短上影，最优
        elif 2 <= candle_body_pct <= 4:
            total_score += 3        # 中阳线
        elif candle_body_pct > 5 or upper_shadow > 3:
            total_score += 0        # 大阳线或长上影
        elif candle_body_pct > 0 and amplitude < 5:
            total_score += 2        # 普通小阳
        else:
            total_score += 0        # 阴线或异常

        # ========== 5. 风险因子（10分）==========

        # 5.1 RSI超买超卖（5分）— 不变
        if 50 <= rsi_val <= 70:
            total_score += 5
        elif rsi_val > 70:
            total_score += 2
        elif 40 <= rsi_val < 50:
            total_score += 3
        elif rsi_val < 40:
            total_score += 1
        else:
            total_score += 0

        # 5.2 波动率控制（5分）— 不变
        amplitudes = []
        if len(df) >= 5:
            high_5d = df['high'].iloc[-5:].max()
            low_5d = df['low'].iloc[-5:].min()
            close_5d_start = df['close'].iloc[-5]
            amp_5d = (high_5d - low_5d) / close_5d_start * 100 if close_5d_start > 0 else 0
            amplitudes.append(amp_5d)
        if len(df) >= 10:
            high_10d = df['high'].iloc[-10:].max()
            low_10d = df['low'].iloc[-10:].min()
            close_10d_start = df['close'].iloc[-10]
            amp_10d = (high_10d - low_10d) / close_10d_start * 100 if close_10d_start > 0 else 0
            amplitudes.append(amp_10d)
        if len(df) >= 20:
            high_20d = df['high'].iloc[-20:].max()
            low_20d = df['low'].iloc[-20:].min()
            close_20d_start = df['close'].iloc[-20]
            amp_20d = (high_20d - low_20d) / close_20d_start * 100 if close_20d_start > 0 else 0
            amplitudes.append(amp_20d)

        if len(amplitudes) == 3:
            avg_volatility = amplitudes[0] * 0.5 + amplitudes[1] * 0.3 + amplitudes[2] * 0.2
        elif len(amplitudes) == 2:
            avg_volatility = amplitudes[0] * 0.6 + amplitudes[1] * 0.4
        elif len(amplitudes) == 1:
            avg_volatility = amplitudes[0]
        else:
            avg_volatility = 0

        if 2 <= avg_volatility <= 8:
            total_score += 5     # 低波动，匹配2~4%收益目标
        elif 8 < avg_volatility <= 15:
            total_score += 3     # 中等波动
        elif avg_volatility < 2:
            total_score += 3     # 波动过低，可能不动
        elif 15 < avg_volatility <= 25:
            total_score += 1     # 高波动
        else:
            total_score += 0     # 极高波动，排除

        total_score = max(0, min(100, total_score))
        return round(total_score, 1)

    except Exception as e:
        print(f"⚠️  计算评分失败 ({market}{code}): {e}")
        return None
