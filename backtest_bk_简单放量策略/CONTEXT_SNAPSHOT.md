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

### 5. **🆕 股票池评分系统（2026-05-03）**
**文件**: [`backtest/score_stockpool.py`](file://e:\LearnPY\Projects\StockBot\backtest\score_stockpool.py)

**功能**：为股票池中的每只股票计算综合评分

**核心特性**：
- ✅ 支持单日和批量评分
- ✅ 评分结果格式：`股票代码,评分`（如 `603768,2.5`）
- ✅ **备份控制**：默认不生成备份文件，通过 `--backup` 参数显式启用
- ✅ 输出详细的进度和统计信息

**使用示例**：
```bash
# 单日期评分（不生成备份）
python backtest/score_stockpool.py --date 2024-01-15

# 批量评分（指定日期范围）
python backtest/score_stockpool.py --start-date 2024-01-01 --end-date 2024-01-10

# 需要生成备份时
python backtest/score_stockpool.py --date 2024-01-15 --backup
```

**技术细节**：
- [append_scores_to_file()](file://e:\LearnPY\Projects\StockBot\backtest\score_stockpool.py#L257-L304) - 追加评分到文件，支持备份控制
- [batch_process()](file://e:\LearnPY\Projects\StockBot\backtest\score_stockpool.py#L306-L359) - 批量处理多个日期
- 备份文件命名：`stockpool_YYYYMMDD.txt.bak`

---

### 6. **🆕 回测收益率计算工具（2026-05-03）**
**文件**: [`backtest/calc_backtest_rate.py`](file://e:\LearnPY\Projects\StockBot\backtest\calc_backtest_rate.py)

**功能**：基于评分过滤后的股票池，计算单日或区间收益率

**评分过滤机制**：
- ✅ 从 [config.yaml](file://e:\LearnPY\Projects\StockBot\config.yaml) 读取 `backtest_minscore` 配置项
- ✅ **严格过滤**：无评分数据的股票直接过滤掉
- ✅ **阈值过滤**：评分 < `backtest_minscore` 的股票过滤掉
- ✅ 输出详细的过滤统计（总数、通过数、过滤原因）

**计算模式**：
1. **单日收益率**：当日开盘买入，收盘卖出
2. **区间收益率**：起始日开盘买入，结束日收盘卖出

**资金使用率诊断**：
- ⚠️ <80%：警告，存在较多闲置资金，提供优化建议
- ℹ️ 80-95%：提示，正常现象（100股整数倍限制）
- ✅ >95%：良好

**使用示例**：
```bash
# 计算单日收益率
python backtest/calc_backtest_rate.py --date 2026-04-20 --pooldate 20260420

# 计算区间收益率
python backtest/calc_backtest_rate.py --start 2026-04-20 --end 2026-04-22 --pooldate 20260420

# 同时计算单日和区间收益
python backtest/calc_backtest_rate.py --date 2026-04-20 --start 2026-04-20 --end 2026-04-22 --pooldate 20260420

# 自定义初始资金
python backtest/calc_backtest_rate.py --date 2026-04-20 --pooldate 20260420 --capital 200000
```

**输出报告**：
- 📊 个股详情（代码、名称、开盘价、收盘价、买入股数、投入金额、收益率、盈亏）
- 💰 汇总报告（总投入、总市值、综合收益率、总盈亏）
- 💹 资金使用率诊断（初始资金、实际投入、闲置资金、使用率、优化建议）
- 📋 详细数据表（按收益率排序）
- 🏆 最佳/最差表现

**技术细节**：
- [load_stock_pool()](file://e:\LearnPY\Projects\StockBot\backtest\calc_backtest_rate.py#L54-L147) - 加载股票池并应用评分过滤
- [calculate_single_day_returns()](file://e:\LearnPY\Projects\StockBot\backtest\calc_backtest_rate.py#L362-L463) - 单日收益率计算
- [calculate_period_returns()](file://e:\LearnPY\Projects\StockBot\backtest\calc_backtest_rate.py#L465-L593) - 区间收益率计算
- 严格遵守A股100股整数倍限制
- 自动保存报告到 `data/report_*.txt`

---

### 7. **🆕 沪深300数据增量更新（2026-05-03）**
**文件**: [`backtest/update_hs300_data.py`](file://e:\LearnPY\Projects\StockBot\backtest\update_hs300_data.py)

**优化内容**：从全量更新改为增量更新模式

**智能日期确定**：
- ✅ 未指定 [start_date](file://e:\LearnPY\Projects\StockBot\backtest\backtest_engine.py#L0-L0)：自动读取本地文件最新日期+1天
- ✅ 未指定 [end_date](file://e:\LearnPY\Projects\StockBot\backtest\backtest_engine.py#L0-L0)：默认为今天
- ✅ 首次运行：自动获取完整历史数据（2020-01-01至今）

**数据合并策略**：
- ✅ 自动备份旧文件（时间戳命名）
- ✅ 合并新旧数据并按日期去重
- ✅ 保留最新记录，避免重复

**使用示例**：
```bash
# 增量更新（最常用）
python backtest/update_hs300_data.py

# 指定日期范围
python backtest/update_hs300_data.py --start 2026-04-01 --end 2026-04-30

# 重新获取完整历史数据
python backtest/update_hs300_data.py --start 2020-01-01
```

**性能提升**：
- ⚡ 日常更新：从几分钟降至几秒（只下载新增数据）
- 💾 数据安全：自动备份，支持回滚
- 🔄 灵活控制：支持任意日期范围

**技术细节**：
- [update_hs300_data()](file://e:\LearnPY\Projects\StockBot\backtest\update_hs300_data.py#L23-L188) - 主函数，支持增量更新
- 命令行参数：`--start`、`--end`
- 数据源：东方财富网API

---

### 8. **🆕 白名单智能加载（2026-05-03）**
**文件**: [`local/utils.py`](file://e:\LearnPY\Projects\StockBot\local\utils.py) - [load_whitelist()](file://e:\LearnPY\Projects\StockBot\local\utils.py#L632-L672)

**优化内容**：支持自动回退到最近的白名单文件

**加载策略**：
1. ✅ 优先使用 `data/whitelist_当天日期.txt`
2. ✅ 如果不存在，自动查找并使用最新的白名单文件
3. ✅ 完全没有则返回空集合并提示用户生成

**辅助函数**：
- [_find_latest_whitelist()](file://e:\LearnPY\Projects\StockBot\local\utils.py#L577-L604) - 查找最新的白名单文件
- [_load_whitelist_file()](file://e:\LearnPY\Projects\StockBot\local\utils.py#L607-L629) - 加载单个白名单文件

**适用场景**：
- 📅 **周末/节假日运行**：自动使用最近交易日的白名单
- 🔄 **跨天运行**：凌晨运行时自动使用前一天的白名单
- ⚠️ **数据缺失**：某天忘记生成白名单，自动回退到最近可用数据

**输出示例**：
```
[WARNING] 指定日期白名单不存在: whitelist_20260503.txt
[INFO] 正在查找最近的白名单文件...
[OK] 使用最近白名单: 20260430
[LOAD] 加载白名单 (20260430): 4500 只股票
[PATH] 文件路径: E:\LearnPY\Projects\StockBot\data\whitelist_20260430.txt
```

**优势**：
- ✅ 避免降级到慢速扫描模式
- ✅ 透明提示，清晰显示使用的白名单日期和路径
- ✅ 向后兼容，不影响现有代码调用

---

### 9. **🆕 修复沪深300数据路径问题（2026-05-03）**
**文件**: 
- [`backtest/backtest_engine.py`](file://e:\LearnPY\Projects\StockBot\backtest\backtest_engine.py)
- [`backtest/update_hs300_data.py`](file://e:\LearnPY\Projects\StockBot\backtest\update_hs300_data.py)

**问题**：原代码使用相对路径 `Path("data/hs300_eastmoney.csv")`，导致从当前工作目录查找文件

**影响**：
- ❌ 在项目根目录运行：`python backtest/run_backtest.py` ✅ 正常
- ❌ 在其他目录运行：`cd .. && python backtest/run_backtest.py` ❌ 找不到文件

**修复方案**：改为使用项目根目录的绝对路径
```python
project_root = Path(__file__).parent.parent
csv_file = project_root / "data" / "hs300_eastmoney.csv"
```

**优势**：
- ✅ 无论从哪个目录运行脚本，都能正确定位到数据文件
- ✅ 跨平台兼容（Windows/Linux）
- ✅ 与项目中其他模块的路径处理方式保持一致

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

### 🆕 新增工具
- `backtest/score_stockpool.py` - 股票池评分工具
- `backtest/calc_backtest_rate.py` - 回测收益率计算工具
- `backtest/update_hs300_data.py` - 沪深300数据更新工具（增量更新）

### 数据源
- `data/hs300_eastmoney.csv` - 沪深300历史数据（1529条，2020-2026）

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
✅ 🆕 股票池评分系统（支持备份控制）  
✅ 🆕 回测收益率计算工具（评分过滤 + 资金使用率诊断）  
✅ 🆕 沪深300数据增量更新（智能日期检测 + 自动合并）  
✅ 🆕 白名单智能加载（自动回退到最近文件）  
✅ 🆕 修复沪深300数据路径问题（项目根目录绝对路径）  

### 待验证
⏳ 运行2021年全年回测，验证总收益率是否为-6.7%左右

### 使用命令
```bash
# 短期回测（推荐测试）
python backtest/run_backtest.py --start-date 2025-10-01 --end-date 2026-04-27 --hold-days 3

# 长期回测（2021全年）
python backtest/run_backtest.py --start-date 2021-01-01 --end-date 2021-12-31 --hold-days 3

# 生成股票池评分
python backtest/score_stockpool.py --start-date 2024-01-01 --end-date 2026-01-01

# 计算回测收益率
python backtest/calc_backtest_rate.py --date 2026-04-20 --pooldate 20260420

# 更新沪深300数据（增量更新）
python backtest/update_hs300_data.py
```

---

## 💡 注意事项

1. **数据完整性**：确保 `data/hs300_eastmoney.csv` 存在且包含回测周期数据
2. **白名单文件**：确保 `data/whitelist_*.txt` 存在（可通过 `python local/manage_stock_list.py --update` 生成）
3. **通达信路径**：配置正确的通达信安装目录（默认 `D:\Install\zd_zxzq_gm`）
4. **100股限制影响**：高价股可能导致资金闲置，这是正常现象
5. **评分过滤**：回测收益率计算会自动过滤低分股票，确保只有优质股票参与回测
6. **增量更新**：定期运行 `update_hs300_data.py` 保持沪深300数据最新（建议每周一次）
7. **白名单回退**：周末/节假日运行时，系统会自动使用最近交易日的白名单，无需手动干预

---

**最后更新时间**：2026-05-03  
**核心成果**：实现了准确的交易周期收益率计算，支持完整的沪深300对比分析，新增股票池评分系统、回测收益率计算工具、沪深300增量更新、白名单智能加载等功能
