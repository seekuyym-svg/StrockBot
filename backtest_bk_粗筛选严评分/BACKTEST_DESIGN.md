# 选股策略回测方案设计文档

## 📋 需求概述

对 `select_daysvol.py` 的持续放量选股策略进行历史回测，验证其有效性。

**核心要素：**
- **回测周期**：过去2年（或可配置）
- **选股逻辑**：基于本地通达信数据的持续放量策略（连续N天成交量递增）
- **持仓规则**：选出后持有3天卖出
- **对比基准**：沪深300指数同期收益率
- **白名单机制**：从 `data/whitelist_*.txt` 读取（取最近的文件）

---

## 🎯 方案对比

### 方案一：简单回测脚本（入门级）

#### 特点
- 独立的Python脚本，不依赖复杂框架
- 直接复用现有代码中的函数（`check_continuous_volume`等）
- 逐日模拟选股过程，记录每只股票的买入价、卖出价
- 输出简单的统计报表和图表

#### 优点
- ✅ 实现简单，易于理解和调试
- ✅ 完全控制回测逻辑
- ✅ 可以快速验证想法

#### 缺点
- ❌ 需要手动处理数据对齐、停牌等问题
- ❌ 性能可能较慢（逐日遍历）
- ❌ 图表功能有限

#### 适用场景
快速验证策略有效性，学习回测原理

#### 技术实现要点
```python
# 伪代码示例
for each trading day in backtest_period:
    # 1. 读取白名单
    whitelist = load_whitelist()
    
    # 2. 检查每只股票是否满足放量条件
    selected_stocks = []
    for stock in whitelist:
        if check_continuous_volume(reader, stock, period=5):
            selected_stocks.append(stock)
    
    # 3. 记录买入信号（次日开盘价）
    for stock in selected_stocks:
        buy_price = get_next_day_open(stock)
        trades.append({
            'stock': stock,
            'buy_date': next_day,
            'buy_price': buy_price,
            'sell_date': next_day + 3 days,
            'status': 'pending'
        })
    
    # 4. 检查是否有到期的卖出信号
    for trade in trades:
        if trade['status'] == 'pending' and current_date == trade['sell_date']:
            sell_price = get_close_price(trade['stock'], current_date)
            trade['sell_price'] = sell_price
            trade['return'] = (sell_price - trade['buy_price']) / trade['buy_price']
            trade['status'] = 'completed'
```

---

### 方案二：基于Backtrader框架（专业级）

#### 特点
- 使用成熟的量化回测框架 Backtrader
- 将选股逻辑封装为自定义策略类
- 自动处理资金管理、滑点、手续费等
- 丰富的性能指标和可视化

#### 优点
- ✅ 专业可靠，业界标准
- ✅ 自动处理复权、分红等复杂问题
- ✅ 支持多策略对比、参数优化
- ✅ 强大的统计分析能力

#### 缺点
- ❌ 学习曲线较陡
- ❌ 需要适配现有代码到Backtrader的数据格式
- ❌ 额外依赖 `backtrader` 库

#### 适用场景
长期策略研究，需要精确的回测结果

#### 技术实现要点
```python
import backtrader as bt

class VolumeStrategy(bt.Strategy):
    params = (
        ('volume_period', 5),
        ('hold_days', 3),
    )
    
    def __init__(self):
        self.order_history = []
        
    def next(self):
        # 获取当前日期
        current_date = self.datas[0].datetime.date(0)
        
        # 检查选股条件
        for data in self.datas:
            if self.check_volume_condition(data):
                # 买入信号
                self.buy(data=data)
                
    def check_volume_condition(self, data):
        # 检查连续N天成交量递增
        volumes = [data.volume[-i] for i in range(1, self.params.volume_period + 2)]
        return all(volumes[i] > volumes[i+1] for i in range(len(volumes)-1))
    
    def notify_order(self, order):
        # 记录订单状态
        if order.status in [order.Completed]:
            self.order_history.append({
                'date': order.executed.dt,
                'price': order.executed.price,
                'size': order.executed.size
            })

# 运行回测
cerebro = bt.Cerebro()
cerebro.addstrategy(VolumeStrategy)
cerebro.adddata(data_feed)
cerebro.run()
cerebro.plot()
```

---

### 方案三：向量化回测（高性能）

#### 特点
- 使用 Pandas + NumPy 进行向量化计算
- 一次性加载所有股票的历史数据
- 通过矩阵运算批量判断每日的选股条件
- 并行化处理提升速度

