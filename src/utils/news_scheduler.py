# -*- coding: utf-8 -*-
"""股票资讯监控调度器 - 定时获取股票资讯并推送"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import sys
from pathlib import Path
import pandas as pd
from loguru import logger
import requests
import re
import json
import akshare as ak

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.config import get_config
from src.utils.news_crawler import get_eastmoney_crawler
from src.utils.notification import send_news_notification, get_feishu_notifier


class NewsMonitorScheduler:
    """股票资讯监控调度器"""
    
    def __init__(self):
        """初始化调度器"""
        self.scheduler = BackgroundScheduler()
        self.config = get_config()
        self.monitor_config = self.config.stock_news_monitor
        self.crawler = get_eastmoney_crawler()
        
        # ✨ 新增：交易日历缓存
        self.trading_days_cache = None
        
        if not self.monitor_config.enabled:
            logger.info("ℹ️ 股票资讯监控未启用")
            return
        
        # ✨ 新增：加载交易日历
        self._load_trading_calendar()
        
        # 获取股票池
        self.stock_pool = [
            {'code': stock.code, 'name': stock.name, 'index': stock.index}
            for stock in self.monitor_config.stock_pool
        ]
        
        if not self.stock_pool:
            logger.warning("⚠️ 股票池为空，无法启动资讯监控")
            return
        
        logger.info(f"✅ 股票资讯监控调度器已初始化")
        logger.info(f"   监控股票数量: {len(self.stock_pool)}")
        for stock in self.stock_pool:
            logger.info(f"   - {stock['name']} ({stock['code']})")
        
        # 配置定时任务
        schedule = self.monitor_config.schedule
        cron_trigger = CronTrigger(
            hour=schedule.hour,
            minute=schedule.minute,
            second=schedule.second,
            timezone='Asia/Shanghai'
        )
        
        logger.info(f"   定时任务: 每天 {schedule.hour:02d}:{schedule.minute:02d}:{schedule.second:02d} 执行")
        
        # 添加定时任务
        self.scheduler.add_job(
            func=self._fetch_and_send_news,
            trigger=cron_trigger,
            id='news_monitor_job',
            name='股票资讯监控任务',
            replace_existing=True
        )
    
    def _load_trading_calendar(self):
        """
        加载交易日历（带缓存）
        
        使用 akshare 获取A股交易日历，支持周末和法定节假日过滤
        失败时降级为仅过滤周末的方案
        """
        try:
            import akshare as ak
            
            logger.info("[INFO] 正在从 akshare 获取A股交易日历...")
            
            # 获取中国A股交易日历
            trade_dates_df = ak.tool_trade_date_hist_sina()
            
            if trade_dates_df is None or trade_dates_df.empty:
                logger.warning("[WARN] 无法从 akshare 获取交易日历，降级为仅过滤周末")
                self.trading_days_cache = None
                return
            
            # 转换为 datetime 对象并缓存
            self.trading_days_cache = pd.to_datetime(trade_dates_df['trade_date']).tolist()
            logger.info(f"[OK] 成功加载 {len(self.trading_days_cache)} 个交易日至缓存")
            
        except Exception as e:
            logger.warning(f"[WARN] 获取交易日历失败: {e}，降级为仅过滤周末")
            self.trading_days_cache = None
    
    def _is_trading_day(self, check_date=None):
        """
        判断指定日期是否为交易日
        
        Args:
            check_date: 要检查的日期，默认为当前日期
            
        Returns:
            bool: True表示交易日，False表示非交易日
        """
        if check_date is None:
            check_date = datetime.now()
        
        # 如果有缓存的交易日历
        if self.trading_days_cache:
            # 只比较日期部分（去除时分秒）
            check_date_only = check_date.replace(hour=0, minute=0, second=0, microsecond=0)
            is_trading = check_date_only in self.trading_days_cache
            return is_trading
        
        # 降级方案：仅过滤周末
        weekday = check_date.weekday()
        if weekday < 5:  # 周一到周五
            return True
        else:
            return False
    
    def _fetch_stock_metrics(self, symbol: str, name: str) -> dict:
        """
        获取股票行情指标（涨跌幅、市值等）- 使用腾讯财经API
        
        Args:
            symbol: 股票代码 (如 sz.002706)
            name: 股票名称
            
        Returns:
            包含涨跌幅、市值和收盘价的字典
        """
        metrics = {
            'daily_change_pct': None,  # 最近一日涨跌幅
            'weekly_change_pct': None,  # 最近一周涨跌幅
            'monthly_change_pct': None,  # 最近一月涨跌幅
            'circulating_market_cap': None,  # 流通市值（亿元）
            'close_price': None  # 最新收盘价
        }
        
        try:
            # 提取市场前缀和代码
            parts = symbol.split('.')
            if len(parts) != 2:
                logger.warning(f"   ⚠️ 股票代码格式错误: {symbol}")
                return metrics
            
            market = parts[0].upper()  # SZ 或 SH
            code = parts[1]            # 002706
            
            # 设置请求头
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
            
            # 1. 从腾讯财经获取实时行情（日涨跌幅）
            tencent_url = f"http://qt.gtimg.cn/q={market.lower()}{code}"
            logger.debug(f"   📊 正在从腾讯财经获取 {name}({code}) 的实时行情...")
            
            response = requests.get(tencent_url, headers=headers, timeout=5)
            response.raise_for_status()
            response.encoding = 'gbk'
            
            content = response.text
            
            # 腾讯财经数据格式: v_sz002706="1~良信股份~002706~10.50~10.30~10.45~..."
            if '~' in content and '=' in content:
                match = re.search(r'="([^"]+)"', content)
                if match:
                    data_str = match.group(1)
                    parts_data = data_str.split('~')
                    
                    if len(parts_data) >= 80:
                        # 提取当前价格（parts[3]是最新价）
                        current_price = float(parts_data[3]) if parts_data[3] else 0
                        metrics['close_price'] = round(current_price, 2)
                        
                        # 提取日涨跌幅（parts[32]是涨跌幅百分比）
                        change_pct = float(parts_data[32]) if parts_data[32] else 0
                        metrics['daily_change_pct'] = round(change_pct, 2)
                        
                        # 提取流通市值
                        # 字段[72]或[76]是流通股本（股数），需要乘以当前价格得到市值
                        circulating_shares = 0
                        
                        for idx in [72, 76]:
                            if len(parts_data) > idx and parts_data[idx]:
                                try:
                                    shares = float(parts_data[idx])
                                    if shares > 0:
                                        circulating_shares = shares
                                        break
                                except:
                                    continue
                        
                        if circulating_shares > 0 and current_price > 0:
                            market_cap_yuan = circulating_shares * current_price
                            metrics['circulating_market_cap'] = round(market_cap_yuan / 1e8, 2)  # 转换为亿元
                        
                        logger.debug(f"   ✅ 腾讯实时行情: 现价{metrics['close_price']:.2f} | 日{metrics['daily_change_pct']:+.2f}% | 市值{metrics['circulating_market_cap']}亿")
            
            # 2. 从腾讯财经获取历史K线数据计算周/月涨跌幅
            klines = self._get_historical_klines_from_tencent(market.lower(), code, days=120)
            
            if not klines.empty and len(klines) >= 21:
                latest_close = klines['收盘'].iloc[-1]
                
                # 如果实时行情未获取到收盘价，使用K线数据的收盘价
                if metrics['close_price'] is None or metrics['close_price'] == 0:
                    metrics['close_price'] = round(latest_close, 2)
                
                # 计算周涨幅（5个交易日前，索引-6）
                if len(klines) >= 6:
                    price_1w_ago = klines['收盘'].iloc[-6]
                    weekly_change = ((latest_close - price_1w_ago) / price_1w_ago) * 100
                    metrics['weekly_change_pct'] = round(weekly_change, 2)
                
                # 计算月涨幅（20个交易日前，索引-21）
                if len(klines) >= 21:
                    price_1m_ago = klines['收盘'].iloc[-21]
                    monthly_change = ((latest_close - price_1m_ago) / price_1m_ago) * 100
                    metrics['monthly_change_pct'] = round(monthly_change, 2)
                
                logger.debug(f"   ✅ 腾讯K线: 周{metrics['weekly_change_pct']:+.2f}% | 月{metrics['monthly_change_pct']:+.2f}%")
            else:
                logger.warning(f"   ⚠️ 腾讯K线数据不足: {len(klines)}条")
            
            # 构建日志信息
            daily_str = f"{metrics['daily_change_pct']:+.2f}%" if metrics['daily_change_pct'] is not None else "N/A"
            weekly_str = f"{metrics['weekly_change_pct']:+.2f}%" if metrics['weekly_change_pct'] is not None else "N/A"
            monthly_str = f"{metrics['monthly_change_pct']:+.2f}%" if metrics['monthly_change_pct'] is not None else "N/A"
            cap_str = f"{metrics['circulating_market_cap']}亿" if metrics['circulating_market_cap'] is not None else "N/A"
            close_str = f"{metrics['close_price']:.2f}" if metrics['close_price'] is not None else "N/A"
            
            logger.info(f"   ✅ 行情指标: 现价{close_str} | 日{daily_str} | 周{weekly_str} | 月{monthly_str} | 市值{cap_str}")
            
        except Exception as e:
            logger.warning(f"   ⚠️ 获取 {name} 行情指标失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())
        
        return metrics
    
    def _get_historical_klines_from_tencent(self, market: str, code: str, days: int = 120) -> pd.DataFrame:
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
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
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
                            # 如果是字典，跳过（异常情况）
                            logger.debug(f"警告: 遇到字典格式的K线数据，跳过: {line}")
                            continue
                        
                        if isinstance(line, (list, tuple)) and len(line) >= 6:
                            try:
                                records.append({
                                    '日期': line[0],
                                    '开盘': float(line[1]),
                                    '收盘': float(line[2]),
                                    '最高': float(line[3]),
                                    '最低': float(line[4]),
                                    '成交量': float(line[5]) * 100,  # 手转股
                                    '成交额': float(line[6]) if len(line) > 6 else 0  # 成交额可能不存在
                                })
                            except (ValueError, TypeError) as e:
                                logger.debug(f"警告: 解析K线数据失败，跳过: {e}, 数据: {line}")
                                continue
                    
                    df = pd.DataFrame(records)
                    if not df.empty:
                        df['日期'] = pd.to_datetime(df['日期'])
                        df = df.sort_values('日期').reset_index(drop=True)
                        logger.debug(f"成功从腾讯财经获取 {market}{code} 历史K线：{len(df)}条")
                        return df
            
            return pd.DataFrame()
            
        except Exception as e:
            logger.debug(f"腾讯财经历史K线失败: {e}")
            return pd.DataFrame()
    
    def _fetch_and_send_news(self, target_date: str = None):
        """获取资讯并发送通知
        
        Args:
            target_date: 目标日期（格式：YYYY-MM-DD），用于测试。默认为None表示使用当天日期
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # ✨ 新增：检查是否为交易日
        if not self._is_trading_day():
            today_str = datetime.now().strftime('%Y-%m-%d')
            weekday_map = {0: '周一', 1: '周二', 2: '周三', 3: '周四', 
                          4: '周五', 5: '周六', 6: '周日'}
            weekday_str = weekday_map[datetime.now().weekday()]
            logger.info(f"\n{'='*60}")
            logger.info(f"⏭️ [{today_str}] {weekday_str} 非交易日，跳过资讯推送")
            logger.info(f"{'='*60}\n")
            return
        
        # 如果指定了目标日期，在日志中显示
        date_info = f" (测试日期: {target_date})" if target_date else ""
        
        logger.info(f"\n{'='*60}")
        logger.info(f"🔄 【股票资讯监控】开始执行{date_info}...")
        logger.info(f"{'='*60}")
        logger.info(f"执行时间: {current_time}")
        logger.info(f"现在开始获取个股资讯和公告")
        
        try:
            # 导入趋势分析器（从项目根目录导入）
            import sys
            from pathlib import Path
            # 确保项目根目录在sys.path中
            project_root = Path(__file__).parent.parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            
            from tool_bullbear_a import TrendAnalyzer
            trend_analyzer = TrendAnalyzer()
            
            # 检查资讯来源是否启用
            news_sources = self.monitor_config.news_sources
            
            # 获取所有股票的资讯
            all_news = []
            
            for stock in self.stock_pool:
                symbol = stock['code']
                name = stock['name']
                index = stock.get('index', '')  # 获取中文序号
                
                # 控制台输出时也显示序号
                if index:
                    logger.info(f"\n📊 处理股票: {index}、{name} ({symbol})")
                else:
                    logger.info(f"\n📊 处理股票: {name} ({symbol})")
                
                # 获取股票行情数据（涨跌幅、市值等）
                stock_metrics = self._fetch_stock_metrics(symbol, name)
                
                # 获取趋势分析结果（使用新版100分评分系统）
                logger.info(f"   📈 正在进行多空信号分析...")
                
                # 解析股票代码
                parts = symbol.split('.')
                trend_analysis = None
                
                if len(parts) == 2:
                    market = parts[0].lower()  # 'sh' 或 'sz'
                    code = parts[1]            # '000792'
                    
                    try:
                        # 调用新版评分函数（支持历史日期）
                        from local.utils import calculate_trend_score_v2
                        score = calculate_trend_score_v2(market, code, days=300, end_date=target_date)
                        
                        if score is not None:
                            # 根据百分制评分确定趋势类型和描述
                            if score >= 80:
                                trend_type = 'BULLISH'
                                conclusion = "🟢 强势多头"
                            elif score >= 60:
                                trend_type = 'SLIGHTLY_BULLISH'
                                conclusion = "🟡 温和上涨"
                            elif score >= 40:
                                trend_type = 'NEUTRAL'
                                conclusion = "⚪ 震荡整理"
                            elif score >= 20:
                                trend_type = 'SLIGHTLY_BEARISH'
                                conclusion = "🟠 弱势下跌"
                            else:
                                trend_type = 'BEARISH'
                                conclusion = "🔴 极弱空头"
                            
                            # 获取收盘价
                            close_price = stock_metrics.get('close_price', 0)
                            
                            # 构建趋势分析结果（保持与原格式兼容）
                            trend_analysis = {
                                'symbol': symbol,
                                'name': name,
                                'date': datetime.now().strftime('%Y-%m-%d'),
                                'close': close_price,
                                'trend': trend_type,
                                'score': score,
                                'conclusion': conclusion,
                                'previous_score': None  # 暂时不实现前一日对比
                            }
                            
                            logger.info(f"   ✅ 评分完成: {score:.1f}分 | {conclusion}")
                        else:
                            logger.warning(f"   ⚠️ 评分计算失败，跳过该股票的趋势分析")
                            trend_analysis = None
                    except Exception as e:
                        logger.warning(f"   ⚠️ 评分计算异常: {e}")
                        trend_analysis = None
                else:
                    logger.warning(f"   ⚠️ 股票代码格式错误，跳过趋势分析")
                
                stock_news = {
                    'code': symbol,
                    'name': name,
                    'index': index,  # 添加中文序号
                    'individual_news': [],
                    'financial_reports': [],
                    'metrics': stock_metrics,  # 添加行情指标
                    'trend_analysis': trend_analysis  # 添加趋势分析结果
                }
                
                # 获取个股资讯（最新3条）
                if news_sources.individual_news.enabled:
                    logger.info(f"   📰 获取个股资讯...")
                    individual_news = self.crawler.fetch_individual_news(symbol, name)
                    # 只保留最新3条
                    stock_news['individual_news'] = individual_news[:3]
                    logger.info(f"   ✅ 获取到 {len(stock_news['individual_news'])} 条个股资讯")
                
                # 获取公告（最新1条）
                if news_sources.financial_reports.enabled:
                    logger.info(f"   📑 获取公告...")
                    financial_reports = self.crawler.fetch_financial_reports(symbol, name)
                    # 只保留最新1条
                    stock_news['financial_reports'] = financial_reports[:1]
                    logger.info(f"   ✅ 获取到 {len(stock_news['financial_reports'])} 条公告")

                all_news.append(stock_news)
                
                # 避免请求过快
                import time
                time.sleep(1)
            
            # 统计总数
            total_count = sum(
                len(news['individual_news']) + len(news['financial_reports'])
                for news in all_news
            )
            
            logger.info(f"\n✅ 资讯获取完成，共 {total_count} 条")
            
            # 发送大盘环境信号通知
            self._send_market_signal_notification()
            
            # 发送选股结果通知
            self._send_stockpool_notification()
            
            # 再发送资讯日报通知
            if total_count > 0:
                news_data = {
                    'stock_pool': all_news,
                    'fetch_time': current_time,
                    'total_count': total_count
                }
                
                success = send_news_notification(news_data)
                if success:
                    logger.success(f"📱 飞书通知发送成功")
                else:
                    logger.error(f"❌ 飞书通知发送失败")
            else:
                logger.info(f"ℹ️ 今日暂无新资讯，跳过通知")
            
            logger.info(f"✅ 本轮资讯监控完成\n")
            
        except Exception as e:
            logger.error(f"❌ 资讯监控执行异常: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _get_latest_trading_date(self) -> str:
        """
        获取最近的交易日（使用akshare获取交易日历）
        
        Returns:
            str: 交易日期字符串 (格式: YYYYMMDD)，失败则返回当日日期
        """
        try:
            # 获取A股交易日历
            trade_cal = ak.tool_trade_date_hist_sina()
            
            if trade_cal is not None and not trade_cal.empty:
                # 转换为datetime列表
                trade_dates = pd.to_datetime(trade_cal['trade_date']).tolist()
                
                # 获取当前日期
                today = pd.Timestamp(datetime.now().date())
                
                # 找到最近的一个交易日（小于等于今天）
                trading_dates = [d for d in trade_dates if d <= today]
                
                if trading_dates:
                    latest_date = max(trading_dates)
                    date_str = latest_date.strftime('%Y%m%d')
                    logger.info(f"✅ 最近交易日: {latest_date.strftime('%Y-%m-%d')}")
                    return date_str
            
            # 降级方案：如果akshare失败，手动判断
            logger.warning("⚠️ 无法获取交易日历，使用降级方案")
            today = datetime.now()
            
            # 如果是周末，追溯到周五
            if today.weekday() == 5:  # 周六
                today -= timedelta(days=1)
            elif today.weekday() == 6:  # 周日
                today -= timedelta(days=2)
            
            return today.strftime('%Y%m%d')
            
        except Exception as e:
            logger.warning(f"⚠️ 获取交易日历失败: {e}，使用降级方案")
            # 降级方案
            today = datetime.now()
            if today.weekday() == 5:  # 周六
                today -= timedelta(days=1)
            elif today.weekday() == 6:  # 周日
                today -= timedelta(days=2)
            return today.strftime('%Y%m%d')
    
    def _get_stock_fundamentals(self, symbol: str):
        """
        获取股票基本面指标（PE-TTM、换手率、最高价、收盘价等）- 使用腾讯财经API
        
        Args:
            symbol: 股票代码 (如 sz.002706 或 sh.600519)
            
        Returns:
            dict: 包含 pe_ttm、turnover_rate、high_price、close_price 的字典，获取失败返回None
        """
        try:
            # 解析股票代码
            parts = symbol.split('.')
            if len(parts) != 2:
                return {'pe_ttm': None, 'turnover_rate': None, 'high_price': None, 'close_price': None}
            
            market = parts[0].upper()  # SZ 或 SH
            code = parts[1]
            
            # 调用腾讯财经API
            url = f"http://qt.gtimg.cn/q={market.lower()}{code}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            response.encoding = 'gbk'
            
            content = response.text
            
            # 解析数据
            if '~' in content and '=' in content:
                match = re.search(r'="([^"]+)"', content)
                if match:
                    data_str = match.group(1)
                    parts_data = data_str.split('~')
                    
                    result = {
                        'pe_ttm': None, 
                        'turnover_rate': None,
                        'high_price': None,
                        'close_price': None
                    }
                    
                    if len(parts_data) >= 40:
                        # parts[39] 是 PE-TTM（滚动市盈率）
                        pe_ttm_str = parts_data[39]
                        if pe_ttm_str and pe_ttm_str.strip():
                            try:
                                pe_ttm = float(pe_ttm_str)
                                if pe_ttm > 0:
                                    result['pe_ttm'] = round(pe_ttm, 2)
                            except ValueError:
                                pass
                        
                        # parts[38] 是换手率（%）
                        turnover_str = parts_data[38]
                        if turnover_str and turnover_str.strip():
                            try:
                                turnover_rate = float(turnover_str)
                                if turnover_rate >= 0:
                                    result['turnover_rate'] = round(turnover_rate, 2)
                            except ValueError:
                                pass
                        
                        # parts[33] 是最高价
                        if len(parts_data) > 33 and parts_data[33]:
                            try:
                                high_price = float(parts_data[33])
                                if high_price > 0:
                                    result['high_price'] = round(high_price, 2)
                            except ValueError:
                                pass
                        
                        # parts[3] 是当前价格（即收盘价）
                        if len(parts_data) > 3 and parts_data[3]:
                            try:
                                close_price = float(parts_data[3])
                                if close_price > 0:
                                    result['close_price'] = round(close_price, 2)
                            except ValueError:
                                pass
                    
                    return result
            
            return {'pe_ttm': None, 'turnover_rate': None, 'high_price': None, 'close_price': None}
            
        except Exception as e:
            logger.debug(f"获取 {symbol} 基本面指标失败: {e}")
            return {'pe_ttm': None, 'turnover_rate': None, 'high_price': None, 'close_price': None}

    # ==================== 大盘环境信号推送 ====================

    def _read_market_signal(self) -> dict:
        """
        读取当日大盘环境信号

        从 data/signal_history.json 中获取最新一条记录（按日期），
        若当日无记录则返回空字典。

        Returns:
            dict: 包含 passed / indices / reasons / market_volume 等字段，或无数据时返回 {}
        """
        signal_file = project_root / "data" / "signal_history.json"
        if not signal_file.exists():
            logger.info("ℹ️  signal_history.json 不存在，跳过信号推送")
            return {}

        try:
            with open(signal_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return {}
                history = json.loads(content)

            if not isinstance(history, list) or not history:
                return {}

            # 取最新一条（按日期排序，取最后一条）
            latest = max(history, key=lambda x: x.get('date', ''))
            return latest

        except Exception as e:
            logger.warning(f"⚠️ 读取 signal_history.json 失败: {e}")
            return {}

    def _send_market_signal_notification(self):
        """
        发送大盘环境信号飞书通知

        读取 signal_history.json 获取当日信号结果，
        格式化为飞书卡片推送，包含各指数状态和成交额。
        """
        try:
            signal = self._read_market_signal()
            if not signal:
                return

            signal_date = signal.get('date', '未知')
            passed = signal.get('passed', False)
            mode = signal.get('pass_mode', 'dual_consensus')
            market_volume = signal.get('market_volume')
            volume_pass = signal.get('volume_pass', True)
            reasons = signal.get('reasons', [])

            logger.info(f"\n{'=' * 60}")
            logger.info(f"📡 【大盘环境信号】已获取 - {signal_date}")
            logger.info(f"{'=' * 60}")

            # 构建信号内容
            result_icon = "✅ 允许买入" if passed else "❌ 禁止买入"

            content = f"**日期**: {signal_date}\n"
            content += f"**结果**: {result_icon}\n"
            content += f"**模式**: {mode}\n"

            # 沪深市场成交额
            if market_volume is not None:
                vol_icon = "✅" if volume_pass else "❌"
                vol_trend = signal.get('volume_trend', '')
                vol_avg = signal.get('volume_avg_5')
                vol_detail = f"5日均量: {vol_avg:.0f}亿, {vol_trend}" if vol_avg and vol_trend else vol_trend
                detail_str = f" ({vol_detail})" if vol_detail else ""
                content += f"**沪深市场成交额**: {market_volume:.0f}亿{detail_str}\n\n"

            # 不通过原因
            if reasons:
                content += f"**📕 不通过原因**:\n"
                for r in reasons:
                    content += f"   • {r}\n"

            # 发送飞书通知
            notifier = get_feishu_notifier()
            if not notifier.enabled:
                logger.warning("⚠️ 飞书通知未启用，跳过大盘信号推送")
                return

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message = {
                "msg_type": "interactive",
                "card": {
                    "config": {"wide_screen_mode": True},
                    "header": {
                        "title": {"tag": "plain_text", "content": "📡 大盘环境信号"},
                        "template": "red" if not passed else "green"
                    },
                    "elements": [
                        {"tag": "div", "text": {"tag": "lark_md", "content": content}},
                        {"tag": "hr"},
                        {"tag": "note", "elements": [
                            {"tag": "plain_text", "content": f"ETF马丁格尔量化交易系统 | {current_time}"}
                        ]}
                    ]
                }
            }

            headers = {'Content-Type': 'application/json'}
            response = requests.post(
                notifier.webhook_url,
                headers=headers,
                data=json.dumps(message, ensure_ascii=False).encode('utf-8'),
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                if result.get('StatusCode') == 0 or result.get('code') == 0:
                    logger.success(f"📱 大盘环境信号飞书通知发送成功")
                else:
                    logger.error(f"❌ 飞书API返回错误: {result.get('msg', '未知错误')}")
            else:
                logger.error(f"❌ 飞书通知发送失败，HTTP状态码: {response.status_code}")

            logger.info("✅ 大盘环境信号通知完成\n")

        except Exception as e:
            logger.error(f"❌ 大盘环境信号通知异常: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _send_stockpool_notification(self):
        """
        发送选股结果飞书通知
        """
        try:
            logger.info("\n" + "="*80)
            logger.info("📊 【选股结果通知】开始执行...")
            logger.info("="*80)
            
            # 1. 获取最近的交易日
            trading_date = self._get_latest_trading_date()
            logger.info(f"📅 目标日期: {trading_date}")
            
            # 2. 构建文件路径
            filename = f"stockpool_{trading_date}.txt"
            filepath = project_root / "data" / filename
            
            if not filepath.exists():
                logger.warning(f"⚠️ 选股结果文件不存在: {filepath}")
                logger.info("ℹ️ 跳过选股结果通知")
                return
            
            logger.info(f"✅ 找到选股结果文件: {filepath}")
            
            # 3. 读取文件内容
            stocks = []
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # 跳过注释行、分隔线和空行
                    if not line or line.startswith('#') or line.startswith('-'):
                        continue
                    
                    # 解析股票代码和评分
                    if ',' in line:
                        parts = line.split(',')
                        if len(parts) >= 2:
                            code = parts[0].strip()
                            try:
                                score = float(parts[1].strip())
                            except ValueError:
                                logger.warning(f"⚠️ 评分解析失败: {line}")
                                continue
                            
                            # 添加市场前缀
                            if not code.startswith(('sh.', 'sz.', 'bj.')):
                                if code.startswith('6'):
                                    code = f'sh.{code}'
                                elif code.startswith(('0', '3')):
                                    code = f'sz.{code}'
                                elif code.startswith(('8', '4')):
                                    code = f'bj.{code}'
                                else:
                                    continue
                            
                            stocks.append({
                                'code': code,
                                'score': score
                            })
            
            if not stocks:
                logger.info("ℹ️ 选股结果为空，跳过通知")
                return
            
            logger.info(f"📈 读取到 {len(stocks)} 只股票")
            
            # 4. 获取股票详细信息（名称、PE-TTM、换手率）
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            stock_details = []
            
            for i, stock in enumerate(stocks, 1):
                code = stock['code']
                score = stock['score']
                
                logger.info(f"   [{i}/{len(stocks)}] 处理 {code}...")
                
                # 获取股票名称
                from src.utils.buy_order_scheduler import get_stock_name
                code_without_prefix = code.split('.')[1] if '.' in code else code
                name = get_stock_name(code_without_prefix)
                
                # 获取基本面指标（PE-TTM、换手率、最高价、收盘价）
                fundamentals = self._get_stock_fundamentals(code)
                pe_ttm = fundamentals.get('pe_ttm')
                turnover_rate = fundamentals.get('turnover_rate')
                high_price = fundamentals.get('high_price')
                close_price = fundamentals.get('close_price')
                
                stock_details.append({
                    'code': code_without_prefix,
                    'full_code': code,
                    'name': name,
                    'score': score,
                    'pe_ttm': pe_ttm,
                    'turnover_rate': turnover_rate,
                    'high_price': high_price,
                    'close_price': close_price
                })
                
                # 避免请求过快
                import time
                time.sleep(0.5)
            
            # 5. 构建飞书消息
            content = f"**今日选股结果**\n"
            content += f"**时间**: {current_time}\n"
            content += f"**数量**: {len(stock_details)} 只股票\n\n"
            content += f"**━━━━━━━━━━━━━━━**\n\n"
            
            for i, stock in enumerate(stock_details, 1):
                pe_str = f"{stock['pe_ttm']:.2f}" if stock['pe_ttm'] is not None else "N/A"
                turnover_str = f"{stock['turnover_rate']:.2f}%" if stock['turnover_rate'] is not None else "N/A"
                
                # 计算当日回撤
                intraday_drawdown = None
                if stock['high_price'] is not None and stock['close_price'] is not None and stock['close_price'] > 0:
                    intraday_drawdown = (stock['high_price'] - stock['close_price']) / stock['close_price'] * 100
                
                content += f"**{i}. {stock['name']} ({stock['code']})**\n"
                content += f"   评分: {stock['score']:.1f}分\n"
                content += f"   PE-TTM: {pe_str}\n"
                content += f"   换手率: {turnover_str}\n"
                
                # 如果当日回撤 >= 5%，显示回撤信息
                if intraday_drawdown is not None and intraday_drawdown >= 5:
                    drawdown_str = f"{intraday_drawdown:.2f}%"
                    # 如果 >= 8%，使用红色标记
                    if intraday_drawdown >= 8:
                        content += f"   <font color='red'>当日回撤: -{drawdown_str}</font>\n"
                    else:
                        content += f"   当日回撤: -{drawdown_str}\n"
                
                content += f"\n"
            content += f"**━━━━━━━━━━━━━━━**\n"
            
            # 6. 发送飞书通知
            notifier = get_feishu_notifier()
            
            if not notifier.enabled:
                logger.warning("⚠️ 飞书通知未启用，跳过发送")
                return
            
            # 构建飞书消息体
            message = {
                "msg_type": "interactive",
                "card": {
                    "config": {
                        "wide_screen_mode": True
                    },
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": "今日选股结果"
                        },
                        "template": "blue"
                    },
                    "elements": [
                        {
                            "tag": "div",
                            "text": {
                                "tag": "lark_md",
                                "content": content
                            }
                        },
                        {
                            "tag": "hr"
                        },
                        {
                            "tag": "note",
                            "elements": [
                                {
                                    "tag": "plain_text",
                                    "content": f"ETF马丁格尔量化交易系统 | {current_time}"
                                }
                            ]
                        }
                    ]
                }
            }
            
            # 发送请求
            import json
            headers = {'Content-Type': 'application/json'}
            response = requests.post(
                notifier.webhook_url,
                headers=headers,
                data=json.dumps(message, ensure_ascii=False).encode('utf-8'),
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('StatusCode') == 0 or result.get('code') == 0:
                    logger.success(f"📱 选股结果飞书通知发送成功: {len(stock_details)} 只股票")
                else:
                    error_code = result.get('code', 'unknown')
                    error_msg = result.get('msg', '未知错误')
                    logger.error(f"❌ 飞书API返回错误 (code: {error_code}): {error_msg}")
            else:
                logger.error(f"❌ 飞书通知发送失败，HTTP状态码: {response.status_code}")
            
            logger.info("✅ 选股结果通知完成\n")
            
        except Exception as e:
            logger.error(f"❌ 选股结果通知执行异常: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def start(self):
        """启动调度器"""
        if not self.monitor_config.enabled or not self.stock_pool:
            logger.warning("⚠️ 股票资讯监控未正确配置，无法启动")
            return
        
        # 启动调度器
        self.scheduler.start()
        logger.info(f"✅ 股票资讯监控定时任务已启动")
        logger.info(f"📅 下次执行时间: {self._get_next_run_time()}")
    
    def stop(self):
        """停止调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("⏹️ 股票资讯监控定时任务已停止")
    
    def _get_next_run_time(self):
        """获取下次运行时间"""
        try:
            job = self.scheduler.get_job('news_monitor_job')
            if job and job.next_run_time:
                return job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
        except:
            pass
        return "未知"
    
    def run_once(self, target_date: str = None):
        """立即执行一次（用于测试）
        
        Args:
            target_date: 目标日期（格式：YYYY-MM-DD），用于测试
        """
        if target_date:
            logger.info(f"🧪 立即执行一次资讯监控（测试日期: {target_date}）...")
        else:
            logger.info("🧪 立即执行一次资讯监控...")
        self._fetch_and_send_news(target_date)


# 全局调度器实例
_news_scheduler = None


def get_news_monitor_scheduler() -> NewsMonitorScheduler:
    """获取资讯监控调度器单例"""
    global _news_scheduler
    if _news_scheduler is None:
        _news_scheduler = NewsMonitorScheduler()
    return _news_scheduler


def start_news_monitor_scheduler():
    """启动资讯监控调度器"""
    scheduler = get_news_monitor_scheduler()
    scheduler.start()
    return scheduler


def stop_news_monitor_scheduler():
    """停止资讯监控调度器"""
    global _news_scheduler
    if _news_scheduler:
        _news_scheduler.stop()
        _news_scheduler = None


def test_news_monitor(target_date: str = None):
    """测试资讯监控（立即执行一次）
    
    Args:
        target_date: 目标日期（格式：YYYY-MM-DD），用于测试
    """
    scheduler = get_news_monitor_scheduler()
    scheduler.run_once(target_date)