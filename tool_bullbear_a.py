# -*- coding: utf-8 -*-
"""
个股多头/空头排列判断模块

功能：
1. 使用腾讯财经API获取股票历史K线数据
2. 计算常用移动平均线：MA5、MA10、MA20、MA60
3. 定义多头/空头判定规则（均线排列 + 辅助验证）
4. 对配置的股票池进行批量分析并输出结果
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from loguru import logger
import requests
import re

from src.utils.config import get_config


class TrendAnalyzer:
    """趋势分析器 - 判断个股多头/空头排列"""
    
    def __init__(self):
        """初始化趋势分析器"""
        self.config = get_config()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    
    def _get_historical_klines_from_tencent(self, market: str, code: str, days: int = 250) -> pd.DataFrame:
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
            # 腾讯财经日K线API
            url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
            params = {
                "param": f"{market}{code},day,,,{days},qfq"  # qfq=前复权
            }
            
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            
            # 解析腾讯财经返回的数据结构
            if result.get('code') == 0 and result.get('data'):
                stock_data = result['data'].get(f'{market}{code}', {})
                klines = stock_data.get('qfqday', []) or stock_data.get('day', [])
                
                if klines:
                    records = []
                    for line in klines:
                        # 兼容处理：line可能是列表或字典
                        if isinstance(line, dict):
                            # 跳过分红数据
                            continue
                        
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
                        logger.debug(f"成功从腾讯财经获取 {market}{code} 历史K线：{len(df)}条")
                        return df
            
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"腾讯财经历史K线获取失败 ({market}{code}): {e}")
            return pd.DataFrame()
    
    def calculate_ma(self, df: pd.DataFrame, periods: List[int] = [5, 10, 20, 60]) -> pd.DataFrame:
        """
        计算移动平均线
        
        Args:
            df: K线数据DataFrame
            periods: 均线周期列表
            
        Returns:
            添加了MA列的DataFrame
        """
        for p in periods:
            df[f'MA{p}'] = df['close'].rolling(window=p).mean()
        return df
    
    def check_alignment(self, df: pd.DataFrame, short: int = 5, mid: int = 10, 
                       long_period: int = 20, extra_long: int = 60) -> Tuple[str, str]:
        """
        判断均线排列状态
        
        Args:
            df: 包含MA数据的DataFrame
            short: 短期均线周期
            mid: 中期均线周期
            long_period: 长期均线周期
            extra_long: 超长期均线周期
            
        Returns:
            (trend_type, message): 趋势类型和描述信息
            - trend_type: 'bullish' (多头), 'bearish' (空头), 'neutral' (盘整)
        """
        latest = df.iloc[-1]  # 最新一天的数据
        
        # 检查最新值是否为空（数据不足）
        if pd.isna(latest.get(f'MA{short}')) or pd.isna(latest.get(f'MA{mid}')) or pd.isna(latest.get(f'MA{long_period}')):
            return 'neutral', "数据不足，无法判断均线排列"
        
        ma_short = latest[f'MA{short}']
        ma_mid = latest[f'MA{mid}']
        ma_long = latest[f'MA{long_period}']
        
        # 多头排列: 短 > 中 > 长，且短均线 > 长均线（确保方向）
        if ma_short > ma_mid > ma_long:
            # 额外检查：短期均线是否明显高于长期均线（避免粘合误判）
            ratio = ma_short / ma_long if ma_long > 0 else 1
            if ratio > 1.01:  # 1% 以上差距
                return 'bullish', f"均线多头排列 (MA{short}>MA{mid}>MA{long_period})"
            else:
                return 'neutral', f"均线粘合略偏多 (MA{short}>MA{mid}>MA{long_period} 但差距小于1%)"
        
        # 空头排列: 短 < 中 < 长
        if ma_short < ma_mid < ma_long:
            ratio = ma_long / ma_short if ma_short > 0 else 1
            if ratio > 1.01:
                return 'bearish', f"均线空头排列 (MA{short}<MA{mid}<MA{long_period})"
            else:
                return 'neutral', f"均线粘合略偏空 (MA{short}<MA{mid}<MA{long_period} 但差距小于1%)"
        
        # 其他情况：均线缠绕、交叉
        return 'neutral', "均线相互缠绕，无明显趋势"
    
    def compute_macd(self, df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[float, float, float]:
        """
        计算MACD指标并返回最新值
        
        Returns:
            (dif, dea, macd_bar): DIF值、DEA值、柱状线值
        """
        ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=signal, adjust=False).mean()
        macd_bar = (dif - dea) * 2  # 柱状线
        return dif.iloc[-1], dea.iloc[-1], macd_bar.iloc[-1]
    
    def compute_rsi(self, df: pd.DataFrame, period: int = 14) -> float:
        """计算RSI指标"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]
    
    def compute_bollinger_bands(self, df: pd.DataFrame, period: int = 20, std_dev: int = 2) -> Tuple[int, float, float]:
        """
        计算布林带，返回最新价相对于上中下轨的位置
        
        Returns:
            (position, upper, lower): 位置标识、上轨、下轨
            position: 1=突破上轨，0=中轨附近，-1=跌破下轨
        """
        ma = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()
        upper = ma + std_dev * std
        lower = ma - std_dev * std
        latest_close = df['close'].iloc[-1]
        latest_upper = upper.iloc[-1]
        latest_lower = lower.iloc[-1]
        
        # 返回相对位置
        if latest_close > latest_upper:
            position = 1
        elif latest_close < latest_lower:
            position = -1
        else:
            position = 0
        
        return position, latest_upper, latest_lower
    
    def analyze_stock(self, symbol: str, name: str = '') -> Optional[Dict]:
        """
        综合分析一只股票
        
        Args:
            symbol: 股票代码 (格式: sz.002706 或 sh.600519)
            name: 股票名称
            
        Returns:
            分析结果字典，包含所有指标和判断结论
        """
        try:
            # 提取市场前缀和代码
            parts = symbol.split('.')
            if len(parts) != 2:
                logger.error(f"股票代码格式错误: {symbol}")
                return None
            
            market = parts[0].lower()  # sh 或 sz
            code = parts[1]
            
            logger.info(f"\n{'='*60}")
            logger.info(f"📊 分析 {name} ({symbol})")
            logger.info(f"{'='*60}")
            
            # 1. 获取数据
            df = self._get_historical_klines_from_tencent(market, code, days=300)
            if df.empty or len(df) < 60:
                logger.warning(f"❌ 数据不足（少于60个交易日），当前: {len(df)}条")
                return None
            
            # 2. 计算均线
            df = self.calculate_ma(df)
            
            # 3. 判断均线排列
            trend, ma_msg = self.check_alignment(df)
            
            # 4. 辅助指标
            dif, dea, macd_bar = self.compute_macd(df)
            rsi_val = self.compute_rsi(df)
            boll_pos, upper, lower = self.compute_bollinger_bands(df)
            latest_close = df['close'].iloc[-1]
            latest_vol = df['volume'].iloc[-1]
            vol_ma20 = df['volume'].rolling(20).mean().iloc[-1]
            
            # 5. 综合评分
            score = 0
            reasons = []
            
            if trend == 'bullish':
                score += 3
                reasons.append("均线多头排列")
            elif trend == 'bearish':
                score -= 3
                reasons.append("均线空头排列")
            
            # MACD辅助
            if dif > dea and dif > 0:
                score += 1
                reasons.append("MACD金叉且位于零轴上")
            elif dif < dea and dif < 0:
                score -= 1
                reasons.append("MACD死叉且位于零轴下")
            
            # RSI辅助
            if rsi_val > 60:
                score += 1
                reasons.append(f"RSI强势 ({rsi_val:.1f})")
            elif rsi_val < 40:
                score -= 1
                reasons.append(f"RSI弱势 ({rsi_val:.1f})")
            
            # 布林带辅助
            if boll_pos == 1:
                score += 1
                reasons.append("价格突破布林上轨")
            elif boll_pos == -1:
                score -= 1
                reasons.append("价格跌破布林下轨")
            
            # 成交量验证
            vol_ratio = latest_vol / vol_ma20 if vol_ma20 > 0 else 1
            if vol_ratio > 1.2 and latest_close > df['close'].iloc[-2]:
                score += 0.5
                reasons.append("价涨量增")
            elif vol_ratio > 1.2 and latest_close < df['close'].iloc[-2]:
                score -= 0.5
                reasons.append("价跌量增")
            
            # 6. 最终结论
            if score >= 2:
                conclusion = "🟢 多头排列 (强烈看涨)"
                trend_label = "BULLISH"
            elif score > 0:
                conclusion = "🟡 偏多震荡 (谨慎看涨)"
                trend_label = "SLIGHTLY_BULLISH"
            elif score == 0:
                conclusion = "⚪ 无明显趋势 (观望)"
                trend_label = "NEUTRAL"
            elif score > -2:
                conclusion = "🟠 偏空震荡 (谨慎看跌)"
                trend_label = "SLIGHTLY_BEARISH"
            else:
                conclusion = "🔴 空头排列 (强烈看跌)"
                trend_label = "BEARISH"
            
            # 7. 构建结果
            result = {
                'symbol': symbol,
                'name': name,
                'date': df.index[-1].strftime('%Y-%m-%d'),
                'close': latest_close,
                'trend': trend_label,
                'score': score,
                'ma_message': ma_msg,
                'ma5': df['MA5'].iloc[-1],
                'ma10': df['MA10'].iloc[-1],
                'ma20': df['MA20'].iloc[-1],
                'ma60': df['MA60'].iloc[-1],
                'macd_dif': dif,
                'macd_dea': dea,
                'macd_bar': macd_bar,
                'rsi': rsi_val,
                'boll_upper': upper,
                'boll_lower': lower,
                'boll_position': boll_pos,
                'volume': latest_vol,
                'vol_ma20': vol_ma20,
                'vol_ratio': vol_ratio,
                'reasons': reasons,
                'conclusion': conclusion
            }
            
            # 8. 输出详细结果
            logger.info(f"最新日期: {result['date']}")
            logger.info(f"最新收盘价: {latest_close:.2f}")
            logger.info(f"均线状态: {ma_msg}")
            logger.info(f"MA5: {df['MA5'].iloc[-1]:.2f} | MA10: {df['MA10'].iloc[-1]:.2f} | MA20: {df['MA20'].iloc[-1]:.2f} | MA60: {df['MA60'].iloc[-1]:.2f}")
            logger.info(f"MACD: DIF={dif:.3f} | DEA={dea:.3f} | 柱线={macd_bar:.3f}")
            logger.info(f"RSI(14): {rsi_val:.1f}")
            logger.info(f"布林带: 上轨={upper:.2f} | 中轨={(upper+lower)/2:.2f} | 下轨={lower:.2f}")
            logger.info(f"成交量: {latest_vol:.0f} (20日均量: {vol_ma20:.0f}, 比例: {vol_ratio:.2f})")
            logger.info(f"综合评分: {score:.1f} ({'偏多' if score>1 else '偏空' if score<-1 else '中性'})")
            logger.info(f"关键信号: {'; '.join(reasons) if reasons else '无明显信号'}")
            logger.info(f"\n📊 最终判断: {conclusion}")
            
            return result
            
        except Exception as e:
            logger.error(f"分析出错 ({symbol}): {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def analyze_stock_pool(self) -> List[Dict]:
        """
        分析配置的股票池中的所有股票
        
        Returns:
            所有股票的分析结果列表
        """
        # 从配置中获取股票池
        monitor_config = self.config.stock_news_monitor
        
        if not monitor_config.enabled:
            logger.warning("⚠️ 股票资讯监控未启用，无法获取股票池")
            return []
        
        stock_pool = [
            {'code': stock.code, 'name': stock.name}
            for stock in monitor_config.stock_pool
        ]
        
        if not stock_pool:
            logger.warning("⚠️ 股票池为空")
            return []
        
        logger.info(f"\n{'='*60}")
        logger.info(f"🚀 开始分析股票池 ({len(stock_pool)}只股票)")
        logger.info(f"{'='*60}")
        
        results = []
        for stock in stock_pool:
            result = self.analyze_stock(stock['code'], stock['name'])
            if result:
                results.append(result)
            
            # 避免请求过快
            import time
            time.sleep(1)
        
        # 输出汇总报告
        self._print_summary(results)
        
        return results
    
    def _print_summary(self, results: List[Dict]):
        """打印分析汇总报告"""
        if not results:
            logger.warning("\n⚠️ 没有有效的分析结果")
            return
        
        logger.info(f"\n{'='*60}")
        logger.info(f"📋 分析汇总报告")
        logger.info(f"{'='*60}")
        
        bullish_count = sum(1 for r in results if r['trend'] in ['BULLISH', 'SLIGHTLY_BULLISH'])
        bearish_count = sum(1 for r in results if r['trend'] in ['BEARISH', 'SLIGHTLY_BEARISH'])
        neutral_count = sum(1 for r in results if r['trend'] == 'NEUTRAL')
        
        logger.info(f"总计分析: {len(results)}只股票")
        logger.info(f"🟢 多头排列: {bullish_count}只")
        logger.info(f"🔴 空头排列: {bearish_count}只")
        logger.info(f"⚪ 中性观望: {neutral_count}只")
        
        logger.info(f"\n详细结果:")
        for i, result in enumerate(results, 1):
            trend_emoji = "🟢" if result['trend'] in ['BULLISH', 'SLIGHTLY_BULLISH'] else "🔴" if result['trend'] in ['BEARISH', 'SLIGHTLY_BEARISH'] else "⚪"
            logger.info(f"{i}. {trend_emoji} {result['name']} ({result['symbol']})")
            logger.info(f"   收盘价: {result['close']:.2f} | 评分: {result['score']:.1f} | {result['conclusion']}")


def main():
    """主函数 - 分析配置的股票池"""
    analyzer = TrendAnalyzer()
    results = analyzer.analyze_stock_pool()
    
    if results:
        logger.success(f"\n✅ 分析完成，共分析 {len(results)}只股票")
    else:
        logger.error("\n❌ 分析失败")


if __name__ == "__main__":
    main()