#### 优点
- ✅ 性能极高（比逐日循环快10-100倍）
- ✅ 代码简洁优雅
- ✅ 适合大规模数据回测

#### 缺点
- ❌ 内存占用大（需加载所有股票历史数据）
- ❌ 逻辑复杂度较高
- ❌ 难以处理复杂的交易规则（如停牌跳过）

#### 适用场景
大数据量回测，追求极致性能

#### 技术实现要点
```python
import pandas as pd
import numpy as np

# 1. 加载所有股票的历史数据到DataFrame
all_data = load_all_stock_data(whitelist, start_date, end_date)

# 2. 计算每只股票的成交量变化
for stock in whitelist:
    df = all_data[stock]
    df['volume_change'] = df['volume'].pct_change()
    df['is_increasing'] = df['volume'] > df['volume'].shift(1)
    
    # 标记连续N天放量的日期
    df['signal'] = df['is_increasing'].rolling(window=5).sum() == 5

# 3. 向量化计算收益
signals = df[df['signal'] == True]
for signal_date in signals.index:
    buy_price = get_next_day_open(signal_date)
    sell_price = get_close_price(signal_date + 3 days)
    returns.append((sell_price - buy_price) / buy_price)

# 4. 批量统计
total_return = np.prod(1 + np.array(returns)) - 1
win_rate = np.mean(np.array(returns) > 0)
```

---

### 方案四：混合方案（平衡型）⭐ **推荐方案**

#### 特点
- 结合方案一的简单性和方案三的性能
- 按月/季度分批回测，避免内存爆炸
- 复用现有代码的核心函数
- 提供清晰的报告输出

#### 优点
- ✅ 平衡性能和复杂度
- ✅ 易于扩展（可调整持仓天数、加仓策略等）
- ✅ 充分利用现有代码
- ✅ 输出直观的报告

#### 缺点
- ⚠️ 中等复杂度，需要合理设计数据结构

#### 适用场景
**本项目采用此方案**，兼顾开发效率和回测准确性

#### 核心流程
```
1. 确定回测时间范围（如 2024-01-01 至 2026-01-01）
2. 按交易日遍历：
   a. 读取固定白名单（whitelist_20260424.txt）
   b. 对每只股票检查是否满足"连续5天放量"条件
   c. 记录选中的股票及买入价格（次日开盘价）
   d. 3个交易日后以收盘价卖出，计算收益
   e. 遇到停牌则跳过该股票
3. 同时记录沪深300同期涨跌幅
4. 生成对比报告：
   - 总收益率对比
   - 年化收益率
   - 最大回撤
   - 胜率（盈利交易占比）
   - 夏普比率
   - 盈亏比
   - 累计收益曲线对比图
   - 月度收益柱状图
```

#### 技术实现架构
```python
class BacktestEngine:
    def __init__(self, config):
        self.config = config
        self.trades = []  # 交易记录
        self.daily_returns = []  # 每日收益
        self.benchmark_returns = []  # 基准收益
        
    def run_backtest(self):
        """执行回测"""
        # 1. 初始化
        self.load_whitelist()
        self.load_benchmark_data()
        
        # 2. 逐日回测
        for date in self.trading_days:
            selected_stocks = self.select_stocks(date)
            self.execute_trades(date, selected_stocks)
            self.check_exit_signals(date)
            
        # 3. 计算统计指标
        self.calculate_metrics()
        
        # 4. 生成报告
        self.generate_report()
        
    def select_stocks(self, date):
        """选股逻辑"""
        selected = []
        for stock in self.whitelist:
            if self.check_volume_condition(stock, date):
                selected.append(stock)
        return selected
        
    def execute_trades(self, date, stocks):
        """执行买入交易"""
        for stock in stocks:
            buy_price = self.get_next_open_price(stock, date)
            if buy_price and not self.is_suspended(stock, date + 1):
                self.trades.append({
                    'stock': stock,
                    'buy_date': date + timedelta(days=1),
                    'buy_price': buy_price,
                    'sell_date': date + timedelta(days=4),  # 3个交易日后
                    'status': 'pending'
                })
                
    def calculate_metrics(self):
        """计算统计指标"""
        # 总收益率
        self.total_return = self.calculate_total_return()
        
        # 年化收益率
        self.annualized_return = self.calculate_annualized_return()
        
        # 胜率
        self.win_rate = self.calculate_win_rate()
        
        # 夏普比率
        self.sharpe_ratio = self.calculate_sharpe_ratio()
        
        # 最大回撤
        self.max_drawdown = self.calculate_max_drawdown()
        
        # 盈亏比
        self.profit_loss_ratio = self.calculate_profit_loss_ratio()
```

