# -*- coding: utf-8 -*-
"""市场研判模块 - 基于RSI和BOLL指标的综合判断"""
from typing import Optional, Tuple
from loguru import logger


class MarketAnalyzer:
    """市场分析器 - 综合RSI和BOLL指标进行研判"""
    
    # RSI阈值配置
    RSI_OVERBOUGHT = 70  # 超买阈值
    RSI_OVERSOLD = 30    # 超卖阈值
    
    # BOLL轨道接近阈值（百分比）
    BOLL_CLOSE_THRESHOLD = 3.0  # 距离轨道3%以内视为"接近"
    
    @staticmethod
    def analyze_market_condition(
        rsi: Optional[float],
        boll_up_diff_pct: Optional[float],
        boll_middle_diff_pct: Optional[float],
        boll_down_diff_pct: Optional[float]
    ) -> str:
        """
        综合分析市场状态
        
        Args:
            rsi: RSI指标值
            boll_up_diff_pct: 价格与BOLL上轨的价差百分比
            boll_middle_diff_pct: 价格与BOLL中轨的价差百分比
            boll_down_diff_pct: 价格与BOLL下轨的价差百分比
            
        Returns:
            str: 研判结果 ("回调", "反弹", "震荡", "暂无")
        """
        # 如果数据不完整，返回"暂无"
        if rsi is None:
            return "暂无"
        
        if any([boll_up_diff_pct is None, boll_middle_diff_pct is None, boll_down_diff_pct is None]):
            return "暂无"
        
        # 判断RSI状态
        is_overbought = rsi > MarketAnalyzer.RSI_OVERBOUGHT
        is_oversold = rsi < MarketAnalyzer.RSI_OVERSOLD
        
        # 判断是否接近BOLL轨道（使用绝对值）
        near_upper_track = abs(boll_up_diff_pct) <= MarketAnalyzer.BOLL_CLOSE_THRESHOLD
        near_lower_track = abs(boll_down_diff_pct) <= MarketAnalyzer.BOLL_CLOSE_THRESHOLD
        
        # 规则1: RSI超买 + 价格接近BOLL上轨 → 回调信号
        if is_overbought and near_upper_track:
            logger.info(f"📊 市场研判: 回调 (RSI={rsi:.2f} 超买, 距上轨{boll_up_diff_pct:+.2f}%)")
            return "回调"
        
        # 规则2: RSI超卖 + 价格接近BOLL下轨 → 反弹机会
        if is_oversold and near_lower_track:
            logger.info(f"📊 市场研判: 反弹 (RSI={rsi:.2f} 超卖, 距下轨{boll_down_diff_pct:+.2f}%)")
            return "反弹"
        
        # 规则3: RSI中性 + 价格在中轨附近 → 震荡行情
        # 中轨附近的定义：距离中轨在BOLL_CLOSE_THRESHOLD范围内
        near_middle_track = abs(boll_middle_diff_pct) <= MarketAnalyzer.BOLL_CLOSE_THRESHOLD
        if not is_overbought and not is_oversold and near_middle_track:
            logger.info(f"📊 市场研判: 震荡 (RSI={rsi:.2f} 中性, 距中轨{boll_middle_diff_pct:+.2f}%)")
            return "震荡"
        
        # 规则4: 其他情况
        return "暂无"
    
    @staticmethod
    def get_analysis_description(analysis_result: str) -> str:
        """
        获取研判结果的详细说明
        
        Args:
            analysis_result: 研判结果
            
        Returns:
            str: 详细说明文本
        """
        descriptions = {
            "回调": "RSI超买且价格接近BOLL上轨，存在回调风险 ⚠️",
            "反弹": "RSI超卖且价格接近BOLL下轨，存在反弹机会 ✅",
            "震荡": "RSI中性且价格在BOLL中轨附近，处于震荡阶段 🔄",
            "暂无": "当前市场状态不明确，建议继续观望 ⏸️"
        }
        return descriptions.get(analysis_result, "暂无")


# 全局分析器实例
_analyzer = None


def get_market_analyzer() -> MarketAnalyzer:
    """获取市场分析器单例"""
    global _analyzer
    if _analyzer is None:
        _analyzer = MarketAnalyzer()
    return _analyzer


def analyze_market(
    rsi: Optional[float],
    boll_up_diff_pct: Optional[float],
    boll_middle_diff_pct: Optional[float],
    boll_down_diff_pct: Optional[float]
) -> str:
    """
    便捷函数：分析市场状态
    
    Args:
        rsi: RSI指标值
        boll_up_diff_pct: 价格与BOLL上轨的价差百分比
        boll_middle_diff_pct: 价格与BOLL中轨的价差百分比
        boll_down_diff_pct: 价格与BOLL下轨的价差百分比
        
    Returns:
        str: 研判结果 ("回调", "反弹", "震荡", "暂无")
    """
    analyzer = get_market_analyzer()
    return analyzer.analyze_market_condition(rsi, boll_up_diff_pct, boll_middle_diff_pct, boll_down_diff_pct)


def get_analysis_description(analysis_result: str) -> str:
    """
    便捷函数：获取研判结果的详细说明
    
    Args:
        analysis_result: 研判结果
        
    Returns:
        str: 详细说明文本
    """
    analyzer = get_market_analyzer()
    return analyzer.get_analysis_description(analysis_result)
