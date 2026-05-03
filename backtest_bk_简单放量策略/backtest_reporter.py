# -*- coding: utf-8 -*-
"""
回测报告生成器

功能：
1. 计算并展示所有统计指标
2. 生成可视化图表（累计收益曲线、月度收益柱状图）
3. 输出文本报告和HTML报告
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from loguru import logger

# 设置中文字体
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backtest.backtest_engine import TradeRecord


class BacktestReporter:
    """回测报告生成器"""
    
    def __init__(self, trades: List[TradeRecord], config: dict, output_dir: str, metrics: dict = None):
        """
        初始化报告生成器
        
        Args:
            trades: 交易记录列表
            config: 回测配置
            output_dir: 输出目录
            metrics: 预计算的指标字典（可选，如果不提供则自行计算）
        """
        self.trades = trades
        self.config = config
        self.output_dir = Path(output_dir)
        
        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 计算或使用预计算的指标
        if metrics is not None:
            self.metrics = metrics
            logger.info("[INFO] 使用预计算的指标数据")
        else:
            logger.warning("[WARN] 未提供预计算指标，将自行计算（可能与引擎计算结果不一致）")
            self.metrics = self._calculate_metrics()
    
    def _calculate_metrics(self) -> dict:
        """计算统计指标"""
        if not self.trades:
            return {}
        
        metrics = {}
        
        # 提取收益率数组
        returns = np.array([trade.return_pct for trade in self.trades])
        
        # 1. 基础指标
        metrics['total_trades'] = len(self.trades)
        metrics['winning_trades'] = int(np.sum(returns > 0))
        metrics['losing_trades'] = int(np.sum(returns < 0))
        metrics['win_rate'] = metrics['winning_trades'] / metrics['total_trades'] * 100
        
        # 总收益率
        cumulative_return = np.prod([1 + r/100 for r in returns]) - 1
        metrics['total_return'] = cumulative_return * 100
        
        # 年化收益率
        start_date = self.config['start_date']
        end_date = self.config['end_date']
        days_span = (end_date - start_date).days
        years = days_span / 365.25
        if years > 0:
            metrics['annualized_return'] = ((1 + cumulative_return) ** (1/years) - 1) * 100
        else:
            metrics['annualized_return'] = 0
        
        # 2. 进阶指标
        metrics['avg_return'] = np.mean(returns)
        metrics['max_single_return'] = np.max(returns)
        metrics['min_single_return'] = np.min(returns)
        
        # 盈亏比
        avg_win = np.mean(returns[returns > 0]) if np.any(returns > 0) else 0
        avg_loss = abs(np.mean(returns[returns < 0])) if np.any(returns < 0) else 1
        metrics['profit_loss_ratio'] = avg_win / avg_loss if avg_loss > 0 else 0
        
        # 夏普比率
        risk_free_rate = 3.0
        excess_returns = returns - risk_free_rate / 252
        if len(excess_returns) > 1 and np.std(excess_returns) > 0:
            metrics['sharpe_ratio'] = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
        else:
            metrics['sharpe_ratio'] = 0
        
        # 最大回撤
        cumulative_returns = np.cumprod([1 + r/100 for r in returns])
        peak = np.maximum.accumulate(cumulative_returns)
        drawdown = (cumulative_returns - peak) / peak
        metrics['max_drawdown'] = np.min(drawdown) * 100
        
        # 3. 基准对比（从trades中推断）
        # 这里简化处理，实际应该从引擎传入
        metrics['benchmark_total_return'] = None
        metrics['excess_return'] = None
        
        return metrics
    
    def generate_full_report(self):
        """生成完整报告"""
        logger.info("\n" + "=" * 80)
        logger.info("📈 选股策略回测报告")
        logger.info("=" * 80)
        
        # 1. 打印文本报告
        self._print_text_report()
        
        # 2. 生成可视化图表
        self._generate_charts()
        
        # 3. 保存详细交易记录
        self._save_trade_details()
        
        logger.info(f"\n✅ 报告已保存至: {self.output_dir}")
    
    def _print_text_report(self):
        """打印文本报告"""
        if not self.metrics:
            logger.warning("[WARN] 没有数据可报告")
            return
        
        m = self.metrics
        start_date = self.config['start_date'].strftime('%Y-%m-%d')
        end_date = self.config['end_date'].strftime('%Y-%m-%d')
        
        print(f"\n{'='*80}")
        print(f"📊 回测总结报告")
        print(f"{'='*80}")
        print(f"回测周期: {start_date} 至 {end_date}")
        print(f"交易天数: {(self.config['end_date'] - self.config['start_date']).days} 天")
        print(f"放量周期: {self.config.get('volume_period', 5)} 天")
        print(f"持仓天数: {self.config.get('hold_days', 3)} 天")
        
        # ========== 策略与基准对比（核心指标）==========
        print(f"\n{'='*80}")
        print(f"💰 收益对比分析")
        print(f"{'='*80}")
        
        # 策略收益率
        print(f"\n【策略表现】")
        print(f"  总收益率:      {m['total_return']:+.2f}%")
        print(f"  年化收益率:    {m['annualized_return']:+.2f}%")
        
        # ========== 新增：资金利用率诊断 ==========
        if 'capital_utilization_rate' in m:
            print(f"\n【资金使用效率】")
            print(f"  总体资金利用率: {m['capital_utilization_rate']:.1f}%")
            print(f"  累计闲置资金:   {m['total_idle_capital']:,.2f} 元")
            print(f"  跳过股票数:     {m['total_skipped_stocks']} 只 (因不足100股)")
            
            # 如果资金利用率低，给出警告和建议
            if m['capital_utilization_rate'] < 80:
                print(f"\n  ⚠️  警告：资金利用率较低，可能原因：")
                print(f"     1. 高价股比例过高（导致无法买入100股整数倍）")
                print(f"     2. 每次选股数量过多（单只股票分配资金过少）")
                print(f"     3. 初始资金相对股价偏低")
                print(f"\n  💡 建议：")
                print(f"     - 过滤掉单价过高的股票（如 > 200元）")
                print(f"     - 减少每次选股的股票数量")
                print(f"     - 增加初始回测资金")
        
        # 沪深300基准收益率
        if m['benchmark_total_return'] is not None:
            print(f"\n【沪深300基准】")
            print(f"  区间收益率:    {m['benchmark_total_return']:+.2f}%")
            if m['benchmark_annualized_return'] is not None:
                print(f"  年化收益率:    {m['benchmark_annualized_return']:+.2f}%")
            
            # 超额收益对比
            excess = m['excess_return']
            print(f"\n【对比结果】")
            if excess >= 0:
                print(f"  ✅ 跑赢沪深300:  {excess:+.2f}%")
            else:
                print(f"  ❌ 跑输沪深300:  {excess:+.2f}%")
            
            # 可视化对比
            print(f"\n  收益率对比图:")
            strategy_bar = "█" * int(abs(m['total_return']) / 2)
            benchmark_bar = "█" * int(abs(m['benchmark_total_return']) / 2)
            
            if m['total_return'] >= 0:
                print(f"  策略:   [{strategy_bar}] {m['total_return']:+.2f}%")
            else:
                print(f"  策略:   [-{strategy_bar}] {m['total_return']:+.2f}%")
            
            if m['benchmark_total_return'] >= 0:
                print(f"  沪深300:[{benchmark_bar}] {m['benchmark_total_return']:+.2f}%")
            else:
                print(f"  沪深300:[-{benchmark_bar}] {m['benchmark_total_return']:+.2f}%")
        else:
            print(f"\n⚠️  未获取到沪深300基准数据，无法进行对比")
        
        # ========== 风险指标 ==========
        print(f"\n{'='*80}")
        print(f"⚠️  风险指标")
        print(f"{'='*80}")
        print(f"胜率:          {m['win_rate']:.1f}%  ({m['winning_trades']}/{m['total_trades']} 笔交易盈利)")
        print(f"夏普比率:      {m['sharpe_ratio']:.2f}")
        print(f"最大回撤:      {m['max_drawdown']:.1f}%")
        print(f"盈亏比:        {m['profit_loss_ratio']:.1f}:1")
        
        # ========== 交易统计 ==========
        print(f"\n{'='*80}")
        print(f"📈 交易统计")
        print(f"{'='*80}")
        print(f"总交易次数:    {m['total_trades']} 笔")
        print(f"平均收益:      {m['avg_return']:+.2f}%")
        print(f"最大单笔收益:  {m['max_single_return']:+.2f}%")
        print(f"最大单笔亏损:  {m['min_single_return']:+.2f}%")
        
        # 找出最佳和最差交易
        if self.trades:
            best_trade = max(self.trades, key=lambda t: t.return_pct)
            worst_trade = min(self.trades, key=lambda t: t.return_pct)
            print(f"\n最佳交易: {best_trade.stock_name}({best_trade.stock_code}) {best_trade.return_pct:+.2f}%")
            print(f"最差交易: {worst_trade.stock_name}({worst_trade.stock_code}) {worst_trade.return_pct:+.2f}%")
        
        # ========== 新增：交易周期资金明细表 ==========
        if 'cycle_details' in m and len(m['cycle_details']) > 0:
            print(f"\n{'='*80}")
            print(f"📋 交易周期资金明细（前10个周期）")
            print(f"{'='*80}")
            print(f"{'周期':<6} {'买入日期':<12} {'股票数':<8} {'期初资金':<14} {'理论投入':<14} {'实际投入':<14} {'利用率':<8} {'跳过':<6}")
            print(f"{'-'*80}")
            
            for i, cycle in enumerate(m['cycle_details'][:10]):  # 只显示前10个周期
                buy_date_str = cycle['buy_date'].strftime('%Y-%m-%d')
                
                if cycle['theoretical_investment'] > 0:
                    utilization = cycle['actual_investment'] / cycle['theoretical_investment'] * 100
                else:
                    utilization = 0
                
                print(
                    f"{i+1:<6} "
                    f"{buy_date_str:<12} "
                    f"{cycle['num_stocks']:<8} "
                    f"{cycle['initial_capital']:<14,.0f} "
                    f"{cycle['theoretical_investment']:<14,.0f} "
                    f"{cycle['actual_investment']:<14,.0f} "
                    f"{utilization:<7.1f}% "
                    f"{cycle['skipped_count']:<6}"
                )
            
            if len(m['cycle_details']) > 10:
                print(f"... 还有 {len(m['cycle_details']) - 10} 个周期")
            
            print(f"{'-'*80}")
            print(f"说明：")
            print(f"  - 理论投入：按期初资金平均分配到每只股票的金额总和")
            print(f"  - 实际投入：考虑100股限制后实际买入的金额总和")
            print(f"  - 利用率 = 实际投入 / 理论投入 × 100%")
            print(f"  - 跳过：因股价过高导致不足100股而无法买入的股票数量")
    
    def _generate_charts(self):
        """生成可视化图表"""
        if not self.trades:
            logger.warning("[WARN] 没有交易数据，跳过图表生成")
            return
        
        try:
            # 1. 累计收益曲线对比图
            self._plot_cumulative_returns()
            
            # 2. 月度收益柱状图
            self._plot_monthly_returns()
            
            logger.info("[OK] 图表生成完成")
            
        except Exception as e:
            logger.error(f"[ERROR] 生成图表失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _plot_cumulative_returns(self):
        """绘制累计收益曲线对比图"""
        fig, ax = plt.subplots(figsize=(14, 7))
        
        # 按日期排序交易
        sorted_trades = sorted(self.trades, key=lambda t: t.sell_date)
        
        # 计算累计收益
        dates = []
        cumulative_returns = [1.0]  # 初始值为1
        
        for trade in sorted_trades:
            dates.append(trade.sell_date)
            last_return = cumulative_returns[-1]
            new_return = last_return * (1 + trade.return_pct / 100)
            cumulative_returns.append(new_return)
        
        # 转换为百分比
        cumulative_returns_pct = [(r - 1) * 100 for r in cumulative_returns[1:]]
        
        # 绘制策略收益曲线
        ax.plot(dates, cumulative_returns_pct, label='策略收益', linewidth=2, color='#2E86AB')
        
        # 如果有基准数据，绘制基准曲线（这里简化处理）
        # 实际应该从引擎传入基准数据
        
        # 添加零线
        ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.5)
        
        # 设置标题和标签
        ax.set_title('累计收益曲线对比', fontsize=16, fontweight='bold')
        ax.set_xlabel('日期', fontsize=12)
        ax.set_ylabel('累计收益率 (%)', fontsize=12)
        ax.legend(loc='best', fontsize=11)
        ax.grid(True, alpha=0.3)
        
        # 格式化x轴日期
        fig.autofmt_xdate()
        
        # 保存图表
        chart_path = self.output_dir / f"backtest_cumulative_returns_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(chart_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"[CHART] 累计收益曲线已保存: {chart_path}")
    
    def _plot_monthly_returns(self):
        """绘制月度收益柱状图"""
        fig, ax = plt.subplots(figsize=(14, 7))
        
        # 按月份分组计算收益
        monthly_data = {}
        
        for trade in self.trades:
            month_key = trade.sell_date.strftime('%Y-%m')
            if month_key not in monthly_data:
                monthly_data[month_key] = []
            monthly_data[month_key].append(trade.return_pct)
        
        # 计算每月平均收益
        months = sorted(monthly_data.keys())
        avg_returns = [np.mean(monthly_data[m]) for m in months]
        
        # 创建柱状图
        colors = ['#A23B72' if r < 0 else '#F18F01' for r in avg_returns]
        bars = ax.bar(range(len(months)), avg_returns, color=colors, alpha=0.7, edgecolor='black')
        
        # 添加数值标签
        for i, (bar, val) in enumerate(zip(bars, avg_returns)):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{val:.1f}%',
                   ha='center', va='bottom' if val >= 0 else 'top',
                   fontsize=9)
        
        # 设置标题和标签
        ax.set_title('月度收益分布', fontsize=16, fontweight='bold')
        ax.set_xlabel('月份', fontsize=12)
        ax.set_ylabel('平均收益率 (%)', fontsize=12)
        ax.set_xticks(range(len(months)))
        ax.set_xticklabels(months, rotation=45, ha='right')
        ax.axhline(y=0, color='gray', linestyle='-', linewidth=0.5)
        ax.grid(True, alpha=0.3, axis='y')
        
        # 保存图表
        chart_path = self.output_dir / f"backtest_monthly_returns_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(chart_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"[CHART] 月度收益柱状图已保存: {chart_path}")
    
    def _save_trade_details(self):
        """保存详细交易记录到CSV文件"""
        if not self.trades:
            return
        
        # 转换为DataFrame
        trade_dicts = [trade.to_dict() for trade in self.trades]
        df = pd.DataFrame(trade_dicts)
        
        # 按卖出日期排序
        df = df.sort_values('sell_date')
        
        # 保存为CSV
        csv_path = self.output_dir / f"backtest_trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        
        logger.info(f"[CSV] 交易明细已保存: {csv_path}")


def main():
    """测试报告生成器"""
    # 这里可以添加测试代码
    pass


if __name__ == "__main__":
    main()
