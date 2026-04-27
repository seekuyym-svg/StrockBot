# -*- coding: utf-8 -*-
"""股票资讯爬虫模块 - 从新浪财经和东方财富网获取个股资讯和财务报告"""
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from datetime import datetime
from loguru import logger
import time


class EastMoneyCrawler:
    """东方财富网爬虫"""
    
    def __init__(self):
        """初始化爬虫"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Referer': 'https://quote.eastmoney.com/',
        })
        self.timeout = 10  # 超时时间（秒）
        
    def fetch_individual_news(self, symbol: str, stock_name: str, target_date: str = None) -> List[Dict[str, Any]]:
        """
        获取个股资讯
        
        Args:
            symbol: 股票代码 (如 sz.002706)
            stock_name: 股票名称
            target_date: 目标日期 (YYYY-MM-DD)，如果为None则获取最新
            
        Returns:
            资讯列表
        """
        # 处理股票代码格式
        pure_code = symbol.replace('.', '').replace('sz', '').replace('sh', '')
        
        # 确定市场前缀
        market_prefix = 'sz' if symbol.startswith('sz') or (len(pure_code) == 6 and pure_code[0] in ['0', '3']) else 'sh'
        
        # 使用新浪财经API
        news_list = self._fetch_from_sina(market_prefix, pure_code, stock_name, symbol, target_date)
        
        logger.info(f"✅ 成功获取 {len(news_list)} 条个股资讯")
        return news_list
    
    def _fetch_from_sina(self, market_prefix: str, pure_code: str, stock_name: str, symbol: str, target_date: str = None) -> List[Dict[str, Any]]:
        """从新浪财经获取个股资讯 - 从主页面直接抓取"""
        news_list = []
        
        try:
            # 构建URL - 使用新浪财经个股主页
            url = f"https://finance.sina.com.cn/realstock/company/{market_prefix}{pure_code}/nc.shtml"
            
            date_info = f" (目标日期: {target_date})" if target_date else ""
            logger.info(f"🕷️ 正在从新浪财经抓取 {stock_name}({symbol}) 的个股资讯{date_info}...")
            logger.info(f"   URL: {url}")
            
            response = self.session.get(url, timeout=self.timeout, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://finance.sina.com.cn/'
            })
            response.raise_for_status()
            # 新浪财经页面使用GBK编码
            response.encoding = 'gbk'
            
            # 解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 找到公司资讯模块
            news_div = soup.find('div', class_='block_news_gs')
            if not news_div:
                logger.warning("   未找到公司资讯模块")
                return []
            
            # 找到ul列表
            ul = news_div.find('ul')
            if not ul:
                logger.warning("   未找到资讯列表")
                return []
            
            # 提取所有li项
            items = ul.find_all('li')
            logger.info(f"   找到 {len(items)} 条资讯")
            
            for item in items:
                span = item.find('span')
                a = item.find('a')
                
                if not a:
                    continue
                
                # 提取日期
                date_str = span.get_text(strip=True) if span else ""
                # 转换日期格式 (04-18) -> 2026-04-18
                if date_str and len(date_str) == 7:  # 格式如 (04-18)
                    month_day = date_str.strip('()')
                    current_year = datetime.now().year
                    full_date = f"{current_year}-{month_day}"
                else:
                    full_date = datetime.now().strftime('%Y-%m-%d')
                
                # 提取标题和链接
                title = a.get_text(strip=True)
                href = a.get('href', '')
                
                if not title or len(title) < 5:
                    continue
                
                # 构建完整URL
                if href.startswith('/'):
                    full_url = f"https://finance.sina.com.cn{href}"
                elif href.startswith('http'):
                    full_url = href
                else:
                    continue
                
                # 添加到列表
                news_list.append({
                    'title': title[:200],  # 限制标题长度
                    'time': full_date,
                    'url': full_url,
                    'type': 'individual_news',
                    'symbol': symbol,
                    'stock_name': stock_name
                })
            
            # 去重（基于URL）
            seen_urls = set()
            unique_news = []
            for news in news_list:
                if news['url'] not in seen_urls:
                    seen_urls.add(news['url'])
                    unique_news.append(news)
            
            news_list = unique_news
            
            logger.info(f"   解析完成，共 {len(news_list)} 条资讯")
            
        except Exception as e:
            logger.error(f"新浪财经API失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())
        
        return news_list

    def _fetch_from_cninfo(self, pure_code: str, market_prefix: str, stock_name: str, symbol: str, target_date: str = None) -> List[Dict[str, Any]]:
        """从巨潮资讯网获取公告"""
        url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
        
        payload = {
            'pageSize': '50',
            'pageNum': '1',
            'column': 'szse' if market_prefix == 'SZ' else 'sse',
            'tabName': 'fulltext',
            'plate': '',
            'stock': f'{pure_code},{market_prefix}',
            'searchkey': '',
            'secid': '',
            'category': '',
            'trade': ''
        }
        
        try:
            date_info = f" (目标日期: {target_date})" if target_date else ""
            logger.info(f"🕷️ 正在抓取 {stock_name}({symbol}) 的个股资讯{date_info}...")
            
            response = self.session.post(url, data=payload, timeout=self.timeout, headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': 'http://www.cninfo.com.cn/',
                'X-Requested-With': 'XMLHttpRequest'
            })
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            data = response.json()
            return self._parse_cninfo_announcements(data, symbol, stock_name, target_date, market_prefix)
            
        except Exception as e:
            logger.warning(f"巨潮API失败: {e}")
            return []
    
    def _fetch_f10_fallback(self, market_prefix: str, pure_code: str, stock_name: str, symbol: str, target_date: str = None) -> List[Dict[str, Any]]:
        """使用F10公司大事页面作为fallback"""
        news_list = []
        
        try:
            # F10公司大事页面URL
            url = f"https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html?type=web&code={market_prefix}{pure_code}#/gsds"
            
            date_info = f" (目标日期: {target_date})" if target_date else ""
            logger.info(f"🕷️ 正在通过F10页面获取 {stock_name}({symbol}) 的资讯{date_info}...")
            
            # 由于F10页面也是SPA，我们直接提供一个有意义的链接
            # 让用户点击后查看完整的公司大事
            news_list.append({
                'title': f'{stock_name} - 点击查看完整公司大事和最新资讯',
                'time': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'url': url,
                'type': 'individual_news',
                'symbol': symbol,
                'stock_name': stock_name
            })
            
            logger.info(f"   提供F10页面链接供用户查看")
            
        except Exception as e:
            logger.error(f"F10 fallback失败: {e}")
        
        return news_list
    
    def _parse_cninfo_announcements(self, data: Dict, symbol: str, stock_name: str, target_date: str = None, market_prefix: str = 'SZ') -> List[Dict[str, Any]]:
        """
        解析巨潮资讯网公告
        
        Args:
            data: API返回的数据
            symbol: 股票代码
            stock_name: 股票名称
            target_date: 目标日期
            market_prefix: 市场前缀
            
        Returns:
            解析后的资讯列表
        """
        news_list = []
        
        try:
            announcements = data.get('announcements', [])
            if not announcements:
                logger.info("   未找到公告数据")
                return []
            
            for ann in announcements:
                try:
                    title = ann.get('announcementTitle', '')
                    announcement_time = ann.get('announcementTime', '')
                    adjunct_url = ann.get('adjunctUrl', '')
                    sec_name = ann.get('secName', stock_name)
                    
                    if not title or len(title) < 5:
                        continue
                    
                    # 格式化时间（时间戳转日期）
                    pub_time = self._format_timestamp(announcement_time)
                    
                    # 如果指定了目标日期，过滤不匹配的日期
                    if target_date and target_date not in pub_time:
                        continue
                    
                    # 构建完整URL
                    if adjunct_url:
                        url = f"http://www.cninfo.com.cn/{adjunct_url}"
                    else:
                        #  fallback到F10页面
                        pure_code = symbol.split('.')[-1] if '.' in symbol else symbol
                        url = f"https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html?type=web&code={market_prefix}{pure_code}#/gsds"
                    
                    news_list.append({
                        'title': title[:200],  # 保留完整标题
                        'time': pub_time,
                        'url': url,
                        'type': 'individual_news',
                        'symbol': symbol,
                        'stock_name': stock_name
                    })
                    
                except Exception as e:
                    logger.debug(f"解析单条公告失败: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"解析API数据失败: {e}")
        
        logger.info(f"   解析完成，共 {len(news_list)} 条资讯")
        return news_list
    
    def _format_timestamp(self, timestamp) -> str:
        """
        格式化时间戳
        
        Args:
            timestamp: 时间戳（毫秒）
            
        Returns:
            标准格式的时间字符串
        """
        if not timestamp:
            return datetime.now().strftime('%Y-%m-%d %H:%M')
        
        try:
            # 如果是整数时间戳（毫秒）
            if isinstance(timestamp, (int, float)):
                ts = timestamp / 1000 if timestamp > 10000000000 else timestamp
                return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
            
            # 如果已经是字符串
            if isinstance(timestamp, str):
                if '-' in timestamp and ':' in timestamp:
                    return timestamp[:16]
                elif '-' in timestamp:
                    return timestamp[:10] + " 00:00"
        except:
            pass
        
        return str(timestamp)
    
    def fetch_financial_reports(self, symbol: str, stock_name: str, target_date: str = None) -> List[Dict[str, Any]]:
        """
        获取财务报告公告
        
        Args:
            symbol: 股票代码（格式：sh.600000 或 sz.000001）
            stock_name: 股票名称
            target_date: 目标日期（格式：YYYY-MM-DD），用于测试
            
        Returns:
            公告列表，每项包含 title, time, url
        """
        # 转换股票代码格式为纯数字
        pure_code = symbol.split('.')[-1] if '.' in symbol else symbol
        
        # 使用公告API v1
        url = f"http://np-anotice-stock.eastmoney.com/api/security/ann?sr=-1&page_size=50&page_index=1&ann_type=A&client_source=web&stock_list={pure_code}&f_node=0&s_node=0"
        
        try:
            date_info = f" (目标日期: {target_date})" if target_date else ""
            logger.info(f"🕷️ 正在抓取 {stock_name}({symbol}) 的财务报告公告{date_info}...")
            
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            data = response.json()
            reports_list = self._parse_financial_reports_api(data, symbol, stock_name, target_date)
            logger.info(f"✅ 成功获取 {len(reports_list)} 条财务报告")
            return reports_list
            
        except Exception as e:
            logger.error(f"❌ 抓取 {stock_name} 财务报告失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return []
    
    def _parse_financial_reports_api(self, data: Dict, symbol: str, stock_name: str, target_date: str = None) -> List[Dict[str, Any]]:
        """
        解析财务报告公告API响应
        
        Args:
            data: API返回的数据
            symbol: 股票代码
            stock_name: 股票名称
            target_date: 目标日期
            
        Returns:
            解析后的公告列表
        """
        reports_list = []
        
        try:
            # 查找公告列表
            ann_data = data.get('data', {})
            if not isinstance(ann_data, dict):
                return []
                
            announcements = ann_data.get('list', [])
            
            for announcement in announcements:
                try:
                    title = announcement.get('title', '') or announcement.get('title_ch', '')
                    notice_date = announcement.get('notice_date', '')
                    art_code = announcement.get('art_code', '')
                    
                    if not title or len(title) < 5:
                        continue
                    
                    # 只保留财务报告相关的公告
                    financial_keywords = ['年报', '季报', '财报', '报告', '审计', '公告', '披露', '业绩', '财务', 
                                        '内部控制', '社会责任', 'ESG', '利润分配', '会计估计']
                    if not any(keyword in title for keyword in financial_keywords):
                        continue
                    
                    # 格式化时间
                    pub_time = self._format_notice_date(notice_date)
                    
                    # 如果指定了目标日期，过滤不匹配的日期
                    if target_date and target_date not in pub_time:
                        continue
                    
                    # 构建公告详情页URL - 使用东方财富网
                    if art_code:
                        # 东方财富网公告详情页
                        url = f"http://data.eastmoney.com/notices/detail/{symbol.split('.')[-1]}/{art_code}.html"
                    else:
                        url = ""
                    
                    reports_list.append({
                        'title': title[:200],  # 保留完整标题
                        'time': pub_time,
                        'url': url,
                        'type': 'financial_report',
                        'symbol': symbol,
                        'stock_name': stock_name
                    })
                    
                except Exception as e:
                    logger.debug(f"解析单条公告失败: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"解析API数据失败: {e}")
        
        logger.info(f"   解析完成，共 {len(reports_list)} 条公告")
        return reports_list
    
    def _format_time(self, time_str: str) -> str:
        """
        格式化时间字符串
        
        Args:
            time_str: 时间字符串
            
        Returns:
            标准格式的时间字符串
        """
        if not time_str:
            return datetime.now().strftime('%Y-%m-%d %H:%M')
        
        try:
            # 处理各种日期格式
            if 'T' in time_str:
                # ISO格式: 2024-01-01T00:00:00
                return time_str[:16].replace('T', ' ')
            elif '-' in time_str and ':' in time_str:
                # 标准格式: 2024-01-01 12:00:00
                return time_str[:16]
            elif '-' in time_str:
                # 仅日期: 2024-01-01
                return time_str[:10] + " 00:00"
        except:
            pass
        
        return time_str
    
    def _format_notice_date(self, date_str: str) -> str:
        """
        格式化公告日期
        
        Args:
            date_str: 日期字符串
            
        Returns:
            标准格式的时间字符串
        """
        if not date_str:
            return datetime.now().strftime('%Y-%m-%d %H:%M')
        
        try:
            # 处理格式: 2026-04-11 00:00:00
            if '-' in date_str and ':' in date_str:
                return date_str[:16]
            elif '-' in date_str:
                return date_str[:10] + " 00:00"
        except:
            pass
        
        return date_str
    
    def fetch_all_news(self, stock_pool: List[Dict[str, str]], target_date: str = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取股票池中所有股票的资讯和公告
        
        Args:
            stock_pool: 股票池列表，每项包含 code 和 name
            target_date: 目标日期（格式：YYYY-MM-DD），用于测试
            
        Returns:
            字典，key为股票代码，value为该股票的资讯和公告列表
        """
        all_news = {}
        
        for stock in stock_pool:
            symbol = stock['code']
            name = stock['name']
            
            # 获取个股资讯
            individual_news = self.fetch_individual_news(symbol, name, target_date)
            
            # 获取财务报告
            financial_reports = self.fetch_financial_reports(symbol, name, target_date)
            
            # 合并结果
            all_news[symbol] = {
                'name': name,
                'individual_news': individual_news,
                'financial_reports': financial_reports,
                'total_count': len(individual_news) + len(financial_reports)
            }
            
            # 避免请求过快被限制
            time.sleep(1)
        
        return all_news


# 全局爬虫实例
_crawler = None


def get_eastmoney_crawler() -> EastMoneyCrawler:
    """获取东方财富爬虫单例"""
    global _crawler
    if _crawler is None:
        _crawler = EastMoneyCrawler()
    return _crawler