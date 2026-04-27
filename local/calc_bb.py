# -*- coding: utf-8 -*-
"""
独立股票多空信号评估工具

功能：
1. 使用腾讯财经API获取股票历史K线数据
2. 计算常用移动平均线：MA5、MA10、MA20、MA60
3. 定义多头/空头判定规则（均线排列 + 辅助验证）
4. 综合评分系统（-5到+5分）
5. 持久化评分数据到txt文件，支持历史对比
6. 完全独立于项目配置系统，直接在代码中配置股票池

使用方法：
    在 STOCK_POOL 列表中配置需要评估的股票（只需代码，无需名称）
    运行: python calc_bb.py
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from loguru import logger
import requests
import os
from pathlib import Path
import time
import sys

# 添加当前目录到Python路径，以便导入utils模块
sys.path.insert(0, str(Path(__file__).parent))
from utils import get_stock_name  # 导入统一的股票名称获取函数


# ==================== 配置区域 ====================
"""
# 股票列表1#0420
STOCK_POOL = [
    "sh.601991",
    "sh.603565",
    "sh.603606",
    "sh.688089",
    "sh.688211",
    "sh.688392",
    "sh.688558",
    "sh.688683"
]
"""
"""
# 股票列表2#仙人指路#0422
STOCK_POOL = [
    "sz.300179",
    "sz.301150",
    "sz.301389",
    "sh.688146",
    "sh.688268",
    "sh.688655",
    "sh.688707"
]
"""

# 股票列表3#持续放量#0422
STOCK_POOL = [
    "sz.000526",
    "sz.002830",
    "sz.003013",
    "sh.600963",      
    "sh.601777",
    "sh.688020"  
]

"""
# 股票列表4#放量上攻#0422
STOCK_POOL = [
    "sz.000722",
    "sh.603936"
]
"""

# 评分文件路径
SCORE_FILE_PATH = Path(__file__).parent.parent / "data" / "trend_scores_1.txt"
# r'E:\LearnPY\Projects\StockBot\data\trend_scores_1.txt'
# =================================================


class StockTrendAnalyzer:
    """股票趋势分析器 - 独立版本"""
    
    def __init__(self):
        """初始化分析器"""
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        # 确保评分文件目录存在
        SCORE_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    def _get_historical_klines(self, market: str, code: str, days: int = 300) -> pd.DataFrame:
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
            url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
            params = {
                "param": f"{market}{code},day,,,{days},qfq"  # qfq=前复权
            }
            
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
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
                        logger.debug(f"✅ 获取 {market}{code} K线数据: {len(df)}条")
                        return df
            
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"❌ 获取K线数据失败 ({market}{code}): {e}")
            return pd.DataFrame()
    
    def _calculate_ma(self, df: pd.DataFrame, periods: List[int] = [5, 10, 20, 60]) -> pd.DataFrame:
        """计算移动平均线"""
        for p in periods:
            df[f'MA{p}'] = df['close'].rolling(window=p).mean()
        return df
    
    def _check_trend_alignment(self, df: pd.DataFrame) -> Tuple[str, str]:
        """
        判断均线排列状态
        
        Returns:
            (trend_type, message): 趋势类型和描述
        """
        latest = df.iloc[-1]
        
        # 检查数据完整性
        if pd.isna(latest.get('MA5')) or pd.isna(latest.get('MA10')) or pd.isna(latest.get('MA20')):
            return 'neutral', "数据不足，无法判断均线排列"
        
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
    
    def _compute_macd(self, df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[float, float, float]:
        """计算MACD指标"""
        ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=signal, adjust=False).mean()
        macd_bar = (dif - dea) * 2
        return dif.iloc[-1], dea.iloc[-1], macd_bar.iloc[-1]
    
    def _compute_rsi(self, df: pd.DataFrame, period: int = 14) -> float:
        """计算RSI指标"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]
    
    def _compute_bollinger(self, df: pd.DataFrame, period: int = 20, std_dev: int = 2) -> Tuple[int, float, float]:
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
    
    def _save_score(self, symbol: str, date: str, score: float):
        """保存评分到文件"""
        try:
            file_exists = os.path.exists(SCORE_FILE_PATH)
            
            with open(SCORE_FILE_PATH, 'a', encoding='utf-8') as f:
                if not file_exists:
                    f.write("股票代码,日期,评分\n")
                f.write(f"{symbol},{date},{score:.1f}\n")
            
            logger.debug(f"💾 评分已保存: {symbol} | {date} | {score:.1f}")
            
        except Exception as e:
            logger.error(f"❌ 保存评分失败: {e}")
    
    def _get_previous_score(self, symbol: str, current_date: str) -> Optional[float]:
        """获取前一日评分"""
        try:
            if not os.path.exists(SCORE_FILE_PATH):
                return None
            
            current_dt = datetime.strptime(current_date, '%Y-%m-%d')
            previous_dt = current_dt - timedelta(days=1)
            previous_date = previous_dt.strftime('%Y-%m-%d')
            
            with open(SCORE_FILE_PATH, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in lines[1:]:  # 跳过表头
                    line = line.strip()
                    if not line:
                        continue
                    
                    parts = line.split(',')
                    if len(parts) == 3 and parts[0] == symbol and parts[1] == previous_date:
                        try:
                            return float(parts[2])
                        except ValueError:
                            continue
            
            return None
            
        except Exception as e:
            logger.error(f"❌ 读取历史评分失败: {e}")
            return None
    
    def analyze_stock(self, symbol: str, name: str = '') -> Optional[Dict]:
        """
        综合分析一只股票
        
        Args:
            symbol: 股票代码 (格式: sh.600519 或 sz.000858)
            name: 股票名称
            
        Returns:
            分析结果字典
        """
        try:
            # 解析股票代码
            parts = symbol.split('.')
            if len(parts) != 2:
                logger.error(f"❌ 股票代码格式错误: {symbol}")
                return None
            
            market = parts[0].lower()
            code = parts[1]
            
            logger.info(f"\n{'='*70}")
            logger.info(f"📊 分析 {name} ({symbol})")
            logger.info(f"{'='*70}")
            
            # 1. 获取K线数据
            df = self._get_historical_klines(market, code, days=300)
            if df.empty or len(df) < 60:
                logger.warning(f"⚠️ 数据不足（需至少60个交易日），当前: {len(df)}条")
                return None
            
            # 2. 计算均线
            df = self._calculate_ma(df)
            
            # 3. 判断趋势
            trend, ma_msg = self._check_trend_alignment(df)
            
            # 4. 计算辅助指标
            dif, dea, macd_bar = self._compute_macd(df)
            rsi_val = self._compute_rsi(df)
            boll_pos, upper, lower = self._compute_bollinger(df)
            
            latest_close = df['close'].iloc[-1]
            latest_vol = df['volume'].iloc[-1]
            vol_ma20 = df['volume'].rolling(20).mean().iloc[-1]
            vol_ratio = latest_vol / vol_ma20 if vol_ma20 > 0 else 1
            
            # 5. 综合评分
            score = 0
            reasons = []
            
            # 均线排列评分
            if trend == 'bullish':
                score += 3
                reasons.append("✅ 均线多头排列")
            elif trend == 'bearish':
                score -= 3
                reasons.append("❌ 均线空头排列")
            
            # MACD评分
            if dif > dea and dif > 0:
                score += 1
                reasons.append(f"✅ MACD金叉且零轴上方 (DIF={dif:.3f})")
            elif dif < dea and dif < 0:
                score -= 1
                reasons.append(f"❌ MACD死叉且零轴下方 (DIF={dif:.3f})")
            
            # RSI评分
            if rsi_val > 60:
                score += 1
                reasons.append(f"✅ RSI强势区 ({rsi_val:.1f})")
            elif rsi_val < 40:
                score -= 1
                reasons.append(f"❌ RSI弱势区 ({rsi_val:.1f})")
            
            # 布林带评分
            if boll_pos == 1:
                score += 1
                reasons.append(f"✅ 价格突破布林上轨 ({upper:.2f})")
            elif boll_pos == -1:
                score -= 1
                reasons.append(f"❌ 价格跌破布林下轨 ({lower:.2f})")
            
            # 成交量评分
            prev_close = df['close'].iloc[-2]
            if vol_ratio > 1.2 and latest_close > prev_close:
                score += 0.5
                reasons.append(f"✅ 价涨量增 (量比{vol_ratio:.2f})")
            elif vol_ratio > 1.2 and latest_close < prev_close:
                score -= 0.5
                reasons.append(f"❌ 价跌量增 (量比{vol_ratio:.2f})")
            
            # 6. 最终结论
            if score >= 2:
                conclusion = "🟢 强烈看涨 (多头排列)"
                trend_label = "BULLISH"
            elif score > 0:
                conclusion = "🟡 谨慎看涨 (偏多震荡)"
                trend_label = "SLIGHTLY_BULLISH"
            elif score == 0:
                conclusion = "⚪ 观望等待 (无明显趋势)"
                trend_label = "NEUTRAL"
            elif score > -2:
                conclusion = "🟠 谨慎看跌 (偏空震荡)"
                trend_label = "SLIGHTLY_BEARISH"
            else:
                conclusion = "🔴 强烈看跌 (空头排列)"
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
            
            # 8. 保存评分
            analysis_date = result['date']
            self._save_score(symbol, analysis_date, score)
            
            # 9. 获取前日评分对比
            previous_score = self._get_previous_score(symbol, analysis_date)
            result['previous_score'] = previous_score
            
            # 10. 输出详细报告
            self._print_detail_report(result, previous_score)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 分析出错 ({symbol}): {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def _print_detail_report(self, result: Dict, previous_score: Optional[float]):
        """打印详细分析报告"""
        logger.info(f"📅 分析日期: {result['date']}")
        logger.info(f"💰 最新收盘价: ¥{result['close']:.2f}")
        logger.info(f"📈 均线状态: {result['ma_message']}")
        logger.info(f"   MA5: {result['ma5']:.2f} | MA10: {result['ma10']:.2f} | MA20: {result['ma20']:.2f} | MA60: {result['ma60']:.2f}")
        logger.info(f"📊 MACD: DIF={result['macd_dif']:.3f} | DEA={result['macd_dea']:.3f} | 柱线={result['macd_bar']:.3f}")
        logger.info(f"📉 RSI(14): {result['rsi']:.1f}")
        logger.info(f"📐 布林带: 上轨={result['boll_upper']:.2f} | 中轨={(result['boll_upper']+result['boll_lower'])/2:.2f} | 下轨={result['boll_lower']:.2f}")
        logger.info(f"📦 成交量: {result['volume']:.0f} (20日均量: {result['vol_ma20']:.0f}, 量比: {result['vol_ratio']:.2f})")
        logger.info(f"⭐ 综合评分: {result['score']:+.1f}分")
        
        # 显示评分变化
        if previous_score is not None:
            change = result['score'] - previous_score
            if change > 0:
                change_str = f"↑ +{change:.1f}"
            elif change < 0:
                change_str = f"↓ {change:.1f}"
            else:
                change_str = "→ 持平"
            logger.info(f"📊 评分变化: 昨日 {previous_score:.1f} → 今日 {result['score']:.1f} ({change_str})")
        else:
            logger.info(f"📊 评分变化: 无历史数据")
        
        logger.info(f"🔍 关键信号:")
        for reason in result['reasons']:
            logger.info(f"   {reason}")
        
        logger.info(f"\n🎯 最终判断: {result['conclusion']}")
    
    def analyze_stock_pool(self, stock_pool: List[str]) -> List[Dict]:
        """
        批量分析股票池
        
        Args:
            stock_pool: 股票代码列表 ["sh.600519", "sz.000858", ...]
            
        Returns:
            分析结果列表
        """
        if not stock_pool:
            logger.warning("⚠️ 股票池为空")
            return []
        
        logger.info(f"\n{'='*70}")
        logger.info(f"🚀 开始批量分析 ({len(stock_pool)}只股票)")
        logger.info(f"{'='*70}")
        
        results = []
        for i, symbol in enumerate(stock_pool, 1):
            # 自动获取股票名称
            parts = symbol.split('.')
            if len(parts) == 2:
                code = parts[1]
                name = get_stock_name(code)
                logger.info(f"[{i}/{len(stock_pool)}] 正在分析 {name} ({symbol})...")
            else:
                logger.warning(f"⚠️ 股票代码格式错误: {symbol}，跳过")
                continue
            
            result = self.analyze_stock(symbol, name)
            if result:
                results.append(result)
            
            # 避免请求过快
            if i < len(stock_pool):
                time.sleep(1)
        
        # 输出汇总报告
        self._print_summary(results)
        
        return results
    
    def _print_summary(self, results: List[Dict]):
        """打印汇总报告"""
        if not results:
            logger.warning("\n⚠️ 没有有效的分析结果")
            return
        
        logger.info(f"\n{'='*70}")
        logger.info(f"📋 分析汇总报告")
        logger.info(f"{'='*70}")
        
        bullish_count = sum(1 for r in results if r['trend'] in ['BULLISH', 'SLIGHTLY_BULLISH'])
        bearish_count = sum(1 for r in results if r['trend'] in ['BEARISH', 'SLIGHTLY_BEARISH'])
        neutral_count = sum(1 for r in results if r['trend'] == 'NEUTRAL')
        
        logger.info(f"📊 总计分析: {len(results)}只股票")
        logger.info(f"🟢 多头排列: {bullish_count}只")
        logger.info(f"🔴 空头排列: {bearish_count}只")
        logger.info(f"⚪ 中性观望: {neutral_count}只")
        
        logger.info(f"\n📝 详细排名:")
        # 按评分从高到低排序
        sorted_results = sorted(results, key=lambda x: x['score'], reverse=True)
        
        for i, result in enumerate(sorted_results, 1):
            if result['trend'] in ['BULLISH', 'SLIGHTLY_BULLISH']:
                emoji = "🟢"
            elif result['trend'] in ['BEARISH', 'SLIGHTLY_BEARISH']:
                emoji = "🔴"
            else:
                emoji = "⚪"
            
            logger.info(f"{i}. {emoji} {result['name']} ({result['symbol']})")
            logger.info(f"   收盘价: ¥{result['close']:.2f} | 评分: {result['score']:+.1f} | {result['conclusion']}")
            
            # 显示与前日对比
            if result.get('previous_score') is not None:
                change = result['score'] - result['previous_score']
                if change > 0:
                    change_icon = "📈"
                elif change < 0:
                    change_icon = "📉"
                else:
                    change_icon = "➡️"
                logger.info(f"   评分变化: {change_icon} {result['previous_score']:.1f} → {result['score']:.1f} ({change:+.1f})")


def main():
    """主函数"""
    logger.info("="*70)
    logger.info("🎯 独立股票多空信号评估工具")
    logger.info("="*70)
    logger.info(f"📅 运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"📂 评分文件: {SCORE_FILE_PATH}")
    logger.info(f"📊 待分析股票: {len(STOCK_POOL)}只")
    
    # 创建分析器
    analyzer = StockTrendAnalyzer()
    
    # 执行分析
    results = analyzer.analyze_stock_pool(STOCK_POOL)
    
    # 输出总结
    if results:
        logger.success(f"\n✅ 分析完成！共分析 {len(results)}只股票")
        logger.info(f"💾 评分数据已保存到: {SCORE_FILE_PATH}")
    else:
        logger.error("\n❌ 分析失败，请检查网络连接或股票代码")


if __name__ == "__main__":
    main()
