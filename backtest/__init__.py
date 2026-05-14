# -*- coding: utf-8 -*-
"""
选股策略回测工具包

提供对 select_daysvol.py 持续放量选股策略的历史回测功能。

主要模块:
    - backtest_engine: 回测引擎核心
    - backtest_reporter: 报告生成器
    - run_backtest: 主入口脚本
    - test_backtest: 快速测试脚本

使用方法:
    python backtest/run_backtest.py --start-date 2024-01-01 --end-date 2026-01-01
"""

from .backtest_engine import BacktestEngine, TradeRecord
from .backtest_reporter import BacktestReporter

__all__ = ['BacktestEngine', 'TradeRecord', 'BacktestReporter']