---

## 🔧 关键技术问题与解决方案

### 1. 数据源确认

| 问题 | 答案 |
|------|------|
| 本地通达信数据是否覆盖了过去2年的完整历史？ | ✅ 是的 |
| 是否需要复权处理？ | ✅ 前复权（qfq） |
| 沪深300数据从哪里获取？ | akshare 或腾讯财经API |

### 2. 白名单时间匹配

| 问题 | 答案 |
|------|------|
| 白名单文件命名格式 | `whitelist_YYYYMMDD.txt`（如 `whitelist_20260424.txt`） |
| 回测时如何匹配日期？ | **选项B**：只用一个固定的白名单（最近的） |
| 实现方式 | 直接读取 `data/whitelist_20260424.txt` |

### 3. 交易细节

| 问题 | 答案 |
|------|------|
| 买入时机 | **次日开盘价** |
| 卖出时机 | **3个交易日后的收盘价** |
| 是否考虑手续费？ | ❌ 不考虑 |
| 遇到停牌如何处理？ | **跳过该股票**（不执行交易） |

### 4. 输出形式

#### 基础统计指标
- ✅ 总收益率
- ✅ 年化收益率
- ✅ 胜率（盈利交易占比）

#### 进阶统计指标
- ✅ 夏普比率
- ✅ 最大回撤
- ✅ 盈亏比

#### 可视化图表
- ✅ 累计收益曲线对比图（策略收益 vs 沪深300）
- ✅ 月度收益柱状图

---

## 📊 预期输出示例

### 1. 控制台输出
```
================================================================================
📈 选股策略回测报告
================================================================================
回测周期: 2024-01-01 至 2026-01-01
交易天数: 480 天
白名单股票数: 150 只

【策略表现】
总收益率:      +45.23%
年化收益率:    +20.15%
胜率:          62.5%  (125/200 笔交易盈利)
夏普比率:      1.35
最大回撤:      -12.8%
盈亏比:        2.1:1

【基准对比 - 沪深300】
总收益率:      +18.50%
年化收益率:    +8.90%

【超额收益】
相对沪深300:   +26.73%
年化超额收益:  +11.25%

【交易统计】
总交易次数:    200 笔
平均持仓天数:  3.0 天
单笔平均收益:  +0.23%
最大单笔收益:  +8.5%  (000001)
最大单笔亏损:  -5.2%  (600519)

✅ 回测完成！报告已保存至: data/backtest_report_20260425.html
```

### 2. 可视化图表
- **累计收益曲线对比图**：展示策略与沪深300的收益走势对比
- **月度收益柱状图**：展示每个月的收益分布情况

---

## 🚀 实施计划

### 第一阶段：核心回测引擎（预计1-2小时）
1. 创建 `local/backtest_engine.py` 文件
2. 实现基本的回测逻辑框架
3. 集成现有的 `check_continuous_volume` 和 `load_whitelist` 函数
4. 实现交易记录和收益计算

### 第二阶段：数据统计与报告（预计1小时）
1. 实现统计指标计算函数
2. 生成文本报告
3. 保存到文件

### 第三阶段：可视化输出（预计1小时）
1. 使用 matplotlib 绘制累计收益曲线
2. 绘制月度收益柱状图
3. 保存图表为图片文件

### 第四阶段：测试与优化（预计30分钟）
1. 小范围测试（1个月数据）
2. 验证数据准确性
3. 性能优化

---

## 📝 注意事项

1. **数据一致性**：确保所有数据使用前复权，避免价格跳空
2. **停牌处理**：在买入和卖出时都需要检查停牌状态
3. **交易日计算**：使用交易日历而非自然日计算持仓天数
4. **内存管理**：分批加载数据，避免一次性加载过多
5. **错误处理**：对数据缺失、API失败等情况做好容错

---

## 🎯 最终选择

**用户选择：方案四（混合方案）**

理由：
- ✅ 可以复用现有的 `check_continuous_volume`、`load_whitelist` 等函数
- ✅ 性能足够（2年数据约500个交易日，假设白名单200只股票，总共10万次检查，完全可以接受）
- ✅ 灵活性高，后续可以轻松调整为"持有5天"、"加入止损"等策略
- ✅ 输出完整的统计指标和可视化图表

---

**文档版本**: v1.0  
**创建时间**: 2026-04-25  
**作者**: Lingma Assistant
