# -*- coding: utf-8 -*-
"""市场数据获取模块 - 基于东方财富网网页爬虫"""
import os
from datetime import datetime, timedelta
from typing import Optional, List
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
import re
import json
from loguru import logger

from src.models.models import MarketData
from src.utils.config import get_config


class EastMoneyWebScraper:
    """基于东方财富网网页爬虫的数据提供者"""
    
    def __init__(self):
        self.config = get_config()
        # ETF代码映射
        self.etf_codes = {
            "sh.513120": "513120",  # 港股创新药ETF
            "sh.513050": "513050"   # 中概互联网ETF
        }
        
        # 设置请求头，模拟浏览器访问
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
        }
    
    def get_realtime_data(self, symbol: str) -> Optional[MarketData]:
        """获取实时行情数据（从东方财富网网页）"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                if symbol not in self.etf_codes:
                    logger.error(f"不支持的ETF代码：{symbol}")
                    return None
                
                code = self.etf_codes[symbol]
                
                # 方法1: 尝试从东方财富个股页面抓取
                market_data = self._scrape_from_quote_page(symbol, code)
                
                if market_data:
                    logger.info(f"成功获取 {symbol} ({market_data.name}) 实时行情：现价={market_data.current_price:.3f}, 涨跌幅={market_data.change_pct:.2f}%")
                    return market_data
                
                # 方法2: 如果网页抓取失败，尝试备用API
                logger.warning(f"网页抓取失败，尝试备用API...")
                market_data = self._get_from_backup_api(symbol, code)
                
                if market_data:
                    return market_data
                
                logger.error(f"所有方法都失败")
                return None
                
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"获取数据失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                    import time
                    time.sleep(retry_delay)
                else:
                    logger.error(f"获取 {symbol} 数据失败（已重试{max_retries}次）: {e}")
                    return None
        
        return None
    
    def _scrape_from_quote_page(self, symbol: str, code: str) -> Optional[MarketData]:
        """从东方财富网个股行情页面抓取数据"""
        try:
            # 方法1: 先尝试腾讯财经API（更稳定）
            market_data = self._get_from_tencent_api(symbol, code)
            if market_data:
                return market_data
            
            # 方法2: 尝试东方财富网个股页面
            url = f"https://quote.eastmoney.com/sh{code}.html"
            
            logger.debug(f"正在抓取: {url}")
            
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            html_content = response.text
            
            # 方法3: 从JSON数据中提取
            market_data = self._parse_json_from_html(html_content, symbol)
            if market_data:
                return market_data
            
            # 方法4: 从HTML标签中提取
            market_data = self._parse_html_tags(html_content, symbol)
            if market_data:
                return market_data
            
            return None
            
        except Exception as e:
            logger.debug(f"网页抓取失败: {e}")
            return None
    
    def _get_from_tencent_api(self, symbol: str, code: str) -> Optional[MarketData]:
        """从腾讯财经API获取数据（更稳定）"""
        try:
            # 腾讯财经实时行情API
            url = f"http://qt.gtimg.cn/q=sh{code}"
            
            response = requests.get(url, headers=self.headers, timeout=5)
            response.raise_for_status()
            response.encoding = 'gbk'
            
            content = response.text
            
            # 腾讯财经数据格式: v_sh513120="1~港股创新药ETF~513120~1.271~1.282~1.270~..."
            if '~' in content and '=' in content:
                # 提取引号内的内容
                match = re.search(r'="([^"]+)"', content)
                if not match:
                    return None
                
                data_str = match.group(1)
                parts = data_str.split('~')
                
                if len(parts) < 10:
                    return None
                
                # 解析字段
                name = parts[1]  # 股票名称
                current_price = float(parts[3])  # 当前价格
                prev_close = float(parts[4])  # 昨收
                open_price = float(parts[5])  # 今开
                volume = int(float(parts[6])) * 100  # 成交量（手转股）
                high_price = float(parts[33]) if len(parts) > 33 and parts[33] else current_price  # 最高
                low_price = float(parts[34]) if len(parts) > 34 and parts[34] else current_price  # 最低
                amount = float(parts[37]) if len(parts) > 37 and parts[37] else 0  # 成交额
                
                # 计算涨跌幅
                change_pct = ((current_price - prev_close) / prev_close * 100) if prev_close > 0 else 0
                
                # 获取历史数据计算技术指标
                klines = self._get_historical_klines_from_tencent(symbol, code, days=120)
                indicators = self._calculate_indicators(klines)
                
                return MarketData(
                    symbol=symbol,
                    name=name,
                    current_price=current_price,
                    open_price=open_price if open_price > 0 else current_price,
                    high_price=high_price if high_price > 0 else current_price,
                    low_price=low_price if low_price > 0 else current_price,
                    volume=volume,
                    amount=amount,
                    change_pct=change_pct,
                    timestamp=datetime.now(),
                    ema_20=indicators.get('ema_20'),
                    ema_60=indicators.get('ema_60'),
                    ma_5=indicators.get('ma_5'),
                    volume_ma5=indicators.get('volume_ma5'),
                    rsi=indicators.get('rsi'),
                    capital_flow=0.0,
                    boll_up=indicators.get('boll_up'),
                    boll_middle=indicators.get('boll_middle'),
                    boll_down=indicators.get('boll_down')
                )
            
            return None
            
        except Exception as e:
            logger.debug(f"腾讯财经API失败: {e}")
            return None
    
    def _get_historical_klines_from_tencent(self, symbol: str, code: str, days: int = 120) -> pd.DataFrame:
        """从腾讯财经获取历史K线"""
        try:
            # 腾讯财经日K线API
            url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
            params = {
                "param": f"sh{code},day,,,{days},qfq"
            }
            
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            
            # 解析腾讯财经返回的数据结构
            if result.get('code') == 0 and result.get('data'):
                stock_data = result['data'].get(f'sh{code}', {})
                klines = stock_data.get('qfqday', []) or stock_data.get('day', [])
                
                if klines:
                    records = []
                    for line in klines:
                        if len(line) >= 6:  # 至少需要6个字段：日期、开盘、收盘、最高、最低、成交量
                            records.append({
                                '日期': line[0],
                                '开盘': float(line[1]),
                                '收盘': float(line[2]),
                                '最高': float(line[3]),
                                '最低': float(line[4]),
                                '成交量': float(line[5]) * 100,  # 手转股
                                '成交额': float(line[6]) if len(line) > 6 else 0  # 成交额可能不存在
                            })
                    
                    df = pd.DataFrame(records)
                    if not df.empty:
                        df['日期'] = pd.to_datetime(df['日期'])
                        df = df.sort_values('日期').reset_index(drop=True)
                        logger.info(f"成功从腾讯财经获取 {symbol} 历史K线：{len(df)}条")
                        return df
            
            return pd.DataFrame()
            
        except Exception as e:
            logger.debug(f"腾讯财经历史K线失败: {e}")
            return pd.DataFrame()

    def _parse_json_from_html(self, html_content: str, symbol: str) -> Optional[MarketData]:
        """从HTML中的JSON数据解析"""
        try:
            # 查找包含行情数据的script标签
            # 东方财富通常在window.quote或类似变量中存储数据
            
            # 尝试匹配各种可能的JSON数据模式
            patterns = [
                r'window\.quotemsg\s*=\s*({.*?});',
                r'var\s+quotemsg\s*=\s*({.*?});',
                r'"hq"\s*:\s*({.*?})',
                r'data\s*:\s*({.*?"f43".*?})',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, html_content, re.DOTALL)
                if match:
                    try:
                        json_str = match.group(1)
                        # 清理JSON字符串
                        json_str = json_str.replace("'", '"')
                        data = json.loads(json_str)
                        
                        # 解析数据
                        market_data = self._extract_from_json(data, symbol)
                        if market_data:
                            return market_data
                    except:
                        continue
            
            return None
            
        except Exception as e:
            logger.debug(f"JSON解析失败: {e}")
            return None
    
    def _extract_from_json(self, data: dict, symbol: str) -> Optional[MarketData]:
        """从JSON数据中提取行情信息"""
        try:
            # 尝试不同的数据结构
            if isinstance(data, dict):
                # 直接包含字段
                if 'f43' in data:
                    return self._build_market_data(data, symbol)
                
                # 嵌套结构
                for key in ['data', 'hq', 'quote', 'result']:
                    if key in data and isinstance(data[key], dict):
                        if 'f43' in data[key]:
                            return self._build_market_data(data[key], symbol)
            
            return None
            
        except Exception as e:
            logger.debug(f"JSON数据提取失败: {e}")
            return None
    
    def _build_market_data(self, data: dict, symbol: str) -> Optional[MarketData]:
        """构建MarketData对象"""
        try:
            # 东方财富字段映射
            current_price = float(data.get('f43', 0)) / 100 if data.get('f43') else 0
            open_price = float(data.get('f46', 0)) / 100 if data.get('f46') else current_price
            high_price = float(data.get('f44', 0)) / 100 if data.get('f44') else current_price
            low_price = float(data.get('f45', 0)) / 100 if data.get('f45') else current_price
            volume = int(data.get('f47', 0)) if data.get('f47') else 0
            amount = float(data.get('f48', 0)) if data.get('f48') else 0
            change_pct = float(data.get('f170', 0)) / 100 if data.get('f170') else 0
            name = data.get('f58', symbol)
            
            if current_price == 0:
                return None
            
            # 获取历史数据计算技术指标
            klines = self._get_historical_klines(symbol, days=120)
            indicators = self._calculate_indicators(klines)
            
            return MarketData(
                symbol=symbol,
                name=name,
                current_price=current_price,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
                volume=volume,
                amount=amount,
                change_pct=change_pct,
                timestamp=datetime.now(),
                ema_20=indicators.get('ema_20'),
                ema_60=indicators.get('ema_60'),
                ma_5=indicators.get('ma_5'),
                volume_ma5=indicators.get('volume_ma5'),
                rsi=indicators.get('rsi'),
                capital_flow=0.0
            )
            
        except Exception as e:
            logger.debug(f"构建MarketData失败: {e}")
            return None
    
    def _parse_html_tags(self, html_content: str, symbol: str) -> Optional[MarketData]:
        """从HTML标签中解析数据"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 尝试从常见的CSS类名中提取数据
            price_elements = soup.find_all(class_=re.compile(r'price|current|last', re.I))
            change_elements = soup.find_all(class_=re.compile(r'change|pct|zdf', re.I))
            
            if not price_elements:
                return None
            
            # 提取价格
            current_price = None
            for elem in price_elements:
                try:
                    text = elem.get_text().strip()
                    # 匹配数字格式
                    match = re.search(r'[\d.]+', text)
                    if match:
                        price = float(match.group())
                        if 0 < price < 1000:  # 合理的价格范围
                            current_price = price
                            break
                except:
                    continue
            
            if not current_price:
                return None
            
            # 提取涨跌幅
            change_pct = 0
            for elem in change_elements:
                try:
                    text = elem.get_text().strip()
                    match = re.search(r'([+-]?[\d.]+)%?', text)
                    if match:
                        change_pct = float(match.group(1))
                        break
                except:
                    continue
            
            # 获取历史数据
            klines = self._get_historical_klines(symbol, days=120)
            indicators = self._calculate_indicators(klines)
            
            return MarketData(
                symbol=symbol,
                name=symbol,
                current_price=current_price,
                open_price=current_price,
                high_price=current_price,
                low_price=current_price,
                volume=0,
                amount=0,
                change_pct=change_pct,
                timestamp=datetime.now(),
                ema_20=indicators.get('ema_20'),
                ema_60=indicators.get('ema_60'),
                ma_5=indicators.get('ma_5'),
                volume_ma5=indicators.get('volume_ma5'),
                rsi=indicators.get('rsi'),
                capital_flow=0.0,
                boll_up=indicators.get('boll_up'),
                boll_middle=indicators.get('boll_middle'),
                boll_down=indicators.get('boll_down')
            )
            
        except Exception as e:
            logger.debug(f"HTML标签解析失败: {e}")
            return None
    
    def get_sh_index(self) -> Optional[float]:
        """获取上证指数"""
        try:
            # 使用腾讯财经API获取上证指数（代码：sh000001）
            url = "http://qt.gtimg.cn/q=sh000001"
            
            response = requests.get(url, headers=self.headers, timeout=5)
            response.raise_for_status()
            response.encoding = 'gbk'
            
            content = response.text
            
            # 腾讯财经数据格式: v_sh000001="1~上证指数~000001~3240.12~3230.45~..."
            if '~' in content and '=' in content:
                # 提取引号内的内容
                match = re.search(r'="([^"]+)"', content)
                if not match:
                    logger.debug("无法解析上证指数数据")
                    return None
                
                data_str = match.group(1)
                parts = data_str.split('~')
                
                if len(parts) >= 4:
                    # parts[3] 是当前指数点位
                    index_value = float(parts[3])
                    logger.debug(f"成功获取上证指数: {index_value:.2f}")
                    return index_value
            
            logger.debug("上证指数数据格式异常")
            return None
            
        except Exception as e:
            logger.debug(f"获取上证指数失败: {e}")
            return None
    
    def _get_historical_klines(self, symbol: str, days: int = 120) -> pd.DataFrame:
        """获取历史K线数据（通用方法）"""
        if symbol not in self.etf_codes:
            logger.warning(f"不支持的ETF代码：{symbol}")
            return pd.DataFrame()
        
        code = self.etf_codes[symbol]
        return self._get_historical_klines_from_tencent(symbol, code, days)
    
    def _calculate_indicators(self, klines: pd.DataFrame) -> dict:
        """计算技术指标"""
        indicators = {
            'ema_20': None,
            'ema_60': None,
            'ma_5': None,
            'volume_ma5': None,
            'rsi': None,
            'boll_up': None,
            'boll_middle': None,
            'boll_down': None
        }
        
        if klines is None or klines.empty:
            return indicators
        
        try:
            # 确保有收盘价数据
            if '收盘' not in klines.columns:
                return indicators
            
            close_prices = klines['收盘']
            
            # 计算EMA指标
            if len(close_prices) >= 20:
                indicators['ema_20'] = close_prices.ewm(span=20, adjust=False).mean().iloc[-1]
            
            if len(close_prices) >= 60:
                indicators['ema_60'] = close_prices.ewm(span=60, adjust=False).mean().iloc[-1]
            
            # 计算MA5
            if len(close_prices) >= 5:
                indicators['ma_5'] = close_prices.rolling(window=5).mean().iloc[-1]
            
            # 计算成交量MA5
            if '成交量' in klines.columns and len(klines) >= 5:
                indicators['volume_ma5'] = klines['成交量'].rolling(window=5).mean().iloc[-1]
            
            # 计算RSI (14日)
            if len(close_prices) >= 15:
                delta = close_prices.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                indicators['rsi'] = rsi.iloc[-1]
            
            # 计算BOLL布林带 (20日，2倍标准差)
            if len(close_prices) >= 20:
                middle = close_prices.rolling(window=20).mean()
                std = close_prices.rolling(window=20).std()
                indicators['boll_middle'] = middle.iloc[-1]
                indicators['boll_up'] = (middle + 2 * std).iloc[-1]
                indicators['boll_down'] = (middle - 2 * std).iloc[-1]
            
        except Exception as e:
            logger.debug(f"计算技术指标失败: {e}")
        
        return indicators
    
    def _get_from_backup_api(self, symbol: str, code: str) -> Optional[MarketData]:
        """从备用API获取数据"""
        try:
            # 备用API URL
            url = f"http://api.example.com/quote/{code}"
            
            response = requests.get(url, headers=self.headers, timeout=5)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            data = response.json()
            
            # 解析备用API返回的数据结构
            if data.get('success'):
                name = data.get('name', symbol)
                current_price = data.get('current_price', 0)
                open_price = data.get('open_price', current_price)
                high_price = data.get('high_price', current_price)
                low_price = data.get('low_price', current_price)
                volume = data.get('volume', 0)
                amount = data.get('amount', 0)
                change_pct = data.get('change_pct', 0)
                
                if current_price == 0:
                    return None
                
                # 获取历史数据计算技术指标
                klines = self._get_historical_klines(symbol, days=120)
                indicators = self._calculate_indicators(klines)
                
                return MarketData(
                    symbol=symbol,
                    name=name,
                    current_price=current_price,
                    open_price=open_price,
                    high_price=high_price,
                    low_price=low_price,
                    volume=volume,
                    amount=amount,
                    change_pct=change_pct,
                    timestamp=datetime.now(),
                    ema_20=indicators.get('ema_20'),
                    ema_60=indicators.get('ema_60'),
                    ma_5=indicators.get('ma_5'),
                    volume_ma5=indicators.get('volume_ma5'),
                    rsi=indicators.get('rsi'),
                    capital_flow=0.0,
                    boll_up=indicators.get('boll_up'),
                    boll_middle=indicators.get('boll_middle'),
                    boll_down=indicators.get('boll_down')
                )
            
            return None
            
        except Exception as e:
            logger.debug(f"备用API失败: {e}")
            return None


# 全局单例
_data_provider = None


def get_market_data_provider() -> EastMoneyWebScraper:
    """获取市场数据提供者单例"""
    global _data_provider
    if _data_provider is None:
        _data_provider = EastMoneyWebScraper()
    return _data_provider


def get_market_data(symbol: str) -> Optional[MarketData]:
    """获取市场数据（便捷函数）"""
    provider = get_market_data_provider()
    return provider.get_realtime_data(symbol)


def get_sh_index() -> Optional[float]:
    """获取上证指数（便捷函数）"""
    provider = get_market_data_provider()
    return provider.get_sh_index()


def get_capital_flow(symbol: str) -> Optional[float]:
    """获取资金流向（便捷函数）"""
    # 暂时返回None，后续可以实现
    return None
