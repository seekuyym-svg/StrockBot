# -*- coding: utf-8 -*-
"""飞书通知模块 - 通过飞书机器人发送交易信号通知"""
import requests
import json
from typing import Dict, Any, Optional
from datetime import datetime
from loguru import logger
from src.utils.config import get_config
from src.utils.market_analyzer import analyze_market, get_analysis_description


class FeishuNotifier:
    """飞书通知器"""
    
    def __init__(self):
        """初始化飞书通知器"""
        self.config = get_config()
        self.feishu_config = self.config.notification.feishu
        self.enabled = self.feishu_config.enabled
        self.webhook_url = self.feishu_config.webhook_url
        self.notify_signals = self.feishu_config.notify_signals
        
        # 频率控制：记录最后发送时间
        self.last_send_time = {}  # {symbol_signal_type: timestamp}
        self.min_interval_seconds = 60  # 同一标的同类型信号最小间隔60秒
        
        if self.enabled:
            if not self.webhook_url:
                logger.warning("⚠️ 飞书通知已启用但未配置 Webhook URL，通知功能将不可用")
                self.enabled = False
            else:
                logger.info(f"✅ 飞书通知已启用，将通知以下信号类型: {self.notify_signals}")
                logger.info(f"⏱️ 频率控制：同一标的同类型信号最小间隔 {self.min_interval_seconds} 秒")
        else:
            logger.info("ℹ️ 飞书通知未启用")
    
    def should_notify(self, signal_type: str, reason: str = "") -> bool:
        """
        判断是否应该发送通知
        
        Args:
            signal_type: 信号类型（BUY/SELL/ADD/STOP/WAIT）
            reason: 信号原因（用于判断是否为价格监控提醒）
            
        Returns:
            bool: 是否应该发送通知
        """
        logger.debug(f"🔧 [DEBUG-Notify] should_notify 检查: signal_type='{signal_type}', reason='{reason[:50]}...'")
        
        if not self.enabled:
            logger.debug(f"❌ [DEBUG-Notify] 飞书通知未启用，返回False")
            return False
        
        # 如果是价格监控提醒，即使类型为WAIT也发送
        if signal_type == "WAIT" and "价格监控" in reason:
            logger.debug(f"✅ [DEBUG-Notify] 检测到价格监控提醒，允许发送")
            return True
        
        result = signal_type in self.notify_signals
        logger.debug(f"🔧 [DEBUG-Notify] 检查 signal_type 是否在 notify_signals {self.notify_signals} 中: {result}")
        return result
    
    def send_signal_notification(self, signal_data: Dict[str, Any]) -> bool:
        """
        发送交易信号通知
        
        Args:
            signal_data: 信号数据字典
            
        Returns:
            bool: 是否发送成功
        """
        logger.debug(f"\n{'='*60}")
        logger.debug(f"📱 [DEBUG-Notify] 开始发送飞书通知")
        logger.debug(f"📱 [DEBUG-Notify] 信号数据: symbol={signal_data.get('symbol')}, signal_type={signal_data.get('signal_type')}")
        
        if not self.enabled:
            logger.warning(f"❌ [DEBUG-Notify] 飞书通知未启用，直接返回False")
            logger.debug(f"{'='*60}\n")
            return False
        
        symbol = signal_data.get('symbol', '')
        signal_type = signal_data.get('signal_type', '')
        reason = signal_data.get('reason', '')
        symbol_signal_type = f"{symbol}_{signal_type}"
        
        logger.debug(f"🔧 [DEBUG-Notify] symbol={symbol}, signal_type={signal_type}, reason='{reason[:50]}...'")
        logger.debug(f"🔧 [DEBUG-Notify] 频率控制键名: {symbol_signal_type}")
        
        # 检查是否需要通知该类型的信号（传入reason用于价格监控判断）
        logger.debug(f"🔧 [DEBUG-Notify] 调用 should_notify...")
        should_send = self.should_notify(signal_type, reason)
        logger.debug(f"🔧 [DEBUG-Notify] should_notify 返回: {should_send}")
        
        if not should_send:
            logger.debug(f"❌ [DEBUG-Notify] should_notify 返回False，不发送通知")
            logger.debug(f"{'='*60}\n")
            return False
        
        logger.debug(f"✅ [DEBUG-Notify] 通过 should_notify 检查")
        
        # 检查频率控制
        current_time = datetime.now().timestamp()
        last_send_time = self.last_send_time.get(symbol_signal_type, 0)
        time_since_last_send = current_time - last_send_time
        
        logger.debug(f"🔧 [DEBUG-Notify] 频率控制检查:")
        logger.debug(f"   当前时间戳: {current_time:.0f}")
        logger.debug(f"   上次发送时间戳: {last_send_time:.0f}")
        logger.debug(f"   时间间隔: {time_since_last_send:.0f}秒 (要求>=60秒)")
        
        if time_since_last_send < self.min_interval_seconds:
            remaining_time = self.min_interval_seconds - time_since_last_send
            logger.warning(f"⚠️ [DEBUG-Notify] 飞书通知频率限制：{symbol} {signal_type} 距上次发送仅 {time_since_last_send:.0f}秒，还需等待 {remaining_time:.0f}秒")
            logger.debug(f"❌ [DEBUG-Notify] 频率控制拦截，返回False")
            logger.debug(f"{'='*60}\n")
            return False
        
        logger.debug(f"✅ [DEBUG-Notify] 通过频率控制检查")
        
        try:
            # 构建消息内容
            logger.debug(f"🔧 [DEBUG-Notify] 调用 _build_message...")
            message = self._build_message(signal_data)
            logger.debug(f"✅ [DEBUG-Notify] 消息构建成功")
            
            # 发送请求
            logger.debug(f"🔧 [DEBUG-Notify] 准备发送HTTP请求到: {self.webhook_url[:50]}...")
            headers = {'Content-Type': 'application/json'}
            response = requests.post(
                self.webhook_url,
                headers=headers,
                data=json.dumps(message, ensure_ascii=False).encode('utf-8'),
                timeout=10
            )
            
            logger.debug(f"🔧 [DEBUG-Notify] HTTP响应状态码: {response.status_code}")
            
            # 检查响应
            if response.status_code == 200:
                result = response.json()
                logger.debug(f"🔧 [DEBUG-Notify] API响应: {result}")
                
                if result.get('StatusCode') == 0 or result.get('code') == 0:
                    logger.success(f"📱 飞书通知发送成功: {signal_data.get('symbol')} - {signal_type}")
                    logger.debug(f"✅ [DEBUG-Notify] 更新最后发送时间: {symbol_signal_type} = {current_time:.0f}")
                    self.last_send_time[symbol_signal_type] = current_time
                    logger.debug(f"{'='*60}\n")
                    return True
                else:
                    error_code = result.get('code', 'unknown')
                    error_msg = result.get('msg', '未知错误')
                    
                    # 特别处理频率限制错误
                    if error_code == 11232:
                        logger.warning(f"⚠️ 飞书API频率限制（code: {error_code}）：{error_msg}")
                        logger.warning(f"💡 建议：增加 min_interval_seconds 配置或检查是否有多个实例运行")
                    else:
                        logger.error(f"❌ 飞书API返回错误 (code: {error_code}): {error_msg}")
                    
                    logger.debug(f"❌ [DEBUG-Notify] API返回错误，返回False")
                    logger.debug(f"{'='*60}\n")
                    return False
            else:
                logger.error(f"❌ 飞书通知发送失败，HTTP状态码: {response.status_code}")
                logger.debug(f"❌ [DEBUG-Notify] HTTP状态码非200，返回False")
                logger.debug(f"{'='*60}\n")
                return False
                
        except requests.exceptions.Timeout:
            logger.error("❌ 飞书通知发送超时")
            logger.debug(f"❌ [DEBUG-Notify] 请求超时异常，返回False")
            logger.debug(f"{'='*60}\n")
            return False
        except requests.exceptions.ConnectionError:
            logger.error("❌ 飞书通知连接失败，请检查网络和Webhook URL")
            logger.debug(f"❌ [DEBUG-Notify] 连接异常，返回False")
            logger.debug(f"{'='*60}\n")
            return False
        except Exception as e:
            logger.error(f"❌ 飞书通知发送异常: {e}")
            logger.debug(f"❌ [DEBUG-Notify] 未知异常: {type(e).__name__}: {e}")
            logger.debug(f"{'='*60}\n")
            return False
    
    def _build_message(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建飞书消息体
        
        Args:
            signal_data: 信号数据字典
            
        Returns:
            Dict: 飞书消息体
        """
        symbol = signal_data.get('symbol', 'N/A')
        name = signal_data.get('name', 'N/A')
        signal_type = signal_data.get('signal_type', 'N/A')
        
        # 确保signal_type是字符串格式（处理枚举对象）
        if hasattr(signal_type, 'value'):
            signal_type = signal_type.value
        elif hasattr(signal_type, 'name'):
            signal_type = signal_type.name
        
        price = signal_data.get('price', 0)
        change_pct = signal_data.get('change_pct', 0)
        reason = signal_data.get('reason', '')
        target_shares = signal_data.get('target_shares', 0)
        avg_cost = signal_data.get('avg_cost', 0)
        
        # 根据信号类型设置颜色和标题
        color_map = {
            'BUY': 'green',
            'ADD': 'blue',
            'SELL': 'red',
            'STOP': 'orange'
        }
        
        emoji_map = {
            'BUY': '🟢',
            'ADD': '🔵',
            'SELL': '🔴',
            'STOP': '⚠️'
        }
        
        title_map = {
            'BUY': '买入信号',
            'ADD': '加仓信号',
            'SELL': '卖出信号',
            'STOP': '止损信号'
        }
        
        # 检测是否为价格监控提醒
        is_price_alert = "价格监控" in reason
        
        if is_price_alert:
            # 根据reason内容设置不同的颜色和标题
            if "卖出提醒" in reason or "回落" in reason:
                color = "red"
                emoji = "🔴"
                title = "卖出提醒（价格监控）"
            elif "买入提醒" in reason or "反弹" in reason:
                color = "green"
                emoji = "🟢"
                title = "买入提醒（价格监控）"
            else:
                color = "gray"
                emoji = "📊"
                title = "价格监控提醒"
        else:
            color = color_map.get(signal_type, 'gray')
            emoji = emoji_map.get(signal_type, '📊')
            title = title_map.get(signal_type, '交易信号')
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 构建消息内容
        # **{emoji} {title}**
        content = f"""   
**标的**: {name} ({symbol})
**类型**: {signal_type}
**价格**: ¥{price:.3f}
**涨跌**: {change_pct:+.2f}%"""
        # **时间**: {current_time}
        
        # 添加额外信息
        if target_shares > 0:
            content += f"\n**目标份额**: {target_shares:,} 份"
        
        if avg_cost > 0:
            content += f"\n**平均成本**: ¥{avg_cost:.3f}"
        
        # 添加BOLL布林带三轨完整价差信息（简化格式）
        boll_up_diff_pct = signal_data.get('boll_up_diff_pct')
        boll_middle_diff_pct = signal_data.get('boll_middle_diff_pct')
        boll_down_diff_pct = signal_data.get('boll_down_diff_pct')
        
        if all([boll_up_diff_pct is not None, boll_middle_diff_pct is not None, boll_down_diff_pct is not None]):
            # 计算各轨道价差的绝对值（用于判断哪个最近）
            up_abs = abs(boll_up_diff_pct)
            middle_abs = abs(boll_middle_diff_pct)
            down_abs = abs(boll_down_diff_pct)
            
            # 找出最近的轨道
            min_diff = min(up_abs, middle_abs, down_abs)
            closest_track = ""
            if min_diff == up_abs:
                closest_track = "上轨"
            elif min_diff == middle_abs:
                closest_track = "中轨"
            else:
                closest_track = "下轨"
            
            # 构建简化的BOLL信息显示
            up_marker = " ← 此轨最近" if closest_track == "上轨" else ""
            middle_marker = " ← 此轨最近" if closest_track == "中轨" else ""
            down_marker = " ← 此轨最近" if closest_track == "下轨" else ""
            
            boll_info = f"BOLL: 上轨{boll_up_diff_pct:+.2f}%{up_marker} | 中轨{boll_middle_diff_pct:+.2f}%{middle_marker} | 下轨{boll_down_diff_pct:+.2f}%{down_marker}"
            content += f"\n**{boll_info}**"
        
        # 添加RSI指标及判断
        rsi_value = signal_data.get('rsi')
        if rsi_value is not None:
            # 判断RSI区域
            if rsi_value > 70:
                rsi_zone = "超买区 ⚠️"
                rsi_emoji = "🔴"
            elif rsi_value >= 30:
                rsi_zone = "中性区"
                rsi_emoji = "🟡"
            else:
                rsi_zone = "超卖区 ✅"
                rsi_emoji = "🟢"
            
            content += f"\n**RSI: {rsi_value:.2f} ({rsi_emoji} {rsi_zone})**"
        
        # 添加市场研判（RSI + BOLL综合分析）
        analysis_result = analyze_market(
            rsi=signal_data.get('rsi'),
            boll_up_diff_pct=signal_data.get('boll_up_diff_pct'),
            boll_middle_diff_pct=signal_data.get('boll_middle_diff_pct'),
            boll_down_diff_pct=signal_data.get('boll_down_diff_pct')
        )
        
        if analysis_result != "暂无":
            analysis_desc = get_analysis_description(analysis_result)
            content += f"\n**💡 研判: {analysis_result} - {analysis_desc}**"
        else:
            content += f"\n**💡 研判: 暂无。**"
        
        if reason:
            content += f"\n\n**原因**: {reason}"
        
        # 构建飞书消息体（使用交互式卡片格式）
        message = {
            "msg_type": "interactive",
            "card": {
                "config": {
                    "wide_screen_mode": True
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"{emoji} {title}"
                    },
                    "template": color
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
        
        return message
    
    def test_notification(self) -> bool:
        """
        发送测试通知
        
        Returns:
            bool: 是否发送成功
        """
        if not self.enabled:
            logger.warning("⚠️ 飞书通知未启用，无法发送测试消息")
            return False
        
        test_data = {
            'symbol': 'sh.513120',
            'name': '港股创新药ETF广发',
            'signal_type': 'BUY',
            'price': 1.281,
            'change_pct': 0.71,
            'reason': '测试通知：初始建仓',
            'target_shares': 14000,
            'avg_cost': 1.281,
            'boll_up_diff_pct': -5.56,
            'boll_middle_diff_pct': 4.22,
            'boll_down_diff_pct': 13.99,
            'rsi': 74.32
        }
        
        logger.info("🧪 发送飞书测试通知...")
        return self.send_signal_notification(test_data)
    
    def send_news_notification(self, news_data: Dict[str, Any]) -> bool:
        """
        发送股票资讯通知
        
        Args:
            news_data: 资讯数据字典，包含 stock_pool 和各股票的资讯列表
            
        Returns:
            bool: 是否发送成功
        """
        if not self.enabled:
            logger.warning("⚠️ 飞书通知未启用，无法发送资讯消息")
            return False
        
        try:
            # 构建消息内容
            message = self._build_news_message(news_data)
            
            # 发送请求
            headers = {'Content-Type': 'application/json'}
            response = requests.post(
                self.webhook_url,
                headers=headers,
                data=json.dumps(message, ensure_ascii=False).encode('utf-8'),
                timeout=10
            )
            
            # 检查响应
            if response.status_code == 200:
                result = response.json()
                if result.get('StatusCode') == 0 or result.get('code') == 0:
                    logger.success(f"📱 股票资讯飞书通知发送成功")
                    return True
                else:
                    error_code = result.get('code', 'unknown')
                    error_msg = result.get('msg', '未知错误')
                    logger.error(f"❌ 飞书API返回错误 (code: {error_code}): {error_msg}")
                    return False
            else:
                logger.error(f"❌ 飞书通知发送失败，HTTP状态码: {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error("❌ 飞书通知发送超时")
            return False
        except requests.exceptions.ConnectionError:
            logger.error("❌ 飞书通知连接失败，请检查网络和Webhook URL")
            return False
        except Exception as e:
            logger.error(f"❌ 飞书通知发送异常: {e}")
            return False
    
    def _build_news_message(self, news_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建股票资讯飞书消息体
        
        Args:
            news_data: 资讯数据字典
            
        Returns:
            Dict: 飞书消息体
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 构建消息头部
        content = f"**📊 股票资讯日报**\n"
        content += f"**时间**: {current_time}\n\n"
        
        stock_pool = news_data.get('stock_pool', [])
        total_news_count = 0
        
        # 遍历每只股票
        for stock_info in stock_pool:
            symbol = stock_info.get('code', '')
            name = stock_info.get('name', '')
            index = stock_info.get('index', '')  # 获取中文序号
            individual_news = stock_info.get('individual_news', [])
            financial_reports = stock_info.get('financial_reports', [])
            
            stock_total = len(individual_news) + len(financial_reports)
            total_news_count += stock_total
            
            # 如果该股票没有任何资讯，跳过
            if stock_total == 0:
                continue
            
            # 添加股票标题（带序号）
            content += f"**━━━━━━━━━━━━━━━**\n"
            if index:
                content += f"**🏢 {index}、{name} ({symbol})**\n"
            else:
                content += f"**🏢 {name} ({symbol})**\n"
            
            # 添加行情指标
            metrics = stock_info.get('metrics', {})
            daily_change = metrics.get('daily_change_pct')
            weekly_change = metrics.get('weekly_change_pct')
            monthly_change = metrics.get('monthly_change_pct')
            market_cap = metrics.get('circulating_market_cap')
            
            if any([daily_change is not None, weekly_change is not None, 
                   monthly_change is not None, market_cap is not None]):
                content += f"**📈 行情指标**: "
                indicators = []
                
                # 辅助函数：根据涨跌幅正负添加颜色
                def format_change(value, prefix):
                    if value is None:
                        return None
                    if value > 0:
                        # 红色（涨）
                        return f"<font color='red'>{prefix}{value:+.2f}%</font>"
                    elif value < 0:
                        # 绿色（跌）
                        return f"<font color='green'>{prefix}{value:+.2f}%</font>"
                    else:
                        # 零值，使用默认色
                        return f"{prefix}{value:+.2f}%"
                
                if daily_change is not None:
                    indicators.append(format_change(daily_change, "日"))
                if weekly_change is not None:
                    indicators.append(format_change(weekly_change, "周"))
                if monthly_change is not None:
                    indicators.append(format_change(monthly_change, "月"))
                if market_cap is not None:
                    indicators.append(f"市值{market_cap}亿")
                
                content += " | ".join(indicators) + "\n"
            
            # 添加多空信号
            trend_analysis = stock_info.get('trend_analysis') or {}
            if trend_analysis:
                trend_type = trend_analysis.get('trend', 'NEUTRAL')
                score = trend_analysis.get('score', 0)
                close_price = trend_analysis.get('close', 0)
                conclusion = trend_analysis.get('conclusion', '')
                previous_score = trend_analysis.get('previous_score')  # 获取前一日评分
                
                # 根据趋势类型选择emoji
                if trend_type in ['BULLISH', 'SLIGHTLY_BULLISH']:
                    trend_emoji = "🟢"
                elif trend_type in ['BEARISH', 'SLIGHTLY_BEARISH']:
                    trend_emoji = "🔴"
                else:
                    trend_emoji = "⚪"
                
                # 提取简洁的趋势描述（去掉emoji和括号内容）
                trend_desc_map = {
                    'BULLISH': '多头排列',
                    'SLIGHTLY_BULLISH': '偏多震荡',
                    'NEUTRAL': '中性观望',
                    'SLIGHTLY_BEARISH': '偏空震荡',
                    'BEARISH': '空头排列'
                }
                trend_desc = trend_desc_map.get(trend_type, '未知')
                
                # 格式化多空信号行（包含前一日评分对比）
                if close_price > 0:
                    content += f"**{trend_emoji} 多空信号**: {trend_desc}（{score:.1f}分），{close_price:.2f}元"
                else:
                    content += f"**{trend_emoji} 多空信号**: {trend_desc}（{score:.1f}分）"
                
                # 添加前一日评分对比
                if previous_score is not None:
                    score_change = score - previous_score
                    if score_change > 0:
                        change_icon = "📈"
                        change_color = "red"
                        change_text = f"↑+{score_change:.1f}"
                    elif score_change < 0:
                        change_icon = "📉"
                        change_color = "green"
                        change_text = f"↓{score_change:.1f}"
                    else:
                        change_icon = "➡️"
                        change_color = "gray"
                        change_text = "→持平"
                    
                    content += f" | {change_icon} 较昨日: <font color='{change_color}'>{change_text}</font>（昨{previous_score:.1f}分）"
                
                content += "\n"

            content += f"**━━━━━━━━━━━━━━━**\n\n"
            
            # 添加个股资讯（最多3条）
            if individual_news:
                display_count = len(individual_news)
                content += f"**📰 个股资讯 ({display_count}条):**\n"
                for i, news in enumerate(individual_news[:3], 1):  # 最多显示3条
                    title = news.get('title', '无标题')
                    pub_time = news.get('time', '')
                    url = news.get('url', '')
                    
                    # 截断过长的标题
                    if len(title) > 50:
                        title = title[:47] + "..."
                    
                    # 检查是否为当日资讯，添加NEW标签
                    new_tag = ""
                    if pub_time and pub_time[:10] == datetime.now().strftime('%Y-%m-%d'):
                        new_tag = " 🔥NEW"
                    
                    content += f"{i}. **{title}** | {pub_time}{new_tag}\n"
                    content += f"   🔗 [查看详情]({url})\n\n"
            else:
                content += f"**📰 个股资讯**: 暂无\n\n"
            
            # 添加公告（最多1条）
            if financial_reports:
                display_count = len(financial_reports)
                content += f"**📑 公告 ({display_count}条):**\n"
                for i, report in enumerate(financial_reports[:1], 1):  # 最多显示1条
                    title = report.get('title', '无标题')
                    pub_time = report.get('time', '')
                    url = report.get('url', '')
                    
                    # 只保留日期部分（YYYY-MM-DD），去掉时间
                    if pub_time and len(pub_time) >= 10:
                        pub_time = pub_time[:10]
                    
                    # 截断过长的标题
                    if len(title) > 60:
                        title = title[:57] + "..."
                    
                    # 检查是否为当日公告，添加NEW标签
                    new_tag = ""
                    if pub_time == datetime.now().strftime('%Y-%m-%d'):
                        new_tag = " 🔥NEW"
                    
                    content += f"{i}. **{title}** | {pub_time}{new_tag}\n"
                    content += f"   🔗 [查看详情]({url})\n\n"
            else:
                content += f"**📑 公告**: 暂无\n\n"

            content += "\n"
        
        # 添加汇总信息
        content += f"**━━━━━━━━━━━━━━━**\n"
        content += f"**📈 汇总**: 共监控 {len(stock_pool)} 只股票，获取 {total_news_count} 条资讯\n"
        
        # 构建飞书消息体（使用交互式卡片格式）
        message = {
            "msg_type": "interactive",
            "card": {
                "config": {
                    "wide_screen_mode": True
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": "📊 股票资讯日报"
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
                                "content": f"股票资讯监控系统 | {current_time}"
                            }
                        ]
                    }
                ]
            }
        }
        
        return message


# 全局通知器实例
_notifier = None


def get_feishu_notifier() -> FeishuNotifier:
    """获取飞书通知器单例"""
    global _notifier
    if _notifier is None:
        _notifier = FeishuNotifier()
    return _notifier


def send_signal_notification(signal_data: Dict[str, Any]) -> bool:
    """
    发送信号通知（便捷函数）
    
    Args:
        signal_data: 信号数据字典
        
    Returns:
        bool: 是否发送成功
    """
    notifier = get_feishu_notifier()
    return notifier.send_signal_notification(signal_data)


def test_feishu_notification() -> bool:
    """
    测试飞书通知（便捷函数）
    
    Returns:
        bool: 是否发送成功
    """
    notifier = get_feishu_notifier()
    return notifier.test_notification()


def send_news_notification(news_data: Dict[str, Any]) -> bool:
    """
    发送股票资讯通知（便捷函数）
    
    Args:
        news_data: 资讯数据字典
        
    Returns:
        bool: 是否发送成功
    """
    notifier = get_feishu_notifier()
    return notifier.send_news_notification(news_data)