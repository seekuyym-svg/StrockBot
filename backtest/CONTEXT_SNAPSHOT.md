# StockBot 回测系统优化 - 上下文快照

## 📋 项目背景
StockBot A股智能监控系统中的**回测模块**，用于验证"持续放量选股策略"的历史表现。

---

## ✅ 已完成的优化内容

### 1. **沪深300基准数据获取优化**
- **问题**：原akshare接口不稳定，腾讯财经API只能获取最近320天数据
- **解决方案**：
  - 从**东方财富网API**获取完整历史数据（2020年至今，1529条记录）
  - 保存到本地CSV文件：`data/hs300_eastmoney.csv`
  - 回测引擎优先使用本地CSV，降级到腾讯财经API
- **相关文件**：
  - `backtest/backtest_engine.py` - [get_benchmark_data()](file://e:\LearnPY\Projects\StockBot\backtest\backtest_engine.py#L378-L431), [_load_hs300_from_csv()](file://e:\LearnPY\Projects\StockBot\backtest\backtest_engine.py#L433-L463)
  - `backtest/update_hs300_data.py` - 数据更新脚本
  - `data/hs300_eastmoney.csv` - 本地历史数据文件

---

### 2. **收益率计算逻辑修正（交易周期模式）**
- **问题**：原代码未考虑A股100股整数倍限制，导致收益率计算错误（-95% vs 实际-6.7%）
- **核心概念**：**交易周期** = 选股日 → 次日买入 → 持有N天卖出
- **计算流程**：
  1. 期初资金A平均分配到选中股票池
  2. **关键约束**：每只股票买入股数必须是**100的整数倍**（向下取整）
  3. 持仓N天后卖出，得到期末资金B
  4. B成为下一周期的期初资金（复利效应）
  5. 总收益率 = `(最终期末资金C - 初始资金A) / A × 100%`
- **相关方法**：
  - [_calculate_daily_portfolio_value()](file://e:\LearnPY\Projects\StockBot\backtest\backtest_engine.py#L689-L753) - 基于交易周期计算组合价值
  - [calculate_metrics()](file://e:\LearnPY\Projects\StockBot\backtest\backtest_engine.py#L816-L966) - 计算总收益率、最大回撤等指标
  - [calculate_cycle_metrics()](file://e:\LearnPY\Projects\StockBot\backtest\backtest_engine.py#L755-L814) - 计算每个周期的详细指标（新增）

---

### 3. **回测报告优化（沪深300对比展示）**
- **优化内容**：在回测总结中突出显示策略与沪深300的收益对比
- **报告结构**：
  ```
  💰 收益对比分析
    【策略表现】总收益率、年化收益率
    【沪深300基准】区间收益率、年化收益率
    【对比结果】✅跑赢/❌跑输 + 超额收益
    收益率对比图：[███] 可视化条形图
  
  ⚠️ 风险指标
    胜率、夏普比率、最大回撤、盈亏比
  
  📈 交易统计
    总交易次数、平均收益、最佳/最差交易
  ```
- **相关文件**：
  - `backtest/backtest_reporter.py` - [_print_text_report()](file://e:\LearnPY\Projects\StockBot\backtest\backtest_reporter.py#L138-L220) 重构
  - `backtest/backtest_engine.py` - [generate_report()](file://e:\LearnPY\Projects\StockBot\backtest\backtest_engine.py#L980-L997) 传递预计算指标

---

### 4. **配置灵活性增强**
- **持仓天数**：通过 `--hold-days N` 参数灵活配置（默认3天）
- **配置文件**：[config.yaml](file://e:\LearnPY\Projects\StockBot\config.yaml) 中添加 `backtest` 节点
- **优先级**：命令行参数 > config.yaml > 硬编码默认值

---

## 🔧 核心技术规范

### A股交易规则
```python
# 计算理论可买股数
theoretical_shares = int(capital_per_stock / buy_price)

# 向下取整到100的倍数
actual_shares = (theoretical_shares // 100) * 100

# 不足100股则无法买入
if actual_shares < 100:
    actual_investment = 0
else:
    actual_investment = actual_shares * buy_price
```

### 交易周期资金流转
```
初始资金 A
  ↓
【周期1】期初A → 平均分配 → 买入(100股倍数) → 卖出 → 期末B1
  ↓
【周期2】期初B1 → 平均分配 → 买入(100股倍数) → 卖出 → 期末B2
  ↓
...
  ↓
【周期N】期初B(N-1) → ... → 期末C
  
总收益率 = (C - A) / A × 100%
```

### 选股频率匹配
- **规则**：选股间隔 = 持仓天数
- **实现**：`if idx % hold_days == 0: 执行选股`
- **时间线**：Day N选股 → Day N+1买入 → Day N+M卖出 + 同时选股 → Day N+M+1买入新股票

---

## 📁 关键文件清单

### 核心引擎
- `backtest/backtest_engine.py` - 回测引擎主类（已优化）
- `backtest/backtest_reporter.py` - 报告生成器（已优化）
- `backtest/run_backtest.py` - 回测入口脚本

### 数据源
- `data/hs300_eastmoney.csv` - 沪深300历史数据（1529条，2020-2026）
- `backtest/update_hs300_data.py` - 数据更新工具

### 测试脚本
- `backtest/test_cycle_calculation.py` - 交易周期计算验证
- `backtest/test_report_benchmark.py` - 报告对比展示测试
- `backtest/test_hs300_sources.py` - 数据源对比测试

### 文档
- `backtest/CYCLE_BASED_RETURN_CALCULATION.md` - 交易周期计算规范
- `backtest/HS300_LOCAL_CSV_SOLUTION.md` - 沪深300本地CSV方案
- `backtest/REPORT_BENCHMARK_COMPARISON.md` - 报告对比优化说明
- `backtest/RETURN_CALCULATION_FIX.md` - 收益率计算修正说明

---

## 🎯 当前状态

### 已完成
✅ 沪深300数据获取（东方财富网 + 本地CSV）  
✅ 交易周期收益率计算（含100股限制）  
✅ 回测报告沪深300对比展示  
✅ 持仓天数灵活配置  

### 待验证
⏳ 运行2021年全年回测，验证总收益率是否为-6.7%左右

### 使用命令
```bash
# 短期回测（推荐测试）
python backtest/run_backtest.py --start-date 2025-10-01 --end-date 2026-04-27 --hold-days 3

# 长期回测（2021全年）
python backtest/run_backtest.py --start-date 2021-01-01 --end-date 2021-12-31 --hold-days 3

# 更新沪深300数据
python backtest/update_hs300_data.py
```

---

## 💡 注意事项

1. **数据完整性**：确保 `data/hs300_eastmoney.csv` 存在且包含回测周期数据
2. **白名单文件**：确保 `data/whitelist_*.txt` 存在（可通过 `python local/manage_stock_list.py --update` 生成）
3. **通达信路径**：配置正确的通达信安装目录（默认 `D:\Install\zd_zxzq_gm`）
4. **100股限制影响**：高价股可能导致资金闲置，这是正常现象

---

**最后更新时间**：2026-04-27  
**核心成果**：实现了准确的交易周期收益率计算，支持完整的沪深300对比分析
