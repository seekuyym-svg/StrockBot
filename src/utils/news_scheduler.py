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

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.config import get_config
from src.utils.news_crawler import get_eastmoney_crawler
from src.utils.notification import send_news_notification


class NewsMonitorScheduler:
    """股票资讯监控调度器"""
    
    def __init__(self):
        """初始化调度器"""
        self.scheduler = BackgroundScheduler()
        self.config = get_config()
        self.monitor_config = self.config.stock_news_monitor
        self.crawler = get_eastmoney_crawler()
        
        if not self.monitor_config.enabled:
            logger.info("ℹ️ 股票资讯监控未启用")
            return
        
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
    
    def _fetch_stock_metrics(self, symbol: str, name: str) -> dict:
        """
        获取股票行情指标（涨跌幅、市值等）- 使用腾讯财经API
        
        Args:
            symbol: 股票代码 (如 sz.002706)
            name: 股票名称
            
        Returns:
            包含涨跌幅和市值的字典
        """
        metrics = {
            'daily_change_pct': None,  # 最近一日涨跌幅
            'weekly_change_pct': None,  # 最近一周涨跌幅
            'monthly_change_pct': None,  # 最近一月涨跌幅
            'circulating_market_cap': None  # 流通市值（亿元）
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
                        # 提取日涨跌幅（parts[32]是涨跌幅百分比）
                        change_pct = float(parts_data[32]) if parts_data[32] else 0
                        metrics['daily_change_pct'] = round(change_pct, 2)
                        
                        # 提取流通市值
                        # 字段[72]或[76]是流通股本（股数），需要乘以当前价格得到市值
                        current_price = float(parts_data[3]) if parts_data[3] else 0
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
                        
                        logger.debug(f"   ✅ 腾讯实时行情: 日{metrics['daily_change_pct']:+.2f}% | 市值{metrics['circulating_market_cap']}亿")
            
            # 2. 从腾讯财经获取历史K线数据计算周/月涨跌幅
            klines = self._get_historical_klines_from_tencent(market.lower(), code, days=120)
            
            if not klines.empty and len(klines) >= 21:
                latest_close = klines['收盘'].iloc[-1]
                
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
            
            logger.info(f"   ✅ 行情指标: 日{daily_str} | 周{weekly_str} | 月{monthly_str} | 市值{cap_str}")
            
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
                
                # 获取趋势分析结果
                logger.info(f"   📈 正在进行多空信号分析...")
                trend_analysis = trend_analyzer.analyze_stock(symbol, name)
                
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
            
            # 发送飞书通知
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