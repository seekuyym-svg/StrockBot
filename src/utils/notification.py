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
    
    def should_notify(self, signal_type: str) -> bool:
        """
        判断是否应该发送通知
        
        Args:
            signal_type: 信号类型（BUY/SELL/ADD/STOP/WAIT）
            
        Returns:
            bool: 是否应该发送通知
        """
        if not self.enabled:
            return False
        
        return signal_type in self.notify_signals
    
    def send_signal_notification(self, signal_data: Dict[str, Any]) -> bool:
        """
        发送交易信号通知
        
        Args:
            signal_data: 信号数据字典
            
        Returns:
            bool: 是否发送成功
        """
        if not self.enabled:
            return False
        
        symbol = signal_data.get('symbol', '')
        signal_type = signal_data.get('signal_type', '')
        symbol_signal_type = f"{symbol}_{signal_type}"
        
        # 检查是否需要通知该类型的信号
        if not self.should_notify(signal_type):
            logger.debug(f"信号类型 {signal_type} 不需要通知")
            return False
        
        # 检查频率控制
        current_time = datetime.now().timestamp()
        last_send_time = self.last_send_time.get(symbol_signal_type, 0)
        time_since_last_send = current_time - last_send_time
        
        if time_since_last_send < self.min_interval_seconds:
            remaining_time = self.min_interval_seconds - time_since_last_send
            logger.warning(f"⚠️ 飞书通知频率限制：{symbol} {signal_type} 距上次发送仅 {time_since_last_send:.0f}秒，还需等待 {remaining_time:.0f}秒")
            return False
        
        try:
            # 构建消息内容
            message = self._build_message(signal_data)
            
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
                    logger.success(f"📱 飞书通知发送成功: {signal_data.get('symbol')} - {signal_type}")
                    self.last_send_time[symbol_signal_type] = current_time
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
